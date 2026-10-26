"""Independent actual-bootstrap, grant, two-way transfer and fixed-selection replay.

These histories end at selection, before any selected installation or service.
No historical remote force observation is inferred from packet content alone.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import activation_evidence as a
from . import source_exchange_evidence as t

e=a.e
c=a.c
b=a.b
load=a.load


def transcript(rows,expected,root,view,ballot,sender,recipient,label,*,chunk_bytes=1024):
    e.need(type(chunk_bytes) is int and 0<chunk_bytes<=4*e.MIB,label+' chunk bound')
    position=0;trace=None;ids=set()
    def exchange(wanted,answer):
        nonlocal position,trace
        e.need(position<len(rows),label+' incomplete transcript');row=rows[position];position+=1
        e.need(set(row)=={'request','response'},label+' row')
        kind,request=t.wire(row['request']);reply_kind,response=t.wire(row['response'])
        e.need((kind,reply_kind)==(wanted,answer),label+' kinds')
        if trace is None:
            trace=request['trace'];e.need(str(uuid.UUID(trace))==trace and uuid.UUID(trace).int!=0,label+' trace')
        fields=dict(root=root,view=view,ballot=ballot,trace=trace,sequence=position)
        e.need({k:v for k,v in request.items() if k!='payload'}==dict(fields,sender=sender,recipient=recipient)
               and {k:v for k,v in response.items() if k!='payload'}==dict(fields,sender=recipient,recipient=sender),label+' correlation')
        return request['payload'],response['payload']
    for reference,raw,kind in expected:
        request,offer=exchange('CHUNK','SOURCE_OFFER');tid=request['id']
        e.need(tid not in ids,label+' reused transfer');ids.add(tid);digest=e.digest(raw)
        e.need(request==dict(id=tid,action='REQUEST',offset=0,digest=reference,bytes='')
               and offer==dict(id=tid,digest=digest,bytes=len(raw),kind=kind),label+' original offer')
        for offset in range(0,len(raw),chunk_bytes):
            request,response=exchange('CHUNK','CHUNK');part=raw[offset:offset+chunk_bytes]
            e.need(request==dict(id=tid,action='REQUEST',offset=offset,digest=digest,bytes='')
                   and response==dict(id=tid,action='DATA',offset=offset,digest=e.digest(part),bytes=base64.b64encode(part).decode()),label+' exact data')
        request,response=exchange('TRANSFER_COMMIT','TRANSFER_COMMIT')
        e.need(request==response==dict(id=tid,digest=digest),label+' exact commit')
    e.need(position==len(rows),label+' complete transcript')
    return position


def case(root,size):
    names=[f'node-{i}' for i in range(1,size//2+2)]
    e.need(root.is_dir() and not root.is_symlink(),'promised source case directory')
    e.need({p.name for p in root.iterdir()}=={'original-plan.gsbp','original-application.image','initial','selected','events.json','selected.gsr',*names[1:]},'promised source case inventory')
    before=b.original(root,size,False);_,initial,packet=c.current(before['node-1']);cap=packet['capsule'];r=cap['root'];view=e.authority(r,cap['cut']['view'])
    identities={n:e.f.decode(files['node.gsr'],'records','NODE')['identity'] for n,files in before.items()}
    ballot=dict(counter=2,proposer='node-1',incarnation=identities['node-1']['storage']);bases={};promises={};prepared={};seen=set()
    e.need({p.name for p in (root/'selected').iterdir()}==set(before),'promised source voter inventory')
    actual={n:c.inventory(root/'selected'/n) for n in before}
    for node in before:
        if node not in names:
            e.need(actual[node]==before[node],'promised source unselected voter changed');continue
        prior=c.journal(before[node]['grants.gsr'],r,node);rows=c.journal(actual[node]['grants.gsr'],r,node);suffix=rows[len(prior):]
        e.need(rows[:len(prior)]==prior and [v[0] for v in suffix]==['PROMISE','BASIS']+(['SELECTED'] if node=='node-1' else []),'promised source original journal sequence')
        promise,basis=suffix[:2];identifier=promise[2]['basisId'];e.need(str(uuid.UUID(identifier))==identifier and identifier not in seen,'promised source original UUID');seen.add(identifier)
        expected=dict(root=r,view=view,ballot=ballot,basisId=identifier)
        e.need(promise[2]==expected and basis[2]==dict(expected,voter=node,cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),inventory=e.digest(packet['indexBytes']),accepted=None),'promised source original grant')
        promises[node]=promise[1];bases[node]=basis[1];prefix='sources/'+identifier
        files=dict(before[node],**{'grants.gsr':before[node]['grants.gsr']+promise[1]+basis[1],prefix:None,prefix+'/source.gscp':initial['source.gscp']})
        for h in packet['images']:files[prefix+'/'+h+'.image']=initial[h+'.image']
        if node=='node-1':files['allocator.gsr']=e.f.encode('records','ALLOCATOR',dict(root=r,node=node,counter=2))
        prepared[node]=files
    selected=dict(root=r,view=view,ballot=ballot,cut=cap['cut'],nextEntry=None,
                  sources=[dict(voter=n,basisId=e.f.decode(bases[n],'records','BASIS')['basisId'],basisDigest=e.digest(bases[n])) for n in names])
    encoded=e.f.encode('records','SELECTED',selected)
    e.need(b.t.plans.read(root/'selected.gsr',65536)==encoded,'promised source fixed selection')
    prepared['node-1']['grants.gsr']+=encoded
    for node in names:e.need(actual[node]==prepared[node],'promised source exact selected storage')
    trace=None
    for sequence,node in enumerate(names[1:],1):
        member=root/node;e.need({p.name for p in member.iterdir()}=={'prepare.json','proposer-wire.json','source-wire.json','received'},'promised source peer inventory')
        row=load(member/'prepare.json');e.need(set(row)=={'request','response'},'promised source prepare row')
        kind,request=t.wire(row['request']);answer,response=t.wire(row['response']);e.need((kind,answer)==('PREPARE','PROMISE'),'promised source prepare kinds')
        if trace is None:trace=request['trace'];e.need(str(uuid.UUID(trace))==trace and uuid.UUID(trace).int!=0,'promised source prepare trace')
        fields=dict(root=r,view=view,ballot=ballot,trace=trace,sequence=sequence)
        e.need(request==dict(fields,sender=identities['node-1'],recipient=identities[node],payload=dict(promise=e.digest(promises['node-1'])))
               and response==dict(fields,sender=identities[node],recipient=identities['node-1'],payload=dict(basis=e.digest(bases[node]))),'promised source exact prepare')
        transcript(load(member/'proposer-wire.json'),[(e.digest(promises['node-1']),promises['node-1'],'RECORD')],r,view,ballot,identities[node],identities['node-1'],'proposer record')
        source={'source.gscp':initial['source.gscp'],**{h+'.image':initial[h+'.image'] for h in packet['images']}}
        e.need(c.inventory(member/'received')==source,'promised source exact received files')
        expected=[(e.digest(bases[node]),bases[node],'RECORD'),(e.digest(promises[node]),promises[node],'RECORD'),(e.digest(packet['capsuleBytes']),initial['source.gscp'],'CAPSULE')]
        expected += [(h,initial[h+'.image'],'APPLICATION') for h in sorted(packet['images'])]
        transcript(load(member/'source-wire.json'),expected,r,view,ballot,identities['node-1'],identities[node],'promised source transfer')
    events=load(root/'events.json');e.need([v['node'] for v in events]==sorted(before) and all(set(v)=={'node','events'} for v in events),'promised source event inventory')
    for row in events:
        node=row['node'];steps=row['events']
        if node not in names:e.need('GRANT_BEFORE_RETURN' not in steps,'promised source unselected grant');continue
        required=['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN']
        required=(required+['SELECTED_FORCED','SELECTED_BEFORE_RETURN']) if node=='node-1' else ['PROPOSER_RECORD_VALIDATED',*required,'PROMISE_REPLIED']
        e.need(all(steps.count(v)==1 for v in required) and [steps.index(v) for v in required]==sorted(steps.index(v) for v in required),'promised source force order')
        if node=='node-1':
            expected=['SOURCE_VERIFIED_'+n for n in names[1:]]
            e.need(all(steps.count(v)==1 for v in expected) and [steps.index(v) for v in expected]==sorted(steps.index(v) for v in expected)
                   and steps.index(expected[-1])>steps.index('SELECTED_BEFORE_RETURN'),'promised source accepted callbacks')
        else:e.need('SELECTED_FORCED' not in steps,'promised source premature peer selection')
        e.need('INSTALL_BEFORE_RETURN' not in steps,'promised source premature install')
    return dict(size=size,selected=len(names),ready=False)


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'promised source evidence directory')
    e.need({p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'promised source complete inventory')
    rows=[case(root/f'stable-{n}',n) for n in (3,4,5)]
    wanted=dict(schema='gse-v53-promised-source-v1',status='PASS',cases=rows,publicRuntime=False,network=True,scope='original-promise-through-network-selection')
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(wanted),'promised source scope/receipt');return wanted


def qualify(directory):
    original=validate(directory);results=[]
    variants=[('scope','promised source scope/receipt'),('missing-profile','promised source complete inventory'),('fixed-selection','promised source fixed selection'),
              ('unselected-write','promised source unselected voter changed'),('missing-grant','promised source original journal sequence'),('changed-scratch','promised source exact received files'),
              ('prepare-basis','promised source exact prepare'),('prepare-sender','promised source exact prepare'),('source-sequence','promised source transfer correlation'),
              ('source-offer','promised source transfer original offer'),('source-data','promised source transfer exact data'),('source-commit','promised source transfer exact commit'),
              ('missing-source-commit','promised source transfer incomplete transcript'),('missing-proposer-commit','proposer record incomplete transcript'),
              ('missing-force','promised source force order'),('extra-peer-file','promised source peer inventory')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-promised-source-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(directory,target);root=target/'stable-3';member=root/'node-2'
            if name=='scope':
                value=load(target/'receipt.json');value['publicRuntime']=True;(target/'receipt.json').write_text(json.dumps(value))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name=='fixed-selection':
                path=root/'selected.gsr';v=e.f.decode(path.read_bytes(),'records','SELECTED');v['sources'].reverse();path.write_bytes(e.f.encode('records','SELECTED',v))
            elif name=='unselected-write':(root/'selected/node-3/allocator.gsr').write_bytes(b'changed')
            elif name=='missing-grant':
                path=root/'selected/node-2/grants.gsr';raw=path.read_bytes();r=e.f.decode((root/'selected.gsr').read_bytes(),'records','SELECTED')['root'];rows=c.journal(raw,r,'node-2');path.write_bytes(b''.join(v[1] for v in rows[:-1]))
            elif name=='changed-scratch':next((member/'received').glob('*.image')).write_bytes(b'changed')
            elif name=='missing-force':
                path=root/'events.json';v=load(path);v[1]['events'].remove('BASIS_FORCED');path.write_text(json.dumps(v))
            elif name=='extra-peer-file':(member/'extra.bin').write_bytes(b'foreign')
            else:
                path=member/('prepare.json' if name.startswith('prepare-') else 'proposer-wire.json' if name=='missing-proposer-commit' else 'source-wire.json');v=load(path);rows=[v] if isinstance(v,dict) else v
                if name.startswith('missing-'):rows.pop()
                else:
                    index=len(rows)-1 if name=='source-commit' else 1 if name=='source-data' else 0;kind,frame=t.wire(rows[index]['response'])
                    if name=='prepare-basis':frame['payload']['basis']='0'*64
                    elif name=='prepare-sender':frame['sender']['storage']=str(uuid.UUID(int=53))
                    elif name=='source-sequence':frame['sequence']+=1
                    elif name=='source-offer':frame['payload']['digest']='0'*64
                    elif name=='source-data':frame['payload']['bytes']=base64.b64encode(b'changed').decode();frame['payload']['digest']=e.digest(b'changed')
                    else:frame['payload']['id']=str(uuid.UUID(int=54))
                    rows[index]['response']=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
                path.write_text(json.dumps(rows[0] if name.startswith('prepare-') else rows))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'promised source unrelated negative: '+name+': '+str(error))
            else:raise ValueError('promised source accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else validate(a.directory),sort_keys=True))
