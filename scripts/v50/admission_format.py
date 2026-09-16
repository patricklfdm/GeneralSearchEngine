"""Independent, read-only 1.1 admission byte oracle (stdlib; no product decoder).

This checks frozen format projections, not filesystem force or typed V4 semantics.
Actual Step B output is checked separately by offline_format; runtime admission is Step C.
"""
import base64
import hashlib
import json
import re
import struct
import uuid
from pathlib import Path

META = 65536
IMAGE = 64 * 1024 * 1024
LIMIT = 1 << 40
LONG_MAX = (1 << 63) - 1
ZERO = bytes(32)
TYPES = ('HANDSHAKE', 'ACTIVATION_PROMISE', 'APPEND', 'DURABLE_ACK', 'COMMIT_PROOF',
         'COMMIT_PROOF_ACK', 'COMMIT_ADVANCE', 'CONFLICT', 'AUTHORITY_STATUS_PROBE',
         'SNAPSHOT_OFFER', 'SNAPSHOT_CHUNK', 'SNAPSHOT_INSTALL', 'ACTIVATE_EPOCH',
         'AUTHORITY_STATUS', 'SNAPSHOT_ABORT', 'REJECT')
ROOT_FILES = ('entries.gsr', 'genesis.gsr', 'manifest.gsr', 'node.gsr', 'promises.gsr',
              'proofs.gsr', 'replica.lock', 'storage-ready.gsr')


def check(value, message):
    if not value:
        raise ValueError(message)


def sha(value):
    return hashlib.sha256(value).digest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def json_value(raw):
    def bounded(value, depth=0):
        check(depth <= 16, 'JSON depth')
        if value is None or type(value) in (str, bool):
            return
        if type(value) is int:
            check(-LONG_MAX - 1 <= value <= LONG_MAX, 'JSON integer')
        elif isinstance(value, list):
            for item in value:
                bounded(item, depth + 1)
        elif isinstance(value, dict):
            check(all(re.fullmatch('[A-Za-z][A-Za-z0-9_]*', key) for key in value), 'JSON keys')
            for item in value.values():
                bounded(item, depth + 1)
        else:
            raise ValueError('JSON type')
    value = json.loads(raw)
    bounded(value)
    check(canonical(value) == raw, 'noncanonical JSON')
    return value


def text(value):
    raw = value.encode('utf-8')
    return struct.pack('>i', len(raw)) + raw


def blob(value):
    return struct.pack('>i', len(value)) + value


def framed(kind, body, magic=b'GSER', minor=1):
    prefix = struct.pack('>4sHHHHi', magic, 1, minor, kind, 0, len(body))
    return prefix + sha(prefix + body) + body


def record(raw, kind, maximum=META, magic=b'GSER'):
    check(48 < len(raw) <= maximum, 'frame size')
    family, major, minor, actual, flags, size = struct.unpack('>4sHHHHi', raw[:16])
    check((family, major, minor) == (magic, 1, 1), 'version')
    check(actual == kind and flags == 0, 'kind/flags')
    check(size == len(raw) - 48, 'frame length')
    check(sha(raw[:16] + raw[48:]) == raw[16:48], 'frame digest')
    return Reader(raw[48:])


