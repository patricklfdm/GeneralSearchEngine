"""Independent full-size rich guest qualification. Does not admit cloud execution."""
import argparse
import gzip
import json
import re
from pathlib import Path
from . import cloud_workload_contract as contract,performance_plan as plan,performance_model as m
from . import performance_evidence as old,performance_physical as physical,performance_semantics as semantic
from . import remote_schedule_evidence as scheduling,remote_command as command
from .remote_rich_physical import Calls
from .remote_trace import Decoder
from .remote_rich_plan import CELLS, SHARDS, MODES
from . import performance_artifacts as artifacts, storage_inspector as storage, remote_collection


class EvidenceLocation(artifacts.EvidenceLocation):
    def __init__(self,root,original):
        self.root=Path(root).resolve();self.original=Path(original);self.index=None
        m.need(self.original.is_absolute() and '..' not in self.original.parts,'original rich evidence root')
        if self.root!=self.original:
            index=self.root/remote_collection.INDEX
            self.index=command.read(index)
            actual={p:dict(bytes=v['size'],sha256=v['sha256']) for p,v in storage.inventory(self.root).items() if p!=remote_collection.INDEX}
            m.need(self.index==actual,'relocated rich inventory differs')


def evidence_location(root,execution):
    original_roots={artifacts.recorded_path(a['path']).parent.parent
                    for adapter in execution['adapters'].values() for a in adapter['artifacts']}
    m.need(len(original_roots)==1,'mixed rich evidence roots')
    return EvidenceLocation(root,next(iter(original_roots)))


def lines(root,name,budget=None):
    base=Path(root)/(name+'.jsonl')
    compressed=base.with_name(base.name+'.gz')
    use_gzip=compressed.exists()
    suffix='.jsonl.gz' if use_gzip else '.jsonl'
    parts=[compressed if use_gzip else base,*sorted(base.parent.glob(name+'-part*'+suffix))]
    other='.jsonl' if use_gzip else '.jsonl.gz'
    m.need(not (base.parent/(name+other)).exists() and not list(base.parent.glob(name+'-part*'+other)),'mixed trace encodings')
    rows=[];total=0;decoder=Decoder(budget)
    for i,path in enumerate(parts):
        wanted=base.parent/(name+('' if i==0 else f'-part{i:04d}')+suffix)
        m.need(path==wanted and path.is_file() and not path.is_symlink(),'cloud stream segment identity')
        size=path.stat().st_size;total+=size
        m.need(size<=32<<20 and total<=128<<20,'cloud stream size/completeness')
        with (gzip.open(path,'rb') if use_gzip else path.open('rb')) as stream:
            expanded=0;count=0
            while True:
                line=stream.readline((4<<20)+1)
                if not line:break
                expanded+=len(line);count+=1
                m.need(len(line)<=4<<20 and line.endswith(b'\n') and expanded<=32<<20,'cloud stream expansion/completeness')
                rows.append(decoder.row(m.strict_json(line),len(line)))
            m.need(count>0,'empty cloud stream')
    return rows


def calls(rows,cell,preset):
    wanted=list(contract.program(contract.load(),cell,preset))
    m.need(len(rows)==len(wanted) and len({r['opId'] for r in rows})==len(rows),'cloud call coverage')
    state=m.initial(plan.load())
    for ordinal,(row,want) in enumerate(zip(rows,wanted),1):
        m.need(row['ordinal']==ordinal and row['outcome']=='SUCCESS','cloud call outcome/order')
        m.need(all(row[k]==want[k] for k in ('window','cycle','operation','keys','lane')) and
               row['payloadSha256']==m.sha(want['payload']),'changed cloud request')
        m.need(m.sha(m.canonical(row['answer']))==row['answerSha256'],'cloud result digest')
        m.need(0<=row['apiStartNanos']<row['apiEndNanos'] and row['apiEndNanos']-row['apiStartNanos']<=9600*10**6,'API timing/deadline')
        if cell=='healthy':
            if want['operation'] in m.OP_IDS:state.apply(m.OP_IDS[want['operation']],want['payload'])
            else:m.need(row['answer']==state.answer(want['operation'],want['cycle']),'healthy read semantics')
            m.need(row['afterSequence']==state.sequence,'healthy sequence')
    if cell!='healthy':
        # This is only the static final projection, never the oracle for a concurrent read.
        for want in wanted:
            if want['operation'] in m.OP_IDS:state.apply(m.OP_IDS[want['operation']],want['payload'])
    return state


