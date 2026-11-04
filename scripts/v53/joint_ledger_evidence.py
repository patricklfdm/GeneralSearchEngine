"""Continuous original peer, learner and future ledgers across joint-floor recovery.

Cold reopen compares the already-derived chain to the original reopened files;
it never initializes a ledger from those observations.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import joint_history_evidence as history
from . import joining_profile_peer_evidence as profile
from . import joining_same_view_learner as learner
from . import joining_same_view_future as future
from . import joining_profile_ballot_evidence as ballot_profile

peer=profile.peer
f,disk,need,h,sha=history.f,history.disk,history.need,history.h,history.sha
NODE,SCOPE=history.recovered.NODE,history.recovered.SCOPE


def context(root):
    root=Path(root);events=history.p.read(root/'events.json')
    return history.control.Replay(root,'5-REPLACE',old_owner_lifetimes=history.lifetimes(events))


class ColdOwner:
    def cold_boundary(self):
        if not hasattr(self,'_cold_boundary'):self._cold_boundary=history.recovered.boundary(self.events)
        return self._cold_boundary

    def lifetimes(self):
        return [*super().lifetimes(),(NODE,SCOPE)]

    def write_scope(self,node,at):
        start,_=self.cold_boundary()
        return SCOPE if node==NODE and at>=start else super().write_scope(node,at)

    def reopen_files(self,node,at):
        start,_=self.cold_boundary()
        if node==NODE and at>=start:
            return disk.inventory(self.root/'joint-floor-recovery/after-reopen')
        return super().reopen_files(node,at)


class PeerReplay(ColdOwner,peer.Replay,history.Replay):
    expected_write_counts=None

    def __init__(self,root,*,base=None):
        history.Replay.__init__(self,context(root) if base is None else base)
        self.initialize_chain()

    acquired=history.Replay.acquired
    direct=history.Replay.direct
    governing=history.Replay.governing
    floors=history.Replay.floors
    floor=profile.Replay.floor


class LearnerReplay(ColdOwner,learner.Replay):
    def __init__(self,root,*,base=None):
        base=context(root) if base is None else base
        super().__init__(root,base=base,old_owner_lifetimes=history.lifetimes(base.events))


class FutureReplay(ColdOwner,future.Replay):
    def __init__(self,root,*,base=None):
        base=context(root) if base is None else base
        super().__init__(root,base=base,old_owner_lifetimes=history.lifetimes(base.events))


class BallotReplay(ballot_profile.ballot.Replay):
    def __init__(self,root,*,base=None):
        base=context(root) if base is None else base
        super().__init__(root,base=base,old_owner_lifetimes=history.lifetimes(base.events))

    def reopen_actions(self):
        start,end=history.recovered.boundary(self.events)
        need(not any(row.get('node')==NODE and row['event'].startswith('ALLOCATOR_') for row in self.events[start:end+1]),
             'joint ledger allocation during floor recovery')
        # Whole-original replay binds after-reopen to the unchanged pre-close
        # state. Compare it before another reservation; never seed from it.
        return [(start,'original',(NODE,'joint-floor-recovery/after-reopen','joint-floor-reopen'))]


READERS={'peers':PeerReplay,'learner':LearnerReplay,'future':FutureReplay,'ballot':BallotReplay}


def replay(root,progress=None):
    base=context(root);results={}
    for name,reader in READERS.items():
        instance=reader(root,base=base);results[name]=instance.run()
        if name=='learner':results[name]['joiningWrites']=sum(v['node']==instance.model.joining for v in instance.steps)
        if name=='ballot':results[name]['adoptionFences']=instance.adoption_fences
        if progress:progress(dict(stage=name,status='PASS'))
    return results


def validate(root,progress=None):
    root=Path(root);before=h.inventory(root);original=history.validate(root,progress)
    ledgers=replay(root,progress)
    need(h.inventory(root)==before,'joint ledger original changed')
    return dict(status='PASS',scope='complete-interrupted-history-continuous-ledgers',profile='5-REPLACE',
        precondition=original,ledgers=ledgers,peerLedgerCompositionQualified=True,
        learnerLedgerCompositionQualified=True,futureLedgerCompositionQualified=True,
        ballotCompositionQualified=True,processDeathQualified=False,phase3Complete=False)


MODULES={'peers':peer,'learner':learner,'future':future,'ballot':ballot_profile}
FILES={'peers':peer.FILE,'learner':learner.FILE,'future':future.future.FILE,'ballot':'allocator.gsr'}
EXTRA={
    ('peers','cold-write-owner'):'joining peer original write owner',
    ('learner','cold-write-owner'):'joining learner original event owner',
    ('future','cold-write-owner'):'joining future original event owner',
    ('ballot','cold-promise-owner'):'joining ballot exact promise force order',
    ('peers','cold-reseal-parent-missing'):'joining peer exact open reseal count',
    ('learner','cold-reseal-parent-missing'):'joining learner exact reopen count',
    ('future','cold-reseal-parent-missing'):'joining future exact reopen count',
    ('peers','cold-reseal-order'):'joining peer open reseal force order',
    ('learner','cold-reseal-order'):'joining learner reopen force order',
    ('future','cold-reseal-order'):'joining future reopen force order',
    ('peers','cold-ledger-reset'):'joining peer exact original ledger: open-reseal: '+NODE,
    ('learner','cold-ledger-reset'):'joining learner exact continuous ledger: reopen: '+NODE,
    ('future','cold-ledger-reset'):'joining future exact continuous ledger: reopen: '+NODE,
    ('ballot','cold-ledger-reset'):'joining ballot exact continuous allocator: joint-floor-reopen: '+NODE,
    ('peers','cold-forged-write-field'):'joining peer write event shape',
}

PEER_REMOVALS={
    'force-missing':{'REMOVED_PEER_FORCE'},
    'candidate-parent-missing':{'REMOVED_PEER_CANDIDATE_PARENT'},
    'incomplete-write':{'REMOVED_PEER_FINAL_PARENT'},
    'selected-without-completion':{'REMOVED_PEER_COMPLETION'},
    'reseal-parent-missing':{'REMOVED_PEER_RESEAL_PARENT'},
    'maintenance-omit-write':{'REMOVED_'+point for point in peer.WRITES},
}


def cases(original):
    pending=[];absent=[]
    for stage,module in MODULES.items():
        for name,reason in module.NEGATIVES.items():
            missing=None
            if stage=='learner' and name=='wrong-write-scope' and original['ledgers']['learner']['joiningWrites']==0:
                missing='original continuous learner chain contains no joining-owner write'
            if stage=='ballot':
                fences=original['ledgers']['ballot']['adoptionFences']
                if name=='adoption-fence-missing' and not fences:missing='no original adoption transaction'
                if name=='adoption-promise-missing' and not any(v['promiseAppended'] for v in fences):missing='no original adoption promise append'
            if missing:absent.append(dict(stage=stage,case=name,status='NOT_APPLICABLE',reason=missing))
            else:pending.append((stage,name,reason))
    pending.extend((stage,name,reason) for (stage,name),reason in EXTRA.items())
    return pending,absent


def mutate(root,stage,name):
    need(stage in READERS and (name in MODULES[stage].NEGATIVES or (stage,name) in EXTRA),'joint ledger unknown negative')
    root=Path(root)
    if (stage,name) not in EXTRA:
        reader=READERS[stage](root)
        if stage=='ballot' and name=='unbound-reservation':
            # The historical "other" is node-2, whose final lifetime is now
            # scoped. Choose an unchanged old owner so this targets an unused
            # reservation, not a preceding owner-shape rejection.
            proposer=reader.tx[0]['node']
            other=next(node for node in reader.owners if node not in (proposer,reader.model.joining,NODE))
            reader.events.extend(dict(node=other,event=point) for point in ballot_profile.ballot.WRITES)
            (root/'events.json').write_bytes(f.canonical(reader.events));return
        MODULES[stage].mutate(root,name,reader=reader)
        if stage=='peers' and name in PEER_REMOVALS:
            # Historical drivers renamed removed callbacks. Use actual omission
            # so unrelated-event protection remains byte-for-byte strict.
            events=history.p.read(root/'events.json');markers=PEER_REMOVALS[name]
            matches=[row['event'] for row in events if row['event'] in markers]
            need(set(matches)==markers and len(matches)==len(markers),'joint ledger exact peer omissions')
            (root/'events.json').write_bytes(f.canonical([row for row in events if row['event'] not in markers]))
        return
    if name=='cold-ledger-reset':
        path=root/'joint-floor-recovery/after-reopen'/FILES[stage]
        if stage=='ballot':
            value=f.decode(path.read_bytes(),'records','ALLOCATOR');value['counter']+=1
            path.write_bytes(f.encode('records','ALLOCATOR',value))
        else:path.write_bytes((root/'before-network'/NODE/FILES[stage]).read_bytes())
        return
    events=history.p.read(root/'events.json');start,released=history.recovered.boundary(events)
    if name=='cold-forged-write-field':
        row=next(v for v in events[start:] if v.get('node')==NODE and v['event']==peer.WRITES[0]);row['claimedRevision']=999
    elif name in ('cold-write-owner','cold-promise-owner'):
        points=MODULES[stage].WRITES if name=='cold-write-owner' else ballot_profile.ballot.PROMISE
        lower=released+1 if stage=='peers' else start
        first=next(i for i in range(lower,len(events)) if events[i].get('node')==NODE and events[i]['event']==points[0])
        last=next(i for i in range(first,len(events)) if events[i].get('node')==NODE and events[i]['event']==points[-1])
        for row in events[first:last+1]:
            if row.get('node')==NODE and row['event'] in points:row['scope']='foreign-owner'
    else:
        points=MODULES[stage].RESEAL
        indices=[next(i for i in range(start,len(events)) if events[i].get('node')==NODE and events[i]['event']==point) for point in points]
        if name=='cold-reseal-parent-missing':del events[indices[1]]
        else:events[indices[0]],events[indices[1]]=events[indices[1]],events[indices[0]]
    (root/'events.json').write_bytes(f.canonical(events))


def relevant(stage,row):
    if stage=='peers':return row['event'].startswith('RETENTION_') or row['event']=='SELECTED_RETENTION_COMPLETED'
    if stage=='learner':return learner.relevant(row['event'])
    if stage=='future':return row['event'].startswith('FUTURE_RETENTION_')
    return ballot_profile.ballot.relevant(row) or row['event'] in ballot_profile.ballot.ADOPTION


def negative(root,before,case):
    stage,name,reason=case
    with tempfile.TemporaryDirectory(prefix='v53-joint-ledger-negative-') as tmp:
        changed=Path(tmp)/'raw';shutil.copytree(root,changed);mutate(changed,stage,name)
        allowed='joint-floor-recovery/after-reopen/'+FILES[stage] if name=='cold-ledger-reset' else 'events.json'
        protected=lambda inv:{k:v for k,v in inv['files'].items() if k!=allowed}
        after=h.inventory(changed)
        need(after!=before and protected(after)==protected(before) and after['directories']==before['directories'],
             'joint ledger negative changed protected inputs')
        others=lambda path:[v for v in history.p.read(Path(path)/'events.json') if not relevant(stage,v)]
        need(others(root)==others(changed),'joint ledger negative changed other observations')
        try:READERS[stage](changed).run()
        except ValueError as error:need(str(error)==reason,'joint ledger unrelated rejection: '+stage+'/'+name+': '+str(error))
        else:raise ValueError('joint ledger mutation accepted: '+stage+'/'+name)
    return dict(stage=stage,case=name,status='REJECTED',reason=reason,
                mutationScope='original-reopened-ledger' if name=='cold-ledger-reset' else 'designated-ledger-callbacks')


def qualify(root,*,workers=1,progress=None):
    need(type(workers) is int and 1<=workers<=4,'joint ledger replay workers')
    root=Path(root);before=h.inventory(root);original=validate(root,progress);pending,results=cases(original)
    total=len(pending)+len(results)
    if progress:progress(dict(stage='original',status='PASS',negativeCases=len(pending),notApplicable=len(results)))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(negative,root,before,case):case for case in pending}
        for task in as_completed(tasks):
            stage,name,_=tasks[task]
            try:result=task.result()
            except Exception as error:result=dict(stage=stage,case=name,status='FAIL',failure=str(error),type=type(error).__name__)
            results.append(result)
            if progress:progress(dict(result,completed=len(results),total=total))
    need(h.inventory(root)==before,'joint ledger qualification changed original')
    need(all(v['status'] in ('REJECTED','NOT_APPLICABLE') for v in results),'joint ledger negative matrix failed')
    return dict(original=original,negatives=sorted(results,key=lambda v:(v['stage'],v['case'])),
        rejected=sum(v['status']=='REJECTED' for v in results),notApplicable=sum(v['status']=='NOT_APPLICABLE' for v in results),
        mutatedPrerequisiteReplayed=False,negativePrecondition='whole unmodified original; exact designated callback/file changes only')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--qualify',action='store_true')
    p.add_argument('--workers',type=int,default=1);args=p.parse_args()
    def progress(row):print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    result=qualify(args.root,workers=args.workers,progress=progress) if args.qualify else validate(args.root,progress)
    print(json.dumps(result,sort_keys=True))
