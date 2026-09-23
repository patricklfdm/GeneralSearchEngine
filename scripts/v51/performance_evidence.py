"""Independent local timing/identity/resource/semantic qualification, never cloud admission."""
import os
import zipfile
import math
from pathlib import Path
from . import performance_plan as plan, performance_model as model, performance_semantics as semantic
from . import performance_physical as physical, storage_inspector as storage
from scripts.v50 import runtime_format as configured
from . import performance_artifacts as retained_artifacts

need = model.need


def read(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 64 << 20, 'measurement member type/size')
    return model.strict_json(path.read_bytes())


def lines(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 64 << 20, 'trace member type/size')
    raw = path.read_bytes()
    need(raw.endswith(b'\n'), 'incomplete trace record')
    return [model.strict_json(line) for line in raw.splitlines()]


def interval(value, start, end):
    need(type(value[start]) is int and type(value[end]) is int and 0 <= value[start] <= value[end], 'reversed or noninteger interval')
    return value[end] - value[start]


def summary(calls):
    rows = [r for r in calls if r['window'] != 'warmup']
    result = {}
    for operation in model.OPERATIONS:
        samples = sorted(interval(r, 'apiStartNanos', 'apiEndNanos') for r in rows if r['operation'] == operation)
        need(len(samples) == 8, 'eight measured samples per operation required')
        result[operation] = dict(samples=len(samples), p50Nanos=samples[math.ceil(.50*len(samples))-1],
                                 p95Nanos=samples[math.ceil(.95*len(samples))-1], p99Nanos=samples[math.ceil(.99*len(samples))-1])
    return result


def calls(rows, admitted):
    expected = model.expected(admitted)['rows']
    need(len(rows) == len(expected), 'missing/extra healthy call')
    for observed, wanted in zip(rows, expected):
        need(observed['outcome'] == 'SUCCESS', 'hidden unsuccessful healthy call')
        keys = ('ordinal','window','cycle','operation','keys','payloadSha256','answer','answerSha256','beforeSequence','afterSequence')
        need(model.canonical({k:observed[k] for k in keys}) == model.canonical({k:wanted[k] for k in keys}), 'healthy operation/order/answer differs')
        interval(observed, 'apiStartNanos', 'apiEndNanos')
    need(len({r['opId'] for r in rows}) == len(rows), 'replayed operation ID')


