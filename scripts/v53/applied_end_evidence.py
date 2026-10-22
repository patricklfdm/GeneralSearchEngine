"""Independent exact file-prefix/event replay for the applied-end component's retained JVM tests.

The original protocol history is conditional. This validates actual end-file writes,
ACK ordering and repeated process recovery; it does not establish a real selected round.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from .format_fixture import canonical, decode
from .membership_model import need

FILES = ('plan.json', 'selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'application.image', 'ack.gsr')
CUTS = ('APPLY_VALIDATED', 'APPLY_DIRECTORY_CREATED') + tuple(
    p+'_'+s for p in ('APPLY_PLAN', 'APPLY_METADATA', 'APPLY_IMAGE', 'APPLY_ACK')
    for s in ('CREATED', 'PREFIX_WRITTEN', 'WRITTEN', 'FORCED')) + (
    'APPLY_END_FORCED', 'APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN')


def digest(data): return hashlib.sha256(data).hexdigest()


def read(path, maximum=65536):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1 and path.stat().st_size <= maximum, 'applied evidence file')
    data = path.read_bytes(); need(len(data) <= maximum, 'applied evidence grew'); return data


def state(path):
    path = Path(path); need(path.is_dir() and not path.is_symlink(), 'applied evidence directory')
    names = {p.name for p in path.iterdir()}; need(names <= set(FILES), 'applied evidence member inventory')
    return {n: read(path/n, 64*1024*1024 if n == 'application.image' else 2*1024*1024) for n in sorted(names)}


def simulate(expected, original, exists, stop=None):
    """Predict surviving exact prefixes at the first named cut; never infer force from a hash."""
    current = dict(original); events = []
    def event(name):
        events.append(dict(event=name)); return name == stop
    if event('APPLY_VALIDATED'): return current, exists, events
    if not exists:
        exists = True
        if event('APPLY_DIRECTORY_CREATED'): return current, exists, events
    for name in FILES:
        label = 'APPLY_PLAN' if name == 'plan.json' else 'APPLY_IMAGE' if name == 'application.image' else 'APPLY_ACK' if name == 'ack.gsr' else 'APPLY_METADATA'
        if name == 'ack.gsr' and event('APPLY_END_FORCED'): return current, exists, events
        if name not in current:
            current[name] = b''
            if event(label+'_CREATED'): return current, exists, events
        offset = len(current[name]); middle = offset+(len(expected[name])-offset)//2
        need(expected[name].startswith(current[name]), 'applied original prefix')
        current[name] = expected[name][:middle]
        if event(label+'_PREFIX_WRITTEN'): return current, exists, events
        current[name] = expected[name]
        if event(label+'_WRITTEN'): return current, exists, events
        if event(label+'_FORCED'): return current, exists, events
    if event('APPLY_ACK_DIRECTORY_FORCED'): return current, exists, events
    event('APPLY_BEFORE_RETURN'); return current, exists, events


def validate_case(root, row):
    root = Path(root); mode, cut = row['mode'], row['cut']
    need(mode in ('halt', 'kill') and cut in CUTS, 'applied crash identity')
    names = {'owner.lock', 'end', 'crash', 'recovery-crash', 'final'} | {p+s for p in ('fault', 'recovery-fault', 'resume') for s in ('.stdout', '.stderr')}
    need({p.name for p in root.iterdir()} == names and read(root/'owner.lock') == b'', 'applied case inventory')
    expected = state(root/'final'); need(set(expected) == set(FILES) and state(root/'end') == expected, 'applied complete end inventory')
    manifest = json.loads(expected['plan.json'])
    need(canonical(manifest) == expected['plan.json'] and set(manifest) == {'schema', 'root', 'node', 'files'} and manifest['schema'] == 'gse-v53-applied-end/1.3', 'applied original plan')
    need(manifest['files'] == [dict(path=n, sha256=digest(expected[n]), bytes=len(expected[n])) for n in sorted(set(FILES)-{'plan.json'})], 'applied original member hashes')
    frames = {name: decode(expected[name+'.gsr'], 'records', kind, manifest['root']) for name, kind in
              (('selector', 'SELECTOR'), ('certificate', 'CERTIFICATE'), ('catalog', 'CATALOG'), ('statement', 'CHECKPOINT'), ('ack', 'CHECKPOINT_ACK'))}
    catalog, statement, ack, cert = (frames[n] for n in ('catalog', 'statement', 'ack', 'certificate'))
    need(ack['statement'] == digest(expected['statement.gsr']) and ack['cut'] == catalog['cut'] == statement['end'], 'applied exact ACK end')
    need(statement['catalogAfter'] == digest(expected['catalog.gsr']) and statement['applicationAfter'] == catalog['application'] == digest(expected['application.image']), 'applied exact state hashes')
    need(cert['entry'] == catalog['cut']['entry'] and cert['index'] == catalog['cut']['index'] == statement['start']['index']+1, 'applied original certificate end')
    need(cert['authority'] == digest(canonical(dict(statement['start']['view'], root=manifest['root']))), 'applied original certificate view')
    identity = next((v for v in catalog['identities'] if v['node'] == manifest['node']), None)
    need(identity is not None and ack['voter'] == manifest['node'] == frames['selector']['node'] and ack['incarnation'] == identity['storage'], 'applied exact local identity')
    need(ack['voter'] in set(catalog['cut']['view']['old']+catalog['cut']['view']['new']), 'applied successor voter')
    need(row == dict(mode=mode, cut=cut, status='PASS', ack=digest(expected['ack.gsr'])), 'applied result identity')
    current = {}; exists = False
    for label, point, snapshot, kill in (('fault', cut, 'crash', mode == 'kill'), ('recovery-fault', 'APPLY_IMAGE_PREFIX_WRITTEN', 'recovery-crash', False), ('resume', None, 'final', False)):
        current, exists, events = simulate(expected, current, exists, point)
        need(state(root/snapshot) == current, 'applied exact interrupted bytes: '+label)
        if kill: events.append(dict(event='AWAITING_KILL', cut=point))
        if point is None: events.append(dict(status='PASS', ack=row['ack'], parent=digest(canonical(catalog['cut'])), voter=ack['voter']))
        need(read(root/(label+'.stdout')) == b''.join(canonical(v)+b'\n' for v in events) and read(root/(label+'.stderr')) == b'', 'applied exact force/return order: '+label)
    return dict(case=root.name, status='PASS')


def validate(path):
    path = Path(path); receipt = json.loads(read(path/'receipt.json'))
    need(set(receipt) == {'cases', 'expectedCases', 'powerLoss', 'protocolAuthority'} and receipt['expectedCases'] == 42 and receipt['powerLoss'] is False and receipt['protocolAuthority'] == 'conditional-fixture', 'applied qualification scope')
    need([(v['mode'], v['cut']) for v in receipt['cases']] == [(m, c) for m in ('halt', 'kill') for c in CUTS], 'applied complete crash matrix')
    need({p.name for p in path.iterdir()} == {'receipt.json'} | {v['mode']+'-'+v['cut'] for v in receipt['cases']}, 'applied qualification inventory')
    results = [validate_case(path/(v['mode']+'-'+v['cut']), v) for v in receipt['cases']]
    return dict(status='PASS', cases=len(results), freshJvms=len(results)*3, applicationPublication=False, protocolAuthority='conditional-fixture')


def qualify(path):
    path = Path(path); result = validate(path)  # Original must pass before any mutation.
    receipt = json.loads(read(path/'receipt.json')); row = receipt['cases'][0]; original = path/(row['mode']+'-'+row['cut'])
    negatives = []
    for name in ('missing-image', 'changed-image', 'missing-ack', 'changed-crash', 'early-success', 'missing-force', 'extra-file'):
        with tempfile.TemporaryDirectory(prefix='v53-applied-negative-') as temp:
            copy = Path(temp)/original.name; shutil.copytree(original, copy)
            if name == 'missing-image': (copy/'final/application.image').unlink()
            elif name == 'changed-image': (copy/'final/application.image').write_bytes(b'wrong')
            elif name == 'missing-ack': (copy/'final/ack.gsr').unlink()
            elif name == 'changed-crash': (copy/'crash/ack.gsr').write_bytes((copy/'final/ack.gsr').read_bytes())
            elif name == 'early-success': (copy/'fault.stdout').write_bytes((copy/'resume.stdout').read_bytes())
            elif name == 'missing-force':
                p = copy/'resume.stdout'; p.write_bytes(p.read_bytes().replace(canonical(dict(event='APPLY_END_FORCED'))+b'\n', b''))
            else: (copy/'final/extra').write_bytes(b'')
            try: validate_case(copy, row)
            except (ValueError, OSError) as error: negatives.append(dict(case=name, status='REJECT', reason=str(error)))
            else: raise ValueError('applied mutation accepted: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-applied-replay-') as temp:
        copy = Path(temp)/'retained'; shutil.copytree(path, copy); need(validate(copy) == result, 'applied portable replay')
    return dict(**result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('path'); args = parser.parse_args()
    print(json.dumps(qualify(args.path), sort_keys=True))
