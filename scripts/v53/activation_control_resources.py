"""Original stable activation requests, cached reply bytes and caller custody.

Requires independent native physical and slot qualification. Local labels only
correlate allocations; original connected/local bytes and publications supply
authority. Failed handlers, joining and complete runtime peaks remain separate.
"""
import base64
from collections import defaultdict, deque
import re
from uuid import UUID

from . import slot_control_resources as slots

source=slots.source
need=source.need
ROLES={'activation-control':'CONTROL','activation-waiter':'WAITER'}
OWNER=re.compile(r'(activation-control|activation-waiter)-([0-9a-f]{64})-([0-9a-f-]{36})\Z')
LEGACY=re.compile(r'(activation-control|activation-waiter)-([0-9a-f-]{36})\Z')
REPLIES={'PREPARE':'PROMISE','SELECTED':'INSTALL_ACK','ACCEPT':'ACCEPT_ACK','PROOF':'PROOF_ACK','APPLY':'APPLY_ACK','PUBLISH':'PUBLISH_ACK'}
BOUNDARIES={'PREPARE':('PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'),
            'SELECTED':('SELECTED_FORCED','INSTALL_BEFORE_RETURN')}


def scan(traces):
    lives={};legacy=0
    for node,trace in traces.items():
        source.a.transitions.replay(trace)
        for row in trace['changes']:
            charges=[v for v in row['removed']+row['added'] if any(v['owner'].startswith(role+'-') for role in ROLES)]
            if not charges:continue
            event=row['event'];charge=charges[0];match=OWNER.fullmatch(charge['owner']);old=LEGACY.fullmatch(charge['owner'])
            need(match is not None or old is not None,'activation resources owner binding')
            role=(match or old)[1];nonce=match[3] if match else old[2]
            try:identifier=UUID(nonce)
            except ValueError:raise ValueError('activation resources allocation UUID') from None
            need(identifier.int!=0 and str(identifier)==nonce,'activation resources allocation UUID')
            need(all(v['unit']==ROLES[role] and v['owner']==charge['owner'] for v in charges),'activation resources role/unit')
            need(event in ('RESERVE','RELEASE','CONTROL_GROW') and len(charges)==(2 if event=='CONTROL_GROW' else 1),
                 'activation resources allocation mutation')
            key=node,charge['owner']
            if event=='RESERVE':
                need(key not in lives,'activation resources reused allocation');legacy+=match is None
                lives[key]=dict(node=node,owner=charge['owner'],role=role,binding=match[2] if match else None,
                                start=row['sequence'],end=None,initial=charge['bytes'],growth=[])
            else:
                need(key in lives and lives[key]['end'] is None,'activation resources original lifetime');life=lives[key]
                if event=='RELEASE':life['end']=row['sequence']
                else:
                    need(role=='activation-control' and not life['growth'],'activation resources single cache growth')
                    life['growth'].append((row['sequence'],row['added'][0]['bytes']))
    need(all(v['end'] is not None for v in lives.values()),'activation resources incomplete drain')
    return lives,legacy


def augment(start,edges,matching):
    """One iterative alternating path; matching maps right vertices to left."""
    previous={left:right for right,left in matching.items()};queue=deque([start]);seen={start};parents={}
    while queue:
        left=queue.popleft()
        for right in edges(left):
            if right in parents:continue
            parents[right]=left
            if right not in matching:
                while True:
                    left=parents[right];matching[right]=left
                    if left==start:return True
                    right=previous[left]
            other=matching[right]
            if other not in seen:seen.add(other);queue.append(other)
    return False


def match_calls(waiters,attempts):
    # Generate neighbours lazily: retained histories may contain many exact
    # retries over time even though simultaneous waiters are bounded. Do not
    # allocate a quadratic waiter/attempt relation table for such input.
    def fits(w,a):return a['receivedSequence']<w['start']<w['end']<=a['offeredSequence']
    def forward(i):return (j for j,a in enumerate(attempts) if fits(waiters[i],a))
    def reverse(i):return (j for j,w in enumerate(waiters) if fits(w,attempts[i]))
    mandatory=[i for i,a in enumerate(attempts) if not a['fastEligible']]
    initial={}
    for at in mandatory:need(augment(at,reverse,initial),'activation resources missing mandatory caller')
    matching={at:w for w,at in initial.items()}
    for w in range(len(waiters)):
        if w not in matching.values():need(augment(w,forward,matching),'activation resources unmatched waiter')
    need(len(matching)==len(waiters) and set(mandatory)<=set(matching),'activation resources complete caller matching')
    return {w:at for at,w in matching.items()}


