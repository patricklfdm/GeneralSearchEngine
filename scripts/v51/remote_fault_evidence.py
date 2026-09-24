"""Independent fault schedule, process, wire, durable authority and history replay."""
import argparse
from pathlib import Path, PurePosixPath
import tarfile
from . import performance_model as m, performance_plan as local, cloud_workload_contract as contract
from . import public_history, public_qualification_evidence as physical, public_protocol_evidence as protocol
from . import storage_inspector as storage, runtime_evidence as a, remote_command as commands
from . import performance_artifacts as artifacts, performance_evidence as performance
from .remote_rich_evidence import EvidenceLocation

NODES=('node-1','node-2','node-3')


def read(path):
    path=Path(path)
    m.need(path.is_file() and not path.is_symlink() and path.stat().st_size<=4<<20,'fault JSON member bound/type')
    return m.strict_json(path.read_bytes())


def load_traces(root):
    traces={}
    for node in NODES:
        path=Path(root)/(node+'-trace.jsonl')
        m.need(path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=32<<20,'fault trace member bound/type')
        rows=[]
        with path.open('rb') as stream:
            while True:
                line=stream.readline((4<<20)+1)
                if not line:break
                m.need(len(line)<=4<<20 and line.endswith(b'\n'),'fault trace response bound/completeness')
                row=m.strict_json(line)
                m.need(row['node']==node and all(type(row[k]) is int and row[k]>0 for k in ('pid','generation','order','localNanos')),'fault trace process/counter types')
                rows.append(row)
        traces[node]=rows
    return traces


def expected_documents(tag,size=64):
    return [dict(id=tag+i,value=(f'tag-{tag+i}-'+'x'*size)[:size]) for i in (0,1)]


def accepted_outcome(op,capacity=False):
    if op['outcome']=='SUCCESS':return
    if op['outcome']=='PENDING':
        m.need(op['kind']=='addAll' and op.get('disconnectNanos') is not None,'unexplained disconnected call');return
    reason=op.get('reasonCode');kind=op['kind']
    reasons={'NOT_LEADER','NOT_READY','QUORUM_UNAVAILABLE','STALE_EPOCH','DEADLINE_EXCEEDED'}
    if capacity:reasons.update(('CAPACITY_EXCEEDED','STORAGE_FAILURE'))
    m.need(op['outcome']==('NOT_SUBMITTED' if kind=='addAll' else 'NOT_APPLICABLE') and reason in reasons or
           kind=='addAll' and op['outcome']=='INDETERMINATE' and reason in {'QUORUM_UNAVAILABLE','STALE_EPOCH','DEADLINE_EXCEEDED'},'unclassified fault response')


def archives(root,receipt,location):
    result={}
    for row in receipt['archives']:
        node=row['node'];generation=row['generation'];path=Path(row['path'])
        m.need(path.as_posix()==f'archives/{node}-g{generation}.tar.gz','archive relative identity')
        path=root/path;m.need(path.is_file() and not path.is_symlink() and path.stat().st_size<=32<<20 and m.sha(path.read_bytes())==row['sha256'],'archive identity/size')
        with tarfile.open(path) as tar:
            members=tar.getmembers()
            m.need(len(members)<=16000 and len({v.name for v in members})==len(members) and sum(v.size for v in members)<=256<<20,'archive size/count/duplicates')
            m.need(all((v.isdir() or v.isfile()) and 0<=v.size<=32<<20 and not PurePosixPath(v.name).is_absolute() and
                       '..' not in PurePosixPath(v.name).parts and v.name.split('/')[0]==node for v in members),'unsafe archive')
            files={v.name.removeprefix(node+'/'):tar.extractfile(v).read() for v in members if v.isfile()}
        m.need({k:dict(size=len(v),sha256=m.sha(v)) for k,v in files.items()}==row['inventory'],'archive inventory differs')
        for name in ('manifest.gsr','node.gsr','genesis.gsr','bootstrap-seal.gsr','bootstrap-prepared.gsr'):
            m.need(files[name]==(root/node/name).read_bytes(),'retained authority identity changed')
        stop=next(s for s in receipt['stops'] if s['node']==node and s['generation']==generation)
        start=next(s for s in receipt['starts'] if s['node']==node and s['generation']==generation+1)
        m.need(stop['endNanos']<=row['archivedNanos']<=start['startNanos'],'archive outside stopped/reopen interval')
        result[node,generation]=files
    return result