class Reader:
    def __init__(self, raw):
        self.raw, self.pos = raw, 0

    def take(self, size):
        check(0 <= size <= len(self.raw) - self.pos, 'truncated field')
        value = self.raw[self.pos:self.pos + size]
        self.pos += size
        return value

    def number(self, fmt):
        return struct.unpack('>' + fmt, self.take(struct.calcsize('>' + fmt)))[0]

    def blob(self, maximum=IMAGE):
        size = self.number('i')
        check(0 <= size <= maximum, 'blob bound')
        return self.take(size)

    def text(self, maximum=4096, empty=False):
        raw = self.blob(maximum)
        check(empty or raw, 'empty text')
        return raw.decode('utf-8', 'strict')

    def count(self, maximum, minimum=1):
        count = self.number('i')
        check(0 <= count <= maximum and count <= (len(self.raw) - self.pos) // minimum, 'count bound')
        return count

    def end(self):
        check(self.pos == len(self.raw), 'trailing fields')


def ident(value, maximum=128):
    check(isinstance(value, str) and re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,%d}' % (maximum - 1), value), 'identity')
    return value


def history(group):
    result = sha(b'gse-v50-application-history-v1\0' + group)[:16]
    check(result != bytes(16), 'zero application history')
    return result


def inventory(reader):
    entries = []
    for _ in range(reader.count(10000, 45)):
        name, kind, size, digest = reader.text(), reader.number('B'), reader.number('q'), reader.take(32)
        check(not name.startswith('/') and all(p not in ('', '.', '..') for p in name.split('/'))
              and '\\' not in name and '\0' not in name, 'inventory path')
        check(kind in (0, 1) and 0 <= size <= LIMIT, 'inventory kind/size')
        check(kind != 0 or (size == 0 and digest == ZERO), 'directory inventory')
        entries.append((name, kind, size, digest))
    names = [e[0] for e in entries]
    check(names == sorted(set(names), key=lambda v: v.encode('utf-8')), 'inventory order')
    return entries


def inventory_bytes(entries):
    return struct.pack('>i', len(entries)) + b''.join(text(n) + struct.pack('>Bq', k, s) + h for n, k, s, h in entries)


def inventory_digest(entries):
    return sha(b'gse-v50-payload-inventory-v1\0' + inventory_bytes(entries))


def source(reader):
    kind = reader.number('B')
    family, major, minor, profile = reader.text(32), reader.number('H'), reader.number('H'), reader.text(32)
    source_history, sequence = reader.take(16), reader.number('q')
    entries = inventory(reader)
    check(kind in (0, 1), 'source kind')
    if kind == 0:
        check((family, major, minor, profile, source_history, sequence, entries) ==
              ('none', 0, 0, 'none', bytes(16), 0, []), 'empty source')
    else:
        check(family == 'gse-backup' and major == 1 and minor in (0, 1, 2), 'source version')
        check(profile == ('canonical-only' if minor == 2 else 'full'), 'source profile')
        check(source_history != bytes(16) and 0 <= sequence < LONG_MAX, 'source history/sequence')
        check([e[0] for e in entries] == ['gse-backup-checkpoint', 'gse-backup-manifest', 'gse-backup-metadata']
              and all(e[1] == 1 and e[2] > 0 for e in entries), 'source inventory')
    return kind, source_history, sequence, entries


def application(raw):
    r = Reader(raw)
    check(r.number('H') == 1, 'application version')
    descriptors = [r.text(8192) for _ in range(r.count(10000, 4))]
    fields = []
    for descriptor in descriptors:
        d = json_value(descriptor.encode('utf-8'))
        check(set(d) == {'analyzer', 'field', 'kind'} and isinstance(d['field'], str)
              and 0 < len(d['field'].encode('utf-8')) <= 1024, 'index descriptor')
        check(d['kind'] in ('equality', 'range', 'prefix', 'text') and
              d['analyzer'] == ('gse-simple-v1' if d['kind'] == 'text' else ''), 'index kind/analyzer')
        fields.append(d['field'])
    check(fields == sorted(set(fields), key=lambda v: v.encode('utf-16-be')), 'index order')
    documents = [(r.blob(), r.blob()) for _ in range(r.count(100_000_000, 8))]
    check(len({k for k, _ in documents}) == len(documents), 'duplicate key')
    r.end()
    return descriptors, documents


def genesis(raw):
    r = record(raw, 16, IMAGE)
    check(r.number('H') == 1, 'genesis projection version')
    group = r.take(16)
    check(group != bytes(16), 'zero group')
    src_raw = r.blob(META)
    sr = Reader(src_raw)
    src = source(sr)
    sr.end()
    app_history, base, app = r.take(16), r.number('q'), r.blob()
    r.end()
    check(app_history == history(group) and app_history != src[1], 'application history')
    check(0 <= base < LONG_MAX and base == src[2], 'base sequence')
    indexes, documents = application(app)
    check(src[0] != 0 or not documents, 'empty genesis documents')
    return {'group': group, 'source': src_raw, 'history': app_history, 'base': base,
            'app': app, 'indexes': indexes, 'documents': documents, 'digest': raw[16:48]}


def manifest(raw, g):
    r = record(raw, 1)
    check((r.text(32), r.number('H'), r.number('H'), r.text(32), r.number('H'), r.number('H')) ==
          ('gse-replicated', 1, 1, 'gse-replication', 1, 1), 'manifest version')
    group, configuration, epoch, leader = r.take(16), ident(r.text(128)), r.number('q'), ident(r.text(64), 64)
    check(r.number('i') == 3, 'voter count')
    members = []
    for _ in range(3):
        node, host, port, voter = ident(r.text(64), 64), r.text(1012), r.number('i'), r.number('B')
        check(host.strip() == host and host and len(host.encode('utf-16-be')) <= 506 and 1 <= port <= 65535 and voter == 1, 'endpoint/voter')
        members.append((node, host, port))
    codec, cv, schema, sv, indexes = ident(r.text(128)), r.number('i'), ident(r.text(128)), r.number('i'), r.take(32)
    genesis_digest, app_history, base = r.take(32), r.take(16), r.number('q')
    r.end()
    nodes = [m[0] for m in members]
    check(len(set(nodes)) == 3 and len(set((h, p) for _, h, p in members)) == 3 and leader in nodes, 'members')
    check(group == g['group'] and epoch == 1 and cv > 0 and sv == 1, 'manifest identity')
    # Same domain as the historical application descriptor: canonical descriptor array.
    expected_indexes = sha(canonical(sorted(g['indexes'])))
    check(indexes == expected_indexes and genesis_digest == g['digest'] and app_history == g['history']
          and base == g['base'], 'manifest genesis binding')
    return {'digest': raw[16:48], 'nodes': nodes, 'members': members, 'group': group,
            'configuration': configuration, 'leader': leader, 'codec': codec, 'codecVersion': cv,
            'schema': schema, 'base': base, 'history': app_history}


def exact(value, keys):
    check(isinstance(value, dict) and set(value) == set(keys.split()), 'descriptor fields')


def path_binding(value):
    exact(value, 'path parentRealPath fileStoreName fileStoreType parentFileKey')
    check(all(isinstance(v, str) and v and len(v.encode('utf-8')) <= 4096 and '\0' not in v for v in value.values()), 'path binding')
    for key in ('path', 'parentRealPath'):
        v = value[key]
        check(v.startswith('/') and (v == '/' or all(p not in ('', '.', '..') for p in v[1:].split('/'))), 'normalized path')


def positive_fields(value, maxima):
    exact(value, ' '.join(maxima))
    for key, maximum in maxima.items():
        check(type(value[key]) is int and 1 <= value[key] <= maximum, 'configuration bound: ' + key)


REPLICATION_LIMITS = dict(zip(('maxFrameBytes', 'maxEntriesPerAppend', 'maxInFlightPerPeer',
    'maxPendingClientOperations', 'maxRetryAttempts', 'requestTimeoutMillis', 'retryBackoffMillis',
    'snapshotChunkBytes', 'maxRetainedLogBytes', 'maxSnapshotStagingBytes'),
    (IMAGE, 10000, 4096, 100000, 100, 300000, 60000, IMAGE, LIMIT, LIMIT)))
MATERIALIZATION_LIMITS = dict(zip(('maxEncodedKeyBytes', 'maxEncodedDocumentBytes', 'maxBulkElements',
    'maxDocuments', 'checkpointWalBytes', 'maxRetainedBytes', 'maxDerivedStateBytes'),
    (IMAGE, 4 * IMAGE, 1_000_000, 100_000_000, LIMIT, 16 * LIMIT, 8 * LIMIT)))


def plan(raw, m, g, manifest_raw):
    r = record(raw, 17)
    check(r.number('H') == 1, 'plan version')
    desc = json_value(r.blob(META))
    embedded_manifest, src = r.blob(META), r.blob(META)
    length = r.number('q')
    check(embedded_manifest == manifest_raw and src == g['source'] and length == len(g['raw']), 'plan source/manifest')
    exact(desc, 'operation source maxSourceBytes maxOperationBytes application replicas')
    path_binding(desc['operation'])
    if desc['source'] is not None:
        path_binding(desc['source'])
    check((desc['source'] is None) == (g['source'][0] == 0), 'source path kind')
    check(type(desc['maxSourceBytes']) is int and 1 <= desc['maxSourceBytes'] <= LIMIT
          and type(desc['maxOperationBytes']) is int and 1 <= desc['maxOperationBytes'] <= LIMIT, 'operation bound')
    app = desc['application']
    exact(app, 'documentType idField fields textFields indexes snapshot planner')
    check(isinstance(app['indexes'], list) and all(isinstance(v, str) for v in app['indexes'])
          and len(app['indexes']) == len(g['indexes']) and set(app['indexes']) == set(g['indexes']), 'builder index configuration')
    check(isinstance(app['documentType'], str) and app['documentType'] and isinstance(app['idField'], str), 'schema descriptor')
    check(isinstance(app['fields'], list) and 1 <= len(app['fields']) <= 10000, 'schema fields')
    for field in app['fields']:
        exact(field, 'name type')
        check(all(isinstance(v, str) and v for v in field.values()), 'schema field')
    names = [f['name'] for f in app['fields']]
    check(names == sorted(set(names), key=lambda v: v.encode('utf-16-be')) and app['idField'] in names, 'schema field order')
    check(isinstance(app['textFields'], list) and len(app['textFields']) <= 10000, 'text fields')
    for field in app['textFields']:
        exact(field, 'field analyzer')
        check(field['field'] in names and field['analyzer'] == 'gse-simple-v1', 'text field')
    tnames = [f['field'] for f in app['textFields']]
    check(tnames == sorted(set(tnames), key=lambda v: v.encode('utf-16-be')), 'text field order')
    exact(app['snapshot'], 'queueCapacity maxBatchSize maxBatchWaitSeconds maxBatchWaitNanos')
    q = app['snapshot']
    check(all(type(v) is int for v in q.values()) and 0 < q['queueCapacity'] <= 2147483647 and
          0 < q['maxBatchSize'] <= 2147483647 and 0 <= q['maxBatchWaitSeconds'] <= LONG_MAX and
          0 <= q['maxBatchWaitNanos'] <= 999999999, 'snapshot config')
    check(app['planner'] in ('COST_AWARE', 'FORCE_INDEX', 'FORCE_SCAN'), 'planner config')
    check(isinstance(desc['replicas'], list) and len(desc['replicas']) == 3, 'local configuration count')
    paths = [desc['operation']['path']] + ([] if desc['source'] is None else [desc['source']['path']])
    inventories = []
    for node, local in zip(m['nodes'], desc['replicas']):
        exact(local, 'node target materialization replicationBounds')
        check(local['node'] == node, 'local configuration order')
        path_binding(local['target'])
        mat = local['materialization']
        exact(mat, 'directory format storageIdentity schemaIdentity codecId codecVersion bounds')
        path_binding(mat['directory'])
        exact(mat['format'], 'family major minor')
        check(mat['format']['family'] == 'gse-durable' and mat['format']['major'] == 1 and
              mat['format']['minor'] in (0, 1, 2), 'materialization format')
        ident(mat['storageIdentity'])
        check(mat['schemaIdentity'] == m['schema'] and mat['codecId'] == m['codec'] and
              mat['codecVersion'] == m['codecVersion'], 'local application identity')
        positive_fields(mat['bounds'], MATERIALIZATION_LIMITS)
        check(mat['bounds']['maxRetainedBytes'] > mat['bounds']['checkpointWalBytes'], 'local retained bound')
        if mat['format']['minor'] == 2:
            check(mat['bounds']['maxDerivedStateBytes'] <= mat['bounds']['maxRetainedBytes'], 'derived bound')
        positive_fields(local['replicationBounds'], REPLICATION_LIMITS)
        check(length <= min(IMAGE, local['replicationBounds']['maxSnapshotStagingBytes']), 'genesis capacity')
        paths += [local['target']['path'], mat['directory']['path']]
        inv = inventory(r)
        check([v[0] for v in inv] == list(ROOT_FILES) and all(v[1] == 1 for v in inv), 'planned root inventory')
        inventories.append(inv)
    r.end()
    for i, a in enumerate(paths):
        check(all(a != b and not a.startswith(b.rstrip('/') + '/') and not b.startswith(a.rstrip('/') + '/')
                  for b in paths[i + 1:]), 'path overlap')
    mats = [v['materialization'] for v in desc['replicas']]
    check(all((v['storageIdentity'], v['format']) == (mats[0]['storageIdentity'], mats[0]['format']) for v in mats), 'materialization agreement')
    return desc, inventories


def receipt(raw, plan_raw, m, inventories):
    r = record(raw, 19)
    check(r.blob(META) == plan_raw and r.number('i') == 3, 'receipt plan/count')
    preparations = []
    for node, inv in zip(m['nodes'], inventories):
        prepared = r.blob(META)
        p = record(prepared, 18)
        check(p.take(32) == plan_raw[16:48] and p.take(32) == m['digest'] and p.text(64) == node
              and p.take(32) == inventory_digest(inv), 'preparation binding')
        p.end()
        preparations.append(prepared)
    r.end()
    return preparations


def snapshot(raw, m, g):
    r = record(raw, 8, IMAGE)
    check(r.take(32) == m['digest'] and r.number('q') == g['base'], 'snapshot base/manifest')
    claimed = r.number('q')
    anchors, previous_epoch, previous_incarnation, previous = [], 1, bytes(16), m['digest']
    count = r.count(1_000_000, 89)
    for index in range(1, count + 1):
        epoch, incarnation, op, digest, payload = r.number('q'), r.take(16), r.number('B'), r.take(32), r.take(32)
        check(epoch >= max(2, previous_epoch) and incarnation != bytes(16) and
              (epoch > previous_epoch or incarnation == previous_incarnation) and 1 <= op <= 10, 'snapshot ancestry')
        anchors.append((epoch, incarnation, op, digest, payload, previous))
        previous_epoch, previous_incarnation, previous = epoch, incarnation, digest
    proof, app = r.blob(META), r.blob()
    r.end()
    sequence = g['base'] + sum(a[2] <= 8 for a in anchors)
    check(sequence <= LONG_MAX and claimed == sequence, 'snapshot sequence')
    check(bool(proof) == bool(anchors), 'snapshot proof presence')
    if anchors:
        p = record(proof, 6)
        epoch, incarnation, _, digest, _, prev = anchors[-1]
        check(p.take(32) == m['digest'] and p.number('q') == epoch and p.take(16) == incarnation and
              p.number('q') == count and p.take(32) == digest and p.take(32) == prev, 'snapshot terminal proof')
        n = p.number('i')
        check(n in (2, 3), 'proof quorum')
        voters = []
        for _ in range(n):
            voter, actual = p.text(64), p.take(32)
            expected = sha(text('gse-replication/1.1/DURABLE_ACK') + m['digest'] + text(voter) +
                           struct.pack('>q', epoch) + incarnation + struct.pack('>q', count) + digest)
            check(voter in m['nodes'] and actual == expected, 'proof receipt')
            voters.append(voter)
        check(voters == sorted(set(voters)), 'proof voter order')
        p.end()
    application(app)
    check(anchors or app == g['app'], 'index-zero genesis state')
    return sequence


def wire(raw, m):
    check(len(raw) >= 48, 'wire header')
    kind = struct.unpack('>H', raw[8:10])[0]
    check(1 <= kind <= 16, 'wire kind')
    r = record(raw, kind, IMAGE, b'GSRP')
    value = json_value(r.raw)
    exact(value, 'protocol manifestDigest groupId configurationId sender recipient epoch incarnationId traceId eventSequence type payload')
    check(value['protocol'] == 'gse-replication/1.1' and value['type'] == TYPES[kind - 1], 'wire version/type')
    check(value['manifestDigest'] == m['digest'].hex() and value['groupId'] == str(uuid.UUID(bytes=m['group']))
          and value['configurationId'] == m['configuration'], 'wire manifest binding')
    check(value['sender'] in m['nodes'] and value['recipient'] in m['nodes'] and value['sender'] != value['recipient'], 'wire members')
    for name in ('groupId', 'incarnationId', 'traceId'):
        check(str(uuid.UUID(value[name])) == value[name], 'wire UUID')
    check(type(value['epoch']) is int and value['epoch'] >= 0 and type(value['eventSequence']) is int
          and value['eventSequence'] >= 0, 'wire counters')
    check(value['epoch'] != 0 or kind in (1, 16), 'zero wire epoch')
    check(isinstance(value['payload'], dict) and 'manifestDigest' not in value['payload'], 'wire payload identity location')
    payload = value['payload']
    status = 'promisedEpoch lastLogIndex commitIndex lastDigest commitDigest appliedIndex snapshotIndex recoveryFloor voter damagedTail'
    alternatives = {
        1: [''], 2: [status], 3: ['entry'], 4: ['index entryDigest receiptDigest'],
        5: ['proof'], 6: ['index proofDigest'],
        7: ['action index digest', 'action index digest voters', 'action entries proofs', status],
        8: ['reason'], 9: ['', 'action', 'action transferId offset length'],
        10: ['transferId length digest', 'transferId'], 11: ['transferId offset data', 'transferId offset'],
        12: ['transferId admit', 'transferId imageDigest index digest snapshotIndex'],
        13: ['recovery'], 14: [status, 'transferId length digest', 'transferId offset data'],
        15: [''], 16: ['reason']}
    check(any(set(payload) == set(keys.split()) for keys in alternatives[kind]), 'wire payload fields')
    for key in ('index', 'offset', 'length', 'promisedEpoch', 'lastLogIndex', 'commitIndex', 'appliedIndex', 'snapshotIndex', 'recoveryFloor'):
        if key in payload:
            check(type(payload[key]) is int and payload[key] >= 0, 'wire payload counter')
    for key in ('digest', 'entryDigest', 'receiptDigest', 'proofDigest', 'imageDigest', 'lastDigest', 'commitDigest'):
        if key in payload:
            check(isinstance(payload[key], str) and re.fullmatch('[0-9a-f]{64}', payload[key]), 'wire payload digest')
    for key in ('admit', 'voter', 'damagedTail', 'recovery'):
        if key in payload:
            check(type(payload[key]) is bool, 'wire payload boolean')
    if 'transferId' in payload:
        check(str(uuid.UUID(payload['transferId'])) == payload['transferId'], 'transfer UUID')
    if kind == 13:
        check(payload['recovery'] is True, 'activation recovery')
    if 'action' in payload:
        allowed = {'ready': 'action index digest', 'floor': 'action index digest voters', 'batch': 'action entries proofs'} if kind == 7 else {
            'export': 'action', 'chunk': 'action transferId offset length'}
        check(payload['action'] in allowed and set(payload) == set(allowed[payload['action']].split()), 'wire action')
    for key, expected_kind in (('entry', 5), ('proof', 6), ('data', 0)):
        if key in payload:
            decoded = base64.b64decode(payload[key], validate=True)
            check(base64.b64encode(decoded).decode() == payload[key], 'canonical base64')
            if expected_kind:
                embedded = record(decoded, expected_kind, META if expected_kind == 6 else IMAGE)
                check(embedded.take(32) == m['digest'] and embedded.number('q') == value['epoch']
                      and embedded.take(16) == uuid.UUID(value['incarnationId']).bytes, 'embedded wire identity')
    return value


def initial_root(files, node, m):
    def read(name, kind):
        return record(files[node + '/' + name], kind)
    n = read('node.gsr', 2)
    check(n.take(32) == m['digest'] and n.text(64) == node and n.number('B') == 0, 'bootstrap node identity')
    n.end()
    hashes = [m['digest'], files[node + '/node.gsr'][16:48]]
    for name, kind in (('promises.gsr', 4), ('entries.gsr', 5), ('proofs.gsr', 6)):
        raw = files[node + '/' + name]
        check(len(raw) >= 48, 'root journal header')
        size = 48 + struct.unpack_from('>i', raw, 12)[0]
        header = record(raw[:size], 3)
        check(header.take(32) == m['digest'] and header.text(64) == node and header.number('H') == kind, 'journal header identity')
        header.end()
        hashes.append(raw[16:48])
        if kind == 4:
            promise = record(raw[size:], 4)
            check(promise.take(32) == m['digest'] and promise.text(64) == m['leader']
                  and promise.number('q') == 1 and promise.take(16) == bytes(16), 'initial promise')
            promise.end()
        else:
            check(size == len(raw), 'initial journal tail')
    ready = read('storage-ready.gsr', 7)
    check(ready.take(160) == b''.join(hashes), 'storage-ready hashes')
    ready.end()
    check(files[node + '/replica.lock'] == b'', 'lock bytes')


def journal(raw, plan_raw, receipt_raw, preparations, seal_nodes):
    offset, previous, phases, committed = 0, ZERO, [], False
    expected = [1, 2, 3, 4]
    while offset < len(raw):
        check(len(raw) - offset >= 48, 'journal tail')
        size = struct.unpack_from('>i', raw, offset + 12)[0] + 48
        check(48 < size <= META and size <= len(raw) - offset, 'journal record bound')
        frame = raw[offset:offset + size]
        r = record(frame, 21)
        check(r.take(32) == plan_raw[16:48] and r.number('q') == len(phases) + 1 and r.take(32) == previous, 'journal chain')
        phase = r.number('B')
        check(len(phases) < 4 and phase == expected[len(phases)], 'journal phase')
        for p in preparations:
            check(r.take(32) == (ZERO if phase == 1 else p[16:48]), 'journal preparations')
        check(r.take(32) == (receipt_raw[16:48] if phase == 4 else ZERO), 'journal decision')
        r.end()
        committed = phase == 4
        phases.append(phase)
        previous, offset = frame[16:48], offset + size
    check(committed and (not seal_nodes or len(phases) == 4), 'seal before committed decision')


def administrative_records(files, m, g, descriptor):
    plan_raw, receipt_raw = files['plan.gsr'], files['receipt.gsr']
    size = 48 + struct.unpack_from('>i', files['operation.gsr'], 12)[0]
    previous = files['operation.gsr'][size:size * 2]
    abort = record(files['admin-aborting.gsr'], 21)
    check(abort.take(32) == plan_raw[16:48] and abort.number('q') == 3 and abort.take(32) == previous[16:48]
          and abort.number('B') == 5, 'cleanup pre-commit transition')
    check(abort.take(96) == previous[48 + 73:48 + 169] and abort.take(32) == ZERO, 'abort preparation/decision')
    abort.end()
    cleanup = record(files['admin-cleanup.gsr'], 22)
    check(cleanup.take(32) == plan_raw[16:48] and cleanup.take(32) == previous[16:48], 'cleanup observed tail')
    c = json_value(cleanup.blob(META)); cleanup.end()
    exact(c, 'operation inventory deletePaths')
    check(c['operation'] == descriptor['operation'], 'cleanup operation')
    entries = c['inventory']; check(isinstance(entries, list) and 0 < len(entries) <= 10000, 'cleanup inventory count')
    names, by_path = [], {}
    for e in entries:
        exact(e, 'path kind size digest owner')
        name = e['path']; check(isinstance(name, str) and name.startswith('/') and len(name.encode()) <= 4096
                               and all(v not in ('', '.', '..') for v in name[1:].split('/')), 'cleanup path')
        check(e['kind'] in ('file', 'directory') and type(e['size']) is int and 0 <= e['size'] <= LIMIT
              and re.fullmatch('[0-9a-f]{64}', e['digest']) and e['owner'] in ('source', plan_raw[16:48].hex()), 'cleanup inventory fields')
        check(e['kind'] != 'directory' or e['size'] == 0 and e['digest'] == ZERO.hex(), 'cleanup directory')
        names.append(name); by_path[name] = e
    check(names == sorted(set(names), key=lambda v: v.encode()), 'cleanup inventory order')
    delete = c['deletePaths']
    check(isinstance(delete, list) and len(set(delete)) == len(delete), 'cleanup delete list')
    check(set(delete) == {e['path'] for e in entries if e['owner'] != 'source'}, 'cleanup protected/incomplete deletion')
    for i, name in enumerate(delete):
        check(by_path[name]['owner'] != 'source' and not any(v.startswith(name + '/') for v in delete[i + 1:]), 'cleanup dependency order')
    check(delete[-1] == c['operation']['path'], 'cleanup marker last')
    replacement = files['admin-replacement-plan.gsr']
    r = record(replacement, 23)
    check(r.number('H') == 1 and r.blob(META) == receipt_raw, 'replacement original receipt')
    d = json_value(r.blob(META)); inv = inventory(r); r.end()
    exact(d, 'operation source configuration manifestDigest genesisDigest sourceInventoryDigest')
    path_binding(d['operation']); path_binding(d['source'])
    check(d['manifestDigest'] == m['digest'].hex() and d['genesisDigest'] == g['digest'].hex()
          and d['sourceInventoryDigest'] == inventory_digest(inv).hex(), 'replacement identity/inventory')
    local = d['configuration']; exact(local, 'node target materialization replicationBounds')
    check(local['node'] in m['nodes'], 'replacement node')
    original = descriptor['replicas'][m['nodes'].index(local['node'])]
    check(all(local[k] == original[k] for k in ('node', 'replicationBounds')), 'replacement configuration')
    mat, old_mat = local['materialization'], original['materialization']
    path_binding(mat['directory'])
    check(dict(mat, directory=mat['directory']['path']) == dict(old_mat, directory=old_mat['directory']['path']),
          'replacement materialization policy')
    path_binding(local['target'])
    check(len({d['operation']['path'], d['source']['path'], local['target']['path']}) == 3, 'replacement paths')
    source_node = d['source']['path'].rsplit('/', 1)[-1]
    expected = [(name.removeprefix(source_node + '/'), 1, len(raw), sha(raw)) for name, raw in sorted(files.items()) if name.startswith(source_node + '/')]
    check(inv == expected, 'replacement source bytes')
    identity = record(files['admin-replacement-node.gsr'], 2)
    check(identity.take(32) == m['digest'] and identity.text(64) == local['node'] and identity.number('B') == 1, 'replacement nonvoter')
    identity.end()
    rebuilding = record(files['admin-rebuilding.gsr'], 13)
    check(rebuilding.take(32) == m['digest'] and rebuilding.text(64) == local['node'], 'replacement rebuilding')
    rebuilding.end()
    raw = files['admin-replacement-journal.gsr']; offset, previous_hash = 0, ZERO
    for phase in (1, 2):
        check(len(raw) - offset >= 48, 'replacement journal header')
        size = 48 + struct.unpack_from('>i', raw, offset + 12)[0]
        check(48 < size <= META and size <= len(raw) - offset, 'replacement journal bound')
        row = raw[offset:offset + size]; r = record(row, 21)
        check(r.take(32) == replacement[16:48] and r.number('q') == phase and r.take(32) == previous_hash
              and r.number('B') == phase and r.take(128) == ZERO * 4, 'replacement preparation only')
        r.end(); offset += size; previous_hash = row[16:48]
    check(offset == len(raw), 'replacement journal tail')


def validate(files):
    g = genesis(files['genesis.gsr'])
    g['raw'] = files['genesis.gsr']
    m = manifest(files['manifest.gsr'], g)
    descriptor, inventories = plan(files['plan.gsr'], m, g, files['manifest.gsr'])
    preparations = receipt(files['receipt.gsr'], files['plan.gsr'], m, inventories)
    for node, inv, prepared in zip(m['nodes'], inventories, preparations):
        check(files[node + '/bootstrap-prepared.gsr'] == prepared, 'local preparation')
        for name, kind, size, digest in inv:
            raw = files[node + '/' + name]
            check(len(raw) == size and sha(raw) == digest, 'payload inventory binding')
        check(files[node + '/genesis.gsr'] == g['raw'] and files[node + '/manifest.gsr'] == files['manifest.gsr'], 'local genesis binding')
        initial_root(files, node, m)
        s = record(files[node + '/bootstrap-seal.gsr'], 20)
        check(s.text(64) == node and s.blob(META) == files['receipt.gsr'], 'local seal')
        s.end()
    journal(files['operation.gsr'], files['plan.gsr'], files['receipt.gsr'], preparations, m['nodes'])
    source_reader = Reader(g['source'])
    src = source(source_reader)
    check(sum(v[2] for v in src[3]) <= descriptor['maxSourceBytes'], 'source bytes capacity')
    for name, kind, size, digest in src[3]:
        raw = files['source/' + name]
        check(len(raw) == size and sha(raw) == digest, 'source bytes binding')
    # Initial payloads plus three preparations/seals, one pending seal at a time,
    # coordinator plan/journal and both pending/final receipt copies.
    projected = sum(sum(v[2] for v in inv) for inv in inventories) + sum(len(p) for p in preparations)
    projected += sum(len(files[node + '/bootstrap-seal.gsr']) for node in m['nodes'])
    projected += max(len(files[node + '/bootstrap-seal.gsr']) for node in m['nodes'])
    projected += len(files['plan.gsr']) + len(files['operation.gsr']) + 2 * len(files['receipt.gsr'])
    check(projected <= descriptor['maxOperationBytes'], 'operation bytes capacity')
    for node, inv, local, prepared in zip(m['nodes'], inventories, descriptor['replicas'], preparations):
        retained = sum(v[2] for v in inv) + len(prepared) + 2 * len(files[node + '/bootstrap-seal.gsr'])
        check(retained <= local['replicationBounds']['maxRetainedLogBytes'], 'local retained capacity')
    administrative_records(files, m, g, descriptor)
    sequences = [snapshot(raw, m, g) for name, raw in sorted(files.items()) if name.startswith('snapshot-')]
    for name, raw in files.items():
        if name.startswith('wire-'):
            wire(raw, m)
    check(sequences, 'missing snapshot evidence')
    return {'baseSequence': g['base'], 'applicationHistory': str(uuid.UUID(bytes=g['history'])),
            'snapshotSequences': sequences, 'manifestDigest': m['digest'].hex(), 'genesisDigest': g['digest'].hex()}


def cases(path):
    data = json.loads(Path(path).read_text())
    check(data['schema'] == 'gse-v50-admission-fixtures-v2', 'fixture schema')
    bases = {name: {p: bytes.fromhex(raw) for p, raw in files.items()} for name, files in data['bases'].items()}
    for case in data['cases']:
        files = dict(bases[case['base']])
        for name, raw in case.get('replace', {}).items():
            if raw is None:
                files.pop(name, None)
            else:
                files[name] = bytes.fromhex(raw)
        yield case, files
