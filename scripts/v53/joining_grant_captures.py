"""Collect original writer-held grant copies; never infer force or history validity.

The captured ROOT/NODE/journal/source and selected generation are checked from
bytes. Event-to-copy completeness is separate from later causal history replay.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from . import joining_snapshot as snapshot
from . import joining_retention_evidence as retention

f, need, sha = snapshot.f, snapshot.need, snapshot.s.digest
disk = retention.physical
MIB = snapshot.MIB
DIRECTORY, EVENT = 'grant-captures', 'GRANT_CAPTURED'
MAXIMUM_CAPTURES, MAXIMUM_FILES, MAXIMUM_BYTES = 64, 512, 256*MIB
SCHEMA = 'gse-v53-grant-capture-v1'


def json_file(path):
    raw = snapshot.s.regular(path, MIB)
    def unique(rows):
        need(len(rows) == len(dict(rows)), 'grant capture duplicate JSON key')
        return dict(rows)
    value = json.loads(raw, object_pairs_hook=unique)
    need(f.canonical(value) == raw, 'grant capture canonical metadata')
    f.parse_budget(raw)
    return raw, value


def inventory(root):
    need(root.is_dir() and not root.is_symlink(), 'grant capture directory')
    files, identities, total, pending = {}, {}, 0, [root]
    while pending:
        for path in pending.pop().iterdir():
            name = path.relative_to(root).as_posix(); snapshot.relative(name)
            need(not path.is_symlink() and len(files) < MAXIMUM_FILES, 'grant capture linked/member capacity')
            if path.is_dir():
                files[name] = None; identities[name] = dict(directory=True); pending.append(path)
            else:
                raw = snapshot.s.regular(path, 64*MIB); total += len(raw)
                need(total <= MAXIMUM_BYTES, 'grant capture byte capacity')
                files[name] = raw; identities[name] = dict(size=len(raw), sha256=sha(raw))
    return files, identities, total


def read(path, event, *, learner_retention=True):
    need(path.is_dir() and not path.is_symlink() and {p.name for p in path.iterdir()} == {'capture.json', 'replica'},
         'grant capture layout')
    raw, value = json_file(path/'capture.json')
    need(type(value) is dict and set(value) == {'schema','node','scope','ballot','basisId','basisSha256','packetSha256','files'}
         and value['schema'] == SCHEMA, 'grant capture metadata shape')
    need(set(event) == {'node','scope','event','capture','sha256','basis'} and event['event'] == EVENT
         and event['sha256'] == sha(raw) and event['basis'] == value['basisSha256']
         and all(event[k] == value[k] for k in ('node','scope')), 'grant capture event binding')
    files, observed, total = inventory(path/'replica')
    expected = [dict(name=name, identity=observed[name]) for name in sorted(observed)]
    need(f.canonical(value['files']) == f.canonical(expected), 'grant capture copied inventory')
    required = {'root.gsr','node.gsr','allocator.gsr','grants.gsr','replica.lock','selector.gsr'}
    need(required <= files.keys() and all(type(files[k]) is bytes for k in required)
         and files['replica.lock'] == b'', 'grant capture original authorities')
    f.decode(files['root.gsr'], 'records', 'ROOT'); root = files['root.gsr'][16:48].hex()
    identity = f.decode(files['node.gsr'], 'records', 'NODE', root)['identity']
    counter = f.decode(files['allocator.gsr'], 'records', 'ALLOCATOR', root)
    selector = f.decode(files['selector.gsr'], 'records', 'SELECTOR', root)
    need(identity['node'] == value['node'] == counter['node'] == selector['node'], 'grant capture original owner')
    rows = disk.journal(files['grants.gsr'], root, identity['node'])
    need(len(rows) >= 2 and [v[0] for v in rows[-2:]] == ['PROMISE','BASIS'], 'grant capture complete suffix')
    promise, (_, basis_raw, basis) = rows[-2][1], rows[-1]
    need(f.canonical(basis['ballot']) == f.canonical(value['ballot']) and basis['basisId'] == value['basisId']
         and sha(basis_raw) == value['basisSha256'], 'grant capture original basis')
    prefix = 'sources/'+basis['basisId']+'/'
    need(type(files.get(prefix+'source.gscp')) is bytes, 'grant capture original packet missing')
    packet_raw = files[prefix+'source.gscp']; packet = disk.p.decode(packet_raw); disk.p.bind(packet, basis_raw)
    need(sha(packet_raw) == value['packetSha256'], 'grant capture packet identity')
    need({k for k in files if k.startswith(prefix)} == {prefix+'source.gscp'} |
         {prefix+h+'.image' for h in packet['images']}, 'grant capture source inventory')
    for h, size in packet['images'].items():
        image = files[prefix+h+'.image']
        need(type(image) is bytes and len(image) == size and sha(image) == h, 'grant capture original image')
    _, _, current = disk.current(files)
    need(current['capsule']['root'] == root and current['capsule']['cut'] == basis['cut'], 'grant capture current cut')
    catalog = f.decode(packet['objects'][packet['capsule']['catalog']], 'records', 'CATALOG', root)
    need(identity in catalog['identities'], 'grant capture catalog owner')
    ledgers = [(retention.LEDGERS[0], 0x47535250, 65536)]
    if learner_retention:
        ledgers.append((retention.LEDGERS[2], 0x47534c46, 32768))
    else:
        # Stable competing owners have no learner ledger. This is an exact
        # absence profile, not an optional-ledger fallback for joining histories.
        need(retention.LEDGERS[2] not in files and not any(
            raw[:4] == bytes.fromhex('47534c46') for raw in packet['objects'].values()),
            'grant capture unexpected learner retention')
    for name, magic, maximum in ledgers:
        wrapper, state = retention.source(packet, basis, magic, maximum)
        captured_promise, ledger = retention.parts(wrapper[48:], [8192, maximum])
        need(captured_promise == promise and ledger == files.get(name) and state['root'] == root
             and state['owner'] == identity, 'grant capture frozen ledger binding')
    return dict(capture=event['capture'], node=value['node'], scope=value['scope'], ballot=basis['ballot'],
                basisId=basis['basisId'], basisSha256=sha(basis_raw), root=root, identity=identity,
                bytes=total, files=len(files), cut=basis['cut']['index'])


def collect(raw, events, *, learner_retention=True):
    root = Path(raw)/DIRECTORY
    need(root.is_dir() and not root.is_symlink(), 'grant capture collection missing')
    pending, rows, names, identities, sources, total = {}, [], [], {}, {}, 0
    for position, event in enumerate(events):
        need(type(event) is dict, 'grant capture event row')
        if event.get('event') not in ('GRANT_BEFORE_RETURN', EVENT): continue
        key = event.get('node'), event.get('scope', 'network-owner')
        need(all(type(v) is str and v for v in key), 'grant capture event owner')
        if event['event'] == 'GRANT_BEFORE_RETURN':
            need(key not in pending, 'grant capture missing prior copy')
            pending[key] = position; continue
        need(key in pending and len(rows) < MAXIMUM_CAPTURES, 'grant capture orphan/capacity')
        name = f'capture-{len(rows)+1:04d}'
        need(event.get('capture') == DIRECTORY+'/'+name, 'grant capture ordered unique path')
        row = read(root/name, event, learner_retention=learner_retention); total += row['bytes']
        need(total <= MAXIMUM_BYTES, 'grant capture aggregate capacity')
        owner = row['node']; identity = row['identity']
        need(not rows or row['root'] == rows[0]['root'], 'grant capture mixed roots')
        need(owner not in identities or identities[owner] == identity, 'grant capture owner changed')
        identities[owner] = identity
        binding = row['root'], owner, row['basisSha256']
        need(row['basisId'] not in sources or sources[row['basisId']] == binding, 'grant capture reused source identity')
        sources[row['basisId']] = binding
        row.update(returnEvent=pending.pop(key), capturedEvent=position)
        names.append(name); rows.append(row)
    need(rows and not pending, 'grant capture incomplete event copies')
    need({p.name for p in root.iterdir()} == set(names), 'grant capture unobserved copies')
    return rows


def require_intermediate(raw, rows, *, voters=('node-1', 'node-2'), old_owner_lifetimes=None):
    """Require pre-activation grants for every declared old-majority owner.

    Counters come from the original pre-continuation snapshot, not a ready flag
    or a hard-coded ballot. This checks presence only; no historical derivation.
    """
    lifetimes = {} if old_owner_lifetimes is None else old_owner_lifetimes
    need(type(lifetimes) is dict and set(lifetimes) <= set(voters) and
         all(type(v) is tuple and len(v) == 2 and type(v[0]) is int and v[0] >= 0 and
             type(v[1]) is str and v[1] for v in lifetimes.values()), 'grant capture declared owner lifetimes')
    def scope(row):
        lifetime = lifetimes.get(row['node'])
        return lifetime[1] if lifetime and row['capturedEvent'] >= lifetime[0] else 'network-owner'
    need(all(type(row.get('capturedEvent')) is int and row['capturedEvent'] >= 0 and row['scope'] == scope(row)
             for row in rows if row['node'] in lifetimes), 'grant capture original cold lifetime')
    before = Path(raw)/'before-joint-continuation'
    node1, _, _ = inventory(before/'node-1')
    identity = f.decode(node1['node.gsr'], 'records', 'NODE')['identity']
    allocator = f.decode(node1['allocator.gsr'], 'records', 'ALLOCATOR')
    records = disk.journal(node1['grants.gsr'], allocator['root'], identity['node'])
    counter = max([allocator['counter'], *[v['ballot']['counter'] for _, _, v in records]])+1
    ballot = dict(counter=counter, proposer=identity['node'], incarnation=identity['storage'])
    for owner in voters:
        files, _, _ = inventory(before/owner)
        actual = f.decode(files['node.gsr'], 'records', 'NODE', allocator['root'])['identity']
        for wanted in (ballot, dict(ballot, counter=counter+1)):
            matches = [v for v in rows if v['node'] == owner and v['scope'] == scope(v) and v['ballot'] == wanted
                       and v['root'] == allocator['root'] and v['identity'] == actual]
            need(len(matches) == 1, 'grant capture intermediate preparation missing/duplicate')
    return counter


def validate(raw, events, *, whole_history=False, learner_retention=True):
    need(learner_retention or not whole_history, 'grant capture joining requires learner retention')
    rows = collect(raw, events, learner_retention=learner_retention)
    result = dict(status='PARTIAL', scope='original-grant-copy-collection', captures=len(rows),
                  bytes=sum(v['bytes'] for v in rows), nativeHistoryQualified=False,
                  intermediatePreparationPhysicalQualified=False, forceAndNetworkQualified=False, phase3Complete=False)
    if whole_history: result['intermediateBallot'] = require_intermediate(raw, rows)
    return result


NEGATIVES = {
    'missing-return': 'grant capture orphan/capacity',
    'missing-final-marker': 'grant capture incomplete event copies',
    'duplicate-marker': 'grant capture orphan/capacity',
    'path-traversal': 'grant capture ordered unique path',
    'unobserved-directory': 'grant capture unobserved copies',
    'event-digest': 'grant capture event binding',
    'stale-inventory': 'grant capture copied inventory',
    'missing-image': 'grant capture source inventory',
    'changed-image': 'grant capture original image',
    'torn-journal': 'torn grant journal body',
    'foreign-owner': 'grant capture original owner',
    'frozen-ledger': 'grant capture frozen ledger binding',
}


def mutate(raw, events, name):
    captures = [row for row in events if row.get('event') == EVENT]; first = captures[0]
    path = Path(raw)/first['capture']; replica = path/'replica'
    if name == 'missing-return':
        next(v for v in events if v.get('event') == 'GRANT_BEFORE_RETURN')['event'] = 'OMITTED'
    elif name == 'missing-final-marker': captures[-1]['event'] = 'OMITTED'
    elif name == 'duplicate-marker': events.insert(events.index(first)+1, dict(first))
    elif name == 'path-traversal': first['capture'] = '../outside'
    elif name == 'unobserved-directory': (Path(raw)/DIRECTORY/'unobserved').mkdir()
    elif name == 'event-digest': first['sha256'] = '0'*64
    else:
        _, metadata = json_file(path/'capture.json')
        prefix = replica/'sources'/metadata['basisId']
        if name in ('missing-image','changed-image'):
            packet = disk.p.decode((prefix/'source.gscp').read_bytes()); image = prefix/(next(iter(packet['images']))+'.image')
            if name == 'missing-image': image.unlink()
            else:
                data = image.read_bytes(); image.write_bytes(bytes([data[0]^1])+data[1:])
        elif name == 'stale-inventory': (replica/'extra').write_bytes(b'unobserved')
        elif name == 'torn-journal':
            journal = replica/'grants.gsr'; journal.write_bytes(journal.read_bytes()[:-1])
        elif name == 'foreign-owner':
            allocator = replica/'allocator.gsr'; value = f.decode(allocator.read_bytes(), 'records', 'ALLOCATOR')
            value['node'] = 'node-2' if metadata['node'] != 'node-2' else 'node-1'
            allocator.write_bytes(f.encode('records', 'ALLOCATOR', value))
        elif name == 'frozen-ledger':
            ledger = replica/retention.LEDGERS[0]; before = ledger.read_bytes(); state = retention.peer_source.r.decode(before)
            state.update(revision=state['revision']+1, previous=sha(before)); ledger.write_bytes(retention.peer_source.r.frame(state))
        else: raise ValueError('unknown grant capture mutation')
        if name != 'stale-inventory':
            _, identities, _ = inventory(replica)
            metadata['files'] = [dict(name=k, identity=identities[k]) for k in sorted(identities)]
            encoded = f.canonical(metadata); (path/'capture.json').write_bytes(encoded); first['sha256'] = sha(encoded)


def qualify(raw, events, *, learner_retention=True):
    import copy
    original = validate(raw, events, learner_retention=learner_retention)  # Invalid originals never count as successful rejections.
    outcomes = []
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-grant-negative-') as temp:
            target = Path(temp)/'raw'; target.mkdir(); shutil.copytree(Path(raw)/DIRECTORY, target/DIRECTORY)
            changed = copy.deepcopy(events); mutate(target, changed, name)
            try: validate(target, changed, learner_retention=learner_retention)
            except ValueError as error:
                need(str(error) == reason, 'unrelated grant capture negative: '+name+': '+str(error))
            else: raise ValueError('grant capture mutation accepted: '+name)
            outcomes.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=outcomes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('raw'); parser.add_argument('--whole-history', action='store_true')
    parser.add_argument('--qualify', action='store_true')
    args = parser.parse_args()
    # Aggregate event logs have a per-message budget in the original collector.
    from .joining_history_run import read_json, EVENT_BYTES
    events = read_json(Path(args.raw), 'events.json', EVENT_BYTES)
    result = validate(args.raw, events, whole_history=args.whole_history)
    if args.qualify: result['qualification'] = qualify(args.raw, events)
    print(json.dumps(result, sort_keys=True))
