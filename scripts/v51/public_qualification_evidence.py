"""Bind public histories to independently decoded force, quorum and captured bytes."""
import copy
import json
from pathlib import Path
from . import runtime_evidence as authority, public_history
from .storage_harness import need


def traces_at(root):
    return {f'node-{i}': [json.loads(line) for line in (Path(root) / f'node-{i}-trace.jsonl').read_text().splitlines()]
            for i in (1, 2, 3)}


def physical(root, history, traces=None, *, rejected_tails=None, retired_voters=None, process_generations=None, evidence_location=None):
    traces = traces if traces is not None else traces_at(root)
    result = authority.validate(root, traces, rejected_tails=rejected_tails, retired_voters=retired_voters, evidence_location=evidence_location)
    manifest_bytes = (Path(root) / 'node-1/manifest.gsr').read_bytes()
    manifest = authority.f.inspect(manifest_bytes, 'MANIFEST')
    processes = {}
    entries, voters = {}, {}
    for node, rows in traces.items():
        for row in rows:
            need(row['node'] == node and row['groupId'] == manifest['groupId'] and
                 row['manifestDigest'] == manifest_bytes[16:48].hex(), 'trace authority identity')
            process = row['pid'], row['generation']
            need((row['generation'] in (1, 2) if process_generations is None else
                  process_generations.get((node, row['pid'])) == row['generation'])
                 and processes.setdefault((node, row['pid']), process) == process, 'process generation changed')
            if row['event'] == 'FORCE' and row['kind'] == 'ACCEPT':
                vote = authority.f.inspect(authority.raw(row['record']), 'ACCEPT')
                entry = authority.f.inspect(authority.raw(vote['entry']), 'ENTRY')
                digest = vote['entryDigest']; entries[digest] = entry
                voters.setdefault((vote['epoch'], vote['incarnation'], digest), set()).add(node)
    if process_generations is not None:
        need(set(processes) == set(process_generations), 'missing declared process generation')
    chosen = {digest: entries[digest] for (_, _, digest), nodes in voters.items() if len(nodes) >= 2}
    attempts = {op['opId']: op for op in history}
    need(len(attempts) == len(history), 'duplicate client operation')
    seen_success, captured_reads, barriers, invocation_orders, acceptance_orders = {}, {}, set(), {}, {}
    for node, rows in traces.items():
        invocations, forces, publications, current, promises, validated = {}, {}, {}, {}, {}, {}
        pending_backups, released_backups = {}, {}
        for row in rows:
            pid = row['pid']; event = row['event']
            if event == 'CLIENT_INVOKE':
                invocations[(pid, row['opId'])] = row['order']
                if row['kind'] == 'backup':
                    need(pid not in pending_backups, 'overlapping backup fixture')
                    pending_backups[pid] = row['opId']
                invocation_orders[(node, pid, row['opId'])] = row['order']
            elif event == 'FORCE' and row['kind'] == 'PROMISE':
                promise = authority.f.inspect(authority.raw(row['record']), 'PROMISE')
                promises[pid] = promise['epoch']
            elif event == 'FORCE' and row['kind'] == 'ACCEPT':
                vote = authority.f.inspect(authority.raw(row['record']), 'ACCEPT')
                forces.setdefault((pid, vote['entryDigest']), row['order'])
                acceptance_orders.setdefault((node, pid, vote['entryDigest']), row['order'])
            elif event == 'PUBLISHED':
                snapshot = authority.f.inspect(authority.raw(row['snapshot']), 'SNAPSHOT')
                publications[(pid, len(snapshot['anchors']))] = snapshot
            elif event == 'READ_CAPTURE_VALIDATED':
                need(row['epoch'] == promises.get(pid), 'capture after higher promise')
                need(pid not in validated, 'duplicate capture validation')
                validated[pid] = row
            elif event == 'READ_CAPTURED':
                validation = validated.pop(pid, None)
                need(validation is not None and all(validation[k] == row[k] for k in ('epoch', 'index', 'sequence')), 'capture lacks exact validation')
                need(pid not in current, 'overlapping local capture')
                snapshot = publications.get((pid, row['index']))
                need(snapshot is not None and snapshot['applicationSequence'] == row['sequence'], 'capture has no exact publication')
                proof = authority.f.inspect(authority.raw(snapshot['terminalProof']), 'PROOF')
                digest = snapshot['anchors'][-1]['entryDigest']
                need(digest in chosen and chosen[digest]['operation'] == 9 and proof['epoch'] == row['epoch'], 'capture barrier fence')
                need(digest not in barriers, 'read barrier reused'); barriers.add(digest)
                current[pid] = dict(row=validation, snapshot=snapshot, digest=digest, opId=None)
            elif event == 'READ_CALLBACK':
                capture = current.get(pid); key = pid, row['opId']
                need(capture is not None and capture['opId'] is None and key in invocations, 'callback without own capture')
                need(invocations[key] < forces.get((pid, capture['digest']), -1) < capture['row']['order'], 'barrier predates invocation')
                capture['opId'] = row['opId']
            elif event == 'READ_RELEASED':
                capture = current.pop(pid, None)
                need(capture is not None, 'release without captured view')
                if capture['opId'] is None:
                    identity = pending_backups.pop(pid, None)
                    need(identity is not None and (pid, identity) not in released_backups, 'release without captured query or backup')
                    need(invocations[(pid, identity)] < forces.get((pid, capture['digest']), -1) < capture['row']['order'], 'backup barrier predates invocation')
                    released_backups[(pid, identity)] = capture
                    need(all(row[k] == capture['row'][k] for k in ('epoch', 'index', 'sequence')), 'backup release changed view')
                    continue
                need(all(row[k] == capture['row'][k] for k in ('epoch', 'index', 'sequence')), 'release changed view')
                captured_reads[(node, pid, capture['opId'])] = capture
            elif event == 'CLIENT_SUCCESS' and row['kind'] == 'backup':
                capture = released_backups.pop((pid, row['opId']), None)
                need(capture is not None and row['sequence'] == capture['row']['sequence'], 'backup response lacks exact released view')
            elif event == 'CLIENT_SUCCESS' and row['kind'] in ('read', 'addAll'):
                key = node, pid, row['opId']; seen_success[key] = row
                need(row['opId'] in attempts, 'unrecorded client response')
                if row['kind'] == 'read':
                    capture = captured_reads.get(key)
                    need(capture is not None, 'read response before view release')
                    _, docs = authority.application(authority.raw(capture['snapshot']['application']))
                    need(row['documents'] == [dict(id=k, value=v) for k, v in docs.items()], 'read differs from exact captured bytes')
        need(not pending_backups and not released_backups, 'uncompleted backup capture')
    matched = set()
    for op in history:
        key = op['node'], op['pid'], op['opId']
        need(processes.get((op['node'], op['pid'])) == (op['pid'], op['generation']), 'client process identity')
        if op['outcome'] == 'SUCCESS':
            need(key in seen_success and seen_success[key]['documents'] == op['documents'], 'controller response differs from worker')
        if op['kind'] == 'addAll':
            matches = [digest for digest, entry in chosen.items() if entry['operation'] == 4 and
                       [dict(id=k, value=v) for k, v in authority.documents_command(authority.raw(entry['payload']))] == op['documents']]
            need(len(matches) <= 1, 'uncertain mutation replayed')
            if op['outcome'] == 'SUCCESS': need(len(matches) == 1, 'successful bulk missing from chosen history')
            if op['outcome'] in ('NOT_SUBMITTED', 'VALIDATION_FAILURE'): need(not matches, 'rejected mutation has an effect')
            for digest in matches:
                need(key in invocation_orders and invocation_orders[key] < acceptance_orders.get((op['node'], op['pid'], digest), -1), 'chosen mutation precedes its invocation')
            matched.update(matches)
    need(all(entry['operation'] == 9 or digest in matched for digest, entry in chosen.items()), 'unattributed chosen mutation')
    return dict(result, execution='public-concurrent-history-real-tcp', publicRuntime=True,
                capturedReads=len(captured_reads), attemptedOperations=len(history))


