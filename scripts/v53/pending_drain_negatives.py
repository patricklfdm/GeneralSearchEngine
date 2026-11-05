"""Original-first mutations of failed-close resource continuity observations."""
import argparse
import copy
import json
from pathlib import Path
from . import pending_drain_evidence as r

NEGATIVES={
    'failed-original':'pending drain complete conditional history',
    'missing-failure':'pending drain exact call sequence',
    'wrong-error':'pending drain exact failed close outcome',
    'stale-usage':'resource transitions derived usage',
    'boolean-sequence':'pending drain exact call sequence',
    'released-before-failure':'pending drain storage survives failed close',
    'release-reacquire':'pending drain storage survives failed close',
    'baseline-release-reacquire':'pending drain continuous baseline custody',
    'early-return':'pending drain original baseline restored',
    'changed-files':'pending drain unchanged retained files',
    'missing-files':'pending drain file observations',
    'incomplete-recorder':'resource transitions incomplete observation',
}


def recount(trace,history):
    state={};limits=tuple(trace[k] for k in ('metadataLimit','stagingLimit','queueLimit'))
    for seq,row in enumerate(trace['changes']):
        row['sequence']=seq
        for v in row['removed']:state.pop(r.t.key(v))
        for v in row['added']:state[r.t.key(v)]=v
        row['usage']=r.t.usage(state,limits)
    trace['transitions']=len(trace['changes']);trace['current']=copy.deepcopy(trace['changes'][-1]['usage'])
    for p in history['rows']:p['usage']=copy.deepcopy(trace['changes'][p['sequence']]['usage'])


def mutate(data,name):
    trace,history=data;points={v['event']:v for v in history['rows']};rows=trace['changes']
    if name=='failed-original':history['status']='FAIL'
    elif name=='missing-failure':history['rows'].remove(points['OWNER_CLOSE_FAILED'])
    elif name=='wrong-error':points['OWNER_CLOSE_FAILED']['error']=''
    elif name=='stale-usage':points['OWNER_CLOSE_FAILED']['usage']['metadata']+=1
    elif name=='boolean-sequence':points['OWNER_CLOSE_BEGIN']['sequence']=True
    elif name=='early-return':
        points['OWNER_CLOSE_RETURNED']['sequence']=points['RETRY_CLOSE_BEGIN']['sequence'];recount(*data)
    elif name=='changed-files':history['inventories']['afterSuccess'][0]['sha256']='f'*64
    elif name=='missing-files':del history['inventories']['afterFailure']
    elif name=='incomplete-recorder':trace['failed']=True
    elif name in ('released-before-failure','release-reacquire','baseline-release-reacquire'):
        at=points['OWNER_CLOSE_BEGIN']['sequence'];state={};baseline={}
        for row in rows[:at+1]:
            for v in row['removed']:state.pop(r.t.key(v))
            for v in row['added']:state[r.t.key(v)]=v
            if row['sequence']==points['BASELINE']['sequence']:baseline=r.storage(state.values())
        candidates=baseline if name.startswith('baseline-') else {k:v for k,v in r.storage(state.values()).items() if k not in baseline}
        charge=next(v for v in candidates.values() if not v['claimSource'])
        inserts=[dict(event='RELEASE',removed=[copy.deepcopy(charge)],added=[])]
        if name=='released-before-failure':
            release=next(row for row in rows[at+1:] if row['event']=='RELEASE' and row['removed']==[charge])
            rows.remove(release)
            for p in history['rows']:
                if p['sequence']>=release['sequence']:p['sequence']-=1
        else:inserts.append(dict(event='RESERVE',removed=[],added=[copy.deepcopy(charge)]))
        rows[at+1:at+1]=inserts
        for p in history['rows']:
            if r.EVENTS.index(p['event'])>=r.EVENTS.index('OWNER_CLOSE_FAILED'):p['sequence']+=len(inserts)
        recount(*data)
    else:raise ValueError('unknown pending drain mutation: '+name)


def replay(data):
    r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'pending drain unrelated negative: '+name+': '+str(error))
        else:raise ValueError('pending drain negative accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return results


def qualify(root):
    root=Path(root);before=r.t.collection.inventory(root);data=r.load(root)
    result=dict(original=r.replay(*data),negatives=replay(data))
    r.need(before==r.t.collection.inventory(root),'pending drain changed original')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    print(json.dumps(qualify(a.root),sort_keys=True))