def process(root,node,mode,adapter,windows,budget=None):
    record=old.read(root/(node+'-process.json'));identity=record['ready']['identity']
    m.need(record['cleanup']=='reaped' and record['exitCode']==0 and record['forced'] is False,'guest process cleanup')
    m.need(identity['pid']==record['pid'] and identity['node']==node and identity['mode']==mode and identity['generation']==1,'guest process identity')
    m.need(identity['javaMajor']==21 and identity['processors']==2 and identity['jvmArguments']==plan.load()['jvmArguments'],'guest JVM configuration')
    m.need(identity['planFileSha256']==m.sha((root.parent/'plan.json').read_bytes()),'guest loaded local plan')
    m.need(record['args'][6]==adapter['cp'],'guest isolated classpath')
    for kind,artifact in zip(('core','replication'),adapter['artifacts']):
        path=artifacts.retained(root.parent,artifact['path'],artifact['sha256'])
        m.need(identity[kind+'Source']==artifact['path'] and identity[kind+'Sha256']==artifact['sha256'],'loaded artifact identity')
        if mode!='candidate-v5.1-automatic':
            pinned=next(p for p in plan.load()['publishedControls']['artifacts'] if path.name==p['artifact']+'-'+p['version']+'.jar')
            m.need(pinned['sha256']==artifact['sha256'],'published control pin')
    original=lines(root,node+'-results',budget);by_id={r['opId']:r for r in original}
    m.need(len(by_id)==len(original)==len(record['exchanges']),'missing/duplicate guest response')
    for exchange in record['exchanges']:
        response=by_id[exchange['request']['opId']]
        m.need(response==exchange['response'] and response['outcome']=='SUCCESS' and response['pid']==record['pid'] and
               response['node']==node and response['command']==exchange['request']['command'],'guest response binding')
        m.need(record['startNanos']<=exchange['startNanos']<=exchange['endNanos']<=record['endNanos'],'controller exchange timing')
        m.need(response['workerStartNanos']<=response['workerEndNanos'],'guest exchange timing')
        if response['command']=='call':
            call=response['call']
            m.need(response['workerStartNanos']<=call['apiStartNanos']<call['apiEndNanos']<=response['workerEndNanos'],'API outside original guest interval')
    m.need(original[-1]['command']=='close','guest orderly close')
    raw_samples=lines(root,node+'-samples',budget)
    m.need(all(0<=s['localNanos']-s['samplingStartNanos']<=9600*10**6 for s in raw_samples),'guest sampling deadline')
    for sample in raw_samples:
        if mode=='candidate-v5.1-automatic':
            m.need(type(sample['queues']['maintenancePending']) is int and sample['queues']['maintenancePending'] in (0,1) and
                   (sample['boundary']!='closed' or sample['queues']['maintenancePending']==0),'deferred maintenance bound/drain')
        writer=sample['evidenceWriter']
        m.need(0<=writer['queuedBytes']<=writer['peakBytes']<=16<<20 and
               0<=writer['queuedRecords']<=writer['peakRecords']<=256,'evidence writer queue bounds')
    trace_bytes=sum(p.stat().st_size for p in root.glob(node+'-*.jsonl*'))
    m.need(trace_bytes<=contract.load()['evidence']['perNodePerCellTraceBytes'],'node/cell trace budget')
    samples=old.resources(raw_samples,mode,node,record,windows)
    return record,samples,by_id


