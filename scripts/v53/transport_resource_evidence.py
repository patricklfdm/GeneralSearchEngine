"""Original socket attempts own distinct request/reply buffer reservations.

Frame lengths come from validated original wire bytes. Resource observations
provide exact lease identities and local mutation positions, not message truth.
Other service/cache/control reservations remain a separate lifetime obligation.
"""
import argparse
import base64
import json
from pathlib import Path
import re
from uuid import UUID

from . import joining_connections as connections
from . import native_resource_evidence as accounting
from . import transport_connection_evidence as component

need=accounting.need
HEADER=48
PREFIX='transport-'
OWNER=re.compile(r'transport-(request-send|request-read|response-send|response-read)-([0-9a-f-]{36})\Z')


def owner(value):
    match=OWNER.fullmatch(value)
    need(match is not None,'transport resources frame owner shape')
    try:identifier=UUID(match[2])
    except ValueError:raise ValueError('transport resources frame owner identity') from None
    need(identifier.int!=0 and str(identifier)==match[2],'transport resources frame owner identity')
    return match[1],match[2]


def lifetimes(traces):
    result={};other=0
    for node,trace in traces.items():
        accounting.transitions.replay(trace)
        for change in trace['changes']:
            for side in ('removed','added'):
                for charge in change[side]:
                    if charge['owner'].startswith(PREFIX):
                        need(charge['unit']=='CONTROL','transport resources frame category');owner(charge['owner'])
            removed=[v for v in change['removed'] if v['owner'].startswith(PREFIX)]
            added=[v for v in change['added'] if v['owner'].startswith(PREFIX)]
            if not removed and not added:
                if change['event']=='RESERVE':
                    for charge in change['added']:
                        if charge['unit']!='CONTROL':continue
                        # Old untyped transport UUIDs cannot be guessed by size.
                        try:UUID(charge['owner'])
                        except ValueError:other+=1
                        else:raise ValueError('transport resources unbound legacy frame lease')
                continue
            event=change['event'];sequence=change['sequence']
            need(event in ('RESERVE','CONTROL_GROW','RELEASE'),'transport resources unexpected mutation')
            charge=(added or removed)[0];role,identifier=owner(charge['owner']);key=node,role,identifier
            if event=='RESERVE':
                need(key not in result,'transport resources reused frame lease')
                result[key]=dict(node=node,role=role,connection=identifier,start=sequence,end=None,initial=charge['bytes'],growth=[])
            else:
                need(key in result and result[key]['end'] is None,'transport resources original frame lifetime')
                life=result[key]
                if event=='RELEASE':life['end']=sequence
                else:
                    need(role.endswith('-read') and not life['growth'],'transport resources receive header growth')
                    life['growth'].append((sequence,charge['bytes']))
    need(all(v['end'] is not None for v in result.values()),'transport resources frame not released')
    for life in result.values():
        if life['role'].endswith('-read'):need(life['initial']==HEADER,'transport resources original receive header')
    return result,other


