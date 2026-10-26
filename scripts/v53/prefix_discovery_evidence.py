"""Reconstruct published authority before checking read-only current-prefix TCP bytes.

No download creates historical force observations. Conditional cross-view fixture
checks are separate Java tests, not relabelled as distributed transition evidence.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import bootstrap_publication_evidence as b
from .source_exchange_evidence import wire
from .transport_evidence import load

e=b.e


def transcript(rows,group):
    e.need(len(rows)>1,'prefix transcript incomplete')
    sender=e.f.decode(group['node-1']['node.gsr'],'records','NODE')['identity']
    recipient=e.f.decode(group['node-2']['node.gsr'],'records','NODE')['identity']
    _,local,local_packet=b.c.current(group['node-1']);_,source,packet=b.c.current(group['node-2'])
    cap=packet['capsule'];fields=dict(root=cap['root'],view=e.authority(local_packet['capsule']['root'],local_packet['capsule']['cut']['view']),
                                    ballot=e.f.decode(local['selected.gsr'],'records','SELECTED')['ballot'])
    e.need(set(rows[0])=={'request','response'},'prefix wire row')
    query,reply=wire(rows[0]['request']),wire(rows[0]['response']);q=query[1];r=reply[1]
    nonce=q['payload']['nonce'];status_trace=q['trace']
    e.need(str(uuid.UUID(nonce))==nonce and uuid.UUID(nonce).int!=0 and str(uuid.UUID(status_trace))==status_trace and uuid.UUID(status_trace).int!=0,'prefix discovery nonce')
    e.need(query[0]=='STATUS_PROBE' and reply[0]=='STATUS' and q==dict(fields,sender=sender,recipient=recipient,trace=status_trace,sequence=1,payload=dict(nonce=nonce))
           and r==dict(fields,sender=recipient,recipient=sender,trace=status_trace,sequence=1,payload=dict(nonce=nonce,cut=cap['cut'],ready=False)),
           'prefix discovery original cut')
    position=1;trace=None;identifiers=set()
    def exchange(before_kind,after_kind):
        nonlocal position,trace
        e.need(position<len(rows),'prefix transcript incomplete');row=rows[position];position+=1
        e.need(set(row)=={'request','response'},'prefix wire row')
        before,request=wire(row['request']);after,response=wire(row['response'])
        e.need(before==before_kind and after==after_kind,'prefix wire kinds')
        if trace is None:
            trace=request['trace'];e.need(str(uuid.UUID(trace))==trace and uuid.UUID(trace).int!=0 and trace!=status_trace,'prefix transfer session')
        envelope=dict(fields,trace=trace,sequence=position-1)
        e.need({k:v for k,v in request.items() if k!='payload'}==dict(envelope,sender=sender,recipient=recipient)
               and {k:v for k,v in response.items() if k!='payload'}==dict(envelope,sender=recipient,recipient=sender),'prefix exact correlation')
        return request['payload'],response['payload']
    expected=[(e.digest(e.f.canonical(cap['cut'])),source['source.gscp'],'CAPSULE')]
    expected += [(h,source[h+'.image'],'APPLICATION') for h in sorted(packet['images'])]
    for reference,raw,kind in expected:
        request,offer=exchange('CHUNK','SOURCE_OFFER');identifier=request['id'];digest=e.digest(raw)
        e.need(str(uuid.UUID(identifier))==identifier and uuid.UUID(identifier).int!=0 and identifier not in identifiers,'prefix transfer identity');identifiers.add(identifier)
        e.need(request==dict(id=identifier,action='REQUEST',offset=0,digest=reference,bytes=''),'prefix exact request')
        e.need(offer==dict(id=identifier,digest=digest,bytes=len(raw),kind=kind),'prefix exact offer')
        offset=0
        while offset<len(raw):
            request,response=exchange('CHUNK','CHUNK');part=base64.b64decode(response['bytes'],validate=True)
            e.need(0<len(part)<=4*e.MIB and part==raw[offset:offset+len(part)],'prefix exact data')
            e.need(request==dict(id=identifier,action='REQUEST',offset=offset,digest=digest,bytes=''),'prefix exact request')
            e.need(response==dict(id=identifier,action='DATA',offset=offset,digest=e.digest(part),bytes=base64.b64encode(part).decode()),'prefix exact data')
            offset+=len(part)
        request,response=exchange('TRANSFER_COMMIT','TRANSFER_COMMIT')
        e.need(request==response==dict(id=identifier,digest=digest),'prefix exact commit')
    e.need(position==len(rows),'prefix extra exchange')
    return position


def case(root,size):
    names={f'node-{n}' for n in range(1,size+1)}
    expected={'original-plan.gsbp','original-application.image','initial','after','received','wire.json','events.json','entry-1.gsr','payload-1.bin'}
    expected|={f'round-1-{stage}' for stage in ('prepared','selected','installed','settled')}
    expected|={f'slot-1-{stage}' for stage in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'typed-1-{node}' for node in names}
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()}==expected,'prefix case inventory')
    group=b.campaign(root,b.original(root,size,False),1);group,_=b.publication(root,group,1,None,[])
    for node,files in group.items():
        _,members,packet=b.c.current(files);b.typed_image(root/f'typed-1-{node}',members[packet['capsule']['application']+'.image'])
    b.match(root,'after',group);e.need(load(root/'events.json')==[],'prefix authority writes')
    _,members,packet=b.c.current(group['node-2'])
    expected={'source.gscp':members['source.gscp'],**{h+'.image':members[h+'.image'] for h in packet['images']}}
    e.need(b.c.inventory(root/'received')==expected,'prefix complete received bytes')
    return dict(size=size,exchanges=transcript(load(root/'wire.json'),group))


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'prefix evidence directory')
    e.need({p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'prefix complete inventory')
    cases=[case(root/f'stable-{n}',n) for n in (3,4,5)]
    expected=dict(schema='gse-v53-prefix-discovery-v1',status='PASS',cases=cases,network=True,publicRuntime=False,adoption=False,scope='read-only-current-prefix-acquisition')
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(expected),'prefix scope/receipt');return expected


def qualify(directory):
    original=validate(directory);results=[]
    variants=[('scope','prefix scope/receipt'),('missing-profile','prefix complete inventory'),('storage','admitted exact after'),('force','prefix authority writes'),
              ('scratch','prefix complete received bytes'),('hint','prefix discovery original cut'),('grant','prefix exact offer'),('sequence','prefix exact correlation'),
              ('reference','prefix exact request'),('bytes','prefix exact data'),('commit','prefix exact commit'),('truncated','prefix transcript incomplete'),('extra','prefix extra exchange')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-prefix-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(directory,target);root=target/'stable-3'
            if name=='scope':
                p=target/'receipt.json';v=load(p);v['adoption']=True;p.write_text(json.dumps(v))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name=='storage':(root/'after/node-1/grants.gsr').write_bytes(b'changed')
            elif name=='force':(root/'events.json').write_text('["PROMISE_FORCED"]')
            elif name=='scratch':next((root/'received').glob('*.image')).write_bytes(b'changed')
            else:
                p=root/'wire.json';rows=load(p)
                if name=='truncated':rows.pop()
                elif name=='extra':rows.append(rows[-1])
                else:
                    index=0 if name=='hint' else 1;field='request' if name=='reference' else 'response'
                    if name=='bytes':index=next(i for i,row in enumerate(rows) if wire(row['response'])[0]=='CHUNK')
                    elif name=='commit':index=len(rows)-1
                    kind,value=wire(rows[index][field])
                    if name=='hint':value['payload']['cut']['index']+=1
                    elif name=='grant':value['payload']['kind']='RECORD'
                    elif name=='sequence':value['sequence']+=1
                    elif name=='reference':value['payload']['digest']='0'*64
                    elif name=='bytes':value['payload'].update(bytes=base64.b64encode(b'changed').decode(),digest=e.digest(b'changed'))
                    else:value['payload']['id']=str(uuid.UUID(int=53))
                    rows[index][field]=base64.b64encode(e.f.encode('wire',kind,value)).decode()
                p.write_text(json.dumps(rows))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'prefix unrelated negative: '+name+': '+str(error))
            else:raise ValueError('prefix accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else validate(a.directory),sort_keys=True))
