"""Original storage replay for a native election wait closed before any work.

The successful discovery/barrier/DATA history uses round_driver_evidence with
--discovery unchanged. Neither reader claims an election timer grants authority.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import round_driver_evidence as r
n=r.d
b,c,e,f,need=n.b,n.c,n.e,n.f,n.need
OPEN=('CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED')
ACCEPT=('ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED')
REOPEN=(*OPEN,'RETENTION_RECOVERY_ACTIVE_FORCED','RETENTION_RECOVERY_PARENT_FORCED',
        'FUTURE_RETENTION_RECOVERY_FORCED','FUTURE_RETENTION_RECOVERY_PARENT_FORCED',*ACCEPT)
INITIAL=(*OPEN,*ACCEPT,*(prefix+suffix for prefix in ('RETENTION_','FUTURE_RETENTION_')
    for suffix in ('BEFORE_WRITE','PREFIX_WRITTEN','WRITTEN','FORCED','CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED')))


def lifecycle(calls,events,nodes):
    need(calls==[dict(node=node,operation='initialize-retention',events=list(INITIAL)) for node in sorted(nodes)],
         'closed election wait initialization')
    # Opening the original owner reseals its existing files before the wait.
    # Accept exactly that lifecycle, never arbitrary or additional force events.
    need(events==[dict(node=node,event=event) for node in sorted(nodes) for event in REOPEN],
         'closed election wait exact reopen only')


def validate(root):
    root=Path(root)
    # Same regular-file and aggregate bounds as the other native readers.
    from .discovered_selection_evidence import inventory
    inventory(root)
    b.selection.layout(root,{'initial','original-plan.gsbp','original-application.image','before-network','after-close',
        'calls.json','events.json','wire.json','failures.json'},'closed election wait')
    group=n.s.initialize(b.original(root,3,False))
    group={node:dict(files,**{n.future.FILE:n.future.frame(n.future.initial(files),{})}) for node,files in group.items()}
    b.match(root,'before-network',group);b.match(root,'after-close',group)
    lifecycle(n.read(root/'calls.json'),n.read(root/'events.json'),group)
    for name in ('wire','failures'):need(n.read(root/(name+'.json'))==[],'closed election wait no '+name)
    return dict(status='PASS',scope='native-wait-closed-without-grant',originalFirst=True,authorityWrites=False,
                autonomousElection=False,publicRuntime=False,phase3Complete=False)


NEGATIVES={
    'allocator':'admitted exact after-close: node-1',
    'selector':'admitted exact after-close: node-2',
    'extra-grant':'admitted exact after-close: node-3',
    'hidden-force':'closed election wait exact reopen only',
    'hidden-wire':'closed election wait no wire',
    'hidden-failure':'closed election wait no failures',
}


def qualify(root):
    original=validate(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-election-wait-negative-') as temp:
            dest=Path(temp)/'raw';shutil.copytree(root,dest)
            if name in ('allocator','selector','extra-grant'):
                path={'allocator':'node-1/allocator.gsr','selector':'node-2/selector.gsr','extra-grant':'node-3/extra-grant.gsr'}[name]
                (dest/'after-close'/path).write_bytes(b'changed')
            else:
                path={'hidden-force':'events','hidden-wire':'wire','hidden-failure':'failures'}[name]
                (dest/(path+'.json')).write_bytes(f.canonical([dict(hidden=True)]))
            try:validate(dest)
            except ValueError as error:need(str(error)==reason,'closed election wait unrelated negative '+name+': '+str(error))
            else:raise ValueError('closed election wait accepted negative '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.root),sort_keys=True))
