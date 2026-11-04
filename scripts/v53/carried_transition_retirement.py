"""Carried transition retirement callbacks derived from exact owned bytes.

No transient file capture or process-death claim is made. The complete original
physical/network/export/floor/ledger reduction is a mandatory precondition.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import carried_transition_retention as retention
from . import remove_retirement_evidence as shared

r=retention;s=shared;n=r.n;c=r.c;f=r.f;need=r.need;sha=r.sha
NEGATIVES=s.NEGATIVES


def current_successor(files,parts,payload):
    """Derive the forced reaccept container; snapshots never supply its vote."""
    _,members,packet=c.current(files);chosen=f.decode(parts['SELECTED'],'records','SELECTED')
    entry=f.decode(parts['ENTRY'],'records','ENTRY');accept=f.decode(parts['ACCEPT'],'records','ACCEPT')
    need(members['selected.gsr']==parts['SELECTED'] and chosen['nextEntry']==sha(parts['ENTRY']) and
         entry['index']==packet['capsule']['cut']['index']+1 and sha(payload)==entry['payload'] and
         accept==dict(root=chosen['root'],authority=chosen['view'],ballot=chosen['ballot'],index=entry['index'],entry=sha(parts['ENTRY'])),
         'carried retirement exact current successor')
    tail=f.decode(members['owned-tail.gsr'],'records','ACCEPT')
    need(dict(tail,ballot=accept['ballot'])==accept and s.grants.order(tail['ballot'])<=s.grants.order(accept['ballot']) and
         packet['objects'].get(sha(parts['ENTRY']))==parts['ENTRY'] and packet['objects'].get(sha(payload))==payload,
         'carried retirement unchanged owned tail')
    return r.e.network.physical.e.container([files['selector.gsr'],members['promise.gsr'],parts['SELECTED'],parts['ENTRY'],parts['ACCEPT']],payload)


def generation_plan(files,node,copies,pending=None):
    # First maintenance runs after an exact current reaccept. Its pending vote
    # is unrelated to the inactive-directory transaction and remains byte exact
    # in every derived transient state. The force boundary is checked by plans().
    need(not any(k=='applied-end' or k.startswith('applied-end/') for k in files),'carried retirement before application')
    projected=dict(files)
    if pending is not None:
        need(files['pending.accept']==pending and pending!=c.EMPTY,'carried retirement exact pending projection')
        projected['pending.accept']=c.EMPTY
    after,steps,details=s.generation_plan(projected,node,copies)
    if pending is not None:
        after['pending.accept']=pending
        steps=[(point,dict(state,**{'pending.accept':s.images.old.entry(pending)})) for point,state in steps]
        need(steps[-1][1]==s.physical(after),'carried retirement preserved current successor')
    return after,steps,details


class Replay(s.Replay,r.PeerReplay):
    def __init__(self,root,kind):
        super().__init__(root,kind);self.profile=kind

    def plans(self,files,node,copies,available,row):
        pending=None
        if row['own']['path']==f'installed-1/{node}':
            points=self.phases[1,node]
            need(points['ACCEPT_BEFORE_RETURN']<row['start']<points['PROOF_BEFORE_RETURN'],
                 'carried retirement floor after forced reaccept')
            parts=self.history.phases[0];index=f.decode(parts['ENTRY'],'records','ENTRY')['index']
            pending=current_successor(files,parts,(self.root/f'native-payload-{index}.bin').read_bytes())
            files=dict(files,**{'pending.accept':pending})
        after,steps,details=generation_plan(files,node,copies,pending)
        # While the new vote is pending, its original frozen sources stay owned.
        # Later stable floors can retire covered old accepted tails.
        if pending is not None:decisions=[]
        else:after,decisions=s.source_plans(after,node,available,allow_published_tail=True)
        return after,steps,details,decisions


def replay(root,kind):
    result=Replay(root,kind).run()
    return dict(result,kind=kind,publicReady=False)


def validate(root,kind):
    r.e.network.physical.shape(kind);root=Path(root);before=n.collection.inventory(root)
    original=r.validate(root,kind);result=replay(root,kind)
    need(n.collection.inventory(root)==before,'carried retirement original changed')
    return dict(result,precondition=original)


def negative(root,kind,before,name):
    with tempfile.TemporaryDirectory(prefix='v53-carried-retirement-negative-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed);s.mutate(changed,name);after=n.collection.inventory(changed)
        protected=lambda v:{k:h for k,h in v['files'].items() if k!='events.json'}
        need(protected(before)==protected(after) and before['directories']==after['directories'],'carried retirement negative changed original files')
        other=lambda path:[v for v in n.collection.read_json(Path(path),'events.json',n.collection.EVENT_BYTES) if not v['event'].startswith(s.PREFIXES)]
        need(other(root)==other(changed),'carried retirement negative changed other observations')
        r.replay(changed,kind)
        try:replay(changed,kind)
        except ValueError as error:need(str(error)==NEGATIVES[name],'carried unrelated retirement negative: '+name+': '+str(error))
        else:raise ValueError('carried retirement mutation accepted: '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],retentionReplay='PASS',originalFilesAndOtherObservationsUnchanged=True)


def qualify(root,kind,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'carried retirement replay workers')
    root=Path(root);original=validate(root,kind);before=n.collection.inventory(root);results={}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs=[pool.submit(negative,root,kind,before,name) for name in NEGATIVES]
        for task in as_completed(jobs):
            row=task.result();results[row['case']]=row
            print(json.dumps(dict(kind=kind,case=row['case'],completed=len(results),total=len(jobs))),file=sys.stderr,flush=True)
    need(n.collection.inventory(root)==before,'carried retirement original changed')
    return dict(original=original,negatives=[results[name] for name in sorted(results)],
        negativePrecondition='full-original-physical-network-export-floor-retention; mutated retention replay; unchanged files and other events',
        mutatedFullPrerequisiteReplayed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--kind',required=True,choices=r.e.network.physical.KINDS)
    p.add_argument('--qualify',action='store_true');p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    need(a.qualify or a.workers==1,'carried retirement workers require qualification')
    print(json.dumps(qualify(a.root,a.kind,workers=a.workers) if a.qualify else validate(a.root,a.kind),sort_keys=True))
