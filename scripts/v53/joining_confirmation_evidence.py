"""Conditional joining projection from original frozen confirmation ledgers.

Endpoint/ACK bindings below do not establish force or original capsule history.
The caller must bind each packet and ancestry to its retained native source;
complete physical/network replay remains a separate qualification gate.
"""
import base64
import copy
from . import peer_confirmation_evidence as confirmed
from .ancestry_pruning_evidence import frames

f, need, sha = confirmed.f, confirmed.need, confirmed.sha


def anchor(record, edge=None):
    if edge is None:return {k:record[k] for k in ('cut','catalog','application')}
    suffix='Before' if edge=='start' else 'After'
    return dict(cut=record[edge],catalog=record['catalog'+suffix],application=record['application'+suffix])


def remember(history, point, terminal):
    index=point['cut']['index']
    need(index<=terminal['cut']['index'] and (index not in history or history[index]==point),
         'joining confirmation inconsistent original endpoint')
    history[index]=point


def endpoints(packet, ancestry):
    """Check all supplied bridge bindings, even bridges not needed after merge."""
    cap=packet['capsule'];root=cap['root'];direct={cap['cut']['index']:anchor(cap)}
    identities={v['node']:v for v in f.decode(packet['objects'][cap['catalog']],'records','CATALOG',root)['identities']}
    for item in cap['items']:
        value=f.decode(packet['objects'][item['statement']],'records','CHECKPOINT',root)
        for edge in ('start','end'):remember(direct,anchor(value,edge),cap)
    groups=[]
    for raw in frames(ancestry) if ancestry else ():
        kind=int.from_bytes(raw[8:10],'big')
        if kind==f.catalog()['records']['CHECKPOINT']['id']:groups.append([raw])
        else:
            need(kind==f.catalog()['records']['CHECKPOINT_ACK']['id'] and groups,
                 'joining confirmation orphan ancestry ACK')
            groups[-1].append(raw)
    need(len(groups)<=6,'joining confirmation ancestry count');lower={}
    for rows in groups:
        need(3<=len(rows)<=7 and sum(map(len,rows))<=16384,'joining confirmation ancestry extent')
        value=f.decode(rows[0],'records','CHECKPOINT',root);start=anchor(value,'start');end=anchor(value,'end')
        view=start['cut']['view'];index=start['cut']['index']
        need(value['scope']=='RANGE' and view['operation'] is None and view==end['cut']['view']
             and index<end['cut']['index'] and direct.get(end['cut']['index'])==end,
             'joining confirmation ancestry endpoints')
        voters=[]
        for raw in rows[1:]:
            ack=f.decode(raw,'records','CHECKPOINT_ACK',root);node=ack['voter'];voters.append(node)
            need(node in identities and ack==dict(root=root,voter=node,incarnation=identities[node]['storage'],
                 cut=end['cut'],statement=sha(rows[0])),'joining confirmation ancestry endorsement')
        need(voters==sorted(set(voters)) and set(voters)<=set(view['old']+view['new'])
             and all(len(set(voters)&set(view[k]))>len(view[k])//2 for k in ('old','new')),
             'joining confirmation ancestry quorum')
        need(index not in lower,'joining confirmation duplicate ancestry');lower[index]=start
        if index in direct:need(direct[index]==start,'joining confirmation inconsistent original endpoint')
    return lower | direct


def bind_endpoints(packet, ancestry, peer, learner):
    available=endpoints(packet,ancestry)
    points=[p for row in peer['peers'] for p in [*row.get('renewals',[]),*row['possible']]]
    points += [*learner.get('renewals',[]),*learner['possible']]
    for point in points:
        need(available.get(point['cut']['index'])==point,'joining confirmation original ancestry missing')


def merge(plans, current, identities, learner_points):
    """Release older peer debt only after validating every original obligation."""
    cap=current['capsule'];root=cap['root'];view=cap['cut']['view'];voters=sorted(set(view['old']+view['new']))
    need(2<=len(plans)<=5,'joining confirmation original count')
    history={cap['cut']['index']:anchor(cap)};union={n:{} for n in voters};proofs={}
    for plan in plans:
        confirmed.plan(plan)
        need(plan['root']==root and plan['view']==view,'joining confirmation original root/view')
        for node,row in zip(voters,plan['peers']):
            need(row['identity']==identities[node],'joining confirmation original permanent identity')
            for point in [*row.get('renewals',[]),*row['possible']]:
                remember(history,point,cap);union[node][point['cut']['index']]=copy.deepcopy(point)
            if 'confirmation' in row:
                value=row['confirmation'];point=confirmed.confirmation(value,root,row['identity'])
                order=(-point['cut']['index'],sha(base64.b64decode(value,validate=True)))
                if node not in proofs or order<proofs[node][0]:proofs[node]=(order,value,point)
    for point in learner_points:remember(history,point,cap)
    peers=[]
    for node in voters:
        points=union[node];row=dict(identity=identities[node])
        if node in proofs:
            _,value,point=proofs[node];row['confirmation']=value
            points={i:p for i,p in points.items() if i>=point['cut']['index']}
        need(1<=len(points)<=2,'joining confirmation unresolved endpoint capacity')
        row['possible']=[points[i] for i in sorted(points)];peers.append(row)
    result=dict(root=root,view=view,peers=peers);confirmed.plan(result);return result
