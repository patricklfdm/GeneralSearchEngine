"""Independent inspection of actual Step B output; never invokes Java or repairs files."""
import hashlib
import json
import struct
from pathlib import Path
from . import admission_format as f


def files(path):
    result = {}
    for item in sorted(path.rglob('*')):
        f.check(not item.is_symlink(), 'symlink in offline evidence')
        if item.is_file():
            f.check(item.stat().st_nlink == 1, 'aliased evidence file')
            result[item.relative_to(path).as_posix()] = item.read_bytes()
    return result


def rows(raw):
    result, offset = [], 0
    while offset < len(raw):
        f.check(len(raw) - offset >= 48, 'torn operation header')
        size = 48 + struct.unpack_from('>i', raw, offset + 12)[0]
        f.check(48 < size <= f.META and size <= len(raw) - offset, 'torn operation row')
        encoded = raw[offset:offset + size]
        r = f.record(encoded, 21)
        row = dict(plan=r.take(32), sequence=r.number('q'), previous=r.take(32), phase=r.number('B'),
                   preparations=[r.take(32) for _ in range(3)], receipt=r.take(32), raw=encoded)
        r.end(); result.append(row); offset += size
    f.check(0 < len(result) <= 5, 'invalid journal count')
    previous = f.ZERO
    for index, row in enumerate(result, 1):
        f.check(row['sequence'] == index and row['previous'] == previous, 'operation row chain')
        previous = row['raw'][16:48]
    return result


def bootstrap(root):
    root = Path(root)
    operation = files(root / 'operation')
    allowed = {'operation.lock', 'plan.gsr', 'operation.gsr', 'receipt.pending.gsr', 'receipt.gsr', 'cleanup.gsr'}
    f.check(set(operation) <= allowed and operation['operation.lock'] == b'', 'operation inventory')
    raw = operation['plan.gsr']; r = f.record(raw, 17)
    f.check(r.number('H') == 1, 'plan version')
    descriptor = f.json_value(r.blob(f.META)); manifest_raw = r.blob(f.META); source = r.blob(f.META); length = r.number('q')
    inventories = [f.inventory(r) for _ in range(3)]; r.end()
    f.check(descriptor['operation']['path'] == str(root / 'operation'), 'operation path')
    journal = rows(operation['operation.gsr']) if 'operation.gsr' in operation else []
    phase = journal[-1]['phase'] if journal else 0
    nodes = [v['node'] for v in descriptor['replicas']]
    preparations = [f.framed(18, raw[16:48] + manifest_raw[16:48] + f.text(node) + f.inventory_digest(inv))
                    for node, inv in zip(nodes, inventories)]
    receipt = f.framed(19, f.blob(raw) + struct.pack('>i', 3) + b''.join(f.blob(v) for v in preparations))
    for index, row in enumerate(journal, 1):
        f.check(row['plan'] == raw[16:48], 'operation plan binding')
        if row['phase'] == 5:
            f.check(index > 1 and journal[index - 2]['phase'] in (1, 2)
                    and row['preparations'] == journal[index - 2]['preparations'] and row['receipt'] == f.ZERO, 'abort transition')
        else:
            f.check(row['phase'] == index <= 4 and row['preparations'] == ([f.ZERO] * 3 if index == 1 else [v[16:48] for v in preparations])
                    and row['receipt'] == (receipt[16:48] if index == 4 else f.ZERO), 'publication transition')
    if phase == 5:
        return cleanup(root)
    f.check('cleanup.gsr' not in operation or phase in (1, 2), 'cleanup after commit')
    if 'receipt.gsr' in operation:
        f.check(phase in (3, 4) and operation['receipt.gsr'] == receipt, 'decision publication')
    if 'receipt.pending.gsr' in operation:
        f.check(phase == 3 and operation['receipt.pending.gsr'] == receipt, 'pending receipt')
    if phase == 4:
        f.check(operation.get('receipt.gsr') == receipt, 'committed receipt missing')
    sealed, genesis = [], None
    for node, local, inventory, preparation in zip(nodes, descriptor['replicas'], inventories, preparations):
        target = Path(local['target']['path']); observed = files(target) if target.exists() else {}
        expected = {v[0]: v for v in inventory}
        f.check(set(observed) <= set(expected) | {'bootstrap-prepared.gsr', 'bootstrap-seal.gsr', 'bootstrap-seal.pending.gsr'}, 'unknown target member')
        for name, data in observed.items():
            if name in expected:
                _, kind, size, digest = expected[name]
                f.check(kind == 1 and len(data) <= size and (len(data) != size or f.sha(data) == digest), 'initial payload binding')
        if phase >= 2:
            f.check(set(expected) <= set(observed) and all(len(observed[name]) == v[2] and f.sha(observed[name]) == v[3] for name, v in expected.items()), 'prepared payload missing')
            f.check(observed.get('bootstrap-prepared.gsr') == preparation, 'prepared node receipt missing')
        if 'bootstrap-prepared.gsr' in observed:
            f.check(observed['bootstrap-prepared.gsr'] == preparation, 'local preparation changed')
        if 'genesis.gsr' in observed and len(observed['genesis.gsr']) == length:
            g = f.genesis(observed['genesis.gsr']); g['raw'] = observed['genesis.gsr']
            m = f.manifest(manifest_raw, g)
            f.plan(raw, m, g, manifest_raw)
            f.check(g['source'] == source, 'source provenance binding')
            genesis = g
            if phase >= 2:
                f.initial_root({node + '/' + k: v for k, v in observed.items()}, node, m)
        for name in ('bootstrap-seal.gsr', 'bootstrap-seal.pending.gsr'):
            if name in observed:
                f.check(phase == 4 and observed[name] == f.framed(20, f.text(node) + f.blob(receipt)), 'seal precedes committed decision')
                if name == 'bootstrap-seal.gsr':
                    sealed.append(node)
    if genesis and descriptor['source'] is not None:
        source_path = Path(descriptor['source']['path'])
        if source_path.exists():
            _, _, _, source_members = f.source(f.Reader(source))
            observed = files(source_path)
            f.check(set(observed) == {v[0] for v in source_members}, 'source member set')
            for name, _, size, digest in source_members:
                f.check(len(observed[name]) == size and f.sha(observed[name]) == digest, 'source changed')
        else:
            f.check(phase >= 3, 'uncommitted source lost')
    return dict(phase=phase, sealedNodes=sealed, planDigest=raw[16:48].hex(),
                manifestDigest=manifest_raw[16:48].hex(), applicationSequence=None if genesis is None else genesis['base'])


