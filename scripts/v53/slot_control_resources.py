"""Original slot delivery buffers and socket/local dispatcher waiters.

Requires prior native physical/publication qualification. Allocation labels only
correlate leases; original request bytes and publication images supply authority.
Successful physically qualified slots only; cancellation and whole-runtime maxima remain open.
"""
import base64
from collections import defaultdict
import re
from uuid import UUID

from . import native_source_resources as source
from . import voting_control_resources as voting
from . import publication_resource_evidence as publication

need = source.need
ROLES = {'slot-delivery': 'CONTROL', 'slot-waiter': 'WAITER'}
OWNER = re.compile(r'(slot-delivery|slot-waiter)-([0-9a-f]{64})-([0-9a-f-]{36})\Z')
LEGACY = re.compile(r'(slot-delivery|slot-waiter)-([0-9a-f-]{36})\Z')
KINDS = {'ACCEPT', 'PROOF', 'APPLY'}
INCOMING = KINDS | {'PUBLISH', 'FUTURE_RETENTION_INTENT', 'RETENTION_INTENT'}


def scan(traces):
    leases = {}; legacy = 0
    for node, trace in traces.items():
        source.a.transitions.replay(trace)
        for row in trace['changes']:
            charges = [v for v in row['removed']+row['added'] if any(v['owner'].startswith(role+'-') for role in ROLES)]
            if not charges: continue
            need(len(charges) == 1 and row['event'] in ('RESERVE', 'RELEASE'), 'slot resources immutable allocation')
            charge = charges[0]; match = OWNER.fullmatch(charge['owner']); old = LEGACY.fullmatch(charge['owner'])
            need(match is not None or old is not None, 'slot resources owner binding')
            role = (match or old)[1]; nonce = match[3] if match else old[2]
            need(charge['unit'] == ROLES[role], 'slot resources role/unit')
            try: value = UUID(nonce)
            except ValueError: raise ValueError('slot resources allocation UUID') from None
            need(value.int != 0 and str(value) == nonce, 'slot resources allocation UUID')
            key = node, charge['owner']
            if row['event'] == 'RESERVE':
                need(key not in leases, 'slot resources reused allocation')
                legacy += match is None
                leases[key] = dict(node=node, owner=charge['owner'], role=role, binding=match[2] if match else None,
                                   start=row['sequence'], end=None, bytes=charge['bytes'])
            else:
                need(key in leases and leases[key]['end'] is None and leases[key]['bytes'] == charge['bytes'],
                     'slot resources original lifetime')
                leases[key]['end'] = row['sequence']
    need(all(v['end'] is not None for v in leases.values()), 'slot resources incomplete drain')
    return leases, legacy


def publications(rounds, selection, identities):
    """Expected local ACKs from independently validated original native images."""
    f = publication.native.f; expected = {}
    for slot in rounds:
        certificate = publication.sha(slot['originals'][3])
        for node, files in slot['published'].items():
            directory, _, _ = publication.native.c.current(files)
            expected[node, certificate] = dict(root=selection['root'], view=selection['view'], ballot=selection['ballot'],
                identity=identities[node], payload=dict(certificate=certificate,
                selection=publication.sha(f.encode('records','SELECTED',selection)), published=slot['upper'],
                generation=publication.sha(files[directory+'generation.gsr'])))
    return expected


def required_four_publications(model, identities):
    """Derive ACKs from each checked original selection and published image.

    Caller must first replay the complete required-four physical history. The
    final view/selection cannot stand in for earlier stable and joint slots.
    """
    f, disk = publication.f, publication.disk
    expected = {}
    need(model.phases and len(model.phases) == len(model.entries), 'slot resources complete membership phases')
    for index, parts in enumerate(model.phases, 1):
        selected = f.decode(parts['SELECTED'], 'records', 'SELECTED', model.root)
        certificate = f.decode(parts['CERTIFICATE'], 'records', 'CERTIFICATE', model.root)
        need(certificate['index'] == index and certificate['ballot'] == selected['ballot'] and
             certificate['authority'] == selected['view'], 'slot resources original membership selection')
        digest = publication.sha(parts['CERTIFICATE'])
        voters = [v['voter'] for v in certificate['proofs']]
        need(len(set(voters)) == len(voters) and set(voters) <= set(identities), 'slot resources original publication voters')
        need(all(v['incarnation'] == identities[v['voter']]['storage'] for v in certificate['proofs']),
             'slot resources original publication identity')
        for node in voters:
            files = model.owner('published', index, node)
            prefix, _, packet = disk.current(files)
            anchor = disk.anchor(packet['capsule'])
            need(anchor['cut']['index'] == index and anchor['cut']['entry'] == certificate['entry'],
                 'slot resources original publication image')
            key = node, digest
            need(key not in expected, 'slot resources duplicate publication authority')
            expected[key] = dict(root=model.root, view=selected['view'], ballot=selected['ballot'], identity=identities[node],
                payload=dict(certificate=digest, selection=publication.sha(parts['SELECTED']), published=anchor,
                             generation=publication.sha(files[prefix+'generation.gsr'])))
    return expected


