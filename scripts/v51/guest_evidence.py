"""Independent replay of explicitly selected packaged guest tapes.

Inputs include controller-retained command receipts and the authenticated package
manifest, not just a guest's PASS flag. This checks serialized logical answers,
dispatch and process/resource identity. Concurrent semantics require the separate
physical-history oracle; this module cannot qualify a full cloud cell.
"""
from pathlib import Path
import re
import uuid
from . import cloud_guest as guest, cloud_package as package, cloud_workload_contract as contract
from . import performance_model as m, performance_plan as plan, performance_evidence as old
from . import remote_command as c, remote_collection as parts, remote_schedule as schedule
from . import remote_schedule_evidence as scheduling, remote_rich_evidence as rich
from . import storage_inspector as storage
from . import guest_workload_spec as workload


def retained(root, manifest, owner):
    """Recheck the complete relocated inventory, including changes after extraction."""
    parts.validate_manifest(manifest, m.sha(m.canonical(owner)))
    index = c.read(root/parts.INDEX)
    m.need(m.sha((root/parts.INDEX).read_bytes()) == manifest['memberIndexSha256'], 'guest retained index digest')
    paths = list(root.rglob('*')); total = 0
    m.need(len(paths) <= 4*parts.LIMITS['files'], 'guest retained path count')
    for path in paths:
        m.need(not path.is_symlink() and (path.is_dir() or path.is_file()), 'guest retained file type')
        if path.is_file():
            size = path.stat().st_size; total += size
            m.need(size <= parts.LIMITS['memberBytes'] and total <= parts.LIMITS['expandedBytes'], 'guest retained byte bound')
    actual = {n:dict(bytes=v['size'], sha256=v['sha256']) for n,v in storage.inventory(root).items() if n != parts.INDEX}
    m.need(actual == index, 'guest retained inventory changed')
    return set(index)


def commands(root, config, transcript, *, physical=False, backup=False):
    m.need(type(transcript) is list and 2 <= len(transcript) <= 2000, 'guest controller transcript bound')
    store = c.CommandStore(root/'store', config['binding'])
    rows, identifiers, process, previous = [], set(), None, 0
    for item in transcript:
        m.need(set(item) == {'request', 'receipt'}, 'guest transcript fields')
        request, receipt = item['request'], item['receipt']
        c.validate_request(request, config['binding'])
        identity = store.envelope(request, receipt['state'])
        m.need(all(receipt.get(k) == v for k,v in identity.items()), 'guest controller receipt binding')
        command_id = request['commandId']
        m.need(command_id not in identifiers, 'guest duplicate controller command'); identifiers.add(command_id)
        observed = receipt['process']
        m.need(set(observed) == {'pid', 'bootId', 'startTicks'} and type(observed['pid']) is int and observed['pid'] > 0 and
               str(uuid.UUID(observed['bootId'])) == observed['bootId'] and re.fullmatch('[0-9]+', observed['startTicks']),
               'guest command process identity')
        if process is None: process = observed
        m.need(process == observed and previous <= receipt['startedNanos'] <= receipt['endedNanos'], 'guest command lifetime/order')
        previous = receipt['endedNanos']
        if item is not transcript[-1]:
            m.need(store.query(request) == receipt, 'guest retained/controller receipt differs')
            started = c.read(store.command_path(request)/'started.json')
            m.need(started == store.envelope(request, 'RUNNING', process=process, startedNanos=receipt['startedNanos']),
                   'guest started receipt differs')
        rows.append((request, receipt))
    # The in-progress collect command is deliberately excluded from its own archive.
    last_request, last = rows[-1]
    collection_payload=dict(physical=True,backup=True) if backup else ({'physical':True} if physical else {})
    m.need(last_request['command'] == 'collect' and m.canonical(last_request['payload']) == m.canonical(collection_payload) and last['state'] == 'SUCCEEDED',
           'guest final collection receipt')
    wanted = identifiers - {last_request['commandId']}
    m.need({p.name for p in (root/'store/commands').iterdir()} == wanted, 'guest retained command coverage')
    for request, receipt in rows[:-1]:
        folder = store.command_path(request)
        m.need({p.name for p in folder.iterdir()} == {'request.json','started.json','terminal.json'}, 'guest command inventory/cancellation')
        if request['command'] == 'collect':
            # The qualification deliberately requests collection once while live.
            m.need(request['payload'] == {} and receipt['state'] == 'FAILED' and
                   receipt['error'] == dict(type='ValueError', message='guest collection requires stopped JVM'),
                   'guest unexpected failed command')
        else: m.need(receipt['state'] == 'SUCCEEDED', 'guest unsuccessful lifecycle/workload command')
    return rows, process