def negatives(root, history, initial_documents=None, *, rejected_tails=None, retired_voters=None, process_generations=None, max_operations=24):
    original = traces_at(root); cases = []
    target = next(op for op in reversed(history) if op['kind'] == 'read' and op['outcome'] == 'SUCCESS')
    for name, docs in [('stale-read', []), ('partial-atomic-bulk', target['documents'][1:]),
                       ('changed-document-order', target['documents'][::-1])]:
        changed = copy.deepcopy(history); traces = copy.deepcopy(original)
        next(op for op in changed if op['opId'] == target['opId'])['documents'] = docs
        for rows in traces.values():
            for row in rows:
                if row.get('opId') == target['opId'] and row['event'] == 'CLIENT_SUCCESS': row['documents'] = docs
        rejected = []
        for label, verify in [('client-history', lambda: public_history.check(changed, initial_documents=initial_documents, max_operations=max_operations)),
                              ('chosen-and-captured-bytes', lambda: physical(root, changed, traces, rejected_tails=rejected_tails, retired_voters=retired_voters, process_generations=process_generations))]:
            try: verify()
            except ValueError as error: rejected.append(dict(checker=label, reason=str(error)))
            else: raise ValueError(name + ' admitted by ' + label)
        cases.append(dict(case=name, rejected=rejected))
    # Causal negatives are outside the history-only oracle's input vocabulary.
    for name in ('borrowed-barrier', 'missing-proof-force'):
        traces = copy.deepcopy(original)
        if name == 'borrowed-barrier':
            rows = traces[target['node']]
            row = next(r for r in rows if r['event'] == 'CLIENT_INVOKE' and r.get('opId') == target['opId'])
            rows.remove(row)
            callback = next(i for i, r in enumerate(rows) if r['event'] == 'READ_CALLBACK' and r.get('opId') == target['opId'])
            rows.insert(callback, row)
            # Keep a valid local event ordering while making the invocation follow capture.
            counters = {}
            for own in rows:
                counters[own['pid']] = counters.get(own['pid'], 0) + 1
                own['order'] = counters[own['pid']]
        else:
            traces = {n: [r for r in rows if r['event'] != 'FORCE' or r['kind'] != 'PROOF'] for n, rows in traces.items()}
        try: physical(root, history, traces, rejected_tails=rejected_tails, retired_voters=retired_voters, process_generations=process_generations)
        except ValueError as error: cases.append(dict(case=name, rejected=[dict(checker='chosen-and-captured-bytes', reason=str(error))]))
        else: raise ValueError(name + ' admitted')
    return cases
