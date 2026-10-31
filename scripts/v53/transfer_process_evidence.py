"""Original donor TCP process cuts and same-disk restart, never membership closure."""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile

from . import transfer_fault_evidence as fault

x,e,c,f,need,load=fault.x,fault.e,fault.c,fault.f,fault.need,fault.load
POINTS=('SOURCE_OFFER','CHUNK','TRANSFER_COMMIT')
PROFILES=tuple(dict(size=size,point=point,mode=mode) for size in (3,4,5) for point in POINTS for mode in ('halt','kill'))
EMPTY=dict(counts={},leases=0,metadata=0,queued=0,staging=0)
RECOVERY=('CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED',
          'CURRENT_DIRECTORY_FORCED','ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED')


def name(profile):return f"{profile['size']}-{profile['point']}-{profile['mode']}"


def pipe(path):
    def unique(rows):
        need(len(rows)==len(dict(rows)),'transfer process duplicate pipe key');return dict(rows)
    raw=fault.history.snapshot.s.regular(path,4*e.MIB)
    return [json.loads(line,object_pairs_hook=unique) for line in raw.splitlines()]


def sequence(first,source):
    promise,basis,sender,recipient=source
    _,q=fault.frames(first,sender,recipient,basis[2]);tid=q['payload']['id'];envelope={k:v for k,v in q.items() if k not in ('sequence','payload')}
    need(str(fault.uuid.UUID(tid))==tid and fault.uuid.UUID(tid).int!=0,'transfer process original transfer id')
    raw=promise[1];digest=e.digest(raw);logical=[('CHUNK',dict(id=tid,action='REQUEST',offset=0,digest=digest,bytes=''),
        'SOURCE_OFFER',dict(id=tid,digest=digest,bytes=len(raw),kind='RECORD'))]
    for offset in range(0,len(raw),1024):
        part=raw[offset:offset+1024];logical.append(('CHUNK',dict(id=tid,action='REQUEST',offset=offset,digest=digest,bytes=''),
            'CHUNK',dict(id=tid,action='DATA',offset=offset,digest=e.digest(part),bytes=base64.b64encode(part).decode())))
    logical.append(('TRANSFER_COMMIT',dict(id=tid,digest=digest),'TRANSFER_COMMIT',dict(id=tid,digest=digest)))
    encode=lambda k,v:base64.b64encode(f.encode('wire',k,v)).decode();result=[]
    for index,(kind,payload,answer,body) in enumerate(logical,1):
        request=dict(envelope,sequence=index,payload=payload);response=dict(request,sender=recipient,recipient=sender,payload=body)
        result.append((encode(kind,request),encode(answer,response),answer))
    return result,q['trace'],tid


def attempts(rows):
    result=[];i=0
    while i<len(rows):
        at=i;row=rows[i];i+=1
        if row['event']!='CALL':
            need(row['event'] not in ('REPLY','FAILURE','CLIENT_WIRE','SERVER_WIRE'),'transfer process unbound exchange');continue
        q=row['value'];need(set(q)=={'request','expected','deadline'},'transfer process call shape');wire=[];positions=[]
        while i<len(rows) and rows[i]['event'] not in ('REPLY','FAILURE'):
            v=rows[i];i+=1
            if v['event'] in ('CLIENT_WIRE','SERVER_WIRE'):
                wire.append(dict(v['value'],side='client' if v['event']=='CLIENT_WIRE' else 'server'))
                positions.append(i-1)
            else:need(v['event'] in ('SERVER_cut','LOCK_HELD'),'transfer process observation inside attempt')
        need(i<len(rows),'transfer process incomplete attempt');terminal=rows[i];i+=1;outcome=terminal['value']
        reply=terminal['event']=='REPLY'
        need(set(outcome)=={'request','response' if reply else 'reason'} and outcome['request']==q['request'] and
             all(v.get('request')==q['request'] for v in wire),'transfer process exact attempt request')
        need(reply or outcome['reason']=='IO','transfer process original IO failure')
        result.append(dict(q,reply=reply,wire=wire,wirePositions=positions,start=at,end=i-1,outcome=outcome))
    return result


