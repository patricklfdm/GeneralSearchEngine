"""Original physical and full ROOT/prefix/generation acquisition replay.

Complete source receipt is not learner admission, image readiness or joint voting.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import learner_root_evidence as r
from . import promised_source_evidence as t
from . import generation_copy_evidence as g
b,c,d,e,f,need=r.b,r.c,r.d,r.e,r.f,r.need


def transcripts(rows):
    need(type(rows) is list and 0<len(rows)<=32768,'learner source bounded transcript')
    sessions=[]
    for row in rows:
        need(type(row) is dict and set(row)=={'request','response'},'learner source trace row')
        trace=t.t.wire(row['request'])[1]['trace']
        if not sessions or sessions[-1][0]!=trace:
            need(all(trace!=old for old,_ in sessions),'learner source reused session')
            sessions.append((trace,[]))
        sessions[-1][1].append(row)
    need(len(sessions)==4,'learner source complete sessions')
    return [g.attempts(rows) for _,rows in sessions]


def network(root,reserved,request,learner,*,trace_name='learner-source-wire.json',copy_name='learner-source-copy',preceding=(),following=()):
    rows=d.read(root/trace_name);sessions=transcripts(rows)
    server=d.read(root/'wire.json');observed=[]
    need(type(server) is list and len(server)<=32768,'learner source bounded server trace')
    for row in server:
        _,frame=t.t.wire(row['request'])
        if frame['sender']['node']==learner['node']:
            need(set(row)=={'request','response','withheld'} and row['withheld'] is False,'learner source original server trace')
            observed.append({k:row[k] for k in ('request','response')})
    need(observed==list(preceding)+rows+list(following),'learner source exact received trace')
    peer='node-1';identity=d.future.identity(reserved[peer]);prefix,members,packet=c.current(reserved[peer]);cap=packet['capsule']
    # current() exposes manifest members separately from their already-derived
    # generation frame. The received complete copy must include that frame too.
    members=dict(members,**{'generation.gsr':reserved[peer][prefix+'generation.gsr']})
    original=reserved[peer]['root.gsr'];ballot=dict(counter=1,proposer=learner['node'],incarnation=learner['storage'])
    alias=e.digest(f.canonical(dict(schema='gse-v53-learner-root-reference/1.3',root=request['root'],learner=learner,request=request)))
    t.transcript(sessions[0],[(alias,original,'RECORD')],request['root'],request['expected'],ballot,learner,identity,'learner source ROOT',chunk_bytes=4*e.MIB)
    need(len(sessions[1])==1,'learner source single hint')
    row=sessions[1][0];kind,probe=t.t.wire(row['request']);answer,status=t.t.wire(row['response']);nonce=probe['payload']['nonce']
    fields=dict(root=request['root'],view=request['expected'],ballot=ballot,trace=probe['trace'],sequence=1)
    need(kind=='STATUS_PROBE' and answer=='STATUS' and probe==dict(fields,sender=learner,recipient=identity,payload=dict(nonce=nonce))
         and status==dict(fields,sender=identity,recipient=learner,payload=dict(nonce=nonce,cut=cap['cut'],ready=False)),
         'learner source exact hint')
    def reference(scope):return e.digest(f.canonical(dict(schema='gse-v53-learner-source-reference/1.3',root=request['root'],learner=learner,request=request,cut=cap['cut'],scope=scope)))
    expected=[(reference('prefix'),members['source.gscp'],'CAPSULE')]
    expected.extend((digest,members[digest+'.image'],'APPLICATION') for digest in sorted(packet['images']))
    t.transcript(sessions[2],expected,request['root'],request['expected'],ballot,learner,identity,'learner source prefix',chunk_bytes=4*e.MIB)
    expected=[(reference('generation'),members['generation.gsr'],'RECORD')]
    if 'ancestry.gsr' in members:expected.append((e.digest(members['ancestry.gsr']),members['ancestry.gsr'],'RECORD'))
    expected.extend((e.digest(data),data,'RECORD') for name,data in sorted(members.items()) if name not in ('generation.gsr','source.gscp','ancestry.gsr') and not name.endswith('.image'))
    t.transcript(sessions[3],expected,request['root'],request['expected'],ballot,learner,identity,'learner source generation',chunk_bytes=4*e.MIB)
    need(c.inventory(root/copy_name)==members,'learner source exact original generation')
    return dict(peer=peer,exchanges=len(rows),originalFiles=len(members))


def validate(root):
    root=Path(root);need(root.is_dir() and not root.is_symlink(),'learner source regular evidence');total=0
    for count,path in enumerate(root.rglob('*'),1):
        need(not path.is_symlink() and (path.is_file() or path.is_dir()),'learner source regular evidence')
        if path.is_file():total+=path.stat().st_size
        need(count<=65536 and total<=512*e.MIB,'learner source evidence capacity')
    names={'original-plan.gsbp','original-application.image','initial','before-network','installed','selected.gsr',
           'before-learner-source','after-learner-source','after-close','calls.json','events.json','wire.json','failures.json',
           'learner-reserve-payload.bin','learner-source-wire.json','learner-source-result.json','learner-source-copy'}
    names|={f'{stage}-{i}' for stage in ('applied','published') for i in (1,2,3)}
    b.selection.layout(root,names,'learner source')
    reserved,request,learner=r.physical(root,before='before-learner-source',after='after-learner-source')
    result=network(root,reserved,request,learner)
    need(d.read(root/'learner-source-result.json')==dict(status='PASS',scope='native-reservation-complete-source',voter=False,
         materialized=False,publicReady=False,phase3Complete=False),'learner source result scope')
    return dict(status='PASS',scope='native-reservation-complete-source',**result,physicalQualification=True,
                fullNetworkQualification=False,learnerAdmissionQualified=False,phase3Complete=False)


NEGATIVES={
 'extra-file':'context selection learner source inventory',
 'changed-before-read':'admitted exact before-learner-source: node-1',
 'changed-during-read':'admitted exact after-learner-source: node-1',
 'false-public-ready':'learner source result scope',
 'changed-original-copy':'learner source exact original generation',
 'missing-original-copy':'learner source exact original generation',
 'missing-client-receipt':'learner source exact received trace',
 'substituted-request':'learner source prefix original offer',
 'changed-hint':'learner source exact hint',
 'changed-generation-data':'learner source generation exact data',
 'changed-generation-commit':'learner source generation exact commit',
 'foreign-generation-source':'learner source generation correlation',
}


def qualify(root):
    root=Path(root);original=validate(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-learner-source-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target)
            if name=='extra-file':(target/'extra').write_bytes(b'bad')
            elif name in ('changed-before-read','changed-during-read'):
                stage='before-learner-source' if name=='changed-before-read' else 'after-learner-source'
                (target/stage/'node-1/selector.gsr').write_bytes(b'bad')
            elif name=='false-public-ready':
                path=target/'learner-source-result.json';value=d.read(path);value['publicReady']=True;path.write_bytes(f.canonical(value))
            elif name in ('changed-original-copy','missing-original-copy'):
                p=target/'learner-source-copy/generation.gsr'
                if name=='changed-original-copy':p.write_bytes(b'bad')
                else:p.unlink()
            elif name=='missing-client-receipt':
                p=target/'learner-source-wire.json';rows=d.read(p);rows.pop();p.write_bytes(f.canonical(rows))
            else:
                path=target/'learner-source-wire.json';rows=d.read(path);sessions=transcripts(rows)
                if name=='substituted-request':row=sessions[2][0];field='request'
                elif name=='changed-hint':row=sessions[1][0];field='response'
                elif name=='changed-generation-data':row=sessions[3][1];field='response'
                elif name=='changed-generation-commit':row=sessions[3][-1];field='response'
                elif name=='foreign-generation-source':row=sessions[3][0];field='response'
                else:raise ValueError('unknown learner source negative '+name)
                previous=dict(row);kind,frame=t.t.wire(row[field])
                if name=='changed-hint':frame['payload']['cut']['index']+=1
                elif name=='foreign-generation-source':frame['sender']['storage']='00000000-0000-0000-0000-000000000053'
                elif name=='changed-generation-data':
                    data=bytearray(base64.b64decode(frame['payload']['bytes']));data[-1]^=1
                    frame['payload'].update(bytes=base64.b64encode(data).decode(),digest=e.digest(data))
                else:frame['payload']['digest']='0'*64
                row[field]=base64.b64encode(f.encode('wire',kind,frame)).decode();path.write_bytes(f.canonical(rows))
                server_path=target/'wire.json';server=d.read(server_path)
                for item in server:
                    if all(item[k]==v for k,v in previous.items()):item.update(row)
                server_path.write_bytes(f.canonical(server))
            try:validate(target)
            except ValueError as error:need(str(error)==reason,'learner source unrelated negative: '+name+': '+str(error))
            else:raise ValueError('learner source accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--qualify',action='store_true');args=p.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root)))
