"""Original native FINAL publication and removal fencing, without successor votes.

The complete bootstrap and joint history are independently reduced first. This
reader covers the two explicit internal round profiles, not public operations,
all membership profiles, autonomous election scheduling or all of Phase 3.
"""
import argparse
import base64
import copy
import json
import shutil
import tempfile
from pathlib import Path
from . import continuous_transition_evidence as t

a,b,c,d,e,f,need=t.a,t.b,t.c,t.d,t.e,t.f,t.need
PROFILES={
    'removed-follower':dict(proposer='node-1',removed='node-4',published=6,ready=7,activations=2),
    'removed-proposer':dict(proposer='node-4',removed='node-4',published=6,ready=0,activations=1),
}


def maintenance(group,voters,offline):
    result=copy.deepcopy(group)
    for node in voters:
        files=result[node];prefix,_,current=c.current(files);view=current['capsule']['cut']['view']
        files={k:v for k,v in files.items() if not k.startswith('generations/') or k==prefix[:-1] or k.startswith(prefix)}
        chosen=[node];eligible=sorted(set(view['old'])|set(view['new']))
        for peer in eligible:
            if all(len(set(chosen)&set(view[side]))>len(view[side])//2 for side in ('old','new')):break
            if peer==node or peer in offline:continue
            if c.current(group[peer])[2]['capsule']['cut']==current['capsule']['cut']:chosen.append(peer)
        a.x.context.majority(view,sorted(chosen))
        for peer in chosen:
            previous=d.s.r.decode(files[d.s.FILE]);plan=copy.deepcopy(previous['plan'])
            identity=d.future.identity(group[peer]);anchor=c.anchor(c.current(group[peer])[2]['capsule'])
            next(row for row in plan['peers'] if row['identity']==identity)['possible']=[anchor]
            files[d.s.FILE]=d.s.r.frame(dict(previous,revision=previous['revision']+1,previous=e.digest(files[d.s.FILE]),plan=plan))
        result[node]=files
    return result


def install(root,group,ordinal,voters,proposer,offline):
    group=t.reconcile(group,voters)
    if ordinal>1:
        group=maintenance(group,voters,offline)
        group.update(b.settled({n:group[n] for n in voters}))
    _,_,installed=d.s.campaign(root,{n:group[n] for n in voters},ordinal+2,'installed-'+str(ordinal),
                              selected_prefix=d.slot.prefix,proposer=proposer)
    group=dict(group,**installed);b.match(root,'installed-'+str(ordinal),group)
    need((root/f'selected-{ordinal}.gsr').read_bytes()==c.current(group[proposer])[1]['selected.gsr'],
         'departure original selected bytes')
    return group


class NativeSlot(a.NativeSlot):
    def requested(self,slot,entry,payload):
        super().requested(slot,entry,payload)
        need((self.root/f'native-entry-{slot}.gsr').read_bytes()==entry and
             (self.root/f'native-payload-{slot}.bin').read_bytes()==payload,'departure original command')


def scope(root):
    result=d.read(root/'departure-result.json')
    need(type(result) is dict and result.get('profile') in PROFILES,'departure declared profile')
    expected=dict(status='PASS',profile=result['profile'],publicReady=False,**PROFILES[result['profile']])
    need(result==expected,'departure scope');return result


def lifecycle(root,result):
    rows=d.read(root/'events.json');held=[(i,v) for i,v in enumerate(rows) if v['event'].startswith('ROUND_')]
    expected=['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE']*result['activations']+(['BEFORE_READY'] if result['ready'] else [])
    need([v['event'] for _,v in held]==['ROUND_'+v for v in expected],'departure exact round lifecycle')
    ordinal=0;slot=5;selected=None;last=None;completed=-1
    for at,row in held:
        need(set(row)=={'node','event','record','bytes'} and row['node']==result['proposer'],'departure original round owner')
        raw=base64.b64decode(row['bytes'],validate=True);need(e.digest(raw)==row['record'],'departure lifecycle digest')
        if row['event']=='ROUND_INSTALLED':
            ordinal+=1;selected_raw=(root/f'selected-{ordinal}.gsr').read_bytes()
            need(raw==selected_raw,'departure lifecycle original selection');selected=f.decode(raw,'records','SELECTED')
        elif row['event']=='ROUND_SLOT_BEGIN':
            slot+=1;entry=f.decode(raw,'records','ENTRY')
            need(raw==(root/f'native-entry-{slot}.gsr').read_bytes() and entry['origin']==selected['ballot']
                 and entry['authority']==selected['view'] and entry['kind']==('FINAL' if slot==6 else 'BARRIER'),
                 'departure lifecycle original entry')
        elif row['event']=='ROUND_SLOT_COMPLETE':
            ack=f.decode(raw,'wire','PUBLISH_ACK');files=c.inventory(root/f'published-{slot}'/result['proposer'])
            prefix,_,packet=c.current(files);applied=c.inventory(root/f'applied-{slot}'/result['proposer']);identity=d.future.identity(files)
            need(ack['root']==selected['root'] and ack['view']==selected['view'] and ack['ballot']==selected['ballot']
                 and ack['sender']==ack['recipient']==identity and ack['sequence']==1 and ack['payload']==dict(
                     certificate=e.digest(applied['applied-end/certificate.gsr']),selection=e.digest(selected_raw),
                     published=c.anchor(packet['capsule']),generation=e.digest(files[prefix+'generation.gsr'])),
                 'departure original completion acknowledgement')
            completed=at;last=raw
        else:need(raw==last and slot==7,'departure readiness after successor barrier')
    if not result['ready']:
        need(not any(v['node']==result['removed'] and v['event'] in ('ALLOCATOR_FORCED','PROMISE_FORCED','FLOOR_COPIES_FORCED')
                     for v in rows[completed+1:]),'departure must stop before next campaign')
    need(slot==(7 if result['ready'] else 6),'departure complete slots')


def retention_controls(root,slot,selected_raw,within,quorums):
    selected=f.decode(selected_raw,'records','SELECTED');wire=d.read(root/'wire.json')
    targets=[n for n in slot.voters if n!=slot.proposer];local=slot.applied[slot.proposer]
    parent=c.anchor(c.current(local)[2]['capsule']);upper=c.anchor(c.current(slot.group[slot.proposer])[2]['capsule'])
    cert=local['applied-end/certificate.gsr'];certificate=f.decode(cert,'records','CERTIFICATE')
    proof=f.encode('records','PROOF',{k:v for k,v in certificate.items() if k!='proofs'})
    accept=f.encode('records','ACCEPT',{k:v for k,v in certificate.items() if k not in ('proofs','accepts')})
    frames={n:slot.applied[n][d.future.FILE] for n in slot.voters};peers={n:[] for n in slot.voters}
    for count,target in enumerate(targets,1):
        identity=d.future.identity(slot.applied[target]);plan=d.s.r.decode(local[d.s.FILE])['plan']
        lower=next(v for v in plan['peers'] if v['identity']==identity)['possible']
        need(len(lower)==1,'departure exact future lower')
        intent=dict(selection=e.digest(selected_raw),certificate=e.digest(cert),peer=identity,lower=lower[0],parent=parent,upper=upper)
        for node in slot.voters:
            original=slot.applied[node];_,members,_=c.current(original)
            records={k:original['applied-end/'+k] for k in ('selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','ack.gsr') if 'applied-end/'+k in original}
            records.update({k:members[k] for k in ('promise.gsr','selected.gsr')});records.update({'entry.gsr':slot.entry,'accept.gsr':accept,'proof.gsr':proof})
            current=frames[node];metadata=json.loads(current[48:48+int.from_bytes(current[44:48],'big')])
            peers[node].append(dict(identity=identity,lower=lower[0]))
            metadata=dict(d.future.initial(original),revision=metadata['revision']+1,previous=e.digest(current),parent=parent,peers=list(peers[node]))
            frames[node]=d.future.frame(metadata,records)
            names=[v['event'] for v in within[:quorums[count-1]] if v['node']==node]
            need(names.count('FUTURE_RETENTION_PARENT_FORCED')>=count,'departure original local retention force')
            if node==slot.proposer:continue
            matches=[]
            for row in wire:
                kind,request=d.transfer.t.wire(row['request'])
                if kind!='FUTURE_RETENTION_INTENT' or request['ballot']!=selected['ballot'] or request['recipient']!=d.future.identity(original) or request['payload'].get('peer')!=identity:continue
                answer,reply=d.transfer.t.wire(row['response']);matches.append(row)
                need(row.get('withheld') is False and request['sender']==d.future.identity(local)
                     and request['root']==selected['root'] and request['view']==selected['view'] and request['payload']==intent,
                     'departure original future intent')
                expected=dict(request,sender=request['recipient'],recipient=request['sender'],payload=dict(intent=e.digest(f.canonical(intent)),
                              storage='FUTURE',revision=metadata['revision'],digest=e.digest(frames[node])))
                need(answer=='FUTURE_RETENTION_ACK' and reply==expected,'departure original future proof ACK')
                req=e.digest(base64.b64decode(row['request'],validate=True));resp=e.digest(base64.b64decode(row['response'],validate=True))
                need(any(v['event']=='WIRE_RESPONSE' and v['request']==req and v['response']==resp for v in within[:quorums[count-1]]),
                     'departure future ACK before quorum')
            need(1<=len(matches)<=3 and all(v==matches[0] for v in matches),'departure complete bounded future ACKs')


def network(root,slot,ordinal):
    events=d.read(root/'events.json');wire=d.read(root/'wire.json')
    need(type(events) is list and len(events)<32768 and type(wire) is list and len(wire)<32768,'departure bounded traces')
    selected_raw=(root/f'selected-{ordinal}.gsr').read_bytes();selected=f.decode(selected_raw,'records','SELECTED')
    starts=[i for i,v in enumerate(events) if v['event']=='SLOT_BEGIN' and v['index']==slot.slot]
    ends=[i for i,v in enumerate(events) if v['event']=='DRIVER_PUBLISHED' and v['index']==slot.slot]
    need(len(starts)==len(ends)==1 and starts[0]<ends[0],'departure complete native slot boundary')
    start,stop=starts[0],ends[0];within=events[start:stop+1];voters=slot.voters
    quorums=[i for i,v in enumerate(within) if v['event']=='DRIVER_FUTURE_QUORUM_COMPLETE' and v['voters']==list(voters)]
    sends=[i for i,v in enumerate(within) if v['event']=='PUBLICATION_SEND_BOUNDARY']
    need(len(quorums)==len(voters)-1 and len(sends)>=len(voters)-1 and max(quorums)<min(sends),
         'departure retention before publication')
    retention_controls(root,slot,selected_raw,within,quorums)
    identities={n:d.future.identity(files) for n,files in slot.applied.items()}
    local=slot.applied[slot.proposer];cert_raw=local['applied-end/certificate.gsr'];cert=f.decode(cert_raw,'records','CERTIFICATE')
    proof=f.encode('records','PROOF',{k:v for k,v in cert.items() if k!='proofs'})
    accept=f.encode('records','ACCEPT',{k:v for k,v in cert.items() if k not in ('proofs','accepts')})
    for node in voters:
        nonvoting='applied-end/ack.gsr' not in slot.applied[node]
        d.s.ordered([v['event'] for v in within if v['node']==node],
            ['ACCEPT_PARENT_FORCED','PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED',
             'APPLY_NONVOTING_DIRECTORY_FORCED' if nonvoting else 'APPLY_ACK_DIRECTORY_FORCED',
             'FUTURE_RETENTION_PARENT_FORCED','PUBLICATION_SELECTOR_FORCED','FUTURE_RETENTION_PROMOTED','PUBLICATION_BEFORE_RETURN'],
             'departure actual durable phases '+node)
        if nonvoting:need(not any(v['node']==node and v['event']=='APPLY_ACK_DIRECTORY_FORCED' for v in within),'departure cannot force successor vote')
    controls={}
    for row in wire:
        kind,request=d.transfer.t.wire(row['request']);answer,reply=d.transfer.t.wire(row['response'])
        if request['ballot']!=selected['ballot'] or kind not in ('ACCEPT','PROOF','APPLY','PUBLISH'):continue
        need(set(row)=={'request','response','withheld'} and row['withheld'] is False,'departure complete original wire row')
        peer=request['recipient']['node']
        need(peer in voters and peer!=slot.proposer and request['sender']==identities[slot.proposer]
             and request['recipient']==identities[peer] and request['root']==selected['root'] and request['view']==selected['view'],
             'departure original wire authority')
        need({k:v for k,v in reply.items() if k!='payload'}==dict({k:v for k,v in request.items() if k!='payload'},
             sender=request['recipient'],recipient=request['sender']),'departure exact wire correlation')
        controls.setdefault((peer,kind),[]).append((row,request))
        actual=slot.applied[peer]
        if kind in ('ACCEPT','PROOF'):
            original=accept if kind=='ACCEPT' else proof
            expected={('acceptance' if kind=='ACCEPT' else 'proof'):e.digest(original)}
            payload=dict(entry=cert['entry'],receipt=e.digest(f.canonical(dict(root=selected['root'],voter=peer,
                         incarnation=identities[peer]['storage'],phase=kind,record=e.digest(original)))))
            required=[kind+'_PARENT_FORCED',kind+'_ACK_BEFORE_RETURN']
        elif kind=='APPLY':
            expected=dict(certificate=e.digest(cert_raw),selection=e.digest(selected_raw))
            payload=dict(expected,statement=e.digest(actual['applied-end/statement.gsr']),
                         acknowledgement=e.digest(actual['applied-end/ack.gsr']) if 'applied-end/ack.gsr' in actual else None)
            required=['CERTIFICATE_PARENT_FORCED','APPLY_ACK_DIRECTORY_FORCED' if payload['acknowledgement'] else 'APPLY_NONVOTING_DIRECTORY_FORCED','APPLICATION_ACK_BEFORE_RETURN']
        else:
            expected=dict(certificate=e.digest(cert_raw));prefix,_,packet=c.current(slot.group[peer])
            payload=dict(expected,selection=e.digest(selected_raw),published=c.anchor(packet['capsule']),generation=e.digest(slot.group[peer][prefix+'generation.gsr']))
            required=['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN']
        need(answer==kind+'_ACK' and request['payload']==expected and reply['payload']==payload,'departure exact original control ACK')
        req=e.digest(base64.b64decode(row['request'],validate=True));resp=e.digest(base64.b64decode(row['response'],validate=True))
        positions=[i for i,v in enumerate(within) if v['event']=='WIRE_RESPONSE' and v['request']==req and v['response']==resp]
        need(positions,'departure original response event')
        d.s.ordered([v['event'] for v in within[:min(positions)] if v['node']==peer],required,'departure force before '+kind+' ACK')
    need(set(controls)=={(n,k) for n in voters if n!=slot.proposer for k in ('ACCEPT','PROOF','APPLY','PUBLISH')},'departure complete original controls')
    for attempts in controls.values():need(1<=len(attempts)<=3 and all(v==attempts[0] for v in attempts),'departure identical bounded retries')


def validate(root):
    root=Path(root);total=0
    need(root.is_dir() and not root.is_symlink(),'departure regular original inventory')
    for count,path in enumerate(root.rglob('*'),1):
        need(not path.is_symlink() and (path.is_dir() or path.is_file()),'departure regular original inventory')
        if path.is_file():total+=path.stat().st_size
        need(count<=65536 and total<=512*e.MIB,'departure bounded original inventory')
    result=scope(root)
    expected={'initial','original-plan.gsbp','original-application.image','before-network','after-close',
              'calls.json','events.json','wire.json','failures.json','departure-result.json'}
    expected|={'round-1-'+stage for stage in ('prepared','selected','installed','settled')}
    expected|={f'slot-{i}-{stage}' for i in range(1,6) for stage in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'{name}-{i}.{ext}' for i in range(1,6) for name,ext in (('entry','gsr'),('payload','bin'))}
    expected|={f'installed-{i}' for i in range(1,result['activations']+1)}|{f'selected-{i}.gsr' for i in range(1,result['activations']+1)}
    expected|={f'{stage}-{i}' for i in range(6,6+result['activations']) for stage in ('applied','published')}
    expected|={f'native-{name}-{i}.{ext}' for i in range(6,6+result['activations']) for name,ext in (('entry','gsr'),('payload','bin'))}
    if not result['ready']:expected.add('removed-proposer-failure.txt')
    b.selection.layout(root,expected,'departure')
    walk=a.prelude(root,'FINAL');native=NativeSlot.__new__(NativeSlot);native.__dict__.update(walk.__dict__)
    native.proposer=result['proposer'];offline={'node-3'} if result['ready'] else set();profiles=[('FINAL',('node-1','node-2','node-4'))]
    if result['ready']:profiles.append(('BARRIER',('node-1','node-2')))
    for ordinal,(kind,voters) in enumerate(profiles,1):
        native.group=install(root,native.group,ordinal,voters,native.proposer,offline)
        native.group=maintenance(native.group,voters,offline);native.active=list(voters);native.voters=voters;native.first=None
        operation=native.state()[3]['results'][-1]
        native.publish(kind,dict(binding=operation['binding']) if kind=='FINAL' else None);network(root,native,ordinal)
    b.match(root,'after-close',native.group);lifecycle(root,result)
    return dict(status='PASS',profile=result['profile'],physicalQualified=True,publicReady=False,phase3Complete=False)


NEGATIVES={
    'public-ready':'departure scope',
    'wrong-owner':'departure scope',
    'extra-file':'context selection departure inventory',
    'changed-entry':'departure original command',
    'invented-departure-ack':'admitted exact applied-6: node-4',
    'missing-nonvoting-force':'selected retention force order: departure actual durable phases node-4',
    'changed-application-ack':'departure exact original control ACK',
    'missing-application-delivery':'departure complete original controls',
    'invented-ready':'departure exact round lifecycle',
    'changed-retention-proof':'departure original future proof ACK',
    'early-publication':'departure retention before publication',
}


def qualify(root):
    root=Path(root);original=validate(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-departure-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path)
            if name in ('public-ready','wrong-owner'):
                result=d.read(path/'departure-result.json');result['publicReady' if name=='public-ready' else 'removed']=True if name=='public-ready' else 'node-3'
                (path/'departure-result.json').write_text(json.dumps(result))
            elif name=='extra-file':(path/'unaccounted').write_bytes(b'')
            elif name=='changed-entry':(path/'native-entry-6.gsr').write_bytes((path/'entry-5.gsr').read_bytes())
            elif name=='invented-departure-ack':(path/'applied-6/node-4/applied-end/ack.gsr').write_bytes((path/'applied-6/node-1/applied-end/ack.gsr').read_bytes())
            elif name in ('missing-nonvoting-force','invented-ready','early-publication'):
                events=d.read(path/'events.json')
                if name=='missing-nonvoting-force':events=[v for v in events if v['event']!='APPLY_NONVOTING_DIRECTORY_FORCED']
                elif name=='early-publication':
                    send=next(v for v in events if v['event']=='PUBLICATION_SEND_BOUNDARY');events.remove(send)
                    first=next(i for i,v in enumerate(events) if v['event']=='DRIVER_FUTURE_QUORUM_COMPLETE');events.insert(first,send)
                else:events.append(dict(event='ROUND_BEFORE_READY',node='node-4'))
                (path/'events.json').write_text(json.dumps(events))
            else:
                wire=d.read(path/'wire.json');first=next(v for v in wire if d.transfer.t.wire(v['request'])[0]=='APPLY')
                if name=='changed-retention-proof':
                    first=next(v for v in wire if d.transfer.t.wire(v['response'])[0]=='FUTURE_RETENTION_ACK')
                    kind,value=d.transfer.t.wire(first['response']);value['payload']['digest']='0'*64
                    first['response']=base64.b64encode(f.encode('wire',kind,value)).decode()
                elif name=='changed-application-ack':
                    kind,value=d.transfer.t.wire(first['response']);value['payload']['acknowledgement']='0'*64
                    first['response']=base64.b64encode(f.encode('wire',kind,value)).decode()
                else:
                    _,request=d.transfer.t.wire(first['request'])
                    wire=[v for v in wire if not (d.transfer.t.wire(v['request'])[0]=='APPLY'
                          and d.transfer.t.wire(v['request'])[1]['recipient']==request['recipient']
                          and d.transfer.t.wire(v['request'])[1]['ballot']==request['ballot'])]
                (path/'wire.json').write_text(json.dumps(wire))
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'departure unrelated negative: '+name+': '+str(error))
            else:raise ValueError('departure mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
