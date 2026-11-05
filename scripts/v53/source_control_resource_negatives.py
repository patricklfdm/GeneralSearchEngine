"""Coherent accounting mutations against unchanged original source traffic."""
import argparse
import copy
import json
from pathlib import Path
from . import source_control_resource_evidence as r
from .floor_resource_negatives import recount

NEGATIVES={
    'request-size':'source resources original buffer extent',
    'response-size':'source resources original buffer extent',
    'session-size':'source resources original buffer extent',
    'trace-size':'source resources initial trace extent',
    'request-owner':'source resources missing original reservation',
    'response-owner':'source resources missing original reservation',
    'session-owner':'source resources missing original reservation',
    'trace-owner':'source resources missing original reservation',
    'request-released-before-outcome':'source resources not live at boundary',
    'request-released-after-pull':'source resources logical release order',
    'response-released-before-reply':'source resources not live at boundary',
    'trace-released-before-close':'source resources not live at boundary',
    'renewed-deadline':'source resources renewed deadline',
    'wrong-loss-phase':'source resources declared loss phase',
    'missing-loss':'source resources declared losses',
    'unbound-buffer':'source resources unbound reservation',
    'extra-service-reply':'source resources paired service calls',
    'cache-size':'source resources completed cache handoff',
    'cache-after-release':'source resources completed cache handoff',
    'session-after-handoff':'source resources completed cache handoff',
}
COMPLETE={'cache-size','cache-after-release','session-after-handoff'}


def mutate(data,name):
    events,wires,traces,points,ids,root,record,mode=data
    lives,_=r.lifetimes(traces)
    role=next((role for role in r.ROLES if name.startswith(role.removeprefix('source-').removeprefix('transfer-')+'-')),None)
    if name=='request-released-after-pull':role='source-request'
    key,life=next((k,v) for k,v in lives.items() if k[1]==role) if role else (None,None)
    if name.endswith('-size') and name!='cache-size' or name.endswith('-owner'):
        for row in traces[key[0]]['changes']:
            for charge in row['removed']+row['added']:
                if charge['owner']!=life['owner']:continue
                if name.endswith('-size'):charge['bytes']+=1
                else:charge['owner']=charge['owner'].replace(key[2],'f'*64 if key[2]!='f'*64 else 'e'*64)
    elif name=='request-released-before-outcome':
        next(p for p,e in zip(points,events) if e['event']=='SOURCE_FAILURE')['sequence']=life['end']
    elif name=='request-released-after-pull':
        p=next(p for p,e in zip(points,events) if e['event']=='SOURCE_PULL_CLOSED')
        last=max((v for k,v in lives.items() if k[1]=='source-request'),key=lambda v:v['end']);p['sequence']=last['end']-1
    elif name=='response-released-before-reply':
        p=next(p for p,e in zip(points,events) if e['event']=='TRANSFER_BEFORE_REPLY');p['sequence']=life['end']
    elif name=='trace-released-before-close':
        next(p for p,e in zip(points,events) if e['event']=='SOURCE_SERVICE_CLOSE_BEGIN')['sequence']=life['end']
    elif name=='renewed-deadline':
        [v for v in events if v['event']=='SOURCE_CALL'][1]['deadline']+=1
    elif name=='wrong-loss-phase':data[-1]='lost-data' if mode=='lost-offer' else 'lost-offer'
    elif name=='missing-loss':
        # A known event cannot replace the independent withheld-reply declaration.
        next(v for v in events if v['event']=='SOURCE_REPLY_DROP')['event']='SOURCE_CACHE_RETRY'
    elif name=='unbound-buffer':
        charge=dict(unit='CONTROL',owner='source-request-'+'0'*64+'-00000000-0000-0000-0000-000000000099',bytes=1,claimSource='')
        traces['node-2']['changes'].extend([dict(event='RESERVE',removed=[],added=[charge]),dict(event='RELEASE',removed=[charge],added=[])])
    elif name=='extra-service-reply':
        at=next(i for i,e in enumerate(events) if e['event']=='TRANSFER_BEFORE_REPLY')
        events.insert(at,copy.deepcopy(events[at]));points.insert(at,copy.deepcopy(points[at]))
        for i,p in enumerate(points):p['eventIndex']=i
    else:
        trace=next(v for k,v in lives.items() if k[1]=='transfer-trace');growth=trace['growth'][0][0];rows=traces['node-1']['changes']
        if name=='cache-size':
            for position,row in enumerate(rows[growth:],growth):
                for charge in ([] if position==growth else row['removed'])+row['added']:
                    if charge['owner']==trace['owner']:charge['bytes']+=1
        elif name=='cache-after-release':rows[growth],rows[growth+1]=rows[growth+1],rows[growth]
        elif name=='session-after-handoff':
            meta=next(v for k,v in lives.items() if k[1]=='source-session')
            last=max((i for i,e in enumerate(events) if e['event']=='TRANSFER_BEFORE_REPLY' and r.net.wire(e['response'])[0]=='TRANSFER_COMMIT'),default=-1)
            # A complete handoff must already have freed metadata at its first reply.
            first=next(i for i,e in enumerate(events) if e['event']=='TRANSFER_BEFORE_REPLY' and r.net.wire(e['response'])[0]=='TRANSFER_COMMIT')
            r.need(last>=first,'source negative completed reply');points[first]['sequence']=meta['end']-1
    recount(traces,points)


def replay(data):
    r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        if data[-1]=='exhausted-offer' and (name in COMPLETE or name=='wrong-loss-phase'):continue
        changed=list(copy.deepcopy(data));mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'source resources unrelated negative: '+name+': '+str(error))
        else:raise ValueError('source resources accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return results


def qualify(directory):
    root=Path(directory);before=r.a.collection.inventory(root);original=r.validate(root)
    cases=[dict(case=name,negatives=replay(r.case(root/name,name)[1])) for name in r.CASES]
    r.need(r.a.collection.inventory(root)==before,'source resources negatives changed original')
    return dict(status='PASS',original=original,cases=cases,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    print(json.dumps(qualify(a.root),sort_keys=True))