def local_calls(events, identities, root, expected):
    calls = []; pending = {}; used = set()
    for at, event in enumerate(events):
        if not event.get('event', '').startswith('LOCAL_SLOT_'): continue
        name = event['event']; node = event['node']
        need(name in ('LOCAL_SLOT_REQUEST','LOCAL_SLOT_RESPONSE') and
             set(event) == {'node','event','record','bytes'}, 'slot resources local observation shape')
        raw = base64.b64decode(event['bytes'], validate=True); kind, value = source.network.t.wire(event['bytes'])
        need(source.network.t.sha(raw) == event['record'] and node in identities and
             value['root'] == root and value['sender'] == value['recipient'] == identities[node],
             'slot resources local original bytes')
        if name == 'LOCAL_SLOT_REQUEST':
            need(kind == 'PUBLISH' and node not in pending and set(value['payload']) == {'certificate'},
                 'slot resources local publication request')
            key = node, value['payload']['certificate']; original = expected.get(key)
            need(original is not None and key not in used and value['view'] == original['view'] and
                 value['ballot'] == original['ballot'] and value['sequence'] == 1,
                 'slot resources local original publication')
            pending[node] = (at, value, event['record'], original, key)
        else:
            need(kind == 'PUBLISH_ACK' and node in pending, 'slot resources local publication response')
            start, request, digest, original, key = pending.pop(node)
            need({k:v for k,v in value.items() if k != 'payload'} == {k:v for k,v in request.items() if k != 'payload'} and
                 value['payload'] == original['payload'], 'slot resources local original acknowledgement')
            used.add(key); calls.append(dict(node=node, binding=digest, received=start, offered=at, kind='PUBLISH', certificate=request['payload']['certificate']))
    need(not pending and calls, 'slot resources complete local observations')
    return calls


