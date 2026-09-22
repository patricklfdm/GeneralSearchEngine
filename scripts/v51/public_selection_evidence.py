"""Read-only selection oracle over raw frozen bases, forced votes and wire events."""
import copy
import json
from pathlib import Path
from . import runtime_evidence as a
from .public_promise_evidence import retained_files, sealed_schedule
from .public_protocol_evidence import ranges
from .storage_harness import need

BOUNDARIES = {'higher-ballot-accept': 'WIRE_AFTER_RESPONSE_READ_ACCEPT',
              'higher-ballot-proof': 'WIRE_AFTER_RESPONSE_READ_COMMIT_PROOF',
              'hidden-proof': 'WIRE_BEFORE_REQUEST_WRITE_COMMIT_PROOF',
              'epoch-during-basis': 'WIRE_BEFORE_RESPONSE_WRITE_BASIS_CHUNK:continuation'}
CASES = {'duplicate-prepare', 'lagging-candidate', *BOUNDARIES}


def paused(rows, observed, boundary):
    """Only compare sequence numbers within one process; never compare JVM clocks."""
    own = [r for r in rows if r['pid'] == observed['pid']]
    need(sum(r['event'] == 'CUT_REACHED' for r in own) == 1
         and observed in own and observed['event'] == 'CUT_REACHED' and observed['mode'] == 'pause'
         and observed['cut'] == boundary, 'missing exact selection pause')
    event, _, detail = boundary.partition(':')
    before = [r for r in own if r['order'] < observed['order']]
    need(before and before[-1]['event'] == event and (not detail or before[-1].get('cut') == detail),
         'selection pause lacks exact wire boundary')
    released = [r for r in own if r['event'] == 'CUT_RELEASED' and r['cut'] == event and r['order'] > observed['order']]
    need(len(released) == 1, 'selection pause not released once')
    return before[-1], released[0], own


def higher_between(rows, pause, released, observed, epoch):
    need(observed in rows and observed['event'] == 'FORCE' and observed['kind'] == 'PROMISE'
         and observed['pid'] == pause['pid'] == released['pid']
         and pause['order'] < observed['order'] < released['order'], 'higher promise did not cross held exchange')
    value = a.f.inspect(a.raw(observed['record']), 'PROMISE')
    need(value['epoch'] > epoch, 'held exchange not fenced by higher epoch')
    return value


def retry_identity(lost, reply, received):
    need(reply['pid'] == lost['pid'] and reply['order'] > lost['order']
         and reply['request'] == lost['request'] == received['request']
         and reply['frame'] == lost['frame'] == received['frame'], 'duplicate PREPARE changed frozen reply or correlation')


