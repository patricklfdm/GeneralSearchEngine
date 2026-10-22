"""Independent replay of Java-produced physical byte fixtures, never runtime safety evidence.

No production decoder is imported. Catalog state is derived from original commands,
not the producer's assertions. Force rows describe a single fixture-writing JVM;
they do not establish crash durability or remote voting authority.
"""
import copy
import hashlib
import json
from pathlib import Path
import re

from . import format_fixture as f
from .membership_model import need

PROFILES = ('3-ADD', '4-ADD', '4-REMOVE', '5-REMOVE', '3-REPLACE', '4-REPLACE', '5-REPLACE')
COMMANDS = ('BARRIER', 'RESERVE', 'PREPARE', 'READY', 'SEAL', 'INTENT', 'FINAL', 'BARRIER', 'RETIRE')
MIB = 1024 * 1024


def sha(data): return hashlib.sha256(data).hexdigest()
def digest(value): return sha(f.canonical(value))


def parse(data):
    f.parse_budget(data)
    def pairs(rows):
        need(len(rows) == len(dict(rows)), 'duplicate evidence key')
        return dict(rows)
    try: value = json.loads(data.decode('ascii'), object_pairs_hook=pairs)
    except (ValueError, UnicodeError) as error: raise ValueError('evidence JSON') from error
    need(f.canonical(value) == data, 'noncanonical evidence')
    return value


def exact(value, keys):
    need(type(value) is dict and set(value) == set(keys.split()), 'evidence fields')


def physical(root):
    root = Path(root)
    need(root.is_dir() and not root.is_symlink(), 'evidence directory')
    paths = list(root.rglob('*'))
    need(not any(p.is_symlink() for p in paths), 'linked evidence')
    need(all(p.is_file() or p.is_dir() for p in paths), 'nonregular evidence')
    manifest_path = root/'manifest.json'
    need(manifest_path.is_file() and manifest_path.stat().st_size <= 2*MIB, 'manifest capacity')
    manifest = parse(manifest_path.read_bytes())
    exact(manifest, 'schema runtimeEnabled authorityEvidence execution files forces')
    need(manifest['schema'] == 'gse-v53-context-fixture-v1' and manifest['runtimeEnabled'] is False
         and manifest['authorityEvidence'] is False and manifest['execution'] == 'single-jvm-byte-fixture', 'fixture scope')
    rows = manifest['files']
    need(type(rows) is list and 0 < len(rows) <= 8192, 'physical inventory count')
    for row in rows: exact(row, 'path sha256 size')
    files = {r['path']: r for r in rows}
    need(len(files) == len(rows), 'duplicate physical file')
    need({p.relative_to(root).as_posix() for p in paths if p.is_file()} == set(files) | {'manifest.json'}, 'physical inventory')
    total = 0
    # Validate all declared lengths and paths before reading any payload.
    for name, row in files.items():
        need(re.fullmatch(r'[A-Za-z0-9-]+(?:/[A-Za-z0-9.-]+)+', name) is not None
             and all(p not in ('.', '..') for p in name.split('/')), 'physical path')
        exact(row, 'path sha256 size')
        need(type(row['size']) is int and 0 <= row['size'] <= (64 if '/images/' in name else 8)*MIB, 'physical file capacity')
        need(re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None and (root/name).stat().st_size == row['size'], 'physical size/hash declaration')
        total += row['size']
    need(total <= 512*MIB, 'fixture archive capacity')
    data = {}
    for name, row in files.items():
        raw = (root/name).read_bytes()
        need(len(raw) == row['size'] and sha(raw) == row['sha256'], 'physical file hash: '+name)
        data[name] = raw
    forces = manifest['forces']; need(type(forces) is list and len(forces) <= len(files), 'force count')
    order = {}
    for index, row in enumerate(forces, 1):
        exact(row, 'path sequence sha256')
        need(type(row['sequence']) is int and row['sequence'] == index and row['path'] not in order
             and row['path'] in files and row['sha256'] == files[row['path']]['sha256'], 'fixture force trace')
        order[row['path']] = index
    return data, order


