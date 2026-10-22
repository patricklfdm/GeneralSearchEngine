"""Independently walk compacted Java capsules against validated original byte histories.

These are single-JVM fixtures. Applied/force copies are not live replica evidence.
The observer derives every source catalog before using any checkpoint endorsement.
"""
from pathlib import Path

from . import context_evidence as c
from . import source_packet as p
from . import format_fixture as f
from .membership_model import need


def file_bytes(path, maximum):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum, 'missing/linked/oversized capsule file')
    data = path.read_bytes(); need(len(data) <= maximum, 'capsule file grew'); return data


def source(root):
    files, forces = c.physical(root)
    need({name.split('/')[0] for name in files} == set(c.PROFILES), 'capsule source profiles')
    sources = {}
    for name in c.PROFILES:
        c.profile(name, files, forces)  # Includes independent control reduction and owned original phases.
        history = c.parse(files[name+'/history.json'])
        objects = {path.rsplit('/', 1)[1][:-4]: data for path, data in files.items() if path.startswith(name+'/objects/')}
        states = [f.decode(objects[history['steps'][0]['catalogBefore']], 'records', 'CATALOG')]
        states += [f.decode(objects[step['catalogAfter']], 'records', 'CATALOG') for step in history['steps']]
        entries = [f.decode(objects[step['entry']], 'records', 'ENTRY') for step in history['steps']]
        sources[name] = dict(history=history, objects=objects, states=states, entries=entries)
    need(set(forces) == {name for name in files if '/owned/' in name}, 'source force inventory')
    return sources


def spans(entries, through):
    start = 0; result = []
    while start < through:
        end = start+1; membership = entries[start]['kind'] in ('INTENT', 'FINAL')
        if not membership:
            while end < through and entries[end]['kind'] not in ('INTENT', 'FINAL'): end += 1
        result.append((start, end, 'MEMBERSHIP' if membership else 'RANGE')); start = end
    return result


