"""Continuous future/learner ledgers over actual ADD/REPLACE profile owners.

Physical, network, export, control, maintenance and peer replay must pass on the
unchanged original first. Negative copies alter only the designated callbacks;
their other observations, wire and physical files remain byte-for-byte intact.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_profile_peer_evidence as peer
from . import joining_same_view_future as future
from . import joining_same_view_learner as learner
from .joining_profile_evidence import PROFILES,topology

need,collection=peer.need,peer.collection


class FutureReplay(future.Replay):
    def __init__(self,root,profile):super().__init__(root,base=peer.maintenance.Replay(root,profile))


class LearnerReplay(learner.Replay):
    def __init__(self,root,profile):super().__init__(root,base=peer.maintenance.Replay(root,profile))


def validate(root,profile):
    topology(profile);root=Path(root);before=collection.inventory(root)
    original=peer.validate(root,profile)
    recorded_future=FutureReplay(root,profile).run();reader=LearnerReplay(root,profile);recorded_learner=reader.run()
    need(collection.inventory(root)==before,'joining profile ledgers original changed')
    return dict(status='PARTIAL',scope='profile-original-continuous-retention-ledgers',profile=profile,
                precondition=original,future=recorded_future,learner=recorded_learner,
                joiningLearnerWrites=sum(v['node']==reader.model.joining for v in reader.steps),
                peerLedgerCompositionQualified=True,futureLedgerCompositionQualified=True,learnerLedgerCompositionQualified=True,
                ballotCompositionQualified=False,allMembershipProfilesQualified=False,processDeathQualified=False,phase3Complete=False)


def negative(root,before,profile,stage,name):
    need(stage in ('future','learner'),'joining profile ledger stage')
    module,reader=(future,FutureReplay) if stage=='future' else (learner,LearnerReplay)
    need(name in module.NEGATIVES,'joining profile ledger negative name')
    relevant=(lambda event:event.startswith('FUTURE_RETENTION_')) if stage=='future' else learner.relevant
    with tempfile.TemporaryDirectory(prefix='v53-profile-ledger-negative-') as temp:
        copied=Path(temp)/'raw';shutil.copytree(root,copied)
        try:module.mutate(copied,name,reader=reader(copied,profile))
        except StopIteration as error:raise ValueError('joining profile ledger missing negative target: '+stage+': '+name) from error
        after=collection.inventory(copied);protected=lambda value:{k:v for k,v in value['files'].items() if k!='events.json'}
        need(protected(before)==protected(after) and before['directories']==after['directories'],
             'joining profile ledger negative changed original files')
        other=lambda path:[v for v in collection.read_json(Path(path),'events.json',collection.EVENT_BYTES) if not relevant(v['event'])]
        need(other(root)==other(copied),'joining profile ledger negative changed other observations')
        try:reader(copied,profile).run()
        except ValueError as error:need(str(error)==module.NEGATIVES[name],'joining profile unrelated ledger negative: '+stage+': '+name+': '+str(error))
        else:raise ValueError('joining profile ledger mutation accepted: '+stage+': '+name)
    return dict(stage=stage,case=name,status='REJECTED',reason=module.NEGATIVES[name],mutationScope=stage+'-callbacks-only')


def qualify(root,profile,*,workers=1,progress=None):
    need(type(workers) is int and 1<=workers<=4,'joining profile ledger replay workers')
    root=Path(root);original=validate(root,profile);before=collection.inventory(root);cases=[];results=[]
    for stage,module in (('future',future),('learner',learner)):
        for name in module.NEGATIVES:
            if stage=='learner' and name=='wrong-write-scope' and original['joiningLearnerWrites']==0:
                results.append(dict(stage=stage,case=name,status='NOT_APPLICABLE',
                    reason='original continuous learner chain contains no joining-owner write'))
            else:cases.append((stage,name))
    if progress:progress(dict(stage='original',status='PASS',negativeCases=len(cases),notApplicable=len(results)))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(negative,root,before,profile,stage,name):(stage,name) for stage,name in cases}
        for task in as_completed(tasks):
            stage,name=tasks[task]
            try:result=task.result()
            except Exception as error:result=dict(stage=stage,case=name,status='FAIL',failure=str(error),type=type(error).__name__)
            results.append(result)
            if progress:progress(dict(result,completed=len(results),total=len(cases)+sum(v['status']=='NOT_APPLICABLE' for v in results)))
    need(collection.inventory(root)==before,'joining profile ledger qualification changed original')
    need(all(v['status'] in ('REJECTED','NOT_APPLICABLE') for v in results),'joining profile ledger negative matrix failed')
    return dict(original=original,negatives=sorted(results,key=lambda v:(v['stage'],v['case'])),
                rejected=sum(v['status']=='REJECTED' for v in results),notApplicable=sum(v['status']=='NOT_APPLICABLE' for v in results),
                negativePrecondition='full original peer chain; unchanged files, wire and non-designated observations',
                mutatedPrerequisiteReplayed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root')
    parser.add_argument('--profile',required=True,choices=PROFILES);parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    result=qualify(args.root,args.profile,workers=args.workers,progress=lambda v:print(json.dumps(v),file=sys.stderr,flush=True)) if args.qualify else validate(args.root,args.profile)
    print(json.dumps(result,sort_keys=True))
