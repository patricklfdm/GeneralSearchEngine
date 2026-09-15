"""Read-only independent verifier for sealed 1.1 runtime files and retained proof chains."""
import struct
from pathlib import Path
from . import admission_format as f


def journal(path, kind, m, node, torn=False):
    raw = path.read_bytes(); offset = 0; result = []
    while offset < len(raw):
        if len(raw) - offset < 48:
            f.check(torn and offset > 0, 'incomplete journal header'); break
        length = 48 + struct.unpack_from('>i', raw, offset + 12)[0]
        f.check(48 <= length <= f.IMAGE, 'journal frame bound')
        if length > len(raw) - offset:
            f.check(torn and offset > 0, 'incomplete journal payload'); break
        frame = raw[offset:offset + length]
        r = f.record(frame, kind if offset else 3, f.IMAGE)
        if not offset:
            f.check((r.take(32), r.text(64), r.number('H')) == (m['digest'], node, kind), 'journal identity'); r.end()
        else:
            result.append(frame)
        offset += length
    f.check(offset > 0, 'empty journal')
    return result


def proof(raw, m, anchors):
    r = f.record(raw, 6)
    identity, epoch, incarnation, index, digest, previous = r.take(32), r.number('q'), r.take(16), r.number('q'), r.take(32), r.take(32)
    f.check(identity == m['digest'] and 1 <= index <= len(anchors), 'proof identity/index')
    a = anchors[index - 1]
    f.check((epoch, incarnation, digest, previous) == (a[0], a[1], a[3], a[5]), 'proof ancestry')
    count = r.number('i'); f.check(count in (2, 3), 'proof quorum')
    voters = []
    for _ in range(count):
        voter, receipt = r.text(64), r.take(32)
        f.check(voter in m['nodes'] and receipt == f.sha(f.text('gse-replication/1.1/DURABLE_ACK') + identity + f.text(voter)
                + struct.pack('>q', epoch) + incarnation + struct.pack('>q', index) + digest), 'receipt domain')
        voters.append(voter)
    f.check(voters == sorted(set(voters)), 'duplicate/unordered voters'); r.end()
    return index


def chain(directory, m, g, node, epochs, snapshot=None, torn=False):
    anchors = []; committed = 0
    if snapshot:
        f.snapshot(snapshot, m, g)
        r = f.record(snapshot, 8, f.IMAGE); r.take(48)
        previous = m['digest']
        for _ in range(r.count(1_000_000, 89)):
            a = (r.number('q'), r.take(16), r.number('B'), r.take(32), r.take(32), previous)
            anchors.append(a); previous = a[3]
        terminal, app = r.blob(f.META), r.blob(); r.end()
        committed = len(anchors)
        if terminal: proof(terminal, m, anchors)
    for raw in journal(directory / 'entries.gsr', 5, m, node, torn):
        r = f.record(raw, 5, f.IMAGE)
        identity, epoch, incarnation, index, op = r.take(32), r.number('q'), r.take(16), r.number('q'), r.number('B')
        previous_epoch, previous_index, previous = r.number('q'), r.number('q'), r.take(32)
        size, digest = r.number('i'), r.take(32); payload = r.take(size); r.end()
        f.check(identity == m['digest'] and index == len(anchors) + 1 and previous_index == index - 1 and 1 <= op <= 10, 'entry index/identity')
        f.check(previous == (anchors[-1][3] if anchors else m['digest']) and previous_epoch == (anchors[-1][0] if anchors else 1), 'entry predecessor')
        f.check(epoch >= max(2, previous_epoch) and incarnation != bytes(16) and (epoch > previous_epoch or incarnation == anchors[-1][1]), 'entry incarnation')
        f.check(epochs.get(epoch) == incarnation or snapshot and epoch not in epochs and epoch < max(epochs), 'entry promise')
        f.check(f.sha(payload) == digest and (op <= 8 or not payload), 'entry payload')
        anchors.append((epoch, incarnation, op, raw[16:48], digest, previous))
    for raw in journal(directory / 'proofs.gsr', 6, m, node):
        index = proof(raw, m, anchors); f.check(index > committed, 'proof ledger regresses'); committed = index
    return anchors, committed


