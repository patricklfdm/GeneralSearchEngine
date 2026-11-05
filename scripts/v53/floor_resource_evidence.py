"""Bind floor reservations to original copy bytes and their complete lifetime.

The caller first admits physical/network/export/maintenance evidence. Neither
callbacks nor journal totals supply expected files. This layer covers copied
floors and the pinned local generation, not receiving scratch or all storage.
"""
from . import resource_transitions as t
from . import required_four_maintenance as maintenance

need, sha = t.need, maintenance.m.sha


def extents(copy, prefix, *,pinned=False):
    members=copy['members'];images=sorted(name for name in members if name.endswith('.image'))
    metadata=len(copy['manifest'])+sum(len(raw) for name,raw in members.items() if name not in images)
    result={('GENERATION' if pinned else 'SOURCE',prefix):metadata}
    for ordinal,name in enumerate(images):
        owner='generation-'+prefix+':'+name if pinned else prefix+':'+str(ordinal)
        result['APPLICATION',owner]=len(members[name])
    need(all(size>0 for size in result.values()),'floor resources empty original extent')
    return result


def plans(reader):
    """Use already admitted original floor inputs, including physical pin proof."""
    result=[]
    for floor in reader.floor_inputs:
        start=floor['start'];own=floor['own'];node=own['node']
        end=next(i for i in range(start+1,len(reader.events)) if reader.events[i].get('node')==node and
                 reader.events[i]['event']=='FLOOR_RELEASE_BEFORE_RETURN')
        points=[i for i in range(start,end+1) if reader.events[i].get('node')==node and
                reader.events[i]['event'].startswith('FLOOR_') and reader.events[i]['event']!='FLOOR_COPY_BEFORE_RETURN']
        network=any(reader.events[i]['event']=='FLOOR_COPY_HANDED_OFF' for i in points)
        pinned=(node,start) in reader.pinned_floors
        ordered=sorted((v for peer,v in floor['copies'].items() if not pinned or peer!=node),
                       key=lambda v:((v['node']==node) if network else False,sha(v['manifest'])))
        pin={}
        if pinned:
            selector=maintenance.m.f.decode((reader.root/own['path']/'selector.gsr').read_bytes(),'records','SELECTOR')
            need(selector['digest']==sha(own['manifest']),'floor resources original pinned selector')
            pin=extents(own,selector['generation'],pinned=True)
        result.append(dict(node=node,start=start,end=end,points=points,network=network,pin=pin,
                           copies=[extents(v,'floor:'+sha(v['manifest'])) for v in ordered]))
    return result


def lifetimes(traces):
    """Keep every floor reservation, including those between event checkpoints."""
    result={};active={}
    for node,trace in traces.items():
        t.replay(trace);active[node]={};result[node]=[]
        for row in trace['changes']:
            for value in row['removed']:
                if not value['owner'].startswith('floor:'):continue
                key=t.key(value);life=active[node].pop(key,None)
                need(life is not None and row['event']=='RELEASE' and value==life['charge'],
                     'floor resources copy changed before release')
                life['end']=row['sequence']
            for value in row['added']:
                if not value['owner'].startswith('floor:'):continue
                key=t.key(value)
                need(row['event']=='RESERVE' and key not in active[node] and not value['claimSource'],
                     'floor resources original copy reservation')
                life=dict(charge=value,start=row['sequence'],end=None)
                active[node][key]=life;result[node].append(life)
        need(not active[node],'floor resources unclosed copy')
    return result


