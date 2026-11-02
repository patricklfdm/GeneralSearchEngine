"""Bind continuous REMOVE allocator and promise forces across original process death.

The independently replayed admitted prelude is the only seed. Original later
snapshots compare state; they cannot reset counters after SIGKILL or reopen.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import shutil
import sys
import tempfile
import json
from . import remove_process_retirement as prior
from . import joining_same_view_ballot as b
p,c,f,need,sha=prior.p,prior.c,prior.f,prior.need,prior.sha
class Replay:
    label='REMOVE process ballot'
    def __init__(self,root,profile):
        base=prior.r.m.e.Replay(root,profile);history_root=Path(root)/'history'
        original=p.a.prelude(history_root,'INTENT',size=len(base.history.old)).group
        self.initialize(history_root,profile,base,original)
    def initialize(self,root,profile,base,original):
        self.root=Path(root);self.profile=profile;self.base=base
        self.events=base.events;self.history=base.history;self.tx=b.allocations(self.events,self.history.old,None)
        self.state=b.State(c.current(original['node-1'])[2]['capsule']['root']);self.used=set();self.promise_points=set();self.self_grants=0;self.promise_comparisons=0
        for node,files in original.items():
            counter=f.decode(files['allocator.gsr'],'records','ALLOCATOR')['counter'];self.state.seed(node,counter,self.promised(files,node))
        self.snapshot('before-network')
    def promised(self,files,node):return max([0,*[v['ballot']['counter'] for _,_,v in c.journal(files['grants.gsr'],self.state.root,node)]])
    def original(self,node,path,label):
        files=c.inventory(self.root/path);self.state.compare(node,files['allocator.gsr'],label)
        need(self.state.observed[node]==self.promised(files,node),self.label+' continuous promise: '+label+': '+node);self.promise_comparisons+=1
    def snapshot(self,path):
        for node in self.history.old:self.original(node,path+'/'+node,path)
    def promise(self,node,lower,upper,ballot,actions):
        rows=[(i,v) for i,v in enumerate(self.events) if lower<i<upper and v['node']==node and v['event'].startswith('PROMISE_')]
        need([v['event'] for _,v in rows]==b.PROMISE and all(set(v)=={'node','event'} for _,v in rows),self.label+' promise force order')
        need(not self.promise_points.intersection(i for i,_ in rows),self.label+' reused promise');self.promise_points.update(i for i,_ in rows)
        actions.append((rows[-1][0],'promise',(node,ballot['counter'])))
    def grant(self,node,ballot):
        ids=prior.n.n.shared.s.catalog.identities(self.history.states[-1]['identities'])
        need(ballot==dict(counter=self.state.counters[node],proposer=node,incarnation=ids[node]['storage']),self.label+' reserved ballot')
    def activation_phases(self):return self.history.activations(self.root.parent,self.profile).phases
    def snapshot_actions(self):return prior.r.snapshot_actions(self.base,'snapshot')
    def run(self):
        actions=[];lower=-1
        for parts in self.activation_phases():
            raw=parts['SELECTED'];selected=f.decode(raw,'records','SELECTED');ballot=selected['ballot']
            ends=[i for i,v in enumerate(self.events) if v['event']=='ROUND_INSTALLED' and v['record']==sha(raw)]
            need(len(ends)==1,self.label+' exact installed boundary');end=ends[0]
            for source in selected['sources']:
                node=source['voter'];starts=[i for i,v in enumerate(self.events) if lower<i<end and v['node']==node and v['event']=='CURRENT_BEFORE_CAPTURE']
                returns=[i for i,v in enumerate(self.events) if lower<i<end and v['node']==node and v['event']=='GRANT_BEFORE_RETURN']
                need(len(starts)==len(returns)==1 and starts[0]<returns[0],self.label+' grant boundaries');start=starts[0];returned=returns[0]
                captures=[v for v in self.base.sources if v['node']==node and sha(v['basis'])==source['basisDigest']]
                need(len(captures)==1 and captures[0]['start']==returned and captures[0]['value']['ballot']==ballot,self.label+' original grant')
                self.promise(node,start,returned,ballot,actions)
                if node==ballot['proposer']:
                    current=max(i for i,v in enumerate(self.events[:start]) if v['node']==node and v['event']=='CURRENT_DIRECTORY_FORCED')
                    candidates=[v for v in self.tx if v['node']==node and max(lower,current)<v['start']<v['end']<start]
                    need(len(candidates)==1 and candidates[0]['start'] not in self.used,self.label+' one reservation per grant')
                    self.used.add(candidates[0]['start']);self.self_grants+=1;actions.append((start,'grant',(node,ballot)))
            lower=end
        need(self.used=={v['start'] for v in self.tx},self.label+' unbound allocator')
        need(self.promise_points=={i for i,v in enumerate(self.events) if v['event'].startswith('PROMISE_')},self.label+' unbound promise')
        actions.extend((v['end'],'reserve',(v,)) for v in self.tx)
        actions+=self.snapshot_actions()
        for own in self.base.windows:
            if own['start']>=0 and self.events[own['start']]['event']=='INSTALL_BEFORE_RETURN':actions.append((own['start'],'original',(own['node'],own['path'],'installed')))
        for _,kind,values in sorted(actions,key=lambda v:v[0]):getattr(self.state if kind in ('reserve','promise') else self,kind)(*values)
        self.snapshot('after-close')
        return dict(status='PARTIAL',ballotForceCompositionQualified=True,completeObservedCompositionQualified=False,
            selfGrants=self.self_grants,reservations=len(self.tx),forcedPromises=len(self.promise_points)//3,
            allocatorComparisons=self.state.comparisons,promiseComparisons=self.promise_comparisons,counters=self.state.counters,observed=self.state.observed,
            chain=sha(f.canonical(self.state.steps)),phase3Complete=False)


def replay(root,profile):return Replay(root,profile).run()


def validate(root):
    root=Path(root);before=p.run.h.inventory(root);original=prior.validate(root)
    result=replay(root,p.profile_at(root))
    need(p.run.h.inventory(root)==before,'REMOVE process ballot original changed')
    return dict(result,precondition=original,originalObservationCoverageComplete=False)


NEGATIVES={
    'force-missing':'joining ballot exact allocator force order',
    'rename-before-force':'joining ballot exact allocator force order',
    'directory-force-missing':'joining ballot exact allocator force order',
    'duplicate-return':'joining ballot exact allocator force order',
    'incomplete-write':'joining ballot incomplete allocation',
    'unknown-allocator-event':'joining ballot unsupported allocator event',
    'foreign-owner':'joining ballot allocator event shape',
    'forged-field':'joining ballot allocator event shape',
    'reservation-after-grant':'REMOVE process ballot one reservation per grant',
    'reservation-before-open':'REMOVE process ballot one reservation per grant',
    'extra-local-reservation':'REMOVE process ballot one reservation per grant',
    'unbound-reservation':'REMOVE process ballot unbound allocator',
    'promise-write-missing':'REMOVE process ballot promise force order',
    'promise-force-before-write':'REMOVE process ballot promise force order',
    'promise-extra-field':'REMOVE process ballot promise force order',
    'promise-unknown':'REMOVE process ballot promise force order',
    'promise-unbound':'REMOVE process ballot unbound promise',
    'promise-duplicate':'REMOVE process ballot promise force order',
}


def relevant(row):return row['event'].startswith(('ALLOCATOR_','PROMISE_'))


def mutate(root,profile,name):
    import copy
    n=prior.n;events,_=n.observations(root,profile)
    shared=[n.e.parse(v) for v in (Path(root)/'history/process-trace.jsonl').read_bytes().splitlines()];mapping=[]
    for row in shared:
        translated=[row['value']] if row['origin']=='parent' else n.normalize(row['value']['kind'],row['value']['value'])[0]
        mapping.extend([row]*len(translated))
    need(len(mapping)==len(events),'REMOVE process ballot mutation mapping')
    transactions=b.allocations(events,tuple('node-'+str(i+1) for i in range(int(profile['profile'][0]))),None)
    def locate(row):return next(i for i,v in enumerate(shared) if v is row)
    def move(rows,target):
        ids={id(v) for v in rows};shared[:]=[v for v in shared if id(v) not in ids]
        at=locate(target);shared[at:at]=rows
    def first(point):return next(i for i,v in enumerate(events) if v['event']==point)
    tx=transactions[0]
    rows=[mapping[i] for i in range(tx['start'],tx['end']+1) if events[i]['node']==tx['node'] and events[i]['event'] in b.WRITES]
    if name in ('force-missing','directory-force-missing','incomplete-write'):
        row=rows[3 if name=='force-missing' else 5] if name!='incomplete-write' else mapping[transactions[-1]['end']]
        shared.pop(locate(row))
    elif name=='rename-before-force':move([rows[4]],rows[3])
    elif name=='duplicate-return':move([copy.deepcopy(rows[-1])],rows[-1])
    elif name=='unknown-allocator-event':
        shared.insert(locate(rows[0]),dict(origin='parent',value=dict(node='node-1',event='ALLOCATOR_UNKNOWN')))
    elif name in ('foreign-owner','forged-field'):
        value=dict(events[tx['start']]);value.update(dict(node='node-9') if name=='foreign-owner' else dict(counter=1))
        shared[locate(rows[0])]=dict(origin='parent',value=value)
    elif name in ('reservation-after-grant','reservation-before-open'):
        # Keep child STORE shape and lifetime intact; all rows stay within the
        # killed worker's original lifetime, on the wrong side of its boundary.
        target=first('CURRENT_BEFORE_CAPTURE') if name=='reservation-after-grant' else next(
            i for i,v in enumerate(events) if v['event']=='CURRENT_DIRECTORY_FORCED' and mapping[i]['origin']==profile['mode'])
        if name=='reservation-after-grant':
            target=next(i for i,v in enumerate(events) if i>tx['end'] and v['node']==tx['node'] and v['event']=='GRANT_BEFORE_RETURN')
        move(rows,mapping[target])
    elif name=='extra-local-reservation':move(copy.deepcopy(rows),rows[0])
    elif name=='unbound-reservation':
        at=locate(rows[-1])+1;shared[at:at]=[dict(origin='parent',value=dict(node='node-2',event=event)) for event in b.WRITES]
    elif name.startswith('promise-'):
        start=next(i for i,v in enumerate(events) if v['event']==b.PROMISE[0] and mapping[i]['origin']=='parent')
        node=events[start]['node'];parts=[mapping[next(i for i,v in enumerate(events) if i>=start and v['node']==node and v['event']==event)] for event in b.PROMISE]
        if name=='promise-write-missing':shared.pop(locate(parts[1]))
        elif name=='promise-force-before-write':move([parts[2]],parts[1])
        elif name=='promise-extra-field':parts[1]['value']['claimedHash']='a'*64
        elif name=='promise-unknown':parts[1]['value']['event']='PROMISE_UNKNOWN'
        elif name=='promise-duplicate':move([copy.deepcopy(parts[2])],parts[2])
        elif name=='promise-unbound':
            shared.extend(dict(origin='parent',value=dict(node=node,event=event)) for event in b.PROMISE)
        else:raise ValueError('REMOVE process unknown ballot negative')
    else:raise ValueError('REMOVE process unknown ballot negative')
    n.rewrite(root,shared)


def negative(root,profile,before,name):
    with tempfile.TemporaryDirectory(prefix='v53-remove-process-ballot-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,profile,name)
        after=p.run.h.inventory(changed)
        protected=lambda inv:{k:v for k,v in inv['files'].items() if k not in prior.r.OBSERVATIONS}
        need(protected(before)==protected(after) and before['directories']==after['directories'],
             'REMOVE process ballot negative changed physical or wire inputs')
        original,_=prior.n.observations(root,profile);altered,_=prior.n.observations(changed,profile)
        need([v for v in original if not relevant(v)]==[v for v in altered if not relevant(v)],
             'REMOVE process ballot negative changed other observations')
        # Promise callbacks overlap the network activation reader. A missing
        # promise must fail here for its declared reason, not in that earlier
        # reader. Retirement/continuous retention still replay on every copy.
        prior.replay(changed,profile)
        try:replay(changed,profile)
        except ValueError as error:need(str(error)==NEGATIVES[name],'REMOVE process unrelated ballot negative: '+name+': '+str(error))
        else:raise ValueError('REMOVE process ballot mutation accepted: '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],retirementReplay='PASS',physicalWireAndOtherObservationsUnchanged=True)


def qualify(root,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'REMOVE process ballot replay workers')
    root=Path(root);original=validate(root);before=p.run.h.inventory(root);profile=p.profile_at(root);results=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(negative,root,profile,before,name):name for name in NEGATIVES}
        for task in as_completed(tasks):
            name=tasks[task]
            try:result=task.result()
            except Exception as error:result=dict(case=name,status='FAIL',type=type(error).__name__,failure=str(error))
            results.append(result);print(json.dumps(dict(result,completed=len(results),total=len(tasks))),file=sys.stderr,flush=True)
    need(p.run.h.inventory(root)==before,'REMOVE process ballot negatives changed original')
    need(all(v['status']=='REJECTED' for v in results),'REMOVE process ballot negative matrix failed')
    return dict(original=original,negatives=sorted(results,key=lambda v:v['case']),
        negativePrecondition='full original through retirement; mutated continuous retention/retirement; unchanged physical, wire and non-ballot observations',
        mutatedFullPrerequisiteReplayed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    print(json.dumps(qualify(args.root,workers=args.workers) if args.qualify else validate(args.root),sort_keys=True))
