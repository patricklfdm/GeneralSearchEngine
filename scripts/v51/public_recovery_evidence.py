"""Independent checks for imported genesis, lifecycle cuts and startup rejection."""
import copy
import json
from pathlib import Path
from . import public_qualification_evidence as q, runtime_evidence as authority, storage_inspector as storage
from .storage_harness import need


def imported(root, expected):
    root = Path(root); manifests = []; genesis = []
    for node in ('node-1', 'node-2', 'node-3'):
        manifest = authority.f.inspect((root / node / 'manifest.gsr').read_bytes(), 'MANIFEST')
        encoded = (root / node / 'genesis.gsr').read_bytes(); image = authority.f.inspect(encoded, 'GENESIS')
        need(manifest['genesisDigest'] == encoded[16:48].hex(), 'import genesis binding')
        indexes, docs = authority.application(authority.raw(image['application']))
        need(manifest['baseSequence'] == image['baseSequence'] == expected['sequence'], 'import base sequence')
        need([dict(id=k, value=v) for k, v in docs.items()] == expected['documents'], 'import document order/bytes')
        need(indexes == [dict(analyzer='', field='value', kind='equality')], 'import index definition'); manifests.append(manifest); genesis.append(image)
    need(manifests.count(manifests[0]) == 3 and genesis.count(genesis[0]) == 3, 'import voter genesis differs')
    return dict(status='PASS', baseSequence=expected['sequence'], documents=len(expected['documents']))


def admission(before, after, results):
    need(before == after, 'failed admission changed retained authority')
    need(len(results) == 2 and len({r['pid'] for r in results}) == 2, 'admission needs independent reopen attempts')
    for result in results:
        need(result['state'] == 'FAILED' and result['outcome'] == 'NOT_APPLICABLE' and
             result.get('reasonCode') in ('INTEGRITY_FAILURE', 'STORAGE_FAILURE'), 'unsafe authority admitted')
    return dict(status='PASS', attempts=2, authorityUnchanged=True)