def replay(events, wires, traces, boundaries, identities, root, expected, transactions, *, require_complete=True):
    need(type(require_complete) is bool, 'slot resources completeness policy')
    leases, legacy = scan(traces)
    if legacy or not leases:
        need(not require_complete, 'slot resources original bindings required')
        return dict(status='NOT_OBSERVED', legacyReservations=legacy, slotResourcesQualified=False,
                    wholeRuntimeResourcesQualified=False, phase3Complete=False)
    # Includes exact unsent invocation copies and connected failure terminals.
    transport = source.frames.replay(events,wires,traces,boundaries,identities,root,require_all_frames=False)
    network = source.network.replay(events,wires,identities,root)
    frames,_ = source.frames.lifetimes(traces)
    need(len(boundaries) == len(events), 'slot resources complete boundaries')
    def point(at, node):
        row = boundaries[at]
        need(type(row) is dict and set(row) == {'eventIndex','node','sequence','usage'} and
             type(row['eventIndex']) is int and row['eventIndex'] == at and row['node'] == node == events[at]['node'] and
             type(row['sequence']) is int and 0 <= row['sequence'] < len(traces[node]['changes']), 'slot resources original checkpoint')
        source.a.transitions.same_usage(row['usage'], traces[node]['changes'][row['sequence']]['usage'])
        return row['sequence']
    groups = defaultdict(list)
    for key, life in leases.items(): groups[life['node'],life['role'],life['binding']].append((key,life))
    successes = {v['sent']:v for v in network['rows']}; failures = {v['sent']:v for v in network['failed']}
    used = set(); outgoing = defaultdict(list)
    for at,event in enumerate(events):
        if event.get('event') not in source.network.SENDS | {source.frames.UNSENT}: continue
        kind,request = source.network.t.wire(event['bytes'])
        if kind not in KINDS: continue
        node=event['node']; digest=source.network.t.sha(base64.b64decode(event['bytes'],validate=True))
        unsent=event['event']==source.frames.UNSENT
        identifier=event['invocation'] if unsent else event['connection']['id']
        copied=frames.get((node,'request-send',identifier))
        need(copied is not None, 'slot resources original transport copy')
        choices=[(k,v) for k,v in groups[node,'slot-delivery',digest] if v['start'] < copied['start'] < v['end']]
        need(len(choices)==1, 'slot resources unique request handoff')
        key,life=choices[0]; size=len(base64.b64decode(event['bytes'],validate=True))
        need(life['bytes']==size, 'slot resources original delivery extent')
        response=successes.get(at); failure=failures.get(at)
        reason=event['reason'] if unsent else failure['clientReason'] if failure else None
        delivered=response['delivered'] if response else None
        if delivered is not None:
            need(response['answer']==kind+'_ACK' and life['start']<=point(delivered,node)<life['end'],
                 'slot resources delivery released before acknowledgement')
        else:need(reason in ('IO','DEADLINE'), 'slot resources failed delivery outside qualification')
        outgoing[key].append(dict(start=copied['start'],delivered=delivered)); used.add(key)
    for key,rows in outgoing.items():
        ordered=sorted(rows,key=lambda v:v['start'])
        need(1<=len(rows)<=3 and ordered[-1]['delivered'] is not None and
             all(v['delivered'] is None for v in ordered[:-1]), 'slot resources bounded successful identical delivery')
    attempts=defaultdict(list)
    for row in network['rows']:
        if row['kind'] not in INCOMING: continue
        node=row['request']['recipient']['node']; key=node,row['requestHash']
        attempts[key].append(dict(receivedSequence=point(row['received'],node),offeredSequence=point(row['offered'],node),
                                  received=row['received'],offered=row['offered'],kind=row['kind'],local=False,
                                  certificate=row['request']['payload'].get('certificate')))
    calls=local_calls(events,identities,root,expected)
    for call in calls:
        node=call['node']; key=node,call['binding']
        need(key not in attempts, 'slot resources local call cannot reuse socket')
        attempts[key].append(dict(call,receivedSequence=point(call['received'],node),
                                 offeredSequence=point(call['offered'],node),local=True))
    waiters={}; local_count=0; network_count=0
    for (node,role,binding),pairs in list(groups.items()):
        if role!='slot-waiter':continue
        rows=attempts.get((node,binding),[])
        need(rows and all(v['bytes']==0 for _,v in pairs),'slot resources original waiter binding/extent')
        try:voting.match_waiters([v for _,v in pairs],rows)
        except ValueError:raise ValueError('slot resources waiter call interval') from None
        waiters[node,binding]=[v for _,v in pairs];used.update(k for k,_ in pairs)
        if rows[0]['local']:
            need(len(pairs)==1,'slot resources one local waiter');local_count+=1
        else:network_count+=len(pairs)
    need(local_count==len(calls),'slot resources missing local waiter')
    voting_leases,_=voting.scan(traces)
    for life in voting_leases.values():
        if life['role']!='voting-waiter':continue
        candidates=waiters.get((life['node'],life['binding']),[])
        need(sum(v['start']<life['start']<life['end']<v['end'] for v in candidates)==1,
             'slot resources voting child waiter custody')
    # Each physically validated publication is inside its original PUBLISH call
    # and dispatcher waiter, including the direct local call without a socket.
    published=0; local_publications=set()
    for transaction in transactions:
        node=transaction[0]['node']; first=transaction[0]['eventIndex']; last=transaction[-1]['eventIndex']; choices=[]
        files=transaction[0].get('files',{});raw=files.get('applied-end/certificate.gsr')
        need(type(raw) is bytes,'slot resources original publication certificate')
        publication.native.f.decode(raw,'records','CERTIFICATE');certificate=publication.sha(raw)
        need((node,certificate) in expected,'slot resources original publication certificate')
        for (n,binding),rows in attempts.items():
            if n!=node:continue
            for row in rows:
                if row['kind']!='PUBLISH' or row['certificate']!=certificate or not row['received']<first<=last<row['offered']:continue
                for life in waiters.get((n,binding),[]):
                    if all(life['start']<=point(v['eventIndex'],node)<life['end'] for v in transaction):
                        choices.append((life['owner'],row))
        need(len({owner for owner,_ in choices})==1,'slot resources publication waiter custody')
        published+=1
        for _,row in choices:
            if row['local']:local_publications.add(row['received'])
    need(local_publications=={v['received'] for v in calls},'slot resources local publication not observed')
    need(used==set(leases),'slot resources incomplete allocation coverage')
    return dict(status='PASS',deliveryReservations=len(outgoing),deliveryAttempts=sum(map(len,outgoing.values())),
                networkWaiters=network_count,localWaiters=local_count,publicationTransactions=published,
                boundReservations=len(used),transport=transport,slotResourcesQualified=True,
                interruptedHandlersQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)
