"""Causal checks for public mutation cuts and reads overlapping a higher promise."""
from . import runtime_evidence as a
from .storage_harness import need
from pathlib import Path

MUTATION_CUTS = ('ACCEPT_BEFORE_WRITE', 'ACCEPT_AFTER_FORCE', 'ACCEPT_ACK_RECEIVED',
                 'PROOF_BEFORE_WRITE', 'PROOF_AFTER_FORCE', 'PROOF_ACK_RECEIVED',
                 'BEFORE_PUBLISH', 'PUBLISHED')


def read_fence(rows, operation, before_capture):
    invoke = next(r for r in rows if r['event'] == 'CLIENT_INVOKE' and r.get('opId') == operation['opId'])
    reached = next(r for r in rows if r['event'] == 'CUT_REACHED' and r['order'] > invoke['order'])
    release = next(r for r in rows if r['event'] == 'CUT_RELEASED' and r['order'] > reached['order'])
    boundary = next(r for r in reversed(rows[:rows.index(reached)]) if r['event'] == reached['cut'])
    need(reached['cut'] == ('READ_BEFORE_CAPTURE' if before_capture else 'READ_CAPTURED'), 'wrong paused read boundary')
    promises = [a.f.inspect(a.raw(r['record']), 'PROMISE') for r in rows
                if reached['order'] < r['order'] < release['order'] and r['event'] == 'FORCE' and r['kind'] == 'PROMISE']
    need(any(p['epoch'] > boundary['epoch'] for p in promises), 'read was not crossed by a forced higher promise')
    callback = [r for r in rows if r['event'] == 'READ_CALLBACK' and r.get('opId') == operation['opId']]
    if before_capture:
        need(operation['outcome'] == 'NOT_APPLICABLE' and operation.get('reasonCode') == 'STALE_EPOCH', 'uncaptured read did not reject the stale epoch')
        need(not callback, 'stale read invoked query callback')
    else:
        need(operation['outcome'] == 'SUCCESS' and len(callback) == 1 and callback[0]['order'] > release['order'], 'captured read did not complete after step-down')
    return dict(status='PASS', cut=reached['cut'], capturedEpoch=boundary['epoch'],
                laterEpoch=max(p['epoch'] for p in promises), outcome=operation['outcome'])


def mutation_cut(root, traces, history, crash):
    encoded = (Path(root) / 'node-1/manifest.gsr').read_bytes()
    manifest = dict(a.f.inspect(encoded, 'MANIFEST'), digest=encoded[16:48].hex())
    rows = [r for r in traces[crash['node']] if r['pid'] == crash['pid'] and r['order'] <= crash['observed']['order']]
    op = next(op for op in history if op['node'] == crash['node'] and op['outcome'] == 'PENDING' and op['kind'] == 'addAll')
    cut = crash['requestedCut']; need(cut in MUTATION_CUTS, 'unknown mutation cut')
    matching = []
    for row in rows:
        if row['event'] == 'FORCE' and row['kind'] == 'ACCEPT':
            vote = a.f.inspect(a.raw(row['record']), 'ACCEPT'); entry = a.f.inspect(a.raw(vote['entry']), 'ENTRY')
            if entry['operation'] == 4 and [dict(id=k, value=v) for k, v in a.documents_command(a.raw(entry['payload']))] == op['documents']:
                matching.append(vote)
    if cut == 'ACCEPT_BEFORE_WRITE':
        need(not matching, 'before-write cut has a forced acceptance')
        return dict(status='PASS', cut=cut, forced=False, clientOutcome=op['outcome'])
    need(len(matching) == 1, 'mutation cut lacks its exact forced entry')
    vote = matching[0]; digest = vote['entryDigest']; index = a.f.inspect(a.raw(vote['entry']), 'ENTRY')['index']
    proofs = {a.storage.sha(a.raw(r['record'])): a.f.inspect(a.raw(r['record']), 'PROOF') for r in rows
              if r['event'] == 'FORCE' and r['kind'] == 'PROOF'}
    proofs = {key: proof for key, proof in proofs.items() if proof['entryDigest'] == digest}
    entry_acks = []; proof_acks = []
    # Wire frames are decoded independently, including compact authority records.
    for r in rows:
        if r['event'] != 'RECEIVED': continue
        frame = a.f.wire(a.raw(r['frame']), manifest); payload = frame['payload']
        if frame['type'] == 'ACCEPT_ACK' and payload.get('entryDigest') == digest: entry_acks.append(frame)
        if frame['type'] == 'COMMIT_PROOF_ACK' and payload.get('index') == index and payload.get('proofDigest') in proofs: proof_acks.append(frame)
    stage = MUTATION_CUTS.index(cut)
    need(bool(entry_acks) == (stage >= 2), 'entry receipt crossed the declared cut')
    need(bool(proofs) == (stage >= 4), 'proof force crossed the declared cut')
    need(bool(proof_acks) == (stage >= 5), 'proof receipt crossed the declared cut')
    for event, threshold in (('BEFORE_PUBLISH', 6), ('PUBLISHED', 7)):
        publications = [a.f.inspect(a.raw(r['snapshot']), 'SNAPSHOT') for r in rows if r['event'] == event]
        target = [p for p in publications if p['anchors'][-1]['entryDigest'] == digest]
        need(bool(target) == (stage >= threshold), 'publication crossed the declared cut: ' + event)
    final = next(op for op in reversed(history) if op['kind'] == 'read' and op['outcome'] == 'SUCCESS')
    included = all(d in final['documents'] for d in op['documents'])
    if stage >= 2: need(included, 'entry quorum value lost after failover')
    return dict(status='PASS', cut=cut, index=index, entryDigest=digest, included=included, clientOutcome=op['outcome'])
