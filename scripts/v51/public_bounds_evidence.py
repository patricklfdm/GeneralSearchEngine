"""Independent public rejection checks: exact outcomes, raw forces and byte preservation."""
import copy
import hashlib
import json
import struct
import tarfile
from . import runtime_evidence as authority, storage_inspector as storage
from .storage_harness import need

ADMISSION_REASONS = {
    'disk-v10': 'PROTOCOL_MISMATCH', 'disk-v11': 'PROTOCOL_MISMATCH',
    'automatic-on-configured': 'PROTOCOL_MISMATCH', 'configured-on-automatic': 'INTEGRITY_FAILURE',
    'group-mismatch': 'INTEGRITY_FAILURE', 'configuration-mismatch': 'INTEGRITY_FAILURE',
    'schema-mismatch': 'INTEGRITY_FAILURE', 'bounds-mismatch': 'INTEGRITY_FAILURE',
}


def admission_authority(root, case, original, before):
    archived = {}
    with tarfile.open(root/'rejected-authority.tar.gz') as tar:
        for member in tar.getmembers():
            if member.isdir(): continue
            need(member.isfile(), 'rejected archive member type')
            need(member.name not in archived, 'duplicate rejected archive member')
            archived[member.name] = tar.extractfile(member).read()
    expected = {node+'/'+name: entry for node, files in before.items() for name, entry in files.items()}
    need({name: dict(size=len(raw), sha256=storage.sha(raw)) for name, raw in archived.items()} == expected, 'rejected archive inventory differs')
    if case.startswith('disk-'):
        raw = archived['node-1/manifest.gsr']
        restored = disk_header_fault(raw, 0 if case == 'disk-v10' else 1)
        storage.f.inspect(restored, 'MANIFEST')
        changed = copy.deepcopy(before)
        changed['node-1']['manifest.gsr'] = dict(size=len(restored), sha256=storage.sha(restored))
        need(changed == original, 'disk fault changed more than version header')
    else:
        need(before == original, 'configuration probe changed authority')
        for node in before:
            raw = archived[node+'/manifest.gsr']
            if case == 'automatic-on-configured':
                from scripts.v50 import admission_format as legacy
                legacy.manifest(raw, legacy.genesis(archived[node+'/genesis.gsr']))
            else:
                need(storage.f.inspect(raw, 'MANIFEST')['mode'] == 'AUTOMATIC', 'wrong probe authority mode')
    return dict(status='PASS', archivedFiles=len(archived), isolatedFault=True)


def disk_header_fault(raw, minor):
    header = struct.unpack('>4sHHHHi', raw[:16])
    need(header[:5] == (b'GSER', 1, minor, 1, 0) and header[-1] == len(raw)-48, 'wrong disk version fault')
    need(hashlib.sha256(raw[:16]+raw[48:]).digest() == raw[16:48], 'disk fault checksum')
    restored = struct.pack('>4sHHHHi', b'GSER', 1, 2, 1, 0, len(raw)-48)
    return restored+hashlib.sha256(restored+raw[48:]).digest()+raw[48:]


def admission(case, before, after_each, attempts):
    need(before and len(attempts) == len(after_each) == 2, 'two retained admission attempts required')
    need(len({v['pid'] for v in attempts}) == 2, 'independent admission process identity')
    for result, after in zip(attempts, after_each):
        need(before == after, 'rejection mutated authority')
        need(result['case'] == case and result['state'] == 'FAILED' and result['outcome'] == 'NOT_APPLICABLE'
             and result.get('reasonCode') == ADMISSION_REASONS[case], 'wrong admission rejection')
    return dict(status='PASS', attempts=2, authorityUnchanged=True)


