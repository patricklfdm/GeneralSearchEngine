"""Original-first replay of selector-coupled local retention merges.

The native fixture starts from actual public bootstrap and original votes. This
reader derives both generations, every frozen source, the conservative merge and
all interrupted/recovered files. No Java PASS or claimed ready snapshot is an
authority. This is not quorum dispatch, automatic maintenance or power-loss proof.
"""
from __future__ import annotations
import argparse
import copy
import json
import shutil
import struct
import tempfile
import uuid
from pathlib import Path
from . import peer_retention_source_evidence as s

r, b, p, f = s.r, s.b, s.p, s.f
need, sha = r.need, r.sha
FILE, NEXT = 'peer-retention.gspr', 'peer-retention.next.gspr'
POINTS = ('INSTALL_GENERATION_FORCED', 'INSTALL_SELECTOR_RENAMED', 'INSTALL_PARENT_FORCED',
          'RETENTION_PREFIX_WRITTEN', 'RETENTION_FORCED', 'RETENTION_RENAMED',
          'RETENTION_PARENT_FORCED', 'SELECTED_RETENTION_COMPLETED')


def part(raw):
    return struct.pack('>I', len(raw))+raw


def envelope(packet):
    return part(packet['capsuleBytes'])+part(packet['indexBytes'])


def intent(owner, selected, before, rows):
    body = part(f.canonical(owner))+part(selected)+part(before)+struct.pack('>I', len(rows))
    for basis, packet, wrapper in rows:
        body += part(basis)+part(envelope(packet))+part(wrapper)
    prefix = struct.pack('>IHHII', 0x47535253, 1, 3, 0, len(body))
    need(len(body)+48 < 8*1024*1024, 'selected retention object bound')
    return prefix+bytes.fromhex(sha(prefix+body))+body


def merged(before, sources):
    original = r.decode(before); plan = copy.deepcopy(original['plan'])
    by_owner = {f.canonical(row['identity']): row for row in plan['peers']}
    for raw in sources:
        state = r.decode(raw)
        need(state['root'] == original['root'] and state['plan']['view'] == plan['view'], 'selected retention same native view')
        need({f.canonical(row['identity']) for row in state['plan']['peers']} == set(by_owner), 'selected retention permanent identities')
        for row in state['plan']['peers']:
            existing = by_owner[f.canonical(row['identity'])]
            endpoints = {a['cut']['index']: a for a in existing['possible']}
            for anchor in row['possible']:
                index = anchor['cut']['index']
                need(index not in endpoints or endpoints[index] == anchor, 'selected retention conflicting endpoint')
                endpoints[index] = anchor
            need(1 <= len(endpoints) <= 2, 'selected retention endpoint bound')
            existing['possible'] = [endpoints[k] for k in sorted(endpoints)]
    if plan == original['plan']:
        return before
    return r.frame(dict(original, revision=original['revision']+1, previous=sha(before), plan=plan))


def initialize(group):
    cap = b.c.current(group['node-1'])[2]['capsule']
    identities = [f.decode(group[n]['node.gsr'], 'records', 'NODE')['identity'] for n in sorted(group)]
    plan = dict(root=cap['root'], view=cap['cut']['view'],
                peers=[dict(identity=i, possible=[b.c.anchor(cap)]) for i in identities])
    return {n: dict(files, **{FILE: r.frame(dict(root=cap['root'], owner=identity, revision=0, previous=None, plan=plan))})
            for (n, files), identity in zip(sorted(group.items()), identities)}


