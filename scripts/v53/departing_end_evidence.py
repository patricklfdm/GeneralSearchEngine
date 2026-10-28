"""Original nonvoting applied files and actual process cuts; authority is conditional.

This storage qualification never counts the departing member as a checkpoint voter.
Native application, future retention, publication and readiness require later evidence.
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from .applied_end_evidence import read, state, digest
from .format_fixture import canonical, decode, encode
from .membership_model import need

FILES = ('plan.json', 'selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'application.image')
PROFILES = ('4-REMOVE', '5-REMOVE', '3-REPLACE', '4-REPLACE', '5-REPLACE')
CUTS = ('APPLY_VALIDATED', 'APPLY_DIRECTORY_CREATED') + tuple(
    p+'_'+s for p in ('APPLY_PLAN', 'APPLY_METADATA', 'APPLY_IMAGE')
    for s in ('CREATED', 'PREFIX_WRITTEN', 'WRITTEN', 'FORCED')) + (
    'APPLY_END_FORCED', 'APPLY_NONVOTING_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN')

NEGATIVE_REASONS = {'missing-image': 'departing complete end', 'changed-image': 'departing complete end', 'fake-ack': 'departing exact nonvoting inventory', 'changed-crash': 'departing exact interrupted bytes: fault', 'early-success': 'departing exact force/return order: fault', 'missing-force': 'departing exact force/return order: resume', 'extra-file': 'applied evidence member inventory', 'wrong-profile': 'departing exact profile identity', 'changed-parent': 'departing exact applied state', 'wrong-entry': 'kind/flags/length', 'insufficient-joint-proof': 'departing original joint proofs', 'foreign-incarnation': 'departing original joint proofs'}


def simulate(expected, original, exists, stop=None):
    current = dict(original); events = []
    def event(name):
        events.append(dict(event=name)); return name == stop
    if event('APPLY_VALIDATED'): return current, exists, events
    if not exists:
        exists = True
        if event('APPLY_DIRECTORY_CREATED'): return current, exists, events
    for name in FILES:
        label = 'APPLY_PLAN' if name == 'plan.json' else 'APPLY_IMAGE' if name == 'application.image' else 'APPLY_METADATA'
        if name not in current:
            current[name] = b''
            if event(label+'_CREATED'): return current, exists, events
        offset = len(current[name]); middle = offset+(len(expected[name])-offset)//2
        need(expected[name].startswith(current[name]), 'departing original prefix')
        current[name] = expected[name][:middle]
        if event(label+'_PREFIX_WRITTEN'): return current, exists, events
        current[name] = expected[name]
        if event(label+'_WRITTEN'): return current, exists, events
        if event(label+'_FORCED'): return current, exists, events
    for name in ('APPLY_END_FORCED', 'APPLY_NONVOTING_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN'):
        if event(name): break
    return current, exists, events


def materialization(expected, entry_bytes, parent_bytes, profile):
    need(set(expected) == set(FILES), 'departing exact nonvoting inventory')
    manifest = json.loads(expected['plan.json'])
    need(canonical(manifest) == expected['plan.json'] and set(manifest) == {'schema', 'root', 'node', 'files'}
         and manifest['schema'] == 'gse-v53-applied-end/1.3', 'departing original plan')
    need(manifest['files'] == [dict(path=n, sha256=digest(expected[n]), bytes=len(expected[n]))
                             for n in sorted(set(FILES)-{'plan.json'})], 'departing original member hashes')
    frames = {name: decode(expected[name+'.gsr'], 'records', kind, manifest['root']) for name, kind in
              (('selector', 'SELECTOR'), ('certificate', 'CERTIFICATE'), ('catalog', 'CATALOG'), ('statement', 'CHECKPOINT'))}
    entry = decode(entry_bytes, 'records', 'ENTRY', manifest['root'])
    parent = json.loads(parent_bytes)
    need(set(parent) == {'cut', 'catalog', 'application'} and canonical(parent) == parent_bytes, 'departing original parent')
    catalog, statement, cert = (frames[n] for n in ('catalog', 'statement', 'certificate'))
    old, new = parent['cut']['view'], catalog['cut']['view']
    node = manifest['node']; size, operation = profile.split('-'); size = int(size)
    old_nodes = ['node-'+str(i) for i in range(1, size+1)]
    new_nodes = old_nodes[:-1] + (['node-6'] if operation == 'REPLACE' else [])
    need(node == 'node-'+str(size) == frames['selector']['node'] and old['old'] == old_nodes and old['new'] == new_nodes,
         'departing exact profile identity')
    need(old['operation'] is not None and node in old['old'] and node not in old['new'] and
         new == dict(generation=old['generation']+1, old=old['new'], new=old['new'], operation=None), 'departing exact successor')
    need(any(v['node'] == node for v in catalog['identities']), 'departing retained identity')
    need(entry['kind'] == 'FINAL' and entry['index'] == cert['index'] == catalog['cut']['index'] == parent['cut']['index']+1
         and entry['previous'] == parent['cut']['entry'] and digest(entry_bytes) == cert['entry'] == catalog['cut']['entry'],
         'departing exact original FINAL')
    need(cert['authority'] == entry['authority'] == digest(canonical(dict(old, root=manifest['root']))), 'departing governing certificate')
    identities = {v['node']: v['storage'] for v in catalog['identities']}
    eligible = set(old['old']+old['new'])
    for phase in ('accepts', 'proofs'):
        witnesses = cert[phase]; voters = [w['voter'] for w in witnesses]
        need(voters == sorted(set(voters)) and set(voters) <= eligible and
             all(w['incarnation'] == identities.get(w['voter']) for w in witnesses) and
             all(len(set(voters) & set(old[side])) > len(old[side])//2 for side in ('old', 'new')),
             'departing original joint '+phase)
    need(cert['ballot']['proposer'] in eligible and
         cert['ballot']['incarnation'] == identities.get(cert['ballot']['proposer']), 'departing original proposer')
    need(statement['scope'] == 'MEMBERSHIP' and statement['start'] == parent['cut'] and statement['end'] == catalog['cut']
         and statement['catalogBefore'] == parent['catalog'] and statement['applicationBefore'] == parent['application']
         and statement['catalogAfter'] == digest(expected['catalog.gsr'])
         and statement['applicationAfter'] == catalog['application'] == digest(expected['application.image']), 'departing exact applied state')
    return manifest, statement


def validate_case(root, row):
    root = Path(root); profile, mode, cut = (row[k] for k in ('profile', 'mode', 'cut'))
    need(profile in PROFILES and mode in ('halt', 'kill') and cut in CUTS, 'departing crash identity')
    names = {'owner.lock', 'entry.gsr', 'parent.json', 'end', 'crash', 'recovery-crash', 'final'} | {
        p+s for p in ('fault', 'recovery-fault', 'resume') for s in ('.stdout', '.stderr')}
    need(not root.is_symlink() and {p.name for p in root.iterdir()} == names and read(root/'owner.lock') == b'', 'departing case inventory')
    expected = state(root/'final'); need(state(root/'end') == expected, 'departing complete end')
    manifest, statement = materialization(expected, read(root/'entry.gsr'), read(root/'parent.json'), profile)
    need(row == dict(profile=profile, mode=mode, cut=cut, status='PASS', statement=digest(expected['statement.gsr']), node=manifest['node']), 'departing result identity')
    current = {}; exists = False
    for label, point, snapshot, kill in (('fault', cut, 'crash', mode == 'kill'), ('recovery-fault', 'APPLY_IMAGE_PREFIX_WRITTEN', 'recovery-crash', False), ('resume', None, 'final', False)):
        current, exists, events = simulate(expected, current, exists, point)
        need(state(root/snapshot) == current, 'departing exact interrupted bytes: '+label)
        if kill: events.append(dict(event='AWAITING_KILL', cut=point))
        if point is None: events.append(dict(status='PASS', profile=profile, completion='NONVOTING', statement=row['statement'], node=manifest['node']))
        need(read(root/(label+'.stdout')) == b''.join(canonical(v)+b'\n' for v in events)
             and read(root/(label+'.stderr')) == b'', 'departing exact force/return order: '+label)
    return dict(case=root.name, status='PASS')


def validate(path):
    path = Path(path); need(not path.is_symlink(), 'departing root symlink'); receipt = json.loads(read(path/'receipt.json', 262144))
    need(set(receipt) == {'schema', 'cases', 'expectedCases', 'powerLoss', 'protocolAuthority'}
         and receipt['schema'] == 'gse-v53-departing-end-v1' and receipt['expectedCases'] == 170
         and receipt['powerLoss'] is False and receipt['protocolAuthority'] == 'conditional-fixture', 'departing qualification scope')
    need([(v['profile'], v['mode'], v['cut']) for v in receipt['cases']] == [(p, m, c) for p in PROFILES for m in ('halt', 'kill') for c in CUTS], 'departing complete crash matrix')
    need({p.name for p in path.iterdir()} == {'receipt.json'} | {v['profile']+'-'+v['mode']+'-'+v['cut'] for v in receipt['cases']}, 'departing qualification inventory')
    results = [validate_case(path/(v['profile']+'-'+v['mode']+'-'+v['cut']), v) for v in receipt['cases']]
    return dict(status='PASS', cases=len(results), freshJvms=len(results)*3, protocolAuthority='conditional-fixture', checkpointVotes=0, nativePublication=False)


def qualify(path):
    path = Path(path); result = validate(path)
    row = json.loads(read(path/'receipt.json', 262144))['cases'][0]; original = path/(row['profile']+'-'+row['mode']+'-'+row['cut'])
    negatives = []
    for name in ('missing-image', 'changed-image', 'fake-ack', 'changed-crash', 'early-success', 'missing-force', 'extra-file', 'wrong-profile', 'changed-parent', 'wrong-entry', 'insufficient-joint-proof', 'foreign-incarnation'):
        with tempfile.TemporaryDirectory(prefix='v53-departing-negative-') as temp:
            copy = Path(temp)/original.name; shutil.copytree(original, copy); test_row = dict(row)
            if name == 'missing-image': (copy/'final/application.image').unlink()
            elif name == 'changed-image': (copy/'final/application.image').write_bytes(b'wrong')
            elif name == 'fake-ack':
                for folder in ('end', 'final'): (copy/folder/'ack.gsr').write_bytes(b'not-a-vote')
            elif name == 'changed-crash': (copy/'crash/application.image').write_bytes((copy/'final/application.image').read_bytes())
            elif name == 'early-success': (copy/'fault.stdout').write_bytes((copy/'resume.stdout').read_bytes())
            elif name == 'missing-force':
                p = copy/'resume.stdout'; p.write_bytes(p.read_bytes().replace(canonical(dict(event='APPLY_END_FORCED'))+b'\n', b''))
            elif name == 'wrong-profile': test_row['profile'] = '5-REMOVE'
            elif name == 'changed-parent':
                p = copy/'parent.json'; v = json.loads(p.read_bytes()); v['catalog'] = 'f'*64; p.write_bytes(canonical(v))
            elif name == 'wrong-entry': (copy/'entry.gsr').write_bytes((copy/'final/certificate.gsr').read_bytes())
            elif name in ('insufficient-joint-proof', 'foreign-incarnation'):
                data = decode((copy/'final/certificate.gsr').read_bytes(), 'records', 'CERTIFICATE')
                if name == 'insufficient-joint-proof': data['proofs'] = data['proofs'][:2]
                else: data['proofs'][0]['incarnation'] = '00000000-0000-0000-0000-000000000099'
                for folder in ('end', 'final'):
                    base = copy/folder; changed = encode('records', 'CERTIFICATE', data); (base/'certificate.gsr').write_bytes(changed)
                    plan = json.loads((base/'plan.json').read_bytes())
                    for member in plan['files']:
                        if member['path'] == 'certificate.gsr': member.update(bytes=len(changed), sha256=digest(changed))
                    (base/'plan.json').write_bytes(canonical(plan))
            else: (copy/'final/extra').write_bytes(b'')
            try: validate_case(copy, test_row)
            except (ValueError, OSError) as error:
                need(str(error) == NEGATIVE_REASONS[name], 'departing unexpected negative rejection: '+name+': '+str(error))
                negatives.append(dict(case=name, status='REJECT', reason=str(error)))
            else: raise ValueError('departing mutation accepted: '+name)
    return dict(**result, negatives=negatives)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('path'); args = parser.parse_args()
    print(json.dumps(qualify(args.path), sort_keys=True))
