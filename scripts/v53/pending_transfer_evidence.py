"""Original-first exact packet/context transfer replay; new source authority is conditional.

No source force, retirement, resource lease or complete owner progress is established here.
Every old generation/vote remains byte-identical; only the backing grant/packet changes.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from . import pending_context_evidence as e

ROUNDS = tuple(range(21, 28))


def validate(root):
    root = Path(root)
    e.need(root.is_dir() and not root.is_symlink(), 'transfer root directory')
    expected = {'receipt.json'} | {f'round-{n}' for n in ROUNDS} | {f'current-{n}.gscp' for n in ROUNDS[1:]}
    e.need({p.name for p in root.iterdir()} == expected, 'transfer complete round inventory')
    for path in root.rglob('*'):
        e.need(not path.is_symlink() and (path.is_file() or path.is_dir()), 'transfer linked/nonregular member')
    first = root/'round-21'
    initial_segments, initial_metadata, initial_binding = e.decode((first/'context.gspc').read_bytes())
    original_vote, values = e.votes((first/'pending.accept').read_bytes(), e.p.decode((first/'original-generation/source.gscp').read_bytes())['capsule']['cut'])
    old_packet = e.p.decode((first/'original-generation/source.gscp').read_bytes())
    protected = dict(old_packet['objects'])
    for phase in ('ENTRY', 'ACCEPT', 'PAYLOAD', 'PROOF', 'CERTIFICATE'):
        protected[e.digest(original_vote[phase])] = original_vote[phase]
    base_binding = {k: v for k, v in initial_binding.items() if k != 'backingPacket'}
    rows = []
    for counter in ROUNDS:
        round_root = root/f'round-{counter}'
        result = e.validate(round_root, backing_ballot=counter)
        segments, metadata, binding = e.decode((round_root/'context.gspc').read_bytes())
        e.need(segments[1] == initial_segments[1] and segments[4] == initial_segments[4] and metadata == initial_metadata
               and {k: v for k, v in binding.items() if k != 'backingPacket'} == base_binding,
               'transfer changed original context')
        for name in ('pending.accept', 'root.gsr', 'old-selector.gsr'):
            e.need((round_root/name).read_bytes() == (first/name).read_bytes(), 'transfer changed original bytes')
        backing = e.p.decode((round_root/'backing-source.gscp').read_bytes())
        if counter == 21:
            continue
        current_path = root/f'current-{counter}.gscp'
        e.need(0 < current_path.stat().st_size <= 32*e.MIB, 'transfer current packet capacity')
        current = e.p.decode(current_path.read_bytes())
        e.need({k: v for k, v in current['capsule'].items() if k != 'inventory'}
               == {k: v for k, v in backing['capsule'].items() if k != 'inventory'}, 'transfer changed current capsule')
        marker = ('current-capture-only-'+str(counter)).encode('ascii')
        e.need(current['objects'].get(e.digest(marker)) == marker, 'transfer current round marker')
        # A merge must contain exactly the current and original objects; prior backing
        # inventories are not input. This detects hidden accumulation and silent omission.
        objects = dict(current['objects'])
        for digest, raw in protected.items():
            e.need(digest not in objects or objects[digest] == raw, 'transfer conflicting protected bytes')
            objects[digest] = raw
        images = dict(current['images'])
        for digest, size in old_packet['images'].items():
            e.need(digest not in images or images[digest] == size, 'transfer conflicting protected image')
            images[digest] = size
        e.need(backing['objects'] == objects and backing['images'] == images, 'transfer exact protected union')
        e.need(e.packet_bytes(current['capsule'], objects, images) == (round_root/'backing-source.gscp').read_bytes(),
               'transfer exact canonical packet')
        for abandoned in range(22, counter):
            e.need(e.digest(('current-capture-only-'+str(abandoned)).encode('ascii')) not in backing['objects'],
                   'transfer accumulated abandoned backing')
        rows.append(dict(ballot=counter, objects=len(objects), contextBytes=result['contextBytes']))
    receipt_path = root/'receipt.json'; e.need(receipt_path.stat().st_size <= 16384, 'transfer receipt capacity')
    receipt = e.parse(receipt_path.read_bytes())
    expected = dict(schema='gse-v53-pending-transfer-v1', status='PASS', rounds=rows, newSourceOwnership='conditional-fixture',
                    contextForced=False, retirementAuthorized=False, runtimeEnabled=False)
    e.need(receipt == expected and all(type(receipt[k]) is type(v) for k, v in expected.items()), 'transfer exact receipt scope')
    return dict(status='PASS', rounds=7, transfers=6, originalFirst=True, originalVotePhase='CERTIFICATE',
                newSourceOwnership='conditional-fixture', contextForced=False, retirementAuthorized=False,
                runtimeEnabled=False, maximumBytesIndependentlyReplayed=False, fullOwnerProgress=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    variants = {
        'missing-round': 'transfer complete round inventory',
        'extra-round': 'transfer complete round inventory',
        'linked-current': 'transfer linked/nonregular member',
        'changed-current': 'transfer current round marker',
        'earlier-current': 'transfer current round marker',
        'changed-backing-ballot': 'context higher local source ballot/grant',
        'stale-context': 'context exact supplied selector/backing grant',
        'missing-certificate': 'context exact borrowed original certificate',
        'changed-original-metadata': 'context exact original metadata inventory/bytes',
        'false-retirement': 'transfer exact receipt scope',
        'false-force': 'transfer exact receipt scope',
        'false-source-ownership': 'transfer exact receipt scope',
    }
    for name, reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-transfer-negative-') as temporary:
            case = Path(temporary)/'evidence'; shutil.copytree(root, case)
            selected = case/'round-23'; context = selected/'context.gspc'
            if name == 'missing-round': shutil.rmtree(selected)
            elif name == 'extra-round': (case/'round-28').mkdir()
            elif name == 'linked-current':
                path = case/'current-23.gscp'; path.unlink(); path.symlink_to((root/path.name).resolve())
            elif name == 'changed-current':
                path = case/'current-23.gscp'; packet = e.p.decode(path.read_bytes()); objects = dict(packet['objects'])
                objects.pop(e.digest(b'current-capture-only-23')); path.write_bytes(e.packet_bytes(packet['capsule'], objects, packet['images']))
            elif name == 'earlier-current': shutil.copyfile(case/'current-22.gscp', case/'current-23.gscp')
            elif name == 'stale-context': shutil.copyfile(case/'round-22/context.gspc', context)
            elif name in ('changed-backing-ballot', 'changed-original-metadata', 'missing-certificate'):
                segments, metadata, binding = e.decode(context.read_bytes())
                if name == 'changed-backing-ballot':
                    for i, file, kind in ((2, 'backing-promise.gsr', 'PROMISE'), (3, 'backing-basis.gsr', 'BASIS')):
                        value = e.f.decode(segments[i], 'records', kind); value['ballot']['counter'] = 22
                        segments[i] = e.f.encode('records', kind, value); (selected/file).write_bytes(segments[i])
                elif name == 'changed-original-metadata': metadata['selected-coverage.json'] = b'{}'
                else:
                    path = selected/'backing-source.gscp'; packet = e.p.decode(path.read_bytes()); objects = dict(packet['objects']); objects.pop(binding['certificate'])
                    raw = e.packet_bytes(packet['capsule'], objects, packet['images']); path.write_bytes(raw); packet = e.p.decode(raw)
                    binding['backingPacket'] = e.info(raw); segments[0] = e.f.canonical(binding)
                    basis = e.f.decode(segments[3], 'records', 'BASIS'); basis.update(capsule=e.digest(packet['capsuleBytes']), inventory=e.digest(packet['indexBytes']))
                    segments[3] = e.f.encode('records', 'BASIS', basis); (selected/'backing-basis.gsr').write_bytes(segments[3])
                context.write_bytes(e.encode(segments, metadata))
            else:
                path = case/'receipt.json'; value = e.parse(path.read_bytes())
                if name == 'false-retirement': value['retirementAuthorized'] = True
                elif name == 'false-force': value['contextForced'] = True
                else: value['newSourceOwnership'] = 'actual-force'
                path.write_bytes(e.f.canonical(value))
            try: validate(case)
            except ValueError as error:
                e.need(str(error) == reason, 'wrong transfer negative reason: '+name+': '+str(error))
                negatives.append(dict(case=name, reason=reason))
            else: raise ValueError('accepted transfer mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-transfer-portable-') as temporary:
        moved = Path(temporary)/'evidence'; shutil.copytree(root, moved)
        e.need(validate(moved) == result, 'transfer portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args()
    print(json.dumps(qualify(args.root), sort_keys=True))