def process(root, mode, node, adapter, admitted):
    record = read(root / (node + '-process.json'))
    identity = record['ready']['identity']
    need(record['node'] == node and record['cleanup'] == 'reaped' and record['exitCode'] == 0 and record['forced'] is False, 'process lifecycle')
    need(type(record['pid']) is int and record['pid'] > 0 and record['linuxStartTicks'].isdigit(), 'OS process identity')
    need(record['startNanos'] <= record['readyNanos'] <= record['endNanos'], 'process controller interval')
    need(identity['pid'] == record['pid'] and identity['node'] == node and identity['mode'] == mode and identity['generation'] == 1, 'loaded process identity')
    need(identity['javaMajor'] == 21 and identity['javaRuntime'].startswith('21.') and identity['javaVendor']
         and identity['jvmArguments'] == admitted['jvmArguments'] and identity['processors'] == 2, 'exact JVM configuration')
    need(identity['host']['os']=='Linux' and set(identity['host'])=={'os','architecture','processLimits','cpuStatus','cgroup','cpuQuota','memoryLimit'},'host limits absent')
    need(type(identity['observedClockResolutionNanos']) is int and identity['observedClockResolutionNanos'] > 0, 'clock resolution observation')
    need(identity['planFileSha256'] == model.sha((root.parent / 'plan.json').read_bytes()), 'loaded plan identity')
    args = record['args']
    need(args[:6] == ['java', *admitted['jvmArguments'], '-cp'] and args[6] == adapter['cp'], 'isolated runtime classpath')
    for kind, artifact in zip(('core','replication'), adapter['artifacts']):
        need(identity[kind+'Source'] == artifact['path'] and identity[kind+'Sha256'] == artifact['sha256'], 'loaded artifact mismatch')
    actual_results = lines(root / (node + '-results.jsonl'))
    need(len(actual_results) == len(record['exchanges']), 'missing worker/controller response')
    previous = record['readyNanos']
    for exchange, result in zip(record['exchanges'], actual_results):
        need(previous <= exchange['startNanos'] <= exchange['endNanos'] <= record['endNanos'], 'controller exchange chronology')
        previous = exchange['endNanos']
        need(exchange['response'] == result and exchange['request']['opId'] == result['opId'] and
             exchange['request']['command'] == result['command'] and result['pid'] == record['pid'] and result['node'] == node and result['mode'] == mode, 'response provenance')
        need(exchange['outcome'] == result['outcome'] == 'SUCCESS', 'hidden failed exchange')
        interval(result, 'workerStartNanos', 'workerEndNanos')
        if result['command'] == 'call':
            row = result['call']
            need(result['workerStartNanos'] <= row['apiStartNanos'] <= row['apiEndNanos'] <= result['workerEndNanos'], 'API interval outside worker interval')
    need(actual_results[-1]['command'] == 'close', 'missing orderly close result')
    samples = lines(root / (node + '-samples.jsonl'))
    need(samples and samples[0]['boundary'] == 'start' and samples[-1]['boundary'] == 'closed', 'resource lifecycle boundaries')
    need([r['order'] for r in samples] == list(range(1,len(samples)+1)), 'missing/reordered sample')
    need(all(a['localNanos'] <= b['localNanos'] for a,b in zip(samples,samples[1:])), 'sample clock reversal')
    for row in samples:
        need(row['node'] == node and row['mode'] == mode and row['pid'] == record['pid'], 'borrowed resource process')
        need(0 < row['heapUsedBytes'] <= row['heapMaxBytes'] <= 512<<20 and
             0 < row['VmRSSBytes'] <= row['VmHWMBytes'] and row['threads'] > 0, 'memory/thread resource bound')
        need(all(type(row[k]) is int and row[k] >= 0 for k in ('gcCount','gcMillis','cpuNanos','retainedBytes')), 'missing/invalid resource counter')
        need(row['retainedBytes'] <= 128<<20 and all(type(v) is int and v >= 0 for v in row['processIo'].values()), 'retained/IO bound')
        if mode == 'candidate-v5.1-automatic':
            queue = row['queues']
            need(0 <= queue['admissionAvailable'] <= 4 and 0 <= queue['inboundAvailable'] <= 8 and
                 all(type(v) is int and 0 <= v <= 2 for v in queue['outboundAvailable'].values()), 'permit accounting')
            need(all(type(queue[k]) is int and 0 <= queue[k] <= 64<<20 for k in ('pinsBytes','stagingBytes','queuedBytes')), 'pin/staging/transport bound')
            need(0<=queue['authorityDiskBytes']<=64<<20 and 0<=queue['transferDiskBytes']<=64<<20,'authority/transfer disk bound')
            need(all(type(queue[k]) is int and 0 <= queue[k] <= ceiling for k,ceiling in
                     [('orderedQueue',4),('deadlinesQueue',4),('inputsQueue',32),('completionsQueue',16),
                      ('networkQueue',4),('appQueue',4),('clientsQueue',2)]), 'queue ceiling')
            if row['boundary'] == 'closed':
                need(queue['admissionAvailable'] == 4 and queue['inboundAvailable'] == 8 and
                     all(v == 2 for v in queue['outboundAvailable'].values()) and queue['queuedBytes'] == 0, 'reservations leaked after close')
    # Every started one-second tick must be represented. Exact delay is retained;
    # this is a sampling observation, not a claim about an unsampled hard peak.
    duration = samples[-1]['localNanos'] - samples[0]['localNanos']
    need(sum(r['boundary'] == 'periodic' for r in samples) >= max(0, duration//1_000_000_000 - 1), 'missing required periodic resource samples')
    for window in ['warmup', *admitted['localSmoke']['windows']]:
        need(sum(r['boundary'] == 'window-start' and r['window'] == window for r in samples) == 1, 'missing window boundary sample')
    return record, dict(samples=len(samples), sampledRssPeakBytes=max(r['VmRSSBytes'] for r in samples),
                        heapPeakBytes=max(r['heapUsedBytes'] for r in samples))


def trace_identity(rows, record):
    need(rows and [r['order'] for r in rows] == list(range(1,len(rows)+1)), 'missing trace event')
    need(all(r['pid'] == record['pid'] and r['node'] == record['node'] for r in rows), 'trace process identity')
    need(all(a['localNanos'] <= b['localNanos'] for a,b in zip(rows,rows[1:])), 'trace local clock reversal')
    for row in rows:
        if 'forceStartNanos' in row:
            need(row['window'].startswith('instrumented') and
                 row['forceStartNanos'] <= row['forceEndNanos'] <= row['localNanos'], 'force timing/window')
    for window in ('instrumented-a','instrumented-b'):
        forced = [r for r in rows if r['event'] == 'FORCE' and r.get('window') == window]
        need(all('forceStartNanos' in r for r in forced), 'missing instrumented force timing')


def configured_physical(root, calls, traces):
    reports = {node:configured.inspect(root/node) for node in traces}
    need(all(r['sequence'] == 76 for r in reports.values()), 'configured retained sequence')
    need(len({tuple(r['anchors']) for r in reports.values()}) == 1, 'configured retained prefix mismatch')
    # Actual force records, not just self-reported durable receipt hashes.
    from scripts.v50 import admission_format as fmt
    anchors = reports['node-1']['anchors']
    entries, voters, proof_forces = {}, {}, {}
    for node, rows in traces.items():
        for row in rows:
            if row['event'] != 'FORCE':
                continue
            encoded = physical.raw(row['record'])
            need(len(encoded) <= 16384, 'configured record encoding ceiling')
            if row['kind'] == 'ENTRY':
                r = fmt.record(encoded,5,1<<20)
                identity,epoch,incarnation,index,op = r.take(32),r.number('q'),r.take(16),r.number('q'),r.number('B')
                r.number('q');r.number('q');r.take(32)
                size,digest = r.number('i'),r.take(32); payload=r.take(size);r.end()
                need(fmt.sha(payload) == digest and anchors[index-1] == encoded[16:48].hex(), 'configured forced ancestry')
                entries[index] = op,payload
                voters.setdefault((epoch,incarnation,index,encoded[16:48]),set()).add(node)
            elif row['kind'] == 'PROOF':
                r = fmt.record(encoded,6);r.take(32);r.number('q');r.take(16);index=r.number('q')
                proof_forces.setdefault(index,set()).add(node)
    chosen = {identity[2] for identity,nodes in voters.items() if len(nodes)>=2}
    need(chosen == set(range(1,len(anchors)+1)) and all(len(proof_forces.get(i,set()))>=2 for i in chosen), 'configured actual force quorum missing')
    state=model.initial(plan.load());mutations=[]
    for i in sorted(entries):
        op,payload=entries[i]
        if op <= 8:
            state.apply(op,payload);mutations.append((op,model.sha(payload)))
        else:
            need(op == 9 and not payload,'unexpected configured auxiliary entry')
    expected=[(model.OP_IDS[c['operation']],c['payloadSha256']) for c in calls if c['operation'] in model.OP_IDS]
    need(mutations == expected and state.sequence == 76,'configured mutation projection')
    # Published V5.0 does not use automatic read NO_OPs.
    need(len(anchors)-len(mutations) <= 2,'configured control relabelled automatic barriers')
    genesis_bytes=(root/'node-1/genesis.gsr').read_bytes()
    genesis=fmt.genesis(genesis_bytes);genesis['raw']=genesis_bytes
    manifest=fmt.manifest((root/'node-1/manifest.gsr').read_bytes(),genesis)
    replies={model.sha(physical.raw(r['frame'])) for events in traces.values() for r in events if r['event']=='REPLY'}
    publications={};successes=set();expected_calls={c['opId']:c for c in calls}
    for node,events in traces.items():
        forced=set();remote_entry=set();remote_proof=set();current=None
        for event in events:
            kind=event['event']
            if kind=='FORCE':
                raw=physical.raw(event['record']);forced.add((event['kind'],raw[16:48].hex()))
                if event['kind']=='PROOF' and node=='node-1':
                    reader=fmt.record(raw,6);reader.take(32);reader.number('q');reader.take(16);index=reader.number('q')
                    need(anchors[index-1] in remote_entry,'configured proof before remote durable entry ACK')
            elif kind in ('REPLY','RECEIVED'):
                encoded=physical.raw(event['frame']);request=physical.raw(event['request'])
                need(len(encoded)<=1<<20 and len(request)<=1<<20,'configured frame bound')
                message=fmt.wire(encoded,manifest);sent=fmt.wire(request,manifest)
                need(all(message[k]==sent[k] for k in ('epoch','incarnationId','traceId','eventSequence')) and
                     message['sender']==sent['recipient'] and message['recipient']==sent['sender'],'configured response correlation')
                if kind=='RECEIVED':need(model.sha(encoded) in replies,'configured response lacks actual peer')
                if message['type'] in ('DURABLE_ACK','COMMIT_PROOF_ACK'):
                    entry=message['type']=='DURABLE_ACK';digest=message['payload']['entryDigest' if entry else 'proofDigest']
                    if kind=='REPLY':need(('ENTRY' if entry else 'PROOF',digest) in forced,'configured ACK before own force')
                    else:(remote_entry if entry else remote_proof).add(digest)
            elif kind=='AFTER_APPLICATION_PUBLICATION' and node=='node-1':
                index=event['index']
                # Each retained proof is also force-observed by an actual follower.
                proof_rows=[r for r in events if r['event']=='FORCE' and r['kind']=='PROOF' and r['order']<event['order']]
                matching=[]
                for r in proof_rows:
                    encoded=physical.raw(r['record']);reader=fmt.record(encoded,6);reader.take(32);reader.number('q');reader.take(16)
                    if reader.number('q')==index:matching.append(encoded[16:48].hex())
                need(any(('PROOF',digest) in forced and digest in remote_proof for digest in matching),'configured publication before proof quorum')
                publications[index]=event['order']
            elif kind=='CLIENT_INVOKE':current=event
            elif kind=='CLIENT_RESULT':
                need(current is not None and current['opId']==event['opId'],'configured unmatched call result')
                if event['command']=='call':
                    call=expected_calls[event['opId']]
                    if call['operation'] in model.OP_IDS:
                        index=call['afterSequence']-4+1
                        need(node=='node-1' and current['order']<publications.get(index,-1)<event['order'],'configured success before own publication')
                    successes.add(event['opId'])
                current=None
    need(successes==set(expected_calls),'configured missing success observation')
    return dict(status='PASS',chosen=len(chosen),mutations=len(mutations),finalSequence=state.sequence)




def distribution(samples):
    ordered=sorted(samples)
    need(ordered and all(type(v) is int and v>=0 for v in ordered),'empty/invalid timing samples')
    return dict(samples=len(ordered),p50Nanos=ordered[math.ceil(.5*len(ordered))-1],
                p95Nanos=ordered[math.ceil(.95*len(ordered))-1],p99Nanos=ordered[math.ceil(.99*len(ordered))-1])


def timing(rows, windows, exchanges, traces, manifest=None):
    """Same-clock distributions. ABBA is descriptive, with no speedup acceptance threshold."""
    result={}
    for window in windows:
        name=window['window'];own=[r for r in rows if r['window']==name]
        duration=interval(window,'startNanos','endNanos')
        rate=len(own)*1e9/duration if duration else None
        result[name]=dict(attempted=len(own),completed=len(own),successfulWrites=sum(r['operation'] in model.OP_IDS for r in own),
                         successfulReads=sum(r['operation'] not in model.OP_IDS for r in own),
                         touchedMutationDocuments=sum(len(r['keys']) for r in own if r['operation'] in model.OP_IDS),
                         admission='unsupported: no separate public admission timestamp',
                         elapsedNanos=duration,attemptedPerSecond=rate,completedPerSecond=rate,
                         api={op:distribution([interval(r,'apiStartNanos','apiEndNanos') for r in own if r['operation']==op]) for op in model.OPERATIONS},
                         controller={op:distribution([interval(exchanges[r['opId']][1],'startNanos','endNanos') for r in own if r['operation']==op]) for op in model.OPERATIONS})
    forces={};queues={}
    for node,events in traces.items():
        queued={}
        for event in events:
            if event['event']=='FORCE' and 'forceStartNanos' in event:
                forces.setdefault(node,{}).setdefault(event['window'],{}).setdefault(event['kind'],[]).append(interval(event,'forceStartNanos','forceEndNanos'))
            if manifest is None:continue
            if event['event']=='SEND_QUEUED':queued[event['id']]=event
            if event['event']=='REQUEST':
                request=physical.f.wire(physical.raw(event['request']),manifest)
                kinds={'PREPARE':'PREPARE','SELECTED_OFFER':'INSTALL','ACCEPT':'ACCEPT','COMMIT_PROOF':'PROOF','HEARTBEAT':'HEARTBEAT'}
                if request['type'] not in kinds:continue
                before=queued.get(request['eventSequence'])
                need(before is not None and before['kind']==kinds[request['type']],'missing protocol executor observation')
                need(before['peer']==request['recipient'] and before['order']<event['order'] and
                     before['localNanos']<=event['localNanos'],'network queue causal interval')
                window=event.get('window','startup')
                if window.startswith('instrumented'):
                    queues.setdefault(node,{}).setdefault(window,[]).append(event['localNanos']-before['localNanos'])
    force_summary={n:{w:{k:distribution(v) for k,v in kinds.items()} for w,kinds in windows.items()} for n,windows in forces.items()}
    queue_summary={n:{w:distribution(v) for w,v in windows.items()} for n,windows in queues.items()}
    if manifest is not None:
        need(all(any(window in counts for counts in queue_summary.values()) for window in ('instrumented-a','instrumented-b')),'missing instrumented queue observations')
    return dict(windows=result,force=force_summary,queue=queue_summary,
                queueBoundary='executor submission to actual request write; includes serialization/connection/reservation; same JVM',
                instrumentation='correctness and resource sampling always on; B includes force and queue duration detail')


def artifacts(root,mode,adapter,pinned,source_inventory):
    classes=root/('classes-'+mode)
    need(storage.inventory(classes)==adapter['classes'],'compiled adapter inventory differs')
    need(adapter['sources'] and all(source_inventory.get(p)==digest for p,digest in adapter['sources'].items()),'mixed adapter source')
    paths=[retained_artifacts.recorded_path(a['path']) for a in adapter['artifacts']]
    need(len(paths)==(1 if mode=='published-v4.4-local' else 2) and len(set(paths))==len(paths) and
         len({p.parent for p in paths})==1 and
         adapter['cp']==os.pathsep.join(map(str,[*paths,paths[0].parent.parent/classes.name])), 'isolated adapter classpath')
    names=[]
    for artifact in adapter['artifacts']:
        path=retained_artifacts.retained(root,artifact['path'],artifact['sha256'])
        if mode!='candidate-v5.1-automatic':need(pinned[path.name]==artifact['sha256'],'wrong control artifact')
        else:need(path.name.endswith('-5.1.0-SNAPSHOT.jar'),'wrong candidate version')
        with zipfile.ZipFile(path) as archive:
            names+=archive.namelist()
    need(not(set(adapter['classes'])&set(names)),'adapter shadows production class')
    need(not any('/V51Measured' in n or '/V51PerformanceObserver' in n or '/V51Measurement' in n or '/V51SmallPerformance' in n for n in names),'measurement assets packaged into production')


def physical_trace_values(root):
    from .public_qualification_evidence import traces_at
    return traces_at(root).values()


def validate(root):
    root=Path(root).resolve();admitted=plan.load(root/'plan.json');execution=read(root/'execution.json')
    need(execution['execution'] == admitted['execution'] and execution['paidCloud'] is False, 'measurement provenance')
    if (root/'receipt.json').exists():
        receipt=read(root/'receipt.json')
        need(receipt['status']=='PASS' and not receipt['cleanupErrors'] and 0<=receipt['cleanupNanos']<=60_000_000_000 and
             0<receipt['elapsedNanos']<=900_000_000_000,'incomplete final qualification')
        negatives=read(root/'negatives.json')
        need(len(negatives)==receipt['negativeCases']>=30 and all(n['status']=='REJECTED' for n in negatives),'incomplete negative qualification')
    original_roots={retained_artifacts.recorded_path(a['path']).parent.parent for adapter in execution['adapters'].values() for a in adapter['artifacts']}
    need(len(original_roots)==1, 'mixed recorded evidence roots')
    location=retained_artifacts.EvidenceLocation(root,next(iter(original_roots)))
    expected=model.expected(admitted);results={};pids=set();toolchains=set()
    source_inventory=read(root/'source-inventory.json')
    need(model.sha((root/'source-inventory.json').read_bytes())==execution['sourceInventorySha256'],'source inventory binding')
    pinned={a['artifact']+'-'+a['version']+'.jar':a['sha256'] for a in admitted['publishedControls']['artifacts']}
    need(storage.inventory(root/'source') == read(root/'source-before.json') == read(root/'source-after.json'), 'source backup changed')
    semantic.source_backup(root/'source',model.initial(admitted))
    for mode in admitted['modes']:
        directory=root/mode;adapter=execution['adapters'][mode];rows=read(directory/'calls.json')
        calls(rows,admitted)
        artifacts(root,mode,adapter,pinned,source_inventory)
        nodes=['local'] if mode == 'published-v4.4-local' else ['node-1','node-2','node-3']
        records={};resources={};traces={}
        for artifact in adapter['artifacts']:
            if mode != 'candidate-v5.1-automatic':
                need(pinned[Path(artifact['path']).name] == artifact['sha256'], 'wrong published control artifact')
        for node in nodes:
            record,sampled=process(directory,mode,node,adapter,admitted);records[node]=record;resources[node]=sampled
            need(record['pid'] not in pids,'serial/reused voter process identity');pids.add(record['pid'])
            identity=record['ready']['identity'];toolchains.add((identity['javaRuntime'],identity['javaVendor']))
            if node != 'local':
                traces[node]=lines(directory/(node+'-trace.jsonl'));trace_identity(traces[node],record)
        if len(nodes)==3:
            need(max(r['readyNanos'] for r in records.values()) < min(r['endNanos'] for r in records.values()), 'serial stand-in for concurrent voters')
        exchanges={e['request']['opId']:(r,e) for r in records.values() for e in r['exchanges']}
        for row in rows:
            need(row['opId'] in exchanges,'unknown call exchange')
            record,exchange=exchanges[row['opId']]
            need(row['node']==record['node'] and row['pid']==record['pid'] and
                 all(row[k]==v for k,v in exchange['response']['call'].items()),'call tape differs from actual response')
        windows=read(directory/'windows.json')
        need([w['window'] for w in windows]==['warmup',*admitted['localSmoke']['windows']],'window order')
        previous=0
        for window in windows:
            need(previous<=window['startNanos'] and interval(window,'startNanos','endNanos')<=30_000_000_000,'window bound/order')
            previous=window['endNanos']
            for row in rows:
                if row['window']==window['window']:
                    exchange=exchanges[row['opId']][1]
                    need(window['startNanos']<=exchange['startNanos']<=exchange['endNanos']<=window['endNanos'],'call outside its controller window')
        if mode=='published-v4.4-local':
            proof=semantic.selected_checkpoint(directory/'store',expected['state'])
        else:
            restored=read(root/('restore-'+mode)/'restore.stdout')
            semantic.state_observation(restored,expected['state'])
            proof=physical.automatic(directory,rows,traces,evidence_location=location) if mode=='candidate-v5.1-automatic' else configured_physical(directory,rows,traces)
        manifest_bytes=(directory/'node-1/manifest.gsr').read_bytes() if mode=='candidate-v5.1-automatic' else None
        manifest=dict(physical.f.inspect(manifest_bytes,'MANIFEST'),digest=manifest_bytes[16:48].hex()) if manifest_bytes else None
        results[mode]=dict(status='PASS',calls=len(rows),measuredCalls=80,latency=summary(rows),resources=resources,physical=proof,
                           measurements=timing(rows,windows,exchanges,traces,manifest))
    need(len(toolchains)==1 and len(pids)==7,'toolchain/process-set identity')
    from .performance_failover import validate as validate_failover
    failure_root=root/'failover'
    failure=validate_failover(failure_root,read(failure_root/'receipt.json'),read(failure_root/'history.json'),admitted,evidence_location=location)
    candidate_artifacts=execution['adapters']['candidate-v5.1-automatic']['artifacts']
    for trace in physical_trace_values(failure_root):
        for identity in (r for r in trace if r['event']=='PERFORMANCE_IDENTITY'):
            need((identity['javaRuntime'],identity['javaVendor']) in toolchains,'mixed failover toolchain')
            need(all(identity[k+'Source']==a['path'] and identity[k+'Sha256']==a['sha256'] for k,a in zip(('core','replication'),candidate_artifacts)),'mixed failover artifacts')
    for mode in ('candidate-v5.1-automatic','failover'):
        manifest=physical.f.inspect((root/mode/'node-1/manifest.gsr').read_bytes(),'MANIFEST')
        seal=physical.f.inspect((root/mode/'node-1/bootstrap-seal.gsr').read_bytes(),'SEAL')
        receipt=physical.f.inspect(physical.raw(seal['receipt']),'RECEIPT')
        sealed=physical.f.inspect(physical.raw(receipt['plan']),'PLAN')
        policy={k:v for k,v in admitted['automaticPolicy'].items() if k!='applyTo'}
        need(len(sealed['targets'])==3 and all(t['bounds']==admitted['replicationBounds'] and t['policy']==policy for t in sealed['targets']),'sealed bounds/policy drift')
    stages=read(root/'stages.json')
    need([s['name'] for s in stages]==[s['name'] for s in admitted['budgets']['stages'] if s['name']!='cleanup'],'stage schedule')
    previous=0
    for stage,limit in zip(stages,admitted['budgets']['stages']):
        if stage['name']=='validation' and 'endNanos' not in stage:continue
        need(stage['status']=='PASS' and previous<=stage['startNanos'] and interval(stage,'startNanos','endNanos')<=limit['seconds']*1_000_000_000,'stage time budget/order')
        previous=stage['endNanos']
    return dict(status='PASS',modes=results,failover=failure,toolchain=list(next(iter(toolchains))),paidCloud=False)