def replay(events,wires,traces,boundaries,identities,root,*,require_all_frames=True):
    need(type(require_all_frames) is bool,'transport resources completeness option')
    network=connections.replay(events,wires,identities,root)
    leases,other=lifetimes(traces);used=set();known=set();checks=0
    need(type(boundaries) is list and len(boundaries)==len(events),'transport resources complete checkpoints')
    def point(at,node):
        nonlocal checks
        row=boundaries[at]
        need(type(row) is dict and set(row)=={'eventIndex','node','sequence','usage'} and type(row['eventIndex']) is int and
             row['eventIndex']==at and row['node']==node==events[at]['node'] and type(row['sequence']) is int and
             0<=row['sequence']<len(traces[node]['changes']),'transport resources exact checkpoint')
        accounting.transitions.same_usage(row['usage'],traces[node]['changes'][row['sequence']]['usage']);checks+=1
        return row['sequence']
    def get(node,role,identifier,required=True):
        key=node,role,identifier;life=leases.get(key)
        need(life is not None or not required,'transport resources missing original frame lease')
        if life is not None:used.add(key)
        known.add((node,identifier));return life
    def live(life,at,expected):
        seq=point(at,life['node']);size=life['initial']
        for position,extent in life['growth']:
            if position<=seq:size=extent
        need(life['start']<=seq<life['end'],'transport resources frame not live at boundary')
        need(size==expected,'transport resources original frame extent')
    def closed(life,at):
        need(life['end']<=point(at,life['node']),'transport resources frame not closed at terminal')
    def send(life,size):
        need(life['initial']==size and not life['growth'],'transport resources original send buffer')
    responses={v['sent']:v for v in network['rows']};failed={v['sent']:v for v in network['failed']}
    wire_sizes={v['connection']['id']:len(base64.b64decode(v['response'],validate=True)) for v in wires}
    for at,event in enumerate(events):
        if event.get('event') not in connections.SENDS:continue
        client=event['node'];client_id=event['connection']['id'];size=len(base64.b64decode(event['bytes'],validate=True))
        response=responses.get(at);failure=failed.get(at)
        need(response is not None or failure is not None,'transport resources original attempt outcome')
        outgoing=get(client,'request-send',client_id);send(outgoing,size);live(outgoing,at,size)
        incoming=get(client,'response-read',client_id,required=failure is None)
        if incoming is not None:
            need(outgoing['start']<incoming['start']<incoming['end']<outgoing['end'],
                 'transport resources caller nested release order')
            need(point(at,client)<incoming['start'],'transport resources receive before request send')
        if failure is None:
            received=response['received'];server_id=response['serverConnection'];server=response['request']['recipient']['node']
            answer_size=wire_sizes[server_id];live(incoming,response['delivered'],answer_size)
        else:
            received=failure['received'];server_id=failure['serverConnection'];server=failure['recipient']
            closed(outgoing,failure['clientFailed'])
            if incoming is not None:
                closed(incoming,failure['clientFailed'])
                if incoming['growth']:
                    need(response is not None and incoming['growth'][0][1]==wire_sizes[server_id],
                         'transport resources failed receive original extent')
        if received is None:continue
        request=get(server,'request-read',server_id);live(request,received,size)
        answer=get(server,'response-send',server_id,required=response is not None)
        if response is not None:
            answer_size=wire_sizes[server_id];send(answer,answer_size);live(request,response['offered'],size);live(answer,response['offered'],answer_size)
            need(point(received,server)<answer['start'] and request['start']<answer['start']<answer['end']<request['end'],
                 'transport resources receiver nested release order')
        else:need(answer is None,'transport resources unobserved offered response')
        if failure is not None:
            live(request,failure['serverFailed'],size)
            if answer is not None:closed(answer,failure['serverFailed'])
    extra=set(leases)-used
    need(not any((node,identifier) in known for node,role,identifier in extra),'transport resources foreign role on observed connection')
    unbound=[leases[key] for key in sorted(extra)]
    need(not require_all_frames or not unbound,'transport resources unobserved frame lifetimes')
    return dict(status='PASS',attempts=network['attempts'],failedAttempts=len(network['failed']),
                boundFrameLifetimes=len(used),checkedFrameBoundaries=checks,unobservedFrameLifetimes=unbound,
                otherControlReservations=other,observedTransportFramesQualified=True,
                allTransportFramesQualified=not unbound,controlLifetimesQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def validate(directory):
    root=Path(directory);before=accounting.collection.inventory(root)
    original=component.validate(root,reader=connections.replay,resource_transitions=True);cases=[]
    for name in component.CASES:
        case=root/name;index,traces,boundaries,events=accounting.load(case)
        group=component.n.b.original(case,3,False)
        all_ids={node:component.f.decode(files['node.gsr'],'records','NODE')['identity'] for node,files in group.items()}
        # This component starts only the original caller and receiver transports.
        identities={node:all_ids[node] for node in ('node-1','node-2')}
        authority=component.n.b.c.current(group['node-1'])[2]['capsule']['root']
        accounting.replay(index,traces,boundaries,events,identities,authority)
        wires=accounting.collection.read_json(case,'wire.json',accounting.collection.WIRE_BYTES)
        result=replay(events,wires,traces,boundaries,all_ids,authority)
        need(result['otherControlReservations']==0,'transport resources component has foreign control work')
        cases.append(dict(result,case=name))
    need(accounting.collection.inventory(root)==before,'transport resources original changed')
    return dict(status='PASS',scope='original-tcp-frame-resource-lifetimes',original=original,cases=cases,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    print(json.dumps(validate(a.root),sort_keys=True))
