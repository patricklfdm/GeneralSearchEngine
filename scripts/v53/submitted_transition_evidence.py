"""Original physical replay of BARRIER, submitted SEAL, INTENT, FINAL, BARRIER.

This profile has two distinct internal readiness boundaries, separated by the
same serialized membership operation. No public-service or process-fault claim.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import continuous_transition_evidence as t

a,b,c,d,e,f,need=t.a,t.b,t.c,t.d,t.e,t.f,t.need
SLOTS=((4,'BARRIER',1,('node-1','node-2','node-3')),
       (5,'SEAL',1,('node-1','node-2','node-3')),
       (6,'INTENT',1,('node-1','node-2','node-3')),
       (7,'FINAL',2,('node-1','node-2','node-3')),
       (8,'BARRIER',3,('node-1','node-2')))


class NativeSlot(t.NativeSlot):
    def required_anchors(self):
        anchors={}
        for node in self.voters:
            for name,raw in self.group[node].items():
                if name.startswith('sources/') and name.endswith('/source.gscp'):
                    lower=c.anchor(e.p.decode(raw)['capsule']);index=lower['cut']['index']
                    need(index not in anchors or anchors[index]==lower,'submitted conflicting retained source anchor')
                    anchors[index]=lower
        if self.first:
            lower=self.first['end'];index=lower['cut']['index']
            need(index not in anchors or anchors[index]==lower,'submitted conflicting first slot anchor')
            anchors[index]=lower
        return [anchors[index] for index in sorted(anchors)]


def install(root,group,ordinal,voters):
    group=t.reconcile(group,voters)
    if ordinal>1:
        group=a.maintenance(group,voters)
        group.update(b.settled({node:group[node] for node in voters}))
    _,_,installed=d.s.campaign(root,{node:group[node] for node in voters},ordinal+2,
                              'installed-'+str(ordinal),selected_prefix=d.slot.prefix)
    for node,files in installed.items():
        prefix,members,packet=c.current(files);_,prior,_=c.current(group[node]);anchors={}
        for name,raw in group[node].items():
            if name.startswith('sources/') and name.endswith('/source.gscp'):
                cut=e.p.decode(raw)['capsule']['cut'];index=cut['index']
                need(index not in anchors or anchors[index]==cut,'submitted conflicting install source')
                anchors[index]=cut
        ancestry=b''.join(a.x.retained_campaign_ancestry(prior,packet,anchors[index]) for index in sorted(anchors))
        if ancestry:
            # The old local source is still owned after the new selection.
            # Keep only its authenticated hidden bridge, never invent a vote.
            members=dict(members,**{'ancestry.gsr':ancestry})
            selector,generation=c.generation(members,packet['capsule'],node,prefix.split('/')[1],None)
            files.update(generation);files['selector.gsr']=selector
    group=dict(group,**installed);b.match(root,'installed-'+str(ordinal),group)
    need((root/f'selected-{ordinal}.gsr').read_bytes()==c.current(group['node-1'])[1]['selected.gsr'],
         'submitted original selected bytes')
    return group


def layout(root):
    need(root.is_dir() and not root.is_symlink(),'submitted regular original inventory')
    total=0
    for count,path in enumerate(root.rglob('*'),1):
        need(not path.is_symlink() and (path.is_file() or path.is_dir()),'submitted regular original inventory')
        if path.is_file():total+=path.stat().st_size
        need(count<=65536 and total<=512*e.MIB,'submitted bounded original inventory')
    expected={'initial','original-plan.gsbp','original-application.image','before-network','after-close',
              'calls.json','events.json','wire.json','failures.json'}
    expected|={'round-1-'+stage for stage in ('prepared','selected','installed','settled')}
    expected|={f'slot-{i}-{stage}' for i in range(1,4) for stage in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'{name}-{i}.{ext}' for i in range(1,4) for name,ext in (('entry','gsr'),('payload','bin'))}
    expected|={f'installed-{i}' for i in range(1,4)}|{f'selected-{i}.gsr' for i in range(1,4)}
    expected|={f'{stage}-{i}' for i in range(4,9) for stage in ('applied','published')}
    expected|={f'native-{name}-{i}.{ext}' for i in range(4,9) for name,ext in (('entry','gsr'),('payload','bin'))}
    b.selection.layout(root,expected,'submitted transition')
    for name in ('events','wire','failures'):
        rows=d.read(root/(name+'.json'));need(type(rows) is list and len(rows)<=32768,'submitted bounded traces')


def lifecycle(root):
    events=d.read(root/'events.json');rows=[row for row in events if row['event'].startswith('ROUND_')]
    wanted=['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE','BEFORE_READY','SLOT_BEGIN','SLOT_COMPLETE',
            'SLOT_BEGIN','SLOT_COMPLETE','INSTALLED','SLOT_BEGIN','SLOT_COMPLETE',
            'INSTALLED','SLOT_BEGIN','SLOT_COMPLETE','BEFORE_READY']
    need([row['event'] for row in rows]==['ROUND_'+name for name in wanted],'submitted exact lifecycle')
    ordinal=0;index=3;last=None
    for row in rows:
        need(set(row)=={'node','event','record','bytes'} and row['node']=='node-1','submitted original owner')
        raw=base64.b64decode(row['bytes'],validate=True);need(e.digest(raw)==row['record'],'submitted lifecycle digest')
        kind=row['event'].removeprefix('ROUND_')
        if kind=='INSTALLED':
            ordinal+=1;selected_raw=(root/f'selected-{ordinal}.gsr').read_bytes()
            need(raw==selected_raw,'submitted original selection');selected=f.decode(raw,'records','SELECTED')
            need(selected['nextEntry'] is None,'submitted noncarried profile')
        elif kind=='SLOT_BEGIN':
            index+=1;entry=f.decode(raw,'records','ENTRY');declared=SLOTS[index-4]
            need(raw==(root/f'native-entry-{index}.gsr').read_bytes() and entry['index']==index
                 and entry['kind']==declared[1] and ordinal==declared[2]
                 and entry['origin']==selected['ballot'] and entry['authority']==selected['view'],'submitted original entry')
        elif kind=='SLOT_COMPLETE':
            ack=f.decode(raw,'wire','PUBLISH_ACK');files=c.inventory(root/f'published-{index}/node-1')
            prefix,_,packet=c.current(files);applied=c.inventory(root/f'applied-{index}/node-1');identity=d.future.identity(files)
            need(ack['root']==selected['root'] and ack['view']==selected['view'] and ack['ballot']==selected['ballot']
                 and ack['sender']==ack['recipient']==identity and ack['sequence']==1 and ack['payload']==dict(
                     certificate=e.digest(applied['applied-end/certificate.gsr']),selection=e.digest(selected_raw),
                     published=c.anchor(packet['capsule']),generation=e.digest(files[prefix+'generation.gsr'])),
                 'submitted original completion')
            last=raw
        else:need(index in (4,8) and raw==last,'submitted readiness after stable barrier')


def publication(root,slot,ordinal):
    events=d.read(root/'events.json');wire=d.read(root/'wire.json');voters=slot.voters
    selected_raw=(root/f'selected-{ordinal}.gsr').read_bytes();selected=f.decode(selected_raw,'records','SELECTED')
    starts=[i for i,v in enumerate(events) if v['event']=='SLOT_BEGIN' and v['index']==slot.slot]
    ends=[i for i,v in enumerate(events) if v['event']=='DRIVER_PUBLISHED' and v['index']==slot.slot]
    need(len(starts)==len(ends)==1 and starts[0]<ends[0],'submitted complete slot boundary')
    within=events[starts[0]:ends[0]+1]
    quorums=[i for i,v in enumerate(within) if v['event']=='DRIVER_FUTURE_QUORUM_COMPLETE' and v['voters']==list(voters)]
    sends=[i for i,v in enumerate(within) if v['event']=='PUBLICATION_SEND_BOUNDARY']
    need(len(quorums)==len(voters)-1 and len(sends)>=len(voters)-1 and max(quorums)<min(sends),
         'submitted retention before publication')
    cert=e.digest(slot.applied['node-1']['applied-end/certificate.gsr']);responses={}
    for row in wire:
        kind,request=d.transfer.t.wire(row['request'])
        if kind!='PUBLISH' or request['ballot']!=selected['ballot'] or request['payload']!=dict(certificate=cert):continue
        answer,reply=d.transfer.t.wire(row['response']);peer=request['recipient']['node']
        need(peer in voters[1:] and row.get('withheld') is False and request['sender']==d.future.identity(slot.applied['node-1'])
             and request['recipient']==d.future.identity(slot.applied[peer]) and request['root']==selected['root']
             and request['view']==selected['view'],'submitted original publication request')
        prefix,_,packet=c.current(slot.group[peer]);payload=dict(certificate=cert,selection=e.digest(selected_raw),
            published=c.anchor(packet['capsule']),generation=e.digest(slot.group[peer][prefix+'generation.gsr']))
        need(answer=='PUBLISH_ACK' and reply==dict(request,sender=request['recipient'],recipient=request['sender'],payload=payload),
             'submitted original publication response')
        responses.setdefault(peer,[]).append(row)
        response=e.digest(base64.b64decode(row['response'],validate=True))
        at=next((i for i,v in enumerate(within) if v['event']=='WIRE_RESPONSE' and v.get('response')==response),None)
        need(at is not None,'submitted response before completion')
        d.s.ordered([v['event'] for v in within[:at] if v['node']==peer],
            ['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN'],'submitted forced publication')
    need(set(responses)==set(voters[1:]),'submitted complete publication responses')
    for attempts in responses.values():need(1<=len(attempts)<=3 and all(v==attempts[0] for v in attempts),'submitted bounded identical delivery')


def validate(root):
    root=Path(root);layout(root);walk=a.prelude(root,'READY')
    native=NativeSlot.__new__(NativeSlot);native.__dict__.update(walk.__dict__);previous=0
    for index,kind,ordinal,voters in SLOTS:
        if ordinal!=previous:
            native.group=install(root,native.group,ordinal,voters);native.first=None;previous=ordinal
        native.group=a.maintenance(native.group,voters);native.active=list(voters);native.voters=voters
        operation=native.state()[3]['results'][-1]
        command=dict(number=1) if kind=='SEAL' else dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}) if kind=='INTENT' else dict(binding=operation['binding']) if kind=='FINAL' else None
        native.publish(kind,command);need(native.slot==index,'submitted slot sequence');publication(root,native,ordinal)
    b.match(root,'after-close',native.group);lifecycle(root)
    return dict(status='PASS',profile='submitted-seal',slots=[4,5,6,7,8],activations=3,physicalQualified=True,
                internalReadyCuts=[4,8],publicReady=False,phase3Complete=False)


NEGATIVES={
    'extra-file':'context selection submitted transition inventory',
    'seal-entry':'continuous original native command',
    'missing-range-ancestor':'admitted exact applied-5: node-1',
    'missing-install-ancestor':'admitted exact installed-2: node-1',
    'changed-final-certificate':'transition exact native command',
    'changed-final-selector':'admitted exact published-8: node-1',
    'missing-reactivation':'submitted exact lifecycle',
    'early-readiness':'submitted exact lifecycle',
    'wrong-readiness':'submitted readiness after stable barrier',
    'wrong-completion':'submitted original completion',
    'changed-publication-ack':'submitted original publication response',
    'early-publication':'submitted retention before publication',
}


def qualify(root):
    root=Path(root);original=validate(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-submitted-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path)
            if name=='extra-file':(path/'unaccounted').write_bytes(b'')
            elif name=='seal-entry':(path/'native-entry-5.gsr').write_bytes((path/'native-entry-4.gsr').read_bytes())
            elif name=='missing-range-ancestor':(path/'applied-5/node-1/applied-end/ancestor-0-statement.gsr').unlink()
            elif name=='missing-install-ancestor':
                files=c.inventory(path/'installed-2/node-1');prefix=c.current(files)[0]
                (path/'installed-2/node-1'/prefix/'ancestry.gsr').unlink()
            elif name=='changed-final-certificate':
                file=path/'applied-7/node-1/applied-end/certificate.gsr';value=f.decode(file.read_bytes(),'records','CERTIFICATE')
                value['entry']='0'*64;file.write_bytes(f.encode('records','CERTIFICATE',value))
            elif name=='changed-final-selector':(path/'published-8/node-1/selector.gsr').write_bytes(b'changed')
            elif name=='changed-publication-ack':
                wire=d.read(path/'wire.json');row=next(v for v in wire if d.transfer.t.wire(v['request'])[0]=='PUBLISH')
                kind,value=d.transfer.t.wire(row['response']);value['payload']['generation']='0'*64
                row['response']=base64.b64encode(f.encode('wire',kind,value)).decode();(path/'wire.json').write_text(json.dumps(wire))
            else:
                rows=d.read(path/'events.json')
                def event(kind,ordinal=0):return [v for v in rows if v['event']=='ROUND_'+kind][ordinal]
                if name=='missing-reactivation':rows.remove(event('INSTALLED',1))
                elif name=='early-readiness':
                    ready=event('BEFORE_READY',1);rows.remove(ready);rows.insert(rows.index(event('INSTALLED',2)),ready)
                elif name in ('wrong-readiness','wrong-completion'):
                    row=event('BEFORE_READY',1) if name=='wrong-readiness' else event('SLOT_COMPLETE',1)
                    value=f.decode(base64.b64decode(row['bytes']),'wire','PUBLISH_ACK');value['payload']['generation']='0'*64
                    raw=f.encode('wire','PUBLISH_ACK',value);row.update(bytes=base64.b64encode(raw).decode(),record=e.digest(raw))
                else:
                    row=next(v for v in rows if v['event']=='PUBLICATION_SEND_BOUNDARY');rows.remove(row)
                    first=next(i for i,v in enumerate(rows) if v['event']=='DRIVER_FUTURE_QUORUM_COMPLETE');rows.insert(first,row)
                (path/'events.json').write_text(json.dumps(rows))
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'submitted unrelated negative: '+name+': '+str(error))
            else:raise ValueError('submitted mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
