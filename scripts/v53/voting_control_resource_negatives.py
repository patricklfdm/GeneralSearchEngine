"""Original-first voting resource mutations; leave the retained original intact."""
import argparse
import copy
import json
from pathlib import Path

from . import voting_control_resources as r
from . import native_resource_evidence as native
from .floor_resource_negatives import recount

NEGATIVES = {
    'control-short': 'voting resources original control extent',
    'control-long': 'voting resources original control extent',
    'control-binding': 'voting resources unobserved allocation',
    'waiter-binding': 'voting resources unobserved allocation',
    'control-omitted': 'voting resources forced work lacks unique control',
    'waiter-omitted': 'voting resources one writer and admitted waiters',
    'legacy-binding': 'voting resources original bindings required',
    'control-after-read': 'voting resources control request interval',
    'force-after-release': 'voting resources forced work lacks unique control',
    'return-after-release': 'voting resources control released before durable return',
    'waiter-released-first': 'voting resources writer not held by original waiter',
    'extra-waiter': 'voting resources waiter request interval',
    'extra-writer': 'voting resources one writer and admitted waiters',
    'reused-allocation': 'voting resources reused allocation',
    'missing-force': 'voting resources exact original force',
    'missing-return': 'voting resources original durable return',
}


def mutate(data, name):
    r.need(name in NEGATIVES, 'voting resources declared negative')
    events,wires,traces,points,ids,root = data
    lives,_=r.scan(traces)
    control=next(v for v in lives.values() if v['role']=='voting-control')
    waiter=next(v for v in lives.values() if v['role']=='voting-waiter' and
                v['node']==control['node'] and v['binding']==control['binding'] and
                v['start']<control['start']<control['end']<v['end'])
    node=control['node'];rows=traces[node]['changes'];target=waiter if name.startswith('waiter-') else control
    if name in ('control-short','control-long','control-binding','waiter-binding','control-omitted','waiter-omitted','legacy-binding'):
        for row in rows:
            for charge in row['removed']+row['added']:
                if charge['owner']!=target['owner']:continue
                if name.endswith(('short','long')):charge['bytes']+=-1 if name.endswith('short') else 1
                elif name.endswith('binding') and name!='legacy-binding':charge['owner']=charge['owner'].replace(target['binding'],'0'*64)
                elif name.endswith('omitted'):charge['owner']='unqualified-'+charge['owner']
                else:charge['owner']=target['role']+'-'+r.OWNER.fullmatch(target['owner'])[3]
    elif name in ('control-after-read','force-after-release','return-after-release','missing-force','missing-return'):
        net=r.source.network.replay(events,wires,ids,root)
        requests=[v for v in net['rows'] if v['request']['recipient']['node']==node and v['requestHash']==control['binding']]
        kind=requests[0]['kind']
        force=next(i for i,e in enumerate(events) if e['node']==node and e['event']==r.FORCE[kind] and
                   control['start']<=points[i]['sequence']<control['end'])
        returned=next(i for i in range(force+1,len(events)) if events[i]['node']==node and events[i]['event']==r.RETURN[kind])
        if name=='control-after-read':
            for request in requests:
                if points[request['received']]['sequence']<control['start']:
                    points[request['received']]['sequence']=control['start']
        elif name=='force-after-release':
            # Move the actual release delta; retain monotonically ordered event
            # checkpoints and recompute every usage instead of forging totals.
            at=points[force]['sequence']
            r.need(control['start']<at<control['end'],'voting resources negative release placement')
            rows.insert(at,rows.pop(control['end']))
        elif name=='return-after-release':
            # Force and return commonly share one sequence because no resource
            # changed between them. Place the release after that sequence, then
            # advance return/later checkpoints, preserving force-before-release.
            at=points[returned]['sequence']+1;end=control['end']
            r.need(control['start']<at<=end,'voting resources negative return placement')
            rows.insert(at,rows.pop(end))
            for i,point in enumerate(points):
                if point['node']!=node:continue
                if at<=point['sequence']<end:point['sequence']+=1
                if i>=returned:point['sequence']=max(at,point['sequence'])
        elif name=='missing-force':events[force]['event']='OMITTED_FORCE'
        else:events[returned]['event']='OMITTED_RETURN'
    elif name=='waiter-released-first':rows[control['end']],rows[waiter['end']]=rows[waiter['end']],rows[control['end']]
    else:
        original=waiter if name=='extra-waiter' else control
        charge=copy.deepcopy(rows[original['start']]['added'][0])
        if name!='reused-allocation':charge['owner']=charge['owner'][:-36]+'00000000-0000-0000-0000-000000000099'
        rows.extend([dict(event='RESERVE',removed=[],added=[charge]),dict(event='RELEASE',removed=[charge],added=[])])
    recount(traces,points)


def replay(data,progress=None):
    original=r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'voting resources unrelated negative: '+name+': '+str(error))
        else:raise ValueError('voting resources accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(stage='voting-control-negatives',case=name,completed=len(results),total=len(NEGATIVES)))
    return dict(original=original,negatives=results)


def qualify(root):
    root=Path(root);before=native.collection.inventory(root)
    preceding=native.validate(root,source_control=True,control_closes=True,export_ownership=True,direct_exports=True,voting_control=True)
    index,traces,points,events=native.load(root)
    ids={v['identity']['node']:v['identity'] for v in index['owners']}
    wires=native.collection.read_json(root,'wire.json',native.collection.WIRE_BYTES)
    result=replay((events,wires,traces,points,ids,index['root']))
    r.need(native.collection.inventory(root)==before,'voting resources original changed during negatives')
    return dict(result,precondition=preceding,originalInventorySha256=native.collection.digest(
                json.dumps(before,sort_keys=True,separators=(',',':')).encode()),
                status='PASS',wholeRuntimeResourcesQualified=False,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');args=p.parse_args()
    print(json.dumps(qualify(args.root),sort_keys=True))
