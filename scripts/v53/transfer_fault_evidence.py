"""Original-first replay of actual TCP loss and terminal transfer lifetimes.

Three immutable public-bootstrap sources; no process-death or membership-profile
claim. Injected clocks and observed resource counters stay explicitly labelled.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from . import source_exchange_evidence as exchange
from . import joining_history_run as history

x=exchange.x; e=x.e; c=x.c; f=e.f; need=e.need
CASES=('lost-offer','lost-data','lost-commit','exhausted-offer','expired-active','expired-completed',
       'closed-active','changed-completed','owner-closed-completed')


def load(path):
    def unique(rows):
        need(len(rows)==len(dict(rows)), 'transfer fault duplicate JSON key')
        return dict(rows)
    return json.loads(history.snapshot.s.regular(Path(path),e.MIB),object_pairs_hook=unique)


def source_order(rows,images):
    """Local callbacks are source-bound observations, not a crash qualification."""
    events=['CURRENT_'+v for v in ('VALIDATED','FILES_FORCED','GENERATION_FORCED','SELECTOR_FORCED','DIRECTORY_FORCED')]
    events+=['ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED']
    events+=['ALLOCATOR_'+v for v in ('BEFORE_WRITE','CREATED','WRITTEN','FORCED','RENAMED','DIRECTORY_FORCED','BEFORE_RETURN')]
    events+=['CURRENT_BEFORE_CAPTURE','PROMISE_BEFORE_WRITE','PROMISE_WRITTEN','PROMISE_FORCED']
    events+=['CAPTURE_INTENT_'+v for v in ('CREATED','PREFIX_WRITTEN','WRITTEN','FORCED','PARENT_FORCED')]
    events+=['SOURCE_BEFORE_CREATE','SOURCE_CREATED']
    events+=['SOURCE_PACKET_'+v for v in ('CREATED','PREFIX_WRITTEN','WRITTEN','FORCED')]
    events+=['SOURCE_IMAGE_'+v for _ in range(images) for v in ('CREATED','PREFIX_WRITTEN','WRITTEN','FORCED')]
    events+=['SOURCE_FILES_DIRECTORY_FORCED','SOURCE_DIRECTORY_FORCED']
    events+=['BASIS_'+v for v in ('BEFORE_WRITE','PREFIX_WRITTEN','WRITTEN','FORCED')]
    events+=['CAPTURE_INTENT_DELETED','CAPTURE_INTENT_CLEARED','GRANT_BEFORE_RETURN']
    need(rows==[dict(node='node-1',operation='transfer-fault-source',events=events)],'transfer fault original source force order')


def resource(value):
    need(type(value) is dict and set(value)=={'leases','metadata','staging','queued','counts'} and
         all(type(value[k]) is int and value[k]>=0 for k in ('leases','metadata','staging','queued')) and
         type(value['counts']) is dict and all(type(k) is str and type(v) is int and v>0 for k,v in value['counts'].items()) and
         sum(value['counts'].values())==value['leases'],'transfer fault resource observation shape')
    return value


def calls(events):
    """Require actual client/server boundaries, including dropped wire replies."""
    need(type(events) is list and len(events)<=1024 and all(type(v) is dict and type(v.get('event')) is str for v in events),
         'transfer fault event collection')
    attempts=[];controls=[];i=0
    while i<len(events):
        row=events[i];i+=1
        if row['event']!='CALL':
            need(row['event'] in ('OPEN','EXPIRE','CLOSE_SERVICE','CLOSE_OWNER','CHANGE_RETRY','RESET_CLOCK','BEFORE_CLOSE','AFTER_CLOSE'),
                 'transfer fault unbound observation');controls.append((len(attempts),row));continue
        request=row['request'];body=[]
        while i<len(events) and events[i]['event'] not in ('REPLY','FAILURE'):
            body.append(events[i]);i+=1
        need(i<len(events),'transfer fault missing attempt outcome');outcome=events[i];i+=1
        need(outcome['request']==request and all(v.get('request')==request for v in body),'transfer fault exact attempt request')
        reply=outcome['event']=='REPLY';dropped=any(v['event']=='DROP' for v in body)
        wanted=[('BEFORE_REQUEST_WRITE','client'),('AFTER_REQUEST_READ','server')]
        if reply or dropped:wanted.append(('BEFORE_RESPONSE_WRITE','server'))
        if dropped:wanted.append(('DROP',None))
        if reply:wanted.append(('AFTER_RESPONSE_READ','client'))
        need([(v['event'],v.get('side')) for v in body]==wanted and not (reply and dropped),'transfer fault TCP attempt order')
        responses=[v['response'] for v in body if 'response' in v]
        if reply:responses.append(outcome['response'])
        need(not responses or all(v==responses[0] for v in responses),'transfer fault exact attempted response')
        need(reply or outcome.get('reason')=='IO','transfer fault original IO outcome')
        attempts.append(dict(request=request,response=responses[0] if responses else None,reply=reply,drop=dropped,
                             expected=row['expected'],deadline=row['deadline']))
    return attempts,controls


def frames(raw,sender,recipient,basis):
    kind,value=exchange.wire(raw)
    wanted=dict(root=basis['root'],view=basis['view'],ballot=basis['ballot'],sender=sender,recipient=recipient)
    need(all(value[k]==v for k,v in wanted.items()),'transfer fault original correlation')
    need(str(uuid.UUID(value['trace']))==value['trace'] and uuid.UUID(value['trace']).int!=0,'transfer fault original trace')
    return kind,value


def scenario(root,name,source):
    promise,basis,sender,recipient=source;events=load(root/'events.json');attempts,controls=calls(events)
    need(attempts and controls and controls[0][0]==0 and controls[0][1]['event']=='OPEN','transfer fault original scope')
    opened=controls[0][1];started=opened['started'];budget=60*10**9
    need(type(started) is int and started>0 and opened==dict(event='OPEN',started=started,budget=budget,maximumAttempts=3,
         source=e.digest(basis[1])) and all(v['deadline']==started+budget for v in attempts),'transfer fault original deadline')
    _,first=frames(attempts[0]['request'],sender,recipient,basis[2]);trace=first['trace'];tid=first['payload']['id']
    need(str(uuid.UUID(tid))==tid and uuid.UUID(tid).int!=0,'transfer fault original transfer id')
    envelope={k:v for k,v in first.items() if k not in ('sequence','payload')};raw=promise[1];digest=e.digest(raw)
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
        a=dict(q,sender=recipient,recipient=sender,payload=apayload)
        expected.append((encoded(qkind,q),encoded(akind,a),akind))
    position=0;drops=0
    def consume(wanted,*,reply=True,drop=False):
        nonlocal position,drops
        need(position<len(attempts),'transfer fault incomplete attempt matrix');actual=attempts[position];position+=1
        frames(actual['request'],sender,recipient,basis[2])
        need(actual['request']==wanted[0] and actual['expected']==wanted[2],'transfer fault immutable original request')
        need(actual['reply']==reply and actual['drop']==drop,'transfer fault required delivery outcome')
        need(actual['response']==(wanted[1] if reply or drop else None),'transfer fault original response bytes')
        drops+=int(drop)
    if name=='exhausted-offer':
        for _ in range(3):consume(expected[0],reply=False,drop=True)
    else:
        selected=expected[:1] if name.endswith('-active') else expected
        lost={'lost-offer':0,'lost-data':1,'lost-commit':len(expected)-1}.get(name)
        for index,wanted in enumerate(selected):
            if index==lost:consume(wanted,reply=False,drop=True)
            consume(wanted)
    before=position;last=expected[0] if name.endswith('-active') else expected[-1]
    required=[(0,opened)]
    if name.startswith('expired'):
        required.append((position,dict(event='EXPIRE',offset=budget)));consume(last,reply=False)
        required.append((position,dict(event='RESET_CLOCK')));consume(last,reply=False)
    elif name in ('closed-active','owner-closed-completed'):
        required.append((position,dict(event='CLOSE_SERVICE' if name=='closed-active' else 'CLOSE_OWNER')));consume(last,reply=False)
    elif name=='changed-completed':
        required.append((position,dict(event='CHANGE_RETRY')))
        kind,value=exchange.wire(last[0]);value['payload']['digest']='0'*64
        consume((encoded(kind,value),None,kind),reply=False);consume(last,reply=False)
    need(position==len(attempts),'transfer fault complete attempt matrix')
    closed=name.startswith('expired') or name in ('closed-active','owner-closed-completed')
    usage=dict(traces=0 if closed else 1,live=int(name=='exhausted-offer'),calls=0,closed=closed)
    required += [(position,dict(event='BEFORE_CLOSE',usage=usage)),(position,dict(event='AFTER_CLOSE',usage=dict(traces=0,live=0,calls=0,closed=True)))]
    need(f.canonical(controls)==f.canonical(required),'transfer fault exact scope controls')
    result=load(root/'result.json')
    need(set(result)=={'case','status','drops','baseline','after','clientBaseline','clientAfter'} and
         result['case']==name and result['status']=='PASS' and type(result['drops']) is int and result['drops']==drops,
         'transfer fault observed result')
    empty=dict(leases=0,metadata=0,staging=0,queued=0,counts={})
    for key in ('baseline','after','clientBaseline','clientAfter'):resource(result[key])
    need(result['baseline']['leases']>0 and result['baseline']['counts'].get('SOURCE')==1,
         'transfer fault original owner resource observation')
    need(result['after']==(empty if name=='owner-closed-completed' else result['baseline']) and
         result['clientAfter']==result['clientBaseline']==empty,'transfer fault resource release observation')
    received=name!='exhausted-offer' and not name.endswith('-active')
    need({p.name for p in root.iterdir()}=={'events.json','result.json'}|({'record.gsr'} if received else set()),'transfer fault case inventory')
    if received:need((root/'record.gsr').read_bytes()==raw,'transfer fault original received record')
    return dict(case=name,attempts=position,droppedReplies=drops,received=received,terminalProbes=position-before)


def validate(directory):
    root=Path(directory);history.inventory(root)
    need({p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'transfer fault complete profile inventory')
    profiles=[];summaries=[]
    for size in (3,4,5):
        member=root/f'stable-{size}';x.case(member,size,additional=('cases','calls.json'))
        files=c.inventory(member/'captured/node-1');_,_,packet=c.current(files)
        source_order(load(member/'calls.json'),len(packet['images']))
        rows=c.journal(files['grants.gsr'],packet['capsule']['root'],'node-1');promise,basis=rows[-2:]
        sender=f.decode(c.inventory(member/'captured/node-2')['node.gsr'],'records','NODE')['identity']
        recipient=f.decode(files['node.gsr'],'records','NODE')['identity']
        need({p.name for p in (member/'cases').iterdir()}==set(CASES),'transfer fault complete case inventory')
        results=[scenario(member/'cases'/name,name,(promise,basis,sender,recipient)) for name in CASES]
        baselines=[load(member/'cases'/name/'result.json')['baseline'] for name in CASES]
        need(all(v==baselines[0] for v in baselines),'transfer fault continuous owner resource observation')
        profiles.append(dict(size=size,cases=results));summaries.append(dict(size=size,cases=[dict(case=name,size=size) for name in CASES]))
    need(f.canonical(load(root/'receipt.json'))==f.canonical(dict(schema='gse-v53-transfer-faults-v1',status='PASS',profiles=summaries,network=True,
                                      publicRuntime=False,phase3Complete=False)),'transfer fault exact matrix receipt')
    return dict(status='PASS',scope='original-public-bootstrap-TCP-transfer-faults',profiles=profiles,cases=27,
                faultInjectionClock='explicit-offset; not measured elapsed time',resourceCounts='source-bound observations',
                processDeathQualified=False,allMembershipProfilesQualified=False,phase3Complete=False)


NEGATIVES=(
    ('scope','transfer fault exact matrix receipt'),
    ('missing-profile','transfer fault complete profile inventory'),
    ('missing-case','transfer fault complete case inventory'),
    ('changed-after','admitted exact after: node-2'),
    ('changed-record','transfer fault original received record'),
    ('missing-drop','transfer fault TCP attempt order'),
    ('delivered-drop','transfer fault TCP attempt order'),
    ('foreign-sender','transfer fault original correlation'),
    ('extended-deadline','transfer fault original deadline'),
    ('raised-attempt-limit','transfer fault original deadline'),
    ('changed-response','transfer fault original response bytes'),
    ('changed-retry','transfer fault immutable original request'),
    ('extra-attempt','transfer fault complete attempt matrix'),
    ('wrong-drop-count','transfer fault observed result'),
    ('early-expiry','transfer fault exact scope controls'),
    ('missing-clock-reset','transfer fault exact scope controls'),
    ('missing-promise-force','transfer fault original source force order'),
    ('basis-before-force','transfer fault original source force order'),
    ('missing-source-image-force','transfer fault original source force order'),
    ('retained-live-export','transfer fault exact scope controls'),
    ('server-resource-leak','transfer fault resource release observation'),
    ('client-resource-leak','transfer fault resource release observation'),
    ('boolean-resource-count','transfer fault resource observation shape'),
    ('missing-owner-resources','transfer fault original owner resource observation'),
    ('changed-owner-lifetime','transfer fault continuous owner resource observation'),
)


def mutate(root,name):
    """Mutate one copied observation; never fabricate another native execution."""
    p=root/'stable-3';case=p/'cases/lost-offer'
    def edit(path,change):
        value=load(path);change(value);path.write_text(json.dumps(value))
    if name=='scope':edit(root/'receipt.json',lambda v:v.update(phase3Complete=True))
    elif name=='missing-profile':shutil.rmtree(root/'stable-5')
    elif name=='missing-case':shutil.rmtree(p/'cases/closed-active')
    elif name=='changed-after':(p/'after/node-2/allocator.gsr').write_bytes(b'changed')
    elif name=='changed-record':(case/'record.gsr').write_bytes(b'changed')
    elif name in ('missing-promise-force','basis-before-force','missing-source-image-force'):
        def force(rows):
            events=rows[0]['events']
            if name=='basis-before-force':
                i=events.index('BASIS_WRITTEN');j=events.index('BASIS_FORCED');events[i],events[j]=events[j],events[i]
            else:events.remove('PROMISE_FORCED' if name=='missing-promise-force' else 'SOURCE_IMAGE_FORCED')
        edit(p/'calls.json',force)
    elif name in ('wrong-drop-count','server-resource-leak','client-resource-leak','boolean-resource-count',
                  'missing-owner-resources','changed-owner-lifetime'):
        def result(v):
            if name=='wrong-drop-count':v['drops']+=1
            elif name=='server-resource-leak':v['after']['metadata']+=1
            elif name=='client-resource-leak':v['clientAfter']['metadata']+=1
            elif name=='boolean-resource-count':v['after']['leases']=True
            elif name=='missing-owner-resources':
                v['baseline']=copy.deepcopy(v['clientBaseline']);v['after']=copy.deepcopy(v['clientAfter'])
            else:v['baseline']['metadata']+=1;v['after']['metadata']+=1
        edit(case/'result.json',result)
    else:
        if name in ('early-expiry','missing-clock-reset'):case=p/'cases/expired-completed'
        path=case/'events.json';events=load(path)
        if name=='missing-drop':events[:]=[v for v in events if v['event']!='DROP']
        elif name=='delivered-drop':
            drop=next(v for v in events if v['event']=='DROP');failed=next(v for v in events if v['event']=='FAILURE')
            failed.update(event='REPLY',response=drop['response']);failed.pop('reason')
        elif name=='extended-deadline':next(v for v in events if v['event']=='CALL')['deadline']+=1
        elif name=='raised-attempt-limit':events[0]['maximumAttempts']=4
        elif name=='early-expiry':next(v for v in events if v['event']=='EXPIRE')['offset']-=1
        elif name=='missing-clock-reset':events[:]=[v for v in events if v['event']!='RESET_CLOCK']
        elif name=='retained-live-export':next(v for v in events if v['event']=='AFTER_CLOSE')['usage']['live']=1
        elif name=='extra-attempt':
            start=next(i for i,v in enumerate(events) if v['event']=='CALL')
            end=next(i for i,v in enumerate(events) if v['event']=='FAILURE')+1
            at=next(i for i,v in enumerate(events) if v['event']=='BEFORE_CLOSE');events[at:at]=copy.deepcopy(events[start:end])
        else:
            starts=[i for i,v in enumerate(events) if v['event']=='CALL']
            start=starts[1 if name=='changed-retry' else 0]
            end=next(i for i in range(start,len(events)) if events[i]['event'] in ('REPLY','FAILURE'))+1
            field='response' if name=='changed-response' else 'request'
            rows=[v for v in events[start:end] if field in v];kind,value=exchange.wire(rows[0][field])
            if name=='foreign-sender':value['sender']=copy.deepcopy(value['recipient'])
            elif name=='changed-response':value['payload']['digest']='0'*64
            elif name=='changed-retry':value['sequence']+=1
            else:raise ValueError('unknown transfer fault mutation: '+name)
            encoded=base64.b64encode(f.encode('wire',kind,value)).decode()
            for row in rows:row[field]=encoded
        path.write_text(json.dumps(events))


def qualify(directory):
    root=Path(directory);before=history.inventory(root)
    original=validate(root);results=[]
    need(history.inventory(root)==before,'transfer fault original modified')
    for name,reason in NEGATIVES:
        with tempfile.TemporaryDirectory(prefix='v53-transfer-fault-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(root,target);mutate(target,name)
            try:validate(target)
            except ValueError as error:
                need(str(error)==reason,'transfer fault unrelated negative: '+name+': '+str(error))
            else:raise ValueError('transfer fault accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
        need(history.inventory(root)==before,'transfer fault original modified')
    return dict(original=original,negatives=results,originalPreserved=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
