"""Original reservation continuity through observed failed constructors.

This component reader checks accounting and file observations. It grants no
native authority, listener recovery, or whole-runtime resource qualification.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
from . import pending_drain_evidence as collection

t=collection.t
need=collection.need
SCOPES={'checkpoint':('checkpoint-bind','checkpoint-capacity'),
        'head':('head-bind','head-capacity'),
        'source-service':('service-guard','service-expiry','service-capacity')}
ROLES={'checkpoint':'joining-checkpoint-service-','head':'learner-head-','source-service':'transfer-service-'}
FIELDS={'case','begin','failed','error','message','beforeFiles','afterFiles'}


def files(rows):
    need(type(rows) is list and 0<len(rows)<=4096,'construction original file observations')
    names=[]
    for row in rows:
        need(type(row) is dict and set(row)=={'path','sha256'} and type(row['path']) is str and 0<len(row['path'])<=1024 and
             not PurePosixPath(row['path']).is_absolute() and all(v not in ('','..','.') for v in row['path'].split('/')) and
             type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']), 'construction original file observations')
        names.append(row['path'])
    need(len(set(names))==len(names),'construction original file observations')


def replay(trace,history):
    accounting=t.replay(trace)
    need(type(history) is dict and set(history)=={'schema','scope','status','cases','completeMembershipHistory'} and
         history['schema']=='gse-v53-construction-rollback-v1' and type(history['scope']) is str and history['scope'] in SCOPES and
         history['status']=='PASS' and history['completeMembershipHistory'] is False,'construction complete conditional history')
    scope=history['scope'];cases=history['cases'];rows=trace['changes']
    need(type(cases) is list and len(cases)==len(SCOPES[scope]),'construction exact failed cases')
    previous=-1;wanted=set()
    for case,name in zip(cases,SCOPES[scope]):
        need(type(case) is dict and set(case)==FIELDS and case['case']==name,'construction exact failed cases')
        for field in ('begin','failed'):
            p=case[field]
            need(type(p) is dict and set(p)=={'sequence','usage'} and type(p['sequence']) is int and 0<=p['sequence']<len(rows) and previous<=p['sequence'],
                 'construction ordered original boundaries')
            previous=p['sequence'];wanted.add(previous);t.same_usage(p['usage'],rows[previous]['usage'])
        bind=name.endswith('-bind');capacity=name.endswith('-capacity')
        expected='java.net.BindException' if bind else 'java.io.IOException' if name.endswith('-guard') else 'java.lang.IllegalArgumentException'
        need(case['error']==expected and type(case['message']) is str and 0<len(case['message'])<=1024 and
             (bind or case['message']==('resource ownership/count' if capacity else 'construction guard rejected' if name.endswith('-guard') else
                                       'original transfer service deadline/closed')), 'construction exact failure outcome')
        if capacity:need(case['begin']['usage']['counts'].get('CONTROL')==t.COUNTS['CONTROL'],'construction original capacity pressure')
        files(case['beforeFiles']);need(case['beforeFiles']==case['afterFiles'],'construction unchanged original files')
    state={};states={}
    for row in rows:
        for v in row['removed']:state.pop(t.key(v))
        for v in row['added']:state[t.key(v)]=v
        if row['sequence'] in wanted:states[row['sequence']]=dict(state)
    total=0
    for case in cases:
        begin=case['begin']['sequence'];end=case['failed']['sequence'];original=states[begin];allocated=[]
        for row in rows[begin+1:end+1]:
            need(not any(t.key(v) in original for v in row['removed']+row['added']),'construction continuous original custody')
            for v in row['added']:
                need(v['unit']=='CONTROL' and v['bytes']==32768 and not v['claimSource'] and
                     re.fullmatch(re.escape(ROLES[scope])+r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',v['owner']),
                     'construction exact temporary reservation')
                allocated.append(t.key(v))
        need(states[end]==original,'construction rollback before failure return')
        need(len(allocated)==len(set(allocated))==(1 if case['case'].endswith(('-bind','-expiry')) else 0),
             'construction complete temporary acquisitions')
        total+=len(allocated)
    return dict(status='PASS',scope='conditional-'+scope+'-constructor-rollback',cases=len(cases),rolledBackReservations=total,
                resourceTransitions=accounting['transitions'],failedConstructionRollbackQualified=True,
                serviceRecoveryQualified=False,physicalStorageQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def validate(root):return replay(*collection.load(root))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    print(json.dumps(validate(a.root),sort_keys=True))
