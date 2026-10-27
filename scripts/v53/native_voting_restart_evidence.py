"""Derive native vote crash/reopen from original bootstrap and actual wire/files."""
import argparse
import base64
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import native_voting_evidence as v
b, e, c, need = v.b, v.e, v.c, v.need
POINTS=('ACCEPT_CANDIDATE_FORCED','ACCEPT_ACK_BEFORE_RETURN','PROOF_CANDIDATE_FORCED','PROOF_ACK_BEFORE_RETURN')


def log(path):
    lines=b.t.plans.read(path,8*e.MIB).decode().splitlines()
    need(all(line.startswith(('EVENT ','CUT ','READY ','REQUEST ','WIRE ','RECEIVED ','CLOSED ')) for line in lines),'native vote restart log shape')
    return lines


def validate(root):
    root=Path(root); result=v.read(root/'restart-result.json'); mode, point=result.get('mode'),result.get('cut')
    need(mode in ('halt','kill') and point in POINTS and result==dict(status='PASS',mode=mode,cut=point,exit=23 if mode=='halt' else 137,
         resumeExit=0,duplicateReceipts=2,originalDispatch='FAILED',freshRemoteObservations=0),'native vote restart result')
    phase=point.split('_')[0]; group=b.campaign(root,b.original(root,3,False),1); b.match(root,'before-voting',group)
    _,local,packet=c.current(group['node-1']); cap=packet['capsule']; selected=e.f.decode(local['selected.gsr'],'records','SELECTED')
    identities={node:e.f.decode(files['node.gsr'],'records','NODE')['identity'] for node,files in group.items()}
    entry=e.f.encode('records','ENTRY',dict(root=cap['root'],authority=selected['view'],index=1,previous=cap['cut']['entry'],origin=selected['ballot'],kind='BARRIER',payload=e.digest(b'')))
    need(b.t.plans.read(root/'entry.gsr',16384)==entry and b.t.plans.read(root/'payload.bin',e.MIB)==b'','native vote restart original entry')
    accept=e.f.encode('records','ACCEPT',dict(root=cap['root'],authority=selected['view'],ballot=selected['ballot'],index=1,entry=e.digest(entry)))

    def receipt(node):return e.f.canonical(dict(root=cap['root'],voter=node,incarnation=identities[node]['storage'],phase='ACCEPT',record=e.digest(accept)))

    proof=e.f.encode('records','PROOF',dict(e.f.decode(accept,'records','ACCEPT'),accepts=[dict(voter=node,incarnation=identities[node]['storage'],receipt=e.digest(receipt(node))) for node in sorted(group)]))
    if phase=='PROOF':need(b.t.plans.read(root/'proof.gsr',16384)==proof,'native vote restart original proof')

    def pending(node,extra):
        _,local,_=c.current(group[node]); raw=e.container([group[node]['selector.gsr'],local['promise.gsr'],local['selected.gsr'],entry,accept],b'')+extra
        return raw[:8]+struct.pack('>I',len(raw))+raw[12:]

    before=dict(group)
    for node in group:
        if node=='node-1' or phase=='PROOF':before[node]=dict(group[node],**{'pending.accept':pending(node,proof if phase=='PROOF' and node=='node-1' else b'')})
    b.match(root,'crash-ready',before)
    complete=pending('node-3',proof if phase=='PROOF' else b''); interrupted=dict(before['node-3'])
    interrupted['pending.accept.next' if point.endswith('CANDIDATE_FORCED') else 'pending.accept']=complete
    need(c.inventory(root/'interrupted')==interrupted,'native vote restart interrupted original files')
    recovered=dict(before['node-3'],**{'pending.accept':complete})
    need(c.inventory(root/'recovered')==recovered,'native vote restart recovered original files');b.match(root,'after-voting',dict(before,**{'node-3':recovered}))
    raw=b.t.plans.read(root/'vote-request.gsrp',16384); sent=e.f.decode(raw,'wire',phase); record=accept if phase=='ACCEPT' else proof
    need(sent==dict(root=cap['root'],view=selected['view'],ballot=selected['ballot'],trace=sent['trace'],sequence=1,sender=identities['node-1'],recipient=identities['node-3'],
                   payload={('acceptance' if phase=='ACCEPT' else 'proof'):e.digest(record)}),'native vote restart exact request')
    ack=e.f.encode('wire',phase+'_ACK',dict(sent,sender=sent['recipient'],recipient=sent['sender'],payload=dict(entry=e.digest(entry),receipt=e.digest(e.f.canonical(dict(
        root=cap['root'],voter='node-3',incarnation=identities['node-3']['storage'],phase=phase,record=e.digest(record)))))))
    need(b.t.plans.read(root/'vote-ack.gsrp',16384)==ack,'native vote restart exact acknowledgement')
    original=log(root/'worker.log'); resume=log(root/'resume.log')
    need(original[-1]=='CUT '+point and original.count('CUT '+point)==1 and original.count('READY '+mode)==1
         and [line for line in original if line.startswith('REQUEST ')]==['REQUEST '+base64.b64encode(raw).decode()]
         and not any(line.startswith('WIRE ') for line in original),'native vote restart exact failed dispatch')
    need(resume.count('READY resume')==1 and resume[-1]=='CLOSED resume' and not any(line.startswith(('CUT ','RECEIVED ')) for line in resume),'native vote restart no fresh observations')
    writes=[line for line in resume if line.startswith('WIRE ')]; expected={'request':base64.b64encode(raw).decode(),'response':base64.b64encode(ack).decode()}
    need(len(writes)==2 and all(json.loads(line[5:])==expected for line in writes)
         and resume.count('EVENT '+phase+'_ACK_BEFORE_RETURN')==2,'native vote restart duplicate original ACKs')
    ready=resume.index('READY resume'); need([line for line in resume[ready+1:] if line.startswith('EVENT ')]==['EVENT '+phase+'_ACK_BEFORE_RETURN']*2,'native vote restart duplicate no writes')
    originals={e.digest(item):item for item in ((accept,entry,receipt('node-1')) if phase=='ACCEPT' else (proof,receipt('node-1'),receipt('node-2')))}
    rows=[json.loads(line[9:]) for line in original if line.startswith('RECEIVED ')]; source=v.read(root/'wire.json'); traces=defaultdict(list)
    for row in rows:
        need(dict(row,withheld=False) in source,'native vote restart actual source response')
        kind,request=v.transfer.wire(row['request']); reply_kind,response=v.transfer.wire(row['response'])
        peer=request['recipient']['node']
        need(peer in ('node-1','node-2') and request['sender']==identities['node-3'] and request['recipient']==identities[peer] and request['root']==cap['root']
             and request['view']==selected['view'] and request['ballot']==selected['ballot']
             and {k:x for k,x in response.items() if k!='payload'}==dict({k:x for k,x in request.items() if k!='payload'},sender=request['recipient'],recipient=request['sender']),
             'native vote restart transfer authority')
        traces[request['trace']].append((kind,request,reply_kind,response))
    observed=Counter()
    for history in traces.values():
        need(len(history)==3,'native vote restart complete transfer'); first=history[0][1]; digest=history[0][3]['payload']['digest']; tid=first['payload']['id']; peer=first['recipient']['node']
        need(digest in originals,'native vote restart original transfer reference'); content=originals[digest]; reference=e.digest(e.f.canonical(dict(schema='gse-v53-vote-observation/1.3',receipt=digest))) if content in (receipt('node-1'),receipt('node-2')) else digest
        for index,(kind,request,reply_kind,response) in enumerate(history):
            need(request['sequence']==index+1 and request['recipient']==first['recipient'],'native vote restart sequence')
            a,z=request['payload'],response['payload']
            if index==0:need((kind,reply_kind)==('CHUNK','SOURCE_OFFER') and a==dict(id=tid,action='REQUEST',offset=0,digest=reference,bytes='')
                and z==dict(id=tid,kind='RECORD',digest=digest,bytes=len(content)),'native vote restart exact offer')
            elif index==1:need((kind,reply_kind)==('CHUNK','CHUNK') and a==dict(id=tid,action='REQUEST',offset=0,digest=digest,bytes='')
                and z==dict(id=tid,action='DATA',offset=0,digest=digest,bytes=base64.b64encode(content).decode()),'native vote restart exact bytes')
            else:need((kind,reply_kind)==('TRANSFER_COMMIT','TRANSFER_COMMIT') and a==z==dict(id=tid,digest=digest),'native vote restart exact commit')
        observed[(peer,digest)]+=1
    wanted=Counter([('node-1',e.digest(accept)),('node-1',e.digest(entry)),('node-1',e.digest(receipt('node-1')))] if phase=='ACCEPT' else [('node-1',e.digest(proof)),('node-1',e.digest(receipt('node-1'))),('node-2',e.digest(receipt('node-2')))])
    need(observed==wanted,'native vote restart complete original observations')
    return dict(status='PASS',mode=mode,cut=point,phase=phase,transfers=sum(observed.values()),duplicateReceipts=2,autonomous=False)


