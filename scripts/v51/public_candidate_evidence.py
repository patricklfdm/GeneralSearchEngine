"""Independent candidate crash, ballot reuse and wire-order evidence checks."""
import copy
import json
from pathlib import Path
from . import public_promise_evidence as promises
from . import runtime_evidence as a
from .public_protocol_evidence import crash_rows
from .storage_harness import need

BOUNDARIES = {'before-write': 'PROMISE_BEFORE_WRITE', 'after-write': 'PROMISE_AFTER_WRITE',
              'after-force': 'PROMISE_AFTER_FORCE', 'before-ack': 'PROMISE_BEFORE_ACK',
              'basis-ack': 'BASIS_BEFORE_ACK', 'before-prepare': 'WIRE_BEFORE_REQUEST_WRITE_PREPARE',
              'after-promise': 'WIRE_AFTER_RESPONSE_READ_PREPARE:PROMISE'}


def prepare_order(forces, bases, messages):
    need(messages and all(any(force < basis < message for force in forces for basis in bases)
                          for message in messages), 'message precedes forced promise/frozen basis')


def fresh_campaigns(retained, later, node):
    """A restarted campaign advances every retained grant, with a fresh incarnation."""
    need(later, 'missing restarted self campaign')
    old_epoch = retained[-1]['epoch']; old_incarnations = {v['incarnation'] for v in retained}
    epochs = {}; incarnations = {}
    for value in later:
        need(value['proposer'] == node and value['epoch'] > old_epoch, 'restarted candidate reused a retained epoch')
        need(value['incarnation'] not in old_incarnations, 'restarted candidate reused a retained incarnation')
        identity = a.storage.ballot(value)
        need(value['epoch'] not in epochs or epochs[value['epoch']] == identity, 'changed same-epoch campaign')
        need(value['incarnation'] not in incarnations or incarnations[value['incarnation']] == value['epoch'], 'incarnation reused across campaigns')
        need(not epochs or value['epoch'] >= max(epochs), 'campaign epoch moved backwards')
        epochs[value['epoch']] = identity; incarnations[value['incarnation']] = value['epoch']
    return sorted(epochs)


def restart_schedule(starts, history, traces, receipt):
    node = receipt['crash']['node']; old = receipt['oldLeader']
    need(len(starts) == 5 and len({s['pid'] for s in starts}) == 5, 'candidate process start inventory')
    for row in starts:
        need(row['startNanos'] <= row['readyNanos'] and any(r['event'] == 'STARTED' and r['pid'] == row['pid']
             and r['generation'] == row['generation'] for r in traces[row['node']]), 'unbound public process start')
    restarted = next((s for s in starts if s['node'] == node and s['generation'] == 2), None)
    restored = next((s for s in starts if s['node'] == old and s['generation'] == 2), None)
    op = next((h for h in history if h['opId'] == receipt['postRestartWrite']), None)
    need(restarted and restored and op, 'missing restart/majority write')
    need(op['kind'] == 'addAll' and op['outcome'] == 'SUCCESS' and op['node'] == node and op['pid'] == restarted['pid']
         and restarted['readyNanos'] < op['startNanos'] < op['endNanos'] < restored['startNanos'], 'old leader returned before restarted-candidate write')
    reads = [r for r in history if r['kind'] == 'read' and r['outcome'] == 'SUCCESS' and r['pid'] == restarted['pid']
             and op['endNanos'] < r['startNanos'] < r['endNanos'] < restored['startNanos']]
    need(reads and all(d in reads[-1]['documents'] for d in op['documents']), 'missing candidate read before old leader restart')
    return op


