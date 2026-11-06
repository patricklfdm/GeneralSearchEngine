"""Exact joining-close observation mutations after the owning original passes."""
import copy
from . import joining_owner_close as r
from .floor_resource_negatives import recount

NEGATIVES={
    'missing-open':'joining close complete ordered lifetimes',
    'missing-return':'joining close complete ordered lifetimes',
    'duplicate-begin':'joining close complete ordered lifetimes',
    'foreign-owner':'joining close exact original marker',
    'foreign-scope':'joining close complete ordered lifetimes',
    'post-close-event':'joining close scoped event after return',
    'empty-interval':'joining close distinct resource lifetimes',
    'early-return':'resource transitions derived usage',
    'empty-begin':'joining close distinct resource lifetimes',
    'allocation-during-close':'joining close only release during shutdown',
    'control-during-close':'joining close quiescent live journal',
    'after-final-return':'joining close final return is terminal',
}


def mutate(data,name):
    events,traces,boundaries,node=data;r.need(name in NEGATIVES,'joining close declared mutation')
    opened,start,end=r.intervals(events,node)['initial-owner'];rows=traces[node]['changes']
    first=boundaries[start]['sequence'];last=boundaries[end]['sequence']
    if name=='missing-open':events[opened]['event']='MISSING_OPEN'
    elif name=='missing-return':events[end]['event']='MISSING_RETURN'
    elif name=='duplicate-begin':events[end]['event']=r.BEGIN
    elif name=='foreign-owner':events[start]['node']='foreign-node'
    elif name=='foreign-scope':events[start]['scope']='other-owner'
    elif name=='post-close-event':events.append(dict(node=node,scope='initial-owner',event='OTHER'))
    elif name=='empty-interval':boundaries[start]['sequence']=last
    elif name=='early-return':boundaries[end]['sequence']=last-1
    elif name=='empty-begin':boundaries[start]['sequence']=0
    else:
        value=dict(unit='CONTROL',owner='joined-close-negative',bytes=1,claimSource='')
        at=len(rows) if name=='after-final-return' else first+1
        rows[at:at]=[dict(event='RESERVE',removed=[],added=[value]),dict(event='RELEASE',removed=[value],added=[])]
        for b in boundaries:
            if b['node']==node and b['sequence']>=at:b['sequence']+=2
        if name=='control-during-close':boundaries[start]['sequence']=at
    if name!='post-close-event':recount(traces,boundaries)


def replay(data,progress=None):
    r.replay(*data);result=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'joining close unrelated rejection: '+name+': '+str(error))
        else:raise ValueError('joining close accepted mutation: '+name)
        result.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(stage='joining-close-negatives',case=name,completed=len(result),total=len(NEGATIVES)))
    return result