def process(root, config, manifest, base, rows, service):
    mode = config['mode']; node = 'local' if mode == package.MODES[0] else config['binding']['node']
    starts = [(q,r) for q,r in rows if q['command'] == 'start-voter']
    stops = [(q,r) for q,r in rows if q['command'] == 'stop-voter']
    m.need(len(starts) == len(stops) == 1 and starts[0][0]['payload'] == {} and
           stops[0][0]['payload'] == {'forced':False} and stops[0][1]['result'] == {'stopped':True}, 'guest JVM lifecycle coverage')
    start, stop = starts[0][1], stops[0][1]
    prepares = [(q,r) for q,r in rows if q['command'] == 'prepare-cell']
    m.need(len(prepares) <= 1, 'guest preparation coverage')
    for request, receipt in prepares:
        m.need(config['binding']['node'] == 'node-1' and request['payload'] == {} and receipt['result'] == {'prepared':True} and
               receipt['endedNanos'] <= start['startedNanos'], 'guest preparation role/order')
    for request, receipt in rows[:-1]:
        if request['command'] in ('fault','window','collect'):
            m.need(start['endedNanos'] <= receipt['startedNanos'] <= receipt['endedNanos'] <= stop['startedNanos'], 'guest live command order')
    ready = start['result']; identity = ready['identity']; record = c.read(root/(node+'-jvm.json'))
    closed = c.read(root/(node+'-stop.json'))
    m.need(set(record) == {'pid','startTicks','bootId','args'} and type(record['pid']) is int and record['pid'] > 0 and
           record['pid'] != service['pid'] and record['bootId'] == service['bootId'] and
           re.fullmatch('[0-9]+',record['startTicks']), 'guest JVM OS identity')
    m.need(closed == dict(record, exitCode=0, forced=False, readerReaped=True), 'guest JVM unclean stop')
    m.need(ready['status'] == 'STARTED' and all(identity[k] == v for k,v in
           dict(pid=record['pid'],node=node,mode=mode,generation=1,javaMajor=21,processors=2).items()), 'guest loaded JVM identity')
    env = contract.load()['environment']; spec = manifest['modes'][mode]; base = Path(base)
    m.need(base.is_absolute() and '..' not in base.parts and manifest['jvmArguments'] == env['jvmArguments'] and
           identity['jvmArguments'] == env['jvmArguments'] and identity['javaVendor'] == env['javaVendor'] and
           identity['javaRuntime'] == env['javaRuntime'], 'guest loaded JVM configuration')
    files = {v['path']:v for v in manifest['files']}
    local_plan = 'source-inputs/docs/v5x/v5.1/phase6-plan.json'
    m.need(identity['planFileSha256'] == files[local_plan]['sha256'] == m.sha(plan.PLAN.read_bytes()), 'guest loaded frozen plan')
    m.need(identity['host']['os'] == 'Linux' and type(identity['observedClockResolutionNanos']) is int and
           identity['observedClockResolutionNanos'] > 0, 'guest host/clock observation')
    m.need(spec['main'] == package.MAINS[mode] and spec['classes'] == 'classes-'+mode and
           len(spec['jars']) == (1 if node == 'local' else 2), 'guest isolated classpath')
    for kind,name in zip(('core','replication'),spec['jars']):
        m.need(identity[kind+'Source'] == str(base/name) and identity[kind+'Sha256'] == files[name]['sha256'], 'guest loaded artifact identity')
    cp = ':'.join(str(base/n) for n in [*spec['jars'],spec['classes']])
    argv = [str(base/'runtime/bin/java'),*env['jvmArguments'],'-cp',cp,package.PACKAGE+spec['main'],
            config['root'],'run' if node == 'local' else node[-1],str(base/local_plan),str(Path(config['root'])/'source')]
    m.need(record['args'] == argv, 'guest JVM argv changed')
    m.need(start['endedNanos'] <= stop['startedNanos'] <= stop['endedNanos'] <= rows[-1][1]['startedNanos'], 'guest JVM lifecycle order')
    return node, record, start, stop


