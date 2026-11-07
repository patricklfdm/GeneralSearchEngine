"""Original source request, response, session and completed-cache lifetimes.

This component reader qualifies one serial record pull, including TCP retries.
It does not infer unobserved exports or qualify every native runtime CONTROL.
"""
import argparse
import base64
import json
from pathlib import Path
import re
from uuid import UUID
from . import segmented_transcript
from . import native_resource_evidence as a
from . import connection_transcript as net
from . import source_export_evidence as physical

need=a.need
ROLES=('source-request','source-response','source-session','transfer-trace')
OWNER=re.compile(r'(source-request|source-response|source-session|transfer-trace)-([0-9a-f]{64})-([0-9a-f-]{36})\Z')
CASES=('lost-offer','lost-data','lost-commit','exhausted-offer')
CONTROL={'SOURCE_CALL','SOURCE_REPLY','SOURCE_FAILURE','SOURCE_PULL_CLOSED','SOURCE_CACHE_RETRY',
         'SOURCE_SERVICE_CLOSE_BEGIN','SOURCE_SERVICE_CLOSE_RETURNED','SOURCE_REPLY_DROP','TRANSFER_ADMITTED','TRANSFER_BEFORE_REPLY'}


def binding(request):
    return physical.e.digest(physical.e.f.canonical(dict(root=request['root'],source=request['recipient'],
                         reader=request['sender'],trace=request['trace'])))


def lifetimes(traces):
    lives={};other=0
    for node,trace in traces.items():
        a.transitions.replay(trace)
        for row in trace['changes']:
            selected=[]
            for side in ('removed','added'):
                for charge in row[side]:
                    if not any(charge['owner'].startswith(role+'-') for role in ROLES):continue
                    match=OWNER.fullmatch(charge['owner'])
                    need(match is not None and charge['unit']=='CONTROL','source resources bound owner shape')
                    try:nonce=UUID(match[3])
                    except ValueError:raise ValueError('source resources allocation UUID') from None
                    need(nonce.int!=0 and str(nonce)==match[3],'source resources allocation UUID')
                    selected.append((charge,match))
            if not selected:
                if row['event']=='RESERVE':other+=sum(v['unit']=='CONTROL' for v in row['added'])
                continue
            charge,match=selected[0];key=(node,match[1],match[2]);event=row['event'];seq=row['sequence']
            need(event in ('RESERVE','CONTROL_GROW','RELEASE'),'source resources mutation kind')
            if event=='RESERVE':
                need(key not in lives,'source resources duplicate logical reservation')
                lives[key]=dict(owner=charge['owner'],start=seq,end=None,initial=charge['bytes'],growth=[])
            else:
                need(key in lives and lives[key]['owner']==charge['owner'] and lives[key]['end'] is None,
                     'source resources original allocation lifetime')
                if event=='RELEASE':lives[key]['end']=seq
                else:
                    need(match[1]=='transfer-trace' and not lives[key]['growth'],'source resources unexpected buffer growth')
                    lives[key]['growth'].append((seq,row['added'][0]['bytes']))
    need(all(v['end'] is not None for v in lives.values()),'source resources unreleased allocation')
    return lives,other