def inspect(directory, torn=False):
    directory = Path(directory)
    g = f.genesis((directory / 'genesis.gsr').read_bytes()); g['raw'] = (directory / 'genesis.gsr').read_bytes()
    manifest_raw = (directory / 'manifest.gsr').read_bytes(); m = f.manifest(manifest_raw, g)
    r = f.record((directory / 'node.gsr').read_bytes(), 2)
    f.check(r.take(32) == m['digest'], 'node manifest'); node, origin = r.text(64), r.number('B'); r.end()
    f.check(node in m['nodes'] and origin in (0, 1), 'node origin')
    seal = f.record((directory / 'bootstrap-seal.gsr').read_bytes(), 20)
    f.check(seal.text(64) == node, 'seal node'); receipt = seal.blob(f.META); seal.end()
    plan = f.record(receipt, 19).blob(f.META)
    descriptor, inventories = f.plan(plan, m, g, manifest_raw)
    preparations = f.receipt(receipt, plan, m, inventories)
    f.check((directory / 'bootstrap-prepared.gsr').read_bytes() == preparations[m['nodes'].index(node)], 'local preparation')
    epochs = {}
    for raw in journal(directory / 'promises.gsr', 4, m, node):
        r = f.record(raw, 4); f.check(r.take(32) == m['digest'] and r.text(64) == m['leader'], 'promise identity')
        epoch, incarnation = r.number('q'), r.take(16); r.end()
        f.check(epoch > max(epochs, default=0) and (incarnation == bytes(16)) == (epoch == 1), 'promise order')
        epochs[epoch] = incarnation
    f.check(1 in epochs, 'initial promise missing')
    selected = directory; snap = None; snapshot_index = 0
    if (directory / 'current.gsr').exists():
        r = f.record((directory / 'current.gsr').read_bytes(), 10)
        f.check(r.take(32) == m['digest'] and r.text(64) == node, 'selector identity')
        slot, generation, seal_digest, admitted = r.text(32), r.take(16), r.take(32), r.number('B'); r.end()
        f.check(slot in ('generation-a', 'generation-b') and admitted in (0, 1), 'selector slot')
        selected = directory / slot
        seal_raw = (selected / 'generation.gsr').read_bytes(); f.check(seal_raw[16:48] == seal_digest, 'selector seal')
        r = f.record(seal_raw, 11)
        f.check((r.take(32), r.text(64), r.take(16)) == (m['digest'], node, generation), 'generation identity')
        snap = (selected / 'snapshot.gsr').read_bytes(); f.check(r.take(32) == snap[16:48], 'snapshot digest')
        for name in ('entries.gsr', 'proofs.gsr'): f.check(r.take(32) == (selected / name).read_bytes()[16:48], 'generation journal')
        r.end(); snapshot_index = struct.unpack_from('>i', snap, 96)[0]
    anchors, committed = chain(selected, m, g, node, epochs, snap, torn)
    floor = 0
    if (directory / 'recovery-floor.gsr').exists():
        r = f.record((directory / 'recovery-floor.gsr').read_bytes(), 12)
        f.check(r.take(32) == m['digest'] and r.text(64) == node, 'floor identity')
        floor, digest, count = r.number('q'), r.take(32), r.number('i')
        f.check(0 <= floor <= committed and digest == (anchors[floor-1][3] if floor else m['digest']) and count in (2, 3), 'floor proof')
        voters = [r.text(64) for _ in range(count)]; r.end()
        f.check(voters == sorted(set(voters)) and set(voters) <= set(m['nodes']), 'floor voters')
    return dict(node=node, base=g['base'], sequence=g['base'] + sum(a[2] <= 8 for a in anchors[:committed]),
                lastIndex=len(anchors), committed=committed, snapshotIndex=snapshot_index, floor=floor,
                manifest=m['digest'].hex(), history=g['history'].hex(), anchors=[a[3].hex() for a in anchors], origin=origin)