def exchange(actual,wanted,kind):
    need(actual['request']==wanted[0] and actual['expected']==wanted[2],'transfer process immutable request')
    observed=[(v['side'],v['event']) for v in actual['wire']]
    prefix=[('client','BEFORE_REQUEST_WRITE'),('server','AFTER_REQUEST_READ'),('server','BEFORE_RESPONSE_WRITE')]
    if kind=='success':need(actual['reply'] and observed==prefix+[('client','AFTER_RESPONSE_READ')],'transfer process successful TCP order')
    elif kind=='cut':need(not actual['reply'] and observed==prefix,'transfer process interrupted TCP order')
    else:need(not actual['reply'] and observed in ([],prefix[:1]),'transfer process dead donor retry order')
    responses=[]
    for row in actual['wire']:
        responds=row['event'] in ('BEFORE_RESPONSE_WRITE','AFTER_RESPONSE_READ')
        need(set(row)=={'side','event','request'}|({'response'} if responds else set()),'transfer process wire shape')
        if responds:responses.append(row['response'])
    if actual['reply']:responses.append(actual['outcome']['response'])
    need(all(v==wanted[1] for v in responses),'transfer process original response bytes')


def lifecycle(root,life,rows,profile,process,source):
    promise,basis,_,_=source;pid=process['children'][life-1]['pid']
    need(rows and rows[0]==dict(event='SERVER_STARTED',life=life,value=dict(life=life,pid=pid)),
         'transfer process original worker start')
    controls=[(i,v['event'],v['value']) for i,v in enumerate(rows) if v['event'] not in ('CALL','REPLY','FAILURE','CLIENT_WIRE','SERVER_WIRE')]
    names=['SERVER_STARTED']+['SERVER_STORE']*len(RECOVERY)+['SERVER_OPEN','PULL_OPEN']
    names+=['SERVER_cut','LOCK_HELD'] if life==1 else ['SERVER_CLOSED']
    names+=['EXIT','LOCK_RELEASED','CLIENT_RELEASED']
    need([event for _,event,_ in controls]==names and [value for _,event,value in controls if event=='SERVER_STORE']==list(RECOVERY),
         'transfer process exact worker lifecycle')
    opened=controls[1+len(RECOVERY)][2];pull=controls[2+len(RECOVERY)][2]
    budget=60*10**9
    need(type(opened.get('started')) is int and opened['started']>0 and opened==dict(started=opened['started'],budget=budget,
         promise=e.digest(promise[1]),basis=e.digest(basis[1])),'transfer process retained source binding')
    need(type(pull.get('started')) is int and pull['started']>0 and pull==dict(started=pull['started'],budget=budget),
         'transfer process original pull scope')
    calls=attempts(rows);need(calls and controls[2+len(RECOVERY)][0]<calls[0]['start'],'transfer process pull before exchange')
    need(all(v['deadline']==pull['started']+budget for v in calls),'transfer process original deadline')
    expected,trace,tid=sequence(calls[0]['request'],source)
    if life==1:
        cut=next(i for i,v in enumerate(expected) if v[2]==profile['point'])
        need(len(calls)==cut+3,'transfer process bounded failed attempts')
        for actual,wanted in zip(calls[:cut],expected[:cut]):exchange(actual,wanted,'success')
        exchange(calls[cut],expected[cut],'cut')
        for actual in calls[cut+1:]:exchange(actual,expected[cut],'dead')
        marker,held=controls[-5:-3]
        need(marker[2]==dict(mode=profile['mode'],name=profile['point'],pid=pid) and held[2]==pid and
             calls[cut]['wirePositions'][-1]<marker[0]<held[0]<calls[cut]['end'],'transfer process exact held cut')
    else:
        need(len(calls)==len(expected),'transfer process complete resumed transfer')
        for actual,wanted in zip(calls,expected):exchange(actual,wanted,'success')
        closed=controls[-4];fault.resource(closed[2]);need(closed[2]==EMPTY and calls[-1]['end']<closed[0],'transfer process resumed drain')
    fault.resource(controls[-1][2])
    need(controls[-3][2]==dict(pid=pid,exit=process['children'][life-1]['exit']) and calls[-1]['end']<controls[-3][0] and
         controls[-2][2]==pid and controls[-1][2]==EMPTY,'transfer process death release observations')
    # Pipe observations must equal the retained original stdout, not summaries.
    path=root/f'life-{life}'
    need({p.name for p in path.iterdir()}=={'stdout','stderr'}|({'stop.request'} if life==2 else set()),'transfer process worker inventory')
    need((path/'stderr').read_bytes()==b'','transfer process worker stderr')
    if life==2:need((path/'stop.request').read_bytes()==b'stop\n','transfer process explicit resume stop')
    output=pipe(path/'stdout')
    wanted=[dict(action=v['event'].removeprefix('SERVER_'),value=v['value']) for v in rows if v['event'].startswith('SERVER_')]
    need(output==wanted,'transfer process original pipe observations')
    return dict(life=life,attempts=len(calls),trace=trace,transfer=tid)


