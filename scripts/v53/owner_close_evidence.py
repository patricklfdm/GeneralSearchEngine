"""Explicit native owner-close intervals; historical last events are not close calls.

This accounting layer follows independent physical/native admission. It does not
prove an OS-lock release instant or filesystem custody between every mutation.
"""
from . import resource_transitions as t

need=t.need
BEGIN='RESOURCE_OWNER_CLOSE_BEGIN'
RETURNED='RESOURCE_OWNER_CLOSE_RETURNED'
V1='gse-v53-resource-capture-index-v1'
V2='gse-v53-resource-capture-index-v2'


def intervals(events):
    result={}
    for at,event in enumerate(events):
        point=event.get('event','')
        if not point.startswith('RESOURCE_OWNER_CLOSE'):continue
        need(set(event)=={'node','event'} and point in (BEGIN,RETURNED),'owner close exact marker')
        node=event['node'];pair=result.setdefault(node,[])
        need(point==(BEGIN if not pair else RETURNED) and len(pair)<2,'owner close ordered unique pair')
        pair.append(at)
    for node,pair in result.items():
        need(len(pair)==2,'owner close complete pair')
        need(not any(v.get('node')==node for v in events[pair[1]+1:]),'owner close event after return')
    return result


def replay(index,traces,boundaries,events,expected):
    pairs=intervals(events);schema=index.get('schema')
    if schema==V1:
        need('closingOwners' not in index and not pairs,'owner close undeclared markers')
        return dict(status='NOT_OBSERVED',owners=0,ownerCloseIntervalsQualified=False,
                    physicalShutdownOrderQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)
    need(schema==V2 and type(index.get('closingOwners')) is list and index['closingOwners']==sorted(expected) and
         expected and set(pairs)==set(expected),'owner close complete original owners')
    need(len(events)==len(boundaries),'owner close complete checkpoints')
    released=0;rows_checked=0;owners={}
    for node,(start,end) in pairs.items():
        need(node in traces,'owner close original budget');trace=traces[node];t.replay(trace)
        def sequence(at):
            point=boundaries[at];seq=point['sequence']
            need(type(point['eventIndex']) is int and point['eventIndex']==at and point['node']==node and
                 type(seq) is int and 0<=seq<len(trace['changes']),'owner close exact checkpoint')
            t.same_usage(point['usage'],trace['changes'][seq]['usage']);return seq
        first,last=sequence(start),sequence(end)
        need(first<last==len(trace['changes'])-1,'owner close terminal resource interval')
        before=trace['changes'][first]['usage'];after=trace['changes'][last]['usage']
        need(before['leases']>0 and before['queued']==0 and not any(before['counts'].get(v,0) for v in ('CONTROL','WAITER')),
             'owner close quiescent storage owner')
        t.same_usage(after,t.EMPTY)
        changes=trace['changes'][first+1:last+1]
        need(all(v['event']=='RELEASE' for v in changes),'owner close only release during shutdown')
        count=sum(len(v['removed']) for v in changes)
        need(count==before['leases'],'owner close exact release inventory')
        released+=count;rows_checked+=len(changes)
        owners[node]=dict(begin=start,returned=end,beginSequence=first,returnedSequence=last,released=count)
    return dict(status='PASS',scope='quiescent-original-network-owner-close-accounting',owners=owners,
                releasedLeases=released,checkedChanges=rows_checked,ownerCloseIntervalsQualified=True,
                physicalShutdownOrderQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)
