"""Reject close-interval mutations only after unchanged original evidence passes."""
import argparse
import copy
import json
from pathlib import Path
from . import control_close_evidence as r

NEGATIVES={
    'truncated':'control close complete bounded recorder',
    'failed':'control close complete bounded recorder',
    'missing-return':'control close complete cleanup intervals',
    'missing-session':'control close complete cleanup intervals',
    'early-service-return':'control close release before normal return',
    'late-session-begin':'control close original live invocation',
    'wrong-return-call':'control close matched normal return',
    'duplicate-child':'control close exact ordered row',
    'unknown-child':'control close original live children',
    'missing-trace-child':'control close trace missing service',
    'missing-response-child':'control close complete response inventory',
    'wrong-child-role':'control close child release order',
    'boolean-resource-sequence':'control close exact ordered row',
    'before-allocation':'control close original live invocation',
    'return-with-children':'control close matched normal return',
    'external-return-before-release':'control close external call interval',
}


def mutate(data,name):
    traces,closes,events,boundaries=data;value=closes['node-1'];rows=value['rows']
    def row(kind,event):return next(v for v in rows if r.role(v['owner'])==kind and v['event']==event)
    service=row('transfer-service','BEGIN');session=row('source-session','BEGIN')
    end=row('transfer-service','RETURNED');life=r.allocations(traces['node-1'])
    if name in ('truncated','failed'):value[name]=True
    elif name in ('missing-return','missing-session'):
        remove={v['sequence'] for v in rows if r.role(v['owner'])=='source-session' and
                (name=='missing-session' or v['event']=='RETURNED')}
        remaining=[v for v in rows if v['sequence'] not in remove];positions={v['sequence']:i for i,v in enumerate(remaining)}
        for v in remaining:v['call']=positions[v['call']];v['sequence']=positions[v['sequence']]
        value['rows']=remaining;value['observations']=len(remaining)
    elif name=='early-service-return':end['resourceSequence']=life[end['owner']]['end']-1
    elif name=='late-session-begin':session['resourceSequence']=life[session['owner']]['end']
    elif name=='wrong-return-call':end['call']=session['call']
    elif name=='duplicate-child':service['children']*=2
    elif name=='unknown-child':service['children']=['transfer-trace-'+'f'*64+'-00000000-0000-0000-0000-000000000099']
    elif name=='missing-trace-child':service['children']=[]
    elif name=='missing-response-child':session['children']=[]
    elif name=='wrong-child-role':
        # A completed session is already released when its parent service closes.
        # Use a live trace as a session's response child to preserve that precondition.
        session['children']=[row('transfer-trace','BEGIN')['owner']]
    elif name=='boolean-resource-sequence':session['resourceSequence']=True
    elif name=='before-allocation':rows[0]['resourceSequence']=0
    elif name=='return-with-children':end['children']=list(service['children'])
    elif name=='external-return-before-release':
        i=next(i for i,v in enumerate(events) if v['event']=='SOURCE_SERVICE_CLOSE_RETURNED')
        boundaries[i]['sequence']=life[service['owner']]['end']-1
    else:raise ValueError('unknown close mutation: '+name)


def replay(data):
    r.component(*data);result=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.component(*changed)
        except ValueError as error:r.need(str(error)==reason,'control close unrelated negative: '+name+': '+str(error))
        else:raise ValueError('control close accepted negative: '+name)
        result.append(dict(case=name,status='REJECTED',reason=reason))
    return result


def qualify(root):
    root=Path(root);before=r.a.collection.inventory(root);original=r.validate(root)
    cases=[dict(case=name,negatives=replay(r.case(root/name,name)[1])) for name in r.source.CASES]
    r.need(r.a.collection.inventory(root)==before,'control close negatives changed original')
    return dict(status='PASS',original=original,cases=cases,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');args=p.parse_args()
    print(json.dumps(qualify(args.root),sort_keys=True))
