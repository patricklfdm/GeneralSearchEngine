"""Original-first close accounting negatives; no workload retries or evidence edits."""
import argparse
import copy
import json
from pathlib import Path
import sys

from . import owner_close_evidence as r, native_resource_evidence as native
from .floor_resource_negatives import recount

NEGATIVES={
    'missing-owner':'owner close complete original owners',
    'duplicate-owner':'owner close complete original owners',
    'undeclared-markers':'owner close undeclared markers',
    'missing-return':'owner close complete pair',
    'duplicate-begin':'owner close ordered unique pair',
    'unknown-marker':'owner close exact marker',
    'post-close-event':'owner close event after return',
    'empty-interval':'owner close terminal resource interval',
    'early-return':'owner close terminal resource interval',
    'empty-begin':'owner close quiescent storage owner',
    'allocation-during-close':'owner close only release during shutdown',
    'control-during-close':'owner close quiescent storage owner',
}


def mutate(data,name):
    index,traces,boundaries,events,expected=data;r.need(name in NEGATIVES,'owner close declared negative')
    node=index['closingOwners'][0];start,end=r.intervals(events)[node]
    rows=traces[node]['changes'];first=boundaries[start]['sequence'];last=boundaries[end]['sequence']
    if name=='missing-owner':index['closingOwners'].pop()
    elif name=='duplicate-owner':index['closingOwners'].append(node)
    elif name=='undeclared-markers':index['schema']=r.V1;del index['closingOwners']
    elif name=='missing-return':events[end]['event']='OTHER'
    elif name=='duplicate-begin':events[end]['event']=r.BEGIN
    elif name=='unknown-marker':events[end]['event']='RESOURCE_OWNER_CLOSE_UNKNOWN'
    elif name=='post-close-event':events.append(dict(node=node,event='OTHER'))
    elif name=='empty-interval':boundaries[start]['sequence']=last
    elif name=='early-return':boundaries[end]['sequence']=last-1
    elif name=='empty-begin':boundaries[start]['sequence']=0
    else:
        # A balanced reservation/release can preserve all terminal totals. It
        # must still be rejected inside a supposedly quiescent close interval.
        charge=dict(unit='CONTROL',owner='close-negative-control',bytes=1,claimSource='')
        r.need(all(v['owner']!=charge['owner'] for row in rows for v in row['added']),'owner close negative collision')
        at=first+1 if name=='allocation-during-close' else first
        rows[at:at]=[dict(event='RESERVE',removed=[],added=[charge]),dict(event='RELEASE',removed=[charge],added=[])]
        for point in boundaries:
            if point['node']==node and point['sequence']>=at:point['sequence']+=2
        if name=='control-during-close':boundaries[start]['sequence']=at
    if name!='post-close-event':recount(traces,boundaries)


def replay(data,progress=None):
    original=r.replay(*data);r.need(original['status']=='PASS','owner close original markers required')
    results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'owner close unrelated negative: '+name+': '+str(error))
        else:raise ValueError('owner close mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(case=name,completed=len(results),total=len(NEGATIVES)))
    return results


def qualify(root,profile='stable',progress=None):
    root=Path(root);before=native.collection.inventory(root)
    original=native.validate(root,profile,progress);closed=original['ownerCloseResources']
    r.need(closed['status']=='PASS','owner close original markers required')
    index,traces,boundaries,events=native.load(root)
    results=replay((index,traces,boundaries,events,set(closed['owners'])),progress)
    r.need(native.collection.inventory(root)==before,'owner close changed original')
    return dict(status='PASS',original=original,negatives=results,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root')
    p.add_argument('--profile',choices=('stable','5-REPLACE-required-four'),default='stable');a=p.parse_args()
    progress=lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(a.root,a.profile,progress),sort_keys=True))
