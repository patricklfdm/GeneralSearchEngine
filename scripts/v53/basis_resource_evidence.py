"""Original persistent BASIS packet/image charges through retirement and reopen.

Full physical/network/ledger admission comes first. Owner reopen intervals are
bound to independently admitted original cold files, never inferred from a gap
in the journal. Unmarked old-owner shutdown ordering is explicitly not qualified.
"""
from collections import Counter
from uuid import UUID

from . import receive_resource_evidence as receiving

t,need,maintenance,e=receiving.t,receiving.need,receiving.maintenance,receiving.e
REOPEN={'repeated-basis-owner':'joining-originals-native/replica',
        'continuation-owner':'joining-originals-native/replica',
        'stable-cold-owner':'joining-originals-stable-cold/replica'}


def extents(source):
    identifier=source['value']['basisId'];members=source['members'];packet=e.disk.p.decode(members['source.gscp'])
    need(set(members)=={'source.gscp',*(digest+'.image' for digest in packet['images'])},'basis resources original member inventory')
    result={('SOURCE',identifier):len(members['source.gscp'])}
    for digest,size in packet['images'].items():
        raw=members[digest+'.image']
        need(len(raw)==size and e.sha(raw)==digest,'basis resources original image identity')
        result['APPLICATION',identifier+':'+digest]=len(raw)
    return result


def derive(reader):
    events=reader.events;result=[];used_starts=set();used_retirements=set();cold={}
    # CURRENT_VALIDATED also occurs when one still-live owner loads a newly
    # published generation. Only the first opening of each independently
    # admitted joining-owner scope permits a close/reopen reservation interval.
    openings={}
    for at,event in enumerate(events):
        if event.get('node')!=reader.model.joining or event['event']!='CURRENT_VALIDATED':continue
        scope=event.get('scope')
        need(scope in {'initial-owner','retaining-owner',*REOPEN},'basis resources original reopen scope')
        openings.setdefault(scope,at)
    def one(node,name,lower,upper,scope=None):
        points=[i for i in range(lower+1,upper) if events[i].get('node')==node and events[i]['event']==name and
                (scope is None or events[i].get('scope')==scope)]
        need(len(points)==1,'basis resources exact original boundary: '+name);return points[0]
    for source in reader.sources:
        node=source['node'];identifier=source['value']['basisId'];start=source['start'];end=source['end']
        scope=events[start].get('scope');scope=None if scope=='network-owner' else scope
        previous=[i for i in range(start) if events[i].get('node')==node and events[i].get('scope')==scope and events[i]['event']=='CURRENT_BEFORE_CAPTURE']
        need(previous,'basis resources original capture invocation');lower=previous[-1]
        created=one(node,'SOURCE_BEFORE_CREATE',lower,start)
        need(created not in used_starts,'basis resources reused capture boundary');used_starts.add(created)
        wanted=extents(source);segments=[]
        first=dict(reserveAfter=lower,reserveBy=created,liveFrom=created,liveThrough=start,releaseBy=None,kind='capture')
        segments.append(first)
        reopens=sorted(i for scope,i in openings.items() if node==reader.model.joining and scope in REOPEN and start<i<end)
        for at in reopens:
            opened=events[at].get('scope')
            need(node==reader.model.joining and opened in REOPEN,'basis resources original reopen scope')
            prior=max(i for i in range(at) if events[i].get('node')==node)
            segments[-1].update(liveThrough=prior,releaseBy=at)
            ready=one(node,'JOINING_RETENTION_SEED_RECOVERY_FORCED',at,len(events),opened)
            floor=one(node,'CURRENT_DIRECTORY_FORCED',at,ready,opened)
            path=REOPEN[opened]
            if path not in cold:cold[path]=e.disk.inventory(reader.root/path)
            prefix='sources/'+identifier+'/'
            need({name.removeprefix(prefix):raw for name,raw in cold[path].items() if name.startswith(prefix)}==source['members'],
                 'basis resources original reopened source bytes')
            segments.append(dict(reserveAfter=floor,reserveBy=ready,liveFrom=ready,liveThrough=ready,releaseBy=None,kind='reopen'))
        retired=end<len(events)
        if retired:
            transactions=[v for v in reader.capture_transactions if v['node']==node and v['steps'][0]['event']==end]
            need(len(transactions)==1 and (node,end) not in used_retirements,'basis resources exact source retirement')
            used_retirements.add((node,end));steps=transactions[0]['steps'];written=next(v for v in steps if v['point']=='SOURCE_RETIREMENT_WRITTEN')
            prefix='sources/'+identifier+'/'
            need({name.removeprefix(prefix):raw for name,raw in written['files'].items() if name.startswith(prefix)}==source['members'],
                 'basis resources original retiring source bytes')
            deleted=[v for v in steps if v['point']=='SOURCE_RETIREMENT_DIRECTORY_DELETED']
            cleared=[v for v in steps if v['point']=='SOURCE_RETIREMENT_CLEARED']
            need(len(deleted)==len(cleared)==1,'basis resources exact retirement deletion and clear')
            segments[-1].update(liveThrough=deleted[0]['capturedEvent'],releaseBy=cleared[0]['event'])
        elif reopens and events[reopens[-1]].get('scope')=='stable-cold-owner':
            at=reopens[-1];opened=one(node,'FIXTURE_OPEN_RETURNED',at,len(events),'stable-cold-owner')
            closed=one(node,'FIXTURE_CLOSE_RETURNED',opened,len(events),'stable-cold-owner')
            segments[-1].update(liveThrough=opened,releaseBy=closed)
        else:
            # Old owners have no final close callback in this original. Require
            # continuous charging through their last event; do not invent one.
            segments[-1]['liveThrough']=max(i for i,v in enumerate(events) if v.get('node')==node)
        result.append(dict(node=node,id=identifier,extents=wanted,segments=segments,retired=retired))
    need(used_starts=={i for i,v in enumerate(events) if v['event']=='SOURCE_BEFORE_CREATE'},'basis resources complete source capture coverage')
    need(used_retirements=={(v['node'],v['steps'][0]['event']) for v in reader.capture_transactions},
         'basis resources complete retirement coverage')
    need(len({(v['node'],v['id']) for v in result})==len(result) and result,'basis resources unique original sources')
    return result


