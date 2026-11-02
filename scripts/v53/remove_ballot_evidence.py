"""Ordinary REMOVE allocator/promise continuity after captured retirement replay.

Reuse the process reader's force/grant algorithm, with original ordinary history
boundaries. A snapshot compares derived state; it never seeds a later round.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import remove_process_ballot as shared
from . import remove_retirement_prefixes as prior
from . import authority_transition_evidence as preparation

r=prior.r;e=r.e;n=r.n;c=r.c;f=r.f;need=r.need;sha=r.sha
PROFILES=n.original.PROFILES
NEGATIVES={k:v.replace('REMOVE process ballot','REMOVE ballot') for k,v in shared.NEGATIVES.items()}


class Replay(shared.Replay):
    label='REMOVE ballot'
    def __init__(self,root,profile):
        need(profile in PROFILES,'REMOVE ballot profile')
        root=Path(root);base=e.Replay(root,profile)
        original=preparation.prelude(root,'INTENT',size=len(base.history.old)).group
        self.initialize(root,profile,base,original)
    def activation_phases(self):return self.history.phases
    def snapshot_actions(self):
        actions=[]
        for (ordinal,node),points in n.phase.blocks(self.events,self.history).items():
            for prefix,point in (('applied','APPLY_BEFORE_RETURN'),('published','PUBLICATION_BEFORE_RETURN')):
                path=f'{prefix}-{ordinal+4}/{node}'
                actions.append((points[point],'original',(node,path,path)))
        return actions


def replay(root,profile):return Replay(root,profile).run()


def validate(root,captures,profile):
    need(profile in PROFILES,'REMOVE ballot profile');root=Path(root);captures=Path(captures)
    before=n.collection.inventory(root);captured=n.collection.inventory(captures)
    original=prior.validate(root,captures,profile);result=replay(root,profile)
    need(n.collection.inventory(root)==before and n.collection.inventory(captures)==captured,'REMOVE ballot original changed')
    return dict(result,profile=profile,scope='ordinary-REMOVE-continuous-ballot',precondition=original,
                allMembershipProfilesQualified=False,currentSourceNativeCohortQualified=False,processDeathQualified=False,
                originalObservationCoverageComplete=False)


def mutate(root,profile,name):
    need(name in NEGATIVES,'REMOVE ballot unknown negative');root=Path(root)
    events=n.collection.read_json(root,'events.json',n.collection.EVENT_BYTES)
    tx=shared.b.allocations(events,tuple('node-'+str(i+1) for i in range(int(profile[0]))),None)
    first=tx[0];owner=first['node'];other=next('node-'+str(i+1) for i in range(int(profile[0])) if 'node-'+str(i+1)!=owner)
    rows=[v for v in events[first['start']:first['end']+1] if v.get('node')==owner and v['event'] in shared.b.WRITES]
    def locate(row):return next(i for i,v in enumerate(events) if v is row)
    def remove(row):events.pop(locate(row))
    def move(values,target):
        ids={id(v) for v in values};events[:]=[v for v in events if id(v) not in ids]
        at=locate(target);events[at:at]=values
    if name in ('force-missing','directory-force-missing','incomplete-write'):
        remove(events[tx[-1]['end']] if name=='incomplete-write' else rows[3 if name=='force-missing' else 5])
    elif name=='rename-before-force':move([rows[4]],rows[3])
    elif name=='duplicate-return':move([dict(rows[-1])],rows[-1])
    elif name=='unknown-allocator-event':events.append(dict(node=owner,event='ALLOCATOR_UNKNOWN'))
    elif name=='foreign-owner':rows[0]['node']='node-9'
    elif name=='forged-field':rows[0]['counter']=1
    elif name=='reservation-after-grant':move(rows,next(v for v in events if v.get('node')==owner and v['event']=='GRANT_BEFORE_RETURN'))
    elif name=='reservation-before-open':move(rows,events[0])
    elif name=='extra-local-reservation':move([dict(v) for v in rows],rows[0])
    elif name=='unbound-reservation':events.extend(dict(node=other,event=v) for v in shared.b.WRITES)
    else:
        parts=[next(v for v in events if v.get('node')==owner and v['event']==point) for point in shared.b.PROMISE]
        if name=='promise-write-missing':remove(parts[1])
        elif name=='promise-force-before-write':move([parts[2]],parts[1])
        elif name=='promise-extra-field':parts[1]['claimedHash']='a'*64
        elif name=='promise-unknown':parts[1]['event']='PROMISE_UNKNOWN'
        elif name=='promise-duplicate':move([dict(parts[2])],parts[2])
        elif name=='promise-unbound':events.extend(dict(node=owner,event=v) for v in shared.b.PROMISE)
    (root/'events.json').write_bytes(f.canonical(events))


def negative(root,profile,before,name):
    with tempfile.TemporaryDirectory(prefix='v53-remove-ballot-negative-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed)
        try:mutate(changed,profile,name)
        except (StopIteration,IndexError) as error:raise ValueError('REMOVE ballot missing negative target: '+name) from error
        after=n.collection.inventory(changed);protected=lambda value:{k:v for k,v in value['files'].items() if k!='events.json'}
        need(protected(before)==protected(after) and before['directories']==after['directories'],'REMOVE ballot negative changed physical or wire inputs')
        other=lambda path:[v for v in n.collection.read_json(Path(path),'events.json',n.collection.EVENT_BYTES) if not shared.relevant(v)]
        need(other(root)==other(changed),'REMOVE ballot negative changed other observations')
        r.replay(changed,profile)
        try:replay(changed,profile)
        except ValueError as error:need(str(error)==NEGATIVES[name],'REMOVE unrelated ballot negative: '+name+': '+str(error))
        else:raise ValueError('REMOVE ballot mutation accepted: '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],retirementReplay='PASS',physicalWireAndOtherObservationsUnchanged=True)


def qualify(root,captures,profile,*,workers=1,progress=None):
    need(type(workers) is int and 1<=workers<=4,'REMOVE ballot replay workers')
    root=Path(root);captures=Path(captures);original=validate(root,captures,profile)
    before=n.collection.inventory(root);captured=n.collection.inventory(captures);results=[]
    if progress:progress(dict(stage='original',status='PASS',negativeCases=len(NEGATIVES)))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(negative,root,profile,before,name):name for name in NEGATIVES}
        for task in as_completed(tasks):
            try:result=task.result()
            except Exception as error:result=dict(case=tasks[task],status='FAIL',failure=str(error),type=type(error).__name__)
            results.append(result)
            if progress:progress(dict(result,completed=len(results),total=len(tasks)))
    need(n.collection.inventory(root)==before and n.collection.inventory(captures)==captured,'REMOVE ballot qualification changed original')
    need(all(v['status']=='REJECTED' for v in results),'REMOVE ballot negative matrix failed')
    return dict(original=original,negatives=sorted(results,key=lambda v:v['case']),mutatedFullPrerequisiteReplayed=False,
                negativePrecondition='full original including captured retirement; mutated retention/retirement callbacks; unchanged physical files, wire and other observations')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('captures')
    p.add_argument('--profile',required=True,choices=PROFILES);p.add_argument('--qualify',action='store_true');p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    result=qualify(a.root,a.captures,a.profile,workers=a.workers,progress=lambda v:print(json.dumps(v),file=sys.stderr,flush=True)) if a.qualify else validate(a.root,a.captures,a.profile)
    print(json.dumps(result,sort_keys=True))