def validate(root, traces, history, receipt):
    root = Path(root); case = receipt['case']; need(case in CASES, 'unknown selection case')
    manifest = sealed_schedule(root, 'node-3')
    wire = lambda row, key='frame': a.f.wire(a.raw(row[key]), manifest)
    old = receipt['oldLeader']; candidate = receipt['candidate']
    need(old != candidate and {old, candidate} == {'node-1', 'node-2'}, 'selection candidate identity')
    retained_files(root, old, receipt['retained'])
    starts = [r for r in traces[old] if r['event'] == 'STARTED']
    need(len(starts) == 2 and {r['generation'] for r in starts} == {1, 2}
         and starts[0]['pid'] != starts[1]['pid'], 'missing retained public restart')
    recorded = json.loads((root/'worker-starts.json').read_text())
    need(all(any(s['node'] == old and s['pid'] == r['pid'] and s['generation'] == r['generation']
                 and s['startNanos'] < s['readyNanos'] for s in recorded) for r in starts), 'restart process binding')
    operations = {op['opId']: op for op in history}
    final = operations[receipt['finalRead']]; later = operations[receipt['laterWrite']]
    need(final['kind'] == 'read' and final['outcome'] == 'SUCCESS' and final['documents'] == receipt['expected']
         and later['kind'] == 'addAll' and later['outcome'] == 'SUCCESS'
         and later['endNanos'] < final['startNanos'], 'missing post-recovery public service')

    replies = [(node, row, wire(row), wire(row, 'request')) for node, rows in traces.items()
               for row in rows if row['event'] == 'REPLY']
    descriptors = {}; chunks = {}; selections = {}
    for _, _, response, _ in replies:
        payload = response['payload']; kind = response['type']
        for encoded in ([payload['basis']] if kind == 'PROMISE' else payload['bases'] if kind == 'SELECTED_OFFER' else []):
            descriptor = a.frame(encoded, 'BASIS', manifest); key = descriptor['node'], descriptor['basisId']
            need(key not in descriptors or descriptors[key] == encoded, 'changed frozen descriptor')
            descriptors[key] = encoded
        if kind == 'BASIS_CHUNK' and payload['action'] == 'DATA':
            chunks.setdefault((response['sender'], payload['basisId']), []).append((payload['offset'], a.raw(payload['chunk'])))
        if kind == 'SELECTED_OFFER' and payload['response']:
            selected = a.frame(payload['selected'], 'SELECTED', manifest)
            selections[payload['selected']] = selected
    verified = []
    for selected in selections.values():
        bases = []
        for binding in selected['bases']:
            key = binding['node'], binding['basisId']; need(key in descriptors and key in chunks, 'missing selection transfer')
            encoded = a.raw(descriptors[key]); descriptor = a.f.contextual_frame(encoded, 'BASIS', manifest)
            need(encoded[16:48].hex() == binding['basisDigest'], 'selected descriptor digest')
            bases.append(a.recovery.basis(encoded, ranges(chunks[key], descriptor['imageBytes']), manifest))
        a.recovery.select(selected, bases, manifest); verified.append((selected, bases))
    need(verified, 'missing independently reconstructed selection')

    if case == 'duplicate-prepare':
        lost = [r for r in traces['node-3'] if r['event'] == 'PROMISE_REPLY_LOST']
        need(len(lost) == 1, 'missing single lost PROMISE'); lost = lost[0]
        req, response = wire(lost, 'request'), wire(lost)
        need(req['type'] == 'PREPARE' and response['type'] == 'PROMISE' and req['sender'] == candidate, 'lost promise identity')
        matching = [r for n, r, _, _ in replies if n == 'node-3' and r['request'] == lost['request'] and r['order'] > lost['order']]
        received = [r for r in traces[candidate] if r['event'] == 'RECEIVED' and r['request'] == lost['request']]
        need(matching and received, 'lost PROMISE not retried and received'); retry_identity(lost, matching[0], received[0])
        forced = [r for r in traces['node-3'] if r['pid'] == lost['pid'] and r['event'] == 'FORCE' and r['kind'] == 'PROMISE'
                  and a.f.inspect(a.raw(r['record']), 'PROMISE')['epoch'] == req['epoch']]
        need(len(forced) == 1 and forced[0]['order'] < lost['order'], 'duplicate PREPARE appended/replaced promise')
        descriptor = a.frame(response['payload']['basis'], 'BASIS', manifest)
        need(any(s['ballot']['epoch'] == req['epoch'] and any(b[0] == descriptor for b in bases) for s, bases in verified),
             'retried frozen basis not used in selection')
        return dict(status='PASS', epoch=req['epoch'], basisId=descriptor['basisId'], exactRetry=True)

    if case == 'lagging-candidate':
        op = operations[receipt['advancedWrite']]
        need(op['outcome'] == 'SUCCESS' and op['node'] == old and receipt['laggingIndex'] < receipt['advancedIndex'], 'missing advanced acknowledged prefix')
        matches = []
        for selected, bases in verified:
            own = [b for b in bases if b[0]['node'] == candidate]
            remote = [b for b in bases if b[0]['node'] == 'node-3']
            if selected['ballot']['proposer'] == candidate and own and remote:
                low, high = len(own[0][1]['anchors']), len(remote[0][1]['anchors'])
                if low <= receipt['laggingIndex'] < receipt['advancedIndex'] <= high == selected['prefixIndex']:
                    _, documents = a.application(a.raw(remote[0][1]['application']))
                    need(all(documents.get(d['id']) == d['value'] for d in op['documents']), 'advanced basis omitted successful write')
                    matches.append((low, high))
        need(matches and receipt['recoveredLeader'] == candidate, 'lagging candidate did not adopt higher proven basis')
        return dict(status='PASS', candidate=candidate, ownPrefix=matches[0][0], selectedPrefix=matches[0][1])

    node = 'node-3' if case == 'epoch-during-basis' else old
    boundary, released, own = paused(traces[node], receipt['pause'], BOUNDARIES[case])
    req = wire(boundary, 'request'); epoch = req['epoch']; need(epoch == receipt['oldEpoch'], 'held epoch identity')
    promise = higher_between(own, receipt['pause'], released, receipt['higherPromise'], epoch)
    if case == 'epoch-during-basis':
        p = req['payload']; need(req['type'] == 'BASIS_CHUNK' and p['offset'] > 0, 'basis was not partially downloaded')
        prefix = ranges([(response['payload']['offset'], a.raw(response['payload']['chunk'])) for n, r, response, _ in replies
                         if n == node and r['pid'] == boundary['pid'] and r['order'] < boundary['order']
                         and response['type'] == 'BASIS_CHUNK' and response['payload']['basisId'] == p['basisId']], p['offset'])
        key = node, p['basisId']; need(key in descriptors, 'missing interrupted descriptor')
        descriptor = a.frame(descriptors[key], 'BASIS', manifest)
        need(descriptor['ballot']['epoch'] == epoch and descriptor['imageBytes'] > len(prefix), 'wrong interrupted basis')
        need(not any(n == node and r['pid'] == boundary['pid'] and r['order'] < receipt['higherPromise']['order']
                     and response['type'] == 'BASIS_CHUNK' and response['payload']['basisId'] == p['basisId']
                     and response['payload']['offset'] >= len(prefix) for n, r, response, _ in replies),
             'basis download completed past pause before higher promise')
        need(any(n == node and r['pid'] == boundary['pid'] and r['order'] > released['order']
                 and r['request'] == boundary['request'] and r['frame'] == boundary['frame'] for n, r, _, _ in replies),
             'held basis reply never released')
        need(not any(n == node and r['pid'] == boundary['pid'] and r['order'] > receipt['higherPromise']['order']
                     and response['type'] == 'SELECTED_OFFER' and response['payload']['response']
                     and request['epoch'] == epoch for n, r, response, request in replies), 'retired basis activated after higher promise')
        need(any(s['ballot']['epoch'] >= promise['epoch'] and all(b[0]['basisId'] != p['basisId'] for b in bases)
                 for s, bases in verified), 'no fresh selection after basis invalidation')
        return dict(status='PASS', retiredEpoch=epoch, promisedEpoch=promise['epoch'], interruptedBytes=len(prefix))

    op = operations[receipt['heldOperation']]
    need(op['outcome'] == 'INDETERMINATE' and op['node'] == old, 'held mutation falsely completed')
    votes = []
    for n, rows in traces.items():
        for r in rows:
            if r['event'] != 'FORCE' or r['kind'] != 'ACCEPT': continue
            vote = a.frame(r['record'], 'ACCEPT', manifest); entry = a.frame(vote['entry'], 'ENTRY', manifest)
            if entry['operation'] == 4 and [dict(id=k, value=v) for k, v in a.documents_command(a.raw(entry['payload']))] == op['documents']:
                votes.append((n, r, vote, entry))
    original = [v for v in votes if v[0] == old and v[2]['epoch'] == epoch and v[1]['order'] < boundary['order']]
    need(len(original) == 1, 'missing original held acceptance'); _, _, vote, entry = original[0]
    need({v[0] for v in votes if v[2]['epoch'] == epoch} >= {old}
         and len({v[0] for v in votes if v[2]['epoch'] == epoch}) >= 2, 'held entry was not chosen')
    need(all(v[2]['entry'] == vote['entry'] for v in votes), 'chosen bytes changed at higher acceptance')
    target = (a.frame(a.frame(req['payload']['acceptance'], 'ACCEPT', manifest)['entry'], 'ENTRY', manifest)
              if req['type'] == 'ACCEPT' else a.frame(req['payload']['proof'], 'PROOF', manifest))
    need(target['index'] == entry['index'] and (target == entry if req['type'] == 'ACCEPT' else target['entryDigest'] == vote['entryDigest']), 'pause caught different mutation')
    higher_selected = [(s, b) for s, b in verified if s['ballot']['epoch'] > epoch and old not in {v[0]['node'] for v in b}]
    if case == 'higher-ballot-proof':
        need(any(s['prefixIndex'] >= entry['index'] for s, _ in higher_selected), 'survivor did not recover proven held entry')
    else:
        need(any(s['prefixIndex'] == entry['index']-1 and s['nextEntry'] == vote['entry'] for s, _ in higher_selected), 'survivor did not select exact unknown chosen entry')
    proofs = [(n, r, a.frame(r['record'], 'PROOF', manifest)) for n, rows in traces.items() for r in rows if r['event'] == 'FORCE' and r['kind'] == 'PROOF']
    original_proofs = [(n, r) for n, r, proof in proofs if proof['epoch'] == epoch and proof['index'] == entry['index']]
    if case == 'hidden-proof':
        need(original_proofs and all(n == old and r['order'] < boundary['order'] for n, r in original_proofs), 'proof was not hidden on old leader')
    if case == 'higher-ballot-accept': need(not original_proofs, 'old acceptance unexpectedly proved')
    if case.startswith('higher-ballot-'):
        need(any(r['event'] == 'RECEIVED' and r['order'] > released['order'] and r['request'] == boundary['request']
                 and r['frame'] == boundary['frame'] for r in own), 'held ACK did not cross higher promise')
    for r in own:
        if r['order'] > receipt['higherPromise']['order'] and r['event'] == 'PUBLISHED':
            snapshot = a.frame(r['snapshot'], 'SNAPSHOT', manifest)
            need(a.frame(snapshot['terminalProof'], 'PROOF', manifest)['epoch'] > epoch, 'stale leader published after fencing')
    majority = operations[receipt['majorityRead']]; write = operations[receipt['majorityWrite']]
    need(majority['outcome'] == write['outcome'] == 'SUCCESS' and majority['node'] != old and write['node'] != old
         and all(d in majority['documents'] for d in op['documents']), 'chosen unknown missing from surviving public majority')
    return dict(status='PASS', index=entry['index'], originEpoch=entry['originEpoch'], retiredEpoch=epoch,
                promisedEpoch=promise['epoch'], entryDigest=vote['entryDigest'])


