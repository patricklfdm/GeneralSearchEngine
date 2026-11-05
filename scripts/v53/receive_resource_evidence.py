"""Original transfer reservations through receive, metadata force and floor handoff.

Full physical/network/export/ledger admission precedes this layer. A wire COMMIT
is not evidence of installation. Post-handoff learner custody and other storage
owners remain separately qualified; complete conservation alone cannot name files.
"""
from collections import Counter
from uuid import UUID

from . import floor_resource_evidence as floor

t,maintenance,need=floor.t,floor.maintenance,floor.need
e=maintenance.m.e


def key(value):
    q=value['offer']['request']
    return q['sender']['node'],q['payload']['id']


def derive(reader):
    """Expected bytes and boundaries come from admitted originals, not journals."""
    result={};groups=reader.groups;events=reader.events
    for group in groups:
        capsules=[v for v in group if v['kind']=='CAPSULE']
        images=[v for v in group if v['kind']=='APPLICATION']
        need(len(capsules)<=1 and (not images or capsules),'receive resources original source session')
        for content in capsules+images:
            q=content['offer']['request'];node,identifier=key(content)
            need((node,identifier) not in result,'receive resources reused transfer identity')
            chunks=[v for v in reader.rows if v['kind']==v['answer']=='CHUNK' and
                    v['request']['sender']==q['sender'] and v['request']['recipient']==q['recipient'] and
                    v['request']['trace']==q['trace'] and v['request']['payload']['id']==identifier]
            need(chunks,'receive resources missing original chunks')
            packet=e.disk.p.decode(capsules[0]['raw'])
            alias=e.learner_alias(dict(packet=packet),capsules[0]['offer']['request'])
            need(alias in (None,'prefix'),'receive resources original learner prefix')
            unit='APPLICATION' if content['kind']=='APPLICATION' else 'LEARNER' if alias else 'SOURCE'
            row=dict(node=node,id=identifier,unit=unit,size=len(content['raw']),
                     offerSent=content['offer']['sent'],offerDelivered=content['offer']['delivered'],
                     firstChunkSent=chunks[0]['sent'],commitSent=content['commit']['sent'],commitDelivered=content['commit']['delivered'],
                     packet=key(capsules[0]),imageReservation=None,metadata=None,floor=None)
            if unit=='APPLICATION':
                digest=content['offer']['response']['payload']['digest']
                need(packet['images'].get(digest)==len(content['raw']) and e.sha(content['raw'])==digest,
                     'receive resources original declared image')
                packet_id=key(capsules[0])[1]
                last=next(v for v in reversed(reader.rows) if v['kind']==v['answer']=='CHUNK' and
                          v['request']['sender']==q['sender'] and v['request']['trace']==q['trace'] and
                          v['request']['payload']['id']==packet_id)
                row['imageReservation']=(last['delivered'],capsules[0]['commit']['sent'])
            result[node,identifier]=row
    # Every learner prefix in this successful required-four history completes
    # its exact original generation before admission/custody can take the lease.
    used_metadata=set()
    for row in result.values():
        if row['unit']!='LEARNER':continue
        node=row['node'];content=next(v for v in reader.contents if key(v)==(node,row['id']))
        q=content['offer']['request']
        next_receive=min((v['offerSent'] for v in result.values() if v['node']==node and v['unit']=='LEARNER' and v['offerSent']>row['offerSent']),default=len(events))
        points=[i for i,v in enumerate(events) if row['commitDelivered']<i<next_receive and v.get('node')==node and v['event']=='LEARNER_SOURCE_METADATA_RESERVED']
        need(len(points)==1,'receive resources exact learner metadata reservation');point=points[0];used_metadata.add(point)
        copies=[]
        for group in groups:
            first,last=group[0]['offer'],group[-1]['commit'];request=first['request']
            if not (request['sender']==q['sender'] and request['recipient']==q['recipient'] and
                    row['commitDelivered']<first['sent']<last['delivered']<point):continue
            own=reader.current(request['recipient']['node'],first['received'],last['offered'])
            if group[0]['raw']!=own['manifest'] or own['members']['source.gscp']!=content['raw']:continue
            e.authorize_generation(group,reader.windows);copies.append((own,last['delivered']))
        need(len(copies)==1,'receive resources original learner generation');own,delivered=copies[0]
        finished=[i for i,v in enumerate(events) if point<i<next_receive and v.get('node')==node and v['event']=='LEARNER_SOURCE_DIRECTORY_FORCED']
        need(len(finished)==1,'receive resources exact learner metadata force')
        size=floor.extents(own,'original')['SOURCE','original']
        row['metadata']=dict(delivered=delivered,reserved=point,forced=finished[0],size=size)
    need(used_metadata=={i for i,v in enumerate(events) if v['event']=='LEARNER_SOURCE_METADATA_RESERVED'},
         'receive resources complete metadata coverage')
    # Reuse the independently admitted maintenance correspondence. No lease is
    # selected merely because it happens to have the same size as a floor copy.
    previous={};handoffs=0
    for entry in reader.floor_inputs:
        node=entry['own']['node'];start=entry['start'];own=entry['own']
        end=next(i for i in range(start+1,len(events)) if events[i].get('node')==node and events[i]['event']=='FLOOR_RELEASE_BEFORE_RETURN')
        lower=max(own['start'],previous.get(node,-1));previous[node]=end
        points=[i for i in range(start,end+1) if events[i].get('node')==node and events[i]['event']=='FLOOR_COPY_HANDED_OFF']
        if not points:continue
        forced=[i for i in range(start,end+1) if events[i].get('node')==node and events[i]['event']=='FLOOR_COPY_DIRECTORY_FORCED']
        pinned=(node,start) in reader.pinned_floors
        copies=sorted((v for peer,v in entry['copies'].items() if not pinned or peer!=node),key=lambda v:(v['node']==node,e.sha(v['manifest'])))
        need(len(points)==len(forced)==len(copies),'receive resources exact floor handoffs')
        for copy,force,handed in zip(copies,forced,points):
            if copy['node']==node:continue
            found=[v for v in reader.contents if v['kind']=='CAPSULE' and v['offer']['request']['sender']['node']==node and
                   v['offer']['request']['recipient']['node']==copy['node'] and lower<v['offer']['sent']<v['commit']['delivered']<start and
                   v['offer']['request']['payload']['digest']==e.native.current_reference(copy['packet']['capsule'],'retained-current-packet')]
            need(len(found)==1 and found[0]['raw']==copy['members']['source.gscp'],'receive resources original floor packet')
            row=result[key(found[0])]
            need(row['unit']=='SOURCE' and row['floor'] is None,'receive resources unique floor handoff')
            row['floor']=dict(forced=force,handed=handed);handoffs+=1
    bases={(v['node'],v['value']['basisId']) for v in reader.sources}
    need(not bases.intersection(result),'receive resources basis and transfer identity collision')
    return dict(transfers=list(result.values()),bases=bases,floorHandoffs=handoffs)


