"""Actual automatic-owner observations; no reconstruction from final diagnostics.

This checks collection/state transitions and original READY callback linkage.
It does not replace physical, ballot, network or client-completion replay.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile

from . import competing_node_evidence as p
from . import joining_history_run as h

need=p.need;FILE='automatic-lifecycle.json'
FIELDS={'node','ordinal','event','state','rounds','pending','originalStarted','detail','afterEvent','nanoTime'}
EVENTS={'START','ROUND_BEGIN','READY','LOSS','RESTART','SESSION_CLOSED','SESSION_OPENED','FAILED','TERMINATED','CLOSE','DRAINED'}
STATES={'NEW','STARTING','READY','RESTARTING','FAILED','CLOSED'}
LOSSES={'HIGHER_BALLOT','VIEW_CHANGED','CONTACT_UNAVAILABLE'}


def timeline(events,rows,nodes):
    need(type(rows) is list and 0<len(rows)<=256,'automatic lifecycle bounded observations')
    previous=-1;clock=-1;ordinals=dict.fromkeys(nodes,0);by_node={v:[] for v in nodes}
    for row in rows:
        need(type(row) is dict and set(row)==FIELDS and row['node'] in nodes and row['event'] in EVENTS and
             row['state'] in STATES and type(row['detail']) is str and len(row['detail'])<=256,
             'automatic lifecycle observation shape')
        node=row['node'];after=row['afterEvent'];at=row['nanoTime']
        need(type(after) is int and -1<=after<len(events) and type(at) is int and at>=clock and after>=previous and
             (after<0 or events[after]['nanoTime']<=at) and (after+1==len(events) or at<=events[after+1]['nanoTime']),
             'automatic lifecycle original event anchor')
        need(type(row['ordinal']) is int and row['ordinal']==ordinals[node]+1,'automatic lifecycle complete ordinal')
        need(type(row['rounds']) is int and 0<=row['rounds']<=3 and type(row['pending']) is int and 0<=row['pending']<=64 and
             type(row['originalStarted']) is int and 0<=row['originalStarted']<=at,'automatic lifecycle bounded counters')
        ordinals[node]+=1;by_node[node].append(row);previous,clock=after,at
    need(all(by_node.values()),'automatic lifecycle missing owner')
    return by_node


def owner(events,rows,*,opened_after=None):
    node=rows[0]['node'];state='NEW';rounds=0;began=None;session=True;fresh=False;active=False
    lost=False;restart=False;terminated=False;drained=False;ready=[];losses=[];begin=-1
    for row in rows:
        event=row['event'];detail=row['detail'];after=row['afterEvent']
        need(not drained or event in ('CLOSE','DRAINED'),'automatic lifecycle activity after drain')
        if event=='START':
            need(state=='NEW' and began is None,'automatic lifecycle single start');state='STARTING';began=row['originalStarted']
            if opened_after is None:
                opens=[i for i,v in enumerate(events) if v['node']==node and v['event']=='NODE_OPEN']
                need(len(opens)==1 and opens[0]<=after,'automatic lifecycle start before node open')
            else:
                # The restart reader binds an actual owner-construction sidecar
                # before supplying this anchor; no synthetic NODE_OPEN is added.
                need(type(opened_after) is int and -1<=opened_after<=after<len(events),
                     'automatic lifecycle start before observed construction')
        elif event=='ROUND_BEGIN':
            need(began is not None and not terminated and state in ('STARTING','RESTARTING','CLOSED') and
                 (state=='CLOSED' or session and (rounds==0 or fresh)), 'automatic lifecycle round without fresh session')
            rounds+=1;active=True;fresh=False;lost=False;restart=False;begin=after
        elif event=='READY':
            need(active and state in ('STARTING','RESTARTING') and re.fullmatch('[0-9a-f]{64}',detail),
                 'automatic lifecycle ready without live round')
            markers=[i for i,v in enumerate(events) if begin<i<=after and v['node']==node and v['event']=='ROUND_BEFORE_READY'
                     and v.get('record')==detail]
            need(len(markers)==1 and markers[0] not in ready,'automatic lifecycle original ready callback')
            _,ack=p.record(events[markers[0]],'wire','PUBLISH_ACK')
            need(ack['sender']['node']==node and ack['recipient']==ack['sender'] and ack['sequence']==1,
                 'automatic lifecycle local barrier completion')
            ready.append(markers[0]);state='READY'
        elif event=='LOSS':
            need(active and not lost and not terminated and detail in LOSSES,'automatic lifecycle typed active loss')
            active=False;lost=True;losses.append(detail)
        elif event=='RESTART':
            need(lost and state in ('STARTING','READY','RESTARTING') and not restart and rounds<3,
                 'automatic lifecycle unauthorized restart')
            state='RESTARTING';restart=True
        elif event=='SESSION_CLOSED':
            need(session and state in ('RESTARTING','FAILED','CLOSED'),'automatic lifecycle session close order');session=False
        elif event=='SESSION_OPENED':
            need(restart and not session and not terminated and state in ('RESTARTING','CLOSED'),
                 'automatic lifecycle fresh session before old drain')
            session=True;fresh=True
        elif event=='FAILED':
            need(began is not None and state not in ('FAILED','CLOSED') and not terminated and detail,
                 'automatic lifecycle terminal failure order');state='FAILED'
        elif event=='CLOSE':state='CLOSED'
        elif event=='TERMINATED':
            need(began is not None and not terminated and state in ('FAILED','CLOSED') and detail in ('DRAINED','RETAINED') and
                 row['pending']==0 and (detail!='DRAINED' or not session),'automatic lifecycle worker termination order')
            terminated=True
        elif event=='DRAINED':
            need(state=='CLOSED' and not session and row['pending']==0 and (began is None or terminated),
                 'automatic lifecycle premature drain');drained=True
        need(row['state']==state and row['rounds']==rounds,'automatic lifecycle exact state and round')
        need(row['originalStarted']==(began or 0),'automatic lifecycle renewed original deadline')
        if event not in ('READY','LOSS','FAILED','TERMINATED'):need(detail=='','automatic lifecycle unexpected detail')
    need(drained and state=='CLOSED','automatic lifecycle incomplete close')
    return dict(node=node,rounds=rounds,losses=losses,readyCallbacks=ready,started=began is not None,drained=drained)


def validate(root):
    root=Path(root);before=h.inventory(root)
    events=h.read_json(root,'events.json',16*1024*1024);p.trace(root)
    rows=h.read_json(root,FILE,1024*1024);nodes=p.c.NODES
    by_node=timeline(events,rows,nodes);owners=[owner(events,by_node[v]) for v in nodes]
    need(all(v['started'] for v in owners),'automatic lifecycle all original owners started')
    need((root/'failure.txt').read_bytes()==(root/'close-failure.txt').read_bytes()==b'',
         'automatic lifecycle retained execution or observation failure')
    drains=h.read_json(root,'drains.json',1024*1024)
    need(type(drains) is list and [v.get('node') for v in drains]==list(reversed(nodes)) and
         all(v.get('failure')=='' and type(v.get('leases')) is int and v['leases']==0 for v in drains),
         'automatic lifecycle original resource drains')
    need(h.inventory(root)==before,'automatic lifecycle original changed')
    return dict(status='PARTIAL',scope='automatic-owner-observed-lifecycle-collection',owners=owners,observations=len(rows),
                actualStateTransitionsQualified=True,originalDeadlinePreserved=True,physicalNetworkQualified=False,
                lossCauseQualified=False,fullLifecycleQualified=False,finalSourceCohortQualified=False,phase3Complete=False)


NEGATIVES={
    'missing-final-drain':'automatic lifecycle incomplete close',
    'duplicate-ordinal':'automatic lifecycle complete ordinal',
    'changed-origin':'automatic lifecycle renewed original deadline',
    'outside-anchor':'automatic lifecycle original event anchor',
    'early-clock':'automatic lifecycle original event anchor',
    'late-clock':'automatic lifecycle original event anchor',
    'boolean-round':'automatic lifecycle bounded counters',
    'missing-owner':'automatic lifecycle missing owner',
    'forged-readiness':'automatic lifecycle original ready callback',
    'forged-state':'automatic lifecycle exact state and round',
    'activity-after-drain':'automatic lifecycle activity after drain',
    'pending-at-termination':'automatic lifecycle worker termination order',
}


def mutate(root,name):
    need(name in NEGATIVES,'automatic lifecycle unknown mutation');root=Path(root)
    rows=h.read_json(root,FILE,1024*1024);events=h.read_json(root,'events.json',16*1024*1024)
    if name=='missing-final-drain':
        need(rows[-1]['event']=='DRAINED','automatic lifecycle mutation original drain');rows.pop()
    elif name=='duplicate-ordinal':rows.insert(1,dict(rows[0]))
    elif name=='changed-origin':next(v for v in rows if v['event']=='ROUND_BEGIN')['originalStarted']+=1
    elif name=='outside-anchor':rows[0]['afterEvent']=len(events)
    elif name=='early-clock':
        need(rows[0]['afterEvent']>=0,'automatic lifecycle mutation needs original anchor')
        rows[0]['nanoTime']=events[rows[0]['afterEvent']]['nanoTime']-1
    elif name=='late-clock':
        chosen=next(v for v in rows if v['afterEvent']+1<len(events))
        chosen['nanoTime']=events[chosen['afterEvent']+1]['nanoTime']+1
    elif name=='boolean-round':rows[0]['rounds']=True
    elif name=='missing-owner':rows=[v for v in rows if v['node']!=p.c.NODES[-1]]
    elif name=='forged-readiness':next(v for v in rows if v['event']=='READY')['detail']='f'*64
    elif name=='forged-state':rows[0]['state']='READY'
    elif name=='activity-after-drain':
        last=rows[-1];rows.append(dict(last,ordinal=last['ordinal']+1,event='READY',detail='f'*64,nanoTime=last['nanoTime']+1))
    elif name=='pending-at-termination':next(v for v in rows if v['event']=='TERMINATED')['pending']=1
    (root/FILE).write_bytes(p.f.canonical(rows))


def qualify(root):
    root=Path(root);original=validate(root);before=h.inventory(root);outcomes=[]
    protected={k:v for k,v in before['files'].items() if k!=FILE}
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-automatic-lifecycle-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name);after=h.inventory(changed)
            need({k:v for k,v in after['files'].items() if k!=FILE}==protected and after['directories']==before['directories'],
                 'automatic lifecycle negative changed protocol or physical input')
            try:validate(changed)
            except ValueError as error:need(str(error)==reason,'unrelated automatic lifecycle negative: '+name+': '+str(error))
            else:raise ValueError('automatic lifecycle mutation accepted: '+name)
        outcomes.append(dict(case=name,status='REJECTED',reason=reason))
    need(h.inventory(root)==before,'automatic lifecycle negative changed original')
    return dict(original=original,negatives=outcomes)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');a=parser.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.root),sort_keys=True))
