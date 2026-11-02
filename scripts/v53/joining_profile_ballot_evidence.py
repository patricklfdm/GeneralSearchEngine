"""Actual profile allocator, grant and adopted membership-promise composition."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_profile_ledger_evidence as prior
from . import joining_same_view_ballot as ballot
from .joining_profile_evidence import PROFILES,topology

need,collection=prior.need,prior.collection
EXTRA={'adoption-promise-missing':'joining ballot exact promise force order',
       'adoption-fence-missing':'joining ballot exact adoption boundary order'}
NEGATIVES=dict(ballot.NEGATIVES,**EXTRA)


class Replay(ballot.Replay):
    def __init__(self,root,profile):super().__init__(root,base=prior.peer.maintenance.Replay(root,profile))


def validate(root,profile):
    topology(profile);root=Path(root);before=collection.inventory(root);original=prior.validate(root,profile)
    reader=Replay(root,profile);result=reader.run()
    need(collection.inventory(root)==before,'joining profile ballot original changed')
    return dict(status='PARTIAL',scope='profile-original-continuous-ballot',profile=profile,precondition=original,
                ballot=result,adoptionFences=reader.adoption_fences,ballotCompositionQualified=True,
                allMembershipProfilesQualified=False,currentSourceNativeCohortQualified=False,processDeathQualified=False,phase3Complete=False)


def mutate(root,name,reader):
    if name not in EXTRA:return ballot.mutate(root,name,reader=reader)
    reader.run();events=reader.events
    if name=='adoption-promise-missing':
        original=next(v for v in reader.adoption_fences if v['promiseAppended'])
        at=next(i for i in range(original['start']+1,original['end']) if events[i].get('node')==original['node'] and events[i]['event']=='PROMISE_FORCED')
    else:
        original=reader.adoption_fences[0]
        at=next(i for i in range(original['start']+1,original['end']) if events[i].get('node')==original['node'] and events[i]['event']=='ADOPTION_INSTALL_FENCED')
    del events[at];(Path(root)/'events.json').write_bytes(ballot.f.canonical(events))


def negative(root,before,profile,name):
    with tempfile.TemporaryDirectory(prefix='v53-profile-ballot-negative-') as temp:
        copied=Path(temp)/'raw';shutil.copytree(root,copied)
        try:mutate(copied,name,Replay(copied,profile))
        except (StopIteration,IndexError) as error:raise ValueError('joining profile ballot missing negative target: '+name) from error
        after=collection.inventory(copied);protected=lambda value:{k:v for k,v in value['files'].items() if k!='events.json'}
        need(protected(before)==protected(after) and before['directories']==after['directories'],'joining profile ballot negative changed original files')
        relevant=lambda row:ballot.relevant(row) or row['event'] in ballot.ADOPTION
        other=lambda path:[v for v in collection.read_json(Path(path),'events.json',collection.EVENT_BYTES) if not relevant(v)]
        need(other(root)==other(copied),'joining profile ballot negative changed other observations')
        try:Replay(copied,profile).run()
        except ValueError as error:need(str(error)==NEGATIVES[name],'joining profile unrelated ballot negative: '+name+': '+str(error))
        else:raise ValueError('joining profile ballot mutation accepted: '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],mutationScope='allocator-promise-and-adoption-boundaries')


def qualify(root,profile,*,workers=1,progress=None):
    need(type(workers) is int and 1<=workers<=4,'joining profile ballot replay workers')
    root=Path(root);original=validate(root,profile);before=collection.inventory(root);cases=[];results=[]
    for name in NEGATIVES:
        reason=None
        if name=='adoption-fence-missing' and not original['adoptionFences']:reason='no original adoption transaction'
        if name=='adoption-promise-missing' and not any(v['promiseAppended'] for v in original['adoptionFences']):reason='no original adoption promise append'
        if reason:results.append(dict(case=name,status='NOT_APPLICABLE',reason=reason))
        else:cases.append(name)
    if progress:progress(dict(stage='original',status='PASS',negativeCases=len(cases),notApplicable=len(results)))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(negative,root,before,profile,name):name for name in cases}
        for task in as_completed(tasks):
            try:result=task.result()
            except Exception as error:result=dict(case=tasks[task],status='FAIL',failure=str(error),type=type(error).__name__)
            results.append(result)
            if progress:progress(dict(result,completed=len(results),total=len(NEGATIVES)))
    need(collection.inventory(root)==before,'joining profile ballot qualification changed original')
    need(all(v['status'] in ('REJECTED','NOT_APPLICABLE') for v in results),'joining profile ballot negative matrix failed')
    return dict(original=original,negatives=sorted(results,key=lambda v:v['case']),
                rejected=sum(v['status']=='REJECTED' for v in results),notApplicable=sum(v['status']=='NOT_APPLICABLE' for v in results),
                mutatedPrerequisiteReplayed=False,negativePrecondition='full original retention chain; unchanged files, wire and other observations')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root')
    parser.add_argument('--profile',required=True,choices=PROFILES);parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    result=qualify(args.root,args.profile,workers=args.workers,progress=lambda v:print(json.dumps(v),file=sys.stderr,flush=True)) if args.qualify else validate(args.root,args.profile)
    print(json.dumps(result,sort_keys=True))