def authority(root, view): return digest(dict(root=root, **view))


def majority(view, names):
    need(names == sorted(set(names)) and set(names) <= set(view['old']) | set(view['new']), 'quorum identity/order')
    need(all(len(set(names) & set(view[side])) > len(view[side])//2 for side in ('old', 'new')), 'both governing majorities')


def identities(rows):
    need(3 <= len(rows) <= 512 and [r['node'] for r in rows] == sorted({r['node'] for r in rows}), 'identity registry')
    need(len({r['storage'] for r in rows}) == len(rows) and len({(r['host'], r['port']) for r in rows}) == len(rows), 'recycled disk/endpoint')
    return {r['node']: r for r in rows}


def reduce_catalog(before, catalog_hash, kind, payload, entry_hash, root):
    """Independent fixture reducer, with full detail retained until explicit RETIRE."""
    state = copy.deepcopy(before); view = state['cut']['view']; rows = state['results']
    row = next((r for r in rows if r['request']['number'] == state['active']), None)
    index = state['cut']['index']+1
    if kind == 'RESERVE':
        request = payload['request']; target = identities(request['target']); prior = identities(state['identities'])
        old = set(view['old']); new = set(target); added = new-old; removed = old-new
        need(state['active'] is None and len(rows) < 64 and view['generation'] < 256, 'reserve admission')
        need(request['root'] == root and request['expected'] == authority(root, view)
             and request['number'] == state['nextOperation'], 'reserve provenance')
        need((len(added), len(removed)) == {'ADD': (1, 0), 'REMOVE': (0, 1), 'REPLACE': (1, 1)}[request['kind']], 'one member change')
        for name in new & old: need(target[name] == prior[name], 'retained identity drift')
        for name in added:
            need(name not in prior and all(target[name]['storage'] != v['storage'] and
                 (target[name]['host'], target[name]['port']) != (v['host'], v['port']) for v in prior.values()), 'reserved identity reuse')
        prior.update(target); state['identities'] = [prior[k] for k in sorted(prior)]
        state['active'] = request['number']; state['nextOperation'] += 1
        rows.append(dict(request=request, phase='RESERVED', revision=0, prepared=None, receipt=None, binding=None, terminalIndex=None))
    elif kind == 'PREPARE':
        need(row is not None and row['phase'] in ('RESERVED', 'PREPARING', 'READY')
             and payload == dict(number=state['active'], revision=row['revision']+1) and payload['revision'] <= 64, 'prepare phase')
        row.update(phase='PREPARING', revision=payload['revision'], receipt=None,
                   prepared=dict(application=state['application'], catalog=catalog_hash, cut=copy.deepcopy(state['cut']), revision=payload['revision']))
    elif kind == 'READY':
        need(row is not None and row['phase'] == 'PREPARING' and payload['number'] == state['active'], 'ready phase')
        added = [r for r in row['request']['target'] if r['node'] not in view['old']]
        receipt = payload['receipt']
        need(receipt == (dict(root=root, number=state['active'], request=digest(row['request']), prepared=row['prepared'],
                             identity=added[0], image=row['prepared']['application']) if added else None), 'ready exact prepared identity')
        row.update(phase='READY', receipt=receipt)
    elif kind == 'SEAL':
        need(row is not None and row['phase'] == 'READY' and payload == dict(number=state['active'])
             and row['prepared']['application'] == state['application'] and row['prepared']['cut']['index'] >= state['lastDataIndex'], 'seal prepared cut')
        row.update(phase='SEALED', binding=digest({k: row[k] for k in ('request', 'prepared', 'receipt')}))
    elif kind == 'INTENT':
        need(row is not None and row['phase'] == 'SEALED' and payload == dict(sealed={k: row[k] for k in ('request', 'prepared', 'receipt')}), 'intent descriptor')
        row['phase'] = 'JOINT'; view.update(new=[r['node'] for r in row['request']['target']], operation=row['binding'])
    elif kind == 'FINAL':
        need(row is not None and row['phase'] == 'JOINT' and payload == dict(binding=view['operation']), 'final binding')
        row.update(phase='COMPLETED', terminalIndex=index); state['active'] = None
        view.update(old=view['new'], generation=view['generation']+1, operation=None)
    elif kind == 'RETIRE':
        through = payload['through']
        need(state['retiredThrough'] < through < state['nextOperation'] and all(r['phase'] in ('COMPLETED', 'CANCELLED')
             for r in rows if r['request']['number'] <= through), 'retirement terminal prefix')
        state['retiredThrough'] = through; state['results'] = [r for r in rows if r['request']['number'] > through]
    else: need(kind == 'BARRIER' and payload is None and view['operation'] is None, 'fixture barrier')
    state['cut'] = dict(entry=entry_hash, index=index, view=view)
    return state


def profile(name, files, forces):
    history = parse(files[name+'/history.json']); exact(history, 'root profile steps owned')
    need(history['profile'] == name and len(history['steps']) == len(COMMANDS), 'profile inventory')
    objects = {p.split('/')[-1][:-4]: b for p, b in files.items() if p.startswith(name+'/objects/')}
    images = {p.split('/')[-1][:-4]: b for p, b in files.items() if p.startswith(name+'/images/')}
    need(sum(map(len, objects.values())) <= 32*MIB and len(objects) <= 65536, 'metadata inventory capacity')
    need(0 < len(images) <= 7 and all(0 < len(b) <= 64*MIB and sha(b) == h for h, b in images.items()), 'separate application inventory')
    used = set(); used_files = {name+'/history.json'} | {name+'/images/'+h+'.bin' for h in images}
    def raw(h):
        need(h in objects and sha(objects[h]) == h, 'content-addressed record')
        used.add(h); return objects[h]
    def record(h, kind, root=None): return f.decode(raw(h), 'records', kind, root)
    root = record(history['root'], 'ROOT'); root_hash = raw(history['root'])[16:48].hex()
    need(root['limits'] == digest(f.catalog()['resources']), 'resource contract')
    genesis = record(root['genesis'], 'GENESIS')
    need(all(root[k] == genesis[k] for k in ('groupId', 'historyId', 'baseSequence', 'schema', 'indexes'))
         and genesis['source'] == 'EMPTY' and genesis['sourceDigest'] is None, 'fixture genesis')
    size, change = name.split('-'); initial = identities(root['initial'])
    need(len(initial) == int(size) and genesis['application'] in images, 'initial image/size')
    view = dict(generation=0, old=list(initial), new=list(initial), operation=None)
    state = dict(root=root_hash, active=None, application=genesis['application'], applicationSequence=root['baseSequence'],
                 cut=dict(index=0, entry=root['genesis'], view=view), identities=root['initial'], lastDataIndex=0,
                 nextOperation=1, results=[], retiredThrough=0)
    owned = {}; required_owned = set()
    for row in history['owned']:
        exact(row, 'parent record storage voter')
        parent_path, record_path = row['parent'], row['record']
        need(parent_path in files and record_path in files, 'missing owned bytes')
        h = sha(files[record_path]); stem = f"{name}/owned/{row['voter']}/{row['storage']}/{h}"
        need(record_path == stem+'.bin' and parent_path == stem+'.parent', 'owned path identity')
        key = (row['voter'], row['storage'], h)
        need(key not in owned and parent_path in forces and record_path in forces and forces[parent_path] < forces[record_path], 'owned parent force order')
        owned[key] = (parse(files[parent_path]), forces[record_path]); used_files.update((parent_path, record_path))
    previous_after = None
    for index, (step, expected_kind) in enumerate(zip(history['steps'], COMMANDS), 1):
        exact(step, 'catalogBefore entry accept proof certificate catalogAfter')
        need(previous_after is None or previous_after == step['catalogBefore'], 'catalog chain')
        before = record(step['catalogBefore'], 'CATALOG', root_hash)
        need(before == state, 'derived parent catalog')
        entry = record(step['entry'], 'ENTRY', root_hash)
        cert = record(step['certificate'], 'CERTIFICATE', root_hash)
        registry = identities(state['identities']); view = state['cut']['view']
        def ballot(value):
            need(value['counter'] < 2**63-1 and value['proposer'] in registry
                 and value['incarnation'] == registry[value['proposer']]['storage'], 'ballot storage identity')
            return value['counter'], value['proposer'], value['incarnation']
        need(cert['index'] == index == entry['index'] and cert['entry'] == step['entry']
             and cert['authority'] == entry['authority'] == authority(root_hash, view)
             and entry['previous'] == state['cut']['entry'] and entry['kind'] == expected_kind, 'entry governing parent')
        eligible = set(view['old']) | set(view['new'])
        need(cert['ballot']['proposer'] in eligible and entry['origin']['proposer'] in eligible
             and ballot(entry['origin']) <= ballot(cert['ballot']), 'entry original ballot')
        accept = {k: cert[k] for k in ('root', 'authority', 'ballot', 'index', 'entry')}
        need(record(step['accept'], 'ACCEPT', root_hash) == accept, 'exact acceptance')
        need(record(step['proof'], 'PROOF', root_hash) == dict(accept, accepts=cert['accepts']), 'exact proof witnesses')
        for phase, key in (('ACCEPT', 'accepts'), ('PROOF', 'proofs')):
            phased_hash = step['accept' if phase == 'ACCEPT' else 'proof']; voters = []
            for witness in cert[key]:
                voter, storage = witness['voter'], witness['incarnation']; voters.append(voter)
                need(voter in registry and storage == registry[voter]['storage'], 'witness durable identity')
                need(witness['receipt'] == digest(dict(root=root_hash, voter=voter, incarnation=storage, phase=phase, record=phased_hash)), 'phased receipt')
                owned_key = (voter, storage, phased_hash); required_owned.add(owned_key)
                need(owned_key in owned and owned[owned_key][0] == state['cut'], 'owned applied parent')
                if phase == 'PROOF':
                    prior = (voter, storage, step['accept'])
                    need(prior in owned and owned[prior][1] < owned[owned_key][1], 'accept before proof force')
            majority(view, voters)
        payload_bytes = raw(entry['payload'])
        if expected_kind == 'BARRIER': need(payload_bytes == b'', 'empty barrier'); payload = None
        else:
            payload = parse(payload_bytes)
            f.check_type(payload, {'object': f.catalog()['commands'][expected_kind]}, f.catalog()['types'])
        if expected_kind == 'RESERVE': need(payload['request']['kind'] == change, 'profile relabel')
        if expected_kind == 'INTENT': need(raw(digest(payload['sealed'])) == f.canonical(payload['sealed']), 'retained sealed descriptor')
        state = reduce_catalog(state, step['catalogBefore'], expected_kind, payload, step['entry'], root_hash)
        need(record(step['catalogAfter'], 'CATALOG', root_hash) == state, 'derived resulting catalog')
        previous_after = step['catalogAfter']
    need(set(owned) == required_owned, 'owned observation inventory')
    need(used == set(objects), 'unreferenced metadata')
    used_files |= {name+'/objects/'+h+'.bin' for h in objects}
    need(used_files == {p for p in files if p.startswith(name+'/')}, 'profile file roles')
    return dict(profile=name, certificates=len(COMMANDS), ownedRecords=len(owned), retiredThrough=state['retiredThrough'])


def validate(root):
    files, forces = physical(root)
    need({p.split('/')[0] for p in files} == set(PROFILES), 'complete seven profiles')
    cases = [profile(name, files, forces) for name in PROFILES]
    need(set(forces) == {p for p in files if '/owned/' in p}, 'fixture force inventory')
    return dict(status='PASS', execution='single-jvm-byte-fixture', runtimeEnabled=False, authorityEvidence=False,
                profiles=cases, certificates=sum(c['certificates'] for c in cases), fixtureForces=len(forces))