def schedule(history,receipt):
    case=receipt['case'];m.need(4<=len(history)<=24,'fault public-call cap')
    m.need([h['intentId'] for h in history]==[f'call-{n:02d}' for n in range(1,len(history)+1)],'undeclared call IDs')
    m.need([h['kind'] for h in history[:4]]==['addAll']*3+['read'] and all(h['outcome']=='SUCCESS' for h in history[:4]),'fault seed calls')
    for h,tag in zip(history,(10,20,30)):m.need(h['documents']==expected_documents(tag),'fault seed payload')
    m.need(history[3]['response']==receipt['seedRead'] and history[3]['node']==receipt['seedLeader'],'seed leader read binding')
    progress=receipt['progress'];reads=receipt['finalReads']
    m.need(1<=len(progress)<=4 and 1<=len(reads)<=4,'progress/read attempts')
    indexed={h['opId']:h for h in history};used=set(h['opId'] for h in history[:4])
    for i,pair in enumerate(progress):
        m.need(pair['tag']==100+i*10,'fresh progress tags')
        write,view=(indexed[pair[k]['opId']] for k in ('write','read'))
        m.need(write['kind']=='addAll' and write['documents']==expected_documents(pair['tag']) and view['kind']=='read','progress payload')
        m.need(pair['endNanos']-receipt['faultStartNanos']<=60*10**9,'progress pair deadline')
        m.need(pair['startNanos']<=write['startNanos']<=write['endNanos']<=view['startNanos']<=view['endNanos']<=pair['endNanos'],'progress call timing')
        for key,op in [('write',write),('read',view)]:
            m.need(op['response']==pair[key] and op['node']==pair['node'] and op['opId'] not in used,'progress original response')
            used.add(op['opId'])
    success=next((p for p in progress if all(p[k]['outcome']=='SUCCESS' for k in ('write','read'))),None)
    m.need(success is not None and 0<=success['endNanos']-receipt['faultStartNanos']<=60*10**9,'fault first progress deadline')
    for response in reads:
        op=indexed[response['opId']];m.need(op['kind']=='read' and op['response']==response and op['opId'] not in used,'final read binding');used.add(op['opId'])
    m.need(reads[-1]['outcome']=='SUCCESS','no final successful read')
    for op in history[4:]:
        accepted_outcome(op,case=='minority-capacity' and op['node']=='node-3')
        if op['opId'] in used:continue
        kind=op['kind']
        if kind in ('checkpoint','backup'):m.need(case=='maintenance' and op['outcome']=='SUCCESS','unexpected maintenance operation')
        elif op['opId'] in {r['opId'] for r in receipt.get('refusals',[])}:
            m.need(op['response'] in receipt['refusals'] and op['outcome']!='SUCCESS' and (kind!='addAll' or op['documents']==expected_documents(90)),'refusal changed')
        elif kind=='addAll':
            tags=(40,60) if case=='minority-capacity' else (40,)
            size=20000 if case=='minority-capacity' else 4096 if case=='interrupted-transfer' else 512 if case in ('entry-chosen','proof-quorum') else 64
            m.need(case in ('minority-capacity','interrupted-transfer','entry-chosen','proof-quorum','asymmetric-responses') and
                   any(op['documents']==expected_documents(tag,size) for tag in tags),'undeclared target write')
        else:m.need(case=='maintenance' and receipt['pinnedRead']==op['response'],'undeclared read')
    keys=[d['id'] for h in history if h['kind']=='addAll' for d in h['documents']]
    m.need(len(keys)==len(set(keys)),'mutation replay/duplicate keys')
    m.need(history[-1]['response']==reads[-1],'final read is not last public operation')
    return success


