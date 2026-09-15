"""Explicit fixture authoring tool. Tests only read frozen bytes; never regenerate them."""
import argparse
import copy
import json
import struct
import uuid
from pathlib import Path
from . import admission_format as f


def number(fmt, *values):
    return struct.pack('>' + fmt, *values)


def path(value):
    return dict(path=value, parentRealPath=str(Path(value).parent), fileStoreName='/dev/fixture',
                fileStoreType='ext4', parentFileKey='(dev=fixture,ino=100)')


def app_bytes(documents):
    descriptors = [f.canonical(dict(analyzer='', field='value', kind='equality')).decode()]
    return number('Hi', 1, len(descriptors)) + b''.join(f.text(v) for v in descriptors) + number('i', len(documents)) + b''.join(
        f.blob(k) + f.blob(v) for k, v in documents)


def make(base, minor=2):
    group = uuid.UUID('11111111-1111-1111-1111-111111111111').bytes
    incarnation = uuid.UUID('22222222-2222-2222-2222-222222222222').bytes
    nodes = ['node-1', 'node-2', 'node-3']
    # Synthetic source members freeze provenance binding, not published V4 decode.
    sources = {} if base == 0 else {name: ('synthetic-v44-' + str(minor) + '-' + name).encode() for name in
                                  ('gse-backup-checkpoint', 'gse-backup-manifest', 'gse-backup-metadata')}
    source_inv = [(name, 1, len(raw), f.sha(raw)) for name, raw in sorted(sources.items())]
    source = (b'\0' + f.text('none') + number('HH', 0, 0) + f.text('none') + bytes(16) + number('q', 0)
              if not sources else b'\1' + f.text('gse-backup') + number('HH', 1, minor) + f.text('canonical-only' if minor == 2 else 'full')
              + uuid.UUID('33333333-3333-3333-3333-333333333333').bytes + number('q', base)) + f.inventory_bytes(source_inv)
    docs = [] if base == 0 else [(number('i', 3), b'3:shared'), (number('i', 1), b'1:shared')]
    app = app_bytes(docs)
    genesis = f.framed(16, number('H', 1) + group + f.blob(source) + f.history(group) + number('q', base) + f.blob(app))
    descriptors = f.application(app)[0]
    manifest = f.framed(1, f.text('gse-replicated') + number('HH', 1, 1) + f.text('gse-replication') + number('HH', 1, 1)
        + group + f.text('config-v1') + number('q', 1) + f.text(nodes[0]) + number('i', 3)
        + b''.join(f.text(node) + f.text('127.0.0.1') + number('iB', 19101 + i, 1) for i, node in enumerate(nodes))
        + f.text('fixture-codec') + number('i', 1) + f.text('fixture-schema') + number('i', 1)
        + f.sha(f.canonical(sorted(descriptors))) + genesis[16:48] + f.history(group) + number('q', base))
    md = manifest[16:48]
    files = {'genesis.gsr': genesis, 'manifest.gsr': manifest}
    files.update({'source/' + name: raw for name, raw in sources.items()})
    inventories = []
    for node in nodes:
        identity = f.framed(2, md + f.text(node) + b'\0')
        headers = [f.framed(3, md + f.text(node) + number('H', k)) for k in (4, 5, 6)]
        promise = f.framed(4, md + f.text(nodes[0]) + number('q', 1) + bytes(16))
        payloads = dict(zip(('promises.gsr', 'entries.gsr', 'proofs.gsr'), (headers[0] + promise, headers[1], headers[2])))
        payloads.update({'manifest.gsr': manifest, 'genesis.gsr': genesis, 'node.gsr': identity, 'replica.lock': b'',
                        'storage-ready.gsr': f.framed(7, md + identity[16:48] + b''.join(h[16:48] for h in headers))})
        inventories.append([(name, 1, len(raw), f.sha(raw)) for name, raw in sorted(payloads.items())])
        files.update({node + '/' + name: raw for name, raw in payloads.items()})
    config = dict(operation=path('/fixture/operation'), source=None if base == 0 else path('/fixture/source'),
        maxSourceBytes=1 << 30, maxOperationBytes=1 << 30,
        application=dict(documentType='example.Document', idField='id', indexes=descriptors,
            fields=[dict(name='id', type='java.lang.Integer'), dict(name='value', type='java.lang.String')], textFields=[],
            snapshot=dict(queueCapacity=31, maxBatchSize=7, maxBatchWaitSeconds=0, maxBatchWaitNanos=1234567), planner='FORCE_SCAN'), replicas=[])
    for node in nodes:
        config['replicas'].append(dict(node=node, target=path('/fixture/' + node),
            materialization=dict(directory=path('/fixture/materialization-' + node),
                format=dict(family='gse-durable', major=1, minor=2), storageIdentity='fixture-store',
                schemaIdentity='fixture-schema', codecId='fixture-codec', codecVersion=1,
                bounds=dict(maxEncodedKeyBytes=1024, maxEncodedDocumentBytes=65536, maxBulkElements=1000,
                    maxDocuments=10000, checkpointWalBytes=1024, maxRetainedBytes=1 << 30, maxDerivedStateBytes=1 << 20)),
            replicationBounds=dict(zip(f.REPLICATION_LIMITS, (8 << 20, 1000, 256, 10000, 12, 5000, 250, 4 << 20, 8 << 30, 16 << 30)))))
    plan = f.framed(17, number('H', 1) + f.blob(f.canonical(config)) + f.blob(manifest) + f.blob(source) + number('q', len(genesis))
                    + b''.join(f.inventory_bytes(inv) for inv in inventories))
    preparations = [f.framed(18, plan[16:48] + md + f.text(node) + f.inventory_digest(inv)) for node, inv in zip(nodes, inventories)]
    receipt = f.framed(19, f.blob(plan) + number('i', 3) + b''.join(f.blob(p) for p in preparations))
    files.update({'plan.gsr': plan, 'receipt.gsr': receipt})
    previous, journal = f.ZERO, b''
    for phase in range(1, 5):
        row = f.framed(21, plan[16:48] + number('q', phase) + previous + bytes([phase]) +
                       b''.join(f.ZERO if phase == 1 else p[16:48] for p in preparations) +
                       (receipt[16:48] if phase == 4 else f.ZERO))
        journal += row
        previous = row[16:48]
    files['operation.gsr'] = journal
    for node, p in zip(nodes, preparations):
        files[node + '/bootstrap-prepared.gsr'] = p
        files[node + '/bootstrap-seal.gsr'] = f.framed(20, f.text(node) + f.blob(receipt))
    files['snapshot-0.gsr'] = f.framed(8, md + number('qqi', base, base, 0) + f.blob(b'') + f.blob(app))
    anchors, previous, previous_epoch, proofs = [], md, 1, []
    # First entry is application work at LogIndex 1, then two control entries.
    for i, op in enumerate((1, 9, 10), 1):
        payload = number('Hi', 1, 1) + f.blob(number('i', 20)) + f.blob(b'20:shared') if op == 1 else b''
        entry = f.framed(5, md + number('q', 2) + incarnation + number('qBqq', i, op, previous_epoch, i - 1)
                        + previous + number('i', len(payload)) + f.sha(payload) + payload)
        ed = entry[16:48]
        proof = f.framed(6, md + number('q', 2) + incarnation + number('q', i) + ed + previous + number('i', 2)
            + b''.join(f.text(node) + f.sha(f.text('gse-replication/1.1/DURABLE_ACK') + md + f.text(node) + number('q', 2)
                                          + incarnation + number('q', i) + ed) for node in nodes[:2]))
        anchors.append(number('q', 2) + incarnation + bytes([op]) + ed + f.sha(payload))
        files['entry-' + str(i) + '.gsr'] = entry
        proofs.append(proof)
        files['snapshot-' + str(i) + '.gsr'] = f.framed(8, md + number('qqi', base, base + 1, i) + b''.join(anchors)
                                                      + f.blob(proof) + f.blob(app_bytes(docs + [(number('i', 20), b'20:shared')])))
        previous, previous_epoch = ed, 2
    files['recovery-image.gsr'] = f.framed(9, f.blob(files['snapshot-3.gsr']) + number('ii', 0, 0))
    # Every registry ID has a common-envelope fixture; payload tables in the spec
    # distinguish request/reply variants. These examples freeze the identity boundary.
    status = dict(promisedEpoch=2, lastLogIndex=3, commitIndex=3, lastDigest=previous.hex(), commitDigest=previous.hex(),
                  appliedIndex=3, snapshotIndex=3, recoveryFloor=0, voter=True, damagedTail=False)
    b64 = lambda v: __import__('base64').b64encode(v).decode()
    tid = '44444444-4444-4444-4444-444444444444'
    payloads = [{}, status, dict(entry=b64(files['entry-1.gsr'])),
        dict(index=1, entryDigest=files['entry-1.gsr'][16:48].hex(), receiptDigest='00' * 32),
        dict(proof=b64(proofs[0])), dict(index=1, proofDigest=proofs[0][16:48].hex()),
        dict(action='ready', index=3, digest=previous.hex()), dict(reason='CONFLICTING_HISTORY'), {},
        dict(transferId=tid, length=len(files['recovery-image.gsr']), digest=f.sha(files['recovery-image.gsr']).hex()),
        dict(transferId=tid, offset=0, data=b64(files['recovery-image.gsr'])), dict(transferId=tid, admit=True),
        dict(recovery=True), status, {}, dict(reason='PROTOCOL_MISMATCH')]
    # Receipt for the APPEND example is bound to its sender's peer, node-2.
    payloads[3]['receiptDigest'] = f.sha(f.text('gse-replication/1.1/DURABLE_ACK') + md + f.text('node-2') + number('q', 2)
                                      + incarnation + number('q', 1) + files['entry-1.gsr'][16:48]).hex()
    for i, (name, payload) in enumerate(zip(f.TYPES, payloads), 1):
        envelope = dict(protocol='gse-replication/1.1', manifestDigest=md.hex(), groupId=str(uuid.UUID(bytes=group)),
            configurationId='config-v1', sender='node-2' if i in (2, 4, 6, 8, 14, 16) else 'node-1',
            recipient='node-1' if i in (2, 4, 6, 8, 14, 16) else 'node-2', epoch=2,
            incarnationId=str(uuid.UUID(bytes=incarnation)), traceId=tid, eventSequence=i, type=name, payload=payload)
        files['wire-%02d.gsrp' % i] = f.framed(i, f.canonical(envelope), b'GSRP')
    # Administrative record projections use a pre-commit fork of this same plan.
    rowsize = len(journal) // 4
    tail = journal[rowsize:rowsize * 2][16:48]
    abort = f.framed(21, plan[16:48] + number('q', 3) + tail + b'\x05'
                     + b''.join(p[16:48] for p in preparations) + f.ZERO)
    files['admin-aborting.gsr'] = abort
    cleanup_inventory = []
    for node, inv in zip(nodes, inventories):
        cleanup_inventory.append(dict(path='/fixture/' + node, kind='directory', size=0, digest='00' * 32, owner=plan[16:48].hex()))
        for name, kind, size, digest in inv:
            cleanup_inventory.append(dict(path='/fixture/' + node + '/' + name, kind='file', size=size,
                                          digest=digest.hex(), owner=plan[16:48].hex()))
        prepared = files[node + '/bootstrap-prepared.gsr']
        cleanup_inventory.append(dict(path='/fixture/' + node + '/bootstrap-prepared.gsr', kind='file', size=len(prepared),
                                      digest=f.sha(prepared).hex(), owner=plan[16:48].hex()))
    cleanup_inventory.append(dict(path='/fixture/operation', kind='directory', size=0, digest='00' * 32, owner=plan[16:48].hex()))
    for name, raw in [('operation.lock', b''), ('plan.gsr', plan), ('operation.gsr', journal[:rowsize * 2])]:
        cleanup_inventory.append(dict(path='/fixture/operation/' + name, kind='file', size=len(raw), digest=f.sha(raw).hex(), owner=plan[16:48].hex()))
    if sources:
        cleanup_inventory.append(dict(path='/fixture/source', kind='directory', size=0, digest='00' * 32, owner='source'))
        for name, raw in sources.items():
            cleanup_inventory.append(dict(path='/fixture/source/' + name, kind='file', size=len(raw), digest=f.sha(raw).hex(), owner='source'))
    cleanup_inventory.sort(key=lambda v: v['path'].encode())
    delete = sorted([v['path'] for v in cleanup_inventory if v['owner'] != 'source'], key=lambda v: (-v.count('/'), v.encode()))
    # Persisted plan/journal/owner and operation directory are removed last.
    final = ['/fixture/operation/' + n for n in ('plan.gsr', 'operation.gsr', 'operation.lock')] + ['/fixture/operation']
    delete = [v for v in delete if v not in final] + final
    files['admin-cleanup.gsr'] = f.framed(22, plan[16:48] + tail + f.blob(f.canonical(dict(
        operation=config['operation'], inventory=cleanup_inventory, deletePaths=delete))))
    replacement_inv = [(name, 1, len(raw), f.sha(raw)) for name, raw in sorted(
        (k.removeprefix('node-2/'), v) for k, v in files.items() if k.startswith('node-2/'))]
    replacement_config = copy.deepcopy(config['replicas'][0])
    replacement_config['target'] = path('/fixture/replacement-node-1')
    replacement_desc = dict(operation=path('/fixture/replacement-operation'), source=path('/fixture/node-2'),
        configuration=replacement_config, manifestDigest=md.hex(), genesisDigest=genesis[16:48].hex(),
        sourceInventoryDigest=f.inventory_digest(replacement_inv).hex())
    replacement = f.framed(23, number('H', 1) + f.blob(receipt) + f.blob(f.canonical(replacement_desc)) + f.inventory_bytes(replacement_inv))
    files['admin-replacement-plan.gsr'] = replacement
    first = f.framed(21, replacement[16:48] + number('q', 1) + f.ZERO + b'\x01' + f.ZERO * 4)
    second = f.framed(21, replacement[16:48] + number('q', 2) + first[16:48] + b'\x02' + f.ZERO * 4)
    files['admin-replacement-journal.gsr'] = first + second
    files['admin-replacement-node.gsr'] = f.framed(2, md + f.text('node-1') + b'\x01')
    files['admin-rebuilding.gsr'] = f.framed(13, md + f.text('node-1'))
    return files