def replay(floors,events,traces,boundaries):
    """Conditional lifetime reader; complete original admission is separate."""
    need(len(boundaries)==len(events),'floor resources complete boundaries')
    previous={node:-1 for node in traces}
    for at,(event,point) in enumerate(zip(events,boundaries)):
        node=event['node'];sequence=point['sequence']
        need(node in traces and point['node']==node and type(point['eventIndex']) is int and point['eventIndex']==at and
             type(sequence) is int and 0<=sequence and previous[node]<=sequence<len(traces[node]['changes']),
             'floor resources exact event boundary')
        t.same_usage(point['usage'],traces[node]['changes'][sequence]['usage']);previous[node]=sequence
    lives=lifetimes(traces);used=set();covered=set();pin_ranges={node:[] for node in traces};checks=0
    for floor in floors:
        node=floor['node'];points=floor['points'];copies=floor['copies']
        need(points and floor['start']==points[0] and floor['end']==points[-1] and copies,
             'floor resources original floor window')
        expected={};copy_number=0
        if not floor['network']:
            for copy in copies:expected.update(copy)
        else:expected.update(copies[0])
        cleared=None
        for at in points:
            need(at not in covered and events[at]['node']==node,'floor resources duplicate floor boundary');covered.add(at)
            event=events[at]['event'];sequence=boundaries[at]['sequence']
            if event=='FLOOR_COPY_CREATED':
                need(copy_number<len(copies),'floor resources extra copy')
                expected.update(copies[copy_number]);copy_number+=1
            if event=='FLOOR_RELEASE_CLEARED':cleared=sequence
            if event=='FLOOR_RELEASE_BEFORE_RETURN':expected={}
            actual={t.key(v['charge']):v['charge']['bytes'] for v in lives[node] if v['start']<=sequence<v['end']}
            need(actual==expected,'floor resources exact live copy extents');checks+=1
        need(copy_number==len(copies) and cleared is not None,'floor resources complete copies and cleanup')
        first=boundaries[floor['start']]['sequence'];end=boundaries[floor['end']]['sequence']
        created=[boundaries[i]['sequence'] for i in points if events[i]['event']=='FLOOR_COPY_CREATED']
        for ordinal,copy in enumerate(copies):
            begin=first if not floor['network'] or ordinal==0 else created[ordinal]
            for key,size in copy.items():
                found=[(i,v) for i,v in enumerate(lives[node]) if t.key(v['charge'])==key and v['start']<=begin<v['end']]
                need(len(found)==1,'floor resources continuous copy lease');i,life=found[0]
                need((node,i) not in used and life['charge']['bytes']==size and cleared<life['end']<=end,
                     'floor resources complete copy release interval');used.add((node,i))
        if floor['pin']:pin_ranges[node].append((first,end,floor['pin']))
    eligible={i for i,v in enumerate(events) if v['event'].startswith('FLOOR_') and v['event']!='FLOOR_COPY_BEFORE_RETURN'}
    need(covered==eligible and floors,'floor resources complete original floor coverage')
    need(used=={(node,i) for node,rows in lives.items() for i in range(len(rows))},'floor resources unbound copy reservation')
    # A pin uses existing generation leases, which may conservatively exceed
    # physical bytes. Check every mutation, not only floor callbacks: an early
    # release and re-reserve between callbacks must not pass.
    pin_checks=0
    for node,ranges in pin_ranges.items():
        if not ranges:continue
        state={}
        for row in traces[node]['changes']:
            for value in row['removed']:state.pop(t.key(value))
            for value in row['added']:state[t.key(value)]=value
            for start,end,required in ranges:
                if not start<=row['sequence']<=end:continue
                need(all(key in state and not state[key]['claimSource'] and state[key]['bytes']>=size
                         for key,size in required.items()),'floor resources continuous original pin coverage')
                pin_checks+=1
    return dict(status='PASS',scope='original-floor-copy-and-local-pin-storage-lifetimes',floors=len(floors),
                copyLeases=len(used),floorBoundaries=checks,pinnedFloors=sum(map(len,pin_ranges.values())),
                pinnedMutationChecks=pin_checks,floorStorageLifetimesQualified=True,
                receivingScratchQualified=False,physicalPeakQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def bind(root,events,traces,boundaries):
    reader=maintenance.Replay(root);reader.run()
    need(reader.events==events,'floor resources original event input')
    return replay(plans(reader),events,traces,boundaries)
