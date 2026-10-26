"""Replay complete source-delivery bytes and every ordered wire exchange independently.

The actual TCP execution observation is supplied by the bound Java test. This
reader does not create remote Owned observations or qualify distributed activation.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import source_export_evidence as x

e=x.e
c=x.c


def wire(value):
    raw=base64.b64decode(value,validate=True)
    e.need(len(raw)>=48,'source exchange frame header')
    identifier=int.from_bytes(raw[8:10],'big')
    kinds={v['id']:k for k,v in e.f.catalog()['wire'].items()}
    e.need(identifier in kinds,'source exchange frame kind')
    kind=kinds[identifier]
    return kind,e.f.decode(raw,'wire',kind)


def case(root,size):
    x.case(root,size,additional=('received','wire.json'))
    files=c.inventory(root/'captured/node-1');_,_,packet=c.current(files);r=packet['capsule']['root']
    grants=c.journal(files['grants.gsr'],r,'node-1');promise,basis=grants[-2:]
    prefix='sources/'+basis[2]['basisId']+'/'
    source={k.removeprefix(prefix):v for k,v in files.items() if k.startswith(prefix)}
    e.need(c.inventory(root/'received')==source,'source exchange exact scratch')
    sender=e.f.decode(c.inventory(root/'captured/node-2')['node.gsr'],'records','NODE')['identity']
    recipient=e.f.decode(files['node.gsr'],'records','NODE')['identity']
    expected=[(e.digest(basis[1]),basis[1],'RECORD'),(e.digest(promise[1]),promise[1],'RECORD'),
              (basis[2]['capsule'],source['source.gscp'],'CAPSULE')]
    expected += [(name[:-6],raw,'APPLICATION') for name,raw in sorted(source.items()) if name.endswith('.image')]
    rows=x.load(root/'wire.json');position=0;trace=None;identifiers=set()

    def exchange(request_kind,response_kind):
        nonlocal position,trace
        e.need(position<len(rows),'source exchange incomplete transcript')
        row=rows[position];position+=1;e.need(set(row)=={'request','response'},'source exchange row')
        before,request=wire(row['request']);after,response=wire(row['response'])
        e.need(before==request_kind and after==response_kind,'source exchange wire kinds')
        if trace is None:
            trace=request['trace'];e.need(str(uuid.UUID(trace))==trace and uuid.UUID(trace).int!=0,'source exchange session UUID')
        fields=dict(root=r,view=basis[2]['view'],ballot=basis[2]['ballot'],trace=trace,sequence=position)
        e.need({k:v for k,v in request.items() if k!='payload'}==dict(fields,sender=sender,recipient=recipient)
               and {k:v for k,v in response.items() if k!='payload'}==dict(fields,sender=recipient,recipient=sender),'source exchange exact correlation')
        return request['payload'],response['payload']

    for reference,raw,kind in expected:
        request,offer=exchange('CHUNK','SOURCE_OFFER');identifier=request['id']
        e.need(identifier not in identifiers,'source exchange unique transfer');identifiers.add(identifier)
        e.need(request==dict(id=identifier,action='REQUEST',offset=0,digest=reference,bytes=''),'source exchange exact request')
        digest=e.digest(raw)
        e.need(offer==dict(id=identifier,digest=digest,bytes=len(raw),kind=kind),'source exchange exact offer')
        offset=0
        while offset<len(raw):
            request,response=exchange('CHUNK','CHUNK');part=raw[offset:offset+1024]
            e.need(request==dict(id=identifier,action='REQUEST',offset=offset,digest=digest,bytes=''),'source exchange exact request')
            e.need(response==dict(id=identifier,action='DATA',offset=offset,digest=e.digest(part),bytes=base64.b64encode(part).decode()),'source exchange exact data')
            offset+=len(part)
        request,response=exchange('TRANSFER_COMMIT','TRANSFER_COMMIT')
        e.need(request==response==dict(id=identifier,digest=digest),'source exchange exact commit')
    e.need(position==len(rows),'source exchange complete transcript')
    return dict(size=size,exchanges=position)


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'source exchange evidence directory')
    e.need({p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'source exchange complete inventory')
    cases=[case(root/f'stable-{size}',size) for size in (3,4,5)]
    wanted=dict(schema='gse-v53-source-exchange-v1',status='PASS',cases=cases,publicRuntime=False,network=True,scope='complete-original-source-delivery')
    e.need(e.f.canonical(x.load(root/'receipt.json'))==e.f.canonical(wanted),'source exchange scope/receipt')
    return wanted


def qualify(directory):
    original=validate(directory);results=[]
    variants=[('scope','source exchange scope/receipt'),('missing-profile','source exchange complete inventory'),
              ('changed-authority','admitted exact after'),('changed-scratch','source exchange exact scratch'),
              ('missing-offer','source exchange wire kinds'),('sequence','source exchange exact correlation'),
              ('foreign-identity','source exchange exact correlation'),('offer-digest','source exchange exact offer'),
              ('packet-reference','source exchange exact request'),('changed-data','source exchange exact data'),
              ('commit-id','source exchange exact commit'),('missing-commit','source exchange incomplete transcript'),
              ('extra-transfer','source exchange complete transcript')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-source-exchange-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(directory,target);member=target/'stable-3'
            if name=='scope':
                v=x.load(target/'receipt.json');v['publicRuntime']=True;(target/'receipt.json').write_text(json.dumps(v))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name=='changed-authority':(member/'after/node-1/allocator.gsr').write_bytes(b'changed')
            elif name=='changed-scratch':next((member/'received').glob('*.image')).write_bytes(b'changed')
            else:
                path=member/'wire.json';rows=x.load(path)
                if name=='missing-offer':rows.pop(0)
                elif name=='missing-commit':rows.pop()
                elif name=='extra-transfer':rows.append(rows[0])
                else:
                    index=0;field='response'
                    if name=='packet-reference':
                        index=next(i for i,row in enumerate(rows) if wire(row['response'])[0]=='SOURCE_OFFER' and wire(row['response'])[1]['payload']['kind']=='CAPSULE');field='request'
                    elif name=='changed-data':index=next(i for i,row in enumerate(rows) if wire(row['response'])[0]=='CHUNK')
                    elif name=='commit-id':index=len(rows)-1
                    kind,value=wire(rows[index][field])
                    if name=='sequence':value['sequence']+=1
                    elif name=='foreign-identity':value['sender']['storage']=str(uuid.UUID(int=53))
                    elif name in ('offer-digest','packet-reference'):value['payload']['digest']='0'*64
                    elif name=='changed-data':
                        value['payload']['bytes']=base64.b64encode(b'changed').decode();value['payload']['digest']=e.digest(b'changed')
                    else:value['payload']['id']=str(uuid.UUID(int=54))
                    rows[index][field]=base64.b64encode(e.f.encode('wire',kind,value)).decode()
                path.write_text(json.dumps(rows))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'source exchange unrelated negative: '+name+': '+str(error))
            else:raise ValueError('source exchange accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else validate(a.directory),sort_keys=True))
