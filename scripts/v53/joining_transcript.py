"""Shared original transport/transfer replay, independent of physical inventory gates."""
import base64
import hashlib
from collections import defaultdict, deque
from . import joining_phase_evidence as phase
from . import joining_attempts
from . import segmented_transcript

f, need, sha = phase.f, phase.need, phase.sha
wire = phase.exchange.d.transfer.t.wire
SENDS = {'NETWORK_SEND', 'BEFORE_REQUEST_WRITE'}
READS = {'NETWORK_REQUEST', 'AFTER_REQUEST_READ'}


def causal(events, wires, identities, root, *, transfer_only=False, failed=None):
    """Consume each actual send, server read, response and client read once.

    Require complete delivery except for independently bound failed control
    attempts and one explicitly declared initial learner-source loss, paired
    with its next identical successful retry. Failures are never ACK rows.
    Publication may explicitly request only transfer causality; this leaves
    control-attempt qualification to the separate complete-network gate.
    """
    from . import joining_connections
    if joining_connections.present(events,wires):
        result=joining_connections.replay(events,wires,identities,root)
        if failed is not None and not transfer_only:failed.extend(result['failed'])
        return [v for v in result['rows'] if not transfer_only or v['kind'] in ('CHUNK','TRANSFER_COMMIT')]
    rows = phase.exchanges(events, wires, identities, root)
    failures = {} if transfer_only else joining_attempts.failures(events,rows,identities,root)
    completions = defaultdict(list)
    for value in failures.values():
        if not value['withheldResponse']:completions[value['finished']].append(value)
    if transfer_only: rows = [v for v in rows if v['kind'] in ('CHUNK', 'TRANSFER_COMMIT')]
    offers = {v['offered']: v for v in rows}
    pending, accepted = defaultdict(deque), defaultdict(deque)
    sends = reads = 0; live = {}
    for at, row in enumerate(events):
        event = row.get('event')
        if event in SENDS:
            scoped = event == 'BEFORE_REQUEST_WRITE'
            need(set(row) == {'node', 'event', 'request', 'kind', 'bytes'} | ({'scope'} if scoped else set()),
                 'joining network send shape')
            kind, request = wire(row['bytes']); raw = base64.b64decode(row['bytes'], validate=True)
            sender, peer = request['sender']['node'], request['recipient']['node']
            need(sha(raw) == row['request'] and kind == row['kind'], 'joining network send bytes')
            need(row['node'] == sender and sender != peer and request['root'] == root and
                 request['sender'] == identities.get(sender) and request['recipient'] == identities.get(peer),
                 'joining network send identity')
            if transfer_only and kind not in ('CHUNK', 'TRANSFER_COMMIT'): continue
            prior = live.get(row['request'])
            need(prior is None or prior.get('finished', at) < at, 'joining network ambiguous overlapping retry')
            attempt = dict(sent=at, request=request, kind=kind, scope=row.get('scope'))
            live[row['request']] = attempt; pending[row['request']].append(attempt)
            sends += 1
        elif event in READS:
            scoped = event == 'AFTER_REQUEST_READ'
            need(set(row) == {'node', 'event', 'request', 'kind'} | ({'scope'} if scoped else set()),
                 'joining network request shape')
            if transfer_only and row['kind'] not in ('CHUNK', 'TRANSFER_COMMIT'): continue
            need(pending[row['request']], 'joining network receive without send')
            attempt = pending[row['request']].popleft()
            need(row['node'] == attempt['request']['recipient']['node'] and row['kind'] == attempt['kind'],
                 'joining network request binding')
            attempt.update(received=at, receiverScope=row.get('scope'))
            accepted[row['request']].append(attempt); reads += 1
        if at in offers:
            response = offers[at]; digest = response['requestHash']
            need(accepted[digest], 'joining network response without request')
            attempt = accepted[digest].popleft()
            need(attempt['request'] == response['request'] and attempt['kind'] == response['kind'] and
                 attempt['receiverScope'] == row.get('scope'), 'joining network response request binding')
            response.update(sent=attempt['sent'], received=attempt['received'])
            if response.get('withheld',False):
                need(response['delivered'] is None and response['sent']<response['received']<at,'joining network withheld causal order')
                attempt['finished']=failures.get(attempt['sent'],{}).get('finished',at)
            else:
                need(response['delivered'] is not None, 'joining network undelivered healthy response')
                delivered = events[response['delivered']]
                need(attempt['scope'] == delivered.get('scope'), 'joining network client lifetime')
                attempt['finished'] = response['delivered']
                need(response['sent'] < response['received'] < at < response['delivered'], 'joining network causal order')
        for failure in completions.get(at,[]):
            attempt=live.get(failure['requestHash'])
            need(attempt is not None and attempt['sent']==failure['sent'],'joining failure unmatched live attempt')
            queue=(accepted if failure['received'] is not None else pending)[failure['requestHash']]
            need(queue and queue.popleft() is attempt,'joining failure unmatched received attempt')
            attempt['finished']=failure['finished']
    no_response=[value for value in failures.values() if not value['withheldResponse']]
    need(not any(pending.values()) and not any(accepted.values()) and sends == len(rows)+len(no_response) and
         reads == len(rows)+sum(value['received'] is not None for value in no_response),
         'joining network incomplete healthy exchange')
    phase.loss.requests(events,rows)
    if failed is not None:failed.extend(failures.values())
    return rows


