"""Whole-replica ledger writes from original revisions and file-prefix anchors.

Ledger contents are derived by the existing continuous retention reducer. Other
files come from the independent transaction models at their original callbacks.
No captured bytes, final revision counter or declared PASS is expected authority.
"""
from bisect import bisect_left
from . import native_carried_transition_retention as retention
from . import native_carried_transition_forces as forces
from .native_campaign_files import physical

need=forces.need
KINDS={'peer':('RETENTION_',),'future':('FUTURE_RETENTION_',)}
FILES={'peer':('peer-retention.gspr','peer-retention.next.gspr'),
       'future':('future-retention.gsft','future-retention.next.gsft')}
WRITES={kind:tuple(('RETENTION_' if kind=='peer' else 'FUTURE_RETENTION_')+v for v in
    ('BEFORE_WRITE','PREFIX_WRITTEN','WRITTEN','FORCED','CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED')) for kind in KINDS}
RESEALS={'peer':tuple(retention.peer.RESEAL),'future':tuple(retention.future.RESEAL)}
POINTS={point:kind for kind in KINDS for point in WRITES[kind]+RESEALS[kind]}
ANCHORS={('peer','maintenance'):'FLOOR_BEFORE_RETURN',('peer','selected'):'INSTALL_PARENT_FORCED',
         ('peer','publication'):'PUBLICATION_RETIRED',('future','record'):'APPLY_BEFORE_RETURN',
         ('future','clear'):'PUBLICATION_RETIRED'}


