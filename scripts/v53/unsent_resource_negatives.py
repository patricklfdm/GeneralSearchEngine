"""Original-first mutations for exact reserved-but-unwritten attempt bindings."""
import argparse
import copy
import json
from pathlib import Path
import sys
from . import unsent_resource_evidence as component
from .floor_resource_negatives import recount

r=component.r
NEGATIVES={
    'missing-terminal':'transport resources unobserved frame lifetimes',
    'unknown-reason':'transport resources unsent failure reason',
    'duplicate-id':'transport resources unsent reused invocation',
    'connected-id':'transport resources unsent reused invocation',
    'crossed-retry-ids':'transport resources frame not closed at terminal',
    'wrong-original-size':'transport resources original send buffer',
    'wrong-request-hash':'transport resources unsent original request',
    'wrong-request-kind':'transport resources unsent original request',
    'early-terminal':'transport resources frame not closed at terminal',
    'missing-lease':'transport resources missing original frame lease',
    'invented-response-buffer':'transport resources foreign role on observed connection',
    'invented-connection':'transport resources unsent shape',
}


def mutate(data,name):
    events,wires,traces,boundaries,*_=data;r.need(name in NEGATIVES,'unsent declared negative')
    indices=[i for i,v in enumerate(events) if v['event']==r.UNSENT];r.need(len(indices)>=2,'unsent negative applicability')
    at=indices[0];event=events[at];node=event['node'];identifier=event['invocation'];key='transport-request-send-'+identifier
    if name=='missing-terminal':event['event']='UNOBSERVED'
    elif name=='unknown-reason':event['reason']='PASS'
    elif name=='duplicate-id':events[indices[1]]['invocation']=identifier
    elif name=='connected-id':event['invocation']=next(v['connection']['id'] for v in events if v['event'] in r.connections.SENDS)
    elif name=='crossed-retry-ids':event['invocation'],events[indices[1]]['invocation']=events[indices[1]]['invocation'],identifier
    elif name=='wrong-original-size':
        for row in traces[node]['changes']:
            for charge in row['removed']+row['added']:
                if charge['owner']==key:charge['bytes']+=1
    elif name=='wrong-request-hash':event['request']='0'*64 if event['request']!='0'*64 else '1'*64
    elif name=='wrong-request-kind':event['kind']='CHUNK' if event['kind']!='CHUNK' else 'STATUS_PROBE'
    elif name=='early-terminal':boundaries[at]['sequence']=r.lifetimes(traces)[0][node,'request-send',identifier]['end']-1
    elif name=='missing-lease':
        identifiers={key[2] for key in r.lifetimes(traces)[0]}
        value='00000000-0000-0000-0000-000000000099';r.need(value not in identifiers,'unsent negative ID collision');event['invocation']=value
    elif name=='invented-response-buffer':
        charge=dict(unit='CONTROL',owner='transport-response-read-'+identifier,bytes=r.HEADER,claimSource='')
        traces[node]['changes'].extend([dict(event='RESERVE',removed=[],added=[charge]),dict(event='RELEASE',removed=[charge],added=[])])
    elif name=='invented-connection':event['connection']={}
    recount(traces,boundaries)


def replay(data,progress=None):
    r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'unsent unrelated negative: '+name+': '+str(error))
        else:raise ValueError('unsent accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(case=name,completed=len(results),total=len(NEGATIVES)))
    return results


def qualify(directory,progress=None):
    root=Path(directory);before=r.accounting.collection.inventory(root);original=component.validate(root);cases=[]
    for name in component.CASES:
        _,data=component.case(root/name,name);cases.append(dict(case=name,negatives=replay(data,progress)))
    r.need(r.accounting.collection.inventory(root)==before,'unsent qualification changed original')
    return dict(status='PASS',original=original,cases=cases,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    progress=lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(a.root,progress),sort_keys=True))