def transfers(rows, *, contents=None):
    """Check bytes/offsets/extent/commit, keeping rejections out of success.

    This proves transcript integrity. An offer's reference alone is not proof
    that its exporter owned that object at this time; that is a separate gate.
    """
    sessions = defaultdict(list)
    for row in rows:
        if row['kind'] not in ('CHUNK', 'TRANSFER_COMMIT'): continue
        q = row['request']
        # Group by trace and endpoints; changing root/view/ballot within a
        # session must fail, rather than silently create a different session.
        sessions[q['sender']['node'], q['recipient']['node'], q['trace']].append(row)
    complete = retries = rejected = total = uncommitted = 0
    for values in sessions.values():
        values.sort(key=lambda v: v['sent']); header = None; prior = None; sequence = 0
        active = None; identifiers = set(); terminal = False
        for ordinal,row in enumerate(values):
            q, a = row['request'], row['response']; qp, ap = q['payload'], a['payload']
            context = {k:v for k,v in q.items() if k not in ('payload', 'sequence')}
            if header is None: header = context
            need(context == header, 'joining network transfer context')
            if row.get('withheld',False):
                need(prior is None or prior['delivered']<row['sent'],'joining network transfer next before delivery')
                need(row['delivered'] is None and ordinal+1<len(values),'joining network unrecovered transfer loss')
                retry=values[ordinal+1]
                need(not retry.get('withheld',False) and retry['delivered'] is not None and row['offered']<retry['sent'] and
                     row['requestHash']==retry['requestHash'] and row['responseHash']==retry['responseHash'] and
                     row['request']==retry['request'] and row['response']==retry['response'],'joining network changed lost transfer retry')
                retries+=1;continue
            if prior is not None:
                need(prior['delivered'] < row['sent'], 'joining network transfer next before delivery')
                if q['sequence'] == sequence:
                    need(row['requestHash'] == prior['requestHash'] and row['responseHash'] == prior['responseHash'],
                         'joining network changed transfer retry')
                    retries += 1; prior = row; continue
            need(not terminal and q['sequence'] == sequence+1, 'joining network transfer sequence')
            sequence += 1
            if row['answer'] == 'REJECT':
                need(active is None and row['kind'] == 'CHUNK' and sequence == 1,
                     'joining network rejected transfer state')
                terminal = True; rejected += 1
            elif row['answer'] == 'SOURCE_OFFER':
                need(active is None and row['kind'] == 'CHUNK' and qp['id'] not in identifiers and
                     qp == dict(id=ap['id'], action='REQUEST', offset=0, digest=qp['digest'], bytes=''),
                     'joining network source offer')
                need(0 <= ap['bytes'] <= 64*phase.semantic.joining.MIB and ap['kind'] in ('RECORD','CAPSULE','APPLICATION'),
                     'joining network transfer bound')
                deferred=type(row) is segmented_transcript.Exchange
                active = dict(ap, offset=0, digest_state=hashlib.sha256(), offer=row,
                    parts=bytearray() if contents is not None and not deferred else None,
                    chunks=[] if contents is not None and deferred else None)
                identifiers.add(qp['id'])
            elif row['answer'] == 'CHUNK':
                need(active is not None and row['kind'] == 'CHUNK', 'joining network chunk without offer')
                offset = active['offset']; chunk = base64.b64decode(ap['bytes'], validate=True)
                need(qp == dict(id=active['id'], action='REQUEST', offset=offset, digest=active['digest'], bytes='') and
                     ap == dict(id=active['id'], action='DATA', offset=offset, digest=sha(chunk), bytes=ap['bytes']) and
                     0 < len(chunk) <= 4*phase.semantic.joining.MIB and offset+len(chunk) <= active['bytes'],
                     'joining network exact transfer chunk')
                active['offset']+=len(chunk);active['digest_state'].update(chunk)
                if active['parts'] is not None:active['parts'].extend(chunk)
                if active['chunks'] is not None:
                    need(type(row) is segmented_transcript.Exchange and row.source is active['offer'].source,
                         'segmented transcript transfer ownership')
                    active['chunks'].append(row)
            else:
                need(active is not None and row['kind'] == row['answer'] == 'TRANSFER_COMMIT',
                     'joining network commit without offer')
                need(qp == ap == dict(id=active['id'], digest=active['digest']) and
                     active['offset'] == active['bytes'] and active['digest_state'].hexdigest() == active['digest'],
                     'joining network complete transfer commit')
                if contents is not None:
                    contents.append(segmented_transcript.Content(active['offer'],row,active['chunks'],active['kind'],active['bytes'],active['digest'])
                        if active['chunks'] is not None else
                        dict(offer=active['offer'],commit=row,raw=bytes(active['parts']),kind=active['kind']))
                total += active['offset']; complete += 1; active = None
            prior = row
        claim=values[0].get('abortedPrefix',{})
        if claim.get('commitPending',False):
            need(active is not None and active['chunks'] is None and
                 claim['request']['payload']==dict(id=active['id'],digest=active['digest']) and
                 active['offset']==active['bytes'] and active['digest_state'].hexdigest()==active['digest'],
                 'joining network uncommitted object bytes')
            # Retain received bytes for independent authority comparison. No
            # commit row is invented, and these bytes never enter contents.
            if contents is not None:
                claim['uncommittedObject']=dict(offer=active['offer'],last=prior,
                    raw=bytes(active['parts']),kind=active['kind'])
            uncommitted+=1
        else:need(active is None, 'joining network incomplete transfer')
    result=dict(transferSessions=len(sessions), committedTransfers=complete, transferredBytes=total,
                exactTransferRetries=retries, rejectedTransferAttempts=rejected)
    if uncommitted:result['uncommittedTransferObjects']=uncommitted
    return result
