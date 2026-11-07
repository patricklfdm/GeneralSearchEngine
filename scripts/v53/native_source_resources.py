"""Bind multi-session native source buffers to original transport boundaries.

The physical caller must first admit the original history. Local owner names
provide correlation only; original wire bytes determine lengths and routes.
Unobserved/legacy allocations are explicit gaps, never matched by size.
"""
from collections import defaultdict
import base64
import re
from uuid import UUID
from . import segmented_transcript
from . import source_control_resource_evidence as component
from . import joining_connections as network
from . import transport_resource_evidence as frames

a=component.a;need=a.need
ROLES=(*component.ROLES,'joining-checkpoint-trace')
OWNER=re.compile(r'('+'|'.join(ROLES)+r')-([0-9a-f]{64})-([0-9a-f-]{36})\Z')
LEGACY=re.compile(r'('+'|'.join(ROLES)+r')-([0-9a-f-]{36})\Z')


def request_handoff(logical,copied,size):
    need(logical['initial']==size and not logical['growth'],'native source resources original buffer extent')
    need(copied['initial']==size and not copied['growth'],'native source resources original transport copy')
    # SourcePull may be cancelled while the worker still owns its independent
    # copied send buffer. The copy's allocation, not a late socket terminal,
    # must occur within the original logical buffer lifetime.
    need(logical['start']<copied['start']<logical['end'],'native source resources request copy handoff')


def scan(traces):
    leases={};legacy={};other=0
    for node,trace in traces.items():
        a.transitions.replay(trace)
        for row in trace['changes']:
            candidates=[]
            for side in ('removed','added'):
                for charge in row[side]:
                    name=charge['owner']
                    if not any(name.startswith(role+'-') for role in ROLES):continue
                    match=OWNER.fullmatch(name);old=LEGACY.fullmatch(name)
                    need(charge['unit']=='CONTROL' and (match is not None or old is not None),'native source resources owner shape')
                    value=match[3] if match else old[2]
                    try:nonce=UUID(value)
                    except ValueError:raise ValueError('native source resources allocation UUID') from None
                    need(nonce.int and str(nonce)==value,'native source resources allocation UUID')
                    candidates.append((charge,match,old))
            if not candidates:
                if row['event']=='RESERVE':other+=sum(v['unit']=='CONTROL' for v in row['added'])
                continue
            charge,match,old=candidates[0];key=node,charge['owner'];target=leases if match else legacy
            event=row['event'];seq=row['sequence']
            need(event in ('RESERVE','CONTROL_GROW','RELEASE'),'native source resources mutation kind')
            if event=='RESERVE':
                need(key not in target,'native source resources reused allocation')
                target[key]=dict(node=node,owner=charge['owner'],role=(match or old)[1],binding=match[2] if match else None,
                                 start=seq,end=None,initial=charge['bytes'],growth=[])
            else:
                need(key in target and target[key]['end'] is None,'native source resources original lifetime')
                if event=='RELEASE':target[key]['end']=seq
                else:
                    need(target[key]['role'] in ('transfer-trace','joining-checkpoint-trace') and not target[key]['growth'],
                         'native source resources unexpected growth')
                    target[key]['growth'].append((seq,row['added'][0]['bytes']))
    need(all(v['end'] is not None for v in [*leases.values(),*legacy.values()]),'native source resources incomplete close')
    return leases,legacy,other


