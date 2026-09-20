"""Exhaustive bounded network exploration plus reproducible longer fault traces."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import random
from .model import Cluster, Rejected, next_epoch
from .history import validate


def seeds():
    a=Cluster();a.campaign(0);a.campaign(1)
    b=Cluster();epoch=b.campaign(0);b.drain()
    for value in ('ADD:a','UPDATE:a'):b.submit(epoch,value);b.drain()
    b.campaign(0,next_epoch(epoch,0));b.campaign(1,next_epoch(max(v.promise for v in b.voters),1))
    return [('empty-competing',a),('three-slot-prefix-competing',b)]


def run(output,depth=6,seeds_count=32):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    summaries=[];failing=None
    try:
        for name,start in seeds():
            frontier=[start];visited={start.fingerprint()};edges=0;layers=[1]
            for _ in range(depth):
                following=[]
                for state in frontier:
                    for i in range(len(state.messages)):
                        for action in ('deliver','drop'):
                            child=deepcopy(state);failing=child
                            getattr(child,action)(i);validate(child.events);edges+=1
                            key=child.fingerprint()
                            if key not in visited:visited.add(key);following.append(child)
                frontier=following;layers.append(len(frontier))
            summaries.append(dict(name=name,depth=depth,states=len(visited),transitions=edges,layers=layers,
                                  completeWithinDeclaredHorizon=True))
            (output/(name+'-seed.json')).write_text(json.dumps(start.events,indent=2)+'\n')
        for seed in range(seeds_count):
            rng=random.Random(seed);state=Cluster();failing=state;epoch=state.campaign(0);state.drain()
            state.submit(epoch,'ADD_ALL:a,b')
            for _ in range(12):
                if not state.messages:break
                i=rng.randrange(len(state.messages))
                if rng.randrange(5)==0:state.drop(i)
                else:state.deliver(i)
            while state.messages:state.drop()
            proposer=1+seed%2
            epoch=state.campaign(proposer,next_epoch(max(v.promise for v in state.voters),proposer));state.drain()
            state.submit(epoch,'UPDATE:a');state.drain();state.read(epoch,f'read-{seed}');state.drain()
            state.restart((proposer+1)%3);state.finish_read(f'read-{seed}')
            validate(state.events)
            (output/f'seed-{seed:03}.json').write_text(json.dumps(state.events,indent=2)+'\n')
        result=dict(status='PASS',execution='independent-model-only',explorations=summaries,
                    longerSeeds=seeds_count,seedRange=[0,seeds_count-1],duplicateAndCrashSchedules='test_model.py',
                    assumptions='three voters; atomic durable transitions; finite delay/drop horizon; not a universal proof')
        (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result
    except Exception:
        if failing is not None:(output/'failure.json').write_text(json.dumps(failing.events,indent=2)+'\n')
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();print(json.dumps(run(a.output)))
