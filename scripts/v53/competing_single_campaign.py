"""One original campaign wins while the other automatic sessions remain idle.

This is a bootstrap scheduling outcome, not evidence of a competing ballot loss.
Complete physical/network/export replay and lifecycle validation precede claims
and mutations. Idle automatic sessions can still serve the winner's requests.
"""
import copy
from pathlib import Path
from . import competing_pregrant_evidence as pregrant

p=pregrant.prefix;life=pregrant.lifecycle;need=p.need


def claim(reader):
    r=reader.replay;indices=[i for i,v in enumerate(r.events) if v['event']!=p.g.EVENT]
    need([r.events[i] for i in indices]==p.p.trace(reader.root),'competing single original event mapping')
    owners={node:[] for node in r.initial}
    for row in p.p.n.read(reader.root/life.FILE):
        owners[row['node']].append(dict(row,afterEvent=-1 if row['afterEvent']==-1 else indices[row['afterEvent']]))
    return dict(nodes=sorted(r.initial),allocations=r.allocations,
        captures=[{k:v[k] for k in ('node','ballot','basisId','basisSha256')} for v in r.by_basis.values()],
        selections=list(r.selections.values()),bindings=r.bindings,owners=owners,stop=reader.activation_at,
        campaigns=[v for v in r.attempts if v['sent']<reader.activation_at and v['kind'] in ('STATUS_PROBE','PREPARE','SELECTED')])


def bind(v):
    allocations=v['allocations'];nodes=v['nodes'];stop=v['stop']
    need(len(allocations)==1,'competing single exact reservation')
    a=allocations[0];winner=a['node'];ballot=a['ballot']
    need(winner in nodes and ballot['proposer']==winner and a['start']<a['end']<stop,
         'competing single exact reservation')
    caps=v['captures'];voters={c['node'] for c in caps}
    need(len(caps)==len(voters)==2 and winner in voters and voters<=set(nodes) and
         all(c['ballot']==ballot for c in caps),'competing single exact grants')
    selections=v['selections']
    need(len(selections)==1 and selections[0]['value']['ballot']==ballot and
         sorted(selections[0]['value']['sources'],key=lambda c:c['voter'])==
         sorted([dict(voter=c['node'],basisId=c['basisId'],basisDigest=c['basisSha256']) for c in caps],key=lambda c:c['voter']),
         'competing single exact selected pair')
    digest=p.sha(selections[0]['raw']);bindings=v['bindings']
    need(len(bindings)==2 and {b['node'] for b in bindings}==voters and
         all(b['selection']==digest and a['end']<b['forced']<stop for b in bindings),
         'competing single both selection forces')
    need(v['campaigns'] and all(q['request']['sender']['node']==winner for q in v['campaigns']),
         'competing single no idle campaign requests')
    idle=['START','ROUND_BEGIN','CLOSE','SESSION_CLOSED','TERMINATED','DRAINED']
    need(set(v['owners'])==set(nodes),'competing single complete owner sessions')
    for node in nodes:
        rows=v['owners'][node];expected=idle[:2]+(['READY'] if node==winner else [])+idle[2:]
        need([r['event'] for r in rows]==expected and rows[0]['rounds']==0 and
             all(r['rounds']==1 and r['pending']==0 for r in rows[1:]),
             'competing single complete owner sessions')
        need(rows[1]['afterEvent']<(a['start'] if node==winner else stop) and
             stop<=next(r['afterEvent'] for r in rows if r['event']=='CLOSE'),
             'competing single original owner interval')
    return dict(winner=winner,automaticOwners=len(nodes),nativeCampaigns=1,selectedVoters=sorted(voters),
                idleAutomaticSessions=sorted(set(nodes)-{winner}),competingLossQualified=False)


NEGATIVES={
    'missing-reservation':'competing single exact reservation',
    'extra-reservation':'competing single exact reservation',
    'changed-grant-ballot':'competing single exact grants',
    'extra-grant':'competing single exact grants',
    'changed-selected-source':'competing single exact selected pair',
    'missing-selection-force':'competing single both selection forces',
    'invented-idle-discovery':'competing single no idle campaign requests',
    'missing-idle-owner':'competing single complete owner sessions',
    'invented-idle-loss':'competing single complete owner sessions',
    'late-owner-start':'competing single original owner interval',
}


def mutate(v,name):
    need(name in NEGATIVES,'competing single unknown mutation')
    winner=v['allocations'][0]['node'];idle=next(n for n in v['nodes'] if n!=winner)
    if name=='missing-reservation':v['allocations']=[]
    elif name=='extra-reservation':v['allocations'].append(copy.deepcopy(v['allocations'][0]))
    elif name=='changed-grant-ballot':v['captures'][0]['ballot']['counter']+=1
    elif name=='extra-grant':v['captures'].append(copy.deepcopy(v['captures'][0]))
    elif name=='changed-selected-source':v['selections'][0]['value']['sources'][0]['basisDigest']='f'*64
    elif name=='missing-selection-force':v['bindings'].pop()
    elif name=='invented-idle-discovery':v['campaigns'].append(dict(kind='STATUS_PROBE',request=dict(sender=dict(node=idle))))
    elif name=='missing-idle-owner':del v['owners'][idle]
    elif name=='invented-idle-loss':v['owners'][idle].insert(2,dict(event='LOSS'))
    else:v['owners'][idle][1]['afterEvent']=v['stop']


def qualify(root):
    from . import competing_export_evidence as exports
    root=Path(root);before=p.collection.h.inventory(root);reader=exports.Replay(root);original=reader.run()
    life.validate(root)
    value=claim(reader);bind(value);outcomes=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(value);mutate(changed,name)
        try:bind(changed)
        except ValueError as error:need(str(error)==reason,'competing single unrelated negative: '+name+': '+str(error))
        else:raise ValueError('competing single accepted negative: '+name)
        outcomes.append(dict(case=name,status='REJECTED',reason=reason))
    need(p.collection.h.inventory(root)==before,'competing single original changed')
    return dict(original=original,negativeScope='copied-derived-claims-not-native-fault-executions',negatives=outcomes)
