"""Derive complete observed REMOVE retirement across original process recovery.

Physical/network/export/floor/retention qualification runs first. Recovery is
derived from the original first-cut prefix; later snapshots are comparisons.
This does not invent unobserved transient files or close the process matrix.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import remove_process_retention as retention

r=retention;old=r.p.retirement
n,p,c,f,need,sha=r.n,r.p,r.c,r.f,r.need,r.sha
PREFIXES=old.PREFIXES


def strip_floor(files):return {k:v for k,v in files.items() if k!='floor-copies' and not k.startswith('floor-copies/')}


def interrupted(files,node,copies,point,generation_after,generation_steps,available):
    """Finish only the original interrupted transaction, not later maintenance."""
    if point.startswith('RETIREMENT_'):
        at=p.prefix_at(generation_steps,point);prefix=generation_steps[at][1]
        recovered,recovery,_=old.generation_plan(files,node,copies,recover=prefix)
        return recovered,generation_steps[:at+1],recovery,0
    need(point.startswith('SOURCE_RETIREMENT_') or point.startswith('JOURNAL_ROTATION_'),
         'REMOVE process retirement cut kind')
    prefix,recovered,recovery,source_steps=p.source_interruption(generation_after,point,available)
    return recovered,[*generation_steps,*source_steps],recovery,1


def coverage(files,own):
    available=r.peer.t.confirmation.endpoints(own['packet'],own['members'].get('ancestry.gsr',b''))
    plan=r.peer.peers.decode(files[r.peer.FILE])['plan']
    for remote in plan['peers']:
        for point in remote['possible']+remote.get('renewals',[]):
            need(available.get(point['cut']['index'])==point,'REMOVE process retirement retained endpoint coverage')
    return available


def compare_callbacks(actual,steps,reason):
    need([v['event'] for _,v in actual]==[name for name,_ in steps],reason)
    need(all(set(v)=={'node','event'} for _,v in actual),'REMOVE process retirement callback shape')


def capacity(steps):
    peak=0
    for _,state in steps:
        p.capacity(state);peak=max(peak,sum(name.endswith('.image') for name in state))
    return peak


class Replay(r.PeerReplay):
    def __init__(self,root,profile):
        super().__init__(root,profile);self.maintained={};self.retirements=[]

    def floor(self,row):
        super().floor(row);self.maintained[row['start']]=self.state[row['own']['node']]

    def callbacks(self,node,lower,upper):
        return [(i,v) for i,v in enumerate(self.events) if lower<i<upper and v['node']==node and v['event'].startswith(PREFIXES)]

    def run(self):
        peer_result=super().run();bound=set();counts=Counter();recovered=None;peak=0;seen=set()
        for row in self.floor_inputs:
            own=row['own'];node=own['node'];start=row['start'];base=self.files(own)
            if row['reused']:
                need(recovered is not None and node==recovered['node'],'REMOVE process retirement missing original recovery')
                base=strip_floor(recovered['files']);recovered=None
            else:
                # A later floor on the same observed generation would need a
                # new state transition, not a reset to its installed snapshot.
                key=(node,own['path'],sha(own['manifest']))
                need(key not in seen,'REMOVE process retirement repeated snapshot seed');seen.add(key)
            files=old.sources.governing(base,{key:self.files(value) for key,value in row['copies'].items()},node)
            files[r.peer.FILE]=self.maintained[start];available=coverage(files,own)
            current,_,_=c.current(files)
            inactive=any(k.startswith('generations/') and k!=current[:-1] and not k.startswith(current) for k in files)
            if inactive:after,steps,details=old.generation_plan(files,node,row['copies'])
            else:after,steps,details=files,[],{}
            completed,decisions=old.source_plans(after,node,available)
            actual=self.callbacks(node,row['returned'],row['end']);recovery_record=None
            if row['interrupted']:
                need(recovered is None and node=='node-1','REMOVE process retirement interrupted owner')
                result,prefix,recovery,sources=interrupted(files,node,row['copies'],self.profile['point'],after,steps,available)
                compare_callbacks(actual,prefix,'REMOVE process retirement exact interrupted prefix')
                resumed=self.callbacks(node,row['end'],self.live[1][0])
                compare_callbacks(resumed,recovery,'REMOVE process retirement exact original recovery')
                need(result==c.inventory(self.root/'resume-opened-0'/node),'REMOVE process retirement derived recovered tree')
                recovered=dict(node=node,files=result);bound.update(i for i,_ in resumed)
                peak=max(peak,capacity([*prefix,*recovery]));counts.update(dict(recoveryCallbacks=len(recovery),callbacks=len(resumed),interruptedTransactions=1))
                recovery_record=dict(start=row['end'],end=self.live[1][0],events=[name for name,_ in recovery],
                    prefixInventory=sha(f.canonical(prefix[-1][1])))
                expected=prefix;completed=result;source_details=decisions[:sources]
            else:
                expected=[*steps,*[(name,state) for decision in decisions for name,state in decision['steps']]]
                compare_callbacks(actual,expected,'REMOVE process retirement complete transaction callbacks')
                peak=max(peak,capacity(expected));sources=len(decisions);source_details=decisions
            bound.update(i for i,_ in actual)
            counts.update(dict(generations=int(inactive),sources=sources,callbacks=len(actual),
                borrowedGenerations=int(details.get('borrowedImages',False)),generationMembers=details.get('members',0)))
            self.retirements.append(dict(node=node,path=own['path'],start=row['returned'],end=row['end'],
                interrupted=row['interrupted'],reused=row['reused'],**details,
                events=[name for name,_ in expected],sources=[{k:v for k,v in d.items() if k!='steps'} for d in source_details],
                recovery=recovery_record,finalInventory=sha(f.canonical(old.physical(completed)))))
        need(recovered is None,'REMOVE process retirement unconsumed recovered tree')
        need(bound=={i for i,v in enumerate(self.events) if v['event'].startswith(PREFIXES)},'REMOVE process retirement unbound callback')
        return dict(status='PARTIAL',**dict(counts),physicalImagePeak=peak,transactionChainSha256=sha(f.canonical(self.retirements)),
            peerPrecondition=peer_result,completeObservedRetirementCallbacksQualified=True,completeObservedCompositionQualified=False,
            transientRetirementBytesQualified=False,phase3Complete=False)


def replay(root,profile):return Replay(root,profile).run()


def validate(root):
    root=Path(root);before=p.run.h.inventory(root);original=r.validate(root)
    result=replay(root,p.profile_at(root))
    need(p.run.h.inventory(root)==before,'REMOVE process retirement original changed')
    return dict(result,precondition=original,retirementRetentionCompositionQualified=True,
        ballotForceCompositionQualified=False,originalObservationCoverageComplete=False)


NEGATIVES={name:'REMOVE process retirement complete transaction callbacks' for name in old.OMISSIONS}
NEGATIVES.update({name:'REMOVE process retirement complete transaction callbacks' for name in
    ('member-force-before-write','saved-delete-before-original-delete','journal-rename-before-force','duplicate-delete','unbound-in-floor')})
NEGATIVES['callback-extra-field']='REMOVE process retirement callback shape'


def mutate(root,profile,name):
    events,_=n.observations(root,profile)
    shared=[n.e.parse(v) for v in (Path(root)/'history/process-trace.jsonl').read_bytes().splitlines()];mapping=[]
    for row in shared:
        normalized=[row['value']] if row['origin']=='parent' else n.normalize(row['value']['kind'],row['value']['value'])[0]
        mapping.extend([row]*len(normalized))
    need(len(events)==len(mapping),'REMOVE process retirement mutation mapping')
    # Mutate a complete parent-owned retirement, preserving the killed child's
    # first-cut boundary, STORE schema and complete original process lifetimes.
    def first(point):return next(i for i,v in enumerate(events) if v['event']==point and mapping[i]['origin']=='parent')
    def locate(row):return next(i for i,v in enumerate(shared) if v is row)
    def move(point,before):
        at=first(point);row=shared.pop(locate(mapping[at]))
        target=next(i for i,v in enumerate(events) if v['node']==events[at]['node'] and v['event']==before)
        shared.insert(locate(mapping[target]),row)
    if name in old.OMISSIONS:shared.pop(locate(mapping[first(name)]))
    elif name=='member-force-before-write':move('RETIREMENT_MEMBER_FORCED','RETIREMENT_MEMBER_WRITTEN')
    elif name=='saved-delete-before-original-delete':move('RETIREMENT_SAVED_FILE_DELETED','RETIREMENT_FILE_DELETED')
    elif name=='journal-rename-before-force':move('JOURNAL_ROTATION_RENAMED','JOURNAL_ROTATION_FORCED')
    elif name=='duplicate-delete':
        row=mapping[first('RETIREMENT_FILE_DELETED')];shared.insert(locate(row),copy.deepcopy(row))
    elif name=='callback-extra-field':mapping[first('RETIREMENT_PROPOSAL_WRITTEN')]['value']['claimedHash']='a'*64
    elif name=='unbound-in-floor':
        row=mapping[first('RETIREMENT_BEFORE_RETURN')]
        shared.insert(locate(row),dict(origin='parent',value=dict(node=row['value']['node'],event='JOURNAL_ROTATION_UNBOUND')))
    else:raise ValueError('REMOVE process unknown retirement negative')
    n.rewrite(root,shared)


def negative(root,profile,before,name):
    with tempfile.TemporaryDirectory(prefix='v53-remove-process-retirement-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,profile,name)
        after=p.run.h.inventory(changed);protected=lambda inv:{k:v for k,v in inv['files'].items() if k not in r.OBSERVATIONS}
        need(protected(before)==protected(after) and before['directories']==after['directories'],
             'REMOVE process retirement negative changed physical or wire inputs')
        original,_=n.observations(root,profile);altered,_=n.observations(changed,profile)
        other=lambda rows:[v for v in rows if not v['event'].startswith(PREFIXES)]
        need(other(original)==other(altered),'REMOVE process retirement negative changed other observations')
        r.replay(changed,profile)
        try:replay(changed,profile)
        except ValueError as error:need(str(error)==NEGATIVES[name],'REMOVE process unrelated retirement negative: '+name+': '+str(error))
        else:raise ValueError('REMOVE process retirement mutation accepted: '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],retentionReplay='PASS',physicalWireAndOtherObservationsUnchanged=True)


def qualify(root,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'REMOVE process retirement replay workers')
    root=Path(root);original=validate(root);before=p.run.h.inventory(root);profile=p.profile_at(root);results=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(negative,root,profile,before,name):name for name in NEGATIVES}
        for task in as_completed(tasks):
            name=tasks[task]
            try:result=task.result()
            except Exception as error:result=dict(case=name,status='FAIL',type=type(error).__name__,failure=str(error))
            results.append(result);print(json.dumps(dict(result,completed=len(results),total=len(tasks))),file=sys.stderr,flush=True)
    need(p.run.h.inventory(root)==before,'REMOVE process retirement negatives changed original')
    need(all(v['status']=='REJECTED' for v in results),'REMOVE process retirement negative matrix failed')
    return dict(original=original,negatives=sorted(results,key=lambda v:v['case']),
        negativePrecondition='full-original-physical-network-export-floor-retention; mutated retention replay; unchanged files, wire and non-retirement observations',
        mutatedFullPrerequisiteReplayed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    print(json.dumps(qualify(args.root,workers=args.workers) if args.qualify else validate(args.root),sort_keys=True))