def bounds(root, history, traces, case, targets):
    binding = storage.f.inspect((root/'node-1/bootstrap-binding.gsr').read_bytes(), 'BOOTSTRAP_BINDING')
    replicas = json.loads(storage.raw(binding['descriptor']))['replicas']
    need(all(v['replicationBounds']['maxPendingClientOperations'] == 1 and
             v['replicationBounds']['maxFrameBytes'] == 128 << 10 and
             v['materialization']['bounds']['maxBulkElements'] == 4 and
             v['materialization']['bounds']['maxDocuments'] == 4 for v in replicas), 'fixture bounds not sealed')
    if case == 'no-quorum-start':
        starts = json.loads((root/'worker-starts.json').read_text())
        need(len(starts) == 4 and len({s['pid'] for s in starts}) == 4, 'three voters and retained restart required')
        last = max(op['endNanos'] for op in history if op['opId'] in targets)
        need(starts[0]['node'] == 'node-1' and all(s['startNanos'] > last for s in starts[1:]), 'quorum present during solo rejection')
    return rejection_history(history, traces, case, targets)


def sequential_admission(history, traces, case, targets):
    # Pending-capacity probes intentionally overlap their held call; solo startup
    # probes test role rejection. All other calls need an actual idle observation
    # newer than the preceding application response in the same worker process.
    exempt = set(targets) if case.startswith('pending-') or case == 'no-quorum-start' else set()
    checked = 0
    for op in history:
        if op['opId'] in exempt: continue
        own = [r for r in traces[op['node']] if r['pid'] == op['pid']]
        invoke = [r for r in own if r['event'] == 'CLIENT_INVOKE' and r.get('opId') == op['opId']]
        need(len(invoke) == 1, 'missing sequential invocation')
        before = invoke[0]['order']
        previous = max((r['order'] for r in own if r['order'] < before and
                        r['event'] in ('CLIENT_SUCCESS', 'CLIENT_FAILURE') and
                        r.get('kind') in ('addAll', 'read')), default=0)
        need(any(previous < r['order'] < before and r['event'] == 'CLIENT_SUCCESS' and
                 r.get('kind') == 'status' and r.get('pending') == 0 for r in own),
             'missing fresh idle admission before '+op['opId'])
        checked += 1
    need(checked > 0, 'no sequential admission observations')
    return dict(status='PASS', checkedCalls=checked)