def generate():
    bases = {'empty': make(0), **{'import-v1' + str(minor): make(41, minor) for minor in range(3)},
             'near-overflow': make(f.LONG_MAX - 1)}
    cases = [dict(name=name, base=name, valid=True, expected=f.validate(files)) for name, files in bases.items()]
    base = bases['import-v12']

    def bad(name, file, raw, selected='import-v12'):
        cases.append(dict(name=name, base=selected, valid=False, replace={file: None if raw is None else raw.hex()}))

    def reframe(file, body):
        raw = base[file]
        return f.framed(struct.unpack_from('>H', raw, 8)[0], body, raw[:4])

    raw = base['genesis.gsr']
    bad('genesis-checksum', 'genesis.gsr', raw[:-1] + bytes([raw[-1] ^ 1]))
    bad('genesis-truncated', 'genesis.gsr', raw[:-1])
    bad('genesis-trailing', 'genesis.gsr', raw + b'\0')
    bad('legacy-genesis-version', 'genesis.gsr', f.framed(16, raw[48:], minor=0))
    body = bytearray(raw[48:]); body[0:2] = number('H', 2)
    bad('genesis-projection-version', 'genesis.gsr', f.framed(16, body))
    body = bytearray(raw[48:]); source_size = struct.unpack_from('>i', body, 18)[0]
    history_offset = 22 + source_size
    body[history_offset:history_offset + 16] = bytes(16)
    bad('genesis-history-derivation', 'genesis.gsr', f.framed(16, body))
    body = bytearray(raw[48:]); body[history_offset + 16:history_offset + 24] = number('q', f.LONG_MAX)
    bad('genesis-sequence-overflow', 'genesis.gsr', f.framed(16, body))
    body = bytearray(base['manifest.gsr'][48:]); body[-56] ^= 1
    bad('manifest-other-genesis', 'manifest.gsr', f.framed(1, body))
    bad('missing-local-seal', 'node-2/bootstrap-seal.gsr', None)
    bad('seal-wrong-node', 'node-2/bootstrap-seal.gsr', base['node-1/bootstrap-seal.gsr'])
    bad('local-preparation-wrong-node', 'node-2/bootstrap-prepared.gsr', base['node-1/bootstrap-prepared.gsr'])
    bad('source-bytes-changed', 'source/gse-backup-checkpoint', b'changed')
    bad('local-payload-changed', 'node-3/genesis.gsr', b'changed')
    bad('old-unsealed-store', 'node-1/bootstrap-seal.gsr', None, 'empty')
    journal = base['operation.gsr']; row_size = len(journal) // 4
    bad('seal-before-decision', 'operation.gsr', journal[:row_size * 2])
    bad('ambiguous-committing', 'operation.gsr', journal[:row_size * 3])
    bad('journal-torn-tail', 'operation.gsr', journal[:-1])
    body = bytearray(journal[-row_size + 48:]); body[40] ^= 1
    bad('journal-broken-chain', 'operation.gsr', journal[:-row_size] + f.framed(21, body))
    receipt = base['receipt.gsr']; r = f.Reader(receipt[48:]); plan = r.blob(); r.number('i')
    ps = [r.blob() for _ in range(3)]
    bad('receipt-duplicate-preparation', 'receipt.gsr', f.framed(19, f.blob(plan) + number('i', 3) + b''.join(f.blob(v) for v in (ps[0], ps[0], ps[2]))))
    body = bytearray(ps[0][48:]); body[-1] ^= 1
    bad('receipt-inventory-binding', 'receipt.gsr', f.framed(19, f.blob(plan) + number('i', 3) + f.blob(f.framed(18, body)) + b''.join(f.blob(v) for v in ps[1:])))
    for name, offset, value in [('snapshot-false-base', 32, 40), ('snapshot-false-sequence', 40, 99)]:
        body = bytearray(base['snapshot-3.gsr'][48:]); body[offset:offset + 8] = number('q', value)
        bad(name, 'snapshot-3.gsr', f.framed(8, body))
    body = bytearray(base['snapshot-3.gsr'][48:]); body[52 + 89 + 24] = 1
    bad('control-counted-as-application', 'snapshot-3.gsr', f.framed(8, body))
    body = bytearray(base['snapshot-3.gsr'][48:]); body[52 + 2 * 89 + 25] ^= 1
    bad('conflicting-terminal-proof', 'snapshot-3.gsr', f.framed(8, body))
    body = bytearray(base['snapshot-0.gsr'][48:]); body[-1] ^= 1
    bad('index-zero-must-load-genesis', 'snapshot-0.gsr', f.framed(8, body))
    # Re-signed malformed lengths/UTF-8 exercise field admission after frame checks.
    body = bytearray(raw[48:]); body[18:22] = number('i', 2147483647)
    bad('oversized-source-descriptor', 'genesis.gsr', f.framed(16, body))
    for name, edit in [('stale-inlined-protocol', lambda v: v.update(protocol='gse-replication/1.0')),
                       ('same-group-other-genesis-wire', lambda v: v.update(manifestDigest='ab' * 32)),
                       ('wire-missing-manifest', lambda v: v.pop('manifestDigest')),
                       ('wire-unknown-field', lambda v: v.update(extra=1)),
                       ('wire-wrong-recipient', lambda v: v.update(recipient='node-4'))]:
        value = json.loads(base['wire-01.gsrp'][48:]); edit(value)
        bad(name, 'wire-01.gsrp', f.framed(1, f.canonical(value), b'GSRP'))
    bad('wire-legacy-header', 'wire-01.gsrp', f.framed(1, base['wire-01.gsrp'][48:], b'GSRP', 0))
    bad('wire-noncanonical-json', 'wire-01.gsrp', f.framed(1, b' ' + base['wire-01.gsrp'][48:], b'GSRP'))
    # Fully reframe plan while leaving receipt binding old: stale caller projection.
    r = f.Reader(base['plan.gsr'][48:]); r.number('H'); desc = json.loads(r.blob()); tail = r.raw[r.pos:]
    for name, mutate in [('plan-changed-bound', lambda v: v.update(maxSourceBytes=0)),
                         ('plan-local-order', lambda v: v['replicas'].reverse()),
                         ('plan-path-overlap', lambda v: v['operation'].update(path=v['replicas'][0]['target']['path'])),
                         ('plan-codec-mismatch', lambda v: v['replicas'][2]['materialization'].update(codecVersion=2))]:
        changed = copy.deepcopy(desc); mutate(changed)
        bad(name, 'plan.gsr', f.framed(17, number('H', 1) + f.blob(f.canonical(changed)) + tail))
    bad('legacy-storage-manifest', 'manifest.gsr', f.framed(1, base['manifest.gsr'][48:], minor=0))
    # Locate source history from its exact scalar fields, independently of inventory length.
    r = f.Reader(base['genesis.gsr'][48:]); r.number('H'); r.take(16); src = bytearray(r.blob()); sr = f.Reader(src)
    sr.number('B'); sr.text(); sr.number('H'); sr.number('H'); sr.text()
    src[sr.pos:sr.pos + 16] = f.history(uuid.UUID('11111111-1111-1111-1111-111111111111').bytes)
    bad('source-history-collision', 'genesis.gsr', f.framed(16, number('H', 1) + base['genesis.gsr'][50:66] + f.blob(src) + r.raw[r.pos:]))
    near = bases['near-overflow']['snapshot-3.gsr']
    body = bytearray(near[48:]); body[52 + 89 + 24] = 1
    bad('snapshot-arithmetic-overflow', 'snapshot-3.gsr', f.framed(8, body), 'near-overflow')
    envelope = json.loads(base['wire-03.gsrp'][48:])
    envelope['payload']['entry'] = __import__('base64').b64encode(f.framed(5, base['entry-1.gsr'][48:], minor=0)).decode()
    bad('wire-embedded-legacy-entry', 'wire-03.gsrp', f.framed(3, f.canonical(envelope), b'GSRP'))
    envelope = json.loads(base['wire-13.gsrp'][48:]); envelope['payload']['recovery'] = False
    bad('wire-activation-without-recovery', 'wire-13.gsrp', f.framed(13, f.canonical(envelope), b'GSRP'))
    envelope = json.loads(base['wire-11.gsrp'][48:]); envelope['payload']['offset'] = -1
    bad('wire-negative-chunk-offset', 'wire-11.gsrp', f.framed(11, f.canonical(envelope), b'GSRP'))
    r = f.Reader(base['admin-cleanup.gsr'][48:]); prefix = r.take(64); cleanup = json.loads(r.blob())
    cleanup['deletePaths'].insert(0, '/fixture/source/gse-backup-checkpoint')
    bad('cleanup-protected-source', 'admin-cleanup.gsr', f.framed(22, prefix + f.blob(f.canonical(cleanup))))
    body = bytearray(base['admin-aborting.gsr'][48:]); body[40:72] = base['operation.gsr'][-row_size:][16:48]
    bad('cleanup-after-committed', 'admin-aborting.gsr', f.framed(21, body))
    body = bytearray(base['admin-replacement-plan.gsr'][48:]); body[-1] ^= 1
    bad('replacement-source-inventory', 'admin-replacement-plan.gsr', f.framed(23, body))
    bad('replacement-must-be-nonvoter', 'admin-replacement-node.gsr', base['node-1/node.gsr'])
    body = bytearray(base['admin-replacement-journal.gsr'][48:row_size]); body[72] = 4
    bad('replacement-cannot-commit-group', 'admin-replacement-journal.gsr', f.framed(21, body))
    return dict(schema='gse-v50-admission-fixtures-v2', bases={name: {p: raw.hex() for p, raw in sorted(files.items())}
                                                           for name, files in bases.items()}, cases=cases)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(generate(), indent=2, sort_keys=True) + '\n')