def validate_one(root, name, through, original):
    root = Path(root)
    need(root.is_dir() and not root.is_symlink(), 'capsule directory')
    paths = list(root.rglob('*'))
    need(len(paths) <= 1024 and all(not path.is_symlink() and (path.is_file() or path.is_dir()) for path in paths), 'capsule file types/count')
    manifest_path = root/'manifest.json'; packet_path = root/'packet.bin'
    manifest = c.parse(file_bytes(manifest_path, 128*1024))
    c.exact(manifest, 'schema profile through packetSha256 runtimeEnabled authorityEvidence owned forces')
    need(manifest['schema'] == 'gse-v53-capsule-fixture-v1' and manifest['profile'] == name and type(manifest['through']) is int
         and manifest['through'] == through and manifest['runtimeEnabled'] is False and manifest['authorityEvidence'] is False, 'capsule fixture binding/scope')
    data = file_bytes(packet_path, 32*c.MIB); need(c.sha(data) == manifest['packetSha256'], 'capsule packet identity')
    packet_size = len(data); packet = p.decode(data); capsule = packet['capsule']; objects = packet['objects']; used = set()
    def raw(h):
        need(h in objects, 'missing capsule authority object'); used.add(h); return objects[h]
    def original_bytes(h):
        need(h in original['objects'] and raw(h) == original['objects'][h], 'changed original capsule object')
    history, states = original['history'], original['states']; initial = f.decode(raw(history['root']), 'records', 'ROOT')
    root_hash = raw(history['root'])[16:48].hex(); original_bytes(history['root']); original_bytes(initial['genesis'])
    def catalog(at): return history['steps'][at-1]['catalogAfter'] if at else history['steps'][0]['catalogBefore']
    original_bytes(catalog(through))
    need(capsule['root'] == root_hash and capsule['initial'] == initial['genesis'] and capsule['catalog'] == catalog(through)
         and capsule['cut'] == states[through]['cut'] and capsule['application'] == states[through]['application'], 'capsule root/terminal binding')
    expected_files = {'manifest.json', 'packet.bin'}
    for h, size in packet['images'].items():
        path = root/'images'/(h+'.bin'); expected_files.add('images/'+h+'.bin')
        data = file_bytes(path, 64*c.MIB); need(len(data) == size and c.sha(data) == h, 'capsule separate image')
    owned = {}; force_order = {}
    for index, row in enumerate(manifest['forces'], 1):
        c.exact(row, 'path sha256 sequence')
        # No path from the manifest is opened until compared to a constructed owner/hash path below.
        need(type(row['sequence']) is int and row['sequence'] == index and row['path'] not in force_order, 'capsule force order/inventory')
        force_order[row['path']] = (index, row['sha256'])
    for row in manifest['owned']:
        c.exact(row, 'voter storage ack applied')
        f.check_type(row['voter'], 'node', {}); f.check_type(row['storage'], 'uuid', {})
        name_part = row['ack'].rsplit('/', 1)[-1]; need(name_part.endswith('.bin'), 'checkpoint owned name')
        digest = name_part[:-4]; f.check_type(digest, 'hash', {})
        stem = 'owned/'+row['voter']+'/'+row['storage']+'/'+digest
        need(row['ack'] == stem+'.bin' and row['applied'] == stem+'.applied' and digest not in owned, 'checkpoint owned identity')
        raw_ack = file_bytes(root/row['ack'], 2048); applied = file_bytes(root/row['applied'], 16384)
        need(c.sha(raw_ack) == digest and row['ack'] in force_order and row['applied'] in force_order
             and force_order[row['ack']][1] == digest and force_order[row['applied']][1] == c.sha(applied)
             and force_order[row['applied']][0] < force_order[row['ack']][0], 'checkpoint force before verified applied copy')
        owned[digest] = (row, raw_ack, c.parse(applied)); expected_files.update((row['ack'], row['applied']))
    need(set(force_order) == {path for path in expected_files if path.startswith('owned/')}, 'checkpoint force coverage')
    intervals = spans(original['entries'], through)
    need(len(capsule['items']) == len(intervals), 'compacted item coverage')
    used_acks = set()
    for item, (start, end, kind) in zip(capsule['items'], intervals):
        need(item['kind'] == kind, 'hidden membership boundary')
        statement = f.decode(raw(item['statement']), 'records', 'CHECKPOINT', root_hash)
        need(statement == dict(root=root_hash, scope=kind, start=states[start]['cut'], end=states[end]['cut'],
             catalogBefore=catalog(start), catalogAfter=catalog(end), applicationBefore=states[start]['application'],
             applicationAfter=states[end]['application']), 'exact checkpoint prefix/catalog/application')
        members = {row['node']: row for row in states[end]['identities']}; voters = []; item_objects = {item['statement']}
        for ack_hash in item['endorsements']:
            ack = f.decode(raw(ack_hash), 'records', 'CHECKPOINT_ACK', root_hash); voter = ack['voter']; voters.append(voter)
            need(voter in members and ack['incarnation'] == members[voter]['storage'] and ack['cut'] == statement['end']
                 and ack['statement'] == item['statement'], 'checkpoint end/identity')
            need(ack_hash in owned and owned[ack_hash][1] == raw(ack_hash), 'missing owned checkpoint')
            row, _, applied = owned[ack_hash]
            need(row['voter'] == voter and row['storage'] == ack['incarnation'] and applied == dict(root=root_hash, voter=voter,
                 storage=ack['incarnation'], cut=states[end]['cut'], catalog=catalog(end), application=states[end]['application']), 'unapplied checkpoint end')
            used_acks.add(ack_hash); item_objects.add(ack_hash)
        c.majority(states[end]['cut']['view'], voters)
        if kind == 'RANGE': need(item['certificate'] is None and item['descriptor'] is None, 'range objects')
        else:
            step = history['steps'][start]; need(item['certificate'] == step['certificate'], 'original membership certificate')
            for field in ('certificate', 'entry', 'accept', 'proof'):
                original_bytes(step[field]); item_objects.add(step[field])
            payload = original['entries'][start]['payload']; original_bytes(payload); item_objects.add(payload)
            operation = next(r for r in states[start]['results'] if r['request']['number'] == states[start]['active'])
            descriptor = {k: operation[k] for k in ('request', 'prepared', 'receipt')}; h = c.digest(descriptor)
            need(item['descriptor'] == h and raw(h) == f.canonical(descriptor), 'original complete membership descriptor')
            item_objects.add(h)
        need(sum(len(objects[h]) for h in item_objects) <= (16 if kind == 'RANGE' else 48)*1024, 'actual capsule item bytes')
    need(used_acks == set(owned), 'checkpoint ownership coverage')
    need(used == set(objects), 'compacted fixture object inventory')
    need({path.relative_to(root).as_posix() for path in paths if path.is_file()} == expected_files, 'capsule physical inventory')
    return dict(profile=name, through=through, items=len(intervals), objects=len(objects), checkpointAcks=len(owned), packetBytes=packet_size)


def validate(root):
    root = Path(root); sources = source(root/'source')
    need({path.name for path in (root/'capsules').iterdir()} == set(c.PROFILES), 'capsule profile inventory')
    cases = []
    for name in c.PROFILES:
        directory = root/'capsules'/name
        need(not directory.is_symlink() and {p.name for p in directory.iterdir()} == {f'cut-{i}' for i in range(10)}, 'capsule cut inventory')
        cases.extend(validate_one(directory/f'cut-{i}', name, i, sources[name]) for i in range(10))
    return dict(status='PASS', execution='single-jvm-compacted-byte-fixtures', runtimeEnabled=False, authorityEvidence=False,
                cases=cases, capsules=len(cases), checkpointAcks=sum(row['checkpointAcks'] for row in cases))