def campaign(root, group, counter, observed, *, selected_prefix=None, proposer='node-1'):
    """Only fresh UUIDs are observed. Every other byte is independently derived."""
    need(proposer in group, 'selected retention original proposer absent')
    from . import learner_retention_evidence as learner
    learner_mode=any(learner.FILE in files for files in group.values())
    need(not learner_mode or all(learner.FILE in files for files in group.values()),'selected mixed learner retention owners')
    learner_sources={}
    names = sorted(group); local = f.decode(group[proposer]['node.gsr'], 'records', 'NODE')['identity']
    ballot = dict(counter=counter, proposer=proposer, incarnation=local['storage'])
    prepared, sources, grants = {}, {}, {}; identifiers = set()
    for node, files in group.items():
        _, members, packet = b.c.current(files); cap = packet['capsule']
        actual = b.c.inventory(root/observed/node)
        old = b.c.journal(files['grants.gsr'], cap['root'], node)
        history = b.c.journal(actual['grants.gsr'], cap['root'], node)
        need(history[:len(old)] == old and [v[0] for v in history[len(old):len(old)+2]] == ['PROMISE', 'BASIS'], 'selected retention original grant history')
        identifier = history[len(old)][2]['basisId']
        need(str(uuid.UUID(identifier)) == identifier and identifier not in identifiers
             and all(v[2].get('basisId') != identifier for v in old), 'selected retention fresh source identity')
        identifiers.add(identifier)
        value = dict(root=cap['root'], view=b.e.authority(cap['root'], cap['cut']['view']), ballot=ballot, basisId=identifier)
        promise = f.encode('records', 'PROMISE', value); wrapper = s.wrap(promise, files[FILE])
        objects = dict(packet['objects'], **{sha(wrapper): wrapper})
        if learner_mode:
            learner_wrapper=learner.wrap(promise,files[learner.FILE]);objects[sha(learner_wrapper)]=learner_wrapper
        raw = b.c.packet_bytes(cap, objects, packet['images']); frozen = p.decode(raw)
        basis = f.encode('records', 'BASIS', dict(value, voter=node, cut=cap['cut'],
                        capsule=sha(frozen['capsuleBytes']), inventory=sha(frozen['indexBytes']), accepted=None))
        p.bind(frozen, basis); source = 'sources/'+identifier
        changed = dict(files, **{'grants.gsr': files['grants.gsr']+promise+basis, source: None, source+'/source.gscp': raw})
        for h in packet['images']:
            changed[source+'/'+h+'.image'] = members[h+'.image']
        if node == proposer:
            changed['allocator.gsr'] = f.encode('records', 'ALLOCATOR', dict(root=cap['root'], node=node, counter=counter))
        prepared[node], sources[node], grants[node] = changed, (basis, frozen, wrapper), (promise, basis)
        if learner_mode:learner_sources[node]=(basis,frozen,learner_wrapper)
    cap = b.c.current(group[proposer])[2]['capsule']
    selected = f.encode('records', 'SELECTED', dict(root=cap['root'], view=b.e.authority(cap['root'], cap['cut']['view']),
        ballot=ballot, cut=cap['cut'], nextEntry=None, sources=[dict(voter=n,
            basisId=f.decode(grants[n][1], 'records', 'BASIS')['basisId'], basisDigest=sha(grants[n][1])) for n in names]))
    chosen = {n: dict(files, **{'grants.gsr': files['grants.gsr']+selected}) for n, files in prepared.items()}
    installed = {}
    for node, files in chosen.items():
        # All native cuts here are equal. The original proposer's frozen source
        # wins that tie, independently of which receiver installs the decision.
        prefix, old, _ = b.c.current(group[node]); packet = sources[proposer][1]
        owner = f.decode(files['node.gsr'], 'records', 'NODE')['identity']
        record = intent(owner, selected, files[FILE], [sources[n] for n in names])
        objects = dict(packet['objects']) if selected_prefix is None else selected_prefix(packet, files['root.gsr'])
        objects=dict(objects,**{sha(record):record})
        if learner_mode:
            retained=learner.intent(owner,selected,files[learner.FILE],[learner_sources[n] for n in names])
            objects[sha(retained)]=retained
        raw = b.c.packet_bytes(packet['capsule'], objects, packet['images'])
        members = dict(zip(('promise.gsr', 'basis.gsr'), grants[node]), **{'selected.gsr': selected,
            'selected-sources.gsr': b''.join(grants[n][1] for n in names), 'source.gscp': raw})
        members.update({h+'.image': old[h+'.image'] for h in packet['images']})
        selector, generation = b.c.generation(members, p.decode(raw)['capsule'], node, 'b' if prefix == 'generations/a/' else 'a', None)
        installed[node] = dict(files, **generation, **{'selector.gsr': selector,
                              FILE: merged(files[FILE], [group[n][FILE] for n in names])})
        if learner_mode:installed[node][learner.FILE]=learner.merged(files[learner.FILE],[group[n][learner.FILE] for n in names])
    return prepared, chosen, installed