def replay(events,wires,traces,boundaries,identities,root,*,require_complete=True,bindings=None,initials=None):
    need(type(require_complete) is bool,'native source resources completeness policy')
    need(bindings is None or type(bindings) is dict and not bindings,'native source resources empty binding output')
    need(initials is None or type(initials) is dict and not initials,'native source resources empty initial output')
    leases,legacy,other=scan(traces)
    if not leases:
        need(not require_complete,'native source resources required original bindings absent')
        return dict(status='NOT_OBSERVED',reason='original source owner bindings absent',legacyReservations=len(legacy),
                    boundReservations=0,allObservedSourceBuffersBound=False,wholeRuntimeResourcesQualified=False)
    need(not legacy or not require_complete,'native source resources mixed legacy owners')
    transport=network.replay(events,wires,identities,root)
    transport_leases,_=frames.lifetimes(traces)
    used=set();checks=0;requests=defaultdict(list);response_rows=defaultdict(list);early_returns=0
    by_type=defaultdict(list)
    for key,life in leases.items():by_type[life['node'],life['role'],life['binding']].append((key,life))
    need(type(boundaries) is list and len(boundaries)==len(events),'native source resources complete checkpoints')
    def point(at,node):
        nonlocal checks
        p=boundaries[at]
        need(type(p) is dict and set(p)=={'eventIndex','node','sequence','usage'} and type(p['eventIndex']) is int and p['eventIndex']==at and
             p['node']==node==events[at]['node'] and type(p['sequence']) is int and 0<=p['sequence']<len(traces[node]['changes']),
             'native source resources exact checkpoint')
        a.transitions.same_usage(p['usage'],traces[node]['changes'][p['sequence']]['usage']);checks+=1;return p['sequence']
    def at(life,seq):return life['start']<=seq<life['end']
    def unique(rows,reason):need(len(rows)==1,reason);return rows[0]
    def immutable(life,size):need(life['initial']==size and not life['growth'],'native source resources original buffer extent')
    def client(q,h,size,points,invocation,unsent):
        nonlocal early_returns
        node=q['sender']['node'];copied=transport_leases.get((node,'request-send',invocation))
        need(copied is not None,'native source resources missing request copy')
        key,life=unique([(k,v) for k,v in by_type[node,'source-request',h] if at(v,copied['start'])],
                        'native source resources request coverage')
        request_handoff(life,copied,size)
        if unsent:need(copied['end']<=point(points[0],node),'native source resources unwritten copy close')
        else:
            need(at(copied,point(points[0],node)),'native source resources live request copy')
            # Failure callbacks follow release; a successful read precedes it.
            last=point(points[-1],node)
            if events[points[-1]]['event']==network.t.FAIL:need(copied['end']<=last,'native source resources failed copy close')
            else:need(at(copied,last),'native source resources received copy lifetime')
        if life['end']<=point(points[-1],node):early_returns+=1
        used.add(key);requests[key].append(dict(request=q,hash=h,points=points))
    successes={v['sent']:v for v in transport['rows']};failures={v['sent']:v for v in transport['failed']}
    for pos,event in enumerate(events):
        if event.get('event') not in network.SENDS|{'NETWORK_UNSENT_FAILED'}:continue
        kind,q=network.t.wire(event['bytes'])
        if kind not in ('CHUNK','TRANSFER_COMMIT','STATUS_PROBE'):continue
        raw=base64.b64decode(event['bytes'],validate=True);h=component.physical.e.digest(raw)
        # Learner discovery owns its STATUS_PROBE through the same logical
        # request buffer as ROOT acquisition. Ordinary status callers do not.
        # Match the exact original sender/digest; never infer a source buffer
        # from frame size or assign an unobserved reservation to a later retry.
        if kind=='STATUS_PROBE' and not by_type.get((q['sender']['node'],'source-request',h)):continue
        need(event['node']==q['sender']['node'] and q['root']==root and q['sender']==identities.get(event['node']) and
             q['recipient'] in identities.values() and event['request']==h and event['kind']==kind,'native source resources original request')
        if event['event']=='NETWORK_UNSENT_FAILED':
            # Transport frame replay separately binds the unwritten invocation.
            need(event['reason'] in network.t.native.attempts.REASONS,'native source resources unsent reason');points=[pos]
        else:
            terminal=failures[pos]['clientFailed'] if pos in failures else successes[pos]['delivered'];points=[pos,terminal]
        client(q,h,len(raw),points,event['invocation'] if event['event']=='NETWORK_UNSENT_FAILED' else event['connection']['id'],
               event['event']=='NETWORK_UNSENT_FAILED')
    wire_by_id=segmented_transcript.by_connection(wires)
    associations={};meta_responses=defaultdict(set);trace_meta=defaultdict(set);completed=set()
    for row in transport['rows']:
        if row['kind'] not in ('CHUNK','TRANSFER_COMMIT') or row['answer']=='REJECT':continue
        need(row['answer'] in ('SOURCE_OFFER','CHUNK','TRANSFER_COMMIT'),'native source resources original source response')
        q=row['request'];node=q['recipient']['node'];h=row['requestHash'];session=component.binding(q);seq=point(row['offered'],node)
        raw=wire_by_id[row['serverConnection']]['response'];size=len(base64.b64decode(raw,validate=True));choices=[]
        for key,life in by_type[node,'source-response',h]:
            if life['start']>seq:continue
            for meta_key,meta in by_type[node,'source-session',session]:
                if not meta['start']<life['start']<life['end']<meta['end']:continue
                traces_for_session=by_type[node,'transfer-trace',session]+by_type[node,'joining-checkpoint-trace',session]
                for trace_key,trace in traces_for_session:
                    if not trace['start']<meta['start']<meta['end']<trace['end'] or not at(trace,seq):continue
                    if at(life,seq) and at(meta,seq):choices.append((key,life,meta_key,meta,trace_key,trace,False))
                    elif row['answer']=='TRANSFER_COMMIT' and len(trace['growth'])==1:
                        grown,extent=trace['growth'][0]
                        if life['start']<grown<life['end']<meta['end']<=seq:choices.append((key,life,meta_key,meta,trace_key,trace,True))
        key,life,mk,meta,tk,trace,cached=unique(choices,'native source resources original response/cache coverage')
        immutable(life,size);immutable(meta,32768);need(trace['initial']==1024,'native source resources trace extent')
        if key not in associations:
            need(point(row['received'],node)<life['start'],'native source resources first response allocation')
            associations[key]=(mk,tk)
        need(associations[key]==(mk,tk),'native source resources changed session owner')
        if cached:
            need(trace['growth'][0][1]==32768+size,'native source resources completed cache extent');completed.add(tk)
        else:
            need(not trace['growth'] or seq<trace['growth'][0][0],'native source resources response after cache completion')
        used.update((key,mk,tk));meta_responses[mk].add(key);trace_meta[tk].add(mk);response_rows[key].append(row)
    # SourceSession is serial even when different original sessions overlap.
    # Only its last exact response can survive until close/cache handoff.
    first_requests={}
    for mk,keys in meta_responses.items():
        ordered=sorted(keys,key=lambda k:leases[k]['start']);previous=None
        for key in ordered:
            first=response_rows[key][0];q=first['request'];sequence=q['sequence'];life=leases[key]
            if previous is None:
                need(sequence==1,'native source resources missing first session response')
                if initials is not None:
                    first_requests[mk]=dict(bytes=wire_by_id[first['serverConnection']]['request'],
                                            received=point(first['received'],mk[0]),offered=point(first['offered'],mk[0]))
            else:
                old=leases[previous];old_sequence=response_rows[previous][0]['request']['sequence']
                need(sequence==old_sequence+1 and old['start']<=point(first['received'],life['node'])<old['end']<life['start'],
                     'native source resources serial response replacement')
            need(all(v['request']==q and v['response']==first['response'] for v in response_rows[key]),'native source resources changed cached bytes')
            previous=key
    for tk,keys in trace_meta.items():
        need(len(keys)==1,'native source resources trace reopened export')
        need(not leases[tk]['growth'] or tk in completed,'native source resources unobserved completed cache')
    extra=sorted(set(leases)-used)
    need(not require_complete or not extra,'native source resources unobserved source reservations')
    peaks={}
    for node in identities:
        changes=[]
        for key in meta_responses:
            life=leases[key]
            if life['node']==node:changes.extend(((life['start'],1),(life['end'],-1)))
        live=peak=0
        for _,delta in sorted(changes):live+=delta;peak=max(peak,live)
        peaks[node]=peak
    # Emit associations only after the complete original replay has succeeded.
    # Downstream close checks must not infer ownership from equal byte sizes or
    # overlapping sessions. Keys include both original node and allocation UUID.
    if bindings is not None:bindings.update(associations)
    if initials is not None:initials.update(first_requests)
    return dict(status='PASS',boundReservations=len(used),logicalRequests=len(requests),responseBuffers=len(response_rows),sessions=len(meta_responses),
                traces=len(trace_meta),completedCaches=len(completed),originalSourceAttempts=sum(len(v) for v in requests.values()),
                peakConcurrentSessions=peaks,
                logicalReleaseBeforeTransportTerminal=early_returns,
                boundaryChecks=checks,legacyReservations=len(legacy),unobservedReservations=[leases[k] for k in extra],otherControlReservations=other,
                allObservedSourceBuffersBound=not extra and not legacy,serviceCloseIntervalsQualified=False,
                wholeRuntimeResourcesQualified=False,phase3Complete=False)