def cleanup(root):
    root = Path(root); operation = root / 'operation'
    raw = (operation / 'cleanup.gsr').read_bytes(); r = f.record(raw, 22)
    plan, previous = r.take(32), r.take(32); descriptor = f.json_value(r.blob(f.META)); r.end()
    f.exact(descriptor, 'operation inventory deletePaths'); f.path_binding(descriptor['operation'])
    f.check(descriptor['operation']['path'] == str(operation), 'cleanup relocated')
    entries, delete = descriptor['inventory'], descriptor['deletePaths']; names = [e['path'] for e in entries]
    f.check(names == sorted(set(names), key=lambda v: v.encode()), 'cleanup inventory order')
    f.check(len(delete) == len(set(delete)) and set(delete) == {e['path'] for e in entries if e['owner'] == plan.hex()}, 'cleanup deletion ownership')
    f.check(all(e['owner'] in ('source', plan.hex()) for e in entries), 'cleanup owner')
    prefix = 0
    while prefix < len(delete) and not Path(delete[prefix]).exists():
        prefix += 1
    f.check(all(Path(p).exists() for p in delete[prefix:]), 'cleanup non-prefix deletion')
    for index, name in enumerate(delete):
        f.check(not any(v.startswith(name + '/') for v in delete[index + 1:]), 'cleanup dependency order')
    f.check(delete[-1] == str(operation), 'cleanup coordinator last')
    journal = operation / 'operation.gsr'
    if journal.exists():
        parsed = rows(journal.read_bytes()); tail = parsed[-1]
        if tail['phase'] == 5:
            f.check(len(parsed) > 1 and parsed[-2]['phase'] in (1, 2) and tail['plan'] == plan and tail['previous'] == previous
                    and tail['preparations'] == parsed[-2]['preparations'] and tail['receipt'] == f.ZERO, 'cleanup abort decision')
        else:
            f.check(prefix == 0 and tail['phase'] in (1, 2) and tail['raw'][16:48] == previous, 'cleanup before abort')
    missing = set(delete[:prefix])
    for entry in entries:
        f.exact(entry, 'path kind size digest owner')
        path = Path(entry['path'])
        f.check(path.is_absolute() and str(path) == os_path_normalize(path), 'noncanonical cleanup path')
        if str(path) in missing:
            continue
        f.check(not path.is_symlink(), 'symlink in cleanup inventory')
        if entry['kind'] == 'directory':
            f.check(path.is_dir() and entry['size'] == 0 and entry['digest'] == f.ZERO.hex(), 'cleanup directory changed')
            f.check(all(str(child) in names or child == operation / 'cleanup.gsr' for child in path.iterdir()), 'unknown cleanup member')
        else:
            f.check(entry['kind'] == 'file' and path.is_file() and path.stat().st_nlink == 1, 'cleanup file changed')
            data = path.read_bytes()
            if path == journal and rows(data)[-1]['phase'] == 5:
                data = data[:-len(rows(data)[-1]['raw'])]
            f.check(len(data) == entry['size'] and f.sha(data).hex() == entry['digest'], 'cleanup bytes changed')
    return dict(phase=5, deletedPrefix=prefix, deletionCount=len(delete), planDigest=raw[16:48].hex())