def lifetimes(traces,expected,bases):
    result={};other=set()
    for node,trace in traces.items():
        t.replay(trace)
        for row in trace['changes']:
            for side in ('removed','added'):
                for charge in row[side]:
                    if charge['unit'] not in ('SOURCE','LEARNER','APPLICATION'):continue
                    try:identifier=UUID(charge['owner'])
                    except ValueError:continue
                    need(str(identifier)==charge['owner'] and identifier.int!=0,'receive resources transfer identity')
                    identity=node,charge['owner']
                    if identity in bases:other.add(identity);continue
                    need(identity in expected,'receive resources unbound staging lease')
                    if side=='removed':continue
                    need(charge['unit']==expected[identity]['unit'] and not charge['claimSource'],'receive resources original staging category')
                    if row['event']=='RESERVE':
                        need(identity not in result,'receive resources reused staging lease')
                        result[identity]=dict(start=row['sequence'],initial=charge['bytes'],growth=[],end=None,terminal=None)
                    else:
                        need(identity in result and result[identity]['end'] is None and row['event']=='STORAGE_GROW' and
                             charge['unit']=='LEARNER' and not result[identity]['growth'],'receive resources unexpected staging growth')
                        result[identity]['growth'].append((row['sequence'],charge['bytes']))
            for charge in row['removed']:
                identity=node,charge['owner']
                if identity not in result or row['event']=='STORAGE_GROW':continue
                need(result[identity]['end'] is None and row['event'] in ('RELEASE','GENERATION_COMMIT','SOURCE_COMMIT','TRANSFER'),
                     'receive resources exact staging terminal')
                result[identity].update(end=row['sequence'],terminal=row['event'])
    need(set(result)==set(expected) and all(v['end'] is not None for v in result.values()),'receive resources complete staging inventory')
    return result,other


