"""Coherent accounting mutations after unchanged constructor originals pass."""
import argparse
import copy
import json
from pathlib import Path
from . import construction_rollback_evidence as r
from .pending_drain_negatives import recount as account

NEGATIVES={
    'failed-original':'construction complete conditional history',
    'missing-case':'construction exact failed cases',
    'wrong-error':'construction exact failure outcome',
    'empty-message':'construction exact failure outcome',
    'stale-point':'resource transitions derived usage',
    'boolean-point':'construction ordered original boundaries',
    'early-failure-return':'construction rollback before failure return',
    'missing-temporary':'construction complete temporary acquisitions',
    'wrong-role':'construction exact temporary reservation',
    'wrong-bytes':'construction exact temporary reservation',
    'original-gap':'construction continuous original custody',
    'insufficient-pressure':'construction original capacity pressure',
    'changed-files':'construction unchanged original files',
    'incomplete-observation':'resource transitions incomplete observation',
}


def boundaries(history):return [c[k] for c in history['cases'] for k in ('begin','failed')]


def recount(trace,history):account(trace,dict(rows=boundaries(history)))


def state_at(rows,seq):
    state={}
    for row in rows[:seq+1]:
        for v in row['removed']:state.pop(r.t.key(v))
        for v in row['added']:state[r.t.key(v)]=v
    return state


def remove_lifetime(trace,history,key):
    rows=trace['changes'];deleted=[v['sequence'] for v in rows if any(r.t.key(c)==key for c in v['added']+v['removed'])]
    assert len(deleted)==2
    trace['changes']=[v for v in rows if v['sequence'] not in deleted]
    for p in boundaries(history):p['sequence']-=sum(v<=p['sequence'] for v in deleted)
    recount(trace,history)


def mutate(data,name):
    trace,history=data;cases=history['cases'];rows=trace['changes'];first=cases[0]
    temporary=next(c for c in cases if c['case'].endswith(('-bind','-expiry')))
    at=temporary['begin']['sequence'];charge=rows[at+1]['added'][0]
    if name=='failed-original':history['status']='FAIL'
    elif name=='missing-case':cases.pop()
    elif name=='wrong-error':first['error']='java.lang.RuntimeException'
    elif name=='empty-message':first['message']=''
    elif name=='stale-point':first['failed']['usage']['queued']+=1
    elif name=='boolean-point':first['begin']['sequence']=True
    elif name=='early-failure-return':temporary['failed']['sequence']=at+1;recount(*data)
    elif name=='missing-temporary':remove_lifetime(*data,r.t.key(charge))
    elif name in ('wrong-role','wrong-bytes'):
        key=r.t.key(charge)
        for row in rows:
            for v in row['added']+row['removed']:
                if r.t.key(v)==key:
                    if name=='wrong-role':v['owner']='foreign-'+v['owner']
                    else:v['bytes']-=1
        recount(*data)
    elif name in ('original-gap','insufficient-pressure'):
        capacity=next(c for c in cases if c['case'].endswith('-capacity'));at=capacity['begin']['sequence']
        charge=next(v for v in state_at(rows,at).values() if v['unit']=='CONTROL')
        if name=='insufficient-pressure':remove_lifetime(*data,r.t.key(charge))
        else:
            rows[at+1:at+1]=[dict(event='RELEASE',removed=[copy.deepcopy(charge)],added=[]),dict(event='RESERVE',removed=[],added=[copy.deepcopy(charge)])]
            for p in boundaries(history):
                if p['sequence']>at or p is capacity['failed']:p['sequence']+=2
            recount(*data)
    elif name=='changed-files':
        old=first['afterFiles'][0]['sha256'];first['afterFiles'][0]['sha256']=('0' if old[0]!='0' else '1')+old[1:]
    elif name=='incomplete-observation':trace['truncated']=True
    else:raise ValueError('unknown construction mutation: '+name)


def replay(data):
    r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'construction unrelated negative: '+name+': '+str(error))
        else:raise ValueError('construction negative accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return results


def qualify(root):
    root=Path(root);before=r.t.collection.inventory(root);data=r.collection.load(root)
    result=dict(original=r.replay(*data),negatives=replay(data))
    r.need(before==r.t.collection.inventory(root),'construction original changed')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    print(json.dumps(qualify(a.root),sort_keys=True))
