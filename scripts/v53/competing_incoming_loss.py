"""A completed local grant fenced by an original incoming higher PREPARE.

No reply from the losing campaign is manufactured. Its optional unanswered
PREPARE and reverse first-object requests remain bounded, uncommitted attempts.
The complete physical/network history must pass before these claims are used.
"""
import copy
from pathlib import Path
from . import competing_pregrant_evidence as p

need=p.need


def claim(replay,allocation,local,loss,stop):
    return dict(allocation=allocation,local=local,loss=loss,stop=stop,
                identities=replay.identities,captures=list(replay.by_basis.values()),
                selections=list(replay.selections.values()),attempts=replay.attempts,rows=replay.rows)


def bind(value):
    a=value['allocation'];local=value['local'];loss=value['loss'];stop=value['stop']
    node=a['node'];ballot=a['ballot'];at=loss['afterEvent'];ids=value['identities']
    need(loss['node']==node and loss['event']=='LOSS' and loss['detail']=='HIGHER_BALLOT' and
         loss['state']=='STARTING' and loss['rounds']==1 and loss['pending']==0 and
         a['end']<local['returnEvent']<local['capturedEvent']<at<stop,
         'competing incoming actual local-grant loss')
    caps=value['captures'];old=[v for v in caps if v['ballot']==ballot]
    need(old==[local] and local['node']==node and
         not any(v['value']['ballot']==ballot for v in value['selections']) and
         not any(v['request']['ballot']==ballot for v in value['rows']),
         'competing incoming no old remote grant or reply')
    incoming=[v for v in value['attempts'] if v['kind']=='PREPARE' and v['request']['recipient']==ids[node]
              and v['received'] is not None and a['end']<v['received']<=at and
              p.prefix.journal.order(v['request']['ballot'])>p.prefix.journal.order(ballot)]
    need(incoming and len(incoming)<=3 and all(v['request']==incoming[0]['request'] for v in incoming),
         'competing incoming original higher request')
    cause=incoming[0];q=cause['request'];sender=q['sender']['node'];higher=q['ballot']
    sources=[v for v in caps if v['node']==sender and v['ballot']==higher]
    granted=[v for v in caps if v['node']==node and v['ballot']==higher]
    need(q['sender']==ids[sender] and higher['proposer']==sender and len(sources)==len(granted)==1 and
         sources[0]['capturedEvent']<cause['sent']<cause['received']<=at and
         q['payload']==dict(promise=p.prefix.sha(sources[0]['promise'])) and
         local['capturedEvent']<granted[0]['returnEvent'],
         'competing incoming original higher promise')
    attempts=[v for v in value['attempts'] if v['request']['ballot']==ballot]
    prepares=[v for v in attempts if v['kind']=='PREPARE'];pulls=[v for v in attempts if v['kind']=='CHUNK']
    need(len(prepares)<=1 and len(prepares)+len(pulls)==len(attempts),
         'competing incoming bounded losing requests')
    if prepares:
        prepare=prepares[0];request=prepare['request'];peer=request['recipient']['node']
        need(request['sender']==ids[node] and request['recipient']==ids[peer] and peer!=node and
             request['sequence']==sorted(set(ids)-{node}).index(peer)+1 and
             request['payload']==dict(promise=p.prefix.sha(local['promise'])) and prepare['received'] is not None and
             local['capturedEvent']<prepare['sent']<prepare['received']<=at,
             'competing incoming exact losing PREPARE')
        if pulls:
            first=pulls[0];r=first['request'];payload=r['payload']
            need(0<len(pulls)<=3 and r['sender']==ids[peer] and r['recipient']==ids[node] and r['sequence']==1 and
                 payload==dict(id=payload['id'],action='REQUEST',offset=0,digest=p.prefix.sha(local['promise']),bytes='') and
                 all(v['request']==r and v['received'] is not None and prepare['received']<v['sent']<v['received']<stop for v in pulls) and
                 all(x['received']<y['sent'] for x,y in zip(pulls,pulls[1:])),
                 'competing incoming exact unanswered promise pull')
    else:need(not pulls,'competing incoming pull without PREPARE')
    return dict(node=node,ballot=ballot,localGrant=local['capturedEvent'],higherBallot=higher,
                higherRequest=cause['received'],lossAt=at,remoteGrants=0,selected=False,
                cause='incoming-prepare',unanswered=[v['sent'] for v in attempts])


NEGATIVES={
    'wrong-loss':'competing incoming actual local-grant loss',
    'invented-reply':'competing incoming no old remote grant or reply',
    'invented-selection':'competing incoming no old remote grant or reply',
    'missing-higher-request':'competing incoming original higher request',
    'forged-higher-promise':'competing incoming original higher promise',
    'missing-higher-grant':'competing incoming original higher promise',
    'extra-losing-request':'competing incoming bounded losing requests',
}


def mutate(v,name):
    a=v['allocation'];ballot=a['ballot'];node=a['node']
    if name=='wrong-loss':v['loss']['detail']='CONTACT_UNAVAILABLE'
    elif name=='invented-reply':v['rows'].append(dict(request=dict(ballot=ballot)))
    elif name=='invented-selection':v['selections'].append(dict(value=dict(ballot=ballot)))
    elif name=='extra-losing-request':v['attempts'].append(dict(kind='APPLY',request=dict(ballot=ballot)))
    else:
        higher=next(x for x in v['attempts'] if x['kind']=='PREPARE' and x['request']['recipient']==v['identities'][node]
                    and p.prefix.journal.order(x['request']['ballot'])>p.prefix.journal.order(ballot))
        if name=='missing-higher-request':v['attempts']=[x for x in v['attempts'] if x['request']!=higher['request']]
        elif name=='forged-higher-promise':higher['request']['payload']['promise']='0'*64
        else:v['captures']=[x for x in v['captures'] if not (x['node']==node and x['ballot']==higher['request']['ballot'])]


def qualify(root):
    from . import competing_export_evidence as exports
    root=Path(root);before=p.prefix.collection.h.inventory(root);reader=exports.Replay(root);original=reader.run();r=reader.replay
    losses=original['precondition'].get('localGrantLosses',[])
    need(len(losses)==1 and losses[0].get('cause')=='incoming-prepare','competing incoming qualification scope')
    observed=losses[0];a=next(v for v in r.allocations if v['node']==observed['node'] and v['ballot']==observed['ballot'])
    local=next(v for v in r.by_basis.values() if v['node']==a['node'] and v['ballot']==a['ballot'])
    indices=[i for i,v in enumerate(r.events) if v['event']!=p.prefix.g.EVENT]
    loss=next(dict(v,afterEvent=indices[v['afterEvent']]) for v in p.prefix.p.n.read(root/p.lifecycle.FILE)
              if v['node']==a['node'] and v['event']=='LOSS')
    value=claim(r,a,local,loss,reader.activation_at);need(bind(value)==observed,'competing incoming derived claim')
    results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(value);mutate(changed,name)
        try:bind(changed)
        except ValueError as error:need(str(error)==reason,'competing incoming unrelated negative: '+name+': '+str(error))
        else:raise ValueError('competing incoming accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(p.prefix.collection.h.inventory(root)==before,'competing incoming original changed')
    return dict(original=original,negativeScope='copied-derived-claims-after-complete-original-replay',negatives=results)