def ordered(events, expected, label):
    cursor = -1
    for item in expected:
        need(item in events[cursor+1:], 'selected retention force order: '+label)
        cursor = events.index(item, cursor+1)


def calls(root):
    rows = json.loads((root/'calls.json').read_text()); names = ['node-1', 'node-2', 'node-3']
    expected = [(n, 'initialize') for n in names]+[('node-1', 'allocate-1')]
    expected += [(n, phase+'-1') for phase in ('prepare', 'select', 'install') for n in names]
    expected += [(n, 'round-1-settled-'+phase) for phase in ('copy', 'maintain') for n in names]
    expected += [('node-1', 'entry-1')]+[(n, phase+'-1') for phase in ('accept', 'proof', 'certificate', 'apply', 'publish') for n in names]
    expected += [(n, 'slot-1-settled-'+phase) for phase in ('copy', 'maintain') for n in names]+[(n, 'inspect-1') for n in names]
    expected += [('node-1', 'dispatch'), ('node-1', 'allocate')]+[(n, phase) for phase in ('prepare', 'select') for n in names]
    expected += [('node-2', op) for mode in ('halt', 'kill') for _ in POINTS
                 for op in (('lock-probe', 'reopen-after-merge') if mode == 'kill' else ('reopen-after-merge',))]
    need([(v['node'], v['operation']) for v in rows] == expected, 'selected retention original owner calls')
    for row in rows:
        phase = row['operation'].split('-')[0]; events = row['events']
        required = {'initialize': ['RETENTION_FORCED', 'RETENTION_RENAMED', 'RETENTION_PARENT_FORCED'],
            'dispatch': ['RETENTION_FORCED', 'RETENTION_RENAMED', 'RETENTION_PARENT_FORCED'],
            'allocate': ['ALLOCATOR_FORCED', 'ALLOCATOR_DIRECTORY_FORCED', 'ALLOCATOR_BEFORE_RETURN'],
            'prepare': ['PROMISE_FORCED', 'SOURCE_DIRECTORY_FORCED', 'BASIS_FORCED', 'GRANT_BEFORE_RETURN'],
            'select': ['SELECTED_FORCED', 'SELECTED_BEFORE_RETURN'],
            'install': ['INSTALL_GENERATION_FORCED', 'INSTALL_SELECTOR_FORCED', 'INSTALL_PARENT_FORCED', 'INSTALL_BEFORE_RETURN'],
            'accept': ['ACCEPT_ACTIVE_FORCED', 'ACCEPT_BEFORE_RETURN'],
            'proof': ['PROOF_CANDIDATE_FORCED', 'PROOF_PARENT_FORCED', 'PROOF_BEFORE_RETURN'],
            'certificate': ['CERTIFICATE_CANDIDATE_FORCED', 'CERTIFICATE_PARENT_FORCED', 'CERTIFICATE_BEFORE_RETURN'],
            'apply': ['APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN'],
            'publish': ['PUBLICATION_SELECTOR_FORCED', 'PUBLICATION_BEFORE_RETURN']}.get(phase, [])
        ordered(events, required, phase)


