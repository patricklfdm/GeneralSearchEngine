"""Replay real cached source bytes at the unchanged 64 MiB CONTROL queue bound.

Component evidence only: this does not qualify FINAL under combined pressure.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import re
import struct
from uuid import UUID

from . import resource_transitions as t
from . import source_export_evidence as physical
from . import source_control_resource_evidence as source

f=physical.e.f
need=physical.e.need
sha=physical.e.digest
CHUNK=4*t.MIB
LIMIT=64*t.MIB
SCHEMA='gse-v53-source-queue-v1'


def receipt():
    return dict(schema=SCHEMA,status='PASS',sessions=6,queueLimit=LIMIT,chunkBytes=CHUNK,
                phase3Complete=False,combinedResources=False)


def frame(data):
    need(len(data)>=48,'source queue frame header')
    kind=struct.unpack('>H',data[8:10])[0]
    names=[name for name,spec in f.catalog()['wire'].items() if spec['id']==kind]
    need(len(names)==1,'source queue frame kind')
    return names[0],f.decode(data,'wire',names[0]),len(data)


def load(directory):
    root=Path(directory)
    # Original bootstrap, grant, source packet, images and unchanged after-state
    # are checked before any in-memory negative mutation.
    physical.case(root,3,backup=True,additional={'frames','events.json','resources.json','receipt.json'})
    initial=physical.b.original(root,3,True)
    ids={node:f.decode(files['node.gsr'],'records','NODE')['identity'] for node,files in initial.items()}
    _,_,packet=physical.c.current(initial['node-1'])
    exports=physical.c.inventory(root/'exported')
    contents=physical.load(root/'contents.json')
    image=next(v['digest'] for v in contents if v['kind']=='APPLICATION')
    actual=physical.c.inventory(root/'captured'/'node-1')
    rows=physical.c.journal(actual['grants.gsr'],packet['capsule']['root'],'node-1')
    basis=rows[-1][1];basis_hash=sha(basis)
    frames={}
    for name,data in physical.c.inventory(root/'frames').items():
        need(data is not None and name==sha(data)+'.bin','source queue original frame inventory')
        frames[name[:-4]]=frame(data)
    value=dict(events=physical.load(root/'events.json'),trace=t.read(root/'resources.json')[1],frames=frames,
               identities=ids,root=packet['capsule']['root'],basis=basis_hash,
               contents={basis_hash:basis,image:exports[image+'.bin']},image=image,view=rows[-1][2]['view'],ballot=rows[-1][2]['ballot'],
               exportBytes=len(basis)+len(rows[-2][1]))
    need(physical.load(root/'receipt.json')==receipt(),'source queue receipt scope')
    return value


def byte_refusal(usage,response_bytes):
    need(usage['queued']+response_bytes>LIMIT and 0<response_bytes<=8*t.MIB and usage['counts']['CONTROL']<256,
         'source queue byte-bound refusal witness')


def replay(value):
    trace=value['trace'];result=t.replay(trace)
    need(trace['queueLimit']==LIMIT,'source queue frozen limit')
    events=value['events'];frames=value['frames'];ids=value['identities'];root=value['root']
    need(type(events) is list and len(events)==297,'source queue complete events')
    states=[];state={}
    for row in trace['changes']:
        for charge in row['removed']:del state[t.key(charge)]
        for charge in row['added']:state[t.key(charge)]=charge
        states.append(dict(state))
    previous=-1;used=set()
    shapes={
        'CALL':{'request'},'RETURN':{'request','response'},'CALL_FAILED':{'request','reason'},
        'AFTER_REQUEST_READ':{'request','connection'},'BEFORE_RESPONSE_WRITE':{'request','response','connection'},
        'SERVER_FAILED':{'request','connection','reason'},'TRANSFER_ADMITTED':{'request'},
        'TRANSFER_BEFORE_REPLY':{'request','response'},'PRESSURE':{'request'},'DRAINED':set(),'SERVICE_CLOSED':set()}
    for event in events:
        name=event.get('event');need(name in shapes and set(event)=={'event','sequence','queued'}|shapes[name],'source queue event shape')
        at=event['sequence'];need(type(at) is int and previous<=at<len(states),'source queue checkpoint sequence');previous=at
        need(type(event['queued']) is int and event['queued']==trace['changes'][at]['usage']['queued'],'source queue checkpoint usage')
        for key in ('request','response'):
            if key in event:need(event[key] in frames,'source queue missing frame');used.add(event[key])
    need(used==set(frames),'source queue extra frame')
    sessions={};requests={};answers={};attempts=[];pending={};markers={};connections=set()
    for event in events:
        name=event['event'];h=event.get('request')
        if name=='CALL':
            need(h not in pending,'source queue duplicate concurrent request');pending[h]=[event]
        elif name in ('PRESSURE','DRAINED','SERVICE_CLOSED'):
            need(name not in markers and (len(pending)==5 if name=='PRESSURE' else not pending),'source queue marker order');markers[name]=event
        else:
            need(h in pending,'source queue original attempt');pending[h].append(event)
            if name in ('RETURN','CALL_FAILED'):attempts.append(pending.pop(h))
    need(not pending and len(attempts)==49 and set(markers)=={'PRESSURE','DRAINED','SERVICE_CLOSED'},'source queue complete attempts')
    failed=[]
    for attempt in attempts:
        failure=attempt[-1]['event']=='CALL_FAILED'
        names=['CALL','AFTER_REQUEST_READ','TRANSFER_ADMITTED','TRANSFER_BEFORE_REPLY']+(['SERVER_FAILED','CALL_FAILED'] if failure else ['BEFORE_RESPONSE_WRITE','RETURN'])
        need([v['event'] for v in attempt]==names,'source queue attempt ordering')
        h=attempt[0]['request'];kind,q,qbytes=frames[h];answer=attempt[3]['response'];akind,a,abytes=frames[answer]
        need(q['root']==root and q['view']==value['view'] and q['ballot']==value['ballot'] and q['sender'] in (ids['node-2'],ids['node-3']) and q['recipient']==ids['node-1'], 'source queue original identities')
        common={k:v for k,v in q.items() if k not in ('sender','recipient','payload')}
        need(a==dict(common,sender=q['recipient'],recipient=q['sender'],payload=a['payload']),'source queue response correlation')
        trace_id=q['trace'];need(str(UUID(trace_id))==trace_id and UUID(trace_id).int!=0,'source queue session UUID')
        session=sessions.setdefault(trace_id,dict(reader=q['sender'],requests={}))
        need(session['reader']==q['sender'],'source queue session reader');seq=q['sequence']
        old=session['requests'].setdefault(seq,h);need(old==h,'source queue changed retry')
        requests[h]=q
        if h in answers:need(answers[h]==answer,'source queue retry changed cached bytes')
        answers[h]=answer
        connection=attempt[1]['connection'];need(connection not in connections and str(UUID(connection))==connection,'source queue connection identity');connections.add(connection)
        need(attempt[4]['connection']==connection,'source queue server terminal connection')
        live=states[attempt[1]['sequence']]
        need(live.get(('CONTROL','transport-request-read-'+connection),{}).get('bytes')==qbytes,'source queue received request charge')
        offered=states[attempt[3]['sequence']]
        leases=[c for c in offered.values() if c['owner'].startswith('source-response-'+h+'-')]
        need(len(leases)==1 and leases[0]['bytes']==abytes,'source queue cached reply extent')
        if failure:
            need(attempt[4]['reason']=='CAPACITY' and attempt[5]['reason']=='IO','source queue classified capacity refusal')
            at=attempt[4]['sequence'];current=trace['changes'][at]['usage']
            need(attempt[3]['sequence']==at,'source queue refusal checkpoint')
            byte_refusal(current,abytes)
            failed.append((h,answer,at))
        else:
            need(attempt[-1]['response']==answer,'source queue delivered original bytes')
            live=states[attempt[4]['sequence']]
            need(live.get(('CONTROL','transport-response-send-'+connection),{}).get('bytes')==abytes,'source queue actual send extent')
    need(len(sessions)==6 and len(requests)==42 and len(failed)==1,'source queue distinct sessions and failure')
    image=value['image'];basis=value['basis'];contents=value['contents']
    need(CHUNK<len(contents[image])<2*CHUNK,'source queue original image extent')
    for session in sessions.values():
        need(set(session['requests'])==set(range(1,8)),'source queue complete session')
        binding=None;transfers=[]
        for seq,h in sorted(session['requests'].items()):
            kind,q,_=frames[h];akind,a,_=frames[answers[h]];p=q['payload'];target=basis if seq<=3 else image
            transfer=p['id'];need(str(UUID(transfer))==transfer and UUID(transfer).int!=0,'source queue transfer UUID')
            if seq in (1,4):transfers.append(transfer)
            need(transfer==transfers[-1] and (len(transfers)!=2 or transfers[0]!=transfers[1]),'source queue transfer sequence')
            offset=CHUNK if seq==6 else 0
            expected_q=dict(id=transfer,digest=target) if seq in (3,7) else dict(id=transfer,action='REQUEST',offset=offset,digest=target,bytes='')
            need(kind==('TRANSFER_COMMIT' if seq in (3,7) else 'CHUNK') and p==expected_q,'source queue exact request')
            if seq in (1,4):expected_kind='SOURCE_OFFER';payload=dict(id=transfer,digest=target,bytes=len(contents[target]),kind='RECORD' if seq==1 else 'APPLICATION')
            elif seq in (3,7):expected_kind='TRANSFER_COMMIT';payload=p
            else:
                expected_kind='CHUNK';data=contents[target][offset:offset+CHUNK]
                payload=dict(id=transfer,action='DATA',offset=offset,digest=sha(data),bytes=base64.b64encode(data).decode('ascii'))
            need(akind==expected_kind and a['payload']==payload,'source queue original content bytes')
            if binding is None:binding=(q['root'],q['view'],q['ballot'],q['sender'],q['recipient'],q['trace'])
            need(binding==(q['root'],q['view'],q['ballot'],q['sender'],q['recipient'],q['trace']),'source queue unchanged session authority')
    # Bind every source response lifetime, including the reply that could not be sent.
    lives,_=source.lifetimes({'node-1':trace})
    actual={key[2]:life for key,life in lives.items() if key[1]=='source-response'}
    need(set(actual)==set(requests),'source queue complete cached response ownership')
    for h,life in actual.items():
        need(life['initial']==frames[answers[h]][2] and not life['growth'],'source queue cached allocation size')
    bindings={source.binding(requests[s['requests'][1]]) for s in sessions.values()}
    for role,extent in (('source-session',32768),('transfer-trace',1024)):
        owned={key[2]:life for key,life in lives.items() if key[1]==role}
        need(set(owned)==bindings and all(v['initial']==extent and not v['growth'] for v in owned.values()),
             'source queue original session ownership')
    # No synthetic CONTROL ballast may stand in for real buffered bytes.
    allowed={life['owner'] for life in lives.values()};exports=[];services=[]
    for changes in trace['changes']:
        if changes['event']!='RESERVE':continue
        for charge in changes['added']:
            if charge['unit']!='CONTROL':continue
            name=charge['owner']
            if name.startswith('source-export-'):
                need(re.fullmatch('source-export-'+value['basis']+'-[0-9a-f-]{36}',name) is not None and charge['bytes']==value['exportBytes'],
                     'source queue original export handle');exports.append(name)
            elif name.startswith('transfer-service-'):
                need(charge['bytes']==32768,'source queue service metadata');services.append(name)
            elif name not in allowed:
                need(any(name==prefix+c for c in connections for prefix in ('transport-request-read-','transport-response-send-')),
                     'source queue unexplained control charge')
    need(len(exports)==len(set(exports))==7 and len(services)==1,'source queue complete export handles')
    for name in exports+services:
        nonce=name[-36:]
        need(str(UUID(nonce))==nonce and UUID(nonce).int!=0,'source queue handle UUID')
    h,answer,at=failed[0];pressure=markers['PRESSURE'];drained=markers['DRAINED'];closed=markers['SERVICE_CLOSED']
    need(pressure['request']==h and at<pressure['sequence']<drained['sequence']<closed['sequence'],'source queue refusal and recovery order')
    need(frames[h][1]['sequence']==5,'source queue failed large chunk')
    held=[c for c in states[pressure['sequence']].values() if c['owner'].startswith('source-response-')]
    need(len(held)==6 and all(c['bytes']>=CHUNK for c in held),'source queue simultaneous original large caches')
    sends=[c for c in states[pressure['sequence']].values() if c['owner'].startswith('transport-response-send-')]
    need(len(sends)==5 and all(c['bytes']>=CHUNK for c in sends),'source queue simultaneous original send buffers')
    need([attempt[0]['request'] for attempt in attempts].count(h)==3,'source queue one identical recovered retry')
    retry=next(a for a in attempts if a[0]['request']==h and a[-1]['event']=='RETURN' and a[0]['sequence']>pressure['sequence'])
    need(pressure['sequence']<retry[0]['sequence']<drained['sequence'],'source queue retry after original release')
    need(drained['queued']<t.MIB and closed['queued']==0,'source queue released buffers')
    return dict(status='PASS',sessions=6,attempts=49,capacityRefusals=1,recoveredIdenticalRetries=1,
                maximumQueuedBytes=result['maximumObservedReservations']['queued'],queueLimit=LIMIT,
                phase3Complete=False,combinedResources=False)


NEGATIVES={
    'missing-event':'source queue complete events',
    'wrong-limit':'source queue frozen limit',
    'wrong-charge':'source queue checkpoint usage',
    'wrong-reason':'source queue classified capacity refusal',
    'missing-pressure':'source queue complete events',
    'changed-content':'source queue original content bytes',
    'wrong-retry':'source queue delivered original bytes',
    'wrong-response-extent':'resource transitions derived usage',
}

def qualify(value):
    original=replay(value);results=[]
    for name in NEGATIVES:
        changed=dict(value,events=copy.deepcopy(value['events']),trace=copy.deepcopy(value['trace']),frames=dict(value['frames']))
        if name=='missing-event':changed['events'].pop()
        elif name=='wrong-limit':changed['trace']['queueLimit']-=1
        elif name=='wrong-charge':changed['events'][0]['queued']+=1
        elif name=='wrong-reason':next(v for v in changed['events'] if v['event']=='SERVER_FAILED')['reason']='IO'
        elif name=='missing-pressure':changed['events']=[v for v in changed['events'] if v['event']!='PRESSURE']
        elif name=='changed-content':changed['contents']=dict(value['contents']);changed['contents'][value['image']]=b'x'+value['contents'][value['image']][1:]
        elif name=='wrong-retry':
            failed=next(v['request'] for v in changed['events'] if v['event']=='PRESSURE')
            next(v for v in reversed(changed['events']) if v['event']=='RETURN' and v['request']==failed)['response']=failed
        elif name=='wrong-response-extent':
            target=next(v for v in changed['trace']['changes'] if any(c['owner'].startswith('source-response-') for c in v['added']))
            target['added'][0]['bytes']-=1
        try:replay(changed)
        except ValueError as error:
            need(str(error)==NEGATIVES[name],'source queue negative reason drift: '+name)
            results.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('source queue negative accepted: '+name)
    return dict(original=original,negatives=results)


def main():
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');args=p.parse_args()
    value=load(args.directory);print(json.dumps(qualify(value) if args.qualify else replay(value),sort_keys=True))

if __name__=='__main__':main()
