"""Finite accepted-tail recovery at SEAL/INTENT/FINAL under changing authority."""
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from . import integrated_model as m
from . import integrated_oracle as o
from . import operation_model as op
from . import activation_research as ar
from . import recovery_research as rr
from .transition_model import encoded
from .membership_model import NODES,need

PROFILES=((3,'ADD'),(4,'ADD'),(4,'REMOVE'),(5,'REMOVE'),(3,'REPLACE'),(4,'REPLACE'),(5,'REPLACE'))
TARGETS=('SEAL','INTENT','FINAL')
CUTS=('prepared','accept-one','accept-all','proof-one','certified','publication')
FILES=tuple(str(p.relative_to(Path(__file__).resolve().parents[2])) for p in sorted(Path(__file__).resolve().parent.glob('*.py')))


def command(group,kind):
    state=group.state();result=dict(kind=kind,number=1)
    if kind in ('INTENT','FINAL'):result['binding']=state['results']['1']['binding']
    return result


def prepared(group,kind):
    state=group.state();target=deepcopy(state['members'])
    if kind in ('REMOVE','REPLACE'):target.pop(0)
    if kind in ('ADD','REPLACE'):target.append(op.identity('node-6'))
    request=op.request(state,sorted(target,key=lambda v:v['voter']),kind)
    group.commit(dict(kind='RESERVE',request=request));group.commit(dict(kind='PREPARE',number=1,revision=1))
    group.commit(dict(kind='READY',number=1,receipt=group.materialize() if kind!='REMOVE' else None))
    return request


def finish(group):
    phase=group.state()['results']['1']['phase']
    if phase=='READY':group.commit(command(group,'SEAL'))
    if group.state()['results']['1']['phase']=='SEALED':group.commit(command(group,'INTENT'))
    if group.state()['results']['1']['phase']=='JOINT':group.commit()
    group.commit()


def scenario(size,kind,target,cut):
    g=m.Group(size);g.commit();request=prepared(g,kind)
    if target in ('INTENT','FINAL'):g.commit(command(g,'SEAL'))
    if target=='FINAL':g.commit(command(g,'INTENT'))
    try:
        handle,owners=g.begin(command(g,target))
        if cut!='prepared':
            g.select(handle,owners);g.exchange(handle,'accept',owners,count=1 if cut=='accept-one' else None)
            if cut not in ('accept-one','accept-all'):
                g.exchange(handle,'proof',owners,count=1 if cut=='proof-one' else None)
                if cut in ('certified','publication'):
                    g.engine.certify(handle);g.flush()
                    if cut=='publication':g.engine.stage_publication(handle);g.flush()
        end=len(g.events)
        for node in NODES:g.crash(node);g.restart(node)
        # At least one fresh round exercises highest-accepted recovery. Its
        # selected value may differ from the requested activation barrier.
        g.commit(last=True);finish(g)
        record=dict(g.evidence(),profile=[size,kind],target=target,cut=cut,cutEnd=end,
                    ballot=handle[1],owners=owners,request=request)
        audit=o.check(record);coverage(record)
        state=g.state();need(state['members']==request['target'] and state['results']['1']['phase']=='COMPLETED', 'transition not completed')
        return record,dict(events=audit['events'],applications=audit['applications'],campaigns=audit['protocol']['campaigns'],
                           learnerVoteEvents=audit['learnerVoteEvents'])
    except Exception as error:
        error.research_case=g.evidence();raise


def label(r):return f"{r['profile'][0]}-{r['profile'][1]}/{r['target']}/{r['cut']}"


def coverage(r):
    size,kind=r['profile'];need((size,kind) in PROFILES and r['target'] in TARGETS and r['cut'] in CUTS,'integrated label')
    need(tuple(r['old'])==NODES[:size] and r['request']['kind']==kind,'integrated profile')
    events=r['events'];end=r['cutEnd'];ballot=r['ballot']
    need(type(end) is int and 0<end<len(events) and events[end]['event']=='activation' and
         events[end]['detail']['event']=='crash','integrated cut offset')
    accepts=set();proofs=set();selected=False;certified=False;publication=False;starts=[]
    for outer in events[:end]:
        if outer['event']!='activation':continue
        e=outer['detail']
        if e['event']=='start' and e['ballot']==ballot:starts.append(e)
        if e['event']=='selection-force' and e['decision'].ballot==ballot:selected=True
        if e['event']=='publication-stage' and e['ballot']==ballot:publication=True
        if e['event']!='transition':continue
        row=e['detail']
        if row['event']=='certificate' and row['certificate'].ballot==ballot:certified=True
        if row['event']!='slot':continue
        row=row['detail'];msg=row.get('message')
        if msg is not None and msg.ballot==ballot:
            if row['event']=='accept-force':accepts.add(msg.voter)
            if row['event']=='proof-force':proofs.add(msg.voter)
    n=len(r['owners']);expected={'prepared':(0,0,False,False,False),'accept-one':(1,0,True,False,False),
        'accept-all':(n,0,True,False,False),'proof-one':(n,1,True,False,False),
        'certified':(n,n,True,True,False),'publication':(n,n,True,True,True)}[r['cut']]
    need((len(accepts),len(proofs),selected,certified,publication)==expected and len(starts)==1,'integrated crash relabelled')
    entry=m.t.Entry.read(starts[0]['value'])
    if entry.kind=='CONTROL':
        table={e['digest']:e['command'] for e in events[:end] if e['event']=='command'}
        need(table[entry.payload]['kind']==r['target'],'control target relabelled')
    else:need(entry.kind==r['target'],'membership target relabelled')