def qualify(root):
    original=validate(root); results=[]
    variants=[('scope','native vote restart result'),('interrupted','native vote restart interrupted original files'),('recovered','native vote restart recovered original files'),
              ('request','native vote restart exact request'),('ack','native vote restart exact acknowledgement'),('cut','native vote restart exact failed dispatch'),
              ('fresh','native vote restart no fresh observations'),('write','native vote restart duplicate no writes'),('receipt','native vote restart duplicate original ACKs'),
              ('source','native vote restart actual source response')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-vote-restart-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target)
            if name=='scope':
                path=target/'restart-result.json';value=v.read(path);value['freshRemoteObservations']=1;path.write_text(json.dumps(value))
            elif name in ('interrupted','recovered'):(target/name/'pending.accept').write_bytes(b'changed')
            elif name in ('request','ack'):
                path=target/('vote-request.gsrp' if name=='request' else 'vote-ack.gsrp');kind=original['phase']+('_ACK' if name=='ack' else '')
                value=e.f.decode(path.read_bytes(),'wire',kind);value['sequence']+=1;path.write_bytes(e.f.encode('wire',kind,value))
            elif name=='source':(target/'wire.json').write_text('[]')
            else:
                path=target/('worker.log' if name=='cut' else 'resume.log');lines=path.read_text().splitlines()
                if name=='cut':lines=[x for x in lines if not x.startswith('CUT ')]
                elif name=='fresh':lines.insert(-1,'RECEIVED {}')
                elif name=='write':lines.insert(-1,'EVENT ACCEPT_CANDIDATE_FORCED')
                else:lines=[x for x in lines if not x.startswith('WIRE ')][:]
                path.write_text('\n'.join(lines)+'\n')
            try:validate(target)
            except ValueError as error:need(reason in str(error),'native vote restart unrelated negative '+name+': '+str(error))
            else:raise ValueError('native vote restart accepted negative '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
