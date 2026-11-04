"""Replay native record replies revoked at the last handler boundary.

Original bootstrap/source bytes are authority; callback/resource observations are
not votes. Clock and local higher-ballot injections make no remote-election claim.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import transfer_fault_evidence as t
from . import transfer_reply_resources as resources

need=t.need; f=t.f; e=t.e; c=t.c; h=t.history; load=t.load
BOUNDARIES=('offer','data','commit','cached-commit')
FAULTS=('expiry','service-close','owner-close','higher-ballot')
CASES=tuple((size,boundary,fault) for size in (3,4,5) for boundary in BOUNDARIES for fault in FAULTS)
CLOSED=dict(traces=0,live=0,calls=0,closed=True)
EMPTY=dict(leases=0,metadata=0,staging=0,queued=0,counts={})
SCHEMA='gse-v53-transfer-reply-lifetime-v2'


def same(actual,expected,reason):
    # Canonical bytes also distinguish bool from int.
    need(f.canonical(actual)==f.canonical(expected),reason)


def identifier(value):
    try:valid=type(value) is str and str(uuid.UUID(value))==value and uuid.UUID(value).int!=0
    except (ValueError,AttributeError):valid=False
    need(valid,'reply lifetime original UUID')


def replay_events(events,promise,basis,sender,recipient,boundary,fault):
    need(type(events) is list and 1<=len(events)<=1024 and all(type(v) is dict for v in events),'reply lifetime event collection')
    position=0;attempts=0
    def take(event):
        nonlocal position
        need(position<len(events) and events[position].get('event')==event,'reply lifetime event order: '+event)
        row=events[position];position+=1;return row
    opened=take('OPEN');started=opened.get('started');budget=60*10**9
    need(type(started) is int and started>0,'reply lifetime original clock')
    same(opened,dict(event='OPEN',started=started,budget=budget,source=e.digest(basis[1])),'reply lifetime original scope')
    need(position<len(events) and events[position].get('event')=='CALL','reply lifetime first request')
    _,first=t.frames(events[position]['request'],sender,recipient,basis[2]);trace=first['trace'];tid=first['payload']['id']
    identifier(trace);identifier(tid)
    envelope=dict(root=basis[2]['root'],view=basis[2]['view'],ballot=basis[2]['ballot'],sender=sender,recipient=recipient,trace=trace)
    raw=promise[1];digest=e.digest(raw)
    logical=[('CHUNK',dict(id=tid,action='REQUEST',offset=0,digest=digest,bytes=''),'SOURCE_OFFER',dict(id=tid,digest=digest,bytes=len(raw),kind='RECORD'))]
    for offset in range(0,len(raw),1024):
        part=raw[offset:offset+1024]
        logical.append(('CHUNK',dict(id=tid,action='REQUEST',offset=offset,digest=digest,bytes=''),'CHUNK',
                        dict(id=tid,action='DATA',offset=offset,digest=e.digest(part),bytes=base64.b64encode(part).decode())))
    logical.append(('TRANSFER_COMMIT',dict(id=tid,digest=digest),'TRANSFER_COMMIT',dict(id=tid,digest=digest)))
    encoded=lambda kind,value:base64.b64encode(f.encode('wire',kind,value)).decode()
    expected=[]
    for index,(qkind,qpayload,akind,apayload) in enumerate(logical,1):
        q=dict(envelope,sequence=index,payload=qpayload)
        expected.append((encoded(qkind,q),encoded(akind,dict(q,sender=recipient,recipient=sender,payload=apayload)),akind))
    if boundary=='cached-commit':expected.append(expected[-1])
    stop={'offer':0,'data':1}.get(boundary,len(expected)-1)
    def attempt(wanted,*,materialized,revoked=False,success=False):
        nonlocal attempts
        attempts+=1;q,a,kind=wanted
        same(take('CALL'),dict(event='CALL',request=q,expected=kind,deadline=started+budget),'reply lifetime original request/deadline')
        for event,side in (('BEFORE_REQUEST_WRITE','client'),('AFTER_REQUEST_READ','server')):
            same(take(event),dict(event=event,side=side,request=q),'reply lifetime TCP request boundary')
        if materialized:
            live=int(kind!='TRANSFER_COMMIT')
            same(take('MATERIALIZED'),dict(event='MATERIALIZED',request=q,response=a,usage=dict(traces=1,live=live,calls=1,closed=False)),
                 'reply lifetime original materialized response')
        if revoked:
            same(take('REVOKE'),dict(event='REVOKE',request=q,fault=fault),'reply lifetime exact revocation')
            if fault=='expiry':same(take('CLOCK_OFFSET'),dict(event='CLOCK_OFFSET',offset=budget),'reply lifetime exact expiry injection')
            if fault=='higher-ballot':
                higher=dict(basis[2]['ballot'],counter=basis[2]['ballot']['counter']+1)
                same(take('OBSERVED_BALLOT'),dict(event='OBSERVED_BALLOT',ballot=higher),'reply lifetime actual higher observation')
            same(take('REVOKED'),dict(event='REVOKED',request=q),'reply lifetime revocation completed before return')
        if success:
            for event,side in (('BEFORE_RESPONSE_WRITE','server'),('AFTER_RESPONSE_READ','client')):
                same(take(event),dict(event=event,side=side,request=q,response=a),'reply lifetime exact delivered response')
            same(take('REPLY'),dict(event='REPLY',request=q,response=a),'reply lifetime exact client reply')
        else:
            same(take('FAILURE'),dict(event='FAILURE',request=q,reason='IO'),'reply lifetime refused response')
    for i in range(stop+1):attempt(expected[i],materialized=True,revoked=i==stop,success=i<stop)
    drained=take('DRAINED');same(drained.get('usage'),CLOSED,'reply lifetime terminal scope')
    need(set(drained)=={'event','usage','resources'},'reply lifetime drained observation')
    t.resource(drained['resources'])
    if fault=='expiry':same(take('RESET_CLOCK'),dict(event='RESET_CLOCK',offset=0),'reply lifetime reset cannot revive')
    attempt(expected[stop],materialized=False)
    same(take('FRESH_TRACE'),dict(event='FRESH_TRACE'),'reply lifetime new trace probe')
    need(position<len(events) and events[position].get('event')=='CALL','reply lifetime new trace request')
    kind,q=t.frames(events[position]['request'],sender,recipient,basis[2]);identifier(q['trace'])
    need(q['trace']!=trace,'reply lifetime fresh trace must differ')
    newq=dict(envelope,trace=q['trace'],sequence=1,payload=logical[0][1])
    attempt((encoded('CHUNK',newq),None,'SOURCE_OFFER'),materialized=False)
    same(take('AFTER_PROBES'),dict(event='AFTER_PROBES',usage=CLOSED),'reply lifetime no scope revival')
    resources=take('RESOURCES')
    need(set(resources)=={'event','baseline','after','clientAfter'},'reply lifetime resource observations')
    for key in ('baseline','after','clientAfter'):t.resource(resources[key])
    baseline=resources['baseline']
    need(baseline['leases']>0 and baseline['counts'].get('SOURCE')==1,'reply lifetime actual owner baseline')
    same(resources['after'],EMPTY if fault=='owner-close' else baseline,'reply lifetime owner resource release')
    same(drained['resources'],resources['after'],'reply lifetime immediate resource release')
    same(resources['clientAfter'],EMPTY,'reply lifetime client resource release')
    same(take('CLOSED'),dict(event='CLOSED',resources=EMPTY,clientResources=EMPTY),'reply lifetime final resource release')
    need(position==len(events),'reply lifetime extra observations')
    return dict(attempts=attempts,materialized=stop+1,delivered=stop,refused=3)


def scenario(root,size,boundary,fault):
    need({p.name for p in root.iterdir()}=={'source','after','calls.json','events.json','transport-resources.json','result.json'},'reply lifetime case inventory')
    t.x.case(root/'source',size)
    files=c.inventory(root/'source/captured/node-1');_,_,packet=c.current(files)
    t.source_order(load(root/'calls.json'),len(packet['images']))
    expected={f'node-{n}':c.inventory(root/f'source/captured/node-{n}') for n in range(1,size+1)}
    t.x.b.match(root,'after',expected)
    promise,basis=c.journal(files['grants.gsr'],packet['capsule']['root'],'node-1')[-2:]
    sender=f.decode(expected['node-2']['node.gsr'],'records','NODE')['identity']
    recipient=f.decode(files['node.gsr'],'records','NODE')['identity']
    events=load(root/'events.json')
    result=replay_events(events,promise,basis,sender,recipient,boundary,fault)
    result['resources']=resources.replay(load(root/'transport-resources.json'),events,resources.baseline(files,basis[2]),len(promise[1]),fault)
    same(load(root/'result.json'),dict(size=size,boundary=boundary,fault=fault,status='PASS'),'reply lifetime observed case result')
    return dict(size=size,boundary=boundary,fault=fault,**result)


def validate(directory):
    root=Path(directory);h.inventory(root)
    names=[f'{size}-{boundary}-{fault}' for size,boundary,fault in CASES]
    need({p.name for p in root.iterdir()}==set(names)|{'receipt.json'},'reply lifetime complete matrix inventory')
    rows=[];results=[]
    for name,(size,boundary,fault) in zip(names,CASES):
        results.append(scenario(root/name,size,boundary,fault));rows.append(dict(case=name,size=size,boundary=boundary,fault=fault))
    same(load(root/'receipt.json'),dict(schema=SCHEMA,status='PASS',cases=rows,publicRuntime=False,phase3Complete=False),
         'reply lifetime exact matrix receipt')
    return dict(status='PASS',cases=results,caseCount=len(results),scope='native-PROMISE-export-pre-return-revocation',
                clockInjection='explicit-offset',higherBallotInjection='local-native-owner-observation',
                remoteElectionQualified=False,allExportKindsQualified=False,phase3Complete=False)


NEGATIVES={
    'missing-case':'reply lifetime complete matrix inventory',
    'scope':'reply lifetime exact matrix receipt',
    'changed-source':'source export exact complete bytes',
    'changed-after':'admitted exact after: node-2',
    'missing-force':'transfer fault original source force order',
    'missing-materialized':'reply lifetime event order: MATERIALIZED',
    'changed-materialized':'reply lifetime original materialized response',
    'cached-live-export':'reply lifetime original materialized response',
    'late-response':'reply lifetime event order: FAILURE',
    'missing-revoke':'reply lifetime event order: REVOKE',
    'wrong-fault':'reply lifetime exact revocation',
    'missing-revoked':'reply lifetime event order: REVOKED',
    'early-expiry':'reply lifetime exact expiry injection',
    'missing-clock-reset':'reply lifetime event order: RESET_CLOCK',
    'non-higher-ballot':'reply lifetime actual higher observation',
    'extended-deadline':'reply lifetime original request/deadline',
    'foreign-request':'transfer fault original correlation',
    'changed-delivered':'reply lifetime exact delivered response',
    'failed-retry-kind':'reply lifetime refused response',
    'revived-retry':'reply lifetime event order: FAILURE',
    'same-fresh-trace':'reply lifetime fresh trace must differ',
    'missing-new-trace':'reply lifetime event order: FRESH_TRACE',
    'retained-scope':'reply lifetime terminal scope',
    'immediate-leak':'reply lifetime immediate resource release',
    'owner-leak':'reply lifetime owner resource release',
    'client-leak':'reply lifetime client resource release',
    'final-leak':'reply lifetime final resource release',
    'boolean-resource':'transfer fault resource observation shape',
    'wrong-result':'reply lifetime observed case result',
    'extra-event':'reply lifetime extra observations',
    'resource-missing-file':'reply lifetime case inventory',
    'resource-schema':'reply resources observation shape',
    'resource-missing-boundary':'reply resources exact boundary inventory',
    'resource-foreign-boundary':'reply resources exact boundary inventory',
    'resource-outgoing-request':'reply resources outgoing request charge',
    'resource-received-request':'reply resources received request charge',
    'resource-materialized':'reply resources materialized reply charge',
    'resource-server-response':'reply resources outgoing reply charge',
    'resource-client-response':'reply resources incoming reply charge',
    'resource-cached-double-charge':'reply resources materialized reply charge',
    'resource-storage-released':'reply resources materialized reply charge',
    'resource-boolean-count':'reply resources outgoing request charge',
    'resource-invented-baseline':'reply resources original owner baseline',
    'resource-closed-owner':'reply resources received request charge',
}


def mutate(root,name):
    need(name in NEGATIVES,'reply lifetime unknown negative');case=root/'3-offer-expiry'
    def edit(path,change):
        value=load(path);change(value);path.write_bytes(f.canonical(value))
    if name.startswith('resource-'):
        if name=='resource-missing-file':(case/'transport-resources.json').unlink();return
        if name=='resource-invented-baseline':
            rows=load(case/'events.json')
            for row in rows:
                if row['event']=='RESOURCES':
                    row['baseline']['metadata']+=1;row['after']['metadata']+=1
                elif row['event']=='DRAINED':row['resources']['metadata']+=1
            (case/'events.json').write_bytes(f.canonical(rows));return
        if name=='resource-cached-double-charge':case=root/'3-cached-commit-service-close'
        if name in ('resource-server-response','resource-client-response'):case=root/'3-commit-service-close'
        if name=='resource-closed-owner':case=root/'3-offer-owner-close'
        path=case/'transport-resources.json';value=load(path);rows=value['rows']
        if name=='resource-schema':value['schema']='unknown'
        elif name=='resource-missing-boundary':rows.pop()
        elif name=='resource-foreign-boundary':rows[0]['side']='server'
        else:
            point={'resource-outgoing-request':'BEFORE_REQUEST_WRITE','resource-received-request':'AFTER_REQUEST_READ',
                   'resource-materialized':'TRANSFER_BEFORE_REPLY','resource-server-response':'BEFORE_RESPONSE_WRITE',
                   'resource-client-response':'AFTER_RESPONSE_READ','resource-cached-double-charge':'TRANSFER_BEFORE_REPLY',
                   'resource-storage-released':'TRANSFER_BEFORE_REPLY','resource-boolean-count':'BEFORE_REQUEST_WRITE',
                   'resource-closed-owner':'AFTER_REQUEST_READ'}[name]
            candidates=[row for row in rows if row['event']==point];row=candidates[-1 if name in ('resource-cached-double-charge','resource-closed-owner') else 0]
            if name=='resource-boolean-count':row['resources']['counts']['CONTROL']=True
            elif name=='resource-storage-released':row['resources']['metadata']-=1
            elif name=='resource-cached-double-charge':
                offer=next(t.exchange.wire(v['response'])[1] for v in rows if 'response' in v and t.exchange.wire(v['response'])[0]=='SOURCE_OFFER')
                row['resources']['queued']+=32768+offer['payload']['bytes']
                row['resources']['counts']['CONTROL']+=2;row['resources']['leases']+=2
            else:row['resources']['queued']+=1
        path.write_bytes(f.canonical(value));return
    if name=='missing-case':shutil.rmtree(root/'5-cached-commit-higher-ballot');return
    if name=='scope':edit(root/'receipt.json',lambda v:v.update(phase3Complete=True));return
    if name=='changed-source':next((case/'source/exported').iterdir()).write_bytes(b'changed');return
    if name=='changed-after':(case/'after/node-2/allocator.gsr').write_bytes(b'changed');return
    if name=='missing-force':edit(case/'calls.json',lambda v:v[0]['events'].remove('PROMISE_FORCED'));return
    if name=='wrong-result':edit(case/'result.json',lambda v:v.update(status='FAIL'));return
    if name=='cached-live-export':case=root/'3-cached-commit-service-close'
    if name=='changed-delivered':case=root/'3-commit-service-close'
    if name=='non-higher-ballot':case=root/'3-offer-higher-ballot'
    rows=load(case/'events.json')
    def row(event,index=0):return [v for v in rows if v['event']==event][index]
    if name.startswith('missing-'):
        event={'missing-materialized':'MATERIALIZED','missing-revoke':'REVOKE','missing-revoked':'REVOKED',
               'missing-clock-reset':'RESET_CLOCK','missing-new-trace':'FRESH_TRACE'}[name];rows.remove(row(event))
    elif name in ('changed-materialized','changed-delivered'):
        v=row('MATERIALIZED' if name=='changed-materialized' else 'BEFORE_RESPONSE_WRITE');kind,value=t.exchange.wire(v['response']);value['payload']['digest']='0'*64
        v['response']=base64.b64encode(f.encode('wire',kind,value)).decode()
    elif name=='cached-live-export':row('MATERIALIZED',-1)['usage']['live']=1
    elif name=='late-response':
        materialized=row('MATERIALIZED');rows.insert(rows.index(row('FAILURE')),dict(event='BEFORE_RESPONSE_WRITE',side='server',request=materialized['request'],response=materialized['response']))
    elif name=='wrong-fault':row('REVOKE')['fault']='owner-close'
    elif name=='early-expiry':row('CLOCK_OFFSET')['offset']-=1
    elif name=='non-higher-ballot':row('OBSERVED_BALLOT')['ballot']['counter']-=1
    elif name=='extended-deadline':row('CALL')['deadline']+=1
    elif name=='foreign-request':
        v=row('CALL');kind,value=t.exchange.wire(v['request']);value['sender']=copy.deepcopy(value['recipient']);v['request']=base64.b64encode(f.encode('wire',kind,value)).decode()
    elif name=='failed-retry-kind':row('FAILURE',1)['reason']='TIMEOUT'
    elif name=='revived-retry':
        at=rows.index(row('FAILURE',1));rows.insert(at,copy.deepcopy(row('MATERIALIZED')))
    elif name=='same-fresh-trace':
        first=t.exchange.wire(row('CALL')['request'])[1];v=row('CALL',-1);kind,q=t.exchange.wire(v['request']);q['trace']=first['trace'];v['request']=base64.b64encode(f.encode('wire',kind,q)).decode()
    elif name=='retained-scope':row('DRAINED')['usage']['live']=1
    elif name=='immediate-leak':row('DRAINED')['resources']['metadata']+=1
    elif name=='owner-leak':row('RESOURCES')['after']['metadata']+=1
    elif name=='client-leak':row('RESOURCES')['clientAfter']['metadata']+=1
    elif name=='final-leak':row('CLOSED')['resources']['metadata']+=1
    elif name=='boolean-resource':row('DRAINED')['resources']['leases']=True
    elif name=='extra-event':rows.append(dict(event='CLOSED'))
    else:raise ValueError('reply lifetime mutation unimplemented: '+name)
    (case/'events.json').write_bytes(f.canonical(rows))


def qualify(directory):
    root=Path(directory);before=h.inventory(root);original=validate(root);results=[]
    need(h.inventory(root)==before,'reply lifetime original changed')
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-reply-lifetime-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target);mutate(target,name)
            try:validate(target)
            except ValueError as error:need(str(error)==reason,'reply lifetime unrelated negative '+name+': '+str(error))
            else:raise ValueError('reply lifetime accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        need(h.inventory(root)==before,'reply lifetime original changed')
    return dict(original=original,negatives=results,originalPreserved=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else validate(a.directory),sort_keys=True))
