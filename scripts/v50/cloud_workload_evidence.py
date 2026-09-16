"""Independent local workload member/set verification. Cloud lifecycle admission is a later gate."""
import argparse
import base64
import heapq
import json
from pathlib import Path
import re
import struct
import tempfile
import zipfile
from . import admission_format as f, runtime_format
from .cloud_workload_io import read, rows, inventory, unpack, sha_file, validate_source_archive, relative
from .cloud_workload_plan import read_plan, PLAN_SHA256, arithmetic
from .cloud_workload_model import Model, operation, payload, entry
from .performance_model import OP_IDS, INDEXES, document, encoded, canonical, digest
from .performance_evidence import STAGES


def decoded(raw):
    try: result=base64.b64decode(raw,validate=True)
    except Exception as error: raise ValueError('noncanonical base64') from error
    f.check(base64.b64encode(result).decode()==raw,'noncanonical base64');return result


def stream(root,name):
    path=root/name
    return rows(path) if path.is_dir() else iter(())


def state_cuts(root,views):
    cuts=list(stream(root,'state-cuts')); pages=list(stream(root,'states')); used=set()
    for cut in cuts:
        label=cut['label'];f.check(label not in used,'duplicate state cut');used.add(label)
        f.check(cut['sequence'] in views,'unproven state cut');view=views[cut['sequence']]
        f.check(all(cut[k]==view[k] for k in ('sequence','count','documentsSha256','indexCount')),'independent state mismatch')
        selected=[p for p in pages if p['label']==label];docs=[]
        for p in selected:
            f.check(p['sequence']==cut['sequence'] and p['offset']==len(docs) and 0<len(p['documents'])<=256,'state page order')
            docs.extend(p['documents'])
        f.check(docs==view['documents'],'incomplete/forged state pages')
    f.check({p['label'] for p in pages}==used,'unbound state pages')
    return cuts


