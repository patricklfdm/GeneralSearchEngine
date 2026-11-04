"""Complete observed carried INTENT/FINAL attempts and durable network replies.

The independent original physical/lifecycle reduction must pass first. Complete
export capability/maintenance composition and process faults are separate gates.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import carried_transition_evidence as physical
from . import remove_network_evidence as network

need=network.need
NEGATIVES=network.NEGATIVES


def history(root,kind):
    first,_,_=physical.shape(kind)
    return network.History(root,'4-REMOVE',indices=tuple(range(first,8)))


def replay(root,kind):
    return network.replay(root,history(root,kind))


def validate(root,kind):
    physical.shape(kind);root=Path(root);before=network.collection.inventory(root)
    original=physical.validate(root,kind);result=replay(root,kind)
    need(network.collection.inventory(root)==before,'carried transition network original changed')
    return dict(status='PARTIAL',kind=kind,physical=original,network=result,
                observedAttemptsQualified=True,durableActivationAndSlotACKsQualified=True,
                completeExportAuthorityQualified=False,maintenanceCompositionQualified=False,
                processDeathQualified=False,publicReady=False,phase3Complete=False)


def negative(root,kind,before,name):
    reason=NEGATIVES[name]
    observations={'events.json','wire.json','failures.json'}
    protected={k:v for k,v in before['files'].items() if k not in observations}
    with tempfile.TemporaryDirectory(prefix='v53-carried-network-negative-') as temp:
        copied=Path(temp)/'raw';shutil.copytree(root,copied);network.mutate(copied,name)
        after=network.collection.inventory(copied)
        need({k:v for k,v in after['files'].items() if k not in observations}==protected and
             after['directories']==before['directories'],'carried transition network negative changed physical input')
        try:replay(copied,kind)
        except ValueError as error:need(str(error)==reason,'carried transition unrelated network negative: '+name+': '+str(error))
        else:raise ValueError('carried transition network mutation accepted: '+name)
    return dict(case=name,status='REJECTED',reason=reason)


def qualify(root,kind,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'carried transition network replay workers')
    root=Path(root);original=validate(root,kind);before=network.collection.inventory(root);results={}
    def record(row):
        results[row['case']]=row
        print(json.dumps(dict(kind=kind,case=row['case'],completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    if workers==1:
        for name in NEGATIVES:record(negative(root,kind,before,name))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs=[pool.submit(negative,root,kind,before,name) for name in NEGATIVES]
            for job in as_completed(jobs):record(job.result())
    need(network.collection.inventory(root)==before,'carried transition network original changed')
    return dict(original=original,negatives=[results[name] for name in NEGATIVES])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--kind',choices=physical.KINDS,required=True)
    p.add_argument('--qualify',action='store_true');p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    need(a.qualify or a.workers==1,'carried transition workers require qualification')
    print(json.dumps(qualify(a.root,a.kind,workers=a.workers) if a.qualify else validate(a.root,a.kind),sort_keys=True))
