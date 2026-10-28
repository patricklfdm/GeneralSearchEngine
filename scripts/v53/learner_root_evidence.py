"""Independent ROOT-discovery replay; not a complete learner admission gate."""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import tempfile
from scripts.v53 import authority_transition_evidence as a
from scripts.v53 import source_exchange_evidence as exchange

b,c,d,e,f,need=a.b,a.c,a.d,a.e,a.f,a.need
VOTERS=('node-1','node-2')


def physical(root,*,before='before-learner-discovery',after='after-learner-discovery'):
    group=d.s.initialize(b.original(root,3,False))
    group={n:dict(v,**{d.future.FILE:d.future.frame(d.future.initial(v),{})}) for n,v in group.items()}
    b.match(root,'before-network',group)
    _,_,installed=d.s.campaign(root,{n:group[n] for n in VOTERS},2,'installed',selected_prefix=d.slot.prefix)
    group=dict(group,**installed);b.match(root,'installed',group)
    need((root/'selected.gsr').read_bytes()==c.current(group['node-1'])[1]['selected.gsr'],'learner root original selection')
    model=a.NativeSlot.__new__(a.NativeSlot)
    model.root=root;model.group=group;model.active=list(VOTERS);model.voters=VOTERS
    model.required=set();model.slot=0;model.counter=2;model.first=None;model.observed=set();model.phases={};model.documents=[]
    original_root=f.decode(group['node-1']['root.gsr'],'records','ROOT');model.history=original_root['historyId']
    supplied=e.parse((root/'learner-reserve-payload.bin').read_bytes());request=supplied['request']
    for kind,command in [('BARRIER',None),('RESERVE',supplied),('CANCEL',dict(number=1))]:
        model.group=a.maintenance(model.group,VOTERS);model.publish(kind,command)
        if kind=='RESERVE':
            b.match(root,before,model.group)
            b.match(root,after,model.group)
            reserved=copy.deepcopy(model.group)
    b.match(root,'after-close',model.group)
    _,_,packet=c.current(reserved['node-1']);catalog=f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG')
    need(set(supplied)=={'request'} and request==catalog['results'][0]['request'] and request['kind']=='ADD'
         and request['number']==1 and len(request['target'])==4 and catalog['active']==1
         and catalog['results'][0]['phase']=='RESERVED','learner root original reservation')
    joining=[v for v in request['target'] if v['node'] not in VOTERS and v['node']!='node-3']
    need(len(joining)==1 and joining[0]['node']=='node-4','learner root new permanent identity')
    return reserved,request,joining[0]


def network(root,reserved,request,learner):
    server=d.read(root/'wire.json');received=d.read(root/'learner-root-wire.json')
    need(type(server) is list and len(server)<=32768 and type(received) is list and len(received)<=128,'learner root bounded trace')
    original=reserved['node-1']['root.gsr'];digest=e.digest(original);rows=[]
    alias=e.digest(f.canonical(dict(schema='gse-v53-learner-root-reference/1.3',root=request['root'],learner=learner,request=request)))
    for row in server:
        kind,frame=exchange.wire(row['request'])
        if frame['sender']['node']==learner['node']:
            need(set(row)=={'request','response','withheld'} and type(row['withheld']) is bool,'learner root original server trace')
            rows.append((row,kind,frame))
    need(rows,'learner root missing server trace');peers=[];received_expected=[];offset=0
    for node in VOTERS:
        identity=d.future.identity(reserved[node]);part=[]
        while offset<len(rows) and rows[offset][2]['recipient']==identity:
            part.append(rows[offset]);offset+=1
        need(part,'learner root original peer scope');seen={};ordered=[]
        for row,kind,frame in part:
            sequence=frame['sequence'];scope=tuple(frame[k] if isinstance(frame[k],str) else f.canonical(frame[k]) for k in ('root','view','ballot','trace','sender','recipient'))
            need(frame['root']==request['root'] and frame['view']==request['expected'] and frame['sender']==learner
                 and frame['ballot']==dict(counter=1,proposer=learner['node'],incarnation=learner['storage']),
                 'learner root exact correlation')
            response_kind,response=exchange.wire(row['response'])
            need({k:v for k,v in response.items() if k!='payload'}==dict({k:v for k,v in frame.items() if k!='payload'},sender=identity,recipient=learner),
                 'learner root exact reply correlation')
            if sequence in seen:
                previous,count=seen[sequence];need(previous['request']==row['request'] and previous['response']==row['response'] and count<3,
                                                   'learner root identical bounded retry');seen[sequence]=(row,count+1)
            else:
                need(sequence==len(ordered)+1 and (not ordered or scope==ordered[0][4]),'learner root exact sequence')
                seen[sequence]=(row,1);ordered.append((kind,frame['payload'],response_kind,response['payload'],scope))
            if not row['withheld']:received_expected.append({k:row[k] for k in ('request','response')})
        need(sum(row['withheld'] for row,_,_ in part)==1 and len(part)==len(ordered)+1,'learner root one actual lost reply')
        need(len(ordered)>=3,'learner root complete exchange')
        kind,offer_request,reply_kind,offer,_=ordered[0];identifier=offer_request['id']
        need(kind=='CHUNK' and reply_kind=='SOURCE_OFFER' and offer_request==dict(action='REQUEST',id=identifier,offset=0,digest=alias,bytes='')
             and offer==dict(id=identifier,digest=digest,bytes=len(original),kind='RECORD'),'learner root exact original offer')
        position=0
        for kind,chunk,reply_kind,data,_ in ordered[1:-1]:
            need(kind==reply_kind=='CHUNK' and chunk==dict(action='REQUEST',id=identifier,offset=position,digest=digest,bytes=''),
                 'learner root exact chunk request')
            raw=base64.b64decode(data['bytes'],validate=True)
            need(0<len(raw)<=len(original)-position and data==dict(action='DATA',id=identifier,offset=position,digest=e.digest(raw),bytes=base64.b64encode(raw).decode())
                 and original[position:position+len(raw)]==raw,'learner root exact original bytes');position+=len(raw)
        kind,commit,reply_kind,reply,_=ordered[-1]
        need(position==len(original) and kind==reply_kind=='TRANSFER_COMMIT' and commit==reply==dict(id=identifier,digest=digest),
             'learner root exact complete transfer')
        peers.append(node)
    need(offset==len(rows) and received==received_expected,'learner root exact received replies')
    return dict(peers=peers,receivedExchanges=len(received),lostReplies=2)


