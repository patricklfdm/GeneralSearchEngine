"""Continuous carried INTENT/FINAL peer and future-retention ledger replay.

Derive the admitted prefix once. Later snapshots are comparisons, never new
ledger seeds. Export/floor authority of the complete original is mandatory.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import carried_transition_exports as exports
from . import remove_retention_evidence as shared

r=shared;e=exports;n=e.n;c=e.c;f=e.f;need=e.need;sha=e.sha
NEGATIVES=r.NEGATIVES


class PeerReplay(r.PeerReplay):
    def __init__(self,root,kind):
        super().__init__(root,kind,base=e.Replay(root,kind))

    def initial_states(self):
        # FINAL's admitted preparation already contains a peer-ledger reconcile.
        # Derive that revision from bootstrap/control history, not its snapshot.
        walk,_,_=e.network.physical.prelude(self.root,self.kind)
        return walk.group


class FutureReplay(r.FutureReplay):
    def __init__(self,root,kind):
        super().__init__(root,kind,base=e.Replay(root,kind))


def replay(root,kind):
    return dict(status='PARTIAL',kind=kind,peers=PeerReplay(root,kind).run(),future=FutureReplay(root,kind).run(),
        retentionRevisionCompositionQualified=True,completeRetirementTransactions=False,
        processDeathQualified=False,publicReady=False,phase3Complete=False)


def validate(root,kind):
    e.network.physical.shape(kind);root=Path(root);before=n.collection.inventory(root)
    original=e.validate(root,kind);result=replay(root,kind)
    need(n.collection.inventory(root)==before,'carried retention original changed')
    return dict(result,precondition=original)


def mutate(root,kind,stage,name):
    root=Path(root)
    if stage=='peers':
        if name in r.peer.NEGATIVES:r.peer.mutate(root,name,reader=PeerReplay(root,kind))
        else:
            reader=PeerReplay(root,kind);reader.run();events=reader.events
            if name=='completion-forged-scope':next(v for v in events if v['event']=='SELECTED_RETENTION_COMPLETED')['scope']='foreign-owner'
            elif name=='write-forged-field':next(v for v in events if v['event']==r.peer.WRITES[0])['revision']=99
            else:raise ValueError('carried retention unknown peer mutation')
            (root/'events.json').write_bytes(f.canonical(events))
        events=n.collection.read_json(root,'events.json',n.collection.EVENT_BYTES)
        (root/'events.json').write_bytes(f.canonical([v for v in events if not v['event'].startswith('REMOVED_')]))
    else:r.future.mutate(root,name,reader=FutureReplay(root,kind))


def negative(root,kind,before,stage,name):
    reason=NEGATIVES[stage][name]
    with tempfile.TemporaryDirectory(prefix='v53-carried-retention-negative-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,kind,stage,name)
        after=n.collection.inventory(changed);protected=lambda v:{k:h for k,h in v['files'].items() if k!='events.json'}
        need(protected(before)==protected(after) and before['directories']==after['directories'],'carried retention negative changed original files')
        read=lambda path:n.collection.read_json(Path(path),'events.json',n.collection.EVENT_BYTES)
        need(r.unrelated(read(root),stage)==r.unrelated(read(changed),stage),'carried retention negative changed other observations')
        try:(PeerReplay if stage=='peers' else FutureReplay)(changed,kind).run()
        except ValueError as error:need(str(error)==reason,'carried unrelated retention negative: '+stage+': '+name+': '+str(error))
        else:raise ValueError('carried retention mutation accepted: '+stage+': '+name)
    return dict(stage=stage,case=name,status='REJECTED',reason=reason,originalFilesAndOtherObservationsUnchanged=True)


def qualify(root,kind,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'carried retention replay workers')
    root=Path(root);original=validate(root,kind);before=n.collection.inventory(root);results={}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs=[pool.submit(negative,root,kind,before,stage,name) for stage,cases in NEGATIVES.items() for name in cases]
        for task in as_completed(jobs):
            row=task.result();results[row['stage'],row['case']]=row
            print(json.dumps(dict(kind=kind,stage=row['stage'],case=row['case'],completed=len(results),total=len(jobs))),file=sys.stderr,flush=True)
    need(n.collection.inventory(root)==before,'carried retention original changed')
    return dict(original=original,negatives=[results[key] for key in sorted(results)],
        negativePrecondition='full-original-physical-network-export-floor; unchanged files, wire and non-target observations',
        mutatedPrerequisiteReplayed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--kind',required=True,choices=e.network.physical.KINDS)
    p.add_argument('--qualify',action='store_true');p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    need(a.qualify or a.workers==1,'carried retention workers require qualification')
    print(json.dumps(qualify(a.root,a.kind,workers=a.workers) if a.qualify else validate(a.root,a.kind),sort_keys=True))