def replay(events,wires,traces,boundaries,identities,root,record,mode):
    need(mode in CASES,'source resources declared case')
    need(type(events) is list and type(boundaries) is list and len(events)==len(boundaries),'source resources complete boundaries')
    need(all(v.get('event') in CONTROL|net.EVENTS for v in events),'source resources unknown event')
    positions=[i for i,v in enumerate(events) if v['event'] in net.EVENTS]
    network=net.replay([events[i] for i in positions],wires,identities,root,positions=positions,allow_withheld=True)
    need(len(network['rows'])==network['attempts']==network['receivedAttempts'],'source resources complete original attempts')
    leases,other=lifetimes(traces);used=set();checks=0
    def point(at,node):
        nonlocal checks
        p=boundaries[at]
        need(type(p) is dict and set(p)=={'eventIndex','node','sequence','usage'} and type(p['eventIndex']) is int and p['eventIndex']==at and
             p['node']==node==events[at]['node'] and type(p['sequence']) is int and 0<=p['sequence']<len(traces[node]['changes']),
             'source resources exact checkpoint')
        a.transitions.same_usage(p['usage'],traces[node]['changes'][p['sequence']]['usage']);checks+=1
        return p['sequence']
    def get(node,role,digest):
        key=node,role,digest;need(key in leases,'source resources missing original reservation');used.add(key);return leases[key]
    def live(life,at,node):need(life['start']<=point(at,node)<life['end'],'source resources not live at boundary')
    def immutable(life,extent):need(life['initial']==extent and not life['growth'],'source resources original buffer extent')
    def only(event,node):
        rows=[i for i,v in enumerate(events) if v['event']==event]
        need(len(rows)==1 and events[rows[0]]==dict(event=event,node=node),'source resources terminal observation')
        return rows[0]
    closed=only('SOURCE_PULL_CLOSED','node-2');begin=only('SOURCE_SERVICE_CLOSE_BEGIN','node-1');end=only('SOURCE_SERVICE_CLOSE_RETURNED','node-1')
    need(closed<begin<end==len(events)-1,'source resources terminal order')
    drops={v['connection']:(i,v) for i,v in enumerate(events) if v['event']=='SOURCE_REPLY_DROP'}
    need(len(drops)==sum(v['event']=='SOURCE_REPLY_DROP' for v in events)==(3 if mode=='exhausted-offer' else 1),
         'source resources declared losses')
    rows=network['rows'];need(rows,'source resources empty original pull')
    request_map={};request_sizes={};responses={};first=rows[0]['request'];session=binding(first)
    original=physical.e.f.decode(record,'records','PROMISE');digest=physical.e.digest(record)
    need(original['root']==root and first['root']==root,'source resources original record root')
    transfer=first['payload']['id'];expected={1:('CHUNK','SOURCE_OFFER',dict(id=transfer,action='REQUEST',offset=0,digest=digest,bytes=''),
                                                          dict(id=transfer,digest=digest,bytes=len(record),kind='RECORD'))}
    for seq,offset in enumerate(range(0,len(record),1024),2):
        part=record[offset:offset+1024]
        expected[seq]=('CHUNK','CHUNK',dict(id=transfer,action='REQUEST',offset=offset,digest=digest,bytes=''),
                       dict(id=transfer,action='DATA',offset=offset,digest=physical.e.digest(part),bytes=base64.b64encode(part).decode()))
    commit=len(expected)+1;expected[commit]=('TRANSFER_COMMIT','TRANSFER_COMMIT',dict(id=transfer,digest=digest),dict(id=transfer,digest=digest))
    offers=segmented_transcript.by_connection(wires)
    for row in rows:
        q=row['request'];answer=row['response'];seq=q['sequence']
        need(type(seq) is int and seq in expected,'source resources original request sequence')
        common=dict(root=root,view=original['view'],ballot=original['ballot'],trace=first['trace'],sequence=seq)
        wanted,kind,payload,response=expected[seq]
        need(row['kind']==wanted and row['answer']==kind and
             q==dict(common,sender=identities['node-2'],recipient=identities['node-1'],payload=payload) and
             answer==dict(common,sender=identities['node-1'],recipient=identities['node-2'],payload=response),
             'source resources exact original record exchange')
        h=row['requestHash'];request_map[h]=q
        wire=offers[row['serverConnection']];request_sizes[h]=len(base64.b64decode(wire['request'],validate=True))
        responses[h]=len(base64.b64decode(wire['response'],validate=True))
        if row.get('withheld'):
            need(row['failedAttempt'] and row['serverConnection'] in drops,'source resources original withheld failure')
            at,drop=drops[row['serverConnection']]
            need(drop==dict(node='node-1',event='SOURCE_REPLY_DROP',connection=row['serverConnection'],request=h) and row['offered']<at,
                 'source resources drop binding')
            wanted_kind={'lost-offer':'SOURCE_OFFER','lost-data':'CHUNK','lost-commit':'TRANSFER_COMMIT','exhausted-offer':'SOURCE_OFFER'}[mode]
            need(row['answer']==wanted_kind,'source resources declared loss phase')
        else:need(not row['failedAttempt'] and row['delivered'] is not None,'source resources unexpected failure')
    need(set(drops)=={v['serverConnection'] for v in rows if v.get('withheld')},'source resources complete loss bindings')
    need({v['sequence'] for v in request_map.values()}==({1} if mode=='exhausted-offer' else set(expected)),
         'source resources complete record pull')
    # Logical request ownership spans every attempt, rather than one TCP copy.
    calls={};outcomes={};pending=None;deadline=None;attempt_rows={v['sent']:v for v in rows};seen=set()
    for at,event in enumerate(events):
        name=event['event']
        if name not in ('SOURCE_CALL','SOURCE_REPLY','SOURCE_FAILURE','SOURCE_CACHE_RETRY'):continue
        kind,q=net.wire(event['request']);h=physical.e.digest(base64.b64decode(event['request'],validate=True))
        need(event['node']=='node-2' and h in request_map and q==request_map[h],'source resources original client observation')
        if name in ('SOURCE_CALL','SOURCE_CACHE_RETRY'):
            need(pending is None,'source resources overlapping logical attempt');pending=(at,h,name)
            after=[v for pos,v in attempt_rows.items() if pos>at and pos not in seen]
            need(after,'source resources missing actual client attempt');row=min(after,key=lambda v:v['sent']);seen.add(row['sent'])
            need(row['requestHash']==h,'source resources client attempt binding')
            if name=='SOURCE_CACHE_RETRY':
                need(closed<at<begin and q['sequence']==commit and row['delivered']<begin,'source resources completed retry interval');pending=None
            else:
                need(set(event)=={'node','event','request','deadline'} and type(event['deadline']) is int and at<closed,
                     'source resources original request deadline')
                if deadline is None:deadline=event['deadline']
                need(event['deadline']==deadline,'source resources renewed deadline');calls.setdefault(h,[]).append(at)
        else:
            need(pending is not None and pending[1]==h,'source resources client terminal binding')
            row=attempt_rows[max(seen)];terminal=next((v['clientFailed'] for v in network['failed'] if v['sent']==row['sent']),row['delivered'])
            need(terminal<at<closed,'source resources terminal before transport')
            if name=='SOURCE_FAILURE':need(event==dict(node='node-2',event=name,request=event['request'],reason='IO') and row['failedAttempt'],'source resources failed attempt reason')
            else:need(set(event)=={'node','event','request','response'} and not row['failedAttempt'] and net.wire(event['response'])==(row['answer'],row['response']),
                      'source resources client reply bytes')
            outcomes.setdefault(h,[]).append(at);pending=None
    need(pending is None and seen==set(attempt_rows) and set(calls)==set(request_map),'source resources complete logical calls')
    need(sum(v['event']=='SOURCE_CACHE_RETRY' for v in events)==(0 if mode=='exhausted-offer' else 1),'source resources exact cache retry')
    for h,q in request_map.items():
        lease=get('node-2','source-request',h);immutable(lease,request_sizes[h])
        need(len(calls[h])==len(outcomes[h]) and len(calls[h])<=(3 if mode=='exhausted-offer' else 2),'source resources attempt bound')
        for at in calls[h]+outcomes[h]:live(lease,at,'node-2')
        next_call=min((i for other,values in calls.items() if other!=h for i in values if i>outcomes[h][-1]),default=closed)
        need(lease['end']<=point(next_call,'node-2'),'source resources logical release order')
    # Each admitted response has a distinct original request. Completion hands
    # its last reply to the enlarged trace before freeing session reservations.
    admitted={};replied={}
    for at,event in enumerate(events):
        if event['event'] not in ('TRANSFER_ADMITTED','TRANSFER_BEFORE_REPLY'):continue
        kind,q=net.wire(event['request']);h=physical.e.digest(base64.b64decode(event['request'],validate=True))
        need(event['node']=='node-1' and h in request_map and q==request_map[h],'source resources original server observation')
        target=admitted if event['event']=='TRANSFER_ADMITTED' else replied;target.setdefault(h,[]).append(at)
        need(set(event)==({'node','event','request','response'} if target is replied else {'node','event','request'}),
             'source resources service observation shape')
        if target is replied:need(net.wire(event['response'])==(expected[q['sequence']][1],dict(q,sender=q['recipient'],recipient=q['sender'],payload=expected[q['sequence']][3])),
                                 'source resources server reply bytes')
    need(set(admitted)==set(replied)==set(request_map),'source resources complete service observations')
    meta=get('node-1','source-session',session);immutable(meta,32768)
    trace=get('node-1','transfer-trace',session);need(trace['initial']==1024,'source resources initial trace extent')
    need(trace['start']<=point(min(v[0] for v in admitted.values()),'node-1')<meta['start'],'source resources initial session order')
    for h,q in request_map.items():
        response=get('node-1','source-response',h);immutable(response,responses[h]);seq=q['sequence']
        attempts=[v for v in rows if v['requestHash']==h]
        need(len(admitted[h])==len(replied[h])==len(attempts),'source resources paired service calls')
        for entered,returned,attempt in zip(admitted[h],replied[h],attempts):
            need(attempt['received']<entered<returned<attempt['offered'],'source resources service interval')
            live(trace,entered,'node-1');live(trace,returned,'node-1')
        need(meta['start']<response['start'] and point(admitted[h][0],'node-1')<response['start']<=point(replied[h][0],'node-1'),
             'source resources response allocation interval')
        if seq!=commit:
            for at in replied[h]:live(response,at,'node-1');live(meta,at,'node-1')
            following=next((k for k,v in request_map.items() if v['sequence']==seq+1),None)
            if following is not None:
                live(response,admitted[following][0],'node-1')
                need(response['end']<get('node-1','source-response',following)['start'],'source resources cached response replacement')
            else:
                live(response,begin,'node-1');need(response['end']<=point(end,'node-1'),'source resources active response close')
        else:
            need(len(trace['growth'])==1,'source resources completed cache growth')
            grown,extent=trace['growth'][0]
            need(extent==32768+responses[h] and response['start']<grown<response['end']<meta['end']<=point(replied[h][0],'node-1'),
                 'source resources completed cache handoff')
    if mode=='exhausted-offer':
        need(not trace['growth'],'source resources active trace cannot hold completed cache');live(meta,begin,'node-1')
        need(meta['end']<=point(end,'node-1'),'source resources active session close')
    live(trace,begin,'node-1');need(meta['end']<trace['end']<=point(end,'node-1'),'source resources retained trace close')
    need(set(leases)==used,'source resources unbound reservation')
    return dict(status='PASS',logicalRequests=len(calls),tcpAttempts=network['attempts'],droppedReplies=len(drops),
                boundReservations=len(used),boundaryChecks=checks,otherControlReservations=other,
                completeMembershipHistory=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def case(root,mode):
    extra=['wire.json','events.json',a.DIRECTORY]+([] if mode=='exhausted-offer' else ['record.gsr'])
    # The independent close reader requires and validates this optional sidecar.
    # Its presence does not upgrade the original source-buffer qualification.
    if (root/'control-close-captures').exists():extra.append('control-close-captures')
    physical.case(root,3,additional=extra)
    captured=physical.c.inventory(root/'captured/node-1');cap=physical.c.current(captured)[2]['capsule'];root_id=cap['root']
    record=physical.c.journal(captured['grants.gsr'],root_id,'node-1')[-2][1]
    if mode!='exhausted-offer':need(a.collection.snapshot.s.regular(root/'record.gsr',8192)==record,'source resources received original record')
    ids={node:physical.e.f.decode(physical.c.inventory(root/'captured'/node)['node.gsr'],'records','NODE')['identity'] for node in ('node-1','node-2','node-3')}
    index,traces,boundaries,events=a.load(root);a.replay(index,traces,boundaries,events,{n:ids[n] for n in traces},root_id)
    wires=a.collection.read_json(root,'wire.json',a.collection.WIRE_BYTES);data=(events,wires,traces,boundaries,ids,root_id,record,mode)
    return replay(*data),data


def validate(directory):
    root=Path(directory);before=a.collection.inventory(root)
    need({p.name for p in root.iterdir()}=={'receipt.json',*CASES},'source resources complete cases')
    expected=dict(schema='gse-v53-source-control-resources-v1',status='PASS',cases=[dict(case=name,drops=3 if name=='exhausted-offer' else 1) for name in CASES],
                  execution='loopback-tcp-component',completeMembershipHistory=False,phase3Complete=False)
    need(a.collection.read_json(root,'receipt.json',65536)==expected,'source resources receipt scope')
    result=[dict(case=name,resources=case(root/name,name)[0]) for name in CASES]
    need(a.collection.inventory(root)==before,'source resources original changed')
    return dict(status='PASS',cases=result,wholeRuntimeResourcesQualified=False,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');args=p.parse_args()
    print(json.dumps(validate(args.root),sort_keys=True))
