"""Portable original-first corruption tests over compacted byte fixtures."""
import copy
from pathlib import Path
import shutil
import struct
import tempfile

from . import capsule_evidence as e
from . import source_packet as p
from . import format_fixture as f
from .context_evidence import parse, sha
from .membership_model import need

CASES = ('hidden-boundary', 'missing-edge', 'missing-descriptor', 'missing-original-proof',
         'old-majority-only', 'new-majority-only', 'duplicate-ack', 'wrong-checkpoint',
         'catalog-rewrite', 'missing-checkpoint-ownership', 'wrong-applied-cut', 'force-before-applied',
         'missing-owned-file', 'linked-file', 'runtime-relabel', 'missing-cut')


def encode(capsule, objects, images):
    index = f.canonical(dict(schema='gse-membership-source-index/1.3',
        objects=[dict(sha256=h, bytes=len(b)) for h,b in sorted(objects.items())],
        images=[dict(sha256=h, bytes=size) for h,size in sorted(images.items())]))
    capsule = dict(capsule, inventory=sha(index)); frame = f.encode('records', 'CAPSULE', capsule)
    body = len(frame).to_bytes(4, 'big')+frame+len(index).to_bytes(4, 'big')+index+b''.join(b for h,b in sorted(objects.items()))
    prefix = struct.pack('>4sHHHHI', b'GSCP', 1, 3, 0, 0, len(body))
    return prefix+bytes.fromhex(sha(prefix+body))+body


def mutate(root, case):
    path = root/'capsules/5-REPLACE/cut-9'; manifest = parse((path/'manifest.json').read_bytes())
    packet = p.decode((path/'packet.bin').read_bytes()); capsule = copy.deepcopy(packet['capsule']); objects = dict(packet['objects'])
    edge = capsule['items'][1]; owned = manifest['owned'][0]; packet_changed = False
    if case == 'hidden-boundary': edge['kind'] = 'RANGE'; packet_changed = True
    elif case == 'missing-edge': del capsule['items'][1]; packet_changed = True
    elif case == 'missing-descriptor': del objects[edge['descriptor']]; packet_changed = True
    elif case == 'missing-original-proof':
        cert = f.decode(objects[edge['certificate']], 'records', 'CERTIFICATE')
        proof = {k:v for k,v in cert.items() if k != 'proofs'}
        del objects[sha(f.encode('records', 'PROOF', proof))]; packet_changed = True
    elif case in ('old-majority-only', 'new-majority-only'):
        voters = {'node-1', 'node-2', 'node-5' if case.startswith('old') else 'node-6'}
        edge['endorsements'] = [h for h in edge['endorsements'] if f.decode(objects[h], 'records', 'CHECKPOINT_ACK')['voter'] in voters]; packet_changed = True
    elif case == 'duplicate-ack': edge['endorsements'][1] = edge['endorsements'][0]; packet_changed = True
    elif case == 'wrong-checkpoint':
        statement = f.decode(objects[edge['statement']], 'records', 'CHECKPOINT'); statement['catalogBefore'] = 'ff'*32
        raw = f.encode('records', 'CHECKPOINT', statement); objects[sha(raw)] = raw; edge['statement'] = sha(raw); packet_changed = True
    elif case == 'catalog-rewrite':
        catalog = f.decode(objects[capsule['catalog']], 'records', 'CATALOG'); catalog['retiredThrough'] = 0
        raw = f.encode('records', 'CATALOG', catalog); objects[sha(raw)] = raw; capsule['catalog'] = sha(raw); packet_changed = True
    elif case == 'missing-checkpoint-ownership': manifest['owned'].pop(0)
    elif case == 'wrong-applied-cut':
        value = parse((path/owned['applied']).read_bytes()); value['cut']['index'] += 1; data = f.canonical(value)
        (path/owned['applied']).write_bytes(data)
        next(row for row in manifest['forces'] if row['path'] == owned['applied'])['sha256'] = sha(data)
    elif case == 'force-before-applied':
        manifest['forces'][0], manifest['forces'][1] = manifest['forces'][1], manifest['forces'][0]
        for i,row in enumerate(manifest['forces'], 1): row['sequence'] = i
    elif case == 'missing-owned-file': (path/owned['ack']).unlink()
    elif case == 'linked-file': (path/owned['ack']).unlink(); (path/owned['ack']).symlink_to(path/'packet.bin')
    elif case == 'runtime-relabel': manifest['authorityEvidence'] = True
    elif case == 'missing-cut': shutil.rmtree(root/'capsules/3-ADD/cut-0')
    else: raise ValueError('unknown capsule negative')
    if packet_changed:
        data = encode(capsule, objects, packet['images']); (path/'packet.bin').write_bytes(data); manifest['packetSha256'] = sha(data)
    (path/'manifest.json').write_bytes(f.canonical(manifest))


def run(original):
    original = Path(original).resolve(); expected = e.validate(original)
    results = []
    with tempfile.TemporaryDirectory(prefix='v53-capsule-negatives-') as directory:
        copied = Path(directory)/'relocated'; shutil.copytree(original, copied)
        need(e.validate(copied) == expected, 'portable compacted capsule replay')
        for case in CASES:
            target = Path(directory)/case; shutil.copytree(original, target); mutate(target, case)
            try: e.validate(target)
            except ValueError as error: results.append(dict(case=case, status='REJECT', reason=str(error)))
            else: raise ValueError('accepted capsule negative: '+case)
            shutil.rmtree(target)
    need(tuple(r['case'] for r in results) == CASES, 'capsule negative inventory')
    return results
