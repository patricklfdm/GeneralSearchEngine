"""Bind original replay callbacks to the actual continuous completion leases."""
import base64
from . import resource_transitions as r
need=r.need
OWNERS=('application-replay-input','application-replay-output')


def native_membership_starts(events):
    """Called only after the original process/round/physical reader succeeds."""
    from . import native_carried_transition_process as p
    active=None;starts=set()
    for at,row in enumerate(events):
        if row['event']=='ROUND_SLOT_BEGIN':
            raw=base64.b64decode(row['bytes'],validate=True)
            need(row['node']=='node-1' and p.e.digest(raw)==row['record'],'replay resources original round command')
            active=p.f.decode(raw,'records','ENTRY')['kind']
        elif row['event']=='ROUND_SLOT_COMPLETE':active=None
        elif row['event']=='REPLAY_RESERVED' and active in ('INTENT','FINAL'):starts.add(at)
    return starts


def bind(trace,events,boundaries,node,*,closed,membership_starts=frozenset()):
    need(all(type(at) is int and 0<=at<len(events) and events[at]['event']=='REPLAY_RESERVED'
             for at in membership_starts),'replay resources original membership starts')
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
        if event['event'].startswith('REPLAY_'):checkpoints.append((seq,event['event'],at))
    # The reservation survives REPLAY_BEFORE_RETURN (executeRetained), until
    # the journal's later retirement/close. It is never credited as a drain here.
    active=None;intervals=[]
    for seq,point,at in checkpoints:
        if point=='REPLAY_RESERVED':
            need(active is None,'replay resources overlapping operation');active=(seq,at in membership_starts)
        need(active is not None,'replay resources missing reservation boundary')
        if point=='REPLAY_BEFORE_RETURN':intervals.append((active[0],seq,active[1]));active=None
    need(active is None,'replay resources incomplete operation')
    state={};interval=0;owners=None;reserved=[]
    for seq,change in enumerate(trace['changes']):
        for old in change['removed']:del state[r.key(old)]
        for new in change['added']:state[r.key(new)]=new
        while interval<len(intervals) and seq>intervals[interval][1]:interval+=1;owners=None
        if interval<len(intervals) and intervals[interval][0]<=seq<=intervals[interval][1]:
            if owners is None:
                owners=OWNERS[:1] if intervals[interval][2] and ('APPLICATION',OWNERS[1]) not in state else OWNERS
                reserved.append(len(owners)*64*r.MIB)
            need(all(state.get(('APPLICATION',owner))==dict(unit='APPLICATION',owner=owner,
                     bytes=64*r.MIB,claimSource='') for owner in owners) and
                 (len(owners)==2 or ('APPLICATION',OWNERS[1]) not in state),'replay resources two continuous full reservations')
    return dict(callbacks=len(checkpoints),transactions=len(intervals),reservationBytesPerTransaction=reserved,
                fullAccountingValidated=True,closed=result['closed'],wholeRuntimeResourcesQualified=False)
