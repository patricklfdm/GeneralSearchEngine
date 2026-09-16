"""Independent, deterministic Phase 6A operation/state/encoded-payload oracle."""
import hashlib
import json
import struct

OPERATIONS = ('ADD', 'UPDATE', 'REMOVE', 'ADD_ALL', 'UPDATE_ALL', 'REMOVE_ALL',
              'INDEX_DROP', 'INDEX_CREATE', 'GET', 'QUERY')
OP_IDS = dict(zip(('ADD', 'UPDATE', 'REMOVE', 'ADD_ALL', 'UPDATE_ALL', 'REMOVE_ALL', 'INDEX_CREATE', 'INDEX_DROP'), range(1, 9)))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def document(key, revision, seed=17):
    return (key, 'Java ' + str(key), 'news' if (key + revision + seed) % 3 == 0 else 'guide',
            (key * 17 + revision + seed) % 1000, 'java search memory revision ' + str(revision))


def encoded(doc):
    return '\n'.join(map(str, doc)).encode('utf-8')


def display(doc):
    return 'Doc[id=%s, title=%s, category=%s, price=%s, body=%s]' % doc


def blob(raw):
    return struct.pack('>i', len(raw)) + raw


def descriptor(field, kind, analyzer=''):
    return canonical(dict(field=field, kind=kind, analyzer=analyzer)).decode('ascii')


INDEXES = [descriptor('body', 'text', 'gse-simple-v1'), descriptor('category', 'equality'),
           descriptor('price', 'range'), descriptor('title', 'prefix')]


def schedule(plan):
    s = plan['localSmoke']
    docs = {i: document(i, 0, s['seed']) for i in range(1, s['corpusDocuments'] + 1)}
    initial = list(docs.values())
    sequence = s['corpusDocuments'] // s['loadBulkElements']
    rows, anchors = [], [(9, digest(b''))]  # Activation NO_OP.
    cycle = 0
    for window in ['warmup', *s['windows']]:
        count = s['warmupCycles'] if window == 'warmup' else s['cyclesPerWindow']
        for _ in range(count):
            for op in OPERATIONS:
                size = s['mutationBulkElements'] if op.endswith('_ALL') else 1
                keys = [(1 + (cycle + i) % s['corpusDocuments']) if op.startswith('UPDATE') else
                        100000 + cycle * 100 + i for i in range(size)]
                changed = [document(k, cycle + 1, s['seed']) for k in keys]
                before, answer = sequence, None
                payload = struct.pack('>H', 1)
                if op in OP_IDS:
                    if op.startswith('INDEX'):
                        payload += blob((INDEXES[1] if op == 'INDEX_CREATE' else 'category').encode('ascii'))
                    else:
                        payload += struct.pack('>i', size)
                        for key, doc in zip(keys, changed):
                            payload += blob(struct.pack('>i', key))
                            if not op.startswith('REMOVE'):
                                payload += blob(encoded(doc))
                        if op.startswith('REMOVE'):
                            for key in keys:
                                del docs[key]
                        else:
                            docs.update(zip(keys, changed))
                    sequence += 1
                    anchors.append((OP_IDS[op], digest(payload)))
                elif op == 'GET':
                    answer = display(docs[1 + cycle % s['corpusDocuments']])
                else:
                    answer = [d[0] for d in docs.values() if d[2] == 'guide']
                rows.append(dict(window=window, cycle=cycle, operation=op, outcome='success', beforeSequence=before,
                                 afterSequence=sequence, documents=0 if op.startswith('INDEX') or op == 'QUERY' else size,
                                 answerDigest=digest(canonical(answer))))
            cycle += 1
    return dict(initial=initial, documents=list(docs.values()), rows=rows, anchors=anchors, sequence=sequence)


def statistics(windows):
    """Nearest-rank percentiles; requests and touched documents remain separate."""
    result = {}
    for window in windows:
        if window['window'] == 'warmup':
            continue
        operations = {}
        for op in OPERATIONS:
            rows = [r for r in window['rows'] if r['operation'] == op]
            samples = sorted(r['elapsedNanos'] for r in rows)
            n = len(samples)
            operations[op] = dict(attempted=n, admitted=n, completed=n, durableSuccess=n if op in OP_IDS else 0,
                                  rejected=0, timedOut=0, indeterminate=0, documents=sum(r['documents'] for r in rows),
                                  p50Nanos=samples[(n * 50 + 99) // 100 - 1],
                                  p95Nanos=samples[(n * 95 + 99) // 100 - 1],
                                  p99Nanos=samples[(n * 99 + 99) // 100 - 1])
        result[window['window']] = dict(elapsedNanos=window['elapsedNanos'], requests=len(window['rows']),
                                       requestRateMilliHz=len(window['rows']) * 10**12 // window['elapsedNanos'], operations=operations)
    return result


def summary(candidate, control):
    measured = dict(candidate=statistics(candidate), control=statistics(control))
    observations = {}
    for name, values in measured.items():
        baseline = sum(values[w]['elapsedNanos'] for w in ('baseline-a', 'baseline-b'))
        instrumented = sum(values[w]['elapsedNanos'] for w in ('instrumented-a', 'instrumented-b'))
        observations[name] = dict(baselineNanos=baseline, instrumentedNanos=instrumented,
                                  instrumentedToBaselinePpm=instrumented * 1_000_000 // baseline)
    return dict(**measured, overheadObservation=observations,
                fault=dict(attempted=1, durableSuccess=0, indeterminate=1, reason='QUORUM_UNAVAILABLE'))