def process_identity(value,profile):
    need(type(value) is dict and set(value)=={'size','point','mode','parentPid','children','status','phase3Complete'},'transfer process receipt shape')
    children=value['children'];need(type(children) is list and len(children)==2 and all(type(v) is dict and set(v)=={'life','pid','exit'} for v in children),
                                  'transfer process child inventory')
    pids=[value['parentPid']]+[v['pid'] for v in children]
    need(all(type(v) is int and v>0 for v in pids) and len(set(pids))==3,'transfer process distinct workers')
    expected=dict(profile,parentPid=pids[0],children=[dict(life=1,pid=pids[1],exit=73 if profile['mode']=='halt' else 137),
                  dict(life=2,pid=pids[2],exit=0)],status='PASS',phase3Complete=False)
    need(f.canonical(value)==f.canonical(expected),'transfer process exact exit receipt')


def case(root,profile):
    need({p.name for p in root.iterdir()}=={'history','spec.json','events.json','process.json','record.gsr','life-1','life-2'},'transfer process case inventory')
    raw=root/'history';size=profile['size'];x.case(raw,size,additional=('calls.json','interrupted'))
    captured={f'node-{i}':c.inventory(raw/'captured'/f'node-{i}') for i in range(1,size+1)}
    x.b.match(raw,'interrupted',captured);files=captured['node-1'];_,_,packet=c.current(files)
    fault.source_order(load(raw/'calls.json'),len(packet['images']))
    promise,basis=c.journal(files['grants.gsr'],packet['capsule']['root'],'node-1')[-2:]
    identities=[f.decode(captured[node]['node.gsr'],'records','NODE')['identity'] for node in ('node-2','node-1')]
    plan=x.b.t.plans.decode((raw/'original-plan.gsbp').read_bytes(),(raw/'original-application.image').read_bytes(),details=True,size=size,source='EMPTY')['plan']
    paths=plan['descriptor']['paths'];need(load(root/'spec.json')==dict(replica=paths[1]['path'],application=paths[2]['path'],
         mode=profile['mode'],point=profile['point']),'transfer process original path binding')
    process=load(root/'process.json');process_identity(process,profile)
    rows=load(root/'events.json')
    need(type(rows) is list and rows and len(rows)<=2048 and all(type(v) is dict and set(v)=={'event','life','value'} and
         type(v['event']) is str and type(v['life']) is int and v['life'] in (1,2) for v in rows),'transfer process event inventory')
    need([v['life'] for v in rows]==sorted(v['life'] for v in rows),'transfer process original lifetime order')
    lives=[lifecycle(root,life,[v for v in rows if v['life']==life],profile,process,(promise,basis,*identities)) for life in (1,2)]
    need(lives[0]['trace']!=lives[1]['trace'] and lives[0]['transfer']!=lives[1]['transfer'],'transfer process fresh resumed transfer')
    need((root/'record.gsr').read_bytes()==promise[1],'transfer process original received bytes')
    return dict(profile=profile,attempts=sum(v['attempts'] for v in lives),processes=2,interruptedReplies=1,
                originalSourcePreserved=True,status='PASS')