def cell(root,row,adapter,preset,location=None,budget=None):
    budget=budget if budget is not None else [contract.load()['evidence']['traceBytes']]
    mode,name=row['mode'],row['cell']
    m.need(row['directory']==name+'-'+mode,'rich cell directory identity')
    directory=root/row['directory']
    observed=old.read(directory/'calls.json');final=calls(observed,name,preset)
    receipt_windows=old.read(directory/'windows.json');window_names=[w['window'] for w in receipt_windows]
    nodes=['local'] if mode=='published-v4.4-local' else ['node-1','node-2','node-3']
    traces={};resources={};responses={};records={}
    for node in nodes:
        record,resources[node],results=process(directory,node,mode,adapter,window_names,budget)
        responses.update(results);records[node]=record
        if node!='local':
            traces[node]=lines(directory,node+'-trace',budget);old.trace_identity(traces[node],record)
    if len(nodes)>1:
        m.need(max(r['readyNanos'] for r in records.values())<min(r['endNanos'] for r in records.values()),'serial stand-in for voters')
    m.need(row['active'] in nodes and all(c['node']==row['active'] and c['pid']==records[row['active']]['pid'] for c in observed),'rich active worker')
    expected_windows=['warmup',*contract.load()['healthy']['windows']] if name=='healthy' else [name]
    m.need(window_names==expected_windows,'rich window order/coverage')
    for call in observed:
        response=responses[call['opId']]
        m.need(response['command']=='call' and all(call[k]==v for k,v in response['call'].items()),'controller call differs from original JVM response')
    timings=[]
    previous_end=row['startNanos']
    for window in receipt_windows:
        m.need(re.fullmatch('[0-9a-f]{32}',window['commandId']) is not None,'window command ID')
        path=directory/window['window']
        spec=old.read(path/'spec.json');result=old.read(path/'result.json')
        m.need((spec['cell'],spec['preset'],spec['window'])==(name,preset,window['window']),'window identity differs from cell')
        m.need(previous_end<=result['startedNanos']<result['endedNanos']<=row['endNanos'],'cell/window clock order')
        previous_end=result['endedNanos']
        timings.append(dict(window=window['window'],startNanos=result['startedNanos'],endNanos=result['endedNanos']))
        events=lines(path,'arrivals',budget)
        m.need(scheduling.validate(spec,events,result)['status']=='PASS','guest arrival schedule failure')
        owner=row['binding'];store=command.CommandStore(directory/'commands',owner)
        request=command.read(store.root/'commands'/window['commandId']/'request.json')
        m.need(request['command']=='window' and request['payload']==dict(cell=name,preset=preset,window=window['window']),'wrong window command')
        receipt=store.query(request)
        m.need(receipt['state']=='SUCCEEDED' and receipt['requestSha256']==window['requestSha256'] and
               receipt==old.read(path/'receipt.json'),'durable guest window receipt')
        returned=receipt['result'].copy();returned.pop('validation')
        m.need(returned==result,'durable receipt changed scheduled outcome')
        exchanges={e['request']['opId']:e for r in records.values() for e in r['exchanges']}
        expected_calls={c['ordinal']:c for c in spec['calls']}
        for call in result['calls']:
            response=responses[call['result']['opId']]
            exchange=exchanges[response['opId']]
            m.need(all(exchange['request'][k]==v for k,v in expected_calls[call['ordinal']].items()),'arrival/request differs from frozen call')
            m.need(call['invokedNanos']<=exchange['startNanos']<=exchange['endNanos']<=call['endedNanos'],'exchange outside scheduled callback')
            m.need(call['result']['resultSha256']==m.sha(m.canonical(response)),'arrival/JVM result binding')
        if name!='healthy':
            apis=[r for r in observed if r['window']==window['window']]
            m.need(any(a['apiStartNanos']<b['apiStartNanos']<a['apiEndNanos'] for a in apis for b in apis if a['lane']!=b['lane']), 'missing real concurrent Java API overlap')
    if mode=='candidate-v5.1-automatic':
        proof=physical.automatic(directory,observed,traces,evidence_location=location,cloud_calls=Calls(observed))
    elif mode=='published-v5.0-configured':
        proof=old.configured_physical(directory,observed,traces,final_sequence=final.sequence)
    else:
        proof=semantic.selected_checkpoint(directory/'store',final)
    backup=None if mode=='published-v4.4-local' else semantic.source_backup(directory/'export',final)
    restored=directory/'restored-check'
    m.need(old.read(restored/'restore.json')['exitCode']==0,'public restore process failed')
    semantic.state_observation(old.read(restored/'restore.stdout'),final)
    limit=300 if name=='healthy' else next(v['seconds'] for v in contract.load()['cells'] if v['name']==name)
    m.need(0<=row['endNanos']-row['startNanos']<=limit*10**9,'rich cell wall ceiling')
    distributions={op:old.distribution([c['apiEndNanos']-c['apiStartNanos'] for c in observed if c['operation']==op and c['window']!='warmup'])
                   for op in m.OPERATIONS if any(c['operation']==op and c['window']!='warmup' for c in observed)}
    measurements=None
    if name=='healthy':
        paired={e['request']['opId']:(r,e) for r in records.values() for e in r['exchanges']}
        manifest=None
        if mode=='candidate-v5.1-automatic':
            encoded=(directory/'node-1/manifest.gsr').read_bytes()
            manifest=dict(physical.f.inspect(encoded,'MANIFEST'),digest=encoded[16:48].hex())
        measurements=old.timing(observed,timings,paired,traces,manifest)
    return dict(status='PASS',cell=name,mode=mode,calls=len(observed),physical=proof,resources=resources,
                finalBackup=backup,latency=distributions,measurements=measurements)


def coverage(root,execution,expected):
    m.need(tuple((v['cell'],v['mode']) for v in execution['cells'])==tuple(expected),
           'incomplete three-mode/concurrent rich coverage')
    present={name+'-'+mode for name,mode in CELLS if (root/(name+'-'+mode)).exists()}
    m.need(present=={name+'-'+mode for name,mode in expected},'unexpected rich cell directory')


