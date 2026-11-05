"""Original-first activation accounting rejection checks; raw files stay fixed."""
import argparse
import base64
import copy
import json
from pathlib import Path

from . import activation_control_resources as r
from . import native_resource_evidence as native
from .floor_resource_negatives import recount

NEGATIVES={
    'request-short':'activation resources original request extent',
    'request-long':'activation resources original request extent',
    'cache-short':'activation resources original cached extent',
    'cache-long':'activation resources original cached extent',
    'control-binding':'activation resources unobserved allocation',
    'waiter-binding':'activation resources unobserved allocation',
    'missing-control':'activation resources one cache and callers',
    'missing-waiter':'activation resources one cache and callers',
    'legacy-control':'activation resources original bindings required',
    'extra-control':'activation resources one cache and callers',
    'extra-waiter':'activation resources unmatched waiter',
    'reused-control':'activation resources reused allocation',
    'missing-growth':'activation resources original reply growth',
    'extra-growth':'activation resources single cache growth',
    'growth-before-durability':'activation resources original durable boundary',
    'release-before-caller':'activation resources cached reply caller custody',
    'missing-grant-boundary':'activation resources original durable boundary',
    'fast-publication-witness-omitted':'activation resources missing mandatory caller',
    'slot-child-binding':'activation resources slot child custody',
    'publication-control-omitted':'activation resources publication caller custody',
}


def relocate(rows,points,node,old,new):
    order=list(range(len(rows)));item=order.pop(old);order.insert(new,item)
    values=list(rows);rows[:]=[values[i] for i in order];positions={old:new for new,old in enumerate(order)}
    for p in points:
        if p['node']==node:p['sequence']=positions[p['sequence']]


def mutate(data,name):
    r.need(name in NEGATIVES,'activation resources declared negative')
    events,wires,traces,points,ids,root,expected,transactions=data
    lives,_=r.scan(traces)
    candidates=[(i,v) for i,e in enumerate(events) if e['event']=='GRANT_BEFORE_RETURN'
                for v in lives.values() if v['role']=='activation-control' and v['node']==e['node'] and
                v['start']<=points[i]['sequence']<v['growth'][0][0]]
    r.need(candidates,'activation resources negative original grant');control=min(candidates,key=lambda v:v[0])[1]
    waiter=next(v for v in lives.values() if v['role']=='activation-waiter' and
                (v['node'],v['binding'])==(control['node'],control['binding']))
    rows=traces[control['node']]['changes'];node=control['node'];grown,total=control['growth'][0]
    target=waiter if name in ('waiter-binding','missing-waiter') else control
    if name in ('request-short','request-long','cache-short','cache-long','control-binding','waiter-binding',
                'missing-control','missing-waiter','legacy-control'):
        for row in traces[target['node']]['changes']:
            for charge in row['removed']+row['added']:
                if charge['owner']!=target['owner']:continue
                if name.startswith('request-') and charge['bytes']==control['initial']:charge['bytes']+=-1 if name.endswith('short') else 1
                elif name.startswith('cache-') and charge['bytes']==total:charge['bytes']+=-1 if name.endswith('short') else 1
                elif name.endswith('-binding'):charge['owner']=charge['owner'].replace(target['binding'],'0'*64)
                elif name.startswith('missing-'):charge['owner']=charge['owner'].replace('activation-','omitted-',1)
                elif name=='legacy-control':charge['owner']=target['role']+'-'+r.OWNER.fullmatch(charge['owner'])[3]
    elif name in ('extra-control','extra-waiter','reused-control'):
        target=waiter if name=='extra-waiter' else control
        first=copy.deepcopy(rows[target['start']]['added'][0]);last=copy.deepcopy(rows[target['end']]['removed'][0])
        if name!='reused-control':
            for charge in (first,last):charge['owner']=charge['owner'][:-36]+'00000000-0000-0000-0000-000000000099'
        rows.append(dict(event='RESERVE',removed=[],added=[first]))
        if name!='extra-waiter':rows.append(dict(event='CONTROL_GROW',removed=[copy.deepcopy(first)],added=[copy.deepcopy(last)]))
        rows.append(dict(event='RELEASE',removed=[last],added=[]))
    elif name=='missing-growth':
        rows[grown]['removed']=[];rows[grown]['added']=[]
        rows[control['end']]['removed'][0]['bytes']=control['initial']
    elif name=='extra-growth':
        charge=copy.deepcopy(rows[grown]['added'][0]);more=dict(charge,bytes=charge['bytes']+1)
        rows[control['end']]['removed'][0]['bytes']+=1
        rows.insert(grown+1,dict(event='CONTROL_GROW',removed=[charge],added=[more]))
        for p in points:
            if p['node']==node and p['sequence']>grown:p['sequence']+=1
    elif name=='growth-before-durability':relocate(rows,points,node,grown,control['start']+1)
    elif name=='release-before-caller':relocate(rows,points,node,control['end'],waiter['end'])
    elif name=='missing-grant-boundary':
        event=next(e for e in events if e['node']==node and e['event']=='GRANT_BEFORE_RETURN');event['event']='OMITTED_GRANT'
    elif name=='fast-publication-witness-omitted':transactions.clear()
    elif name=='slot-child-binding':
        children,_=r.slots.scan(traces)
        child=next(v for v in children.values() if v['role']=='slot-waiter' and v['node']==node)
        for row in rows:
            for charge in row['removed']+row['added']:
                if charge['owner']==child['owner']:charge['owner']=charge['owner'].replace(child['binding'],control['binding'])
    elif name=='publication-control-omitted':
        selected=None
        for wire in wires:
            kind,value=r.source.network.t.wire(wire['request'])
            if kind=='PUBLISH':
                digest=r.source.network.t.sha(base64.b64decode(wire['request'],validate=True))
                if any(v['role']=='activation-control' and (v['node'],v['binding'])==(value['recipient']['node'],digest) for v in lives.values()):
                    selected=value['recipient']['node'],digest;break
        r.need(selected is not None,'activation resources negative original publication')
        owners={v['owner'] for v in lives.values() if (v['node'],v['binding'])==selected}
        for row in traces[selected[0]]['changes']:
            for charge in row['removed']+row['added']:
                if charge['owner'] in owners:charge['owner']=charge['owner'].replace('activation-','omitted-',1)
    recount(traces,points)


def replay(data):
    original=r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'activation resources unrelated negative: '+name+': '+str(error))
        else:raise ValueError('activation resources accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


def qualify(root):
    root=Path(root);before=native.collection.inventory(root)
    preceding=native.validate(root,source_control=True,control_closes=True,export_ownership=True,direct_exports=True,activation_control=True)
    index,traces,points,events=native.load(root)
    _,rounds,selection,ids=native.publication.native.physical(root,confirmed_retention=True)
    wires=native.collection.read_json(root,'wire.json',native.collection.WIRE_BYTES)
    result=replay((events,wires,traces,points,ids,index['root'],r.slots.publications(rounds,selection,ids),native.publication.collect(root,events)))
    r.need(native.collection.inventory(root)==before,'activation resources original changed during negatives')
    return dict(result,precondition=preceding,originalInventorySha256=native.collection.digest(
                json.dumps(before,sort_keys=True,separators=(',',':')).encode()),status='PASS',
                wholeRuntimeResourcesQualified=False,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');args=p.parse_args()
    print(json.dumps(qualify(args.root),sort_keys=True))