def validate(directory):
    root=Path(directory);fault.history.inventory(root)
    need({p.name for p in root.iterdir()}=={'receipt.json'}|{name(v) for v in PROFILES},'transfer process complete matrix inventory')
    need(f.canonical(load(root/'receipt.json'))==f.canonical(dict(schema='gse-v53-transfer-process-v1',status='PASS',cases=list(PROFILES),
         completeMatrix=True,phase3Complete=False)),'transfer process exact matrix receipt')
    results=[case(root/name(profile),profile) for profile in PROFILES]
    return dict(status='PASS',scope='original-donor-TCP-halt-SIGKILL-reopen',cases=results,processes=36,interruptedReplies=18,
                transferProcessQualified=True,allMembershipProfilesQualified=False,completePhysicalQualified=False,
                forceAndNetworkQualified=False,phase3Complete=False,powerLossQualified=False)


NEGATIVES=(
    ('scope','transfer process exact matrix receipt'),
    ('missing-case','transfer process complete matrix inventory'),
    ('changed-interrupted','admitted exact interrupted: node-2'),
    ('changed-after','admitted exact after: node-1'),
    ('changed-record','transfer process original received bytes'),
    ('foreign-path','transfer process original path binding'),
    ('same-pid','transfer process distinct workers'),
    ('wrong-exit','transfer process exact exit receipt'),
    ('missing-recovery-force','transfer process exact worker lifecycle'),
    ('missing-lock','transfer process exact worker lifecycle'),
    ('cut-before-response','transfer process exact held cut'),
    ('changed-source','transfer process retained source binding'),
    ('extended-deadline','transfer process original deadline'),
    ('changed-retry','transfer process immutable request'),
    ('changed-response','transfer process original response bytes'),
    ('delivered-after-cut','transfer process interrupted TCP order'),
    ('non-io-failure','transfer process original IO failure'),
    ('missing-send','transfer process successful TCP order'),
    ('reused-transfer','transfer process fresh resumed transfer'),
    ('client-leak','transfer process death release observations'),
    ('server-leak','transfer process resumed drain'),
    ('missing-original-stdout','transfer process original pipe observations'),
    ('changed-stop','transfer process explicit resume stop'),
)