def lives(traces,plans):
    expected={(v['node'],owner):(unit,size) for v in plans for (unit,owner),size in v['extents'].items()}
    result={identity:[] for identity in expected};active={}
    for node,trace in traces.items():
        t.replay(trace)
        for row in trace['changes']:
            for side in ('removed','added'):
                for charge in row[side]:
                    identity=node,charge['owner']
                    if identity not in expected:
                        # UUID:image-digest is exclusively a persistent source
                        # image name. Receiving images use the plain transfer ID.
                        prefix,colon,_=charge['owner'].partition(':')
                        if colon:
                            try:UUID(prefix)
                            except ValueError:pass
                            else:raise ValueError('basis resources unbound source image')
                        continue
                    unit,size=expected[identity]
                    need(charge['unit']==unit and not charge['claimSource'],'basis resources original source category')
                    need(charge['bytes']==size,'basis resources exact original source extent')
                    if side=='added':
                        need(row['event']=='RESERVE' and identity not in active,'basis resources immutable source reservation')
                        life=dict(start=row['sequence'],end=None);result[identity].append(life);active[identity]=life
                    else:
                        need(row['event']=='RELEASE' and identity in active,'basis resources exact source release')
                        active.pop(identity)['end']=row['sequence']
    need(not active and all(result.values()),'basis resources complete source reservation inventory')
    return result


def replay(plans,events,traces,boundaries):
    need(plans and len({(v['node'],v['id']) for v in plans})==len(plans),'basis resources unique original sources')
    need(len(events)==len(boundaries),'basis resources complete checkpoints')
    actual=lives(traces,plans);checks=0;unmarked=0
    def sequence(at,node):
        nonlocal checks
        need(type(at) is int and 0<=at<len(events),'basis resources original event position')
        point=boundaries[at];seq=point['sequence']
        need(type(point['eventIndex']) is int and point['eventIndex']==at and point['node']==node==events[at]['node'] and
             type(seq) is int and 0<=seq<len(traces[node]['changes']),'basis resources exact checkpoint')
        t.same_usage(point['usage'],traces[node]['changes'][seq]['usage']);checks+=1;return seq
    for plan in plans:
        node=plan['node'];segments=plan['segments']
        need(segments,'basis resources source owner lifetimes')
        for (unit,owner),size in plan['extents'].items():
            leases=actual[node,owner]
            need(len(leases)==len(segments),'basis resources exact owner lifetime count')
            for lease,segment in zip(leases,segments):
                after=sequence(segment['reserveAfter'],node);by=sequence(segment['reserveBy'],node)
                first=sequence(segment['liveFrom'],node);last=sequence(segment['liveThrough'],node)
                need(after<lease['start']<=by<=first<=last<lease['end'],'basis resources continuous original owner lifetime')
                if segment['releaseBy'] is not None:
                    need(lease['end']<=sequence(segment['releaseBy'],node),'basis resources exact release interval')
            if segments[-1]['releaseBy'] is None:unmarked+=1
    return dict(status='PASS',scope='original-persistent-basis-charges-through-observed-owner-lifetimes',
                sources=len(plans),retiredSources=sum(v['retired'] for v in plans),
                leases=sum(len(v) for v in actual.values()),
                sourceOwnerLifetimes=sum(len(v['segments']) for v in plans),
                reopenedLifetimes=sum(v['kind']=='reopen' for p in plans for v in p['segments']),
                units=dict(Counter(unit for v in plans for unit,_ in v['extents'])),checkedBoundaries=checks,
                unmarkedFinalCloseLeases=unmarked,persistentBasisChargesQualified=True,
                forcedRetirementReleaseQualified=True,unmarkedShutdownPhysicalOrderQualified=False,
                otherStorageLifetimesQualified=False,physicalPeakQualified=False,
                wholeRuntimeResourcesQualified=False,phase3Complete=False)