def validate_cell(root,adapter,location=None):
    root=Path(root);receipt=read(root/'receipt.json');history=read(root/'history.json');case=receipt['case']
    plan=contract.load();spec=next(c for c in plan['cells'][3:] if c['name']==case)
    m.need(read(root/'cloud-plan.json')==plan and read(root/'plan.json')==local.load(),'fault plan differs')
    m.need(receipt['status']=='EXECUTED' and not receipt['cleanupErrors'] and receipt['seconds']==spec['seconds'] and
           0<receipt['endNanos']-receipt['startNanos']<=spec['seconds']*10**9,'fault whole-cell budget/cleanup')
    declared=read(root/'declaration.json')
    m.need(declared==dict(case=case,seeds=[dict(tag=t,valueBytes=64) for t in (10,20,30)],targetTags=[40,60],progressTags=[100,110,120,130],
                         refusalTag=90,operationIds=[f'call-{n:02d}' for n in range(1,25)],maximumProgressPairs=4,maximumFinalReads=4,maximumPublicCalls=24),'changed predeclared fault branches')
    success=schedule(history,receipt)
    requests=[e for e in receipt['events'] if e['event']=='fault-request']
    m.need(len(requests)==1 and requests[0]['node']==receipt['seedLeader'] and requests[0]['controllerNanos']==receipt['faultStartNanos'] and
           history[3]['endNanos']<=receipt['faultStartNanos']<=receipt['endNanos'],'fault request timing/binding')
    traces=load_traces(root);starts=receipt['starts'];stops=receipt['stops']
    mapping={(s['node'],s['pid']):s['generation'] for s in starts}
    m.need(len(mapping)==len(starts)==len(stops) and len({s['pid'] for s in starts})==len(starts),'fault process identity coverage')
    m.need({s['node'] for s in starts if s['generation']==1}==set(NODES),'fault voter coverage')
    for start in starts:
        own=[r for r in traces[start['node']] if r['pid']==start['pid']]
        stop=next(s for s in stops if (s['node'],s['pid'],s['generation'])==(start['node'],start['pid'],start['generation']))
        m.need(receipt['startNanos']<=start['startNanos']<=start['readyNanos']<=stop['startNanos']<=stop['endNanos']<=receipt['endNanos'] and
               start['linuxStartTicks'].isdigit() and stop['exitCode']==(-9 if stop['kill'] else 0),'fault process lifetime')
        m.need([r['order'] for r in own]==list(range(1,len(own)+1)) and all(r['generation']==start['generation'] for r in own),'fault observer continuity')
        configurations=[r for r in own if r['event']=='FAULT_CONFIGURATION']
        m.need(len(configurations)==1,'fault configuration observation missing')
        expected=dict(plan['replicationBounds'],**{k:v for k,v in plan['automaticPolicy'].items() if k!='applyTo'})
        expected.update({k:plan['application'][k] for k in ('maxDocuments','maxBulkElements','maxEncodedKeyBytes','maxEncodedDocumentBytes','checkpointWalBytes','maxRetainedBytes','maxDerivedStateBytes')})
        expected['maxEncodedDocumentBytes']=spec.get('maxEncodedDocumentBytes',4096)
        if case=='minority-capacity' and start['node']=='node-3':expected['maxRetainedLogBytes']=128<<10
        m.need(all(configurations[0].get(k)==v for k,v in expected.items()),'fault sealed configuration drift')
        identities=[r for r in own if r['event']=='PERFORMANCE_IDENTITY'];m.need(len(identities)==1,'fault identity missing')
        identity=identities[0]
        m.need(identity['javaMajor']==21 and identity['processors']==2 and identity['jvmArguments']==plan['environment']['jvmArguments'] and
               identity['planFileSha256']==m.sha((root/'plan.json').read_bytes()) and identity['cloudPlanSha256']==contract.PLAN_SHA256 and
               start['args'][1:5]==plan['environment']['jvmArguments'] and start['args'][6]==adapter['cp'],'fault configuration identity')
        for key,artifact in zip(('core','replication'),adapter['artifacts']):
            artifacts.retained(root.parent,artifact['path'],artifact['sha256'])
            m.need(identity[key+'Source']==artifact['path'] and identity[key+'Sha256']==artifact['sha256'],'fault loaded artifact')
        samples=[r for r in own if r['event']=='PERFORMANCE_SAMPLE']
        m.need(samples and samples[0]['boundary']=='start' and (stop['kill'] or samples[-1]['boundary']=='closed'),'fault sample boundaries')
        m.need(sum(s['boundary']=='periodic' for s in samples)>=max(0,(samples[-1]['localNanos']-samples[0]['localNanos'])//10**9-1),'fault periodic samples missing')
        for s in samples:
            queues=s['queues']
            m.need(0<s['heapUsedBytes']<=s['heapMaxBytes']<=512<<20 and s['VmRSSBytes']>0 and s['threads']>0 and
                   0<=s['retainedBytes']<=128<<20 and 0<=queues['pinsBytes']<=64<<20 and 0<=queues['stagingBytes']<=64<<20,'fault resource bounds')
            m.need(0<=queues['admissionAvailable']<=4 and 0<=queues['inboundAvailable']<=8 and
                   all(0<=v['available']<=2 for v in queues['outboundAvailable']),'fault permit accounting')
            m.need(all(type(queues[k]) is int and 0<=queues[k]<=ceiling for k,ceiling in
                       [('orderedQueue',4),('deadlinesQueue',4),('inputsQueue',32),('completionsQueue',16),('networkQueue',4),('appQueue',4),('clientsQueue',2),
                        ('queuedBytes',64<<20),('authorityDiskBytes',128<<10 if case=='minority-capacity' and start['node']=='node-3' else 64<<20),('transferDiskBytes',64<<20),('maintenancePending',1)]),'fault queue/disk bounds')
            m.need(all(type(s[k]) is int and s[k]>=0 for k in ('gcCount','gcMillis','cpuNanos')) and
                   all(type(v) is int and v>=0 for v in s['processIo'].values()),'missing fault resource counter')
            if s['boundary']=='closed':m.need(queues['queuedBytes']==0 and queues['admissionAvailable']==4 and queues['inboundAvailable']==8 and all(v['available']==2 for v in queues['outboundAvailable']) and queues['maintenancePending']==0,'fault reservations not drained')
            m.need(0<=s['localNanos']-s['samplingStartNanos']<=9600*10**6,'fault sampling deadline')
        m.need((root/(start['node']+'-trace.jsonl')).stat().st_size<=32<<20,'fault trace member overflow')
    m.need(max(s['readyNanos'] for s in starts[:3])<receipt['faultStartNanos']<=min(s['startNanos'] for s in stops if s['generation']==1),'voters did not overlap before fault')
    for h in history:
        start=next(s for s in starts if s['pid']==h['pid'] and s['node']==h['node'])
        stop=next(s for s in stops if s['pid']==h['pid'])
        m.need(start['readyNanos']<=h['startNanos']<= (h['endNanos'] or h['disconnectNanos'])<=stop['endNanos'],'call outside lifetime')
    files=archives(root,receipt,location)
    logical=[h for h in history if h['kind'] in ('read','addAll')]
    proof=physical.physical(root,logical,traces,process_generations=mapping,evidence_location=location,require_restart=case in ('leader-loss','entry-chosen','proof-quorum','group-restart','interrupted-transfer','minority-capacity'))
    hist=public_history.check(logical)
    m.need(proof['chosen']<=512,'fault logical slot bound')
    noops=set()
    for rows in traces.values():
        for row in rows:
            if row['event']=='FORCE' and row['kind']=='ACCEPT':
                accepted=a.f.inspect(a.raw(row['record']),'ACCEPT');entry=a.f.inspect(a.raw(accepted['entry']),'ENTRY')
                if entry['operation']==9:noops.add(accepted['entryDigest'])
    public_reads=sum(h['kind'] in ('read','backup') for h in history)
    m.need(len(noops)-public_reads<=64 and sum(h['kind']=='backup' for h in history)<=8,'activation/auxiliary barrier ceiling')
    inspect=location.inspect if location is not None else storage.inspect
    for join in receipt['rejoins']:
        m.need(0<=join['endNanos']-join['startNanos']<=60*10**9 and join['observed']['provenIndex']>=join['through'] and
               inspect(root/join['node'])['provenThrough']>=join['through'],'fault durable rejoin/deadline')
    observed=fault_facts(root,receipt,history,traces,files)
    return dict(case=case,status='PASS',calls=len(history),history=hist,physical=proof,fault=observed)


def fault_facts(root,r,history,traces,files):
    case=r['case'];old=r['seedLeader'];flat=[x for rows in traces.values() for x in rows]
    encoded=(root/'node-1/manifest.gsr').read_bytes();manifest=dict(a.f.inspect(encoded,'MANIFEST'),digest=encoded[16:48].hex())
    wire=lambda row,key='frame':a.f.wire(a.raw(row[key]),manifest)
    events=r['events'];drops=[x for x in flat if x['event']=='NETWORK_DROP']
    def event(name):
        values=[e for e in events if e['event']==name];m.need(len(values)==1,'fault control event '+name);return values[0]
    if case in ('isolated-old-leader','asymmetric-requests','asymmetric-responses','no-quorum'):
        injection=event('fault-start');heal=event('heal')
        m.need(15*10**9<=heal['controllerNanos']-injection['appliedNanos']<=17*10**9,'fault hold duration')
        m.need(drops and all(x['rule'] in injection['rules'] for x in drops),'missing/wrong actual drops')
        if case=='isolated-old-leader':
            m.need(any(p['node']!=old and p['endNanos']<=heal['controllerNanos'] and all(p[k]['outcome']=='SUCCESS' for k in ('write','read')) for p in r['progress']),'no majority progress under fault')
        if case.startswith('asymmetric-'):
            barrier='BEFORE_REQUEST_WRITE' if case=='asymmetric-requests' else 'AFTER_RESPONSE_READ'
            m.need(all(wire(x,'request')['sender']==old and x['barrier']==barrier for x in drops),'wrong directional drop')
            replies=[x for x in flat if x['event']=='REPLY']
            m.need(any(x['node']==old and wire(x)['type']!='REJECT' and wire(x,'request')['sender']!=old for x in replies),'reverse direction not exercised')
            if case=='asymmetric-responses':m.need(all(any(x['request']==d['request'] for x in replies) for d in drops),'dropped response never executed')
        else:m.need(len(r['refusals'])==2,'missing fault refusals')
        if case=='isolated-old-leader':
            seed_callback=next(x for x in traces[old] if x['event']=='READ_CALLBACK' and x['opId']==r['seedRead']['opId'])
            seed_capture=max((x for x in traces[old] if x['pid']==seed_callback['pid'] and x['event']=='READ_CAPTURE_VALIDATED' and x['order']<seed_callback['order']),key=lambda x:x['order'])
            m.need(any(x['event']=='FORCE' and x['kind']=='PROMISE' and a.f.inspect(a.raw(x['record']),'PROMISE')['epoch']>seed_capture['epoch'] for x in traces[old]),'old leader never durably fenced')
        return dict(drops=len(drops),holdNanos=heal['controllerNanos']-injection['appliedNanos'])
    if case in ('leader-loss','entry-chosen','proof-quorum','interrupted-transfer'):
        killed=[s for s in r['stops'] if s['kill']];m.need(len(killed)==1,'fault crash count');crash=killed[0]
        m.need((crash['node']==old)==(case!='interrupted-transfer'),'wrong crashed voter')
        if case!='leader-loss':
            cut=r['cut'];own=[x for x in traces[crash['node']] if x['pid']==crash['pid']]
            wanted={'entry-chosen':'ACCEPT_ACK_RECEIVED','proof-quorum':'PROOF_ACK_RECEIVED','interrupted-transfer':'STORAGE_CUT:TRANSFER_PROGRESS_BEFORE_ACK'}[case]
            m.need(cut in own and cut['event']=='CUT_REACHED' and cut['cut']==wanted and cut['mode']=='kill','wrong actual cut')
            before=[x for x in own if x['order']<cut['order']];m.need(before[-1]['event']==wanted.split(':')[0],'cut lacks preceding observation')
            if case=='interrupted-transfer':
                retained=files[crash['node'],crash['generation']]
                meta=a.f.contextual_frame(retained['transfer/transfer.gsr'],'TRANSFER',manifest)
                m.need(meta['receivedBytes']==4096<meta['imageBytes'],'not first durable full chunk')
                chunks=[]
                for row in flat:
                    if row['event']=='WIRE_BEFORE_REQUEST_WRITE_SNAPSHOT_CHUNK':
                        req=wire(row,'request');p=req['payload']
                        if p['transferId']==meta['transferId'] and req['recipient']==crash['node']:chunks.append((p['offset'],a.raw(p['chunk'])))
                prefix=protocol.ranges(chunks,4096)
                m.need(retained['transfer/image.gsr'][:4096]==prefix,'partial bytes not from actual wire')
            else:
                pending=[h for h in history if h['outcome']=='PENDING']
                m.need(len(pending)==1 and pending[0]['pid']==crash['pid'] and pending[0]['documents']==expected_documents(40,512),'crashed mutation response fabricated')
                target=pending[0];accepts=[];proofs=[]
                for node,rows in traces.items():
                    for row in rows:
                        if row['event']=='FORCE' and row['kind']=='ACCEPT':
                            vote=a.f.inspect(a.raw(row['record']),'ACCEPT');entry=a.f.inspect(a.raw(vote['entry']),'ENTRY')
                            if entry['operation']==4 and [dict(id=k,value=v) for k,v in a.documents_command(a.raw(entry['payload']))]==target['documents']:accepts.append((node,vote))
                        if row['event']=='FORCE' and row['kind']=='PROOF':proofs.append((node,a.f.inspect(a.raw(row['record']),'PROOF')))
                original=next(v for n,v in accepts if n==old)
                m.need(len({n for n,v in accepts if v['epoch']==original['epoch'] and v['entryDigest']==original['entryDigest']})>=2,'target not actually chosen')
                if case=='proof-quorum':m.need(len({n for n,p in proofs if p['epoch']==original['epoch'] and p['entryDigest']==original['entryDigest']})>=2,'target lacks original proof quorum')
                m.need(all(d in r['finalReads'][-1]['documents'] for d in target['documents']),'chosen target lost')
        return dict(crashed=crash['node'],exitCode=crash['exitCode'],archives=len(files))
    if case=='group-restart':
        m.need(len(r['starts'])==6 and len(files)==3 and max(s['endNanos'] for s in r['stops'] if s['generation']==1)<min(s['startNanos'] for s in r['starts'] if s['generation']==2),'whole group was not stopped')
        return dict(restarted=3)
    if case=='slow-follower':
        begin=event('slow-start');end=event('slow-end');m.need(15*10**9<=end['controllerNanos']-begin['controllerNanos']<=17*10**9,'slow force hold duration')
        own=traces[begin['node']];begins=[x for x in own if x['event']=='SLOW_FORCE_BEGIN'];ends=[x for x in own if x['event']=='SLOW_FORCE_END']
        m.need(begins and len(begins)==len(ends),'slow force never finished')
        for first,last in zip(begins,ends):m.need(first['delayMillis']==last['delayMillis']==1500 and first['kind']==last['kind'] and last['localNanos']-first['localNanos']>=1500*10**6,'force delay not observed')
        return dict(delayedForces=len(begins),lag=r['lag']['leader']['provenIndex']-r['lag']['follower']['provenIndex'])
    if case=='maintenance':
        cut=r['cut'];own=[x for x in traces[old] if x['pid']==cut['pid']]
        release=next(x for x in own if x['event']=='CUT_RELEASED' and x['cut']=='READ_CAPTURED')
        m.need(any(x['event']=='REJOIN_INSTALLED' and cut['order']<x['order']<release['order'] for x in own),'no rejoin while read pinned')
        m.need(r['pinnedRead']['documents']==r['seedRead']['documents'],'captured view changed')
        m.need([h['kind'] for h in history if h['kind'] in ('checkpoint','backup')]==['checkpoint','backup'],'maintenance schedule')
        restore=read(root/'restore.json');restored=read(root/'restore.stdout')
        m.need(restore['exitCode']==0 and restored['coreSource']==str(Path(restore['args'][6].split(':')[0])) and Path(restored['coreSource']).name=='general-search-engine-4.4.0.jar','published restore identity')
        control=next(p for p in local.load()['publishedControls']['artifacts'] if p['artifact']=='general-search-engine' and p['version']=='4.4.0')
        artifacts.retained(root.parent,restored['coreSource'],control['sha256'])
        m.need(restored['documents']==r['finalReads'][-1]['documents'] and restored['sequence']==r['backup']['sequence'],'published V4.4 restore mismatch')
        return dict(pinCrossedRejoin=True,restoreSequence=restored['sequence'])
    if case=='minority-capacity':
        rejection=r['rejection'];m.need(rejection in traces['node-3'] and rejection['event']=='RESOURCE_REJECTED' and rejection['limit']==128<<10 and
                                     rejection['budget']=='retained' and rejection['retained']-rejection['replaced']+rejection['requested']>rejection['limit'],'capacity not actually exceeded')
        m.need(len(r['refusals'])==2 and len(files)==2 and ('node-3',1) in files,'minority restart schedule')
        own=[v for v in traces['node-3'] if v['pid']==rejection['pid']]
        m.need(any(v['event']=='PERFORMANCE_SAMPLE' and v['boundary']=='resource-rejected' and v['order']>rejection['order'] for v in own),'missing quarantined resource sample')
        replies=[v for v in own if v['event']=='REPLY' and v['order']>rejection['order'] and wire(v)['type']=='REJECT' and wire(v)['payload']['reason']=='CAPACITY_EXCEEDED']
        m.need(replies and wire(replies[0])['type']=='REJECT' and wire(replies[0])['payload']['reason']=='CAPACITY_EXCEEDED','resource refusal lacks original capacity reply')
        actual={p:dict(size=len(v),sha256=m.sha(v)) for p,v in files['node-3',1].items()}
        observed={v['path']:dict(size=v['size'],sha256=v['sha256']) for v in rejection['files']}
        m.need(len(observed)==len(rejection['files']) and sum(v['size'] for v in observed.values())==rejection['retained'] and
               all(actual.get(k)==v for k,v in observed.items()),'capacity accounting differs from retained bytes')
        for response in r['refusals']:
            invokes=[v for v in own if v['event']=='CLIENT_INVOKE' and v['opId']==response['opId']]
            m.need(len(invokes)==1 and invokes[0]['order']>replies[0]['order'],'resource refusal precedes witnessed quarantine')
        starts={s['node']:s for s in r['starts'] if s['generation']==2}
        m.need(len(starts)==2 and 'node-3' in starts and any(s['node']!='node-3' for s in starts.values()),'missing retained leader restart')
        for start in starts.values():m.need(any(h['kind']=='read' and h['outcome']=='SUCCESS' and h['node']!='node-3' and h['startNanos']>=start['readyNanos'] for h in history),'healthy service absent after restart')
        return dict(rejectedBytes=rejection['requested'],bound=128<<10)
    raise ValueError('unqualified fault cell')


def validate(root,*,allow_targeted=False):
    root=Path(root).resolve();execution=read(root/'execution.json');cases=execution['cases'];plan=contract.load()
    m.need(execution['status']=='EXECUTED' and execution['paidCloud'] is False and execution['fullRemoteQualification'] is False,'fault execution claim')
    names=[v['case'] for v in cases];expected=[v['name'] for v in plan['cells'][3:]]
    m.need(names==expected or allow_targeted and len(names)==1 and names[0] in expected,'fault matrix coverage')
    m.need(read(root/'cloud-plan.json')==plan and read(root/'plan.json')==local.load(),'fault suite plan')
    m.need(m.sha((root/'source-inventory.json').read_bytes())==execution['sourceInventorySha256'],'fault source inventory')
    pinned={a['artifact']+'-'+a['version']+'.jar':a['sha256'] for a in local.load()['publishedControls']['artifacts']}
    source_inventory=read(root/'source-inventory.json')
    for mode,adapter in execution['adapters'].items():performance.artifacts(root,mode,adapter,pinned,source_inventory)
    adapter=execution['adapters']['candidate-v5.1-automatic'];original=Path(adapter['artifacts'][0]['path']).parent.parent
    location=EvidenceLocation(root,original)
    results=[]
    for row in cases:
        name=row['case'];store_root=root/(name+'-commands');owner=commands.read(store_root/'binding.json')
        m.need(owner['source']==execution['source'] and owner['bundleSha256']==m.sha(m.canonical(adapter)),'fault command bundle/source')
        store=commands.CommandStore(store_root,owner);request=commands.read(store_root/'commands'/row['command']['commandId']/'request.json')
        m.need(request['command']=='fault' and request['payload']==dict(cell=name),'fault command payload')
        receipt=store.query(request)
        m.need(receipt==row['command'] and receipt['state']=='SUCCEEDED' and receipt['result']['receiptSha256']==m.sha((root/name/'receipt.json').read_bytes()),'fault durable receipt')
        results.append(validate_cell(root/name,adapter,location))
    return dict(status='PASS',execution='local-guest-faults-only',paidCloud=False,fullRemoteQualification=False,cases=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--allow-targeted',action='store_true');v=p.parse_args()
    print(m.canonical(validate(v.root,allow_targeted=v.allow_targeted)).decode())
