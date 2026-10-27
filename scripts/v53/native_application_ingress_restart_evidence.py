"""Native certificate/application receiver death and explicit redispatch replay."""
import argparse
import base64
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil
import tempfile
from . import native_application_ingress_evidence as a
from . import native_application_evidence as native
from . import applied_end_evidence as end_model
b,c,e,f,need = a.b,a.c,a.e,a.f,a.need
POINTS=('CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_BEFORE_RETURN','APPLY_IMAGE_PREFIX_WRITTEN','APPLY_ACK_DIRECTORY_FORCED','APPLICATION_ACK_BEFORE_RETURN')


def log(path):
    lines=b.t.plans.read(path,8*e.MIB).decode().splitlines()
    need(all(line.startswith(('EVENT ','CUT ','READY ','REQUEST ','WIRE ','RECEIVED ','CLOSED ')) for line in lines),'application ingress restart log shape')
    return lines


def validate(root):
    root=Path(root); row=a.v.read(root/'restart-result.json'); mode,point=row.get('mode'),row.get('cut')
    need(mode in ('halt','kill') and point in POINTS and row==dict(status='PASS',mode=mode,cut=point,exit=23 if mode=='halt' else 137,
        resumeExit=0,duplicateReceipts=2,originalDispatch='FAILED',freshRemoteObservations=0),'application ingress restart scope')
    o=a.originals(root); need(o['voting']['size']==3 and o['voting']['kind']=='BARRIER','application ingress restart original profile')
    ends=a.ends(root,o); end=ends['node-3']; before=o['before']; certified=o['certified']['node-3']; b.match(root,'crash-ready',before)
    interrupted=dict(certified)
    if point==POINTS[0]:
        interrupted=dict(before['node-3']); interrupted['pending.accept.next']=certified['pending.accept']
    elif point.startswith('APPLY_') or point==POINTS[-1]:
        partial,exists,_=end_model.simulate(end,{},False,None if point==POINTS[-1] else point)
        need(exists,'application ingress restart end created'); interrupted['applied-end']=None
        interrupted.update({'applied-end/'+k:v for k,v in partial.items()})
    need(c.inventory(root/'interrupted')==interrupted,'application ingress restart exact interrupted files')
    recovered=dict(certified,**{'applied-end':None},**{'applied-end/'+k:v for k,v in end.items()})
    need(c.inventory(root/'recovered')==recovered and c.inventory(root/'end-node-3')==end,'application ingress restart exact recovered files')
    b.match(root,'after-ingress',dict(before,**{'node-3':recovered}))
    request=b.t.plans.read(root/'apply-request.gsrp',32768); sent=f.decode(request,'wire','APPLY'); cap=o['cap']; selected=o['selected']; ids=o['identities']
    need(sent==dict(root=cap['root'],view=selected['view'],ballot=selected['ballot'],trace=sent['trace'],sequence=1,sender=ids['node-1'],recipient=ids['node-3'],
        payload=dict(certificate=e.digest(o['certificate']),selection=e.digest(o['local']['selected.gsr']))),'application ingress restart original request')
    ack=f.encode('wire','APPLY_ACK',dict(sent,sender=sent['recipient'],recipient=sent['sender'],payload=dict(sent['payload'],statement=e.digest(end['statement.gsr']),acknowledgement=e.digest(end['ack.gsr']))))
    need(b.t.plans.read(root/'apply-ack.gsrp',32768)==ack,'application ingress restart original acknowledgement')
    original,resume=log(root/'worker.log'),log(root/'resume.log'); events=[s[6:] for s in original if s.startswith('EVENT ')]
    need(original[-1]=='CUT '+point and original.count('CUT '+point)==1 and original.count('READY '+mode)==1
         and [s for s in original if s.startswith('REQUEST ')]==['REQUEST '+base64.b64encode(request).decode()]
         and not any(s.startswith('WIRE ') for s in original),'application ingress restart failed dispatch')
    need(events[-1]==point and 'CERTIFICATE_CANDIDATE_FORCED' in events,'application ingress restart original certificate force')
    if point not in POINTS[:2]:
        names=['CERTIFICATE_PARENT_FORCED','NATIVE_CERTIFICATE_RETAINED','APPLICATION_AUTHORITY_VALIDATED']
        need(all(events.count(s)==1 for s in names) and [events.index(s) for s in names]==sorted(events.index(s) for s in names),'application ingress restart application after certificate')
        _,_,expected=end_model.simulate(end,{},False,None if point==POINTS[-1] else point)
        need([s for s in events if s.startswith('APPLY_')]==[v['event'] for v in expected],'application ingress restart interrupted end force order')
    need(resume.count('READY resume')==1 and resume[-1]=='CLOSED resume' and not any(s.startswith(('CUT ','RECEIVED ')) for s in resume),'application ingress restart no fresh observations')
    wires=[i for i,s in enumerate(resume) if s.startswith('WIRE ')]; expected=dict(request=base64.b64encode(request).decode(),response=base64.b64encode(ack).decode())
    need(len(wires)==2 and all(json.loads(resume[i][5:])==expected for i in wires),'application ingress restart duplicate acknowledgements')
    need([s for s in resume[wires[0]+1:] if s.startswith('EVENT ')]==['EVENT APPLICATION_ACK_BEFORE_RETURN'],'application ingress restart duplicate no write')
    recovered_events=[s[6:] for s in resume[:wires[0]] if s.startswith('EVENT ')]; native.native_order(recovered_events,1)
    need(recovered_events[-1]=='APPLICATION_ACK_BEFORE_RETURN','application ingress restart ACK after recovery')
    rows=[json.loads(s[9:]) for s in original if s.startswith('RECEIVED ')]; source=a.v.read(root/'wire.json'); traces=defaultdict(list)
    content={e.digest(o['certificate']):o['certificate']}; references={e.digest(o['certificate']):e.digest(o['certificate'])}; wanted=Counter([('node-1',e.digest(o['certificate']))])
    for node in ('node-1','node-2'):
        for phase,record in [('ACCEPT',o['accept']),('PROOF',o['proof'])]:
            raw=o['receipt'](node,phase,record);digest=e.digest(raw);content[digest]=raw;references[digest]=e.digest(f.canonical(dict(schema='gse-v53-vote-observation/1.3',receipt=digest)));wanted[(node,digest)]+=1
    for row in rows:
        need(dict(row,withheld=False) in source,'application ingress restart actual source response')
        kind,sent=a.v.transfer.wire(row['request']); reply_kind,reply=a.v.transfer.wire(row['response']);peer=sent['recipient']['node']
        need(peer in ('node-1','node-2') and sent['sender']==ids['node-3'] and sent['recipient']==ids[peer] and sent['root']==cap['root']
             and sent['view']==selected['view'] and sent['ballot']==selected['ballot'] and {k:v for k,v in reply.items() if k!='payload'}==
             dict({k:v for k,v in sent.items() if k!='payload'},sender=sent['recipient'],recipient=sent['sender']),'application ingress restart transfer authority')
        traces[sent['trace']].append((kind,sent,reply_kind,reply))
    observed=Counter()
    for trace in traces.values():
        need(len(trace)==3,'application ingress restart complete transfer');first=trace[0][1];digest=trace[0][3]['payload']['digest'];tid=first['payload']['id']
        need(digest in content,'application ingress restart original content');raw=content[digest]
        for index,(kind,sent,reply_kind,reply) in enumerate(trace):
            need(sent['sequence']==index+1 and sent['recipient']==first['recipient'],'application ingress restart transfer sequence');x,y=sent['payload'],reply['payload']
            if index==0:need((kind,reply_kind)==('CHUNK','SOURCE_OFFER') and x==dict(id=tid,action='REQUEST',offset=0,digest=references[digest],bytes='') and y==dict(id=tid,kind='RECORD',digest=digest,bytes=len(raw)),'application ingress restart offer')
            elif index==1:need((kind,reply_kind)==('CHUNK','CHUNK') and x==dict(id=tid,action='REQUEST',offset=0,digest=digest,bytes='') and y==dict(id=tid,action='DATA',offset=0,digest=digest,bytes=base64.b64encode(raw).decode()),'application ingress restart original bytes')
            else:need((kind,reply_kind)==('TRANSFER_COMMIT','TRANSFER_COMMIT') and x==y==dict(id=tid,digest=digest),'application ingress restart complete transfer')
        observed[(first['recipient']['node'],digest)]+=1
    need(observed==wanted,'application ingress restart original phased observations')
    return dict(status='PASS',mode=mode,cut=point,originalTransfers=sum(observed.values()),duplicateReceipts=2,freshRemoteObservations=0,published=False,autonomous=False)