def crash(path, before, completed):
    result = json.loads((path/'result.json').read_text()); mode, point = result['mode'], result['cut']
    need(result == dict(status='PASS', mode=mode, cut=point, exit=23 if mode == 'halt' else 137)
         and mode in ('halt', 'kill') and point in POINTS and path.name == mode+'-'+point, 'selected retention crash identity')
    log = (path/'worker.log').read_text(); lines = log.splitlines()
    need(log.count('CUT '+point+'\n') == 1 and 'RESPONSE' not in log, 'selected retention interrupted response')
    events = [v.removeprefix('EVENT ') for v in lines if v.startswith('EVENT ')]
    need(events[-1] == point, 'selected retention actual crash cut')
    ordered(events, ['INSTALL_GENERATION_FORCED']+([] if point == POINTS[0] else ['INSTALL_SELECTOR_FORCED', 'INSTALL_SELECTOR_RENAMED']), point)
    if point in POINTS[3:]:
        ordered(events, ['INSTALL_PARENT_FORCED', 'RETENTION_BEFORE_WRITE', point], point)
    expected = dict(completed)
    if point == POINTS[0]: expected['selector.gsr'] = before['selector.gsr']
    if point not in POINTS[5:]: expected[FILE] = before[FILE]
    if point in POINTS[3:5]:
        raw = completed[FILE]; expected[NEXT] = raw[:len(raw)//2] if point == POINTS[3] else raw
    need(b.c.inventory(path/'interrupted') == expected, 'selected retention exact interrupted files')
    need(b.c.inventory(path/'recovered') == completed, 'selected retention exact recovered files')
    resume = (path/'resume.log').read_text().splitlines()
    # Reopening while collecting node 2's original source may complete the merge.
    recovery = [v.removeprefix('COLLECT node-2 ') if v.startswith('COLLECT node-2 ') else v.removeprefix('EVENT ')
                for v in resume if v.startswith(('COLLECT node-2 ', 'EVENT '))]
    if point in POINTS[:5]:
        ordered(recovery, ['RETENTION_FORCED', 'RETENTION_RENAMED', 'RETENTION_PARENT_FORCED', 'SELECTED_RETENTION_COMPLETED'], 'resume')
    else:
        ordered(recovery, ['RETENTION_RECOVERY_ACTIVE_FORCED', 'RETENTION_RECOVERY_PARENT_FORCED'], 'resume')
        need('RETENTION_BEFORE_WRITE' not in recovery, 'selected retention merge repeated')
    responses = [json.loads(v[9:]) for v in resume if v.startswith('RESPONSE ')]
    state = r.decode(completed[FILE])
    need(responses == [dict(revision=state['revision'], digest=sha(completed[FILE]), plan=state['plan'])], 'selected retention completed response')
    response_at = next(i for i, v in enumerate(resume) if v.startswith('RESPONSE '))
    required = 'SELECTED_RETENTION_COMPLETED' if point in POINTS[:5] else 'RETENTION_RECOVERY_PARENT_FORCED'
    need(any(v in ('EVENT '+required, 'COLLECT node-2 '+required) for v in resume[:response_at]),
         'selected retention response before durability')
    return dict(mode=mode, cut=point, status='PASS')


def validate(root):
    root = Path(root); group = initialize(b.original(root, 3, False))
    prepared, chosen, installed = campaign(root, group, 2, 'round-1-prepared')
    for stage, state in [('prepared', prepared), ('selected', chosen), ('installed', installed)]:
        b.match(root, 'round-1-'+stage, state)
    group = b.settled(installed); b.match(root, 'round-1-settled', group)
    group, _ = b.publication(root, group, 1, None, [])
    # The only pre-selection change is an actual ambiguous dispatch to node 3.
    state = r.decode(group['node-1'][FILE]); plan = copy.deepcopy(state['plan'])
    plan['peers'][2]['possible'].append(b.c.anchor(b.c.current(group['node-1'])[2]['capsule']))
    group['node-1'][FILE] = r.frame(dict(state, revision=1, previous=sha(group['node-1'][FILE]), plan=plan))
    _, ready, completed = campaign(root, group, 3, 'ready'); b.match(root, 'ready', ready)
    calls(root)
    paths = [path for path in root.iterdir() if path.is_dir() and path.name.startswith(('halt-', 'kill-'))]
    need({path.name for path in paths} == {mode+'-'+point for mode in ('halt', 'kill') for point in POINTS}, 'selected retention complete crash matrix')
    rows = [crash(path, ready['node-2'], completed['node-2']) for path in sorted(paths)]
    return dict(status='PASS', scope='native-selector-retention-merge', cases=rows,
                originalBootstrap=True, originalPublication=True, freshProcessRecovery=True,
                quorumDispatch=False, autonomousRuntime=False, phase3Complete=False)


def qualify(root):
    original = validate(root); rows = []
    mutations = [('bootstrap', 'admitted original public bootstrap'),
        ('source', 'admitted exact ready: node-1'), ('before', 'admitted exact ready: node-2'),
        ('selected', 'admitted exact ready: node-2'), ('force', 'selected retention force order: select'),
        ('generation', 'selected retention exact interrupted files'), ('ledger', 'selected retention exact interrupted files'),
        ('recovered', 'selected retention exact recovered files'), ('early-response', 'selected retention interrupted response'),
        ('resume-force', 'selected retention force order: resume'), ('response', 'selected retention completed response'),
        ('missing', 'selected retention complete crash matrix')]
    for name, reason in mutations:
        with tempfile.TemporaryDirectory(prefix='v53-selected-retention-negative-') as temp:
            copied = Path(temp)/'raw'; shutil.copytree(root, copied)
            case = copied/'kill-RETENTION_FORCED'
            if name == 'bootstrap': (copied/'initial/target-0/allocator.gsr').write_bytes(b'bad')
            elif name == 'source':
                file = next((copied/'ready/node-1/sources').glob('*/source.gscp')); file.write_bytes(b'bad')
            elif name == 'before': (copied/'ready/node-2'/FILE).unlink()
            elif name == 'selected':
                file = copied/'ready/node-2/grants.gsr'
                # Preserve the fresh grant prefix, change only a framed selected record.
                original_journal = (Path(root)/'ready/node-2/grants.gsr').read_bytes()
                cap = b.c.current(b.c.inventory(Path(root)/'ready/node-2'))[2]['capsule']
                records = b.c.journal(original_journal, cap['root'], 'node-2')
                selection = copy.deepcopy(records[-1][2]); selection['sources'] = selection['sources'][:-1]
                file.write_bytes(b''.join(v[1] for v in records[:-1])+f.encode('records', 'SELECTED', selection))
            elif name == 'force':
                file = copied/'calls.json'; value = json.loads(file.read_text())
                row = next(v for v in value if v['operation'] == 'select'); row['events'].remove('SELECTED_FORCED'); file.write_text(json.dumps(value))
            elif name == 'generation':
                files = b.c.inventory(case/'interrupted'); prefix = b.c.current(files)[0]
                (case/'interrupted'/prefix/'source.gscp').write_bytes(b'bad')
            elif name == 'ledger': (case/'interrupted'/FILE).write_bytes((case/'recovered'/FILE).read_bytes())
            elif name == 'recovered': (case/'recovered'/FILE).write_bytes((copied/'ready/node-2'/FILE).read_bytes())
            elif name == 'early-response':
                with (case/'worker.log').open('a') as stream: stream.write('RESPONSE {}\n')
            elif name == 'resume-force':
                file = case/'resume.log'; file.write_text('\n'.join(v for v in file.read_text().splitlines() if not v.endswith(' RETENTION_PARENT_FORCED'))+'\n')
            elif name == 'response':
                file = case/'resume.log'; file.write_text('\n'.join('RESPONSE {}' if v.startswith('RESPONSE ') else v for v in file.read_text().splitlines())+'\n')
            else: shutil.rmtree(case)
            try: validate(copied)
            except ValueError as error: need(str(error) == reason, 'negative reached wrong rejection: '+str(error))
            else: raise ValueError('negative unexpectedly accepted: '+name)
            rows.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root), sort_keys=True))
