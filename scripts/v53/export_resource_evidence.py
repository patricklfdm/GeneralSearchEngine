"""Bind three original native export reservations to immutable content bytes.

Public-bootstrap physical replay precedes accounting. This component is not a
network session, arbitrary export family, or whole-runtime peak qualification.
"""
import argparse
import json
from pathlib import Path
import re
from uuid import UUID
from . import source_export_evidence as physical
from . import resource_transitions as t

need=t.need
ROLES=('source-export','record-export','prefix-export')
NAME=re.compile(r'(source-export|record-export|prefix-export)-([0-9a-f]{64})-([0-9a-f-]{36})\Z')
EVENTS=('BEGIN','SOURCE_OPENED','RECORD_OPENED','PREFIX_OPENED','READS_FINISHED','RECORD_RELEASE_BEGIN','RECORD_RELEASED',
        'SOURCE_RELEASE_BEGIN','SOURCE_RELEASED','PREFIX_RELEASE_BEGIN','PREFIX_RELEASED','REUSE_REFUSED','FINISHED')


def originals(root,size):
    original=physical.case(root,size,additional=('resources.json','history.json'))
    files=physical.c.inventory(root/'captured'/'node-1');prefix,_,packet=physical.c.current(files)
    records=physical.c.journal(files['grants.gsr'],packet['capsule']['root'],'node-1');promise,basis=records[-2:]
    return original,{'source-export':dict(reference=physical.e.digest(basis[1]),bytes=len(promise[1])+len(basis[1])),
                     'record-export':dict(reference=physical.e.digest(promise[1]),bytes=len(promise[1])),
                     'prefix-export':dict(reference=physical.e.digest(files[prefix+'generation.gsr']),bytes=4096)}


def replay(trace,history,expected):
    account=t.replay(trace)
    need(type(expected) is dict and set(expected)==set(ROLES) and all(type(v) is dict and set(v)=={'reference','bytes'} and
         type(v['reference']) is str and re.fullmatch('[0-9a-f]{64}',v['reference']) and type(v['bytes']) is int and v['bytes']>0
         for v in expected.values()),'export resources original content expectations')
    need(type(history) is dict and set(history)=={'schema','size','status','cases','completeMembershipHistory'} and
         history['schema']=='gse-v53-export-resources-v1' and type(history['size']) is int and history['size'] in (3,4,5) and
         history['status']=='PASS' and history['completeMembershipHistory'] is False,'export resources original scope')
    cases=history['cases'];rows=trace['changes'];wanted=set();previous=-1
    need(type(cases) is list and len(cases)==2,'export resources complete case pair')
    for case,mode in zip(cases,('close','expiry')):
        need(type(case) is dict and set(case)=={'mode','events'} and case['mode']==mode and
             type(case['events']) is list and len(case['events'])==len(EVENTS),'export resources complete case pair')
        for point,event in zip(case['events'],EVENTS):
            need(type(point) is dict and set(point)=={'event','point'} and point['event']==event,'export resources exact call order')
            p=point['point'];need(type(p) is dict and set(p)=={'sequence','usage'} and type(p['sequence']) is int and
                0<=p['sequence']<len(rows) and previous<=p['sequence'],'export resources original boundaries')
            previous=p['sequence'];wanted.add(previous);t.same_usage(p['usage'],rows[previous]['usage'])
    leases={};state={};states={}
    for row in rows:
        for side in ('added','removed'):
            for v in row[side]:
                if not any(v['owner'].startswith(role+'-') for role in ROLES):continue
                match=NAME.fullmatch(v['owner'])
                need(v['unit']=='CONTROL' and not v['claimSource'] and match is not None,'export resources observed owner binding')
                role,reference,nonce=match.groups()
                try:identifier=UUID(nonce)
                except ValueError:raise ValueError('export resources observed owner binding') from None
                need(identifier.int and str(identifier)==nonce,'export resources observed owner binding')
                need(reference==expected[role]['reference'],'export resources original content binding')
                need(v['bytes']==expected[role]['bytes'],'export resources original content extent')
                name=v['owner']
                if side=='added':
                    need(row['event']=='RESERVE' and name not in leases,'export resources unique immutable allocation')
                    leases[name]=dict(role=role,start=row['sequence'],end=None)
                else:
                    need(row['event']=='RELEASE' and name in leases and leases[name]['end'] is None,'export resources original release')
                    leases[name]['end']=row['sequence']
        for v in row['removed']:state.pop(t.key(v))
        for v in row['added']:state[t.key(v)]=v
        if row['sequence'] in wanted:states[row['sequence']]=dict(state)
    used=set()
    for case in cases:
        points={p['event']:p['point']['sequence'] for p in case['events']};begin=points['BEGIN'];end=points['FINISHED'];base=states[begin]
        need(base,'export resources live native baseline')
        for row in rows[begin+1:end+1]:
            need(not any(t.key(v) in base for v in row['added']+row['removed']),'export resources continuous original custody')
            need(all(v['unit']=='CONTROL' and v['owner'] in leases for v in row['added']+row['removed']),
                 'export resources unexpected interval mutation')
        prior=begin
        for role,opened,label in zip(ROLES,('SOURCE_OPENED','RECORD_OPENED','PREFIX_OPENED'),('SOURCE','RECORD','PREFIX')):
            candidates=[(k,v) for k,v in leases.items() if v['role']==role and prior<v['start']<=points[opened]]
            need(len(candidates)==1 and candidates[0][0] not in used,'export resources complete original acquisitions')
            name,lease=candidates[0];used.add(name);prior=points[opened]
            need(lease['start']<=points['READS_FINISHED']<lease['end'],'export resources overlapping original reads')
            need(points[label+'_RELEASE_BEGIN']<lease['end']<=points[label+'_RELEASED'],
                 'export resources release inside original call')
        need(states[end]==base,'export resources original baseline restored')
        need(points['PREFIX_RELEASED']==points['REUSE_REFUSED']==end,'export resources no revival or duplicate cleanup')
    need(set(leases)==used and len(used)==6,'export resources complete allocation coverage')
    return dict(status='PASS',scope='native-source-record-prefix-export-accounting',size=history['size'],exportReservations=len(used),
                originalCases=2,resourceTransitions=account['transitions'],exportReservationBindingsQualified=True,
                networkSessionQualified=False,expiryClockIndependentlyQualified=False,allExportFamiliesQualified=False,
                wholeRuntimeResourcesQualified=False,phase3Complete=False)


def load(root):
    root=Path(root);history=t.collection.read_json(root,'history.json',4*t.MIB)
    need(type(history) is dict and type(history.get('size')) is int and history['size'] in (3,4,5),'export resources original size')
    original,expected=originals(root,history['size'])
    return (t.read(root/'resources.json')[1],history,expected),original


def validate(root):
    root=Path(root);before=t.collection.inventory(root);data,original=load(root);result=replay(*data)
    need(t.collection.inventory(root)==before,'export resources changed original')
    return dict(result,physicalPrecondition=original)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args();print(json.dumps(validate(a.root),sort_keys=True))
