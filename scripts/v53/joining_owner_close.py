"""Five observed joining journal lifetimes, distinct from final zero accounting."""
from . import resource_transitions as t

need=t.need
SCOPES=('initial-owner','retaining-owner','repeated-basis-owner','continuation-owner','stable-cold-owner')
OPEN='JOINING_OWNER_OPEN_RETURNED'
BEGIN='JOINING_OWNER_CLOSE_BEGIN'
RETURNED='JOINING_OWNER_CLOSE_RETURNED'


def intervals(events,node):
    expected=[(scope,event) for scope in SCOPES for event in (OPEN,BEGIN,RETURNED)]
    rows=[]
    for i,event in enumerate(events):
        if not event.get('event','').startswith('JOINING_OWNER_'):continue
        need(set(event)=={'node','scope','event'} and event.get('node')==node,'joining close exact original marker')
        rows.append((i,event['scope'],event['event']))
    need([(scope,event) for _,scope,event in rows]==expected,'joining close complete ordered lifetimes')
    result={scope:tuple(row[0] for row in rows[at:at+3]) for at,scope in zip(range(0,len(rows),3),SCOPES)}
    for scope,(_,_,returned) in result.items():
        later=[v for v in events[returned+1:] if v.get('node')==node and (v.get('scope')==scope or scope=='stable-cold-owner')]
        need(not later or scope=='stable-cold-owner' and later==[dict(node=node,scope=scope,event='FIXTURE_CLOSE_RETURNED')],
             'joining close scoped event after return')
    return result


def replay(events,traces,boundaries,node):
    spans=intervals(events,node)
    need(node in traces and len(events)==len(boundaries),'joining close original budget/checkpoints')
    trace=traces[node];t.replay(trace);rows=trace['changes'];lifetimes={};released=0
    def sequence(at):
        point=boundaries[at];seq=point['sequence']
        need(type(point['eventIndex']) is int and point['eventIndex']==at and point['node']==node and
             type(seq) is int and 0<=seq<len(rows),'joining close exact checkpoint')
        t.same_usage(point['usage'],rows[seq]['usage']);return seq
    previous=-1
    for scope,(opened,begun,returned) in spans.items():
        first,start,end=map(sequence,(opened,begun,returned))
        need(previous<first<=start<end,'joining close distinct resource lifetimes')
        held=rows[start]['usage']
        need(rows[first]['usage']['leases']>0 and held['leases']>0 and held['counts'].get('JOURNAL')==1 and
             held['counts'].get('GENERATION',0)>0 and held['queued']==0 and
             not any(held['counts'].get(k,0) for k in ('CONTROL','WAITER')),'joining close quiescent live journal')
        t.same_usage(rows[end]['usage'],t.EMPTY)
        changes=rows[start+1:end+1]
        need(all(v['event']=='RELEASE' for v in changes),'joining close only release during shutdown')
        count=sum(len(v['removed']) for v in changes)
        need(count==held['leases'],'joining close exact released inventory')
        lifetimes[scope]=dict(opened=opened,begin=begun,returned=returned,openSequence=first,beginSequence=start,returnedSequence=end,released=count)
        released+=count;previous=end
    need(previous==len(rows)-1,'joining close final return is terminal')
    return dict(status='PASS',scope='five-original-joining-journal-close-intervals',node=node,lifetimes=lifetimes,
                releasedLeases=released,joiningCloseIntervalsQualified=True,physicalShutdownOrderQualified=False,
                wholeRuntimeResourcesQualified=False,phase3Complete=False)