def validate(root, traces, history, receipt, starts=None):
    root = Path(root); stage, mode = receipt['case'].rsplit('-', 1); crash = receipt['crash']; node = crash['node']
    need(stage in BOUNDARIES and crash['cut'] == BOUNDARIES[stage] and mode == crash['mode']
         and node in ('node-1', 'node-2') and node != receipt['oldLeader'], 'wrong candidate scenario')
    before = crash_rows(traces, crash); manifest = promises.sealed_schedule(root, node)
    files = promises.retained_files(root, node, receipt['retained'])
    previous = next((r for r in reversed(before) if r['event'] == 'PROMISE_BEFORE_WRITE'), None)
    need(previous is not None, 'missing candidate pre-write journal')
    initial = a.raw(previous['journal']); retained = files['promises.gsr']; final = (root/node/'promises.gsr').read_bytes()
    old = promises.journal(initial, manifest, node); saved = promises.journal(retained, manifest, node)
    final_rows = promises.journal(final, manifest, node); written = stage != 'before-write'
    promises.extension(initial, retained, final, written)
    need(len(saved) == len(old)+written, 'candidate appended multiple promises at crash')
    old_bytes, prior = old[-1]; saved_bytes, ballot = saved[-1]
    need(any(r['event'] == 'FORCE' and r['kind'] == 'PROMISE' and a.raw(r['record']) == old_bytes
             and r['order'] < previous['order'] for r in before), 'missing prior durable candidate promise')
    if written: need(ballot['proposer'] == node, 'interrupted grant belongs to a peer campaign')
    forced = [r for r in before if r['event'] == 'FORCE' and r['kind'] == 'PROMISE'
              and a.raw(r['record']) == saved_bytes and r['order'] > previous['order']]
    need(bool(forced) == (stage not in ('before-write', 'after-write')), 'candidate promise force ordering')
    if stage not in ('before-prepare', 'after-promise'):
        need(a.raw(before[-1]['journal']) == retained, 'candidate cut journal differs from retained bytes')
    def wire(row, key='request'): return a.f.wire(a.raw(row[key]), manifest)
    outgoing = [r for r in before if r['event'] == 'WIRE_BEFORE_REQUEST_WRITE_PREPARE' and wire(r)['epoch'] > prior['epoch']]
    need(bool(outgoing) == (stage in ('before-prepare', 'after-promise')), 'PREPARE escaped candidate storage crash')
    for row in outgoing:
        req = wire(row)
        need(req['type'] == 'PREPARE' and req['sender'] == req['proposer'] == node
             and (req['epoch'], req['proposer'], req['incarnationId']) == a.storage.ballot(ballot)
             and forced and forced[-1]['order'] < row['order'], 'PREPARE lacks its exact prior self force')
    if outgoing:
        ready = [r['order'] for r in before if r['event'] == 'BASIS_BEFORE_ACK' and a.raw(r['journal']) == retained]
        prepare_order([r['order'] for r in forced], ready, [r['order'] for r in outgoing])
        if stage == 'before-prepare': need(len(outgoing) == 1, 'cut was not before the first PREPARE')
    frozen = []
    if stage in ('basis-ack', 'before-prepare', 'after-promise'):
        for path, data in files.items():
            if not (path.startswith('basis/') and path.endswith('/basis.gsr')): continue
            basis = a.f.contextual_frame(data, 'BASIS', manifest)
            if a.storage.ballot(basis['ballot']) != a.storage.ballot(ballot): continue
            a.recovery.basis(data, files[path.removesuffix('basis.gsr')+'image.gsr'], manifest)
            need(basis['node'] == node, 'candidate basis belongs to another voter'); frozen.append(data)
        need(len(frozen) == 1, 'missing exact frozen candidate basis')
    peer_grants = []
    for owner, rows in traces.items():
        for row in rows:
            if row['event'] != 'FORCE' or not written: continue
            if row['kind'] == 'PROMISE' and owner != node and a.raw(row['record']) == saved_bytes: peer_grants.append((owner, row))
            if row['kind'] in ('ACCEPT', 'PROOF'):
                value = a.f.inspect(a.raw(row['record']), row['kind'])
                need(value['epoch'] != ballot['epoch'], 'interrupted candidate already activated/accepted')
    need(bool(peer_grants) == (stage == 'after-promise'), 'peer grant crossed the declared candidate cut')
    if stage == 'after-promise':
        boundary = before[-1]; req = wire(boundary); response = wire(boundary, 'frame')
        need(response['type'] == 'PROMISE' and response['recipient'] == node and response['sender'] == req['recipient']
             and all(req[k] == response[k] for k in ('traceId', 'eventSequence', 'epoch', 'proposer', 'incarnationId')), 'uncorrelated candidate PROMISE reply')
        need(any(r['request'] == boundary['request'] for r in outgoing), 'received PROMISE lacks outbound PREPARE')
        peer = response['sender']; replies = [r for r in traces[peer] if r['event'] == 'REPLY'
                                             and r['request'] == boundary['request'] and r['frame'] == boundary['frame']]
        need(replies and any(owner == peer and force['pid'] == reply['pid'] and force['order'] < reply['order']
                            for owner, force in peer_grants for reply in replies), 'peer reply lacks same-process promise force')
        for reply in replies:
            ready = [r['order'] for r in traces[peer] if r['event'] == 'BASIS_BEFORE_ACK' and r['pid'] == reply['pid']
                     and promises.journal(a.raw(r['journal']), manifest, peer)[-1][0] == saved_bytes]
            prepare_order([r['order'] for owner, r in peer_grants if owner == peer and r['pid'] == reply['pid']], ready, [reply['order']])
        basis = a.f.contextual_frame(a.raw(response['payload']['basis']), 'BASIS', manifest)
        need(basis['node'] == peer and a.storage.ballot(basis['ballot']) == a.storage.ballot(ballot), 'peer frozen basis ballot mismatch')
    campaigns = []
    for row in traces[node]:
        if row['generation'] != 2 or row['event'] != 'FORCE' or row['kind'] != 'PROMISE': continue
        value = a.f.contextual_frame(a.raw(row['record']), 'PROMISE', manifest)
        if value['proposer'] == node: campaigns.append(value)
    epochs = fresh_campaigns([v for _, v in saved], campaigns, node)
    need(all(value in [v for _, v in final_rows] for value in campaigns), 'new campaign absent from retained journal')
    op = restart_schedule(json.loads((root/'worker-starts.json').read_text()) if starts is None else starts, history, traces, receipt)
    votes = []
    for row in traces[node]:
        if row['generation'] != 2 or row['event'] != 'FORCE' or row['kind'] != 'ACCEPT': continue
        vote = a.f.contextual_frame(a.raw(row['record']), 'ACCEPT', manifest); entry = a.f.contextual_frame(a.raw(vote['entry']), 'ENTRY', manifest)
        if entry['operation'] == 4 and [dict(id=k, value=v) for k, v in a.documents_command(a.raw(entry['payload']))] == op['documents']:
            need(vote['epoch'] in epochs and vote['proposer'] == node, 'recovered write lacks new self campaign'); votes.append(vote)
    need(votes, 'restarted candidate did not force its public write')
    return dict(status='PASS', priorEpoch=prior['epoch'], retainedEpoch=ballot['epoch'], written=written,
                forced=bool(forced), frozenBasis=bool(frozen), peerGranted=bool(peer_grants), restartedEpochs=epochs, candidate=node)


