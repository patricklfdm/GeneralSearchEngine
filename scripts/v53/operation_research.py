"""Finite committed-operation crash schedules; no production consensus claim."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from . import operation_model as m
from . import operation_oracle as o
from .transition_model import encoded
from .membership_model import need

PROFILES=((3,'ADD'),(4,'ADD'),(4,'REMOVE'),(5,'REMOVE'),(3,'REPLACE'),(4,'REPLACE'),(5,'REPLACE'))
PATHS=dict(complete=('RESERVE','PREPARE','READY','SEAL','INTENT','FINAL','RETIRE'),
           cancel=('RESERVE','PREPARE','READY','CANCEL','RETIRE'),
           reprepare=('RESERVE','PREPARE','READY','DATA','PREPARE','READY','SEAL','INTENT','FINAL','RETIRE'))
FILES=tuple('scripts/v53/'+n+'.py' for n in ('__init__','membership_model','ballot_model','transition_model',
    'recovery_model','recovery_oracle','operation_model','operation_oracle','operation_research','test_operation_model'))


def scenario(size,kind,path,cut,boundary):
    members=[m.identity('node-'+str(i)) for i in range(1,size+1)]
    target=members[1:] if kind in ('REMOVE','REPLACE') else list(members)
    if kind in ('ADD','REPLACE'):target=target+[m.identity('node-6')]
    s=m.Store(members);request=m.request(s.state,target,kind);steps=PATHS[path]
    def command(step):
        if step=='RESERVE':return dict(kind=step,request=request)
        if step=='DATA':return dict(kind=step,value='concurrent-data')
        if step=='RETIRE':return dict(kind=step,through=1)
        row=s.state['results']['1'];result=dict(kind=step,number=1)
        if step=='PREPARE':result['revision']=row['revision']+1
        if step=='READY':result['receipt']=s.learner_force(1) if m.joining(s.state,request) else None
        if step in ('INTENT','FINAL'):result['binding']=row['binding']
        return result
    try:
        completed=0
        for index,step in enumerate(steps):
            s.stage(command(step))
            if index==cut and boundary=='stage':break
            s.force();completed+=1
            if index==cut:break
        s.detach_waiter();s.crash();s.restart()
        for step in steps[completed:]:s.stage(command(step));s.force()
        need(s.submit(request)['status']=='RETIRED','old operation revived')
        record=dict(s.evidence(),profile=[size,kind],path=path,cut=cut,boundary=boundary,request=request)
        audit=o.check(record);need(audit['state']==s.state and s.state['retiredThrough']==1,'incomplete operation replay')
        coverage(record)
        return record,dict(events=audit['events'],commits=audit['commits'])
    except Exception as error:
        error.research_case=s.evidence();raise


def label(record):return f"{record['profile'][0]}-{record['profile'][1]}/{record['path']}/{record['cut']}-{record['boundary']}"


def coverage(record):
    size,kind=record['profile'];steps=PATHS[record['path']]
    need((size,kind) in PROFILES and 0<=record['cut']<len(steps) and record['boundary'] in ('stage','force'),'operation coverage label')
    events=record['events'];crashes=[i for i,e in enumerate(events) if e['event']=='crash']
    need(len(crashes)==1 and sum(e['event']=='restart' for e in events)==1,'crash coverage')
    writes=[e for e in events[:crashes[0]] if e['event'] in ('stage','force')]
    last=writes[-1]
    need(last['event']==record['boundary'] and last['command']['kind']==steps[record['cut']] and
         [e['command']['kind'] for e in writes if e['event']=='stage']==list(steps[:record['cut']+1]),'relabelled operation cut')
    need(record['initial']['members']==[m.identity('node-'+str(i)) for i in range(1,size+1)] and
         record['request']['kind']==kind,'relabelled operation profile')


def expected_labels():
    return {f'{size}-{kind}/{path}/{cut}-{boundary}' for size,kind in PROFILES for path,steps in PATHS.items()
            for cut in range(len(steps)) for boundary in ('stage','force')}


def replay(examples):
    need(set(examples)==expected_labels(),'operation replay inventory')
    counts=dict(histories=0,events=0,commits=0)
    for name,record in examples.items():
        need(name==label(record),'operation replay name');coverage(record);result=o.check(record)
        state=result['state'];need(state['active'] is None and state['retiredThrough']==1 and state['nextOperation']==2,'unfinished operation')
        target=record['initial']['members'] if record['path']=='cancel' else record['request']['target']
        need(state['members']==target and state['results']=={},'operation terminal state')
        counts['histories']+=1
        for key in ('events','commits'):counts[key]+=result[key]
    return counts


def binding():
    root=Path(__file__).resolve().parents[2]
    return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                worktreeDirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=root)),
                files={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in FILES})


def run(limit=None):
    need(limit is None or type(limit) is int and limit>=0,'case limit')
    result=dict(schema='gse-v53-operation-research-v1',execution='committed-operation-reducer',productionQualified=False,
                phase0Accepted=False,allInterleavings=False,counts=dict(cases=0,expectedCases=len(expected_labels()),events=0,commits=0))
    examples={};trace=hashlib.sha256()
    for size,kind in PROFILES:
        for path,steps in PATHS.items():
            for cut in range(len(steps)):
                for boundary in ('stage','force'):
                    if limit is not None and result['counts']['cases']>=limit:return dict(result,status='INCOMPLETE',examples=examples)
                    record,audit=scenario(size,kind,path,cut,boundary);examples[label(record)]=record
                    trace.update((encoded(record)+'\n').encode());result['counts']['cases']+=1
                    for key in ('events','commits'):result['counts'][key]+=audit[key]
        print(json.dumps(dict(stage='operation-matrix',profile=[size,kind],cases=result['counts']['cases'])),flush=True)
    return dict(result,status='PASS',traceSha256=trace.hexdigest(),examples=examples,
                assumptions=['certification supplied by separate consensus layer','atomic metadata force','authentic learner receipts'],
                excluded=['accepted-only consensus tails','actual application or disk bytes','live network/leader scheduling','public runtime'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-cases',type=int)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);source=binding()
    try:
        result=run(a.max_cases);need(binding()==source,'source changed')
        path=a.output/'examples.json.gz';path.write_bytes(gzip.compress((encoded(result.pop('examples'))+'\n').encode(),mtime=0))
        result.update(examplesFile=path.name,examplesSha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if result['status']=='PASS':result['replay']=replay(json.loads(gzip.decompress(path.read_bytes())))
    except Exception as error:
        result=dict(status='FAIL',errorType=type(error).__name__,message=str(error),productionQualified=False)
        if hasattr(error,'research_case'):
            path=a.output/'failed-case.json.gz';path.write_bytes(gzip.compress(encoded(error.research_case).encode(),mtime=0))
            result['failedCaseSha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    result['source']=source;(a.output/'receipt.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True));return 0 if result['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