def rejection_history(history, traces, case, targets):
    need(len(targets) == (2 if case.startswith('pending-') or case == 'no-quorum-start' else 1)
         and len(set(targets)) == len(targets), 'missing rejection targets')
    calls = {h['opId']: h for h in history}; rejected = [calls[t] for t in targets]
    need([v['kind'] for v in rejected] == (['addAll', 'read'] if len(targets) == 2 else ['addAll']), 'rejected call kinds')
    docs = rejected[0]['documents']
    if case == 'payload-limit':
        need(len(docs) == 1 and len(docs[0]['value'].encode('utf-8'))*4//3 > 128 << 10, 'payload does not exceed encoded frame')
    elif case == 'bulk-limit': need(len(docs) > 4, 'bulk does not exceed sealed limit')
    elif case == 'document-limit':
        earlier = [d for op in history if op['kind'] == 'addAll' and op['outcome'] == 'SUCCESS' and
                   op['endNanos'] < rejected[0]['startNanos'] for d in op['documents']]
        need(len(docs) <= 4 and len(earlier) == 2 and len(docs)+len(earlier) > 4, 'document limit not exercised')
    for op in rejected:
        need(op['outcome'] == ('NOT_SUBMITTED' if op['kind'] == 'addAll' else 'NOT_APPLICABLE'), 'rejection outcome')
        need(op.get('reasonCode') in (('NOT_LEADER', 'NOT_READY', 'QUORUM_UNAVAILABLE') if case == 'no-quorum-start'
                                    else ('CAPACITY_EXCEEDED',)), 'rejection reason')
        own = [r for r in traces[op['node']] if r['pid'] == op['pid']]
        response = [r for r in own if r['event'] == 'CLIENT_FAILURE' and r.get('opId') == op['opId']]
        need(len(response) == 1 and all(response[0].get(k) == op.get(k) for k in ('kind', 'outcome', 'reasonCode')), 'missing exact worker rejection')
        if case.startswith('pending-'):
            reached = [r for r in own if r['event'] == 'CUT_REACHED']
            released = [r for r in own if r['event'] == 'CUT_RELEASED']
            cut = 'READ_CAPTURED' if case == 'pending-read' else 'ACCEPT_AFTER_FORCE'
            need(len(reached) == len(released) == 1 and reached[0]['cut'] == cut and
                 reached[0]['order'] < response[0]['order'] < released[0]['order'], 'rejection outside held capacity')
            boundary = next((r for r in own if r['event'] == cut and r['order'] < reached[0]['order']), None)
            need(boundary is not None, 'pause without actual runtime boundary')
        if op['kind'] == 'addAll':
            for rows in traces.values():
                for row in rows:
                    if row['event'] == 'FORCE' and row['kind'] == 'ACCEPT':
                        vote = authority.f.inspect(authority.raw(row['record']), 'ACCEPT')
                        entry = authority.f.inspect(authority.raw(vote['entry']), 'ENTRY')
                        if entry['operation'] == 4:
                            docs = [dict(id=k, value=v) for k, v in authority.documents_command(authority.raw(entry['payload']))]
                            need(docs != op['documents'], 'NOT_SUBMITTED mutation reached durable acceptance')
    last = max(op['endNanos'] for op in rejected)
    need(any(op['kind'] == 'addAll' and op['outcome'] == 'SUCCESS' and op['startNanos'] > last for op in history), 'capacity never recovered for writes')
    need(any(op['kind'] == 'read' and op['outcome'] == 'SUCCESS' and op['startNanos'] > last for op in history), 'capacity never recovered for reads')
    return dict(status='PASS', rejections=len(targets), resumedWritesAndReads=True)


def wire(manifest, probes):
    names = ('wire-v10', 'wire-v11', 'wire-mode', 'wire-protocol', 'wire-group', 'wire-manifest', 'wire-oversize')
    need([p['case'] for p in probes] == list(names), 'wire rejection matrix incomplete')
    for probe in probes:
        need(probe['terminal'] in ('EOF', 'RESET') and not probe['response'], 'wrong wire accepted or only timed out')
        need(probe['before'] and probe['before'] == probe['after'], 'wire rejection mutated authority')
        good = storage.raw(probe['controlRequest']); reply = storage.raw(probe['controlResponse'])
        request = storage.f.wire(good, manifest); response = storage.f.wire(reply, manifest)
        need(request['type'] == response['type'] == 'HANDSHAKE' and response['payload'] == {'mode': 'AUTOMATIC'}, 'live handshake control missing')
        need(request['sender'] == response['recipient'] and request['recipient'] == response['sender'] and
             all(request[k] == response[k] for k in ('traceId', 'eventSequence', 'epoch', 'proposer', 'incarnationId')), 'uncorrelated live handshake')
        need(storage.f.wire(storage.raw(probe['initialResponse']), manifest) == response, 'initial live handshake missing')
        bad = storage.raw(probe['request']); header = struct.unpack('>4sHHHHi', bad[:16]); case = probe['case']
        if case == 'wire-oversize':
            need(len(bad) == 48 and header[:5] == (b'GSRP', 1, 2, 1, 0) and
                 probe['maxFrameBytes'] == 1 << 20 and header[-1] + 48 > probe['maxFrameBytes'], 'missing oversized declaration')
        else:
            need(hashlib.sha256(bad[:16]+bad[48:]).digest() == bad[16:48], 'fault has incidental checksum corruption')
            changed = json.loads(bad[48:]); original = dict(request)
            if case in ('wire-v10', 'wire-v11'):
                need(header[:5] == (b'GSRP', 1, 0 if case == 'wire-v10' else 1, 1, 0) and changed == original, 'wrong wire version fault')
            else:
                need(header[:5] == (b'GSRP', 1, 2, 1, 0), 'wrong wire header')
                key = {'wire-mode': 'payload', 'wire-protocol': 'protocol', 'wire-group': 'groupId', 'wire-manifest': 'manifestDigest'}[case]
                need(changed[key] != original[key] and {k:v for k,v in changed.items() if k != key} ==
                     {k:v for k,v in original.items() if k != key}, 'wire fault does not isolate its field')
    return dict(status='PASS', rejectedFrames=len(probes), liveControls=len(probes))


def negatives(check, args, mutations):
    results = []
    for name, mutate in mutations:
        changed = copy.deepcopy(args); mutate(changed)
        try: check(*changed)
        except (ValueError, KeyError) as error: results.append(dict(case=name, status='REJECTED', reason=str(error)))
        else: raise ValueError('rejection checker admitted '+name)
    return results