def negatives(root, traces, history, receipt):
    node = receipt['crash']['node']; stage = receipt['case'].rsplit('-', 1)[0]
    removals = [('missing-cut', lambda r: r['event'] == 'CUT_REACHED'),
                ('missing-boundary', lambda r: r['event'] == receipt['crash']['cut'].split(':')[0]),
                ('missing-prewrite', lambda r: r['event'] == 'PROMISE_BEFORE_WRITE'),
                ('missing-self-force', lambda r: r['event'] == 'FORCE' and r['kind'] == 'PROMISE' and r['generation'] == 1),
                ('missing-restart', lambda r: r['event'] == 'STARTED' and r['generation'] == 2),
                ('missing-new-campaign', lambda r: r['event'] == 'FORCE' and r['kind'] == 'PROMISE' and r['generation'] == 2),
                ('missing-new-acceptance', lambda r: r['event'] == 'FORCE' and r['kind'] == 'ACCEPT' and r['generation'] == 2)]
    changes = []
    for name, remove in removals:
        changed = copy.deepcopy(traces); changed[node] = [r for r in changed[node] if not remove(r)]
        changes.append((name, changed, receipt, None))
    changed = copy.deepcopy(receipt); changed['retained']['sha256'] = '0'*64
    changes.append(('wrong-archive', traces, changed, None))
    changed = copy.deepcopy(receipt); changed['case'] = ('after-write' if stage == 'before-write' else 'before-write')+'-'+receipt['crash']['mode']
    changes.append(('wrong-scenario', traces, changed, None))
    starts = json.loads((Path(root)/'worker-starts.json').read_text())
    for row in starts:
        if row['node'] == receipt['oldLeader'] and row['generation'] == 2: row['startNanos'] = 0
    changes.append(('old-leader-present-too-early', traces, receipt, starts))
    if stage == 'after-promise':
        changed = {n: [r for r in rows if n == node or r['event'] != 'REPLY'] for n, rows in traces.items()}
        changes.append(('missing-peer-reply', changed, receipt, None))
        changed = {n: [r for r in rows if n == node or not (r['event'] == 'FORCE' and r['kind'] == 'PROMISE')] for n, rows in traces.items()}
        changes.append(('missing-peer-force', changed, receipt, None))
        changed = {n: [r for r in rows if n == node or r['event'] != 'BASIS_BEFORE_ACK'] for n, rows in traces.items()}
        changes.append(('missing-peer-basis-publication', changed, receipt, None))
    if stage in ('before-prepare', 'after-promise'):
        changed = copy.deepcopy(traces); changed[node] = [r for r in changed[node] if r['event'] != 'BASIS_BEFORE_ACK']
        changes.append(('missing-self-basis-publication', changed, receipt, None))
    results = []
    for name, changed, claim, starts in changes:
        try: validate(root, changed, history, claim, starts)
        except ValueError as error: results.append(dict(case=name, status='REJECTED', reason=str(error)))
        else: raise ValueError('candidate oracle admitted '+name)
    return results
