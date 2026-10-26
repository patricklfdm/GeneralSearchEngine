"""Original-first replay of actual PROMISE transfer before a receiver's PREPARE.

The source-bound Java test supplies the real TCP/force-order observation. This
reader derives exact storage and wire bytes; it does not qualify full activation.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import source_exchange_evidence as transfer
from . import bootstrap_publication_evidence as b

e=b.e
c=b.c
load=transfer.x.load


def identifier(value):
    e.need(str(uuid.UUID(value))==value and uuid.UUID(value).int!=0,'record exchange UUID')


def case(root,size):
    e.need(root.is_dir() and not root.is_symlink(),'record exchange case directory')
    e.need({p.name for p in root.iterdir()}=={'original-plan.gsbp','original-application.image','initial','captured','after','received.gsr','prepare.json','wire.json','events.json'},'record exchange case inventory')
    before=b.original(root,size,False);_,initial,packet=c.current(before['node-1']);cap=packet['capsule'];r=cap['root']
    identities={n:e.f.decode(files['node.gsr'],'records','NODE')['identity'] for n,files in before.items()}
    ballot=dict(counter=2,proposer='node-1',incarnation=identities['node-1']['storage']);view=e.authority(r,cap['cut']['view'])
    granted={};promises={};bases={};ids=set()
    for node in ('node-1','node-2'):
        actual=c.inventory(root/('captured' if node=='node-1' else 'after')/node)
        prior=c.journal(before[node]['grants.gsr'],r,node);rows=c.journal(actual['grants.gsr'],r,node)
        e.need(rows[:len(prior)]==prior and [v[0] for v in rows[len(prior):]]==['PROMISE','BASIS'],'record exchange original grant sequence')
        promise,basis=rows[-2:];source_id=promise[2]['basisId'];identifier(source_id)
        e.need(source_id not in ids,'record exchange distinct original grants');ids.add(source_id)
        expected=dict(root=r,view=view,ballot=ballot,basisId=source_id)
        e.need(promise[2]==expected and basis[2]==dict(expected,voter=node,cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),inventory=e.digest(packet['indexBytes']),accepted=None),'record exchange exact original grant')
        promises[node]=promise[1];bases[node]=basis[1];prefix='sources/'+source_id
        files=dict(before[node],**{'grants.gsr':before[node]['grants.gsr']+promise[1]+basis[1],prefix:None,prefix+'/source.gscp':initial['source.gscp']})
        for digest in packet['images']:files[prefix+'/'+digest+'.image']=initial[digest+'.image']
        if node=='node-1':files['allocator.gsr']=e.f.encode('records','ALLOCATOR',dict(root=r,node=node,counter=2))
        granted[node]=files
    b.match(root,'captured',dict(before,**{'node-1':granted['node-1']}));b.match(root,'after',dict(before,**granted))
    raw=promises['node-1'];digest=e.digest(raw)
    e.need(b.t.plans.read(root/'received.gsr',8192)==raw,'record exchange received original promise')
    prepare=load(root/'prepare.json');e.need(set(prepare)=={'request','response'},'record exchange prepare row')
    kind,request=transfer.wire(prepare['request']);reply_kind,response=transfer.wire(prepare['response'])
    e.need((kind,reply_kind)==('PREPARE','PROMISE'),'record exchange prepare kinds');identifier(request['trace'])
    fields=dict(root=r,view=view,ballot=ballot,trace=request['trace'],sequence=1)
    e.need(request==dict(fields,sender=identities['node-1'],recipient=identities['node-2'],payload=dict(promise=digest))
           and response==dict(fields,sender=identities['node-2'],recipient=identities['node-1'],payload=dict(basis=e.digest(bases['node-2']))),'record exchange exact prepare')
    rows=load(root/'wire.json');position=0;trace=None

    def exchange(wanted,answer):
        nonlocal position,trace
        e.need(position<len(rows),'record exchange incomplete transcript');row=rows[position];position+=1
        e.need(set(row)=={'request','response'},'record exchange row')
        kind,request=transfer.wire(row['request']);reply_kind,response=transfer.wire(row['response'])
        e.need((kind,reply_kind)==(wanted,answer),'record exchange wire kinds')
        if trace is None:trace=request['trace'];identifier(trace)
        fields=dict(root=r,view=view,ballot=ballot,trace=trace,sequence=position)
        e.need({k:v for k,v in request.items() if k!='payload'}==dict(fields,sender=identities['node-2'],recipient=identities['node-1'])
               and {k:v for k,v in response.items() if k!='payload'}==dict(fields,sender=identities['node-1'],recipient=identities['node-2']),'record exchange exact correlation')
        return request['payload'],response['payload']

    request,offer=exchange('CHUNK','SOURCE_OFFER');tid=request['id'];identifier(tid)
    e.need(request==dict(id=tid,action='REQUEST',offset=0,digest=digest,bytes='')
           and offer==dict(id=tid,digest=digest,bytes=len(raw),kind='RECORD'),'record exchange exact offer')
    for offset in range(0,len(raw),128):
        request,response=exchange('CHUNK','CHUNK');part=raw[offset:offset+128]
        e.need(request==dict(id=tid,action='REQUEST',offset=offset,digest=digest,bytes='')
               and response==dict(id=tid,action='DATA',offset=offset,digest=e.digest(part),bytes=base64.b64encode(part).decode()),'record exchange exact data')
    request,response=exchange('TRANSFER_COMMIT','TRANSFER_COMMIT')
    e.need(request==response==dict(id=tid,digest=digest),'record exchange exact commit')
    e.need(position==len(rows),'record exchange complete transcript')
    events=load(root/'events.json');required=['record-validated','record-returned','PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN','prepare-replied']
    e.need(isinstance(events,list) and all(events.count(v)==1 for v in required)
           and [events.index(v) for v in required]==sorted(events.index(v) for v in required),'record exchange original before grant order')
    return dict(size=size,exchanges=position)


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'record exchange evidence directory')
    e.need({p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'record exchange complete inventory')
    cases=[case(root/f'stable-{size}',size) for size in (3,4,5)]
    wanted=dict(schema='gse-v53-record-exchange-v1',status='PASS',cases=cases,publicRuntime=False,network=True,scope='original-promise-before-prepare')
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(wanted),'record exchange scope/receipt');return wanted


def qualify(directory):
    original=validate(directory);results=[]
    variants=[('scope','record exchange scope/receipt'),('missing-profile','record exchange complete inventory'),
              ('changed-after','admitted exact after'),('received-substitute','record exchange received original promise'),
              ('prepare-reference','record exchange exact prepare'),('sequence','record exchange exact correlation'),
              ('foreign-identity','record exchange exact correlation'),('offer-digest','record exchange exact offer'),
              ('changed-data','record exchange exact data'),('commit-id','record exchange exact commit'),
              ('missing-commit','record exchange incomplete transcript'),('extra-transfer','record exchange complete transcript'),
              ('grant-before-record','record exchange original before grant order')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-record-exchange-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(directory,target);member=target/'stable-3'
            if name=='scope':
                value=load(target/'receipt.json');value['publicRuntime']=True;(target/'receipt.json').write_text(json.dumps(value))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name=='changed-after':(member/'after/node-3/allocator.gsr').write_bytes(b'changed')
            elif name=='received-substitute':(member/'received.gsr').write_bytes(b'changed')
            elif name=='grant-before-record':
                path=member/'events.json';value=load(path);value.remove('record-returned');value.append('record-returned');path.write_text(json.dumps(value))
            else:
                path=member/('prepare.json' if name=='prepare-reference' else 'wire.json');value=load(path);rows=[value] if isinstance(value,dict) else value
                if name=='missing-commit':rows.pop()
                elif name=='extra-transfer':rows.append(rows[0])
                else:
                    index=len(rows)-1 if name=='commit-id' else 1 if name=='changed-data' else 0;field='request' if name=='prepare-reference' else 'response'
                    kind,frame=transfer.wire(rows[index][field])
                    if name=='prepare-reference':frame['payload']['promise']='0'*64
                    elif name=='sequence':frame['sequence']+=1
                    elif name=='foreign-identity':frame['sender']['storage']=str(uuid.UUID(int=54))
                    elif name=='offer-digest':frame['payload']['digest']='0'*64
                    elif name=='changed-data':frame['payload']['bytes']=base64.b64encode(b'changed').decode();frame['payload']['digest']=e.digest(b'changed')
                    else:frame['payload']['id']=str(uuid.UUID(int=55))
                    rows[index][field]=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
                path.write_text(json.dumps(rows[0] if name=='prepare-reference' else rows))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'record exchange unrelated negative: '+name+': '+str(error))
            else:raise ValueError('record exchange accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else validate(a.directory),sort_keys=True))