def negatives(root, traces, history, receipt):
    case = receipt['case']
    changes = [('missing-restart', lambda r: r['event'] == 'STARTED' and r['generation'] == 2),
               ('missing-selection', lambda r: r['event'] == 'REPLY' and json.loads(a.raw(r['frame'])[48:])['type'] == 'SELECTED_OFFER')]
    if case == 'duplicate-prepare':
        changes += [('missing-lost-promise', lambda r: r['event'] == 'PROMISE_REPLY_LOST'),
                    ('missing-retry-receipt', lambda r: r['event'] == 'RECEIVED' and json.loads(a.raw(r['frame'])[48:])['type'] == 'PROMISE')]
    elif case in BOUNDARIES:
        changes += [('missing-pause', lambda r: r['event'] == 'CUT_REACHED'),
                    ('missing-release', lambda r: r['event'] == 'CUT_RELEASED'),
                    ('missing-higher-promise', lambda r: r == receipt['higherPromise'])]
        if case == 'epoch-during-basis':
            changes.append(('missing-basis-prefix', lambda r: r['event'] == 'REPLY' and json.loads(a.raw(r['frame'])[48:])['type'] == 'BASIS_CHUNK'))
        else: changes.append(('missing-entry-force', lambda r: r['event'] == 'FORCE' and r['kind'] == 'ACCEPT'))
    results = []
    for name, remove in changes:
        changed = {n: [r for r in rows if not remove(r)] for n, rows in traces.items()}
        try: validate(root, changed, history, receipt)
        except ValueError as error: results.append(dict(case=name, status='REJECTED', reason=str(error)))
        else: raise ValueError('selection oracle admitted '+name)
    altered = copy.deepcopy(receipt); altered['expected'] = []
    try: validate(root, traces, history, altered)
    except ValueError as error: results.append(dict(case='changed-final-projection', status='REJECTED', reason=str(error)))
    else: raise ValueError('selection oracle admitted changed-final-projection')
    return results