def replay(plan,events,traces,boundaries):
    expected={(v['node'],v['id']):v for v in plan['transfers']}
    need(len(expected)==len(plan['transfers']) and expected,'receive resources original transfer set')
    need(len(boundaries)==len(events),'receive resources complete checkpoints')
    leases,bases=lifetimes(traces,expected,plan['bases']);checks=0;handoffs=0
    def sequence(at,node):
        nonlocal checks
        need(type(at) is int and 0<=at<len(events),'receive resources original event position')
        point=boundaries[at];seq=point['sequence']
        need(type(point['eventIndex']) is int and point['eventIndex']==at and point['node']==node==events[at]['node'] and
             type(seq) is int and 0<=seq<len(traces[node]['changes']),'receive resources exact checkpoint')
        t.same_usage(point['usage'],traces[node]['changes'][seq]['usage']);checks+=1;return seq
    def live(lease,seq,size):
        actual=lease['initial']
        for at,grown in lease['growth']:
            if at<=seq:actual=grown
        need(lease['start']<=seq<lease['end'],'receive resources staging not live at original boundary')
        need(actual==size,'receive resources original staging extent')
    for identity,row in expected.items():
        node=row['node'];lease=leases[identity]
        need(lease['initial']==row['size'],'receive resources original initial extent')
        if row['unit']=='APPLICATION':
            lower,upper=row['imageReservation']
            need(sequence(lower,node)<lease['start']<=sequence(upper,node) and lease['start']<=sequence(row['offerSent'],node),
                 'receive resources image reserved before packet commit')
        else:
            need(sequence(row['offerDelivered'],node)<lease['start']<=sequence(row['firstChunkSent'],node),
                 'receive resources packet reservation before first chunk')
        for point in ('firstChunkSent','commitSent','commitDelivered'):live(lease,sequence(row[point],node),row['size'])
        metadata=row['metadata']
        if row['unit']=='LEARNER':
            need(metadata is not None and len(lease['growth'])==1,'receive resources complete learner metadata growth')
            at,size=lease['growth'][0]
            need(sequence(metadata['delivered'],node)<at<=sequence(metadata['reserved'],node) and size==metadata['size'],
                 'receive resources original learner metadata extent')
            live(lease,sequence(metadata['forced'],node),size)
            need(lease['terminal'] in ('GENERATION_COMMIT','SOURCE_COMMIT','TRANSFER'),'receive resources retained learner custody')
        elif row['unit']=='APPLICATION':
            parent=expected[tuple(row['packet'])];need(parent['metadata'] is not None,'receive resources original learner image parent')
            live(lease,sequence(parent['metadata']['forced'],node),row['size'])
            need(lease['terminal']=='TRANSFER','receive resources retained learner image custody')
        else:need(not lease['growth'] and lease['terminal']=='RELEASE','receive resources complete source cleanup')
        if row['floor']:
            handoff=row['floor'];low=sequence(handoff['forced'],node);high=sequence(handoff['handed'],node)
            live(lease,low,row['size']);need(low<lease['end']<=high,'receive resources forced floor handoff interval');handoffs+=1
    need(handoffs==plan['floorHandoffs'],'receive resources complete floor handoff coverage')
    return dict(status='PASS',scope='original-receiving-file-reservations-and-forced-floor-handoff',
                transfers=len(expected),units=dict(Counter(v['unit'] for v in expected.values())),checkedBoundaries=checks,
                floorHandoffs=handoffs,identifiedPersistentBasisOwners=len(bases),
                receivingTransferChargesQualified=True,receivingFloorHandoffQualified=True,
                postHandoffLearnerCustodyQualified=False,otherStorageLifetimesQualified=False,
                physicalPeakQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def bind(root,events,traces,boundaries):
    reader=maintenance.Replay(root);reader.run()
    need(reader.events==events,'receive resources original event input')
    return replay(derive(reader),events,traces,boundaries)