def decode(raw):
    acts=ar.decode(dict(root=raw['root'],old=raw['old'],input=[],
                       events=[e['detail'] for e in raw['events'] if e['event']=='activation']))['events']
    iterator=iter(acts);events=[]
    for event in raw['events']:
        event=dict(event)
        if event['event']=='activation':event['detail']=next(iterator)
        if event['event']=='apply':
            event['certificate']=rr.decode(dict(old=raw['old'],sourceEvents=[],events=[dict(certificate=event['certificate'])]))['events'][0]['certificate']
        events.append(event)
    return dict(raw,old=tuple(raw['old']),events=events,ballot=m.a.b.Ballot(**raw['ballot']),owners=tuple(raw['owners']))


def replay(examples):
    expected={f'{size}-{kind}/{target}/publication' for size,kind in PROFILES for target in TARGETS}
    need(set(examples)==expected,'integrated replay inventory')
    counts=dict(histories=0,events=0,applications=0,campaigns=0)
    for name,raw in examples.items():
        record=decode(raw);need(label(record)==name,'integrated replay label');coverage(record);audit=o.check(record)
        complete=[s for s in audit['states'].values() if s['members']==record['request']['target'] and
                  s['results'].get('1',{}).get('phase')=='COMPLETED']
        need(len(complete)>=len(record['request']['target']),'incomplete final catalogs')
        counts['histories']+=1;counts['events']+=audit['events'];counts['applications']+=audit['applications']
        counts['campaigns']+=audit['protocol']['campaigns']
    return counts


def binding():
    root=Path(__file__).resolve().parents[2]
    return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                worktreeDirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=root)),
                files={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in FILES})


def run(limit=None):
    need(limit is None or type(limit) is int and limit>=0,'case limit')
    counts=dict(cases=0,expectedCases=len(PROFILES)*len(TARGETS)*len(CUTS),events=0,applications=0,campaigns=0,learnerVoteEvents=0)
    result=dict(schema='gse-v53-integrated-research-v1',execution='global-votes-operation-learner',productionQualified=False,
                phase0Accepted=False,allInterleavings=False,counts=counts)
    examples={};digest=hashlib.sha256()
    for size,kind in PROFILES:
        for target in TARGETS:
            for cut in CUTS:
                if limit is not None and counts['cases']>=limit:return dict(result,status='INCOMPLETE',examples=examples)
                record,audit=scenario(size,kind,target,cut);digest.update((encoded(record)+'\n').encode());counts['cases']+=1
                for key in ('events','applications','campaigns','learnerVoteEvents'):counts[key]+=audit[key]
                if cut=='publication':examples[label(record)]=record
        print(json.dumps(dict(stage='integrated-matrix',profile=[size,kind],cases=counts['cases'])),flush=True)
    return dict(result,status='PASS',examples=examples,traceSha256=digest.hexdigest(),
                assumptions=['authentic identities','atomic metadata/image force','explicit source synchronization','fresh recovery ballot per command'],
                excluded=['steady-state round reuse','physical disk/wire behavior','autonomous liveness','public runtime','compacted-source integration'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-cases',type=int)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False);source=binding()
    try:
        result=run(args.max_cases);need(binding()==source,'source changed')
        path=args.output/'examples.json.gz';path.write_bytes(gzip.compress((encoded(result.pop('examples'))+'\n').encode(),mtime=0))
        result.update(examplesFile=path.name,examplesSha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if result['status']=='PASS':result['replay']=replay(json.loads(gzip.decompress(path.read_bytes())))
    except Exception as error:
        result=dict(status='FAIL',errorType=type(error).__name__,message=str(error),productionQualified=False)
        if hasattr(error,'research_case'):
            path=args.output/'failed-case.json.gz';path.write_bytes(gzip.compress(encoded(error.research_case).encode(),mtime=0))
            result['failedCaseSha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    result['source']=source;(args.output/'receipt.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True));return 0 if result['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
