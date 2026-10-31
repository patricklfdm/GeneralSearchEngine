"""Complete ADD/REPLACE semantic replay, explicitly separate from physical gates."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import joining_catalog_evidence as c
from .joining_profile_evidence import PROFILES, topology

need=c.need
# These mutations have the same meaning for overlapping old/new majorities.
# Removing a joining ACK/vote alone is deliberately NOT a universal negative.
NEGATIVES={
    'missing-applied-slot':'joining complete consecutive applied history',
    'missing-published-slot':'joining complete publication history',
    'changed-joining-ack':'joining retained pending ACK bytes',
    'changed-applied-catalog':'joining independently reduced applied end',
    'changed-offline-owner':'joining offline voter changed',
    'missing-final-ready':'joining complete round lifecycle',
    'final-wrong-binding':'final binding',
    'duplicate-accepts':'quorum identity/order',
    'missing-cold-original':'joining snapshot copied inventory',
}


def validate(root,profile):
    size,kind,_,_=topology(profile)
    result=c.validate(root,size=size,kind=kind)
    return dict(result,semanticFinalAndColdQualified=True,finalAndColdReopenQualified=False,
                pendingQualification=['physical states','force and network','process death','frozen mapping'])


def mutate(root,case,profile):
    if case=='missing-published-slot':shutil.rmtree(root/'published-1')
    elif case=='changed-joining-ack':(root/'joining-forced-ack.gsr').write_bytes(b'changed')
    elif case=='changed-offline-owner':(root/f'applied-1/node-{profile[0]}/unexpected').write_bytes(b'changed')
    elif case=='missing-cold-original':(root/'joining-originals-stable-cold/replica/node.gsr').unlink()
    else:c.mutate(root,case)


def qualify(root,profile):
    root=Path(root);before=c.collection.inventory(root);original=validate(root,profile);results=[]
    for case,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-completion-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,case,profile)
            try:validate(changed,profile)
            except ValueError as error:need(str(error)==reason,'joining completion unrelated negative: '+case+': '+str(error))
            else:raise ValueError('joining completion accepted mutation: '+case)
        results.append(dict(case=case,status='REJECTED',reason=reason))
    need(c.collection.inventory(root)==before,'joining completion original changed during qualification')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--profile',required=True,choices=PROFILES)
    p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.root,a.profile) if a.qualify else validate(a.root,a.profile),sort_keys=True))
