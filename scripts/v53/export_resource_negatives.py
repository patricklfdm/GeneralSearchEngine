"""Exact accounting rejections after the unchanged native physical precondition."""
import argparse
import copy
import json
from pathlib import Path
from . import export_resource_evidence as r
from .pending_drain_negatives import recount as account

NEGATIVES={
    'failed-original':'export resources original scope',
    'missing-mode':'export resources complete case pair',
    'mode-order':'export resources complete case pair',
    'missing-call':'export resources complete case pair',
    'boolean-point':'export resources original boundaries',
    'stale-usage':'resource transitions derived usage',
    'wrong-binding':'export resources original content binding',
    'wrong-size':'export resources original content extent',
    'legacy-name':'export resources observed owner binding',
    'missing-allocation':'export resources complete original acquisitions',
    'extra-allocation':'export resources complete allocation coverage',
    'reused-allocation':'export resources unique immutable allocation',
    'baseline-gap':'export resources continuous original custody',
    'early-release-return':'export resources release inside original call',
    'read-after-release':'export resources overlapping original reads',
    'incomplete-observation':'resource transitions incomplete observation',
}


def points(history):return [p['point'] for case in history['cases'] for p in case['events']]
def recount(trace,history):account(trace,dict(rows=points(history)))


def insert(trace,history,at,rows):
    trace['changes'][at+1:at+1]=rows
    for p in points(history):
        if p['sequence']>at:p['sequence']+=len(rows)
    recount(trace,history)


def mutate(data,name):
    trace,history,expected=data;rows=trace['changes'];first=history['cases'][0]
    marks={p['event']:p['point'] for p in first['events']}
    charge=next(v for row in rows for v in row['added'] if v['owner'].startswith('record-export-'))
    key=r.t.key(charge)
    if name=='failed-original':history['status']='FAIL'
    elif name=='missing-mode':history['cases'].pop()
    elif name=='mode-order':history['cases'].reverse()
    elif name=='missing-call':first['events'].pop()
    elif name=='boolean-point':marks['BEGIN']['sequence']=True
    elif name=='stale-usage':marks['BEGIN']['usage']['queued']+=1
    elif name in ('wrong-binding','wrong-size','legacy-name'):
        for row in rows:
            for v in row['added']+row['removed']:
                if r.t.key(v)!=key:continue
                if name=='wrong-size':v['bytes']+=1
                elif name=='legacy-name':v['owner']='record-export-'+v['owner'][-36:]
                else:
                    match=r.NAME.fullmatch(v['owner']);ref=match[2];wrong=('0' if ref[0]!='0' else '1')+ref[1:]
                    v['owner']=match[1]+'-'+wrong+'-'+match[3]
        recount(trace,history)
    elif name=='missing-allocation':
        removed=[row['sequence'] for row in rows if any(r.t.key(v)==key for v in row['added']+row['removed'])]
        r.need(len(removed)==2,'export negative original lifetime')
        trace['changes']=[row for row in rows if row['sequence'] not in removed]
        for p in points(history):p['sequence']-=sum(s<=p['sequence'] for s in removed)
        recount(trace,history)
    elif name in ('extra-allocation','reused-allocation'):
        value=copy.deepcopy(charge)
        if name=='extra-allocation':value['owner']=value['owner'][:-36]+'ffffffff-ffff-ffff-ffff-ffffffffffff'
        at=history['cases'][-1]['events'][-1]['point']['sequence']
        insert(trace,history,at,[dict(event='RESERVE',removed=[],added=[value]),dict(event='RELEASE',removed=[copy.deepcopy(value)],added=[])])
    elif name=='baseline-gap':
        state={}
        for row in rows[:marks['BEGIN']['sequence']+1]:
            for v in row['removed']:state.pop(r.t.key(v))
            for v in row['added']:state[r.t.key(v)]=v
        original=copy.deepcopy(next(iter(state.values())))
        insert(trace,history,marks['SOURCE_OPENED']['sequence'],[
            dict(event='RELEASE',removed=[original],added=[]),dict(event='RESERVE',removed=[],added=[copy.deepcopy(original)])])
    elif name=='early-release-return':marks['RECORD_RELEASED']['sequence']=marks['RECORD_RELEASE_BEGIN']['sequence'];recount(trace,history)
    elif name=='read-after-release':
        marks['READS_FINISHED']['sequence']=marks['RECORD_RELEASE_BEGIN']['sequence']=marks['RECORD_RELEASED']['sequence'];recount(trace,history)
    elif name=='incomplete-observation':trace['truncated']=True
    else:raise ValueError('unknown export resource mutation: '+name)


def replay(data):
    r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        r.need(changed[2]==data[2],'export negative changed physical expectations')
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'export unrelated resource negative: '+name+': '+str(error))
        else:raise ValueError('export resource negative accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return results


def qualify(root):
    root=Path(root);before=r.t.collection.inventory(root);original=r.validate(root);data,_=r.load(root)
    results=replay(data);r.need(r.t.collection.inventory(root)==before,'export negative original changed')
    return dict(original=original,negativeScope='resource-observations-after-unchanged-physical-replay',negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args();print(json.dumps(qualify(a.root),sort_keys=True))