def validate(root, config, manifest_bytes, package_root, transcript, *, active, healthy=False, physical=False, backup=False, trace_budget=None):
    """Validate one downloaded member against independently retained controller inputs."""
    root = c.directory(root); guest.validate(config); m.need(type(active) is bool and type(healthy) is bool, 'guest issuer/scope flag')
    cell, preset = workload.selection(config)
    m.need('workload' not in config or healthy, 'canonical tape requires complete window evidence')
    m.need(config['mode'] != package.MODES[0] or config['binding']['node'] == package.control_node(config) and active, 'guest local issuer role')
    manifest = m.strict_json(manifest_bytes)
    m.need(m.sha(manifest_bytes) == config['packageManifestSha256'] and manifest['source'] == config['binding']['source'],
           'guest evidence package binding')
    m.need(type(transcript) is list and transcript, 'guest controller transcript absent')
    names = retained(root,transcript[-1]['receipt']['result'],config['binding'])
    m.need(type(physical) is bool and (not physical or healthy and config['mode'] in package.MODES[1:]), 'guest physical scope')
    m.need(type(backup) is bool and (not backup or physical and active), 'guest backup scope')
    rows, service = commands(root,config,transcript,physical=physical,backup=backup)
    m.need(backup or all(q['command'] not in ('backup','restore-backup') for q,_ in rows), 'guest unrequested backup/restore')
    node, record, started, stopped = process(root,config,manifest,package_root,rows,service)
    windows = [(q,r) for q,r in rows if q['command'] == 'window']
    specs = workload.specs(config)[:None if healthy else 1]
    m.need(len(windows) == len(specs)*int(active), 'guest warmup/healthy issuer coverage')
    activations=[r for q,r in rows if q['command']=='fault' and q['payload']==dict(action='activate')]
    configured=config['mode']==package.MODES[1]
    m.need(len(activations)==int(configured and active) and
           (not configured or not active or node==package.control_node(config) and activations[0]['endedNanos']<=windows[0][1]['startedNanos']),
           'guest configured activation role/coverage/order')
    m.need(sum(q['command'] == 'collect' for q,_ in rows) == 1+int(active), 'guest live collection negative coverage')
    limits=contract.load()['evidence']
    ceiling=limits['traceBytes'] if preset=='canonical' else limits['perNodePerCellTraceBytes']
    budget=[ceiling] if trace_budget is None else trace_budget
    m.need(type(budget) is list and len(budget)==1 and type(budget[0]) is int and 0<=budget[0]<=ceiling,
           'guest decoded trace budget')
    if preset=='canonical':
        stored=sum(p.stat().st_size for p in root.glob(node+'-*.jsonl*'))
        m.need(stored<=limits['perNodePerCellTraceBytes'],'node/cell trace budget')
    exchanges = c.read(root/(node+'-exchanges.json'))
    originals = rich.lines(root,node+'-results',budget)
    m.need(0 < len(originals) == len(exchanges) <= 2000, 'guest original response coverage')
    results = {r['opId']:r for r in originals}
    m.need(len(results) == len(originals) and len({e['request']['opId'] for e in exchanges}) == len(exchanges), 'guest duplicate JVM response/request')
    for i, exchange in enumerate(exchanges,1):
        request, response = exchange['request'],exchange['response']
        m.need(request['opId'] == f'{node}-g1-{i}' and results.get(request['opId']) == response and
               exchange['outcome'] == response['outcome'] == 'SUCCESS' and
               all(response[k] == v for k,v in dict(opId=request['opId'],command=request['command'],node=node,
                   pid=record['pid'],mode=config['mode']).items()), 'guest JVM request/result binding')
        m.need(started['endedNanos'] <= exchange['startNanos'] <= exchange['endNanos'] <= stopped['endedNanos'] and
               0 <= response['workerStartNanos'] <= response['workerEndNanos'], 'guest exchange timing')
    m.need(exchanges[-1]['request']['command'] == originals[-1]['command'] == 'close' and
           stopped['startedNanos'] <= exchanges[-1]['startNanos'], 'guest final close response')
    mapped = {exchanges[-1]['request']['opId']}; passive_windows=[]
    for request, receipt in rows:
        if request['command'] == 'fault':
            answer = receipt['result']; op = answer['opId']
            configuration = healthy and not active and request['payload'] in [dict(action='configure',window=s['window']) for s in specs]
            m.need((request['payload'] in ({'action':'status'},{'action':'activate'}) or configuration) and results.get(op) == answer and
                   answer['command'] == request['payload']['action'] and op not in mapped, 'guest control/JVM binding')
            if answer['command'] == 'activate':
                m.need(config['mode'] == package.MODES[1] and node == package.control_node(config), 'guest activation role')
            exchange = next(e for e in exchanges if e['request']['opId'] == op)
            wanted=dict(command=answer['command'],opId=op)
            if configuration:wanted['window']=request['payload']['window']
            m.need(exchange['request']==wanted, 'guest control JVM request')
            m.need(receipt['startedNanos'] <= exchange['startNanos'] <= exchange['endNanos'] <= receipt['endedNanos'], 'guest control interval')
            if configuration:
                passive_windows.append(request['payload']['window'])
            mapped.add(op)
    m.need(passive_windows == ([s['window'] for s in specs] if healthy and not active else []), 'guest passive window coverage')
    calls = [e for e in exchanges if e['request']['command'] == 'call']
    state = m.initial(plan.load())
    m.need(len(calls)==sum(len(s['calls']) for s in specs)*int(active), 'guest frozen call coverage')
    configured = [e for e in exchanges if e['request']['command'] == 'configure']
    m.need(len(configured)==len(specs) if active or healthy else not configured, 'guest window configuration coverage')
    for expected_spec,(request,receipt) in zip(specs,windows):
        name=expected_spec['window']; folder = root/('window-'+cell+'-'+name)
        m.need(request['payload'] == dict(cell=cell,preset=preset,window=name), 'guest warmup scope')
        spec = c.read(folder/'spec.json'); result = c.read(folder/'result.json')
        m.need(m.canonical(spec) == m.canonical(expected_spec), 'guest frozen warmup changed')
        validation = scheduling.validate(spec,rich.lines(folder,'arrivals',budget),result)
        m.need(validation['status'] == 'PASS' and receipt['result'] == dict(window=name,calls=len(spec['calls']),validation=validation),
               'guest warmup receipt differs')
        m.need(receipt['startedNanos'] <= result['startedNanos'] < result['endedNanos'] <= receipt['endedNanos'], 'guest warmup command interval')
        configured = [e for e in exchanges if e['request']['command'] == 'configure' and e['request'].get('window')==name]
        m.need(len(configured) == 1 and configured[0]['request'] == dict(command='configure',opId=configured[0]['request']['opId'],window=name) and
               receipt['startedNanos'] <= configured[0]['startNanos'] <= configured[0]['endNanos'] <= result['startedNanos'], 'guest warmup configuration')
        mapped.add(configured[0]['request']['opId'])
        window_calls=[e for e in calls if e['request'].get('window')==name]
        m.need(len(window_calls) == len(spec['calls']), 'guest frozen call coverage')
        # Concurrent lanes may reach the persistent pipe in a different order.
        # Match frozen ordinals, retaining the original opId and time bindings.
        m.need({e['request'].get('ordinal') for e in window_calls} == {v['ordinal'] for v in spec['calls']},
               'guest frozen ordinal coverage')
        if cell != 'healthy':window_calls.sort(key=lambda e:e['request']['ordinal'])
        arrivals = {r['ordinal']:r for r in result['calls']}
        for expected, exchange in zip(spec['calls'],window_calls):
            op = exchange['request']['opId']; response = exchange['response']; call = response['call']; arrival = arrivals[expected['ordinal']]
            m.need(exchange['request'] == dict(expected,command='call',opId=op) and op not in mapped, 'guest frozen JVM request')
            m.need(arrival['result'] == dict(outcome='SUCCESS',opId=op,resultSha256=m.sha(m.canonical(response))) and
                   arrival['invokedNanos'] <= exchange['startNanos'] <= exchange['endNanos'] <= arrival['endedNanos'], 'guest arrival/JVM response binding')
            m.need(call['outcome'] == 'SUCCESS' and all(call[k] == expected[k] for k in ('ordinal','window','cycle','operation','keys','lane')) and
                   call['payloadSha256'] == m.sha(bytes.fromhex(expected['payload'])), 'guest original call identity')
            m.need(response['workerStartNanos'] <= call['apiStartNanos'] < call['apiEndNanos'] <= response['workerEndNanos'] and
                   call['apiEndNanos']-call['apiStartNanos'] <= 9600*10**6, 'guest original API interval')
            if cell == 'healthy':
                m.need(call['beforeSequence'] == state.sequence, 'guest healthy before-sequence')
            answer = None
            if expected['operation'] in m.OP_IDS: state.apply(m.OP_IDS[expected['operation']],bytes.fromhex(expected['payload']))
            elif cell == 'healthy': answer = state.answer(expected['operation'],expected['cycle'])
            m.need(call['answerSha256'] == m.sha(m.canonical(call['answer'])), 'guest original answer digest')
            if cell == 'healthy':
                m.need(call['answer'] == answer and call['afterSequence'] == state.sequence, 'guest healthy logical answer/sequence')
            # Concurrent read answers are checked against their captured physical
            # prefix by guest_physical_evidence, never this static final state.
            mapped.add(op)
        if cell != 'healthy':
            apis=[exchange['response']['call'] for exchange in window_calls]
            m.need(any(a['apiStartNanos']<b['apiStartNanos']<a['apiEndNanos'] for a in apis for b in apis
                       if a['lane']!=b['lane']), 'missing real concurrent Java API overlap')
    backup_files={};backup_result=None
    if backup:
        from . import guest_backup_evidence
        op,backup_files,backup_result=guest_backup_evidence.validate(root,config,package_root,manifest,rows,exchanges,state,stopped)
        m.need(op not in mapped,'guest duplicate backup mapping');mapped.add(op)
    m.need(mapped == set(results), 'guest unaccounted JVM command')
    samples = rich.lines(root,node+'-samples',budget)
    for sample in samples:
        writer = sample['evidenceWriter']
        m.need(0 <= sample['localNanos']-sample['samplingStartNanos'] <= 9600*10**6 and
               0 <= writer['queuedBytes'] <= writer['peakBytes'] <= 16<<20 and
               0 <= writer['queuedRecords'] <= writer['peakRecords'] <= 256, 'guest sampling/writer bound')
        if config['mode'] == package.MODES[2]:
            pending = sample['queues']['maintenancePending']
            m.need(type(pending) is int and pending in (0,1) and (sample['boundary'] != 'closed' or pending == 0), 'guest maintenance drain')
    resources = old.resources(samples,config['mode'],node,record,[s['window'] for s in specs] if active or healthy else [])
    m.need(sum(s['boundary'] == 'window-start' for s in samples) == (len(specs) if active or healthy else 0), 'guest extra resource window')
    traces = []
    if node != 'local':
        traces = rich.lines(root,node+'-trace',budget)
        old.trace_identity(traces,dict(record,node=node))
        if config['mode'] == package.MODES[2]:
            m.need(all(r['groupId'] == config['groupId'] and r['generation'] == 1 for r in traces), 'guest trace group/generation')
    allowed = {node+'-'+s for s in ('jvm.json','exchanges.json','stop.json','stderr.log')} | {'store/binding.json'}
    allowed |= {f'store/commands/{q["commandId"]}/{n}.json' for q,_ in rows[:-1] for n in ('request','started','terminal')}
    if active: allowed |= {'window-'+cell+'-'+s['window']+'/'+n for s in specs for n in ('spec.json','result.json','arrivals.jsonl')}
    journals = {n for n in names if re.fullmatch(re.escape(node)+r'-(results|samples'+('' if node == 'local' else '|trace')+r')(-part[0-9]{4})?\.jsonl\.gz',n)}
    if physical:
        from . import guest_authority
        prefix='authority/'+node+'/'
        authority=guest_authority.inventory(root/'authority'/node)
        allowed|={prefix+n for n in authority}
    if backup:
        allowed|={'backup/export/'+n for n in backup_files}
        allowed|={'backup/'+n for n in ('backup-claim.json','backup-result.json','restore-claim.json','restore-result.json','restore.stdout','restore.stderr')}
    m.need(names == allowed | journals, 'guest collection closed inventory')
    return dict(status='PASS',execution='guest-healthy-evidence-only' if healthy else 'guest-warmup-evidence-only',node=node,mode=config['mode'],calls=len(calls),
        logicalSemanticsQualified=cell=='healthy',physicalHistoryQualified=False,backupRestore=backup_result,paidCloud=False,fullRemoteQualification=False,
        configSha256=m.sha(m.canonical(config)),collectionSha256=m.sha(m.canonical(rows[-1][1]['result'])),
        resources=resources,journals=dict(results=len(originals),samples=len(samples),trace=len(traces)))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('replay',type=Path); parser.add_argument('--controller',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True); parser.add_argument('--healthy',action='store_true'); parser.add_argument('--physical',action='store_true')
    parser.add_argument('--backup',action='store_true')
    args = parser.parse_args(); controller = c.read(args.controller)
    print(m.canonical(validate(args.replay,controller['config'],args.manifest.read_bytes(),controller['packageRoot'],
        controller['transcript'],active=controller['active'],healthy=args.healthy,physical=args.physical,backup=args.backup)).decode())
