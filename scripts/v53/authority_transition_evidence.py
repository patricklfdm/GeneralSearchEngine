"""Original physical replay of explicitly driven native INTENT/FINAL publication.

Storage preparation is reconstructed from admitted bootstrap. The network-side
snapshots then require the exact independently reduced votes, images, generations
and retention ledgers. This reader does not yet qualify the complete network or
process matrix, autonomous reconfiguration, learners, or public service.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import tempfile
from . import native_dispatch_evidence as d
from . import admitted_cross_view_evidence as x

b,c,e,f,need=d.b,d.c,d.e,d.f,d.need
VOTERS=('node-1','node-2','node-3')


def prelude(root,kind):
    need(kind in ('READY','INTENT','FINAL'),'transition preparation profile')
    group=d.s.initialize(b.original(root,4,False))
    group={n:dict(v,**{d.future.FILE:d.future.frame(d.future.initial(v),{})}) for n,v in group.items()}
    prepared,selected,installed=d.s.campaign(root,group,2,'round-1-prepared',selected_prefix=d.slot.prefix)
    for label,states in [('prepared',prepared),('selected',selected),('installed',installed),('settled',b.settled(installed))]:
        b.match(root,'round-1-'+label,states)
    walk=x.Walk.__new__(x.Walk);walk.root=root;walk.required=set();walk.group=b.settled(installed)
    walk.active=sorted(group);walk.slot=0;walk.counter=2;walk.first=None;walk.observed=set();walk.phases={};walk.documents=[]
    for phase in ('prepare','select','install'):walk.phase(phase+'-1',walk.active)
    walk.history=f.decode(group['node-1']['root.gsr'],'records','ROOT')['historyId']
    _,_,cap,cat=walk.state()
    request=dict(root=cap['root'],expected=e.authority(cap['root'],cap['cut']['view']),number=1,kind='REMOVE',target=cat['identities'][:3])
    controls=[('RESERVE',dict(request=request)),('PREPARE',dict(number=1,revision=1)),
              ('READY',dict(number=1,receipt=None))]
    if kind!='READY':controls.append(('SEAL',dict(number=1)))
    for control,payload in controls:walk.publish(control,payload)
    if kind=='FINAL':
        operation=walk.state()[3]['results'][-1]
        walk.publish('INTENT',dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}))
    b.match(root,'before-network',walk.group)
    calls=d.read(root/'calls.json')
    need(type(calls) is list and len(calls)<=4096,'transition bounded preparation calls')
    critical={
        'prepare':['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'],
        'select':['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],
        'install':['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN'],
        'accept':['ACCEPT_ACTIVE_FORCED','ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN'],
        'proof':['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'],
        'certificate':['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'],
        'apply':['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN']*2,
        'publish':['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN'],
    }
    for label,nodes in walk.phases.items():
        rows=[v for v in calls if v['operation']==label];required=critical[label.rsplit('-',1)[0]]
        need([v['node'] for v in rows]==nodes,'transition preparation force owners')
        for row in rows:need([v for v in row['events'] if v in required]==required,'transition preparation force before return')
    return walk


def install(root,group):
    reconciled={n:copy.deepcopy(group[n]) for n in VOTERS}
    for files in reconciled.values():
        state=d.s.r.decode(files[d.s.FILE]);view=c.current(files)[2]['capsule']['cut']['view']
        if state['plan']['view']!=view:
            plan=dict(state['plan'],view=view)
            need({p['identity']['node'] for p in plan['peers']}==set(view['old'])|set(view['new']),'transition original joining identities')
            files[d.s.FILE]=d.s.r.frame(dict(state,revision=state['revision']+1,previous=e.digest(files[d.s.FILE]),plan=plan))
    _,_,selected=d.s.campaign(root,reconciled,3,'installed',selected_prefix=d.slot.prefix)
    combined=dict(group,**selected);b.match(root,'installed',combined)
    chosen=c.current(combined['node-1'])[1]['selected.gsr']
    need((root/'selected.gsr').read_bytes()==chosen,'transition original selected bytes')
    return combined


def maintenance(group,voters=VOTERS):
    result=copy.deepcopy(group)
    for node in voters:
        files=result[node];current=c.current(files)[0]
        files={k:v for k,v in files.items() if not k.startswith('generations/') or k==current[:-1] or k.startswith(current)}
        for peer in (node,*[n for n in voters if n!=node]):
            previous=d.s.r.decode(files[d.s.FILE]);plan=copy.deepcopy(previous['plan'])
            identity=d.future.identity(group[peer]);anchor=c.anchor(c.current(group[peer])[2]['capsule'])
            next(row for row in plan['peers'] if row['identity']==identity)['possible']=[anchor]
            files[d.s.FILE]=d.s.r.frame(dict(previous,revision=previous['revision']+1,previous=e.digest(files[d.s.FILE]),plan=plan))
        result[node]=files
    return result


class NativeSlot(x.Walk):
    voters=VOTERS
    proposer='node-1'

    def requested(self,slot,entry,payload):
        certificate=f.decode((self.root/f'applied-{slot}/node-1/applied-end/certificate.gsr').read_bytes(),'records','CERTIFICATE')
        need(certificate['entry']==e.digest(entry),'transition exact native command');self.entry=entry

    def application_image(self,slot,nodes):
        return (self.root/f'applied-{slot}'/nodes[0]/'applied-end/application.image').read_bytes()

    def snapshot(self,label,group):
        if label.endswith('-applied'):
            self.applied=copy.deepcopy(group);b.match(self.root,f'applied-{self.slot}',group)
        elif label.endswith('-published'):
            for node in self.voters:
                files=group[node];original=self.applied[node];_,local,packet=c.current(original)
                prefix,members,published=c.current(files);cap=copy.deepcopy(published['capsule']);view=cap['cut']['view']
                # Checkpoint publication uses the governing end view. FINAL's
                # certificate still has the original joint ACCEPT/PROOF quorum,
                # while its new stable checkpoint needs only the new majority.
                eligible=set(view['old'])|set(view['new'])
                chosen={node} if node in eligible else set()
                for peer in sorted(eligible):
                    if all(len(chosen & set(view[side]))>len(view[side])//2 for side in ('old','new')):break
                    chosen.add(peer)
                objects=dict(published['objects']);item=cap['items'][-1];acks=[]
                for digest in item['endorsements']:
                    ack=f.decode(objects[digest],'records','CHECKPOINT_ACK')
                    if ack['voter'] in chosen:acks.append(digest)
                    else:objects.pop(digest)
                item['endorsements']=acks;members=dict(members)
                members['source.gscp']=e.packet_bytes(cap,objects,published['images'])
                selector,generation=c.generation(members,cap,node,prefix.split('/')[1],None)
                files.update(generation);files['selector.gsr']=selector
                ends={k.removeprefix('applied-end/'):v for k,v in original.items() if k.startswith('applied-end/')}
                # The complete applied snapshot was independently derived above.
                cert=f.decode(ends['certificate.gsr'],'records','CERTIFICATE')
                proof=f.encode('records','PROOF',{k:v for k,v in cert.items() if k!='proofs'})
                accept=f.encode('records','ACCEPT',{k:v for k,v in cert.items() if k not in ('proofs','accepts')})
                entry=self.entry
                retained={k:ends[k] for k in ('selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','ack.gsr') if k in ends}
                retained.update({k:local[k] for k in ('promise.gsr','selected.gsr')})
                retained.update({'entry.gsr':entry,'accept.gsr':accept,'proof.gsr':proof})
                state=d.s.r.decode(original[d.s.FILE]);plan=copy.deepcopy(state['plan']);upper=c.anchor(c.current(files)[2]['capsule']);peers=[]
                future=original[d.future.FILE]
                # This is the independently derived preceding frame, already
                # matched to the physical snapshot, not a claimed disk counter.
                prior_revision=json.loads(future[48:48+int.from_bytes(future[44:48],'big')])['revision']
                for revision,peer in enumerate((n for n in self.voters if n!=self.proposer),1):
                    identity=d.future.identity(self.group[peer]);row=next(p for p in plan['peers'] if p['identity']==identity)
                    peers.append(dict(identity=identity,lower=row['possible'][0]))
                    future=d.future.frame(dict(d.future.initial(original),revision=prior_revision+revision,previous=e.digest(future),parent=c.anchor(packet['capsule']),peers=copy.deepcopy(peers)),retained)
                    row['possible'].append(upper)
                files[d.s.FILE]=d.s.r.frame(dict(state,revision=state['revision']+1,previous=e.digest(original[d.s.FILE]),plan=plan))
                files[d.future.FILE]=d.future.frame(dict(d.future.initial(original),revision=prior_revision+len(self.voters),previous=e.digest(future)),{})
            b.match(self.root,f'published-{self.slot}',group)
        # Intermediate ACCEPT/PROOF phases have no separate captured snapshots.
        # Their exact bytes are included in the independently matched applied end.

    def settle(self,label,group,nodes):return group


def publication_boundary(root,slot):
    events=d.read(root/'events.json');wire=d.read(root/'wire.json')
    need(type(events) is list and len(events)<=32768 and type(wire) is list and len(wire)<=32768,'transition bounded traces')
    quorums=[(i,row) for i,row in enumerate(events) if row['event']=='DRIVER_FUTURE_QUORUM_COMPLETE']
    sends=[i for i,row in enumerate(events) if row['event']=='PUBLICATION_SEND_BOUNDARY']
    need(len(quorums)==2 and len(sends)>=2 and all(row['index']==slot.slot and row['voters']==list(VOTERS)
         and i<min(sends) for i,row in quorums),'transition all retention quorums before publication')
    selected=f.decode((root/'selected.gsr').read_bytes(),'records','SELECTED')
    identities={n:d.future.identity(files) for n,files in slot.group.items()};received=set()
    cert=e.digest(slot.applied['node-1']['applied-end/certificate.gsr'])
    for row in wire:
        kind,request=d.transfer.t.wire(row['request'])
        if kind!='PUBLISH':continue
        answer,reply=d.transfer.t.wire(row['response']);peer=request['recipient']['node'];received.add(peer)
        need(peer in VOTERS[1:] and answer=='PUBLISH_ACK' and row.get('withheld') is False,'transition original publication response')
        need(request['root']==selected['root'] and request['view']==selected['view'] and request['ballot']==selected['ballot']
             and request['sender']==identities['node-1'] and request['recipient']==identities[peer]
             and request['payload']==dict(certificate=cert),'transition original publication request')
        prefix,_,packet=c.current(slot.group[peer])
        payload=dict(certificate=cert,selection=e.digest((root/'selected.gsr').read_bytes()),published=c.anchor(packet['capsule']),
                     generation=e.digest(slot.group[peer][prefix+'generation.gsr']))
        expected=dict(request,sender=request['recipient'],recipient=request['sender'],payload=payload)
        need(reply==expected,'transition original publication acknowledgement')
        response=e.digest(base64.b64decode(row['response'],validate=True))
        at=next((i for i,v in enumerate(events) if v['event']=='WIRE_RESPONSE' and v.get('response')==response),None)
        need(at is not None,'transition publication response event')
        d.s.ordered([v['event'] for v in events[:at] if v['node']==peer],
            ['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN'],'transition original publication')
    need(received==set(VOTERS[1:]),'transition all original publication acknowledgements')


def validate(root):
    root=Path(root);result=d.read(root/'authority-result.json');kind=result.get('kind')
    need(kind in ('INTENT','FINAL') and result==dict(status='PASS',kind=kind,publicReady=False),'transition scope')
    last=4 if kind=='INTENT' else 5
    expected={'initial','original-plan.gsbp','original-application.image','before-network','installed','after-close',
              'calls.json','events.json','wire.json','failures.json','authority-result.json','selected.gsr',
              f'applied-{last+1}',f'published-{last+1}'}
    expected|={'round-1-'+stage for stage in ('prepared','selected','installed','settled')}
    expected|={f'slot-{slot}-{stage}' for slot in range(1,last+1) for stage in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'{name}-{slot}.{suffix}' for slot in range(1,last+1) for name,suffix in (('entry','gsr'),('payload','bin'))}
    b.selection.layout(root,expected,'authority transition')
    walk=prelude(root,kind);group=install(root,walk.group)
    native=NativeSlot.__new__(NativeSlot);native.__dict__.update(walk.__dict__)
    native.group=maintenance(group);native.active=list(VOTERS);native.first=None
    operation=native.state()[3]['results'][-1]
    command=dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}) if kind=='INTENT' else dict(binding=operation['binding'])
    native.publish(kind,command)
    b.match(root,'after-close',native.group)
    publication_boundary(root,native)
    return dict(status='PASS',kind=kind,physicalQualified=True,publicationBoundaryQualified=True,
                networkQualified=False,phase3Complete=False,publicReady=False)


NEGATIVES=('scope','extra-file','preparation-selector','installed-selector','selected',
           'applied-vote','applied-ack','published-future','published-peer','unselected','early-publication','wrong-ack','preparation-force','joint-proof-quorum')


def qualify(root):
    root=Path(root);original=validate(root);index=5 if original['kind']=='INTENT' else 6;rows=[]
    targets={
        'preparation-selector':('before-network/node-4/selector.gsr','admitted exact before-network: node-4'),
        'installed-selector':('installed/node-2/selector.gsr','admitted exact installed: node-2'),
        'selected':('selected.gsr','transition original selected bytes'),
        'applied-vote':(f'applied-{index}/node-2/pending.accept',f'admitted exact applied-{index}: node-2'),
        'applied-ack':(f'applied-{index}/node-3/applied-end/ack.gsr',f'admitted exact applied-{index}: node-3'),
        'published-future':(f'published-{index}/node-2/'+d.future.FILE,f'admitted exact published-{index}: node-2'),
        'published-peer':(f'published-{index}/node-1/'+d.s.FILE,f'admitted exact published-{index}: node-1'),
        'unselected':('after-close/node-4/selector.gsr','admitted exact after-close: node-4'),
    }
    for name in NEGATIVES:
        with tempfile.TemporaryDirectory(prefix='v53-authority-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path)
            if name=='scope':
                value=d.read(path/'authority-result.json');value['publicReady']=True
                (path/'authority-result.json').write_text(json.dumps(value));reason='transition scope'
            elif name=='extra-file':
                (path/'extra').write_bytes(b'changed');reason='context selection authority transition inventory'
            elif name=='early-publication':
                values=d.read(path/'events.json');at=next(i for i,v in enumerate(values) if v['event']=='PUBLICATION_SEND_BOUNDARY')
                row=values.pop(at);values.insert(0,row);(path/'events.json').write_text(json.dumps(values))
                reason='transition all retention quorums before publication'
            elif name=='wrong-ack':
                values=d.read(path/'wire.json');row=next(v for v in values if d.transfer.t.wire(v['request'])[0]=='PUBLISH')
                response,fields=d.transfer.t.wire(row['response']);fields['payload']['generation']='0'*64
                row['response']=base64.b64encode(f.encode('wire',response,fields)).decode();(path/'wire.json').write_text(json.dumps(values))
                reason='transition original publication acknowledgement'
            elif name=='preparation-force':
                values=d.read(path/'calls.json');row=next(v for v in values if v['operation']=='accept-1')
                row['events'].remove('ACCEPT_ACTIVE_FORCED');(path/'calls.json').write_text(json.dumps(values))
                reason='transition preparation force before return'
            elif name=='joint-proof-quorum':
                file=path/f'applied-{index}/node-1/applied-end/certificate.gsr'
                value=f.decode(file.read_bytes(),'records','CERTIFICATE');value['proofs']=value['proofs'][:2]
                file.write_bytes(f.encode('records','CERTIFICATE',value));reason=f'admitted exact applied-{index}: node-1'
            else:
                target,reason=targets[name];(path/target).write_bytes(b'changed')
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'transition unrelated negative: '+name+': '+str(error))
            else:raise ValueError('transition mutation accepted: '+name)
        rows.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--qualify',action='store_true');args=p.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
