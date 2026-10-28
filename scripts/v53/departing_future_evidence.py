"""Independent nonvoting future-proof bytes; original voting authority is conditional.

Nine records mean exactly an old-only owner completing its immediate certified
FINAL. They never stand in for a successor checkpoint vote or a native dispatch.
"""
import argparse
import json
import shutil
import struct
import tempfile
from pathlib import Path
from . import departing_end_evidence as d
from .format_fixture import canonical, decode, encode
from .membership_model import need

RECORDS = ('selector.gsr', 'promise.gsr', 'selected.gsr', 'entry.gsr', 'accept.gsr',
           'proof.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr')
KINDS = ('SELECTOR', 'PROMISE', 'SELECTED', 'ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE', 'CATALOG', 'CHECKPOINT')


def originals(metadata, records):
    need(set(records) == set(RECORDS), 'departing future exact original inventory')
    root, owner, parent = (metadata[k] for k in ('root', 'owner', 'parent'))
    frames = {name: decode(records[name], 'records', kind, root) for name, kind in zip(RECORDS, KINDS)}
    catalog, statement, entry, cert = (frames[n+'.gsr'] for n in ('catalog', 'statement', 'entry', 'certificate'))
    node = owner['node']; old = parent['cut']['view']; end = catalog['cut']; new = end['view']
    need(owner in catalog['identities'] and frames['selector.gsr']['node'] == node, 'departing future original owner')
    need(entry['kind'] == 'FINAL' and old['operation'] is not None and node in old['old'] and node not in old['new']
         and new == dict(generation=old['generation']+1, old=old['new'], new=old['new'], operation=None), 'departing future exact removal')
    need(entry['index'] == cert['index'] == end['index'] == parent['cut']['index']+1
         and entry['previous'] == parent['cut']['entry'] and cert['entry'] == end['entry'] == d.digest(records['entry.gsr'])
         and cert['authority'] == entry['authority'] == d.digest(canonical(dict(old, root=root))), 'departing future original FINAL')
    need(statement == dict(root=root, scope='MEMBERSHIP', start=parent['cut'], end=end,
                          catalogBefore=parent['catalog'], applicationBefore=parent['application'],
                          catalogAfter=d.digest(records['catalog.gsr']), applicationAfter=catalog['application']), 'departing future exact statement')
    proof, accept = frames['proof.gsr'], frames['accept.gsr']
    need({k: v for k, v in cert.items() if k != 'proofs'} == proof
         and {k: v for k, v in proof.items() if k != 'accepts'} == accept
         and frames['promise.gsr']['ballot'] == frames['selected.gsr']['ballot'] == accept['ballot'], 'departing future original phases')
    need(all(p['lower']['cut']['index'] < end['index'] for p in metadata['peers']), 'departing future peer advancement')
    return frames


def expected_frame(metadata, records):
    originals(metadata, records)
    parts = [canonical(metadata), *(records[n] for n in RECORDS)]
    body = struct.pack('>I', len(parts[0]))+parts[0]+struct.pack('>I', len(RECORDS))
    body += b''.join(struct.pack('>I', len(p))+p for p in parts[1:])
    need(len(body)+44 <= 3*1024*1024, 'departing future capacity')
    return struct.pack('>IHHI', 0x47534654, 1, 3, len(body)+44)+bytes.fromhex(d.digest(body))+body


def validate_case(path, row):
    profile = row['profile']; size = int(profile.split('-')[0]); node = 'node-'+str(size)
    need(profile in d.PROFILES and set(p.name for p in path.iterdir()) == {'records', 'end', 'future.gsft', 'inherited.gsfs', 'parent.json'}, 'departing future case inventory')
    directory = path/'records'
    need(directory.is_dir() and not directory.is_symlink() and {p.name for p in directory.iterdir()} == set(RECORDS), 'departing future exact original inventory')
    records = {n: d.read(directory/n, 2*1024*1024) for n in RECORDS}
    end = d.state(path/'end'); parent_bytes = d.read(path/'parent.json')
    d.materialization(end, records['entry.gsr'], parent_bytes, profile)
    for name in ('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr'):
        need(records[name] == end[name], 'departing future original end bytes')
    catalog = decode(records['catalog.gsr'], 'records', 'CATALOG'); root = catalog['root']
    owner = next(v for v in catalog['identities'] if v['node'] == node)
    peer = next(v for v in catalog['identities'] if v['node'] == 'node-1')
    parent = json.loads(parent_bytes)
    metadata = dict(root=root, owner=owner, revision=1, previous='ab'*32, parent=parent, peers=[dict(identity=peer, lower=parent)])
    expected = expected_frame(metadata, records); need(d.read(path/'future.gsft', 3*1024*1024) == expected, 'departing future exact original proof')
    body = canonical(dict(root=root, owner=peer, proofs=[dict(owner=owner, sha256=d.digest(expected))]))
    prefix = struct.pack('>IHHII', 0x47534653, 1, 3, 0, len(body))
    inherited = prefix+bytes.fromhex(d.digest(prefix+body))+body
    need(d.read(path/'inherited.gsfs') == inherited, 'departing future inherited original owner')
    need(row == dict(profile=profile, node=node, status='PASS', future=d.digest(expected)), 'departing future result binding')
    return metadata, records


def validate(root):
    root = Path(root); receipt = json.loads(d.read(root/'receipt.json'))
    need(set(receipt) == {'schema', 'authority', 'cases'} and receipt['schema'] == 'gse-v53-departing-future-v1'
         and receipt['authority'] == 'conditional-fixture', 'departing future qualification scope')
    need([r['profile'] for r in receipt['cases']] == list(d.PROFILES), 'departing future complete profile matrix')
    need(set(p.name for p in root.iterdir()) == {'receipt.json', *d.PROFILES}, 'departing future qualification inventory')
    for row in receipt['cases']: validate_case(root/row['profile'], row)
    return dict(status='PASS', profiles=len(d.PROFILES), authority='conditional-fixture', nativeDispatch=False, phase3Complete=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    variants = [('proof', 'future.gsft', 'departing future exact original proof'),
                ('inherited', 'inherited.gsfs', 'departing future inherited original owner'),
                ('end-image', 'end/application.image', 'departing original member hashes'),
                ('fake-ack', 'records/ack.gsr', 'departing future exact original inventory'),
                ('missing-proof', 'records/proof.gsr', 'departing future exact original inventory'),
                ('parent', 'parent.json', 'departing original parent')]
    for name, relative, reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-departing-future-negative-') as temp:
            target = Path(temp)/'raw'; shutil.copytree(root, target); path = target/d.PROFILES[0]/relative
            if name == 'fake-ack': path.write_bytes(b'not-a-vote')
            elif name == 'missing-proof': path.unlink()
            elif name == 'parent': path.write_bytes(path.read_bytes()+b' ')
            else:
                raw = path.read_bytes(); path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            try: validate(target)
            except ValueError as error: need(str(error) == reason, f'departing future wrong negative: {name}: {error}')
            else: raise ValueError('departing future negative accepted: '+name)
            negatives.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(result, negatives=negatives)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('root'); args = p.parse_args()
    print(json.dumps(qualify(args.root), sort_keys=True))
