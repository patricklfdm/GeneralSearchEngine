"""Mutate close annotations while original native storage/traffic stay fixed."""
import argparse
import copy
import json
from pathlib import Path
from . import native_resource_evidence as a
from . import native_control_closes as r

NEGATIVES={
    'truncated':'control close complete bounded recorder',
    'failed':'control close complete bounded recorder',
    'missing-budget':'control close complete original budgets',
    'missing-return':'control close complete cleanup intervals',
    'missing-session':'control close complete cleanup intervals',
    'late-session-begin':'control close original live invocation',
    'wrong-return-call':'control close matched normal return',
    'missing-trace-child':'control close trace missing service',
    'missing-response-child':'native close complete original response inventory',
    'return-with-children':'control close matched normal return',
    'before-allocation':'control close original live invocation',
    'boolean-resource-sequence':'control close exact ordered row',
    'invented-row-count':'control close complete bounded recorder',
}


def mutate(traces,closes,name):
    node=next(n for n,v in closes.items() if any(r.close.role(row['owner'])=='source-session' for row in v['rows']))
    value=closes[node];rows=value['rows'];life=r.close.allocations(traces[node])
    session=next(v for v in rows if v['event']=='BEGIN' and r.close.role(v['owner'])=='source-session' and v['children'])
    service=next(v for v in rows if v['event']=='BEGIN' and r.close.role(v['owner'])=='transfer-service' and v['children'])
    returned=next(v for v in rows if v['event']=='RETURNED' and v['owner']==session['owner'])
    if name in ('truncated','failed'):value[name]=True
    elif name=='missing-budget':del closes[node]
    elif name in ('missing-return','missing-session'):
        removed={v['sequence'] for v in rows if v['owner']==session['owner'] and (name=='missing-session' or v['event']=='RETURNED')}
        remaining=[v for v in rows if v['sequence'] not in removed];positions={v['sequence']:i for i,v in enumerate(remaining)}
        for v in remaining:v['call']=positions[v['call']];v['sequence']=positions[v['sequence']]
        value['rows']=remaining;value['observations']=len(remaining)
    elif name=='late-session-begin':session['resourceSequence']=life[session['owner']]['end']
    elif name=='wrong-return-call':returned['call']=returned['sequence']
    elif name=='missing-trace-child':service['children'].pop()
    elif name=='missing-response-child':session['children']=[]
    elif name=='return-with-children':returned['children']=list(session['children'])
    elif name=='before-allocation':rows[0]['resourceSequence']=0
    elif name=='boolean-resource-sequence':session['resourceSequence']=True
    elif name=='invented-row-count':value['observations']+=1
    else:raise ValueError('unknown native close mutation: '+name)


def replay(traces,closes,associations):
    original=r.bind(traces,closes,associations);result=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(closes);mutate(traces,changed,name)
        try:r.bind(traces,changed,associations)
        except ValueError as error:r.need(str(error)==reason,'native close unrelated negative: '+name+': '+str(error))
        else:raise ValueError('native close accepted negative: '+name)
        result.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=result)


def qualify(root):
    root=Path(root);before=a.collection.inventory(root);original=a.validate(root,control_closes=True)
    index,traces,boundaries,events=a.load(root);closes=r.close.load(root,index);associations={}
    ids={v['identity']['node']:v['identity'] for v in index['owners']}
    wires=a.collection.read_json(root,'wire.json',a.collection.WIRE_BYTES)
    r.source.replay(events,wires,traces,boundaries,ids,index['root'],bindings=associations)
    result=replay(traces,closes,associations)
    r.need(a.collection.inventory(root)==before,'native close negatives changed original')
    return dict(status='PASS',precondition=original,**result,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');args=p.parse_args()
    print(json.dumps(qualify(args.root),sort_keys=True))
