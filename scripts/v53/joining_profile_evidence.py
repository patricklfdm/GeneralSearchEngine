"""Original-first semantic replay of an ADD/REPLACE prefix through JOINT.

This does not qualify FINAL, initialized joining voters, force/network causality,
process death, or complete Phase 3. Profile inputs are explicit reader contracts;
producer result labels never supply membership or quorum authority.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile
from . import joining_catalog_evidence as c

PROFILES = ('3-ADD','4-ADD','3-REPLACE','4-REPLACE','5-REPLACE')
need = c.need


def topology(profile):
    need(profile in PROFILES, 'joining prefix profile')
    size, kind = profile.split('-'); size = int(size)
    old = ['node-'+str(i) for i in range(1,size+1)]
    new = (old if kind=='ADD' else old[:-1]) + ['node-'+str(size+1)]
    return size, kind, old, new


class PrefixReplay(c.Replay):
    def placed_snapshot(self):
        # Shared catalog replay needs original typed/ACK bytes only. This is
        # deliberately a pending snapshot, never represented as native placement.
        if self.placed is None: self.placed = c.joining.read(self.path/'joining-originals-pending',stage='pending')
        return self.placed


def validate(root, profile):
    size, kind, old, new = topology(profile)
    root = Path(root); original = c.collection.inventory(root)
    indices = sorted(int(p.name.removeprefix('applied-')) for p in root.iterdir() if re.fullmatch(r'applied-[1-9][0-9]*',p.name))
    need(1 <= len(indices) <= 64 and indices == list(range(1,len(indices)+1)), 'joining prefix consecutive history')
    need(sorted(p.name for p in root.iterdir() if re.fullmatch(r'published-[1-9][0-9]*',p.name)) ==
         sorted('published-'+str(i) for i in indices), 'joining prefix publication history')
    replay = PrefixReplay(root,size=size,kind=kind)
    kinds = [replay.step(i) for i in indices]
    need(tuple(k for k in kinds if k!='BARRIER') == c.CONTROLS[:-1] and kinds[0]=='BARRIER' and kinds[-1]=='INTENT',
         'joining prefix control order')
    final = replay.states[-1]; live = old[:size//2+1]
    need(final['active']==1 and final['results'][0]['phase']=='JOINT' and
         final['cut']['view']['old']==old and final['cut']['view']['new']==new, 'joining prefix derived joint view')
    # The original old selected set must certify INTENT. The new node's forced
    # CHECKPOINT_ACK is separately observed and does not become an old-side vote.
    need(all([v['voter'] for v in c.f.decode(p['CERTIFICATE'],'records','CERTIFICATE',replay.root)['proofs']]==live
             for p in replay.phases), 'joining prefix fixed old majority')
    for node in live:
        replay.packet(c.disk.current(c.disk.inventory(root/'after-close'/node))[2],len(indices))
    for node in old[len(live):]:
        need(c.disk.inventory(root/'after-close'/node)==c.disk.inventory(root/'before-network'/node),'joining offline voter changed')
    ready = c.lifecycle(root,replay)
    need(c.collection.inventory(root)==original,'joining prefix changed during replay')
    return dict(status='PASS',scope='joining-prefix-catalog-certificate-checkpoint-chain',profile=profile,slots=len(indices),
        controls=kinds,oldVoters=live,newVoters=new,joining=new[-1],
        oldOnlyJointCheckpoint=len(set(live)&set(new))>=len(new)//2+1,internalReadyCuts=ready,
        semanticChainQualified=True,finalAndColdReopenQualified=False,completePhysicalQualified=False,
        forceAndNetworkQualified=False,processDeathQualified=False,phase3Complete=False,publicReady=False)


NEGATIVES = {
    'missing-applied-slot':'joining prefix consecutive history',
    'missing-published-slot':'joining prefix publication history',
    'changed-joining-ack':'joining retained pending ACK bytes',
    'changed-applied-catalog':'joining independently reduced applied end',
    'changed-offline-owner':'joining offline voter changed',
}


def qualify(root,profile):
    root=Path(root); inventory=c.collection.inventory(root); original=validate(root,profile); rows=[]
    # Never accept a mutation failure that was already present in the original.
    for case,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-prefix-negative-') as directory:
            copied=Path(directory)/'raw';shutil.copytree(root,copied)
            if case=='missing-applied-slot':shutil.rmtree(copied/'applied-1')
            elif case=='missing-published-slot':shutil.rmtree(copied/'published-1')
            elif case=='changed-joining-ack':(copied/'joining-forced-ack.gsr').write_bytes(b'changed')
            elif case=='changed-applied-catalog':(copied/'applied-1/node-1/applied-end/catalog.gsr').write_bytes(b'changed')
            elif case=='changed-offline-owner':
                size=int(profile[0]);(copied/f'applied-1/node-{size}/unexpected').write_bytes(b'changed')
            try:validate(copied,profile)
            except ValueError as error:
                need(str(error)==reason,'joining prefix unexpected negative: '+case+': '+str(error))
            else:raise ValueError('joining prefix accepted negative: '+case)
            rows.append(dict(case=case,status='REJECTED',reason=reason))
    need(c.collection.inventory(root)==inventory,'joining prefix changed during negative replay')
    return dict(original=original,negatives=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--profile',required=True,choices=PROFILES)
    p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.root,a.profile) if a.qualify else validate(a.root,a.profile),sort_keys=True))
