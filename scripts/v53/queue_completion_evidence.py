"""Original REMOVE history and actual joint queue pressure on one owner lifetime.

This qualifies recovery after a real queue refusal, not simultaneous maximum
metadata/application occupancy, autonomous membership, or Phase 3 completion.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
from uuid import UUID

from . import continuous_transition_evidence as history
from . import source_queue_evidence as queue
from . import resource_transitions as t
from .offline_fixture_image import application

need=queue.need
POINTS=('JOINT_BEFORE_PRESSURE','SEVEN_SENDS_HELD','EIGHTH_SEND_REFUSED','PRESSURE_DRAINED',
        'FINAL_BEGIN','FINAL_PUBLISHED','BARRIER_PUBLISHED','CLOSED')


def rehearsal_profile(rehearsal,multi_chunk_rehearsal):
    need(type(rehearsal) is bool and type(multi_chunk_rehearsal) is bool and
         (not multi_chunk_rehearsal or rehearsal),'queue completion replay profile')


def load(directory,*,rehearsal=False,multi_chunk_rehearsal=False):
    rehearsal_profile(rehearsal,multi_chunk_rehearsal)
    root=Path(directory);scope=root/'continuous-result.json'
    need(root.is_dir() and not root.is_symlink() and scope.is_file() and not scope.is_symlink() and
         scope.stat().st_size<=4096,'queue completion regular receipt')
    need(history.d.read(root/'continuous-result.json')==dict(status='PASS',kind='REMOVE',activations=3,
         publicReady=False,automaticLifecycle=False),'queue completion continuous scope')
    physical=history.history(root,'continuous-result.json',backup=True,current_maintenance=True,
        additional={'queue-resources.json','queue-completion.json'},maximum_bytes=8*1024*t.MIB,wire_bytes=256*t.MIB)
    original=history.b.original(root,4,True)
    identity={n:queue.f.decode(v['node.gsr'],'records','NODE')['identity'] for n,v in original.items()}
    root_record=queue.f.decode(original['node-1']['root.gsr'],'records','ROOT')
    image=(root/'original-application.image').read_bytes()
    value_bytes=10000 if multi_chunk_rehearsal else 3000 if rehearsal else 32768
    application(image,root_record['historyId'],41,[(i,'q'*value_bytes) for i in range(2 if rehearsal else 129)])
    installed=history.c.inventory(root/'installed-2/node-1')
    _,_,packet=history.c.current(installed)
    journal=history.c.journal(installed['grants.gsr'],packet['capsule']['root'],'node-1')
    selected=queue.f.decode((root/'selected-2.gsr').read_bytes(),'records','SELECTED')
    promise,basis=joint_grant(journal,selected['ballot'])
    return dict(physical=physical,receipt=history.d.read(root/'queue-completion.json'),
                trace=t.read(root/'queue-resources.json')[1],events=history.d.read(root/'events.json'),
                wire=json.loads(history.b.t.plans.read(root/'wire.json',256*t.MIB)),identity=identity,basis=basis,image=image,selected=selected,exportBytes=len(basis)+len(promise))


def joint_grant(rows,ballot):
    bases=[v[1] for v in rows if v[0]=='BASIS' and v[2]['ballot']==ballot]
    promises=[v[1] for v in rows if v[0]=='PROMISE' and v[2]['ballot']==ballot]
    need(len(bases)==len(promises)==1,'queue completion original joint grant')
    return promises[0],bases[0]


def image_commit_sequence(image,chunk):
    need(type(image) is bytes and type(chunk) is int and 0<chunk<=queue.CHUNK and
         chunk<len(image)<=64*t.MIB,'queue completion image extent')
    return 5+(len(image)+chunk-1)//chunk


def replay_session(session,requests,answers,frames,basis,image,chunk):
    """Derive every tail offset and terminal sequence from the original bytes.

    The producer's plan or receipt cannot decide which chunks may be omitted.
    The basis remains the existing one-chunk record in this component.
    """
    terminal=image_commit_sequence(image,chunk)
    need(type(basis) is bytes and 0<len(basis)<=chunk,'queue completion basis extent')
    need(set(session)==set(range(1,terminal+1)),'queue completion session sequence')
    basis_digest=queue.sha(basis);image_digest=queue.sha(image)
    contents={basis_digest:basis,image_digest:image}
    reader=None;transfer=None
    for seq,h in sorted(session.items()):
        kind,q,_=requests[h];akind,a,_=frames[answers[h]];p=q['payload'];digest=basis_digest if seq<=3 else image_digest
        if seq in (1,4):
            need(p['id']!=transfer and str(UUID(p['id']))==p['id'],'queue completion transfer identity');transfer=p['id']
        if reader is None:reader=q['sender']
        offset=(seq-5)*chunk if 5<=seq<terminal else 0
        expected=dict(id=transfer,digest=digest) if seq in (3,terminal) else dict(id=transfer,action='REQUEST',offset=offset,digest=digest,bytes='')
        need(p==expected and q['sender']==reader and kind==('TRANSFER_COMMIT' if seq in (3,terminal) else 'CHUNK'),'queue completion exact request')
        if seq in (1,4):reply_kind='SOURCE_OFFER';payload=dict(id=transfer,digest=digest,bytes=len(contents[digest]),kind='RECORD' if seq==1 else 'APPLICATION')
        elif seq in (3,terminal):reply_kind='TRANSFER_COMMIT';payload=expected
        else:
            reply_kind='CHUNK';data=contents[digest][offset:offset+chunk]
            payload=dict(id=transfer,action='DATA',offset=offset,digest=queue.sha(data),bytes=base64.b64encode(data).decode('ascii'))
        need(akind==reply_kind and a['payload']==payload,'queue completion original content')


def replay(value,*,rehearsal=False,multi_chunk_rehearsal=False):
    rehearsal_profile(rehearsal,multi_chunk_rehearsal)
    chunk=4096 if rehearsal else queue.CHUNK
    receipt=value['receipt'];trace=value['trace'];events=value['events'];selected=value['selected']
    need(set(receipt)=={'schema','status','points','attempts','traces','phase3Complete','combinedMaximumQualified','pressureRequired'} and
         receipt['schema']=='gse-v53-queue-completion-v1' and receipt['status']=='PASS' and
         receipt['pressureRequired'] is (not rehearsal) and receipt['phase3Complete'] is False and receipt['combinedMaximumQualified'] is False,'queue completion scope')
    need(trace['queueLimit']==64*t.MIB,'queue completion frozen queue')
    accounting=t.replay(trace);states=[];state={}
    for row in trace['changes']:
        for charge in row['removed']:del state[t.key(charge)]
        for charge in row['added']:state[t.key(charge)]=charge
        states.append(dict(state))
    points=receipt['points']
    expected_points=[name.replace('EIGHTH_SEND_REFUSED','EIGHTH_SEND_DELIVERED') if rehearsal else name for name in POINTS]
    need([p['event'] for p in points]==expected_points,'queue completion complete milestones')
    previous=-1;event_index=-1
    for point in points:
        at=point['sequence'];index=point['eventIndex']
        need(set(point)=={'event','sequence','queued','eventIndex'} and type(at) is int and previous<=at<len(states) and
             type(index) is int and event_index<=index<=len(events) and
             point['queued']==trace['changes'][at]['usage']['queued'],'queue completion checkpoint binding')
        previous=at;event_index=index
    markers=dict(zip(expected_points,points));start=markers['JOINT_BEFORE_PRESSURE']['eventIndex'];end=markers['FINAL_BEGIN']['eventIndex']
    installed=[i for i,v in enumerate(events) if v.get('event')=='CONTINUOUS_INSTALLED' and v.get('ordinal')==2]
    final=[i for i,v in enumerate(events) if v.get('event')=='SLOT_BEGIN' and v.get('index')==6]
    need(len(installed)==len(final)==1 and installed[0]<start<end<=final[0],'queue completion joint before FINAL')
    for name,index in (('FINAL_PUBLISHED',6),('BARRIER_PUBLISHED',7)):
        done=[i for i,v in enumerate(events) if v.get('event')=='DRIVER_PUBLISHED' and v.get('index')==index]
        need(len(done)==1 and end<done[0]<markers[name]['eventIndex'],'queue completion native publication')
    traces=receipt['traces'];need(len(traces)==4 and traces==sorted(set(traces)) and all(str(UUID(v))==v for v in traces),'queue completion trace set')
    requests={};answers={};frames={};sessions={};deliveries=[]
    for wire in value['wire']:
        raw=base64.b64decode(wire['request'],validate=True);kind,q,qbytes=queue.frame(raw)
        if q['trace'] not in traces:continue
        reply_raw=base64.b64decode(wire['response'],validate=True);akind,a,abytes=queue.frame(reply_raw)
        h=queue.sha(raw);answer=queue.sha(reply_raw)
        need(wire.get('withheld') is False and q['root']==selected['root'] and q['view']==selected['view'] and q['ballot']==selected['ballot'] and
             q['sender'] in [value['identity'][n] for n in ('node-2','node-3')] and q['recipient']==value['identity']['node-1'],
             'queue completion original joint authority')
        need(a==dict(q,sender=q['recipient'],recipient=q['sender'],payload=a['payload']),'queue completion correlated reply')
        session=sessions.setdefault(q['trace'],{})
        need(session.setdefault(q['sequence'],h)==h and answers.setdefault(h,answer)==answer,'queue completion identical replay')
        requests[h]=(kind,q,qbytes);frames[answer]=(akind,a,abytes);deliveries.append((h,answer))
    terminal=image_commit_sequence(value['image'],chunk);unique_requests=4*terminal
    need(set(sessions)==set(traces) and len(requests)==unique_requests and
         len(deliveries)==unique_requests+(9 if rehearsal else 8),'queue completion complete delivered history')
    for session in sessions.values():
        replay_session(session,requests,answers,frames,value['basis'],value['image'],chunk)
    attempts=receipt['attempts'];passed=[v for v in attempts if v['status']=='PASS'];failed=[v for v in attempts if v['status']=='FAIL']
    need(len(attempts)==unique_requests+9 and len(failed)==(0 if rehearsal else 1) and
         (rehearsal or failed[0].get('reason')=='IO') and
         sorted((v['request'],v['response']) for v in passed)==sorted(deliveries),'queue completion complete attempts')
    failures=[v for v in events[start:end] if v.get('event')=='NETWORK_ATTEMPT_FAILED']
    if rehearsal:
        need(not failures,'queue completion rehearsal transport')
    else:
        failed_hash=failed[0]['request'];need(failed_hash in requests and requests[failed_hash][1]['sequence']==5,'queue completion failed large chunk')
        occurrences=[v['status'] for v in attempts if v['request']==failed_hash]
        need(occurrences==['PASS','FAIL','PASS','PASS'],'queue completion recovered identical retry')
        need(len(failures)==2 and {v['reason'] for v in failures}=={'CAPACITY','IO'} and
             all(v['request']==failed_hash for v in failures) and
             any(v['direction']=='INBOUND' and v['node']=='node-1' and v['reason']=='CAPACITY' for v in failures),'queue completion classified refusal')
    baseline={k:v for k,v in states[markers['JOINT_BEFORE_PRESSURE']['sequence']].items() if k[1].startswith('source-export-')}
    need(len(baseline)==2,'queue completion original live exports')
    sizes={frames[answers[session[5]]][2] for session in sessions.values()}
    need(len(sizes)==1,'queue completion equal original chunk extents');size=sizes.pop()
    for name in ('SEVEN_SENDS_HELD','EIGHTH_SEND_DELIVERED' if rehearsal else 'EIGHTH_SEND_REFUSED'):
        point=markers[name];live=states[point['sequence']]
        caches=[v for v in live.values() if any(v['owner'].startswith('source-response-'+s[5]+'-') for s in sessions.values())]
        sends=[v for v in live.values() if v['owner'].startswith('transport-response-send-')]
        need(len(caches)==4 and len(sends)==7 and all(v['unit']=='CONTROL' and v['bytes']==size for v in caches+sends),'queue completion four caches seven sends')
        exports={k:v for k,v in live.items() if k[1].startswith('source-export-')}
        need(len(exports)==6 and all(exports.get(k)==v for k,v in baseline.items()) and
             all(v['owner'].startswith('source-export-'+queue.sha(value['basis'])+'-') and v['bytes']==value['exportBytes'] for v in exports.values()),
             'queue completion six original exports')
        if rehearsal:need(point['queued']+size<=64*t.MIB,'queue completion rehearsal below bound')
        else:queue.byte_refusal(trace['changes'][point['sequence']]['usage'],size)
    need(markers['PRESSURE_DRAINED']['queued']<t.MIB and markers['CLOSED']['queued']==0 and not states[-1],
         'queue completion drained and closed')
    return dict(status='PASS',scope='multi-chunk-completion-rehearsal' if multi_chunk_rehearsal else 'small-image-completion-rehearsal' if rehearsal else 'joint-queue-completion-component-only',sessions=4,capacityRefusals=0 if rehearsal else 1,
                nativeFinalCompleted=True,queuePressureQualified=not rehearsal,maximumQueuedBytes=accounting['maximumObservedReservations']['queued'],
                phase3Complete=False,combinedMaximumQualified=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');p.add_argument('--rehearsal',action='store_true')
    p.add_argument('--multi-chunk-rehearsal',action='store_true');a=p.parse_args()
    options=dict(rehearsal=a.rehearsal or a.multi_chunk_rehearsal,multi_chunk_rehearsal=a.multi_chunk_rehearsal)
    need(not(a.qualify and options['rehearsal']),'queue completion negatives require full original')
    value=load(a.directory,**options)
    print(json.dumps(qualify(value) if a.qualify else replay(value,**options),sort_keys=True))


NEGATIVES={
    'scope':'queue completion scope',
    'queue-limit':'queue completion frozen queue',
    'missing-milestone':'queue completion complete milestones',
    'checkpoint-usage':'queue completion checkpoint binding',
    'pressure-after-final':'queue completion joint before FINAL',
    'publication-boundary':'queue completion native publication',
    'foreign-ballot':'queue completion original joint authority',
    'changed-original-image':'queue completion exact request',
    'unclassified-refusal':'queue completion classified refusal',
    'retry-missing':'queue completion complete attempts',
}


def qualify(value):
    original=replay(value);results=[]
    for name,reason in NEGATIVES.items():
        changed=dict(value,receipt=copy.deepcopy(value['receipt']),events=copy.deepcopy(value['events']),
                     trace=dict(value['trace']),selected=copy.deepcopy(value['selected']))
        r=changed['receipt'];points=r['points']
        if name=='scope':r['combinedMaximumQualified']=True
        elif name=='queue-limit':changed['trace']['queueLimit']-=1
        elif name=='missing-milestone':points.pop()
        elif name=='checkpoint-usage':points[0]['queued']+=1
        elif name=='pressure-after-final':points[0]['eventIndex']=0
        elif name=='publication-boundary':points[5]['eventIndex']=points[4]['eventIndex']
        elif name=='foreign-ballot':changed['selected']['ballot']['counter']+=1
        elif name=='changed-original-image':changed['image']=b'x'+value['image'][1:]
        elif name=='unclassified-refusal':
            next(v for v in changed['events'] if v.get('event')=='NETWORK_ATTEMPT_FAILED' and v.get('reason')=='CAPACITY')['reason']='IO'
        elif name=='retry-missing':r['attempts'].pop()
        try:replay(changed)
        except ValueError as error:
            need(str(error)==reason,'queue completion negative reason drift: '+name+': '+str(error))
            results.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('queue completion negative accepted: '+name)
    return dict(original=original,negatives=results)


if __name__=='__main__':main()