def transaction(initial,before,after,kind):
    need(kind in KINDS and type(before) is bytes and type(after) is bytes and len(after)>44 and before!=after,
         'ledger prefix original revision')
    active,candidate=FILES[kind]
    need(initial.get(active)==physical({active:before})[active] and candidate not in initial,
         'ledger prefix original active/candidate')
    state=dict(initial);steps=[]
    for at,point in enumerate(WRITES[kind]):
        if at==1:state[candidate]=physical({candidate:after[:len(after)//2]})[candidate]
        elif at==2:state[candidate]=physical({candidate:after})[candidate]
        elif at==5:state[active]=state.pop(candidate)
        steps.append((kind,point,dict(state)))
    return steps


class Peers(retention.PeerReplay):
    def __init__(self,root,kind):super().__init__(root,kind);self.raw_changes=[];self.raw_reseals=[]

    def sequence(self,node,changes,lower,upper,kind):
        super().sequence(node,changes,lower,upper,kind)
        actual=[v for v in self.tx if v['node']==node and lower<v['start'] and v['end']<upper]
        for tx,(before,after,_) in zip(actual,changes):
            self.raw_changes.append(dict(tx,kind=kind,ledger='peer',before=before,after=after))

    def reseal(self,row):
        super().reseal(row)
        indices=[i for i,v in enumerate(self.events[:row['peer']+1]) if v.get('node')==row['node'] and v['event'] in RESEALS['peer']][-2:]
        self.raw_reseals.append(dict(node=row['node'],life=row['life'],ledger='peer',indices=indices,raw=self.state[row['node']]))


class Future(retention.FutureReplay):
    def __init__(self,root,kind):super().__init__(root,kind);self.raw_changes=[];self.raw_reseals=[]

    def change(self,node,meta,records,tx,kind,index):
        before=self.state[node]['raw'];super().change(node,meta,records,tx,kind,index)
        self.raw_changes.append(dict(tx,kind=kind,ledger='future',before=before,after=self.state[node]['raw']))

    def reseal(self,row):
        super().reseal(row)
        self.raw_reseals.append(dict(node=row['node'],life=row['life'],ledger='future',indices=row['futureEvents'],raw=self.state[row['node']]['raw']))


def plans(root,kind,cut):
    """Project every original write/reseal, preserving the continuous two lives."""
    peers=Peers(root,kind);peer_result=peers.run();future=Future(root,kind);future_result=future.run()
    need(peers.events==future.events,'ledger prefix original event stream');events=peers.events
    death=next(i for i,v in enumerate(events) if v['event']=='GROUP_CRASH');offset={1:0,2:death+1}
    parts=[[] for _ in range(5)]
    forces.replay(root,kind,cut,prefixes=parts[0],floor_prefixes=parts[1],campaign_prefixes=parts[2],
                  vote_prefixes=parts[3],completion_prefixes=parts[4])
    anchors={};by_node={node:[] for node in peers.history.old}
    for row in (v for part in parts for v in part):
        at=offset[row['life']]+row['eventIndex'];need(at not in anchors,'ledger prefix duplicate original anchor')
        need(events[at].get('node')==row['node'] and events[at]['event']==row['point'],'ledger prefix anchor callback')
        anchors[at]=row;by_node[row['node']].append(at)
    for values in by_node.values():values.sort()
    initial=peers.initial_states()
    cold={1:initial,2:forces.group(root,'before-reopen')}
    ledgers={node:{key:raw for key,raw in files.items() if key in {names[0] for names in FILES.values()}} for node,files in initial.items()}
    writes={};reseals={};transactions={}
    for tx in peers.raw_changes+future.raw_changes:
        node,ledger=tx['node'],tx['ledger']
        indices=[i for i in range(tx['start'],tx['end']+1) if events[i].get('node')==node and events[i]['event'] in WRITES[ledger]]
        need([events[i]['event'] for i in indices]==list(WRITES[ledger]),'ledger prefix original transaction callbacks')
        need(tx['start'] not in transactions,'ledger prefix duplicate transaction');transactions[tx['start']]=(tx,indices)
        for ordinal,at in enumerate(indices):
            need(at not in writes,'ledger prefix duplicate write');writes[at]=(tx,ordinal)
    for row in peers.raw_reseals+future.raw_reseals:
        need([events[i]['event'] for i in row['indices']]==list(RESEALS[row['ledger']]),'ledger prefix original reseal callbacks')
        for at in row['indices']:need(at not in reseals,'ledger prefix duplicate reseal');reseals[at]=row
    expected=[];active={};anchor_checks=0
    for at in sorted(set(anchors)|set(writes)|set(reseals)):
        row=events[at];node=row['node']
        if at in anchors:
            for name,raw in ledgers[node].items():
                need(anchors[at]['files'].get(name)==physical({name:raw})[name],'ledger prefix anchor continuous revision')
            anchor_checks+=1
        elif at in writes:
            tx,ordinal=writes[at];ledger=tx['ledger'];name,_=FILES[ledger]
            if ordinal==0:
                need(ledgers[node][name]==tx['before'] and node not in active,'ledger prefix continuous original predecessor')
                places=by_node[node];position=bisect_left(places,at)-1;need(position>=0,'ledger prefix missing original anchor')
                previous=places[position];anchor=anchors[previous]
                need(anchor['point']==ANCHORS[ledger,tx['kind']] and (previous<death)==(at<death),
                     'ledger prefix exact operation anchor')
                state=dict(anchor['files']);state.update(physical(ledgers[node]))
                active[node]=transaction(state,tx['before'],tx['after'],ledger)
            plan=active[node][ordinal];need(plan[1]==row['event'],'ledger prefix exact original write')
            expected.append(dict(life=1 if at<death else 2,eventIndex=at if at<death else at-death-1,
                                 node=node,kind=ledger,point=plan[1],files=plan[2]))
            if ordinal==5:ledgers[node][name]=tx['after']
            if ordinal==6:del active[node]
        else:
            seal=reseals[at];ledger=seal['ledger'];name,_=FILES[ledger]
            need(node not in active and ledgers[node][name]==seal['raw'],'ledger prefix original reseal revision')
            before=cold[seal['life']][node]
            state=physical(before)
            for key,raw in ledgers[node].items():need(state[key]==physical({key:raw})[key],'ledger prefix cold original revision')
            expected.append(dict(life=seal['life'],eventIndex=at-offset[seal['life']],node=node,kind=ledger,point=row['event'],files=state))
    need(not active and {offset[v['life']]+v['eventIndex'] for v in expected}=={i for i,v in enumerate(events) if v['event'] in POINTS},
         'ledger prefix complete original callback coverage')
    return expected,dict(peers=peer_result,future=future_result,anchorChecks=anchor_checks,
                         transactions=len(transactions),resealCallbacks=len(reseals))
