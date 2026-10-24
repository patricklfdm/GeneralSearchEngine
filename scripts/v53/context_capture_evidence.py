"""Original-first physical replay of local protected capture/context replacement.

No selected-installation, fresh-process or remote campaign qualification is implied.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_source_release_evidence as source
from . import capture_recovery_evidence as capture

e, owner = source.e, source.owner
REBIND = ('CONTEXT_SOURCE_MEMBER_FORCED', 'CONTEXT_SOURCE_DIRECTORY_FORCED', 'CONTEXT_SOURCE_PARENT_FORCED',
          'CONTEXT_CANDIDATE_CREATED', 'CONTEXT_PREFIX_WRITTEN', 'CONTEXT_CANDIDATE_WRITTEN',
          'CONTEXT_CANDIDATE_FORCED', 'CONTEXT_CANDIDATE_PARENT_FORCED', 'CONTEXT_RENAMED', 'CONTEXT_PARENT_FORCED')
CUTS = capture.CUTS[:20]+('BASIS_PREFIX_WRITTEN',)+REBIND+capture.CUTS[20:]


def new_promise(initial, observed, counter):
    raw = observed['grants.gsr']; before = initial['grants.gsr']
    e.need(raw.startswith(before) and len(raw) >= len(before)+48, 'context capture original journal prefix')
    offset = len(before); length = 48+int.from_bytes(raw[offset+12:offset+16], 'big')
    frame = raw[offset:offset+length]; value = e.f.decode(frame, 'records', 'PROMISE')
    old = e.f.decode(e.decode(initial['pending.context'])[0][2], 'records', 'PROMISE')
    expected = dict(old, ballot=dict(old['ballot'], counter=counter), basisId=value['basisId'])
    e.need(value == expected and value['basisId'] != old['basisId'], 'context capture new promise identity')
    e.f.check_type(value['basisId'], 'uuid', {})
    e.need('sources/'+value['basisId'] not in {p.rsplit('/',1)[0] for p in initial}, 'context capture reused source identity')
    return frame, value


def transaction(initial, directories, promise_raw):
    promise = e.f.decode(promise_raw, 'records', 'PROMISE')
    segments, metadata, binding = e.decode(initial['pending.context'])
    backing = e.f.decode(segments[3], 'records', 'BASIS'); bp = 'sources/'+backing['basisId']+'/'
    old_backing = e.p.decode(initial[bp+'source.gscp']); _, original = e.reconstruct(segments[4], old_backing)
    current_path, _, current = e.current(initial)
    vote, _ = e.votes(initial['pending.accept'], original['capsule']['cut'])
    objects = dict(current['objects'])
    objects.update(original['objects'])
    for kind in ('ENTRY', 'ACCEPT', 'PAYLOAD', 'PROOF', 'CERTIFICATE'):
        if kind in vote: objects[e.digest(vote[kind])] = vote[kind]
    images = dict(current['images']); images.update(original['images'])
    packet_raw = e.packet_bytes(current['capsule'], objects, images); packet = e.p.decode(packet_raw)
    basis = dict(promise, voter=binding['node'], cut=current['capsule']['cut'], capsule=e.digest(packet['capsuleBytes']),
                 inventory=e.digest(packet['indexBytes']), accepted=e.digest(vote['ACCEPT']))
    basis_raw = e.f.encode('records', 'BASIS', basis); e.p.bind(packet, basis_raw)
    members = {'source.gscp': packet_raw}
    for h, size in images.items():
        image = initial.get(current_path+h+'.image', initial.get(bp+h+'.image'))
        e.need(image is not None and len(image) == size and e.digest(image) == h, 'context capture protected image')
        members[h+'.image'] = image
    next_segments = list(segments); next_segments[0] = e.f.canonical(dict(binding, backingPacket=e.info(packet_raw)))
    next_segments[2:4] = [promise_raw, basis_raw]; context_raw = e.encode(next_segments, metadata)
    intent = initial['selector.gsr']+promise_raw+basis_raw
    state = dict(initial); dirs = set(directories); steps = []
    def event(name): steps.append((name, dict(state), set(dirs)))
    event('PROMISE_BEFORE_WRITE'); state['grants.gsr'] += promise_raw
    event('PROMISE_WRITTEN'); event('PROMISE_FORCED')
    state['source.capture.gsr'] = b''; event('CAPTURE_INTENT_CREATED')
    state['source.capture.gsr'] = intent[:len(intent)//2]; event('CAPTURE_INTENT_PREFIX_WRITTEN')
    state['source.capture.gsr'] = intent
    for name in ('CAPTURE_INTENT_WRITTEN', 'CAPTURE_INTENT_FORCED', 'CAPTURE_INTENT_PARENT_FORCED'): event(name)
    prefix = 'sources/'+promise['basisId']; event('SOURCE_BEFORE_CREATE'); dirs.add(prefix); event('SOURCE_CREATED')
    for name in ['source.gscp']+sorted(n for n in members if n != 'source.gscp'):
        path = prefix+'/'+name; raw = members[name]; label = 'SOURCE_PACKET' if name == 'source.gscp' else 'SOURCE_IMAGE'
        state[path] = b''; event(label+'_CREATED'); state[path] = raw[:len(raw)//2]; event(label+'_PREFIX_WRITTEN')
        state[path] = raw; event(label+'_WRITTEN'); event(label+'_FORCED')
    event('SOURCE_FILES_DIRECTORY_FORCED'); event('SOURCE_DIRECTORY_FORCED'); event('BASIS_BEFORE_WRITE')
    prior = state['grants.gsr']; state['grants.gsr'] = prior+basis_raw[:len(basis_raw)//2]; event('BASIS_PREFIX_WRITTEN')
    state['grants.gsr'] = prior+basis_raw; event('BASIS_WRITTEN'); event('BASIS_FORCED')
    for _ in members: event('CONTEXT_SOURCE_MEMBER_FORCED')
    event('CONTEXT_SOURCE_DIRECTORY_FORCED'); event('CONTEXT_SOURCE_PARENT_FORCED')
    state['pending.context.next'] = b''; event('CONTEXT_CANDIDATE_CREATED')
    state['pending.context.next'] = context_raw[:len(context_raw)//2]; event('CONTEXT_PREFIX_WRITTEN')
    state['pending.context.next'] = context_raw
    for name in ('CONTEXT_CANDIDATE_WRITTEN', 'CONTEXT_CANDIDATE_FORCED', 'CONTEXT_CANDIDATE_PARENT_FORCED'): event(name)
    del state['pending.context.next']; state['pending.context'] = context_raw; event('CONTEXT_RENAMED'); event('CONTEXT_PARENT_FORCED')
    del state['source.capture.gsr']; event('CAPTURE_INTENT_DELETED'); event('CAPTURE_INTENT_CLEARED'); event('GRANT_BEFORE_RETURN')
    return steps


def events(path):
    result = source.load(path, 131072)
    return result


def match(path, files, dirs, label):
    actual, actual_dirs = owner.read_snapshot(path)
    e.need(actual == files and actual_dirs == dirs, 'context capture exact '+label)


def validate(root):
    root = Path(root); receipt = source.load(root/'receipt.json')
    matrix = receipt.get('schema') == 'gse-v53-context-capture-cuts-v1'
    expected = {'reference', 'receipt.json'} | (set(CUTS) if matrix else {'round-22', 'round-23', 'events-22.json', 'events-23.json'})
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()} == expected, 'context capture evidence inventory')
    source.validate(root/'reference'); initial, dirs = owner.read_snapshot(root/'reference/reopened')
    if matrix:
        for cut in CUTS:
            case = root/cut
            e.need(case.is_dir() and not case.is_symlink() and {p.name for p in case.iterdir()} ==
                   {'crash', 'recovery-crash', 'reopened', 'final', 'events.json'}, 'context capture cut inventory')
            crash, _ = owner.read_snapshot(case/'crash'); frame, _ = new_promise(initial, crash, 22)
            steps = transaction(initial, dirs, frame); at = next(i for i, row in enumerate(steps) if row[0] == cut)
            _, first, first_dirs = steps[at]; match(case/'crash', first, first_dirs, 'first interruption')
            # The second interruption is after all source/BASIS completion, immediately
            # before context replacement. It preserves whichever context/prefix survived.
            complete = next(row for row in steps if row[0] == 'CONTEXT_SOURCE_PARENT_FORCED')
            second = dict(first); second['grants.gsr'] = complete[1]['grants.gsr']
            second.update({p:b for p,b in complete[1].items() if p.startswith('sources/')})
            if 'source.capture.gsr' in second: second['source.capture.gsr'] = complete[1]['source.capture.gsr']
            match(case/'recovery-crash', second, complete[2], 'second interruption')
            final, final_dirs = steps[-1][1:]; match(case/'reopened', final, final_dirs, 'reopen'); match(case/'final', final, final_dirs, 'explicit grant')
            trace = events(case/'events.json'); e.exact(trace, 'first recovery resume')
            e.need(trace['first'] == [v[0] for v in steps[:at+1]], 'context capture first force order')
            e.need(trace['recovery'][-1] == 'CONTEXT_SOURCE_PARENT_FORCED' and not any(v in owner.ACKS for v in trace['recovery']), 'context capture recovery acknowledged')
            resumed = trace['resume']
            e.need(resumed.count('OPEN_RETURNED') == resumed.count('EXPLICIT_GRANT_RETURNED') == resumed.count('GRANT_BEFORE_RETURN') == 1
                   and resumed.index('OPEN_RETURNED') < resumed.index('GRANT_BEFORE_RETURN') < resumed.index('EXPLICIT_GRANT_RETURNED')
                   and not any(v in owner.ACKS-{'GRANT_BEFORE_RETURN'} for v in resumed), 'context capture explicit grant boundary')
        expected_receipt = dict(schema='gse-v53-context-capture-cuts-v1',status='PASS',cuts=list(CUTS),interruptions='injected-IOException',freshProcesses=False,runtimeEnabled=False)
    else:
        for counter in (22, 23):
            observed, _ = owner.read_snapshot(root/f'round-{counter}'); frame, _ = new_promise(initial, observed, counter)
            steps = transaction(initial, dirs, frame); final, dirs = steps[-1][1:]
            match(root/f'round-{counter}', final, dirs, 'clean capture')
            trace = events(root/f'events-{counter}.json'); e.need(trace[:len(steps)] == [v[0] for v in steps], 'context capture clean force order')
            e.need(trace.count('EXPLICIT_GRANT_RETURNED') == trace.count('GRANT_BEFORE_RETURN') == 2
                   and trace[len(steps)] == 'EXPLICIT_GRANT_RETURNED' and trace[-1] == 'EXPLICIT_GRANT_RETURNED', 'context capture clean explicit grant')
            # The owner also reserves one future publication image. That empty
            # completion slot is not an existing file in this physical snapshot.
            e.need(sum(p.endswith('.image') for p in final) == counter-17, 'context capture physical image count')
            initial = final
        expected_receipt = dict(schema='gse-v53-context-capture-v1',status='PASS',rounds=[22,23],maximumImages=7,nextCapture='CAPACITY_EXCEEDED',runtimeEnabled=False,selectedInstallEnabled=False)
    e.need(receipt == expected_receipt, 'context capture receipt scope')
    return dict(status='PASS',cases=len(CUTS) if matrix else 2,originalFirst=True,originalBallot=20,installedBallot=21,
                contextCaptureEnabled=True,selectedInstallEnabled=False,freshProcesses=False,runtimeEnabled=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    matrix = (root/'CAPTURE_INTENT_CREATED').exists()
    variants = {'reference': 'context checksum', 'missing': 'context capture evidence inventory',
                'original-vote': 'context capture exact '+('explicit grant' if matrix else 'clean capture'),
                'backing': 'context capture exact '+('explicit grant' if matrix else 'clean capture'),
                'stale-context': 'context capture exact '+('explicit grant' if matrix else 'clean capture'),
                'scope': 'context capture receipt scope', 'order': 'context capture '+('first' if matrix else 'clean')+' force order',
                'implicit-grant': 'context capture '+('explicit grant boundary' if matrix else 'clean explicit grant')}
    if matrix: variants['second-cut'] = 'context capture exact second interruption'
    for name, reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-context-capture-negative-') as tmp:
            moved = Path(tmp)/'evidence'; shutil.copytree(root, moved)
            case = moved/'CONTEXT_PREFIX_WRITTEN' if matrix else moved
            final = case/'final' if matrix else case/'round-22'
            if name == 'reference':
                p = moved/'reference/original-retirement/initial/pending.context'; raw=p.read_bytes();p.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name == 'missing': shutil.rmtree(moved/'CAPTURE_INTENT_CREATED' if matrix else final)
            elif name == 'original-vote': (final/'pending.accept').write_bytes(b'changed')
            elif name == 'backing': next((final/'sources').rglob('source.gscp')).unlink()
            elif name == 'stale-context': shutil.copyfile(moved/'reference/reopened/pending.context', final/'pending.context')
            elif name == 'scope':
                p=moved/'receipt.json';v=source.load(p);v['runtimeEnabled']=True;p.write_bytes(e.f.canonical(v))
            elif name == 'second-cut': (case/'recovery-crash/pending.accept').write_bytes(b'changed')
            else:
                p=case/'events.json' if matrix else case/'events-22.json';v=events(p)
                trace=v['first' if name=='order' else 'resume'] if matrix else v
                trace.remove('BASIS_FORCED' if name=='order' else 'EXPLICIT_GRANT_RETURNED');p.write_bytes(e.f.canonical(v))
            try: validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong context capture negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else: raise ValueError('accepted context capture mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-context-capture-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'context capture portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
