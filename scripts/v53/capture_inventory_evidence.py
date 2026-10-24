"""Original-first replay of deferred source inventory admission, without a grant claim.

Actual two-grant capture fixtures use the existing journal recovery afterwards.
Historical generation/remote quorum inputs remain conditional; context capture
and rebinding are not enabled by this component.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from . import current_generation_evidence as current
from . import journal_context_evidence as owner
from . import grant_evidence as g
from . import source_packet as packet

f, need = g.f, g.need
CUTS = ('CAPTURE_INTENT_CREATED', 'SOURCE_PACKET_PREFIX_WRITTEN',
        'SOURCE_IMAGE_PREFIX_WRITTEN', 'BASIS_FORCED')


def write_snapshot(path, files, directories):
    path.mkdir()
    for name in sorted(directories): (path/name).mkdir(parents=True, exist_ok=True)
    for name, raw in files.items(): (path/name).write_bytes(raw)


def validate_case(case, size, cut):
    need(case.is_dir() and not case.is_symlink() and {p.name for p in case.iterdir()} ==
         {'initial', 'inventory', 'recovered', 'intent.gsr'}, 'capture inventory case files')
    initial, directories = owner.read_snapshot(case/'initial')
    root = initial['root.gsr'][16:48].hex()
    rows = g.journal(initial['grants.gsr'], root, 'node-1')
    need([k for k, _, _ in rows] == ['PROMISE', 'PROMISE', 'BASIS', 'PROMISE'] +
         (['BASIS'] if cut == 'BASIS_FORCED' else []), 'capture inventory initial journal')
    old, new = rows[2][2], rows[3][2]
    need([rows[i][2]['ballot']['counter'] for i in (0, 1, 3)] == [10, 20, 21]
         and new['basisId'] != old['basisId'], 'capture inventory ballot identity')
    prefix = 'sources/'+new['basisId']; old_prefix = 'sources/'+old['basisId']
    # Isolate only the independently checkable original state. Never derive expected
    # final source bytes, journal or completion from the recovered snapshot.
    base = {p: b for p, b in initial.items() if not p.startswith(prefix+'/') and p != 'source.capture.gsr'}
    base['grants.gsr'] = b''.join(raw for _, raw, _ in rows[:3])
    base_dirs = directories-{prefix}
    with tempfile.TemporaryDirectory(prefix='v53-capture-inventory-original-') as tmp:
        path = Path(tmp)/'node'; write_snapshot(path, base, base_dirs)
        _, _, generation, _ = current.current(path, size)
    source = {p.removeprefix(old_prefix+'/'): b for p, b in base.items() if p.startswith(old_prefix+'/')}
    data = packet.decode(source['source.gscp']); packet.bind(data, rows[2][1])
    need(generation['cut'] == old['cut'] and len(data['images']) == 1, 'capture inventory original profile')
    expected_basis = dict(new, voter='node-1', cut=old['cut'], capsule=old['capsule'],
                          inventory=old['inventory'], accepted=old['accepted'])
    basis_raw = f.encode('records', 'BASIS', expected_basis)
    intent = base['selector.gsr']+rows[3][1]+basis_raw
    need(g.read(case/'intent.gsr', 28672) == intent, 'capture inventory exact intent')
    expected = dict(base); expected['grants.gsr'] += rows[3][1]
    expected['source.capture.gsr'] = b'' if cut == CUTS[0] else intent
    expected_dirs = set(base_dirs)
    if cut != CUTS[0]:
        expected_dirs.add(prefix)
        raw = source['source.gscp']
        expected[prefix+'/source.gscp'] = raw[:len(raw)//2] if cut == CUTS[1] else raw
        if cut != CUTS[1]:
            image = next(h+'.image' for h in data['images']); raw = source[image]
            expected[prefix+'/'+image] = raw[:len(raw)//2] if cut == CUTS[2] else raw
    if cut == CUTS[3]: expected['grants.gsr'] += basis_raw
    need(initial == expected and directories == expected_dirs, 'capture inventory original cut bytes')
    observed, observed_dirs = owner.read_snapshot(case/'inventory')
    need(observed == expected and observed_dirs == expected_dirs, 'capture inventory resolver mutated bytes')
    final = dict(base); final['grants.gsr'] += rows[3][1]+basis_raw
    final.update({prefix+'/'+name: raw for name, raw in source.items()})
    actual, actual_dirs = owner.read_snapshot(case/'recovered')
    need(actual == final and actual_dirs == base_dirs|{prefix}, 'capture inventory exact recovery')
    return dict(case=case.name, status='PASS', size=size, cut=cut)


def validate(root):
    root = Path(root)
    names = {f'{size}-{cut}' for size in (3, 4, 5) for cut in CUTS}
    need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()} == names|{'receipt.json'},
         'capture inventory evidence inventory')
    rows = [validate_case(root/f'{size}-{cut}', size, cut) for size in (3, 4, 5) for cut in CUTS]
    receipt = json.loads(g.read(root/'receipt.json', 16384))
    need(receipt == dict(schema='gse-v53-capture-inventory-v1', status='PASS', cases=rows,
                         contextCaptureEnabled=False, runtimeEnabled=False), 'capture inventory receipt scope')
    return dict(status='PASS', cases=12, profiles=[3, 4, 5], originalFirst=True,
                contextCaptureEnabled=False, freshProcesses=False, runtimeEnabled=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    variants = {'missing-case': 'capture inventory evidence inventory',
                'corrupt-original': 'packet checksum',
                'intent': 'capture inventory exact intent',
                'mutated-prefix': 'capture inventory original cut bytes',
                'resolver-filled-prefix': 'capture inventory resolver mutated bytes',
                'recovery-lost-source': 'capture inventory exact recovery',
                'recovery-changed-basis': 'capture inventory exact recovery',
                'recovery-left-intent': 'capture inventory exact recovery',
                'scope': 'capture inventory receipt scope',
                'symlink': 'owner context linked/nonregular member'}
    for name, reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-capture-inventory-negative-') as tmp:
            moved = Path(tmp)/'evidence'; shutil.copytree(root, moved)
            case = moved/'3-SOURCE_PACKET_PREFIX_WRITTEN'
            if name == 'missing-case': shutil.rmtree(case)
            elif name == 'corrupt-original':
                p = max((case/'initial/sources').rglob('source.gscp'), key=lambda q: q.stat().st_size)
                raw = p.read_bytes(); p.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name == 'intent': (case/'intent.gsr').write_bytes(b'changed')
            elif name == 'mutated-prefix':
                p = next(p for p in (case/'initial/sources').rglob('source.gscp') if p.stat().st_size < max(q.stat().st_size for q in (case/'initial/sources').rglob('source.gscp')))
                p.write_bytes(p.read_bytes()+b'x')
            elif name == 'resolver-filled-prefix':
                sources = list((case/'inventory/sources').rglob('source.gscp'))
                p = min(sources, key=lambda q: q.stat().st_size); p.write_bytes(max(sources, key=lambda q: q.stat().st_size).read_bytes())
            elif name == 'recovery-lost-source': next((case/'recovered/sources').rglob('source.gscp')).unlink()
            elif name == 'recovery-changed-basis': (case/'recovered/grants.gsr').write_bytes((case/'initial/grants.gsr').read_bytes())
            elif name == 'recovery-left-intent': shutil.copyfile(case/'intent.gsr', case/'recovered/source.capture.gsr')
            elif name == 'scope':
                p = moved/'receipt.json'; value = json.loads(p.read_bytes()); value['contextCaptureEnabled'] = True; p.write_bytes(f.canonical(value))
            else:
                p = case/'inventory/selector.gsr'; p.unlink(); p.symlink_to((case/'initial/selector.gsr').resolve())
            try: validate(moved)
            except ValueError as error:
                need(str(error) == reason, 'wrong capture inventory negative: '+name+': '+str(error))
                negatives.append(dict(case=name, reason=reason))
            else: raise ValueError('accepted capture inventory mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-capture-inventory-portable-') as tmp:
        moved = Path(tmp)/'evidence'; shutil.copytree(root, moved)
        need(validate(moved) == result, 'capture inventory portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args()
    print(json.dumps(qualify(args.root), sort_keys=True))
