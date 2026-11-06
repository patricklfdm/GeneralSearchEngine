"""Bind original replay callbacks to the actual continuous completion leases."""
from . import resource_transitions as r
need=r.need
OWNERS=('application-replay-input','application-replay-output')


def bind(trace,events,boundaries,node,*,closed):
    result=r.replay(trace,require_closed=closed)
    need(len(events)==len(boundaries),'replay resources exact event checkpoints')
    checkpoints=[];last=0
    for at,(event,point) in enumerate(zip(events,boundaries)):
        need(type(point) is dict and set(point)=={'eventIndex','node','sequence','usage'} and
             type(point['eventIndex']) is int and point['eventIndex']==at and point['node']==event.get('node'),
             'replay resources original checkpoint owner')
        if event.get('node')!=node:continue
        seq=point['sequence']
        need(type(seq) is int and last<=seq<len(trace['changes']),'replay resources checkpoint order');last=seq
        r.same_usage(point['usage'],trace['changes'][seq]['usage'])
        if event['event'].startswith('REPLAY_'):checkpoints.append((seq,event['event']))
    # The reservation survives REPLAY_BEFORE_RETURN (executeRetained), until
    # the journal's later retirement/close. It is never credited as a drain here.
    active=None;intervals=[]
    for seq,point in checkpoints:
        if point=='REPLAY_RESERVED':
            need(active is None,'replay resources overlapping operation');active=seq
        need(active is not None,'replay resources missing reservation boundary')
        if point=='REPLAY_BEFORE_RETURN':intervals.append((active,seq));active=None
    need(active is None,'replay resources incomplete operation')
    state={};interval=0
    for seq,change in enumerate(trace['changes']):
        for old in change['removed']:del state[r.key(old)]
        for new in change['added']:state[r.key(new)]=new
        while interval<len(intervals) and seq>intervals[interval][1]:interval+=1
        if interval<len(intervals) and intervals[interval][0]<=seq<=intervals[interval][1]:
            need(all(state.get(('APPLICATION',owner))==dict(unit='APPLICATION',owner=owner,
                     bytes=64*r.MIB,claimSource='') for owner in OWNERS),'replay resources two continuous full reservations')
    return dict(callbacks=len(checkpoints),transactions=len(intervals),reservationBytesPerTransaction=128*r.MIB,
                fullAccountingValidated=True,closed=result['closed'],wholeRuntimeResourcesQualified=False)
