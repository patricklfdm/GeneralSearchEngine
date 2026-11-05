"""Continuous peer/learner/future/ballot replay for the required-four original.

Every chain starts at independently derived bootstrap bytes and reaches the
original cold files. Joint/FINAL snapshots never reset its revision or allocator.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import required_four_maintenance as maintenance
from . import joining_profile_peer_evidence as profile_peer
from . import joining_same_view_learner as learner
from . import joining_same_view_future as future
from . import joining_profile_ballot_evidence as ballot_profile

peer=profile_peer.peer
need,collection=maintenance.need,maintenance.collection


class PeerReplay(peer.Replay,maintenance.Replay):
    expected_write_counts=None

    def __init__(self,root,*,base=None):
        base=maintenance.Replay(root) if base is None else base
        self.__dict__.update(vars(base))
        # Only immutable original observations are shared across the four readers.
        self.direct_nodes=set();self.pinned_floors=set();self.initialize_chain()

    acquired=maintenance.Replay.acquired
    direct=maintenance.Replay.direct
    governing=maintenance.Replay.governing
    floors=maintenance.Replay.floors
    floor=profile_peer.Replay.floor


class LearnerReplay(learner.Replay):
    def __init__(self,root,*,base=None):
        super().__init__(root,base=maintenance.Replay(root) if base is None else base)


class FutureReplay(future.Replay):
    def __init__(self,root,*,base=None):
        super().__init__(root,base=maintenance.Replay(root) if base is None else base)


class BallotReplay(ballot_profile.ballot.Replay):
    def __init__(self,root,*,base=None):
        super().__init__(root,base=maintenance.Replay(root) if base is None else base)


READERS={'peers':PeerReplay,'learner':LearnerReplay,'future':FutureReplay,'ballot':BallotReplay}
MODULES={'peers':peer,'learner':learner,'future':future,'ballot':ballot_profile}
PEER_OMISSIONS={
    'force-missing':{'REMOVED_PEER_FORCE'},
    'candidate-parent-missing':{'REMOVED_PEER_CANDIDATE_PARENT'},
    'incomplete-write':{'REMOVED_PEER_FINAL_PARENT'},
    'selected-without-completion':{'REMOVED_PEER_COMPLETION'},
    'reseal-parent-missing':{'REMOVED_PEER_RESEAL_PARENT'},
    'maintenance-omit-write':{'REMOVED_'+point for point in peer.WRITES},
}


def replay(root,progress=None):
    base=maintenance.Replay(root);results={};owners=set((*base.model.old,base.model.joining))
    for name,reader in READERS.items():
        instance=reader(root,base=base);result=instance.run()
        key='finalCounters' if name=='ballot' else 'finalRevisions'
        need(set(result[key])==owners,'required-four complete ledger owners: '+name)
        if name=='learner':result['joiningWrites']=sum(v['node']==base.model.joining for v in instance.steps)
        if name=='ballot':result['adoptionFences']=instance.adoption_fences
        results[name]=result
        if progress:progress(dict(stage=name,status='PASS'))
    return results


def validate(directory,progress=None):
    root=Path(directory);before=collection.inventory(root)
    original=maintenance.validate(root);ledgers=replay(root,progress)
    need(collection.inventory(root)==before,'required-four ledgers original changed')
    return dict(status='PASS',scope='required-four-original-continuous-ledgers',profile=maintenance.exports.PROFILE,
                precondition=original,ledgers=ledgers,peerLedgerCompositionQualified=True,
                learnerLedgerCompositionQualified=True,futureLedgerCompositionQualified=True,ballotCompositionQualified=True,
                wholeRuntimeResourcesQualified=False,completePhysicalQualified=False,processDeathQualified=False,
                finalSourceCohortQualified=False,phase3Complete=False)


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
    return pending,absent


def relevant(stage,row):
    if stage=='peers':return row['event'].startswith('RETENTION_') or row['event']=='SELECTED_RETENTION_COMPLETED'
    if stage=='learner':return learner.relevant(row['event'])
    if stage=='future':return row['event'].startswith('FUTURE_RETENTION_')
    return ballot_profile.ballot.relevant(row) or row['event'] in ballot_profile.ballot.ADOPTION


def mutate(root,stage,name):
    need(stage in READERS and name in MODULES[stage].NEGATIVES,'required-four declared ledger mutation')
    reader=READERS[stage](root);MODULES[stage].mutate(root,name,reader=reader)
    if stage=='peers' and name in PEER_OMISSIONS:
        # Legacy peer drivers mark removals. Keep other observations protected:
        # convert only the known exact removal markers to actual omissions.
        events=collection.read_json(Path(root),'events.json',collection.EVENT_BYTES);markers=PEER_OMISSIONS[name]
        found=[row['event'] for row in events if row['event'] in markers]
        need(set(found)==markers and len(found)==len(markers),'required-four exact peer omissions')
        (Path(root)/'events.json').write_bytes(peer.f.canonical([row for row in events if row['event'] not in markers]))


def negative(root,before,case):
    stage,name,reason=case
    with tempfile.TemporaryDirectory(prefix='v53-required-four-ledger-negative-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed)
        try:mutate(changed,stage,name)
        except (StopIteration,IndexError) as error:raise ValueError('required-four missing ledger mutation target: '+stage+'/'+name) from error
        after=collection.inventory(changed);protected=lambda value:{k:v for k,v in value['files'].items() if k!='events.json'}
        need(after!=before and protected(after)==protected(before) and after['directories']==before['directories'],
             'required-four ledger negative changed protected inputs')
        other=lambda path:[v for v in collection.read_json(Path(path),'events.json',collection.EVENT_BYTES) if not relevant(stage,v)]
        need(other(root)==other(changed),'required-four ledger negative changed other observations')
        try:READERS[stage](changed).run()
        except ValueError as error:need(str(error)==reason,'required-four unrelated ledger negative: '+stage+'/'+name+': '+str(error))
        else:raise ValueError('required-four ledger mutation accepted: '+stage+'/'+name)
    return dict(stage=stage,case=name,status='REJECTED',reason=reason,mutationScope='designated-ledger-callbacks-only')


def qualify(directory,*,workers=1,progress=None):
    need(type(workers) is int and 1<=workers<=4,'required-four ledger replay workers')
    root=Path(directory);before=collection.inventory(root);original=validate(root,progress);pending,results=cases(original)
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
    need(collection.inventory(root)==before,'required-four ledger qualification changed original')
    need(all(v['status'] in ('REJECTED','NOT_APPLICABLE') for v in results),'required-four ledger negative matrix failed')
    return dict(original=original,negatives=sorted(results,key=lambda v:(v['stage'],v['case'])),
                rejected=sum(v['status']=='REJECTED' for v in results),notApplicable=sum(v['status']=='NOT_APPLICABLE' for v in results),
                mutatedPrerequisiteReplayed=False,
                negativePrecondition='whole unmodified original; unchanged files, wire and non-designated observations')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--qualify',action='store_true')
    p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    progress=lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(a.root,workers=a.workers,progress=progress) if a.qualify else validate(a.root,progress),sort_keys=True))
