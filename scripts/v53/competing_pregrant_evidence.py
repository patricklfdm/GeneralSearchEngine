"""Bind an observed pre-grant loss to original allocation and incoming PREPARE.

Only the observed bootstrap case is admitted. A diagnostic string alone cannot
invent a local grant, a higher request or a retry; the surrounding physical and
whole-network readers must also consume the original history.
"""
from . import competing_campaign_prefix as prefix
from . import automatic_lifecycle as lifecycle
import argparse
import json
from pathlib import Path
import shutil
import tempfile

need=prefix.need


def bind(events,attempts,captures,starts,allocation,loss,stop):
    node=allocation['node'];ballot=allocation['ballot'];at=loss['afterEvent']
    need(loss['node']==node and loss['event']=='LOSS' and loss['detail']=='HIGHER_BALLOT'
         and loss['state']=='STARTING' and loss['rounds']==1 and loss['pending']==0
         and allocation['end']<at<stop,'competing pregrant actual first-round loss')
    need(not any(v['node']==node and v['ballot']==ballot for v in captures),
         'competing pregrant unexpected local grant')
    own=[(i,v) for i,v in enumerate(events) if allocation['end']<i<=at and v['node']==node
         and v['event'] not in ('NETWORK_SEND','NETWORK_REQUEST','NETWORK_RECEIVED','WIRE_RESPONSE')]
    need(len(own)==1 and own[0][1]['event']=='CURRENT_BEFORE_CAPTURE',
         'competing pregrant original capture without writes')
    captured=own[0][0]
    need(not any(v['kind']=='PREPARE' and v['request']['sender']['node']==node
                 and v['request']['ballot']==ballot for v in attempts),
         'competing pregrant cannot advertise missing promise')
    incoming=[v for v in attempts if v['kind']=='PREPARE' and v['request']['recipient']['node']==node
              and v['received'] is not None and captured<v['received']<=at
              and prefix.journal.order(v['request']['ballot'])>prefix.journal.order(ballot)]
    need(len(incoming)==1,'competing pregrant original higher PREPARE')
    cause=incoming[0];q=cause['request']
    sources=[v for v in captures if v['node']==q['sender']['node'] and v['ballot']==q['ballot']]
    need(len(sources)==1 and q['ballot']['proposer']==q['sender']['node']
         and sources[0]['capturedEvent']<cause['sent']<cause['received']
         and q['payload']==dict(promise=prefix.sha(sources[0]['promise'])),
         'competing pregrant original higher promise')
    granted=[v for v in captures if v['node']==node and v['ballot']==q['ballot']]
    need(len(granted)==1 and at<starts[granted[0]['basisSha256']]<granted[0]['returnEvent'],
         'competing pregrant loss precedes incoming grant')
    return dict(node=node,ballot=ballot,allocation=allocation['end'],capture=captured,
                higherRequest=cause['received'],lossAt=at,higherBallot=q['ballot'],
                remoteGrant=granted[0]['returnEvent'],localGrantCreated=False)


def validate(replay,allocation,stop):
    # Validate original lifecycle clocks/anchors and map only original events.
    # Grant-copy annotations are interleaved, never treated as runtime events.
    lifecycle.validate(replay.root)
    original=prefix.p.trace(replay.root)
    indices=[i for i,v in enumerate(replay.events) if v['event']!=prefix.g.EVENT]
    need([replay.events[i] for i in indices]==original,'competing pregrant original event mapping')
    rows=prefix.p.n.read(replay.root/lifecycle.FILE)
    losses=[dict(v,afterEvent=indices[v['afterEvent']]) for v in rows
            if v['node']==allocation['node'] and v['event']=='LOSS' and v['afterEvent']>=0
            and allocation['end']<indices[v['afterEvent']]<stop]
    need(len(losses)==1,'competing pregrant exact observed loss')
    begins=[v for v in rows if v['node']==allocation['node'] and v['event']=='ROUND_BEGIN' and v['rounds']==1]
    need(len(begins)==1 and begins[0]['ordinal']<losses[0]['ordinal']
         and (-1 if begins[0]['afterEvent']==-1 else indices[begins[0]['afterEvent']])<allocation['start'],
         'competing pregrant round before allocation')
    return bind(replay.events,replay.attempts,list(replay.by_basis.values()),replay.starts,allocation,losses[0],stop)


NEGATIVES={
    'changed-loss-cause':'competing pregrant actual first-round loss',
    'loss-before-higher-request':'competing pregrant original higher PREPARE',
    'missing-source-image':'competing maintenance final grant/source projection',
    'changed-final-allocator':'competing maintenance final grant/source projection',
    'scratch-residual-payload':'competing exact drained scratch',
    'missing-abandoned-scratch':'competing exact drained scratch',
    'invented-idle-scratch':'competing exact drained scratch',
}


def mutate(root,name):
    root=Path(root);need(name in NEGATIVES,'competing pregrant unknown mutation')
    observations=prefix.p.n.read(root/lifecycle.FILE)
    losses=[v for v in observations if v['event']=='LOSS']
    need(len(losses)==1,'competing pregrant negative original loss inventory');loss=losses[0];node=loss['node']
    if name=='changed-loss-cause':
        loss['detail']='CONTACT_UNAVAILABLE'
        (root/lifecycle.FILE).write_bytes(prefix.f.canonical(observations))
    elif name=='loss-before-higher-request':
        events=prefix.p.n.read(root/'events.json');after=loss['afterEvent']-1
        need(after>=0 and events[after+1]['event']=='NETWORK_REQUEST' and events[after+1]['node']==node,
             'competing pregrant negative received cause boundary')
        for row in observations:
            if row['node']==node and loss['ordinal']<=row['ordinal']<=loss['ordinal']+4:
                row.update(afterEvent=after,nanoTime=events[after]['nanoTime'])
        (root/lifecycle.FILE).write_bytes(prefix.f.canonical(observations))
    elif name=='missing-source-image':next((root/'after-close'/node/'sources').glob('*/*.image')).unlink()
    elif name=='changed-final-allocator':
        path=root/'after-close'/node/'allocator.gsr';value=prefix.f.decode(path.read_bytes(),'records','ALLOCATOR')
        path.write_bytes(prefix.f.encode('records','ALLOCATOR',dict(value,counter=value['counter']+1)))
    elif name=='scratch-residual-payload':(root/'drain-scratch'/node/'outgoing'/'residual.bin').write_bytes(b'unreleased')
    elif name=='missing-abandoned-scratch':shutil.rmtree(root/'drain-scratch'/node/'outgoing')
    else:
        idle=next(v.name for v in (root/'drain-scratch').iterdir() if not (v/'outgoing').exists())
        (root/'drain-scratch'/idle/'outgoing').mkdir()


def qualify(root):
    # Import after module initialization: the integrated reader uses bind().
    from . import competing_export_evidence as exports
    root=Path(root);before=prefix.collection.h.inventory(root)
    reader=exports.Replay(root);original=reader.run()
    need(not reader.replay.transactions and reader.partial is None and
         len(original['precondition']['pregrantLosses'])==1,'competing pregrant qualification scope')
    results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-pregrant-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
            try:exports.validate(changed)
            except ValueError as error:need(str(error)==reason,'unrelated competing pregrant negative: '+name+': '+str(error))
            else:raise ValueError('competing pregrant mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(prefix.collection.h.inventory(root)==before,'competing pregrant original changed')
    return dict(original=original,negativeScope='copied-original-evidence-not-native-fault-executions',negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('raw');args=parser.parse_args()
    print(json.dumps(qualify(args.raw),sort_keys=True))