def qualify(root):
    original=validate(root);results=[]
    for name,reason in [('scope','application ingress restart scope'),('interrupted','application ingress restart exact interrupted files'),
            ('recovered','application ingress restart exact recovered files'),('ack','application ingress restart original acknowledgement'),
            ('source','application ingress restart actual source response'),('fresh','application ingress restart no fresh observations'),
            ('duplicate','application ingress restart duplicate no write')]:
        with tempfile.TemporaryDirectory(prefix='v53-application-restart-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target)
            if name=='scope':
                path=target/'restart-result.json';v=a.v.read(path);v['freshRemoteObservations']=1;path.write_text(json.dumps(v))
            elif name in ('interrupted','recovered','ack'):
                path=target/({'interrupted':'interrupted/pending.accept','recovered':'recovered/selector.gsr','ack':'apply-ack.gsrp'}[name]);path.write_bytes(b'changed')
            elif name=='source':(target/'wire.json').write_text('[]')
            else:
                path=target/'resume.log';lines=path.read_text().splitlines();index=next(i for i,s in enumerate(lines) if s.startswith('WIRE '))+1
                lines.insert(index,'RECEIVED {}' if name=='fresh' else 'EVENT CERTIFICATE_CANDIDATE_FORCED');path.write_text('\n'.join(lines)+'\n')
            try:validate(target)
            except ValueError as error:need(reason in str(error),'application ingress restart unrelated negative '+name+': '+str(error))
            else:raise ValueError('application ingress restart accepted negative '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--negatives',action='store_true');a0=p.parse_args();print(json.dumps(qualify(a0.root) if a0.negatives else validate(a0.root),sort_keys=True))
