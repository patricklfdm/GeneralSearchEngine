"""Profile-aware joining phase, publication and old-voter prefix qualification.

Each component has a deliberately narrow scope. This does not qualify all
control attempts, joining adoption/maintenance or complete physical histories.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import joining_phase_evidence as phase
from . import joining_publication_evidence as publication
from . import joining_transition_evidence as transition
from .joining_profile_evidence import PROFILES, topology

s=phase.semantic
need=s.need
GATES={'phase':phase,'publication':publication,'transition':transition}
NEGATIVES={
    'foreign-force-owner':('phase','joining slot force unknown owner'),
    'live-voter-force-missing':('phase','joining exact slot force order: {live}'),
    'checkpoint-send-missing':('publication','joining network receive without send'),
    'checkpoint-delivery-missing':('publication','joining network undelivered healthy response'),
    'published-extra-object':('publication','joining exact publication inventory'),
    'published-first-proof-missing':('publication','joining exact publication inventory'),
    'published-coverage-ancestor':('publication','joining exact publication inventory'),
    'published-peer-revision':('publication','joining exact publication inventory'),
    'installed-allocator':('transition','joining exact transition inventory: installed-4: node-1'),
    'installed-offline-owner':('transition','joining exact transition inventory: installed-4: {offline}'),
    'applied-allocator':('transition','joining exact transition inventory: applied-8: node-1'),
    'applied-orphan':('transition','joining exact transition inventory: applied-5: node-2'),
}


def gate(root,profile,name):
    size,kind,_,_=topology(profile)
    return GATES[name].validate(Path(root),size=size,kind=kind)


def validate(root,profile):
    topology(profile);root=Path(root);before=s.collection.inventory(root)
    results={name:gate(root,profile,name) for name in GATES}
    need(s.collection.inventory(root)==before,'joining profile physical original changed')
    return dict(status='PARTIAL',profile=profile,scope='slot-forces-publication-old-voter-prefix',gates=results,
        phase3Complete=False,completePhysicalQualified=False,forceAndNetworkQualified=False,processDeathQualified=False,
        pendingQualification=['joining initialization/continuation/adoption','complete control attempts and export authority',
                              'maintenance and peer chain','process death','complete profile cohort','frozen mapping'])


def checkpoint_binding(root,profile):
    size,kind,_,_=topology(profile);replay=s.Replay(root,size=size,kind=kind)
    for index in range(1,12):replay.step(index)
    receipts=publication.CheckpointReceipts(root,replay)
    return next(v for v in receipts.bindings if v['index']==9 and v['node']=='node-1')


def mutate(root,case,profile):
    need(case in NEGATIVES,'unknown joining profile physical mutation')
    size,kind,old,new=topology(profile)
    if case in ('foreign-force-owner','live-voter-force-missing','checkpoint-send-missing','checkpoint-delivery-missing'):
        rows=s.collection.read_json(root,'events.json',s.collection.EVENT_BYTES)
        if case=='foreign-force-owner':rows.append(dict(node='node-99',event=phase.force_names()[0]))
        elif case=='live-voter-force-missing':
            at=next(i for i,v in enumerate(rows) if v.get('node')==old[size//2] and v['event']==phase.force_names()[0]);rows.pop(at)
        else:
            bound=checkpoint_binding(root,profile);rows.pop(bound['sent' if case=='checkpoint-send-missing' else 'committed'])
        (root/'events.json').write_bytes(s.f.canonical(rows))
    elif case.startswith('published-'):
        publication.mutate(root,{'published-extra-object':'extra-packet-object','published-first-proof-missing':'missing-first-proof-object',
            'published-coverage-ancestor':'coverage-ancestor-omitted','published-peer-revision':'peer-revision'}[case])
    elif case=='installed-offline-owner':(root/'installed-4'/old[-1]/'pending.accept').write_bytes(b'foreign offline write')
    else:transition.mutate(root,{'installed-allocator':'installed-allocator','applied-allocator':'applied-allocator','applied-orphan':'applied-orphan-directory'}[case],size=size,kind=kind)


def qualify(root,profile):
    root=Path(root);before=s.collection.inventory(root);original=validate(root,profile);results=[]
    size,kind,old,new=topology(profile)
    for case,(name,template) in NEGATIVES.items():
        reason=template.format(live=old[size//2],offline=old[-1])
        with tempfile.TemporaryDirectory(prefix='v53-joining-profile-physical-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,case,profile)
            # A semantic failure cannot count as a new physical/causal rejection.
            s.validate(changed,size=size,kind=kind)
            try:gate(changed,profile,name)
            except ValueError as error:need(str(error)==reason,'joining profile physical unrelated negative: '+case+': '+str(error))
            else:raise ValueError('joining profile physical accepted mutation: '+case)
        results.append(dict(case=case,gate=name,status='REJECTED',reason=reason))
    need(s.collection.inventory(root)==before,'joining profile physical original changed')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--profile',choices=PROFILES,required=True)
    p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.root,a.profile) if a.qualify else validate(a.root,a.profile),sort_keys=True))
