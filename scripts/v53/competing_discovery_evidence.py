"""Bootstrap discovery interrupted before reservation; never a grant or vote.

The enclosing physical/network/export replay remains mandatory. These probes
are bound to the actual owner round and a later independently replayed remote
grant. Only a delivered prefix of the configured discovery order is admitted.
"""
import copy
from pathlib import Path
from . import competing_pregrant_evidence as pregrant

p=pregrant.prefix;lifecycle=pregrant.lifecycle;need=p.need


def claim(replay,node,stop):
    lifecycle.validate(replay.root)
    indices=[i for i,v in enumerate(replay.events) if v['event']!=p.g.EVENT]
    need([replay.events[i] for i in indices]==p.p.trace(replay.root),'competing discovery original event mapping')
    life=p.p.n.read(replay.root/lifecycle.FILE)
    own=[v for v in life if v['node']==node]
    need([v['event'] for v in own]==['START','ROUND_BEGIN','CLOSE','SESSION_CLOSED','TERMINATED','DRAINED'] and
         own[1]['rounds']==1 and own[1]['pending']==0,'competing discovery original owner round')
    begin=-1 if own[1]['afterEvent']==-1 else indices[own[1]['afterEvent']]
    closed=indices[own[2]['afterEvent']]
    need(not any(v['node']==node for v in replay.allocations),'competing discovery unexpected reservation')
    prior=p.f.decode(p.disk.current(replay.initial[node])[1]['promise.gsr'],'records','PROMISE')['ballot']
    caps=[v for v in replay.by_basis.values() if v['node']==node]
    need(len(caps)==1 and caps[0]['ballot']['proposer']!=node and
         p.journal.order(caps[0]['ballot'])>p.journal.order(prior),'competing discovery original higher grant')
    cap=caps[0];grant=replay.starts[cap['basisSha256']]
    incoming=[v for v in replay.attempts if v['kind']=='PREPARE' and v['request']['recipient']['node']==node
              and v['request']['ballot']==cap['ballot']]
    need(incoming and all(v['received'] is not None and begin<v['sent']<v['received']<grant for v in incoming),
         'competing discovery original incoming grant')
    rows=[v for v in replay.rows if v['kind']=='STATUS_PROBE' and v['request']['sender']['node']==node
          and v['offered']<stop and v['request']['trace'] not in replay.maintenance_traces]
    return dict(node=node,prior=prior,begin=begin,closed=closed,grant=grant,stop=stop,
        peers=sorted(set(replay.identities)-{node}),
        cuts={peer:p.disk.current(replay.initial[peer])[2]['capsule']['cut'] for peer in replay.identities},
        rows=rows)


def bind(value):
    node=value['node'];rows=sorted(value['rows'],key=lambda v:v['sent']);groups={}
    need(value['begin']<value['grant']<value['stop']<=value['closed'],'competing discovery original round interval')
    for row in rows:groups.setdefault(row['request']['recipient']['node'],[]).append(row)
    need(groups and list(groups)==value['peers'][:len(groups)],'competing discovery ordered peer prefix')
    lower=value['begin']
    for peer,attempts in groups.items():
        first=attempts[0];q=first['request']
        need(0<len(attempts)<=3 and q['sender']['node']==node and q['ballot']==value['prior'] and q['sequence']==1 and
             all(v['request']==q and v['answer']=='STATUS' and
                 v['response']['payload']==dict(cut=value['cuts'][peer],nonce=q['payload']['nonce'],ready=False)
                 for v in attempts),'competing discovery exact bootstrap status')
        need(all(v['delivered'] is not None and lower<v['sent']<v['received']<v['offered']<v['delivered']<value['grant']
                 for v in attempts),'competing discovery delivery before higher grant')
        lower=max(v['delivered'] for v in attempts)
    return dict(node=node,probes=len(rows),peers=list(groups),localReservationCreated=False,localGrantCreated=False)


def consume(replay,phase,stop):
    allocated={v['node'] for v in replay.allocations}
    nodes=sorted({sender for kind,sender,_ in phase.controls if kind=='STATUS_PROBE'}-allocated)
    results=[]
    for node in nodes:
        value=claim(replay,node,stop);results.append(bind(value));lower=value['begin']
        for peer in results[-1]['peers']:
            lower=phase.probe(node,peer,value['prior'],value['cuts'][peer],lower,value['grant'])
    return results


NEGATIVES={
    'missing-probe':'competing discovery ordered peer prefix',
    'skipped-peer':'competing discovery ordered peer prefix',
    'changed-ballot':'competing discovery exact bootstrap status',
    'invented-ready':'competing discovery exact bootstrap status',
    'late-delivery':'competing discovery delivery before higher grant',
    'probe-before-round':'competing discovery delivery before higher grant',
}


def mutate(value,name):
    need(name in NEGATIVES,'competing discovery unknown mutation')
    if name=='missing-probe':value['rows']=[]
    elif name=='skipped-peer':value['peers'].reverse()
    elif name=='changed-ballot':value['rows'][0]['request']['ballot']['counter']+=1
    elif name=='invented-ready':value['rows'][0]['response']['payload']['ready']=True
    elif name=='late-delivery':value['rows'][0]['delivered']=value['grant']
    else:value['rows'][0]['sent']=value['begin']


def qualify(root):
    from . import competing_export_evidence as exports
    root=Path(root);before=p.collection.h.inventory(root)
    reader=exports.Replay(root);original=reader.run();replay=reader.replay
    observed=original['precondition'].get('discoveryOnly',[])
    need(len(observed)==1,'competing discovery qualification scope')
    value=claim(replay,observed[0]['node'],reader.activation_at)
    # Mutate copied derived probe claims only. Native bytes are untouched;
    # original validation above is never replaced by these negative results.
    bind(value);results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(value);mutate(changed,name)
        try:bind(changed)
        except ValueError as error:need(str(error)==reason,'competing discovery unrelated negative: '+name+': '+str(error))
        else:raise ValueError('competing discovery mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(p.collection.h.inventory(root)==before,'competing discovery original changed')
    return dict(original=original,negativeScope='derived-claims-not-native-fault-executions',negatives=results)