def validate_schedule(root,plan,profile='local-qualification',*,control=False):
    from .cloud_remote_contract import schedule
    windows=list(stream(root,'windows'));calls=list(stream(root,'calls'));local=schedule(profile,control=control)
    names=local['windows'];f.check([w['name'] for w in windows]==names,'missing/extra workload window')
    all_rows=[];cycle=0;previous=0
    for w in windows:
        name=w['name'];sustained=name=='sustained';cycles=local['warmupCycles'] if name=='warmup' else local['cyclesPerWindow']
        count=local['sustainedCalls'] if sustained else cycles*10
        interval=local['sustainedIntervalNanos'] if sustained else local['healthyIntervalNanos']
        f.check(w['calls']==count and w['intervalNanos']==interval and w['lanes']==(4 if sustained else 1) and w['firstCycle']==cycle,'unreviewed arrival schedule')
        f.check(w['pacing']==local['pacing'],'local pacing mode')
        maximum=local['maximumWindowSeconds']*10**9 if profile=='local-qualification' else count*interval+10**9
        f.check(w['missedSlots']==0 and previous<=w['startNanos'] and count*interval<=w['endNanos']-w['startNanos']<=maximum,'short/overlapping/overlong workload window')
        f.check(w['instrumented'] is (name.startswith('instrumented') or sustained),'instrumentation mode')
        selected=sorted([r for r in calls if r['window']==name],key=lambda r:r['call'])
        f.check(len(selected)==count,'missing/extra operation samples')
        for i,row in enumerate(selected):
            expected=operation(cycle+i//10,i,sustained)
            f.check(row['call']==i and row['cycle']==cycle+i//10 and row['outcome']=='success','operation schedule/outcome')
            f.check(all(row[k]==v for k,v in expected.items()),'workload keys/operation/revision')
            nominal=w['startNanos']+i*interval
            f.check(row['nominalScheduledNanos']==nominal<=row['scheduledNanos']<=row['dispatchNanos']<=row['startNanos']<row['endNanos']<=w['endNanos'],'sample timing')
            if profile=='local-qualification':
                if i: f.check(row['scheduledNanos']>=selected[i-1]['dispatchNanos']+interval,'catch-up arrival burst')
                if i>=w['lanes']: f.check(row['scheduledNanos']>=selected[i-w['lanes']]['endNanos'],'overlapping client lane')
            else:
                f.check(row['scheduledNanos']==nominal and row['dispatchNanos']<nominal+interval,'missed fixed-rate slot')
                if i>=w['lanes']:f.check(selected[i-w['lanes']]['endNanos']<=row['dispatchNanos'],'overlapping client lane')
            f.check(256<=row['beforeSequence']<=row['afterSequence']<=33024,'operation sequence bounds')
            if row['operation'] not in OP_IDS:f.check(row['beforeSequence']==row['afterSequence'],'ambiguous concurrent read cut')
            all_rows.append(row)
        if profile=='local-qualification':f.check(w['endNanos']>=selected[-1]['dispatchNanos']+interval,'short final pacing interval')
        previous=w['endNanos']
        if not sustained:cycle+=cycles
    f.check(len(calls)==len(all_rows),'unbound operation sample')
    return windows,all_rows


def validate_resources(directory,plan,windows=()):
    samples=list(stream(directory,'resources'));f.check(samples,'missing resource samples')
    previous=0
    for sample in samples:
        stamp=sample['observedNanos'];p=sample['process'];s=sample['runtime']
        f.check(stamp>previous,'resource chronology');previous=stamp
        f.check(0<p['heapUsedBytes']<=p['heapMaxBytes']<=2<<30 and 0<p['VmRSSBytes']<=p['VmHWMBytes'],'resource memory bounds')
        f.check(all(type(p[k]) is int and p[k]>=0 for k in ('cpuNanos','gcCount','gcMillis')),'resource counters')
        if 'pendingClients' in s:
            f.check(0<=s['pendingClients']<=16 and 0<=s['appliedIndex']<=s['commitIndex']<=s['lastLogIndex']<=32768,'resource runtime bounds')
            f.check(0<=s['retainedLogBytes']<=256<<20 and 0<=s['retainedBytes']<=128<<20,'observed storage bounds')
            obs=s['observer'];f.check(0<=obs['writerQueue']<=28 and 0<=obs['queuedBytes']<=4<<20,'observed transport bounds')
            f.check(len(obs['peers'])==2 and all(0<=v['queued']<=4 and 0<=v['inFlight']<=4 for v in obs['peers'].values()),'observed peer queue bounds')
        f.check(sample['network']['bytes']>=0 and sample['network']['attempts']>=0,'network counters')
    for w in windows:
        stamps=[s['observedNanos'] for s in samples if w['startNanos']-10**9<=s['observedNanos']<=w['endNanos']+10**9]
        f.check(stamps and stamps[0]<=w['startNanos'] and stamps[-1]>=w['endNanos']-10**9,'resource window coverage')
        f.check(all(b-a<=2_500_000_000 for a,b in zip(stamps,stamps[1:])),'resource sampling gap')


def validate_commit_timings(windows,calls_by_index,events,forces):
    """Bind force pairs to proven entries in writer order, even when clients overlap."""
    enabled={w['name'] for w in windows if w['instrumented']}
    stages=[e for e in events if e['event'] in STAGES]
    f.check(all(v['window'] in enabled for v in [*stages,*forces]),'unbound commit observations')
    for window in windows:
        if not window['instrumented']:continue
        name=window['name']
        committed=sorted((i,r) for i,r in calls_by_index.items() if r['window']==name)
        observed=[e for e in stages if e['window']==name]
        selected=[v for v in forces if v['window']==name]
        f.check([(e['index'],e['event']) for e in observed]==[(i,s) for i,_ in committed for s in STAGES],
                'missing/reordered quorum/publication observations: '+name)
        f.check([v['kind'] for v in selected]==['ENTRY','PROOF']*len(committed),
                'missing/extra/reordered force timings: '+name)
        previous=window['startNanos']
        for offset,(index,row) in enumerate(committed):
            stamps=[e['nanos'] for e in observed[offset*len(STAGES):(offset+1)*len(STAGES)]]
            context=f'{name} index {index}'
            f.check(stamps==sorted(stamps) and window['startNanos']<=row['startNanos']<=stamps[0]<=stamps[-1]<=row['endNanos']<=window['endNanos'],
                    'success before proof/publication: '+context)
            entry_force,proof_force=selected[2*offset:2*offset+2]
            # The writer serializes commits; public client lifetimes may overlap or finish out of order.
            f.check(max(previous,row['startNanos'])<=entry_force['startNanos']<entry_force['endNanos']<=stamps[0] and
                    stamps[1]<=proof_force['startNanos']<proof_force['endNanos']<=stamps[2],
                    'force-to-entry timing: '+context)
            previous=stamps[-1]


def control_views(calls,get_keys):
    """Replay a control order consistent with public sequence brackets, not dispatch order.

    Sustained writes update independent lane keys; each lane waits for its previous
    call. Cross-lane writes commute, so any order satisfying all brackets is valid.
    """
    mutations=sorted((r for r in calls if r['operation'] in OP_IDS),key=lambda r:r['beforeSequence'])
    model=Model();base=model.sequence;last=base+len(mutations)
    completed=[];floor=base
    for row in sorted(calls,key=lambda r:r['startNanos']):
        while completed and completed[0][0]<=row['startNanos']:
            _,after=heapq.heappop(completed);floor=max(floor,after)
        f.check(floor<=row['beforeSequence']<=row['afterSequence']<=last,'control observation chronology')
        heapq.heappush(completed,(row['endNanos'],row['afterSequence']))
    wanted={r['beforeSequence'] for r in calls if r['operation'] not in OP_IDS}
    wanted|={base,last};views={base:model.view(get_keys,True)}
    pending=[];offset=0
    for sequence in range(base+1,last+1):
        while offset<len(mutations) and mutations[offset]['beforeSequence']<sequence:
            row=mutations[offset];heapq.heappush(pending,(row['afterSequence'],offset,row));offset+=1
        f.check(pending,'missing control publication')
        after,_,row=heapq.heappop(pending)
        f.check(sequence<=after<=last and base<=row['beforeSequence'] and row['answerDigest']==digest(canonical(None)),
                'control mutation sequence/success')
        model.apply(OP_IDS[row['operation']],payload(row['operation'],row['keys'],row['revision']))
        if sequence in wanted:views[sequence]=model.view(get_keys,sequence==last)
    for row in calls:
        if row['operation'] in OP_IDS:continue
        f.check(row['beforeSequence']==row['afterSequence'] and row['beforeSequence'] in views,'ambiguous control read cut')
        v=views[row['beforeSequence']]
        answer=v['queryDigest'] if row['operation']=='QUERY' else digest(canonical(v['gets'][row['keys'][0]]))
        f.check(row['answerDigest']==answer,'independent control read')
    return views


def identity(value,receipt,metadata,plan,kind):
    f.check(value['pid']==receipt['pid'] and value['planSha256']==PLAN_SHA256 and value['coreSource']==metadata['jars'][kind]['path'],'process/artifact identity')
    f.check(value['jvmArguments']==plan['jvmArguments'] and value['availableProcessors']==8 and value['os']=='Linux' and value['javaRuntime'].startswith('21'),'JVM identity')
    args=receipt['args'];f.check(args[:5]==[metadata.get('javaExecutable','java'),*plan['jvmArguments']] and args[5]=='-cp','JVM command flags')
    wanted=[metadata['jars'][kind]['path']] if kind=='control' else [metadata['jars'][n]['path'] for n in ('core','replication')]
    f.check(args[6].split(':')[:-1]==wanted,'isolated classpath')
    f.check(receipt['startedNanos']<receipt['finishedNanos'],'process duration')


def inspect_authority(path,plan,frames,volume_layout=False):
    report=runtime_format.inspect(path,torn=True)
    f.check(report['base']==256 and report['lastIndex']<=32768,'authority index bounds')
    genesis=f.genesis((path/'genesis.gsr').read_bytes());genesis['raw']=(path/'genesis.gsr').read_bytes()
    f.check(genesis['documents']==[(struct.pack('>i',i),encoded(document(i,0))) for i in range(1,4097)] and genesis['indexes']==INDEXES,'independent cloud genesis')
    manifest_raw=(path/'manifest.gsr').read_bytes();manifest=f.manifest(manifest_raw,genesis)
    r=f.record((path/'bootstrap-seal.gsr').read_bytes(),20);r.text(64);receipt=f.record(r.blob(f.META),19)
    descriptor,_=f.plan(receipt.blob(f.META),manifest,genesis,manifest_raw)
    f.check(descriptor['application']['snapshot']==plan['application']['snapshot'] and descriptor['application']['planner']==plan['application']['planner'],'application configuration')
    for replica in descriptor['replicas']:
        f.check(replica['replicationBounds']==plan['replicationBounds'],'resolved replication bounds')
        mat=replica['materialization'];f.check(all(v==plan['application'][k] for k,v in mat['bounds'].items()),'resolved application bounds')
        f.check(mat['codecId']=='semantic-codec' and mat['codecVersion']==1 and mat['schemaIdentity']=='semantic-schema' and mat['storageIdentity']=='performance-store','storage identity')
        node=replica['node'];ordinal=node.removeprefix('node-')
        target=Path(replica['target']['path']);materialization=Path(mat['directory']['path'])
        f.check(target.name==node and materialization==target.parent/('materialization-'+node),'authority/materialization placement')
        f.check((target.parent.name=='volume-'+ordinal) is volume_layout,'sealed volume layout')
    # Match the snapshot's complete ancestry and application to independently replayed wire payloads.
    if (path/'current.gsr').exists():
        selector=f.record((path/'current.gsr').read_bytes(),10);selector.take(32);selector.text(64);slot=selector.text(32)
        raw=(path/slot/'snapshot.gsr').read_bytes();f.check(len(raw)<=plan['maximumSnapshotImageBytes'],'snapshot image bound')
        r=f.record(raw,8,f.IMAGE);r.take(48);anchors=[]
        for _ in range(r.count(32768,89)):
            r.take(24);op=r.number('B');h=r.take(32).hex();p=r.take(32).hex();anchors.append((op,h,p))
        r.blob(f.META);indexes,docs=f.application(r.blob());r.end();model=Model()
        for op,h,p in anchors:
            f.check(h in frames and frames[h]['op']==op and frames[h]['payloadSha256']==p,'unbound snapshot operation ancestry')
            model.apply(op,frames[h]['payload'])
        f.check(indexes==model.indexes and docs==[(struct.pack('>i',d[0]),encoded(d)) for d in model.docs.values()],'snapshot application differs from committed payloads')
    return report,manifest


def validate_raw(root,*,remote=False,qualification=False):
    plan=read_plan(root/'plan.json');local=plan['localQualification'];env=read(root/'set.json');profile='local-qualification'
    if remote:
        from .cloud_remote_contract import schedule
        profile=env['preset'];local=schedule(profile)
        f.check((profile=='local-qualification') is qualification,'remote qualification/profile boundary')
        local.update(execution='local-remote-workload-only' if qualification else 'gcp-cloud-workload',preset=profile)
    f.check((env['schema'],env['execution'],env['preset'],env['planSha256'])==('gse-v50-remote-workload-evidence-v1' if remote else plan['evidenceSchema'],local['execution'],local['preset'],PLAN_SHA256),'evidence provenance/profile')
    f.check(env['members']==['node-1','node-2','node-3'] and 0<env['finishedNanos']-env['startedNanos']<=local['maximumRunSeconds']*10**9,'set members/deadline')
    before=inventory(root,exclude=('set.json',),logical=True);f.check(env['files']==before,'evidence inventory')
    meta=read(root/'metadata.json');f.check(meta['execution']==local['execution'] and re.fullmatch('[0-9a-f]{40}',meta['head']) and type(meta['dirty']) is bool,'source provenance')
    volume_layout=meta.get('volumeLayout',False);f.check(type(volume_layout) is bool,'volume layout flag')
    if (root/('remote-bundle.json' if remote else 'offline-bundle.json')).exists():
        bundle=read(root/('remote-bundle.json' if remote else 'offline-bundle.json'))
        f.check(bundle['schema']==('gse-v50-remote-workload-bundle-v1' if remote else 'gse-v50-cloud-workload-bundle-v1') and
                bundle['execution']==('remote-workload-adapter-only' if remote else 'offline-workload-bundle-only') and
                bundle['workloadPlanSha256']==PLAN_SHA256 and bundle['inputs']==meta['inputs'] and bundle['source']==meta['head'] and
                bundle['dirty']==meta['dirty'] and bundle['jars']=={n:v['sha256'] for n,v in meta['jars'].items()},'offline bundle provenance')
        f.check(meta['javaExecutable'].endswith('/jre/bin/java') and '21.0.12+8' in meta['java'],'bundled runtime identity')
        for directory in ('classes-candidate','classes-control'):
            expected={k.removeprefix(directory+'/'):v for k,v in bundle['files'].items() if k.startswith(directory+'/')}
            f.check(inventory(root/directory)==expected,'independently compiled bundle classes')
    else: f.check(meta.get('javaExecutable','java')=='java','unbound runtime executable')
    f.check(sum(v['bytes'] for k,v in before.items() if k.startswith(('streams/','control-streams/','restore-streams/')))<=plan['evidenceBounds']['maxSamplesAndTracesBytes'],'combined sample/trace budget')
    f.check(meta['arithmetic']==arithmetic(plan),'forged budget arithmetic');validate_source_archive(root/'source-inputs.zip',meta['inputs'])
    f.check(meta['inputs']['docs/v5x/v5.0/phase6-cloud-workload-plan.json']==PLAN_SHA256,'source plan binding')
    f.check(set(meta['jars'])=={'core','replication','control'} and meta['jars']['control']['sha256']==plan['publishedControl']['sha256'],'control pin')
    for name,jar in meta['jars'].items():
        path=root/'artifacts'/(name+'.jar');f.check(sha_file(path)==jar['sha256'],'artifact checksum')
        with zipfile.ZipFile(path) as archive:
            f.check(not any('/admission/' in n or 'WorkloadWorker' in n for n in archive.namelist()),'probe leaked into production')
    f.check(inventory(root/'source')==meta['sourceBackup'],'immutable source changed')
    members=[read(p) for p in sorted((root/'members').glob('*.json'))];f.check(members,'missing worker receipts')
    frames={};proofs=[];worker_dirs=[]
    for m in members:
        f.check(m['schema']=='gse-v50-cloud-workload-member-v1' and m['node'] in env['members'] and m['ready']['node']==m['node'],'member provenance')
        identity(m['ready']['identity'],m,meta,plan,'core')
        f.check(m['cleanup']=='reaped' and m['exitCode']==(-9 if m['forced'] else 0) and m['linuxStartTicks'].isdigit(),'worker cleanup')
        f.check(m['startedNanos']<m['readyNanos']<m['finishedNanos'],'ready lifetime')
        relative(m['streams']);d=root/m['streams'];worker_dirs.append(d);validate_resources(d,plan)
        previous=m['readyNanos']
        for e in m['exchanges']:
            f.check(previous<=e['sentNanos']<m['finishedNanos'],'command chronology')
            if 'response' not in e:
                f.check(m['forced'] and e.get('outcome')=='indeterminate' and e is m['exchanges'][-1],'missing command response');continue
            r=e['response'];f.check(e['sentNanos']<e['receivedNanos']<m['finishedNanos'] and r['startNanos']<r['endNanos'],'command duration');previous=e['receivedNanos']
            f.check(r['command']==e['request']['command'],'command identity')
            if not r['accepted']:f.check(r['reason'] in ('QUORUM_UNAVAILABLE','CAPACITY_EXCEEDED'),'unexpected public command failure')
        for row in stream(d,'ledger'):
            raw=decoded(row['frame'])
            if row['type']=='APPEND':
                decoded_entry=entry(raw);h=decoded_entry['digest'];f.check(h not in frames or frames[h]==decoded_entry,'conflicting ledger frame');frames[h]=decoded_entry
            else:f.check(row['type']=='COMMIT_PROOF' and len(raw)<=2048,'proof stream');proofs.append(raw)
    # Verify every retained crash/source generation independently, including snapshots after replacement.
    paths=[root/n for n in env['members']]+list(root.glob('lost-node-*'))+list((root/'cuts').glob('*/node-*'))+list((root/'capacity-sources').glob('*'))
    reports=[];manifest=None
    for path in paths:
        report,manifest=inspect_authority(path,plan,frames,volume_layout);reports.append(report)
    if volume_layout:
        for i in (1,2,3):
            f.check(inventory(root/f'node-{i}',logical=True)==inventory(root/f'volume-{i}'/f'node-{i}',logical=True),'retained volume authority differs')
    final=reports[:3];strongest=max(final,key=lambda r:r['committed']);history=strongest['anchors'][:strongest['committed']]
    for report in reports:
        common=min(report['committed'],len(history));f.check(report['anchors'][:common]==history[:common],'conflicting proven history')
        f.check(report['committed']<=len(history),'lost proven prefix on recovery')
    chain=[]
    for i,h in enumerate(history,1):
        f.check(h in frames,'missing committed payload');e=frames[h]
        f.check(e['index']==i and e['previousIndex']==i-1 and e['previous']==(bytes.fromhex(history[i-2]) if i>1 else manifest['digest']) and e['identity']==manifest['digest'],'payload chain identity')
        chain.append((e['epoch'],e['incarnation'],e['op'],bytes.fromhex(h),bytes.fromhex(e['payloadSha256']),e['previous']))
    valid_proofs={runtime_format.proof(p,manifest,chain) for p in proofs if struct.unpack_from('>q',p,104)[0]<=len(chain)}
    f.check(len(history) in valid_proofs,'terminal proof missing from observed ledger')
    first=[m for m in members if m['generation']==1]
    f.check(len(first)==3 and len({(m.get('instanceId','local'),m['pid']) for m in first})==3,'three initial JVMs')
    first_leader=next(m for m in first if m['node']=='node-1');leader_dir=root/first_leader['streams']
    windows,calls=validate_schedule(leader_dir,plan,profile);validate_resources(leader_dir,plan,windows)
    measured=[e for e in first_leader['exchanges'] if e['request']['command']=='measure'];f.check(len(measured)==len(windows),'measurement command coverage')
    f.check(max(m['readyNanos'] for m in first)<measured[0]['sentNanos'] and measured[-1]['receivedNanos']<min(m['finishedNanos'] for m in first),'three-voter measurement overlap')
    for e,w in zip(measured,windows):
        f.check(e['response']['measurement']=={k:w[k] for k in e['response']['measurement']} and e['request']['window']==w['name'] and
                e['request']['profile']==profile,'window command binding')
    cuts=[r for d in worker_dirs for r in stream(d,'state-cuts')]
    wanted={r['sequence'] for r in cuts}|{r['beforeSequence'] for r in calls if r['operation'] not in OP_IDS}
    get_keys={r['keys'][0] for r in calls if r['operation']=='GET'};state_sequences={r['sequence'] for r in cuts}
    views={};model=Model();by_payload={};by_sequence={}
    if model.sequence in wanted:views[model.sequence]=model.view(get_keys,model.sequence in state_sequences)
    for index,h in enumerate(history,1):
        e=frames[h];model.apply(e['op'],e['payload'])
        if e['op']<=8:by_payload.setdefault((e['op'],e['payloadSha256']),[]).append((index,model.sequence));by_sequence[model.sequence]=index
        if model.sequence in wanted:views[model.sequence]=model.view(get_keys,model.sequence in state_sequences)
    f.check(model.sequence==strongest['sequence'],'independent sequence')
    for d in worker_dirs:state_cuts(d,views)
    # Mutation acknowledgements bind to decoded committed entries, independent of completion ordering.
    events=list(stream(leader_dir,'events'));forces=list(stream(leader_dir,'forces'));successes=0;instrumented={}
    for row in calls:
        op=row['operation']
        f.check(row['afterSequence']<=model.sequence,'claimed sequence exceeds proven authority')
        if op in OP_IDS:
            body=payload(op,row['keys'],row['revision']);matches=by_payload.get((OP_IDS[op],digest(body)),[])
            matches=[(i,s) for i,s in matches if row['beforeSequence']<s<=row['afterSequence']]
            f.check(len(matches)==1 and row['answerDigest']==digest(canonical(None)),'forged durable success/payload')
            index,sequence=matches[0];successes+=1
            if row['window'].startswith('instrumented') or row['window']=='sustained':
                f.check(index not in instrumented,'duplicate measured entry');instrumented[index]=row
        else:
            v=views[row['beforeSequence']];answer=v['queryDigest'] if op=='QUERY' else digest(canonical(v['gets'][row['keys'][0]]))
            f.check(row['answerDigest']==answer,'read does not match publication cut')
    validate_commit_timings(windows,instrumented,events,forces)
    control,restore=read(root/'control.json'),read(root/'restore.json')
    for value,label in ((control,'control-measure'),(restore,'control-restore')):
        identity(value['result']['identity'],value['process'],meta,plan,'control')
        f.check(value['process']['exitCode']==0 and value['process']==read(root/'processes'/(label+'.json')) and value['result']==read(root/'processes'/(label+'.stdout')),'control process binding')
    f.check(control['process']['finishedNanos']<min(m['startedNanos'] for m in members) and max(m['finishedNanos'] for m in members)<restore['process']['startedNanos'],'control/candidate isolation')
    cw,cr=validate_schedule(root/'control-streams',plan,profile,control=True);validate_resources(root/'control-streams',plan,cw)
    state_cuts(root/'control-streams',control_views(cr,get_keys))
    if profile!='failure-drill':
        paired=next(r for r in cuts if r['label']=='paired-steady')
        f.check(all(paired[k]==control['result']['semantic'][k] for k in ('sequence','count','documentsSha256','indexCount')),'paired V4 workload mismatch')
    # Restore is the writer-ordered exported cut, which precedes the deliberate capacity writes.
    restored=restore['result']['semantic'];seq=restored['sequence'];rm=Model()
    for h in history:
        if rm.sequence==seq:break
        e=frames[h];rm.apply(e['op'],e['payload'])
    f.check(rm.sequence==seq,'unproven backup cut');state_cuts(root/'restore-streams',{seq:rm.view((),True)})
    validate_cells(root,plan,members,frames,history,views,restored,profile=profile)
    f.check(read(root/'measurements.json')==measurements(root),'forged measurement summary')
    f.check(inventory(root,exclude=('set.json',),logical=True)==before,'validator mutated evidence')
    return dict(status='PASS',execution=local['execution'],preset=local['preset'],sourceHead=meta['head'],sourceDirty=meta['dirty'],
                corpusDocuments=4096,measuredCalls=len(calls)-local['warmupCycles']*10,durableSuccess=successes-local['warmupCycles']*8,committedThrough=len(history),applicationSequence=model.sequence,
                cells=len(local['cells']),planSha256=PLAN_SHA256,volumeLayout=volume_layout,offlineBundle=(root/'offline-bundle.json').exists())


def validate_cells(root,plan,members,frames,history,views,restored,*,profile='local-qualification'):
    from .cloud_remote_contract import schedule
    cells=read(root/'cells.json');f.check([c['name'] for c in cells]==schedule(profile)['cells'],'missing/reordered cells')
    previous=0
    by_name={c['name']:c for c in cells}
    for cell in cells:
        f.check(cell['status']=='PASS' and previous<=cell['startedNanos']<cell['finishedNanos'],'failed/overlapping cell');previous=cell['finishedNanos']
    all_faults=[r for m in members for r in stream(root/m['streams'],'faults')]
    f.check(any(r['action']=='disconnect' for r in all_faults) and ('slow' not in by_name or any(r['action']=='delay' and r['endNanos']-r['startNanos']>=250000000 for r in all_faults)) and
            any(r['action']=='lost-ack' and r['type']=='SNAPSHOT_CHUNK' for r in all_faults),'missing actual injected fault evidence')
    snap=by_name['snapshot']['details'];f.check(snap['checkpoint']['status']['checkpointSequence']>snap['before']['sequence'],'snapshot selection boundary')
    for name,barrier in [('entry-cut','AFTER_ENTRY_QUORUM'),('proof-cut','AFTER_PROOF_QUORUM')]:
        if name not in by_name:continue
        d=by_name[name]['details'];relative(d['member']);m=read(root/d['member']);f.check(m['forced'] and m['pid']==d['killedPid'],'proof-cut owned process')
        markers=list(stream(root/m['streams'],'barriers'));f.check(len(markers)==1 and markers[0]['barrier']==barrier and markers[0]['pid']==m['pid'],'proof-cut barrier identity')
        reports=[runtime_format.inspect(root/'cuts'/name/f'node-{i}',torn=True) for i in (1,2,3)]
        protected=max(r['committed'] for r in reports);f.check(d['recovered']['status']['commitIndex']>=protected,'lost proof during recovery')
        if name=='proof-cut':f.check(sum(r['committed']>=markers[0]['index'] for r in reports)>=2,'proof quorum lost')
        else:f.check(protected<markers[0]['index'],'entry-only cut manufactured proof')
    restart=by_name['restart' if 'restart' in by_name else 'fencing']['details'];f.check(restart['after']['epoch']>restart['before']['epoch'] and restart['staleResponse']['payload']['reason']=='STALE_EPOCH','stale incarnation fencing')
    if 'leader-replacement' in by_name:
        replacement=by_name['leader-replacement']['details'];f.check(replacement['oneSurvivor']['accepted'] is False and replacement['oneSurvivor']['reason']=='QUORUM_UNAVAILABLE' and replacement['recovered']['accepted'] is True,'leader replacement quorum')
        f.check(runtime_format.inspect(root/'node-1')['origin']==runtime_format.inspect(root/'node-3')['origin']==1,'missing replacement authority')
    maintenance=by_name['maintenance']['details'];f.check(inventory(root/'export')==maintenance['exportInventory'] and maintenance['exported']['backupSequence']==restored['sequence'],'backup cut/retention')
    f.check(maintenance['cancelled']['accepted'] is True and type(maintenance['cancelled']['cancelled']) is bool and (root/'published-after-cut').is_dir(),'cancel/close retention')
    if 'capacity' in by_name:
        capacity=by_name['capacity']['details'];relative(capacity['beforePath']);relative(capacity['afterPath'])
        f.check(inventory(root/capacity['beforePath'],logical=True)==capacity['sourceBefore']==capacity['sourceAfter']==inventory(root/capacity['afterPath'],logical=True),'capacity changed protected source bytes')
        attempts=capacity['attempts'];f.check(1<=len(attempts)<=3 and attempts[-1]['accepted'] is False and attempts[-1]['reason']=='CAPACITY_EXCEEDED','capacity classification')
    if 'no-quorum' in by_name:
        no=by_name['no-quorum']['details'];f.check(no['failure']['accepted'] is False and no['failure']['reason']=='QUORUM_UNAVAILABLE','no-quorum classification')
        f.check(all(no['before'][k]==no['after'][k] for k in ('sequence','count','documentsSha256','indexCount')),'no-quorum committed read changed')


def measurements(root):
    result={}
    for label,directory in [('candidate',root/'streams/node-1-1'),('control',root/'control-streams')]:
        calls=list(stream(directory,'calls'));windows=list(stream(directory,'windows'));measured={}
        for w in windows:
            if w['name']=='warmup':continue
            by_operation={}
            for op in sorted({r['operation'] for r in calls if r['window']==w['name']}):
                selected=[r for r in calls if r['window']==w['name'] and r['operation']==op]
                times=sorted(r['endNanos']-r['startNanos'] for r in selected);n=len(times)
                by_operation[op]=dict(attempted=n,admitted=n,completed=n,durableSuccess=n if op in OP_IDS else 0,
                    rejected=0,timedOut=0,indeterminate=0,documents=sum(r['documents'] for r in selected),
                    p50Nanos=times[(n*50+99)//100-1],p95Nanos=times[(n*95+99)//100-1],p99Nanos=times[(n*99+99)//100-1],
                    maximumSchedulerDelayNanos=max(r['startNanos']-r['scheduledNanos'] for r in selected))
                by_operation[op]['maximumScheduleDeferralNanos']=max(r['scheduledNanos']-r['nominalScheduledNanos'] for r in selected)
            measured[w['name']]=dict(startNanos=w['startNanos'],endNanos=w['endNanos'],sampleCount=w['calls'],
                pacing=w['pacing'],maximumOfferedRateMilliHz=10**12//w['intervalNanos'],
                observedOfferedRateMilliHz=w['calls']*10**12//(w['endNanos']-w['startNanos']),
                completedRateMilliHz=w['calls']*10**12//(w['endNanos']-w['startNanos']),operations=by_operation)
        baseline=sum(r['endNanos']-r['startNanos'] for r in calls if r['window'].startswith('baseline'))
        instrumented=sum(r['endNanos']-r['startNanos'] for r in calls if r['window'].startswith('instrumented'))
        result[label]=dict(windows=measured,instrumentedToBaselineServiceTimePpm=instrumented*1000000//baseline if baseline else None)
    result['faults']={}
    for cell in read(root/'cells.json'):
        if cell['name'] in ('healthy','sustained'):continue
        results=[]
        for path in (root/'members').glob('*.json'):
            for e in read(path)['exchanges']:
                if cell['startedNanos']<=e['sentNanos']<=cell['finishedNanos'] and e['request']['command']=='update':results.append(e.get('response'))
        result['faults'][cell['name']]=dict(attempted=len(results),durableSuccess=sum(r is not None and r['accepted'] for r in results),
            indeterminate=sum(r is None or not r['accepted'] and r['status']['lastLogIndex']>r['status']['commitIndex'] for r in results),
            rejected=sum(r is not None and not r['accepted'] and r['status']['lastLogIndex']==r['status']['commitIndex'] for r in results))
    return result


def validate(bundle):
    bundle=Path(bundle);before=inventory(bundle)
    with tempfile.TemporaryDirectory(prefix='gse-cloud-workload-inspect-') as temp:
        target=Path(temp)/'raw';unpack(bundle,target);result=validate_raw(target)
    f.check(inventory(bundle)==before,'validator modified retained bundle');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('evidence',type=Path)
    print(json.dumps(validate(parser.parse_args().evidence),sort_keys=True))
