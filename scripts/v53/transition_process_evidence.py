"""Original physical projection for interrupted native transition proposers.

Original bytes are reduced before process outcomes, force/response ordering and
negative replay. This controlled same-proposer matrix does not qualify every
transfer trace, alternate-leader takeover or the full Phase 3 protocol.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import tempfile
from . import authority_transition_evidence as a
from . import continuous_transition_evidence as continuous

b,c,d,e,f,need=a.b,a.c,a.d,a.e,a.f,a.need


def trace(path):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=64*e.MIB,
         'transition process bounded trace')
    rows=[]
    for line in path.read_text().splitlines():
        kind,separator,value=line.partition(' ')
        need(separator and kind in {'STORE','ROUND','SLOT','CUT','OPEN','SNAPSHOT','READY','CLOSED',
             'BEFORE_REQUEST_WRITE','AFTER_REQUEST_READ','AFTER_RESPONSE_READ','BEFORE_RESPONSE_WRITE'},
             'transition process trace kind')
        fields={'STORE':{'event','index'},'CUT':{'event','index'},'ROUND':{'event','record'},
                'SLOT':{'event','record','voters'},'AFTER_RESPONSE_READ':{'request','response'},'BEFORE_RESPONSE_WRITE':{'request','response'}}
        if kind in fields:
            value=e.parse(value.encode('ascii'))
            need(type(value) is dict and set(value)==fields[kind],'transition process trace fields')
        rows.append((kind,value))
    return rows


class ProcessSlot(a.NativeSlot):
    """Reuse the original catalog/application/publication reduction, not output hashes."""
    def requested(self,slot,entry,payload):
        need(entry==self.requested_entry,'transition process exact original command')
        certificate=f.decode((self.root/f'{self.mode}-applied-{slot}/node-1/applied-end/certificate.gsr').read_bytes(),
                             'records','CERTIFICATE')
        need(certificate['entry']==e.digest(entry),'transition process applied original entry')
        self.entry=entry

    def application_image(self,slot,nodes):
        return (self.root/f'{self.mode}-applied-{slot}'/nodes[0]/'applied-end/application.image').read_bytes()

    def snapshot(self,label,group):
        if label.endswith('-applied'):
            self.applied=copy.deepcopy(group)
            b.match(self.root,f'{self.mode}-applied-{self.slot}',group)
        elif label.endswith('-published'):
            before_cleanup={}
            self.publication_group(group,before_local_cleanup=before_cleanup)
            if self.mode!='resume' and self.slot==self.cut_index:
                interrupted=copy.deepcopy(group)
                if self.cut_point=='PUBLICATION_SELECTOR_FORCED':
                    own=interrupted['node-1'];original=self.applied['node-1']
                    own['pending.accept']=original['pending.accept']
                    own.update({k:v for k,v in original.items() if k=='applied-end' or k.startswith('applied-end/')})
                    own.update(before_cleanup['node-1'])
                b.match(self.root,'interrupted',interrupted)
            else:b.match(self.root,f'{self.mode}-published-{self.slot}',group)


def install(root,group,raw,mode,ordinal):
    chosen=f.decode(raw,'records','SELECTED');voters=[v['voter'] for v in chosen['sources']]
    view=c.current(group['node-1'])[2]['capsule']['cut']['view']
    a.x.context.majority(view,voters)
    need('node-1' in voters and voters==sorted(voters) and len(set(voters))==len(voters),
         'transition process fixed original selected voters')
    group=continuous.reconcile(group,voters)
    if chosen['cut']['index']>=5:
        group=a.maintenance(group,voters)
        group.update(b.settled({n:group[n] for n in voters}))
    previous=f.decode(group['node-1']['allocator.gsr'],'records','ALLOCATOR')['counter']
    need(chosen['ballot']['counter']==previous+1,'transition process fresh ballot')
    stage=f'{mode}-installed-{ordinal}'
    _,_,installed=d.s.campaign(root,{n:group[n] for n in voters},previous+1,stage,selected_prefix=d.slot.prefix)
    group=dict(group,**installed);b.match(root,stage,group)
    need(c.current(group['node-1'])[1]['selected.gsr']==raw,'transition process original selection')
    return group,voters


def profile_at(root):
    path=Path(root)/'profile.json'
    need(path.is_file() and not path.is_symlink(),'transition process regular profile')
    profile=d.read(path)
    need(set(profile)=={'index','point','mode'} and type(profile['index']) is int and profile['index'] in (5,6)
         and profile['point'] in ('PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN')
         and profile['mode'] in ('halt','kill'),'transition process profile')
    return profile


def physical(root):
    root=Path(root);profile=profile_at(root);history=root/'history'
    original=a.prelude(history,'INTENT');b.match(history,'before-child',original.group)
    model=ProcessSlot.__new__(ProcessSlot);model.__dict__.update(original.__dict__)
    model.cut_index=profile['index'];model.cut_point=profile['point']
    rounds=[]
    for worker,mode in [('interrupted-worker',profile['mode']),('resumed-worker','resume')]:
        rows=trace(root/worker/'stdout');ordinal=0;model.mode=mode;begin=[]
        for kind,row in rows:
            if kind!='ROUND':continue
            raw=base64.b64decode(row['record'],validate=True);event=row['event']
            if event=='INSTALLED':
                ordinal+=1;model.group,model.voters=install(history,model.group,raw,mode,ordinal)
                model.active=list(model.voters);model.first=None
            elif event=='SLOT_BEGIN':
                entry=f.decode(raw,'records','ENTRY');need(ordinal>0,'transition process slot before installation')
                model.group=a.maintenance(model.group,model.voters);model.requested_entry=raw
                operation=model.state()[3]['results'][-1];command=None
                if entry['kind']=='INTENT':command=dict(sealed={k:operation[k] for k in ('request','prepared','receipt')})
                elif entry['kind']=='FINAL':command=dict(binding=operation['binding'])
                else:need(entry['kind']=='BARRIER','transition process unexpected operation')
                model.publish(entry['kind'],command)
                begin.append(dict(index=entry['index'],kind=entry['kind']))
        rounds.append(dict(worker=worker,activations=ordinal,slots=begin))
    b.match(history,'after-resume',model.group);b.match(history,'after-close',model.group)
    cap=model.state()[2];catalog=model.state()[3]
    need(cap['cut']['index']==7 and cap['cut']['view']['operation'] is None and catalog['active'] is None
         and catalog['results'][-1]['phase']=='COMPLETED','transition process exact completed operation')
    return dict(status='PASS',scope='original-physical-projection-only',profile=profile,rounds=rounds,
                processQualification=False,networkQualification=False,phase3Complete=False)


def layout(root,profile):
    need(root.is_dir() and not root.is_symlink(),'transition process regular evidence')
    total=0
    for number,path in enumerate(root.rglob('*'),1):
        need(not path.is_symlink() and (path.is_file() or path.is_dir()),'transition process regular evidence')
        if path.is_file():total+=path.stat().st_size
        need(number<=65536 and total<=512*e.MIB,'transition process evidence capacity')
    b.selection.layout(root,{'profile.json','process.json','history','native-history.txt','interrupted-worker','resumed-worker'},'transition process')
    b.selection.layout(root/'interrupted-worker',{'stdout','stderr'},'interrupted transition worker')
    b.selection.layout(root/'resumed-worker',{'stdout','stderr','ready.json','ready.gsrp'},'resumed transition worker')
    expected={'original-plan.gsbp','original-application.image','initial','before-network','before-child','interrupted',
              'after-resume','after-close','calls.json','events.json','wire.json','failures.json'}
    expected|={'round-1-'+v for v in ('prepared','selected','installed','settled')}
    expected|={f'slot-{n}-{v}' for n in range(1,5) for v in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'{name}-{n}.{ext}' for n in range(1,5) for name,ext in (('entry','gsr'),('payload','bin'))}
    for mode,slots in ((profile['mode'],range(5,profile['index']+1)),('resume',range(profile['index']+1,8))):
        for ordinal,index in enumerate(slots,1):
            expected|={f'{mode}-installed-{ordinal}',f'{mode}-applied-{index}'}
            if mode=='resume' or index!=profile['index']:expected.add(f'{mode}-published-{index}')
    b.selection.layout(root/'history',expected,'transition process history')


def process_outcome(process,profile):
    keys={'parentPid','childPid','resumePid','mode','index','point','exit','resumeExit','publicReady','liveLockRefused'}
    need(set(process)==keys and all(type(process[k]) is int and process[k]>0 for k in ('parentPid','childPid','resumePid'))
         and len({process[k] for k in ('parentPid','childPid','resumePid')})==3
         and type(process['publicReady']) is bool and type(process['liveLockRefused']) is bool
         and type(process['exit']) is int and type(process['resumeExit']) is int and type(process['index']) is int
         and process==dict(profile,parentPid=process['parentPid'],childPid=process['childPid'],resumePid=process['resumePid'],
              exit=23 if profile['mode']=='halt' else 137,resumeExit=0,publicReady=False,liveLockRefused=profile['mode']=='kill'),
         'transition process distinct original workers')


def lifecycle(root,profile,*,interrupted_retirement=False):
    """Publication ACK checks shared with the pre-slot retirement reader.

    That reader separately derives and checks its child's interrupted maintenance
    and cold-open lifecycle before calling this for all three resumed slots.
    """
    history=root/'history';process_outcome(d.read(root/'process.json'),profile)
    wire=d.read(history/'wire.json');events=d.read(history/'events.json')
    need(type(wire) is list and type(events) is list and len(wire)<=32768 and len(events)<=32768,
         'transition process bounded network observations')
    remote_ends={};last_ack=None
    workers=([('resumed-worker','resume',[5,6,7])] if interrupted_retirement else
             [('interrupted-worker',profile['mode'],list(range(5,profile['index']+1))),
              ('resumed-worker','resume',list(range(profile['index']+1,8)))])
    for worker,mode,slots in workers:
        rows=trace(root/worker/'stdout');rounds=[(i,v) for i,(kind,v) in enumerate(rows) if kind=='ROUND']
        expected=['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE']*len(slots)
        if mode=='resume':expected+=['BEFORE_READY']
        else:expected.pop()
        need([v['event'] for _,v in rounds]==expected,'transition process exact round lifecycle')
        need([v for k,v in rows if k=='OPEN']==[mode] and (root/worker/'stderr').read_bytes()==b'',
             'transition process complete worker output')
        if mode=='resume':
            need(rows[-2:]==[('READY','resume'),('CLOSED','resume')] and not any(k=='CUT' for k,_ in rows),
                 'transition process normal resume completion')
            opening=[v['event'] for k,v in rows[:next(i for i,(k,_) in enumerate(rows) if k=='OPEN')] if k=='STORE']
            if profile['point']=='PUBLICATION_SELECTOR_FORCED':
                d.s.ordered(opening,['PUBLICATION_RETIRED','FUTURE_RETENTION_PROMOTED','FUTURE_RETENTION_CLEARED'],
                            'transition original selector recovery')
        else:
            cut=dict(event=profile['point'],index=profile['index'])
            need(rows[-2:]==[('STORE',cut),('CUT',cut)] and sum(k=='CUT' for k,_ in rows)==1
                 and not any(k in ('READY','CLOSED') for k,_ in rows),'transition process exact interrupted boundary')
        snapshots=['resume-opened-0'] if interrupted_retirement else []
        for ordinal,index in enumerate(slots,1):
            at,installed=rounds[(ordinal-1)*3];start,begin=rounds[(ordinal-1)*3+1]
            complete=(mode=='resume' or index!=profile['index'])
            end,done=rounds[(ordinal-1)*3+2] if complete else (len(rows)-1,None)
            selected_raw=base64.b64decode(installed['record'],validate=True);selected=f.decode(selected_raw,'records','SELECTED')
            entry_raw=base64.b64decode(begin['record'],validate=True);entry=f.decode(entry_raw,'records','ENTRY')
            need(entry['index']==index and entry['kind']=={5:'INTENT',6:'FINAL',7:'BARRIER'}[index]
                 and entry['origin']==selected['ballot'] and entry['authority']==selected['view'],
                 'transition process slot authority')
            group={p.name:c.inventory(p) for p in (history/f'{mode}-applied-{index}').iterdir()}
            voters=[v['voter'] for v in selected['sources']];own=group['node-1'];identity=d.future.identity(own)
            need(c.current(own)[1]['selected.gsr']==selected_raw,'transition process original installed selection')
            cert=own['applied-end/certificate.gsr'];cert_digest=e.digest(cert)
            parent_view=c.current(own)[2]['capsule']['cut']['view']
            publish_sequence=len(set(parent_view['old'])|set(parent_view['new']))+1
            need(f.decode(cert,'records','CERTIFICATE')['entry']==e.digest(entry_raw),'transition process original applied certificate')
            inside=rows[start:end+1];store=[v['event'] for k,v in inside if k=='STORE']
            ordered=['ACCEPT_PARENT_FORCED','PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED',
                     'APPLY_BEFORE_RETURN','PUBLICATION_SELECTOR_FORCED']
            if complete or profile['point']=='PUBLICATION_BEFORE_RETURN':
                ordered+=['PUBLICATION_RETIRED','FUTURE_RETENTION_PROMOTED','FUTURE_RETENTION_CLEARED','PUBLICATION_BEFORE_RETURN']
            if complete:ordered+=['PUBLICATION_ACK_BEFORE_RETURN']
            d.s.ordered(store,ordered,'transition original proposer '+str(index))
            slot_rows=[(i,v) for i,(k,v) in enumerate(inside) if k=='SLOT']
            need([v['event'] for _,v in slot_rows]==['APPLIED']+['FUTURE_QUORUM_COMPLETE']*(len(voters)-1)+(['PUBLISHED'] if complete else [])
                 and all(base64.b64decode(v['record'],validate=True)==cert and v['voters']==voters for _,v in slot_rows),
                 'transition process original slot lifecycle')
            requests=[];received=[]
            for i,(kind,value) in enumerate(inside):
                if kind=='BEFORE_REQUEST_WRITE':
                    raw=base64.b64decode(value,validate=True)
                    if int.from_bytes(raw[8:10],'big')==f.catalog()['wire']['PUBLISH']['id']:
                        requests.append((i,raw,f.decode(raw,'wire','PUBLISH')))
                elif kind=='AFTER_RESPONSE_READ':
                    raw=base64.b64decode(value['request'],validate=True)
                    if int.from_bytes(raw[8:10],'big')==f.catalog()['wire']['PUBLISH']['id']:received.append(value)
            need(requests and max(i for i,v in slot_rows if v['event']=='FUTURE_QUORUM_COMPLETE')<min(i for i,_,_ in requests),
                 'transition process retention before publication')
            need({r['recipient']['node'] for _,_,r in requests}==set(voters)-{'node-1'},'transition process publication recipient quorum')
            for peer in voters[1:]:
                sent=[(raw,r) for _,raw,r in requests if r['recipient']['node']==peer]
                need(0<len(sent)<=3 and all(raw==sent[0][0] for raw,_ in sent),'transition process bounded original publication')
                request_raw,request=sent[0];base=history/('interrupted' if not complete else f'{mode}-published-{index}')/peer
                files=c.inventory(base);prefix,_,packet=c.current(files)
                need(request==dict(root=selected['root'],view=selected['view'],ballot=selected['ballot'],trace=request['trace'],sequence=publish_sequence,
                     sender=identity,recipient=d.future.identity(files),payload=dict(certificate=cert_digest)),
                     'transition process exact publication request')
                reply=f.encode('wire','PUBLISH_ACK',dict(request,sender=request['recipient'],recipient=identity,
                    payload=dict(certificate=cert_digest,selection=e.digest(selected_raw),published=c.anchor(packet['capsule']),
                                 generation=e.digest(files[prefix+'generation.gsr']))))
                pair=dict(request=base64.b64encode(request_raw).decode(),response=base64.b64encode(reply).decode())
                need(pair in received and dict(pair,withheld=False) in wire,'transition process original remote acknowledgement')
                response=e.digest(reply);positions=[i for i,v in enumerate(events) if v['event']=='WIRE_RESPONSE' and v.get('response')==response]
                need(positions,'transition process original response event')
                previous=remote_ends.get(peer,-1);limit=positions[0]
                d.s.ordered([v['event'] for v in events[previous+1:limit] if v['node']==peer],
                            ['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN'],
                            'transition original peer '+peer)
                remote_ends[peer]=max(positions)
            snapshots += [f'{mode}-installed-{ordinal}',f'{mode}-applied-{index}']
            if complete:
                snapshots.append(f'{mode}-published-{index}')
                files=c.inventory(history/f'{mode}-published-{index}/node-1');prefix,_,packet=c.current(files)
                last_ack=base64.b64decode(done['record'],validate=True);ack=f.decode(last_ack,'wire','PUBLISH_ACK')
                need(ack==dict(root=selected['root'],view=selected['view'],ballot=selected['ballot'],trace=ack['trace'],sequence=1,
                     sender=identity,recipient=identity,payload=dict(certificate=cert_digest,selection=e.digest(selected_raw),
                     published=c.anchor(packet['capsule']),generation=e.digest(files[prefix+'generation.gsr']))),
                     'transition process original local acknowledgement')
        need([v for k,v in rows if k=='SNAPSHOT']==snapshots,'transition process exact observation boundaries')
        if mode=='resume':
            need(base64.b64decode(rounds[-1][1]['record'],validate=True)==last_ack
                 and (root/worker/'ready.gsrp').read_bytes()==last_ack,'transition process readiness after barrier')
            _,_,packet=c.current(c.inventory(history/'after-resume/node-1'));catalog=f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG')
            need(d.read(root/worker/'ready.json')==dict(state='READY',cut=packet['capsule']['cut'],operation=catalog['results'][-1],publicReady=False),
                 'transition process exact readiness result')


def validate(root):
    root=Path(root);profile=profile_at(root);layout(root,profile)
    original=physical(root);lifecycle(root,profile)
    return dict(original,scope='same-proposer-native-transition-process',processQualification=True,
                publicationAcknowledgementsQualified=True,networkQualification=False)


NEGATIVES={
    'extra-file':'context selection transition process inventory',
    'interrupted-selector':'admitted exact interrupted: node-1',
    'completed-selector':'admitted exact after-resume: node-1',
    'same-worker':'transition process distinct original workers',
    'wrong-exit':'transition process distinct original workers',
    'false-lock':'transition process distinct original workers',
    'premature-ready':'transition process exact interrupted boundary',
    'wrong-cut':'transition process exact interrupted boundary',
    'missing-reactivation':'transition process slot before installation',
    'missing-proposer-force':'selected retention force order: transition original proposer 7',
    'missing-peer-force':'selected retention force order: transition original peer node-2',
    'missing-remote-ack':'transition process original remote acknowledgement',
    'wrong-publication-sequence':'transition process exact publication request',
    'retention-after-send':'transition process retention before publication',
    'wrong-local-ack':'transition process original local acknowledgement',
    'wrong-ready-ack':'transition process readiness after barrier',
    'wrong-ready-result':'transition process exact readiness result',
    'missing-snapshot':'transition process exact observation boundaries',
}


def qualify(root):
    root=Path(root);original=validate(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-transition-process-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target)
            def change_json(path,change):
                value=d.read(path);change(value);path.write_bytes(f.canonical(value))
            if name=='extra-file':(target/'extra').write_bytes(b'extra')
            elif name=='interrupted-selector':(target/'history/interrupted/node-1/selector.gsr').write_bytes(b'changed')
            elif name=='completed-selector':(target/'history/after-resume/node-1/selector.gsr').write_bytes(b'changed')
            elif name in ('same-worker','wrong-exit','false-lock'):
                def change(v):
                    if name=='same-worker':v['resumePid']=v['childPid']
                    elif name=='wrong-exit':v['exit']=0
                    else:v['liveLockRefused']=not v['liveLockRefused']
                change_json(target/'process.json',change)
            elif name=='wrong-ready-ack':(target/'resumed-worker/ready.gsrp').write_bytes(b'changed')
            elif name=='wrong-ready-result':change_json(target/'resumed-worker/ready.json',lambda v:v.update(state='FOLLOWER'))
            elif name=='missing-peer-force':
                path=target/'history/events.json';values=d.read(path)
                values=[v for v in values if not (v['node']=='node-2' and v['event']=='PUBLICATION_SELECTOR_FORCED')]
                path.write_bytes(f.canonical(values))
            else:
                worker='interrupted-worker' if name in ('premature-ready','wrong-cut') else 'resumed-worker'
                path=target/worker/'stdout';rows=trace(path)
                if name=='premature-ready':rows.append(('READY','halt'))
                elif name=='wrong-cut':rows[-1]=('CUT',dict(event='PUBLICATION_BEFORE_RETURN',index=0))
                elif name=='missing-reactivation':
                    at=next(i for i,(k,v) in enumerate(rows) if k=='ROUND' and v['event']=='INSTALLED');rows.pop(at)
                elif name=='missing-proposer-force':
                    rows=[(k,v) for k,v in rows if not(k=='STORE' and v==dict(event='PROOF_PARENT_FORCED',index=7))]
                elif name=='missing-snapshot':
                    at=next(i for i,(k,_) in enumerate(rows) if k=='SNAPSHOT');rows.pop(at)
                elif name=='retention-after-send':
                    at=next(i for i,(k,v) in enumerate(rows) if k=='SLOT' and v['event']=='FUTURE_QUORUM_COMPLETE')
                    row=rows.pop(at)
                    after=next(i for i,(k,v) in enumerate(rows) if k=='BEFORE_REQUEST_WRITE' and
                               int.from_bytes(base64.b64decode(v)[8:10],'big')==f.catalog()['wire']['PUBLISH']['id'])
                    rows.insert(after+1,row)
                elif name=='missing-remote-ack':
                    rows=[(k,v) for k,v in rows if not(k=='AFTER_RESPONSE_READ' and
                          int.from_bytes(base64.b64decode(v['request'])[8:10],'big')==f.catalog()['wire']['PUBLISH']['id'])]
                elif name=='wrong-publication-sequence':
                    for i,(k,v) in enumerate(rows):
                        if k=='BEFORE_REQUEST_WRITE':
                            raw=base64.b64decode(v)
                            if int.from_bytes(raw[8:10],'big')==f.catalog()['wire']['PUBLISH']['id']:
                                request=f.decode(raw,'wire','PUBLISH');request['sequence']=1
                                rows[i]=(k,base64.b64encode(f.encode('wire','PUBLISH',request)).decode())
                elif name=='wrong-local-ack':
                    at=next(i for i,(k,v) in enumerate(rows) if k=='ROUND' and v['event']=='SLOT_COMPLETE')
                    k,v=rows[at];ack=f.decode(base64.b64decode(v['record']),'wire','PUBLISH_ACK');ack['payload']['generation']='0'*64
                    rows[at]=(k,dict(v,record=base64.b64encode(f.encode('wire','PUBLISH_ACK',ack)).decode()))
                else:raise ValueError('unknown transition process negative '+name)
                path.write_text(''.join(k+' '+(v if type(v) is str else f.canonical(v).decode('ascii'))+'\n' for k,v in rows))
            try:validate(target)
            except ValueError as error:need(str(error)==reason,'transition process unrelated negative: '+name+': '+str(error))
            else:raise ValueError('transition process accepted mutation: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--physical-only',action='store_true');mode.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((physical if args.physical_only else qualify if args.qualify else validate)(args.root),sort_keys=True))
