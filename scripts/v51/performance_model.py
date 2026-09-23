"""Independent rich-corpus semantics, not a protocol or performance qualification.

No product code or V5.0 performance model is imported. Projection consumes decoded
commands; actual force/quorum/publication/read-cut evidence is a separate layer.
"""
import hashlib
import json
import re
import struct
from dataclasses import dataclass, field

OPERATIONS = ('ADD', 'UPDATE', 'REMOVE', 'ADD_ALL', 'UPDATE_ALL', 'REMOVE_ALL',
              'INDEX_DROP', 'INDEX_CREATE', 'GET', 'QUERY')
OP_IDS = {'ADD': 1, 'UPDATE': 2, 'REMOVE': 3, 'ADD_ALL': 4, 'UPDATE_ALL': 5,
          'REMOVE_ALL': 6, 'INDEX_CREATE': 7, 'INDEX_DROP': 8, 'NO_OP': 9}
INDEXES = [dict(analyzer=a, field=f, kind=k) for f, k, a in
           [('body', 'text', 'gse-simple-v1'), ('category', 'equality', ''),
            ('price', 'range', ''), ('title', 'prefix', '')]]


def need(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = dict(items)
        need(len(result) == len(items), 'duplicate JSON key')
        return result
    def constant(value):
        raise ValueError('nonfinite JSON: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def document(key, revision, seed=17):
    return (key, 'Java ' + str(key), 'news' if (key + revision + seed) % 3 == 0 else 'guide',
            (key * 17 + revision + seed) % 1000, 'java search memory revision ' + str(revision))


def encode_document(doc):
    return '\n'.join(map(str, doc)).encode('utf-8')


def decode_document(raw):
    need(0 < len(raw) <= 256, 'rich document byte bound')
    fields = raw.decode('utf-8', 'strict').split('\n')
    need(len(fields) == 5, 'rich document fields')
    doc = (int(fields[0]), fields[1], fields[2], int(fields[3]), fields[4])
    need(-(1 << 31) <= doc[0] < 1 << 31 and -(1 << 31) <= doc[3] < 1 << 31, 'rich integer range')
    need(encode_document(doc) == raw, 'noncanonical rich document')
    revision = re.fullmatch(r'java search memory revision ([0-9])', doc[4])
    need(revision is not None and doc == document(doc[0], int(revision[1])), 'document outside frozen rich corpus/program')
    return doc


def display(doc):
    return 'Doc[id=%s, title=%s, category=%s, price=%s, body=%s]' % tuple(doc)


def blob(raw):
    return struct.pack('>i', len(raw)) + raw


class Reader:
    def __init__(self, raw):
        self.raw, self.offset = raw, 0

    def take(self, size):
        need(0 <= size <= len(self.raw) - self.offset, 'truncated rich field')
        value = self.raw[self.offset:self.offset + size]
        self.offset += size
        return value

    def integer(self):
        return struct.unpack('>i', self.take(4))[0]

    def count(self, maximum):
        size = self.integer()
        need(0 <= size <= maximum, 'rich count bound')
        return size

    def blob(self, maximum):
        return self.take(self.count(maximum))

    def key(self):
        raw = self.blob(4)
        need(len(raw) == 4, 'rich key length')
        return struct.unpack('>i', raw)[0]

    def end(self):
        need(self.offset == len(self.raw), 'trailing rich bytes')


def descriptor(raw):
    value = strict_json(raw)
    need(value in INDEXES and canonical(value) == raw, 'unsupported/noncanonical rich index')
    return value


def decode_command(operation, payload):
    need(type(operation) is int and operation in OP_IDS.values(), 'unsupported rich operation')
    need(len(payload) <= 2048, 'rich payload bound')
    if operation == 9:
        need(payload == b'', 'NO_OP payload')
        return None
    reader = Reader(payload)
    need(reader.take(2) == b'\x00\x01', 'rich command version')
    if operation == 7:
        value = descriptor(reader.blob(1024))
    elif operation == 8:
        value = reader.blob(1024).decode('utf-8')
        need(value in {v['field'] for v in INDEXES}, 'unknown index field')
    else:
        count = reader.count(16)
        need(count > 0 and (operation >= 4 or count == 1), 'rich mutation count')
        value = []
        for _ in range(count):
            key = reader.key()
            doc = None if operation in (3, 6) else decode_document(reader.blob(256))
            need(doc is None or doc[0] == key, 'rich document/key mismatch')
            need(key not in {k for k, _ in value}, 'duplicate rich mutation key')
            value.append((key, doc))
    reader.end()
    return value


@dataclass
class State:
    documents: dict = field(default_factory=dict)
    indexes: list = field(default_factory=lambda: [dict(v) for v in INDEXES])
    sequence: int = 4

    def copy(self):
        return State(dict(self.documents), [dict(v) for v in self.indexes], self.sequence)

    def apply(self, operation, payload):
        value = decode_command(operation, payload)
        # Validate every bulk precondition before changing any model state.
        if operation in (1, 2, 3, 4, 5, 6):
            for key, _ in value:
                need((key in self.documents) == (operation in (2, 3, 5, 6)), 'rich mutation precondition')
            need(len(self.documents) + (len(value) if operation in (1, 4) else 0) <= 1024, 'rich document capacity')
            for key, doc in value:
                if operation in (3, 6):
                    del self.documents[key]
                else:
                    self.documents[key] = doc
        elif operation == 7:
            need(value['field'] not in {v['field'] for v in self.indexes}, 'index already exists')
            self.indexes.append(value)
            self.indexes.sort(key=lambda v: v['field'])
        elif operation == 8:
            self.indexes = [v for v in self.indexes if v['field'] != value]
        if operation != 9:
            self.sequence += 1
        return self

    def answer(self, operation, cycle):
        if operation == 'GET':
            return display(self.documents[1 + cycle % 64])
        need(operation == 'QUERY', 'not a rich read')
        return [key for key, doc in self.documents.items() if doc[2] == 'guide' and 'java' in doc[4].lower().split()]

    def application(self):
        return (b'\x00\x01' + struct.pack('>i', len(self.indexes)) + b''.join(blob(canonical(v)) for v in self.indexes)
                + struct.pack('>i', len(self.documents))
                + b''.join(blob(struct.pack('>i', k)) + blob(encode_document(v)) for k, v in self.documents.items()))


def application(raw, sequence):
    need(type(sequence) is int and 0 <= sequence < 1 << 63, 'rich application sequence')
    need(len(raw) <= 128 << 20, 'rich application byte bound')
    reader = Reader(raw)
    need(reader.take(2) == b'\x00\x01', 'rich application version')
    indexes = [descriptor(reader.blob(1024)) for _ in range(reader.count(4))]
    fields = [v['field'] for v in indexes]
    need(fields == sorted(set(fields)), 'rich index order/duplicate')
    docs = {}
    for _ in range(reader.count(1024)):
        key, doc = reader.key(), decode_document(reader.blob(256))
        need(key == doc[0] and key not in docs, 'rich application key/duplicate')
        docs[key] = doc
    reader.end()
    return State(docs, indexes, sequence)


def initial(plan):
    smoke = plan['localSmoke']
    return State({i: document(i, 0, smoke['seed']) for i in range(1, smoke['corpusDocuments'] + 1)},
                 sequence=smoke['corpusDocuments'] // smoke['loadBulkElements'])


def program(plan):
    """Operation tape is independent of the byte decoder/state transition above."""
    smoke = plan['localSmoke']
    cycle = smoke['firstCycle']
    for window in ['warmup', *smoke['windows']]:
        for _ in range(smoke['warmupCycles'] if window == 'warmup' else smoke['cyclesPerWindow']):
            for operation in OPERATIONS:
                size = smoke['mutationBulkElements'] if operation.endswith('_ALL') else 1
                keys = ([1 + cycle % smoke['corpusDocuments']] if operation == 'GET' else [] if operation.startswith('INDEX') or operation == 'QUERY'
                        else [1 + (cycle + i) % smoke['corpusDocuments'] if operation.startswith('UPDATE') else 100000 + cycle * 100 + i for i in range(size)])
                docs = [document(k, cycle + 1, smoke['seed']) for k in keys] if operation.startswith(('ADD', 'UPDATE')) else []
                payload = b''
                if operation in OP_IDS:
                    payload = b'\x00\x01'
                    if operation.startswith('INDEX'):
                        payload += blob(canonical(INDEXES[1]) if operation == 'INDEX_CREATE' else b'category')
                    else:
                        payload += struct.pack('>i', size)
                        for i, key in enumerate(keys):
                            payload += blob(struct.pack('>i', key))
                            if docs:
                                payload += blob(encode_document(docs[i]))
                yield dict(window=window, cycle=cycle, operation=operation, keys=keys,
                           documents=docs, payload=payload)
            cycle += 1


def expected(plan):
    state = initial(plan)
    rows, peak = [], len(state.documents)
    for ordinal, call in enumerate(program(plan), 1):
        operation = call['operation']
        before = state.sequence
        answer = None
        if operation in OP_IDS:
            state.apply(OP_IDS[operation], call['payload'])
        else:
            answer = state.answer(operation, call['cycle'])
        peak = max(peak, len(state.documents))
        rows.append(dict(ordinal=ordinal, window=call['window'], cycle=call['cycle'], operation=operation,
                         keys=call['keys'], payloadSha256=sha(call['payload']), answer=answer,
                         answerSha256=sha(canonical(answer)), beforeSequence=before, afterSequence=state.sequence,
                         applicationSha256=sha(state.application()), indexCount=len(state.indexes), documentCount=len(state.documents)))
    return dict(rows=rows, state=state, peakDocuments=peak)