def replay(events,wires,traces,points,identities,root,expected,transactions,*,require_complete=True):
    need(type(require_complete) is bool,'activation resources completeness policy')
    lives,legacy=scan(traces)
    if legacy or not lives:
        need(not require_complete,'activation resources original bindings required')
        return dict(status='NOT_OBSERVED',legacyReservations=legacy,activationResourcesQualified=False,
                    wholeRuntimeResourcesQualified=False,phase3Complete=False)
    need(len(points)==len(events),'activation resources complete boundaries')
    def point(at,node):
        p=points[at]
        need(type(p) is dict and set(p)=={'eventIndex','node','sequence','usage'} and type(p['eventIndex']) is int and
             p['eventIndex']==at and p['node']==node==events[at]['node'] and type(p['sequence']) is int and
             0<=p['sequence']<len(traces[node]['changes']),'activation resources original checkpoint')
        source.a.transitions.same_usage(p['usage'],traces[node]['changes'][p['sequence']]['usage']);return p['sequence']
    published={}
    for transaction in transactions:
        node=transaction[0]['node'];raw=transaction[0]['files'].get('applied-end/certificate.gsr')
        need(type(raw) is bytes,'activation resources original publication certificate')
        key=node,slots.publication.sha(raw);last=transaction[-1]['eventIndex']
        need(key in expected and key not in published and events[last]['event']=='PUBLICATION_BEFORE_RETURN',
             'activation resources original publication boundary');published[key]=last
    network=source.network.replay(events,wires,identities,root)
    need(all(v['kind'] not in REPLIES or v['received'] is None or any(r['sent']==v['sent'] for r in network['rows'])
             for v in network['failed']),'activation resources failed handler outside qualification')
    by_id={v['connection']['id']:v for v in wires};attempts=defaultdict(list)
    for row in network['rows']:
        kind=row['kind']
        if kind not in REPLIES:continue
        need(row['answer']==REPLIES[kind],'activation resources successful original reply')
        q=row['request'];node=q['recipient']['node'];fast=False
        if kind=='PUBLISH':
            key=node,q['payload']['certificate'];original=expected.get(key)
            need(original is not None and q['view']==original['view'] and q['ballot']==original['ballot'] and
                 row['response']['payload']==original['payload'],
                 'activation resources original publication response')
            # A request may arrive while the publication writer holds the
            # journal monitor, then observe the completed publication after it
            # acquires that monitor. Its response cut, not socket arrival, is
            # decisive. The original publication itself still needs custody
            # below; a matching/later certificate cannot manufacture it.
            fast=key in published and published[key]<row['offered']
        wire=by_id[row['serverConnection']]
        attempts[node,row['requestHash']].append(dict(kind=kind,received=row['received'],offered=row['offered'],
            receivedSequence=point(row['received'],node),offeredSequence=point(row['offered'],node),fastEligible=fast,local=False,
            certificate=q['payload'].get('certificate'),
            requestBytes=base64.b64decode(wire['request'],validate=True),responseBytes=base64.b64decode(wire['response'],validate=True)))
    calls=slots.local_calls(events,identities,root,expected)
    for c in calls:
        node=c['node'];key=node,c['binding'];need(key not in attempts,'activation resources local/socket alias')
        attempts[key].append(dict(kind=c['kind'],received=c['received'],offered=c['offered'],
            receivedSequence=point(c['received'],node),offeredSequence=point(c['offered'],node),fastEligible=False,local=True,
            certificate=c['certificate'],
            requestBytes=base64.b64decode(events[c['received']]['bytes'],validate=True),
            responseBytes=base64.b64decode(events[c['offered']]['bytes'],validate=True)))
    need(attempts,'activation resources original calls absent')
    groups=defaultdict(lambda:defaultdict(list))
    for key,life in lives.items():groups[life['node'],life['binding']][life['role']].append((key,life))
    need(set(groups)<=set(attempts),'activation resources unobserved allocation')
    used=set();controls={};held={};fast_count=0;durable=0;local=0;kinds=defaultdict(int)
    for key,rows in attempts.items():
        node,binding=key;pairs=groups[key];writers=pairs['activation-control'];waiters=pairs['activation-waiter']
        if not writers and not waiters:
            need(all(r['fastEligible'] for r in rows),'activation resources missing original control');fast_count+=len(rows);continue
        need(len(writers)==1 and waiters,'activation resources one cache and callers');owner,control=writers[0]
        need(len(control['growth'])==1,'activation resources original reply growth');grown,extent=control['growth'][0]
        need(all(r['requestBytes']==rows[0]['requestBytes'] and r['responseBytes']==rows[0]['responseBytes'] for r in rows),
             'activation resources identical cached bytes')
        need(control['initial']==len(rows[0]['requestBytes']),'activation resources original request extent')
        need(extent==control['initial']+len(rows[0]['responseBytes']),'activation resources original cached extent')
        need(all(w['initial']==0 for _,w in waiters),'activation resources waiter extent')
        need(any(r['receivedSequence']<control['start']<grown<r['offeredSequence'] for r in rows),
             'activation resources original work interval')
        assignment=match_calls([w for _,w in waiters],rows)
        need(any(w['start']<control['start']<grown<w['end'] for _,w in waiters),'activation resources original caller custody')
        for i,(_,w) in enumerate(waiters):
            need(control['start']<w['end'] and grown<w['end']<control['end'],'activation resources cached reply caller custody')
            local+=rows[assignment[i]]['local']
        fast_count+=len(rows)-len(waiters);controls[key]=control;held[key]=[w for _,w in waiters]
        for name in BOUNDARIES.get(rows[0]['kind'],()):
            matches=[at for at,e in enumerate(events) if e['node']==node and e['event']==name and
                     control['start']<=point(at,node)<grown]
            need(len(matches)==1 and any(r['received']<matches[0]<r['offered'] for r in rows),
                 'activation resources original durable boundary');durable+=1
        used.update([owner,*(k for k,_ in waiters)]);kinds[rows[0]['kind']]+=1
    publication_checks=0
    for transaction in transactions:
        node=transaction[0]['node'];first=transaction[0]['eventIndex'];last=transaction[-1]['eventIndex']
        certificate=slots.publication.sha(transaction[0]['files']['applied-end/certificate.gsr']);choices=set()
        for key,rows in attempts.items():
            control=controls.get(key)
            if key[0]!=node or control is None:continue
            if not any(v['kind']=='PUBLISH' and v['certificate']==certificate and v['received']<first<=last<v['offered'] for v in rows):continue
            if all(control['start']<=point(v['eventIndex'],node)<control['growth'][0][0] for v in transaction) and any(
                    all(w['start']<=point(v['eventIndex'],node)<w['end'] for v in transaction) for w in held[key]):choices.add(control['owner'])
        need(len(choices)==1,'activation resources publication caller custody');publication_checks+=1
    children,_=slots.scan(traces);child_count=0
    for child in children.values():
        if child['role']!='slot-waiter':continue
        key=child['node'],child['binding']
        if key not in attempts:continue  # Retention controls bypass activation dispatch.
        control=controls.get(key)
        need(control is not None and control['start']<child['start']<child['end']<control['growth'][0][0] and
             any(w['start']<child['start']<child['end']<w['end'] for w in held[key]),
             'activation resources slot child custody');child_count+=1
    need(used==set(lives),'activation resources incomplete allocation coverage')
    return dict(status='PASS',boundReservations=len(used),cachedControls=len(controls),waiterReservations=sum(map(len,held.values())),
                kinds=dict(sorted(kinds.items())),calls=sum(map(len,attempts.values())),localCallers=local,fastPublicationReplies=fast_count,
                durableBoundaryChecks=durable,slotChildWaiters=child_count,publicationTransactions=publication_checks,activationResourcesQualified=True,
                interruptedHandlersQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)
