"""Inspect retained offline-survivor experiments without claiming protocol acceptance.

Checks exact selected inventories, unchanged offline files, and supplemental bridge
bytes against the original per-node applied-end files. It does NOT independently
reconstruct every ACCEPT/PROOF, replay application images, or prove force ordering.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile

from . import round_storage_evidence as c
from .ancestry_pruning_evidence import frames
from .membership_model import need


def digest(value):
    return c.digest(value)


def original_acks(raw):
    originals = {}
    for snapshot in sorted(raw.glob('slot-*-applied')):
        for node in sorted(snapshot.glob('node-*')):
            files = c.inventory(node)
            identity = c.f.decode(files['node.gsr'], 'records', 'NODE')['identity']
            for name in sorted(k for k, v in files.items() if k.startswith('applied-end/') and k.endswith('ack.gsr') and v is not None):
                path = node/name
                original = files[name]
                value = c.f.decode(original, 'records', 'CHECKPOINT_ACK')
                need(value['voter'] == identity['node'] and value['incarnation'] == identity['storage'], 'diagnostic original ACK identity')
                statement = files[name.replace('ack.gsr', 'statement.gsr')]
                body = c.f.decode(statement, 'records', 'CHECKPOINT')
                need(value['statement'] == digest(statement) and value['cut'] == body['end'] and value['root'] == body['root'], 'diagnostic original ACK statement')
                originals.setdefault(digest(original), []).append(dict(path=path.relative_to(raw).as_posix(), bytes=original))
    return originals


def inspect_generation(path, originals, wanted):
    files = c.inventory(path)
    prefix, members, packet = c.current(files)
    cap = packet['capsule']
    direct = []
    anchors = {}
    for item in cap['items']:
        value = c.f.decode(packet['objects'][item['statement']], 'records', 'CHECKPOINT')
        direct.append([value['start']['index'], value['end']['index']])
        for cut, catalog, image in (('start', 'catalogBefore', 'applicationBefore'), ('end', 'catalogAfter', 'applicationAfter')):
            anchor = dict(cut=value[cut], catalog=value[catalog], application=value[image])
            key = c.f.canonical(value[cut])
            need(key not in anchors or anchors[key] == anchor, 'diagnostic conflicting direct anchor')
            anchors[key] = anchor
    groups = []
    for frame in frames(members['ancestry.gsr']) if 'ancestry.gsr' in members else []:
        if int.from_bytes(frame[8:10], 'big') == c.f.catalog()['records']['CHECKPOINT']['id']:
            groups.append([frame])
        else:
            need(bool(groups), 'diagnostic ancestry ACK before statement')
            groups[-1].append(frame)
    need(len(groups) <= 6, 'diagnostic ancestry group capacity')
    lower = []
    for group in groups:
        statement = c.f.decode(group[0], 'records', 'CHECKPOINT')
        start = dict(cut=statement['start'], catalog=statement['catalogBefore'], application=statement['applicationBefore'])
        end = dict(cut=statement['end'], catalog=statement['catalogAfter'], application=statement['applicationAfter'])
        need(statement['scope'] == 'RANGE' and statement['start']['view'] == statement['end']['view'] and
             statement['start']['index'] < statement['end']['index'] and anchors.get(c.f.canonical(statement['end'])) == end,
             'diagnostic supplemental endpoints')
        voters = []
        origins = []
        for frame in group[1:]:
            ack = c.f.decode(frame, 'records', 'CHECKPOINT_ACK')
            need(ack['root'] == cap['root'] == statement['root'] and ack['statement'] == digest(group[0]) and ack['cut'] == statement['end'], 'diagnostic supplemental ACK binding')
            exact = [v for v in originals.get(digest(frame), ()) if v['bytes'] == frame]
            need(bool(exact), 'diagnostic supplemental ACK lacks original file')
            voters.append(ack['voter'])
            origins.append(exact[0]['path'])
        need(voters == sorted(set(voters)) and set(voters) <= set(statement['start']['view']['old']) | set(statement['start']['view']['new']), 'diagnostic duplicate/unordered/foreign ACK voter')
        for side in ('old', 'new'):
            electorate = statement['start']['view'][side]
            need(len(set(voters) & set(electorate)) > len(electorate)//2, 'diagnostic supplemental majority')
        lower.append(dict(start=start['cut']['index'], end=end['cut']['index'], matchesOffline=start == wanted,
                          statementSha256=digest(group[0]), originalAcknowledgements=origins))
    selected = {name: digest(data) for name, data in members.items() if name in ('source.gscp', 'ancestry.gsr', 'selected-sources.gsr', 'selected-coverage.json')}
    return dict(cut=cap['cut']['index'], direct=direct, supplemental=lower,
                preservesOffline=any(anchor == wanted for anchor in anchors.values()) or any(v['matchesOffline'] for v in lower),
                ancestryGroups=len(groups), coverageBytes=len(members.get('selected-coverage.json', b'')),
                manifestSha256=digest(files[prefix+'generation.gsr']), originalMembers=selected)


def inspect(directory):
    root = Path(directory)
    raw = root/'raw'
    before = c.inventory(raw/'surviving-stale-before/node-4')
    _, _, old = c.current(before)
    wanted = c.anchor(old['capsule'])
    need(wanted['cut']['index'] == 1, 'diagnostic original offline cut')
    unchanged = []
    for snapshot in sorted(raw.iterdir()):
        if re.fullmatch(r'slot-[2-9]-(accepted|proved|certified|applied|published|settled)', snapshot.name) or re.fullmatch(r'campaign-[34]-(prepared|selected|installed|settled)', snapshot.name) or snapshot.name == 'surviving-stale-after-transition':
            need(c.inventory(snapshot/'node-4') == before, 'diagnostic offline node changed: '+snapshot.name)
            unchanged.append(snapshot.name)
    need(bool(unchanged), 'diagnostic missing offline interval')
    origins = original_acks(raw)
    rows = []
    for snapshot in sorted(raw.iterdir()):
        if re.fullmatch(r'slot-[0-9]+-(published|settled)', snapshot.name) or re.fullmatch(r'campaign-[0-9]+-(prepared|selected|installed|settled)', snapshot.name):
            rows.append(dict(snapshot=snapshot.name, **inspect_generation(snapshot/'node-1', origins, wanted)))
    return dict(status='INSPECTED', scope='physical-inventory-diagnostic', qualification=False,
                phase3Complete=False, offlineAnchor=wanted, unchangedOfflineSnapshots=len(unchanged),
                originalAckRecords=len(origins), snapshots=rows)


def check_integrity(directory):
    original = inspect(directory)
    # These reject damaged diagnostic inputs; they are not the protocol's N gate.
    reasons = {
        'offline-bytes': 'diagnostic offline node changed:',
        'selected-manifest': 'checksum',
        'original-ack-missing': 'diagnostic supplemental ACK lacks original file',
        'original-ack-owner': 'diagnostic original ACK identity',
    }
    examples = [a for row in original['snapshots'] for bridge in row['supplemental']
                for a in bridge['originalAcknowledgements']]
    need(bool(examples), 'diagnostic integrity needs original ACK examples')
    outcomes = []
    for variant, reason in reasons.items():
        with tempfile.TemporaryDirectory(prefix='v53-survivor-diagnostic-') as tmp:
            root = Path(tmp)/'evidence'
            shutil.copytree(Path(directory)/'raw', root/'raw')
            if variant == 'offline-bytes':
                path = root/'raw/slot-2-accepted/node-4/grants.gsr'
                path.write_bytes(path.read_bytes()+b'changed')
            elif variant == 'selected-manifest':
                files = c.inventory(root/'raw/slot-1-published/node-1')
                prefix, _, _ = c.current(files)
                path = root/'raw/slot-1-published/node-1'/prefix/'generation.gsr'
                data = bytearray(path.read_bytes()); data[16] ^= 1; path.write_bytes(data)
            else:
                path = root/'raw'/examples[0]
                if variant == 'original-ack-missing':
                    path.unlink()
                else:
                    value = c.f.decode(path.read_bytes(), 'records', 'CHECKPOINT_ACK')
                    value['voter'] = 'node-6'
                    path.write_bytes(c.f.encode('records', 'CHECKPOINT_ACK', value))
            try:
                inspect(root)
            except ValueError as error:
                need(reason in str(error), 'unrelated diagnostic integrity rejection: '+variant+': '+str(error))
            else:
                raise ValueError('accepted diagnostic corruption: '+variant)
            outcomes.append(dict(case=variant, status='REJECTED', reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-survivor-portable-') as tmp:
        root = Path(tmp)/'evidence'
        shutil.copytree(Path(directory)/'raw', root/'raw')
        need(inspect(root) == original, 'diagnostic relocation mismatch')
    return dict(original=original, integrityMutations=outcomes, portableInventory=True,
                qualification=False, phase3Complete=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    parser.add_argument('--check-integrity', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check_integrity(args.directory) if args.check_integrity else inspect(args.directory), sort_keys=True))