def validate(root):
    root=Path(root);need(root.is_dir() and not root.is_symlink(),'learner root regular evidence');total=0
    for count,path in enumerate(root.rglob('*'),1):
        need(not path.is_symlink() and (path.is_file() or path.is_dir()),'learner root regular evidence')
        if path.is_file():total+=path.stat().st_size
        need(count<=65536 and total<=512*e.MIB,'learner root evidence capacity')
    expected={'original-plan.gsbp','original-application.image','initial','before-network','installed','selected.gsr',
              'before-learner-discovery','after-learner-discovery','after-close','calls.json','events.json','wire.json','failures.json',
              'learner-reserve-payload.bin','learner-root-wire.json','learner-root-result.json'}
    expected|={f'{stage}-{i}' for stage in ('applied','published') for i in (1,2,3)}
    b.selection.layout(root,expected,'learner root')
    reserved,request,learner=physical(root);result=network(root,reserved,request,learner)
    need(d.read(root/'learner-root-result.json')==dict(status='PASS',scope='native-reservation-root-discovery',voter=False,materialized=False,publicReady=False,phase3Complete=False),
         'learner root result scope')
    return dict(status='PASS',scope='native-reservation-root-discovery',**result,physicalQualification=True,
                fullNetworkQualification=False,learnerAdmissionQualified=False,phase3Complete=False)


NEGATIVES={
    'extra-file':'context selection learner root inventory',
    'missing-original-reservation':'admitted exact before-learner-discovery: node-1',
    'changed-during-read':'admitted exact after-learner-discovery: node-1',
    'false-public-ready':'learner root result scope',
    'missing-client-receipt':'learner root exact received replies',
    'false-loss':'learner root one actual lost reply',
    'different-retry':'learner root identical bounded retry',
    'changed-original-chunk':'learner root exact original bytes',
    'foreign-peer':'learner root exact reply correlation',
}


def qualify(root):
    root=Path(root);original=validate(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-learner-root-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target)
            if name=='extra-file':(target/'extra').write_bytes(b'extra')
            elif name in ('missing-original-reservation','changed-during-read'):
                stage='before-learner-discovery' if name=='missing-original-reservation' else 'after-learner-discovery'
                (target/stage/'node-1/selector.gsr').write_bytes(b'changed')
            elif name=='false-public-ready':
                p=target/'learner-root-result.json';v=d.read(p);v['publicReady']=True;p.write_bytes(f.canonical(v))
            elif name=='missing-client-receipt':
                p=target/'learner-root-wire.json';v=d.read(p);v.pop();p.write_bytes(f.canonical(v))
            else:
                p=target/'wire.json';rows=d.read(p)
                scoped=[i for i,v in enumerate(rows) if exchange.wire(v['request'])[1]['sender']['node']=='node-4']
                if name=='false-loss':
                    row=next(rows[i] for i in scoped if rows[i]['withheld']);row['withheld']=False
                else:
                    if name=='different-retry':
                        lost=next(i for i in scoped if rows[i]['withheld'])
                        index=next(i for i in scoped if i>lost and rows[i]['request']==rows[lost]['request'])
                    else:index=next(i for i in scoped if exchange.wire(rows[i]['response'])[0]=='CHUNK')
                    row=rows[index];kind,value=exchange.wire(row['response'])
                    if name=='different-retry':value['payload']['digest']='0'*64
                    elif name=='foreign-peer':value['sender']['storage']='00000000-0000-0000-0000-000000000053'
                    elif name=='changed-original-chunk':
                        raw=bytearray(base64.b64decode(value['payload']['bytes']));raw[-1]^=1
                        value['payload']['bytes']=base64.b64encode(raw).decode();value['payload']['digest']=e.digest(raw)
                    else:raise ValueError('unknown learner negative '+name)
                    row['response']=base64.b64encode(f.encode('wire',kind,value)).decode()
                p.write_bytes(f.canonical(rows))
            try:validate(target)
            except ValueError as error:need(str(error)==reason,'learner root unrelated negative: '+name+': '+str(error))
            else:raise ValueError('learner root accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--qualify',action='store_true');args=p.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(Path(args.root))))
