"""A losing bootstrap may force its own BASIS without obtaining a majority.

Bind that observed loss to a delivered higher-ballot rejection. Unanswered
PREPAREs remain unanswered; a local durable grant never becomes an installation.
The caller must first replay the complete physical/publication history.
"""
from pathlib import Path
import shutil
import tempfile
from . import competing_pregrant_evidence as pregrant

prefix=pregrant.prefix;need=prefix.need;lifecycle=pregrant.lifecycle


def bind(replay,allocation,local,loss,stop):
    node=allocation['node'];ballot=allocation['ballot'];at=loss['afterEvent']
    need(loss['node']==node and loss['event']=='LOSS' and loss['detail']=='HIGHER_BALLOT'
         and loss['state']=='STARTING' and loss['rounds']==1 and loss['pending']==0
         and allocation['end']<local['returnEvent']<local['capturedEvent']<at<stop,
         'competing local-grant actual first-round loss')
    caps=[v for v in replay.by_basis.values() if v['ballot']==ballot]
    need(caps==[local] and local['node']==node and
         not any(v['value']['ballot']==ballot for v in replay.selections.values()),
         'competing local-grant cannot select a majority')
    asks=[v for v in replay.attempts if v['request']['ballot']==ballot]
    peers=sorted(set(replay.identities)-{node})
    need(asks and all(v['kind']=='PREPARE' and v['request']['sender']==replay.identities[node]
         and v['request']['recipient'] in [value for key,value in replay.identities.items() if key!=node]
         and v['request']['payload']==dict(promise=prefix.sha(local['promise']))
         and v['request']['sequence']==peers.index(v['request']['recipient']['node'])+1
         and v['request']['trace']==asks[0]['request']['trace'] and v['received'] is not None
         and local['capturedEvent']<v['sent']<v['received']<=at for v in asks),
         'competing local-grant exact original PREPAREs')
    replies=[v for v in replay.rows if v['request']['ballot']==ballot]
    need(len(replies)==1,'competing local-grant one rejection')
    reply=replies[0];q=reply['request'];higher=reply['response']['payload'].get('promised')
    need(reply['answer']=='REJECT' and type(higher) is dict and
         prefix.journal.order(higher)>prefix.journal.order(ballot) and
         reply['response']['payload']==dict(promised=higher,reason='STALE_EPOCH') and
         reply['delivered'] is not None and reply['sent']<reply['received']<reply['offered']<reply['delivered']<=at,
         'competing local-grant delivered higher rejection')
    rejecting=[v for v in replay.by_basis.values() if v['node']==q['recipient']['node'] and v['ballot']==higher]
    need(len(rejecting)==1 and rejecting[0]['capturedEvent']<reply['received'],
         'competing local-grant original higher promise')
    need(sum(v['sent']==reply['sent'] and v['request']==q for v in asks)==1,
         'competing local-grant rejection request binding')
    unanswered=[v for v in asks if v['sent']!=reply['sent']]
    # The observed loser exhausted one peer, then received a rejection from the
    # other. Do not infer successful replies or generalize to arbitrary retries.
    need(len(unanswered)==3 and len({v['request']['recipient']['node'] for v in unanswered})==1
         and unanswered[0]['request']['recipient']!=q['recipient']
         and all(v['request']==unanswered[0]['request'] for v in unanswered)
         and all(unanswered[i]['received']<unanswered[i+1]['sent'] for i in range(2))
         and unanswered[-1]['received']<reply['sent'],
         'competing local-grant bounded unanswered PREPAREs')
    return dict(node=node,ballot=ballot,localGrant=local['capturedEvent'],higherBallot=higher,
                rejection=reply['delivered'],lossAt=at,remoteGrants=0,selected=False,
                unanswered=[v['sent'] for v in unanswered]),reply


def validate(replay,allocation,local,stop,phase):
    lifecycle.validate(replay.root)
    indices=[i for i,v in enumerate(replay.events) if v['event']!=prefix.g.EVENT]
    need([replay.events[i] for i in indices]==prefix.p.trace(replay.root),
         'competing local-grant original event mapping')
    rows=prefix.p.n.read(replay.root/lifecycle.FILE)
    losses=[dict(v,afterEvent=indices[v['afterEvent']]) for v in rows if v['node']==allocation['node']
            and v['event']=='LOSS' and v['afterEvent']>=0 and allocation['end']<indices[v['afterEvent']]<stop]
    need(len(losses)==1,'competing local-grant exact observed loss')
    begins=[v for v in rows if v['node']==allocation['node'] and v['event']=='ROUND_BEGIN' and v['rounds']==1]
    need(len(begins)==1 and begins[0]['ordinal']<losses[0]['ordinal'] and
         (-1 if begins[0]['afterEvent']==-1 else indices[begins[0]['afterEvent']])<allocation['start'],
         'competing local-grant round before allocation')
    if not any(v['request']['ballot']==allocation['ballot'] for v in replay.rows):
        from . import competing_incoming_loss as incoming
        return incoming.bind(incoming.claim(replay,allocation,local,losses[0],stop))
    result,reply=bind(replay,allocation,local,losses[0],stop)
    q=reply['request']
    phase.control('PREPARE',allocation['node'],q['recipient']['node'],q['payload'],'REJECT',
                  reply['response']['payload'],allocation['ballot'],local['capturedEvent'],stop,sequence=q['sequence'])
    return result


NEGATIVES={
    'changed-loss-cause':'competing local-grant actual first-round loss',
    'loss-before-rejection':'competing local-grant delivered higher rejection',
    **{k:v for k,v in pregrant.NEGATIVES.items() if k not in ('changed-loss-cause','loss-before-higher-request')},
}


def mutate(root,name):
    root=Path(root);need(name in NEGATIVES,'competing local-grant unknown mutation')
    if name!='loss-before-rejection':return pregrant.mutate(root,name)
    rows=prefix.p.n.read(root/lifecycle.FILE);events=prefix.p.n.read(root/'events.json')
    losses=[v for v in rows if v['event']=='LOSS']
    need(len(losses)==1,'competing local-grant mutation original loss');loss=losses[0]
    at=loss['afterEvent']
    need(events[at]['event']=='NETWORK_RECEIVED','competing local-grant mutation rejection anchor')
    for row in rows:
        if row['node']==loss['node'] and loss['ordinal']<=row['ordinal']<=loss['ordinal']+4:
            row.update(afterEvent=at-1,nanoTime=events[at-1]['nanoTime'])
    (root/lifecycle.FILE).write_bytes(prefix.f.canonical(rows))


def qualify(root):
    from . import competing_export_evidence as exports
    root=Path(root);before=prefix.collection.h.inventory(root)
    reader=exports.Replay(root);original=reader.run()
    need(not reader.replay.transactions and reader.partial is None and
         len(original['precondition'].get('localGrantLosses',[]))==1,'competing local-grant qualification scope')
    results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-local-grant-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
            try:exports.validate(changed)
            except ValueError as error:need(str(error)==reason,'unrelated competing local-grant negative: '+name+': '+str(error))
            else:raise ValueError('competing local-grant mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(prefix.collection.h.inventory(root)==before,'competing local-grant original changed')
    return dict(original=original,negativeScope='copied-original-evidence-not-native-fault-executions',negatives=results)
