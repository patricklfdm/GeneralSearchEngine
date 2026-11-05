"""Mutate direct export observations only after unchanged native replay passes."""
import argparse
import copy
import json
from pathlib import Path
from . import special_export_resource_evidence as r
from .export_resource_negatives import points,recount,insert

NEGATIVES={
    'failed-original':'special exports original scope',
    'missing-mode':'special exports complete case pair',
    'mode-order':'special exports complete case pair',
    'missing-call':'special exports complete case pair',
    'wrong-call':'special exports exact call order',
    'boolean-point':'special exports original boundaries',
    'stale-usage':'resource transitions derived usage',
    'wrong-binding':'special exports original content binding',
    'wrong-size':'special exports original extent',
    'legacy-name':'special exports observed binding',
    'missing-allocation':'special exports complete acquisitions',
    'extra-allocation':'special exports unique immutable allocation',
    'reused-allocation':'special exports unique immutable allocation',
    'baseline-gap':'special exports continuous original custody',
    'early-release-return':'special exports release inside call',
    'read-after-release':'special exports overlapping reads',
    'wrong-expiry-policy':'special exports expiry release policy',
    'incomplete-observation':'resource transitions incomplete observation',
}


def mutate(data,name):
    trace,history,expected=data;rows=trace['changes'];first=history['cases'][0]
    marks={v['event']:v['point'] for v in first['events']}
    # A nested prefix borrow is indispensable for ROOT; a receipt is separate
    # from the payload for voting. Both must remain independently charged.
    leases=[v for row in rows[marks['BEGIN']['sequence']+1:marks['OPENED']['sequence']+1] for v in row['added']]
    charge=copy.deepcopy(leases[-1]);key=r.t.key(charge)
    if name=='failed-original':history['status']='FAIL'
    elif name=='missing-mode':history['cases'].pop()
    elif name=='mode-order':history['cases'].reverse()
    elif name=='missing-call':first['events'].pop()
    elif name=='wrong-call':first['events'][1]['event']='UNOBSERVED'
    elif name=='boolean-point':marks['BEGIN']['sequence']=True
    elif name=='stale-usage':marks['BEGIN']['usage']['queued']+=1
    elif name in ('wrong-binding','wrong-size','legacy-name'):
        for row in rows:
            for v in row['added']+row['removed']:
                if r.t.key(v)!=key:continue
                role,reference,nonce=r.NAME.fullmatch(v['owner']).groups()
                if name=='wrong-size':v['bytes']+=1
                elif name=='legacy-name':v['owner']=role+'-'+nonce
                else:v['owner']=role+'-'+('0' if reference[0]!='0' else '1')+reference[1:]+'-'+nonce
        recount(trace,history)
    elif name=='missing-allocation':
        removed=[row['sequence'] for row in rows if any(r.t.key(v)==key for v in row['added']+row['removed'])]
        r.need(len(removed)==2,'special export negative original lifetime')
        trace['changes']=[row for row in rows if row['sequence'] not in removed]
        for p in points(history):p['sequence']-=sum(s<=p['sequence'] for s in removed)
        recount(trace,history)
    elif name=='extra-allocation':
        charge['owner']=charge['owner'][:-36]+'ffffffff-ffff-ffff-ffff-ffffffffffff'
        insert(trace,history,marks['OPENED']['sequence'],[dict(event='RESERVE',removed=[],added=[charge]),
                dict(event='RELEASE',removed=[copy.deepcopy(charge)],added=[])])
    elif name=='reused-allocation':
        at=history['cases'][-1]['events'][-1]['point']['sequence']
        insert(trace,history,at,[dict(event='RESERVE',removed=[],added=[charge]),dict(event='RELEASE',removed=[copy.deepcopy(charge)],added=[])])
    elif name=='baseline-gap':
        state={}
        for row in rows[:marks['BEGIN']['sequence']+1]:
            for v in row['removed']:state.pop(r.t.key(v))
            for v in row['added']:state[r.t.key(v)]=v
        original=copy.deepcopy(next(v for v in state.values() if not v['claimSource']))
        insert(trace,history,marks['OPENED']['sequence'],[dict(event='RELEASE',removed=[original],added=[]),
                dict(event='RESERVE',removed=[],added=[copy.deepcopy(original)])])
    elif name=='early-release-return':
        marks['INVALIDATED']['sequence']=marks['RELEASED']['sequence']=marks['RELEASE_BEGIN']['sequence'];recount(trace,history)
    elif name=='read-after-release':
        marks['READS_FINISHED']['sequence']=marks['RELEASE_BEGIN']['sequence']=marks['RELEASED']['sequence'];recount(trace,history)
    elif name=='wrong-expiry-policy':
        second={v['event']:v['point'] for v in history['cases'][1]['events']}
        second['INVALIDATED']['sequence']=second['RELEASED' if history['family']=='learner-root' else 'RELEASE_BEGIN']['sequence']
        recount(trace,history)
    elif name=='incomplete-observation':trace['truncated']=True
    else:raise ValueError('unknown special export mutation: '+name)


def replay(data):
    r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        r.need(changed[2]==data[2],'special export negative changed expectations')
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'special export unrelated negative '+name+': '+str(error))
        else:raise ValueError('special export negative accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return results


def qualify(root):
    root=Path(root);before=r.t.collection.inventory(root);data,physical=r.load(root)
    result=dict(original=dict(r.replay(*data),physical=physical),negatives=replay(data),
                negativeScope='direct-export-observations-after-native-physical-network-replay')
    r.need(before==r.t.collection.inventory(root),'special export negatives changed original')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args();print(json.dumps(qualify(a.root),sort_keys=True))