def lifecycle(history, traces, case, target):
    attempts = {op['opId']: op for op in history}; op = attempts[target]
    own = [r for r in traces[op['node']] if r['pid'] == op['pid']]
    reached = [r for r in own if r['event'] == 'CUT_REACHED']
    released = [r for r in own if r['event'] == 'CUT_RELEASED']
    need(len(reached) == len(released) == 1 and reached[0]['order'] < released[0]['order'], 'missing lifecycle pause/release')
    start, end = reached[0]['order'], released[0]['order']
    events = [r for r in own if start < r['order'] < end]
    if case.startswith('cancel-'):
        need(op['kind'] == 'addAll' and op['outcome'] == 'CANCELLED', 'mutation cancellation not observed')
        cancels = [r for r in events if r['event'] == 'CLIENT_CANCEL' and r['target'] == target and r['cancelled'] is True]
        need(len(cancels) == 1, 'cancel did not cross paused operation')
        call = next((r for r in own if r['event'] == 'CLIENT_INVOKE' and r.get('opId') == target), None)
        need(call is not None and call['order'] < cancels[0]['order'], 'cancel precedes target invocation')
        accepts = []
        for rows in traces.values():
            for r in rows:
                if r['event'] == 'FORCE' and r['kind'] == 'ACCEPT':
                    vote = authority.f.inspect(authority.raw(r['record']), 'ACCEPT')
                    entry = authority.f.inspect(authority.raw(vote['entry']), 'ENTRY')
                    if entry['operation'] == 4 and [dict(id=k, value=v) for k, v in authority.documents_command(authority.raw(entry['payload']))] == op['documents']:
                        accepts.append((r, vote))
        if case == 'cancel-queued':
            need(reached[0]['cut'] == 'READ_CAPTURED' and start < call['order'] < end and not accepts, 'queued cancellation appended authority')
        else:
            need(reached[0]['cut'] == 'ACCEPT_AFTER_FORCE' and call['order'] < start, 'forced cancellation boundary')
            need(any(r['pid'] == op['pid'] and call['order'] < r['order'] < start for r, _ in accepts), 'cancel before actual local force')
            need(len({r['node'] for r, _ in accepts}) >= 2, 'admitted cancellation did not reach an entry quorum')
            final = next(h for h in reversed(history) if h['kind'] == 'read' and h['outcome'] == 'SUCCESS')
            need(all(d in final['documents'] for d in op['documents']), 'admitted cancellation undone')
    else:
        need(case == 'close-pinned' and reached[0]['cut'] == 'READ_CAPTURED', 'close pause boundary')
        invoked = next((r for r in own if r['event'] == 'CLIENT_INVOKE' and r.get('opId') == target), None)
        callback = next((r for r in own if r['event'] == 'READ_CALLBACK' and r.get('opId') == target), None)
        success = next((r for r in own if r['event'] == 'CLIENT_SUCCESS' and r.get('opId') == target), None)
        need(op['kind'] == 'read' and invoked is not None and callback is not None and success is not None and
             invoked['order'] < start < end < callback['order'] < success['order'], 'close borrowed an unrelated read')
        closes = [r for r in events if r['event'] == 'CLIENT_FAILURE' and r['kind'] == 'closeHandle']
        duplicate = [r for r in events if r['event'] == 'CLIENT_FAILURE' and r['kind'] == 'duplicateStart']
        need(len(closes) == len(duplicate) == 1 and closes[0].get('reasonCode') == 'DEADLINE_EXCEEDED' and
             duplicate[0].get('reasonCode') == 'STORAGE_FAILURE', 'close released active view ownership')
        need(op['outcome'] == 'SUCCESS', 'pinned read did not finish')
        need(any(r['event'] == 'HANDLE_CLOSED' and r['order'] > end for r in own), 'close did not drain after release')
        need(any(h['kind'] == 'duplicateStart' and h['outcome'] == 'SUCCESS' for h in history), 'ownership not reusable after close')
    return dict(status='PASS', boundary=reached[0]['cut'], operation=target)


def negatives(history, traces, case, target):
    results = []
    names = ['missing-pause', 'missing-release', 'missing-cancel' if case.startswith('cancel-') else 'missing-ownership-rejection']
    if case == 'cancel-forced': names.append('missing-local-accept-force')
    operation = next(h for h in history if h['opId'] == target)
    for name in names:
        changed = copy.deepcopy(traces)
        for node, rows in changed.items():
            changed[node] = [r for r in rows if not (
                name == 'missing-pause' and r['event'] == 'CUT_REACHED' or
                name == 'missing-release' and r['event'] == 'CUT_RELEASED' or
                name == 'missing-cancel' and r['event'] == 'CLIENT_CANCEL' or
                name == 'missing-local-accept-force' and r['pid'] == operation['pid'] and r['event'] == 'FORCE' and r['kind'] == 'ACCEPT' or
                name == 'missing-ownership-rejection' and r['event'] == 'CLIENT_FAILURE' and r['kind'] == 'duplicateStart')]
        try: lifecycle(history, changed, case, target)
        except ValueError as error: results.append(dict(case=name, status='REJECTED', reason=str(error)))
        else: raise ValueError('lifecycle oracle accepted ' + name)
    return results


def cursors(candidate, control):
    need(candidate == control, 'published V4.4 cursor semantics differ')
    need(candidate['mutationFailure'] != 'ACCEPTED' and candidate['rebuildFailure'] != 'ACCEPTED', 'stale cursor admitted')
    need(candidate['sequenceAfterReads'] == 1 and candidate['sequenceAfterRebuild'] == 2, 'cursor sequence advanced on read')
    need(candidate['first'] == candidate['freshAfterRebuild'] and candidate['continuedAfterReads'] != candidate['first'], 'cursor continuation/reset')
    return dict(status='PASS', execution='three-public-voters-one-jvm', oracle='published-v4.4')