def os_path_normalize(path):
    import os
    return os.path.normpath(str(path))


def replacement(root):
    root = Path(root); operation = files(root / 'replacement-operation')
    raw = operation['replacement-plan.gsr']; r = f.record(raw, 23)
    f.check(r.number('H') == 1, 'replacement version'); receipt = r.blob(f.META)
    descriptor = f.json_value(r.blob(f.META)); inventory = f.inventory(r); r.end()
    f.exact(descriptor, 'operation source configuration manifestDigest genesisDigest sourceInventoryDigest')
    source = files(Path(descriptor['source']['path']))
    f.check(inventory == [(name, 1, len(data), f.sha(data)) for name, data in sorted(source.items())], 'replacement source inventory')
    f.check(descriptor['sourceInventoryDigest'] == f.inventory_digest(inventory).hex(), 'replacement inventory digest')
    g = f.genesis(source['genesis.gsr']); g['raw'] = source['genesis.gsr']; m = f.manifest(source['manifest.gsr'], g)
    rr = f.record(receipt, 19); original_plan = rr.blob(f.META)
    _, payloads = f.plan(original_plan, m, g, source['manifest.gsr']); f.receipt(receipt, original_plan, m, payloads)
    parsed = rows(operation['replacement.gsr']) if 'replacement.gsr' in operation else []
    f.check(len(parsed) <= 2, 'replacement cannot commit a new group')
    for index, row in enumerate(parsed, 1):
        f.check(row['plan'] == raw[16:48] and row['phase'] == index and row['preparations'] == [f.ZERO] * 3 and row['receipt'] == f.ZERO, 'replacement preparation only')
    target = Path(descriptor['configuration']['target']['path']); observed = files(target) if target.exists() else {}
    node = descriptor['configuration']['node']
    if 'node.gsr' in observed:
        r = f.record(observed['node.gsr'], 2); f.check(r.take(32) == m['digest'] and r.text(64) == node and r.number('B') == 1, 'replacement cannot vote'); r.end()
        marker = f.record(observed['rebuilding.gsr'], 13); f.check(marker.take(32) == m['digest'] and marker.text(64) == node, 'replacement rebuilding marker'); marker.end()
    if len(parsed) == 2:
        f.check('node.gsr' in observed and observed['genesis.gsr'] == source['genesis.gsr'] and observed['manifest.gsr'] == source['manifest.gsr'], 'replacement preparation incomplete')
        seal = f.record(observed['bootstrap-seal.gsr'], 20); f.check(seal.text(64) == node and seal.blob(f.META) == receipt, 'replacement completion provenance'); seal.end()
    return dict(phase=parsed[-1]['phase'] if parsed else 0, voter=False, planDigest=raw[16:48].hex())