def header(root,expected=CELLS):
    root=Path(root).resolve();execution=old.read(root/'execution.json')
    m.need(execution['status']=='EXECUTED' and not execution['cleanupErrors'] and execution['paidCloud'] is False and
           execution['execution']=='local-guest-rich-workload-only','rich execution receipt')
    contract.validate(old.read(root/'cloud-plan.json'));plan.validate(old.read(root/'plan.json'))
    m.need(execution['evidenceWriterChecks']==[dict(status='PASS',case=k,execution='evidence-writer-check-only')
           for k in ('bound-count','bound-bytes','write-failure')],'evidence writer qualification')
    for checked in execution['evidenceWriterChecks']:
        label='writer-'+checked['case']
        m.need(old.read(root/(label+'.json'))['exitCode']==0 and old.read(root/(label+'.stdout'))==checked,
               'missing original writer check result')
    source_inventory=old.read(root/'source-inventory.json')
    m.need(m.sha((root/'source-inventory.json').read_bytes())==execution['sourceInventorySha256'],'source inventory binding')
    pinned={a['artifact']+'-'+a['version']+'.jar':a['sha256'] for a in plan.load()['publishedControls']['artifacts']}
    location=evidence_location(root,execution)
    for mode,adapter in execution['adapters'].items():old.artifacts(root,mode,adapter,pinned,source_inventory)
    m.need(storage.inventory(root/'source')==old.read(root/'source-before.json')==old.read(root/'source-after.json'),'rich source changed')
    semantic.source_backup(root/'source',m.initial(plan.load()))
    coverage(root,execution,expected)
    return execution,location


def validate_rows(root,execution,location,budget):
    results=[]
    for row in execution['cells']:
        m.need(row['binding']['source']==execution['source'] and row['binding']['bundleSha256']==m.sha(m.canonical(execution['adapters'][row['mode']])),'cell source/adapter binding')
        result=cell(root,row,execution['adapters'][row['mode']],execution['preset'],location,budget);results.append(result)
        print(json.dumps(dict(cell=row['cell'],mode=row['mode'],status='PASS')),flush=True)
    return results


def validate(root):
    root=Path(root).resolve();execution,location=header(root)
    results=validate_rows(root,execution,location,[contract.load()['evidence']['traceBytes']])
    return dict(status='PASS',execution='local-guest-rich-workload-only',paidCloud=False,fullRemoteQualification=False,cells=results)


def validate_partial(root,shard):
    m.need(shard in SHARDS,'unknown rich shard')
    root=Path(root).resolve();execution,location=header(root,SHARDS[shard])
    m.need(execution['preset']=='canonical','shard must retain canonical windows')
    results=validate_rows(root,execution,location,[contract.load()['evidence']['traceBytes']])
    return dict(status='PARTIAL',shard=shard,paidCloud=False,fullRemoteQualification=False,cells=results)


def common_identity(root,execution):
    """Compare byte identities, never cross-host PIDs/paths/monotonic clocks."""
    root=Path(root)
    m.need(set(execution['adapters'])==set(MODES),'rich adapter mode coverage')
    return dict(source=execution['source'],sourceInventorySha256=execution['sourceInventorySha256'],
                plans={name:m.sha((root/name).read_bytes()) for name in ('plan.json','cloud-plan.json')},
                seed=storage.inventory(root/'source'),
                adapters={mode:dict(artifacts={Path(a['path']).name:a['sha256'] for a in adapter['artifacts']},
                                    classes=adapter['classes'],sources=adapter['sources'])
                          for mode,adapter in execution['adapters'].items()})


def validate_group(roots):
    m.need(set(roots)==set(SHARDS),'missing or extra rich shard')
    checked={name:header(roots[name],SHARDS[name]) for name in SHARDS}
    identities=[common_identity(roots[name],checked[name][0]) for name in SHARDS]
    m.need(all(i==identities[0] for i in identities),'mixed rich shard source/seed/artifact identity')
    m.need(all(e['preset']=='canonical' for e,_ in checked.values()),'shard must retain canonical windows')
    # One shared expansion budget, exactly as in the original serial validation.
    budget=[contract.load()['evidence']['traceBytes']];results=[]
    for name in SHARDS:
        execution,location=checked[name]
        results.extend(validate_rows(Path(roots[name]),execution,location,budget))
    m.need(tuple((r['cell'],r['mode']) for r in results)==CELLS,'aggregate rich coverage/order')
    return dict(status='PASS',execution='local-guest-rich-workload-only',paidCloud=False,
                fullRemoteQualification=False,cells=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args()
    result=validate(args.root)
    Path(args.root,'validation.json').write_bytes(m.canonical(result)+b'\n')
    print(m.canonical(result).decode())