def mutate(root,variant):
    p=root/name(PROFILES[0]);raw=p/'history'
    def edit(path,change):
        value=load(path);change(value);path.write_text(json.dumps(value))
    if variant=='scope':edit(root/'receipt.json',lambda v:v.update(phase3Complete=True))
    elif variant=='missing-case':shutil.rmtree(root/name(PROFILES[-1]))
    elif variant in ('changed-interrupted','changed-after'):
        stage,node=('interrupted','node-2') if variant=='changed-interrupted' else ('after','node-1')
        (raw/stage/node/'allocator.gsr').write_bytes(b'changed')
    elif variant=='changed-record':(p/'record.gsr').write_bytes(b'changed')
    elif variant=='foreign-path':edit(p/'spec.json',lambda v:v.update(replica='/foreign/original'))
    elif variant=='same-pid':edit(p/'process.json',lambda v:v['children'][1].update(pid=v['children'][0]['pid']))
    elif variant=='wrong-exit':edit(p/'process.json',lambda v:v['children'][0].update(exit=0))
    elif variant=='missing-original-stdout':
        path=p/'life-1/stdout';path.write_text('\n'.join(path.read_text().splitlines()[1:])+'\n')
    elif variant=='changed-stop':(p/'life-2/stop.request').write_bytes(b'wrong\n')
    else:
        rows=load(p/'events.json')
        find=lambda event,life=1:next(v for v in rows if v['event']==event and v['life']==life)
        if variant=='missing-recovery-force':rows.remove(next(v for v in rows if v['event']=='SERVER_STORE' and v['value']=='CURRENT_FILES_FORCED'))
        elif variant=='missing-lock':rows.remove(find('LOCK_HELD'))
        elif variant=='cut-before-response':
            cut,held=find('SERVER_cut'),find('LOCK_HELD');rows.remove(cut);rows.remove(held);i=rows.index(find('CALL'))+1;rows[i:i]=[cut,held]
        elif variant=='changed-source':find('SERVER_OPEN')['value']['basis']='0'*64
        elif variant=='extended-deadline':find('CALL')['value']['deadline']+=1
        elif variant=='changed-retry':
            call=[v for v in rows if v['event']=='CALL' and v['life']==1][1];start=rows.index(call)
            end=next(i for i in range(start,len(rows)) if rows[i]['event']=='FAILURE')
            kind,value=fault.exchange.wire(call['value']['request']);value['sequence']+=1
            encoded=base64.b64encode(f.encode('wire',kind,value)).decode()
            for row in rows[start:end+1]:
                if type(row['value']) is dict and 'request' in row['value']:row['value']['request']=encoded
        elif variant=='changed-response':find('REPLY',2)['value']['response']='changed'
        elif variant=='delivered-after-cut':
            value=find('FAILURE')['value'];value.pop('reason');value['response']='changed';find('FAILURE')['event']='REPLY'
        elif variant=='non-io-failure':find('FAILURE')['value']['reason']='DEADLINE'
        elif variant=='missing-send':rows.remove(next(v for v in rows if v['life']==2 and v['event']=='CLIENT_WIRE' and v['value']['event']=='BEFORE_REQUEST_WRITE'))
        elif variant in ('client-leak','server-leak'):find('CLIENT_RELEASED' if variant=='client-leak' else 'SERVER_CLOSED',2)['value']['metadata']=1
        elif variant=='reused-transfer':
            _,old=fault.exchange.wire(find('CALL')['value']['request'])
            for row in rows:
                if row['life']!=2 or row['event'] not in ('CALL','REPLY','FAILURE','CLIENT_WIRE','SERVER_WIRE'):continue
                for key in ('request','response'):
                    if key not in row['value']:continue
                    kind,value=fault.exchange.wire(row['value'][key]);value['trace']=old['trace'];value['payload']['id']=old['payload']['id']
                    row['value'][key]=base64.b64encode(f.encode('wire',kind,value)).decode()
            output=[dict(action=v['event'].removeprefix('SERVER_'),value=v['value']) for v in rows if v['life']==2 and v['event'].startswith('SERVER_')]
            (p/'life-2/stdout').write_text(''.join(json.dumps(v)+'\n' for v in output))
        else:raise ValueError('unknown transfer process mutation: '+variant)
        (p/'events.json').write_text(json.dumps(rows))


def qualify(directory):
    root=Path(directory);before=fault.history.inventory(root);original=validate(root);results=[]
    need(fault.history.inventory(root)==before,'transfer process original modified')
    for variant,reason in NEGATIVES:
        with tempfile.TemporaryDirectory(prefix='v53-transfer-process-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(root,target);mutate(target,variant)
            try:validate(target)
            except ValueError as error:need(str(error)==reason,'transfer process unrelated negative: '+variant+': '+str(error))
            else:raise ValueError('transfer process accepted negative: '+variant)
            results.append(dict(case=variant,reason=reason,status='REJECTED'))
        need(fault.history.inventory(root)==before,'transfer process original modified')
    return dict(original=original,negatives=results,originalPreserved=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
