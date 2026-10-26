"""Original-first replay of two actual peers using one runtime transfer registry.

Exact physical/wire bytes are independently reconstructed. Session lifetime is
an observation of the source-bound Java test, not remote voting authority.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import source_exchange_evidence as transfer

e=transfer.e
c=transfer.c
load=transfer.x.load


def case(root,size):
    source=transfer.case(root,size,additional=('record-wire.json','record.gsr','lifetime.json'))
    files=c.inventory(root/'captured/node-1');_,_,packet=c.current(files);r=packet['capsule']['root']
    promise,basis=c.journal(files['grants.gsr'],r,'node-1')[-2:];raw=promise[1];digest=e.digest(raw)
    e.need(transfer.x.b.t.plans.read(root/'record.gsr',8192)==raw,'transfer service original record')
    sender=e.f.decode(c.inventory(root/'captured/node-3')['node.gsr'],'records','NODE')['identity']
    recipient=e.f.decode(files['node.gsr'],'records','NODE')['identity']
    rows=load(root/'record-wire.json');position=0;trace=None

    def exchange(wanted,answer):
        nonlocal position,trace
        e.need(position<len(rows),'transfer service incomplete record transcript')
        row=rows[position];position+=1;e.need(set(row)=={'request','response'},'transfer service record row')
        kind,request=transfer.wire(row['request']);reply_kind,response=transfer.wire(row['response'])
        e.need((kind,reply_kind)==(wanted,answer),'transfer service record wire kinds')
        if trace is None:
            trace=request['trace'];e.need(str(uuid.UUID(trace))==trace and uuid.UUID(trace).int!=0,'transfer service session UUID')
        fields=dict(root=r,view=basis[2]['view'],ballot=basis[2]['ballot'],trace=trace,sequence=position)
        e.need({k:v for k,v in request.items() if k!='payload'}==dict(fields,sender=sender,recipient=recipient)
               and {k:v for k,v in response.items() if k!='payload'}==dict(fields,sender=recipient,recipient=sender),'transfer service exact record correlation')
        return request['payload'],response['payload']

    request,offer=exchange('CHUNK','SOURCE_OFFER');tid=request['id']
    e.need(str(uuid.UUID(tid))==tid and uuid.UUID(tid).int!=0,'transfer service transfer UUID')
    e.need(request==dict(id=tid,action='REQUEST',offset=0,digest=digest,bytes='')
           and offer==dict(id=tid,digest=digest,bytes=len(raw),kind='RECORD'),'transfer service exact record offer')
    for offset in range(0,len(raw),1024):
        request,response=exchange('CHUNK','CHUNK');part=raw[offset:offset+1024]
        e.need(request==dict(id=tid,action='REQUEST',offset=offset,digest=digest,bytes='')
               and response==dict(id=tid,action='DATA',offset=offset,digest=e.digest(part),bytes=base64.b64encode(part).decode()),'transfer service exact record data')
    request,response=exchange('TRANSFER_COMMIT','TRANSFER_COMMIT')
    e.need(request==response==dict(id=tid,digest=digest),'transfer service exact record commit')
    e.need(position==len(rows),'transfer service complete record transcript')
    wanted=dict(beforeClose=dict(traces=2,live=2,calls=0,closed=False),afterClose=dict(traces=0,live=0,calls=0,closed=True))
    e.need(e.f.canonical(load(root/'lifetime.json'))==e.f.canonical(wanted),'transfer service observed lifetime')
    return dict(size=size,sourceExchanges=source['exchanges'],recordExchanges=position)


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'transfer service evidence directory')
    e.need({p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'transfer service complete inventory')
    cases=[case(root/f'stable-{size}',size) for size in (3,4,5)]
    wanted=dict(schema='gse-v53-transfer-service-v1',status='PASS',cases=cases,publicRuntime=False,network=True,scope='runtime-scoped-transfer-dispatch')
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(wanted),'transfer service scope/receipt');return wanted


def qualify(directory):
    original=validate(directory);results=[]
    variants=[('scope','transfer service scope/receipt'),('missing-profile','transfer service complete inventory'),
              ('changed-authority','admitted exact after'),('changed-scratch','source exchange exact scratch'),
              ('source-identity','source exchange exact correlation'),('received-substitute','transfer service original record'),
              ('sequence','transfer service exact record correlation'),('foreign-identity','transfer service exact record correlation'),
              ('swapped-peer','transfer service exact record correlation'),('offer-digest','transfer service exact record offer'),
              ('changed-data','transfer service exact record data'),('commit-id','transfer service exact record commit'),
              ('missing-commit','transfer service incomplete record transcript'),('extra-transfer','transfer service complete record transcript'),
              ('live-after-close','transfer service observed lifetime')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-transfer-service-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(directory,target);member=target/'stable-3'
            if name=='scope':
                value=load(target/'receipt.json');value['publicRuntime']=True;(target/'receipt.json').write_text(json.dumps(value))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name=='changed-authority':(member/'after/node-2/allocator.gsr').write_bytes(b'changed')
            elif name=='changed-scratch':next((member/'received').glob('*.image')).write_bytes(b'changed')
            elif name=='received-substitute':(member/'record.gsr').write_bytes(b'changed')
            elif name=='live-after-close':
                path=member/'lifetime.json';value=load(path);value['afterClose']['live']=1;path.write_text(json.dumps(value))
            else:
                path=member/('wire.json' if name=='source-identity' else 'record-wire.json');rows=load(path)
                if name=='missing-commit':rows.pop()
                elif name=='extra-transfer':rows.append(rows[0])
                else:
                    index=len(rows)-1 if name=='commit-id' else 1 if name=='changed-data' else 0
                    kind,frame=transfer.wire(rows[index]['response'])
                    if name=='sequence':frame['sequence']+=1
                    elif name in ('foreign-identity','source-identity'):frame['sender']['storage']=str(uuid.UUID(int=54))
                    elif name=='swapped-peer':frame['recipient']=e.f.decode(c.inventory(member/'captured/node-2')['node.gsr'],'records','NODE')['identity']
                    elif name=='offer-digest':frame['payload']['digest']='0'*64
                    elif name=='changed-data':frame['payload']['bytes']=base64.b64encode(b'changed').decode();frame['payload']['digest']=e.digest(b'changed')
                    else:frame['payload']['id']=str(uuid.UUID(int=55))
                    rows[index]['response']=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
                path.write_text(json.dumps(rows))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'transfer service unrelated negative: '+name+': '+str(error))
            else:raise ValueError('transfer service accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else validate(a.directory),sort_keys=True))
