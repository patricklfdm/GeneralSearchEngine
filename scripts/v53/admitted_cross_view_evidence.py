"""Actual initial-voter REMOVE storage chains, derived from public bootstrap bytes."""
import argparse
import copy
import json
import shutil
import struct
import tempfile
import uuid
from pathlib import Path
from . import bootstrap_publication_evidence as b
from . import context_evidence as context
from .retirement_source_process_evidence import same, read
from .offline_fixture_image import application
from scripts.v43 import derived_format_v12 as core

e,c,t,selection=b.e,b.c,b.t,b.selection


def retain_item(packet,item):
    objects=packet['objects'];keys={item['statement'],*item['endorsements']}
    if item['certificate'] is not None:
        keys|={item['certificate'],item['descriptor']};cert=e.f.decode(objects[item['certificate']],'records','CERTIFICATE')
        keys.add(cert['entry']);entry=e.f.decode(objects[cert['entry']],'records','ENTRY');keys.add(entry['payload'])
        proof={k:v for k,v in cert.items() if k!='proofs'};accept={k:v for k,v in proof.items() if k!='accepts'}
        keys|={e.digest(e.f.encode('records','PROOF',proof)),e.digest(e.f.encode('records','ACCEPT',accept))}
    return {k:objects[k] for k in keys}


class Walk:
    def __init__(self,root,size,backup):
        self.root=Path(root);self.required={'original-plan.gsbp','original-application.image','initial','calls.json','observations.json'}
        self.required|={'round-1-'+s for s in ('prepared','selected','installed','settled')}
        self.group=b.campaign(self.root,b.original(self.root,size,backup),1)
        self.active=sorted(self.group);self.slot=0;self.counter=2;self.first=None;self.observed=set();self.phases={}
        for label in ('prepare-1','select-1','install-1'):self.phase(label,self.active)
        self.documents=[(7,'original'),(2,'你好')] if backup else []
        root=e.f.decode(self.group[self.active[0]]['root.gsr'],'records','ROOT');self.history=root['historyId']
        application((self.root/'original-application.image').read_bytes(),self.history,root['baseSequence'],self.documents)

    def snapshot(self,name,group):
        self.required.add(name);b.match(self.root,name,group)

    def state(self):
        _,members,packet=c.current(self.group[self.active[0]]);cap=packet['capsule']
        return members,packet,cap,e.f.decode(packet['objects'][cap['catalog']],'records','CATALOG')

    def observed_add(self,node,raw,cut):
        identity=e.f.decode(self.group[node]['node.gsr'],'records','NODE')['identity']
        self.observed.add(e.f.canonical(dict(voter=node,storage=identity['storage'],record=e.digest(raw),parent=e.digest(e.f.canonical(cut)))))

    def phase(self,label,nodes):self.phases[label]=list(nodes)

    def settle(self,label,group,nodes):
        result=dict(group);result.update(b.settled({n:group[n] for n in nodes}));self.snapshot(label,result);return result

    def publish(self,kind,command=None,nodes=None):
        nodes=nodes or self.active;members,packet,cap,before=self.state();self.slot+=1;slot=self.slot
        selected=e.f.decode(members['selected.gsr'],'records','SELECTED');r=cap['root'];ids={n:e.f.decode(self.group[n]['node.gsr'],'records','NODE')['identity']['storage'] for n in nodes}
        payload=b'' if kind=='BARRIER' else command if kind=='DATA' else e.f.canonical(command)
        entry=e.f.encode('records','ENTRY',dict(root=r,authority=e.authority(r,cap['cut']['view']),index=slot,previous=cap['cut']['entry'],origin=selected['ballot'],kind=kind,payload=e.digest(payload)))
        for name,data in ((f'entry-{slot}.gsr',entry),(f'payload-{slot}.bin',payload)):
            self.required.add(name);e.need((self.root/name).read_bytes()==data,'cross-view requested command')
        context.majority(cap['cut']['view'],nodes)
        accept=e.f.encode('records','ACCEPT',dict(root=r,authority=selected['view'],ballot=selected['ballot'],index=slot,entry=e.digest(entry)))
        def witnesses(raw,phase):return [dict(voter=n,incarnation=ids[n],receipt=e.digest(e.f.canonical(dict(root=r,voter=n,incarnation=ids[n],phase=phase,record=e.digest(raw))))) for n in nodes]
        proof=e.f.encode('records','PROOF',dict(e.f.decode(accept,'records','ACCEPT'),accepts=witnesses(accept,'ACCEPT')))
        cert=e.f.encode('records','CERTIFICATE',dict(e.f.decode(proof,'records','PROOF'),proofs=witnesses(proof,'PROOF')))
        phases=None
        for stage,extra in [('accepted',[]),('proved',[proof]),('certified',[proof,cert])]:
            phases=dict(self.group)
            for node in nodes:
                files=self.group[node];_,local,_=c.current(files)
                vote=e.container([files['selector.gsr'],local['promise.gsr'],local['selected.gsr'],entry,accept],payload)+b''.join(extra)
                vote=vote[:8]+struct.pack('>I',len(vote))+vote[12:];phases[node]=dict(files,**{'pending.accept':vote})
            self.snapshot(f'slot-{slot}-{stage}',phases)
        for n in nodes:
            self.observed_add(n,accept,cap['cut']);self.observed_add(n,proof,cap['cut'])
        image=(self.root/f'slot-{slot}-applied'/nodes[0]/'applied-end/application.image').read_bytes()
        if kind=='DATA':
            after=copy.deepcopy(before);after.update(application=e.digest(image),applicationSequence=before['applicationSequence']+1,lastDataIndex=slot,cut=dict(cap['cut'],index=slot,entry=e.digest(entry)))
            application(image,self.history,after['applicationSequence'],self.documents+[(707,'after-removal')])
        else:
            e.need(image==members[cap['application']+'.image'],'cross-view control image changed')
            after=context.reduce_catalog(before,cap['catalog'],kind,command,e.digest(entry),r)
        context.majority(after['cut']['view'],nodes);catalog=e.f.encode('records','CATALOG',after)
        membership=kind in ('INTENT','FINAL');retained=list(cap['items']);start=dict(root=r,scope='MEMBERSHIP' if membership else 'RANGE',start=cap['cut'],catalogBefore=cap['catalog'],applicationBefore=cap['application'])
        if not membership and retained and retained[-1]['kind']=='RANGE':start=e.f.decode(packet['objects'][retained.pop()['statement']],'records','CHECKPOINT')
        statement=dict(start,end=after['cut'],catalogAfter=e.digest(catalog),applicationAfter=after['application']);raw_statement=e.f.encode('records','CHECKPOINT',statement)
        lowers=[]
        if self.first and start['start']['index']<self.first['end']['cut']['index']<cap['cut']['index']:lowers.append(('ancestor-0',self.first['end']))
        if start['start']!=cap['cut']:lowers.append(('parent',c.anchor(cap)))
        applied=dict(phases);acks=[];groups={label:[] for label,_ in lowers};bridge_rows=[]
        for n in nodes:
            def ack(raw):return e.f.encode('records','CHECKPOINT_ACK',dict(root=r,voter=n,incarnation=ids[n],cut=after['cut'],statement=e.digest(raw)))
            end=dict(zip(('selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','application.image','ack.gsr'),(phases[n]['selector.gsr'],cert,catalog,raw_statement,image,ack(raw_statement))))
            acks.append(end['ack.gsr']);self.observed_add(n,end['ack.gsr'],after['cut'])
            for label,lower in lowers:
                raw=e.f.encode('records','CHECKPOINT',dict(statement,start=lower['cut'],catalogBefore=lower['catalog'],applicationBefore=lower['application']))
                end[label+'-statement.gsr']=raw;end[label+'-ack.gsr']=ack(raw);groups[label].append(ack(raw));self.observed_add(n,ack(raw),after['cut'])
            end['plan.json']=e.f.canonical(dict(schema='gse-v53-applied-end/1.3',root=r,node=n,files=[dict(path=k,**e.info(v)) for k,v in sorted(end.items())]))
            applied[n]=dict(phases[n],**{'applied-end':None},**{'applied-end/'+k:v for k,v in end.items()})
        self.snapshot(f'slot-{slot}-applied',applied)
        objects={e.digest(self.group[nodes[0]][k]):self.group[nodes[0]][k] for k in ('root.gsr','genesis.gsr')}
        for item in retained:objects.update(retain_item(packet,item))
        for raw in (catalog,raw_statement,*acks,entry,accept,proof,cert,payload):objects[e.digest(raw)]=raw
        descriptor=None
        if membership:
            operation=next(v for v in before['results'] if v['request']['number']==before['active']);descriptor=e.f.canonical({k:operation[k] for k in ('request','prepared','receipt')});objects[e.digest(descriptor)]=descriptor
        item=dict(kind=statement['scope'],statement=e.digest(raw_statement),endorsements=[e.digest(v) for v in acks],certificate=e.digest(cert) if membership else None,descriptor=e.digest(descriptor) if membership else None)
        for label,lower in lowers:
            raw=e.f.encode('records','CHECKPOINT',dict(statement,start=lower['cut'],catalogBefore=lower['catalog'],applicationBefore=lower['application']))
            bridge_rows.append(raw+b''.join(groups[label]));objects.update({e.digest(v):v for v in (raw,*groups[label])})
        if kind=='INTENT' and self.first:
            lower=self.first['end'];first_index=lower['cut']['index']
            # Keep the original hidden endpoint ending at the old RANGE; it is not
            # replaced by an endorsement spanning the membership transition.
            if first_index!=cap['cut']['index']:
                ancestry=members.get('ancestry.gsr',b'');offset=0
                while offset<len(ancestry):
                    size=48+int.from_bytes(ancestry[offset+12:offset+16],'big');raw=ancestry[offset:offset+size];offset+=size
                    value=e.f.decode(raw,'records','CHECKPOINT');raws=[raw]
                    while offset<len(ancestry) and int.from_bytes(ancestry[offset+8:offset+10],'big')!=e.f.catalog()['records']['CHECKPOINT']['id']:
                        size=48+int.from_bytes(ancestry[offset+12:offset+16],'big');raws.append(ancestry[offset:offset+size]);offset+=size
                    if value['start']==lower['cut']:bridge_rows.append(b''.join(raws));objects.update({e.digest(v):v for v in raws})
                e.need(bool(bridge_rows),'cross-view original hidden endpoint absent')
        coverage=dict(schema='gse-v53-selected-coverage/1.3' if self.first is None else 'gse-v53-round-coverage/1.3',selection=e.digest(members['selected.gsr']),parent=c.anchor(cap),certificate=e.digest(cert))
        if self.first:
            coverage['first']={k:self.first[k] for k in ('parent','end','certificate')};objects.update(self.first['proof'])
        else:self.first=dict(parent=c.anchor(cap),end=dict(cut=after['cut'],catalog=e.digest(catalog),application=after['application']),certificate=e.digest(cert),proof={e.digest(v):v for v in (entry,accept,proof,cert,payload)})
        ancestors=[v for label,v in lowers if label.startswith('ancestor')]
        if ancestors:coverage['ancestors']=ancestors
        packed=e.packet_bytes(dict(cap,cut=after['cut'],catalog=e.digest(catalog),application=after['application'],items=retained+[item]),objects,{after['application']:len(image)})
        published=dict(self.group)
        for node in nodes:
            prefix,local,_=c.current(self.group[node]);files={k:local[k] for k in ('promise.gsr','basis.gsr','selected.gsr','selected-sources.gsr')}
            files.update({'source.gscp':packed,c.COVERAGE:e.f.canonical(coverage),after['application']+'.image':image})
            if bridge_rows:files['ancestry.gsr']=b''.join(bridge_rows)
            selector,generation=c.generation(files,e.p.decode(packed)['capsule'],node,'b' if prefix=='generations/a/' else 'a',None)
            published[node]=dict(self.group[node],**generation,**{'selector.gsr':selector,'pending.accept':c.EMPTY})
        self.snapshot(f'slot-{slot}-published',published);self.group=self.settle(f'slot-{slot}-settled',published,nodes)
        for phase in ('accept','proof','certificate','apply','publish'):self.phase(f'{phase}-{slot}',nodes)

    def campaign(self,names=None):
        self.counter+=1;counter=self.counter;names=names or self.active;prepared=dict(self.group);rows={};members,packet,cap,_=self.state()
        local=e.f.decode(self.group[names[0]]['node.gsr'],'records','NODE')['identity'];ballot=dict(counter=counter,proposer=names[0],incarnation=local['storage'])
        for n in names:
            files=self.group[n];actual=c.inventory(self.root/f'campaign-{counter}-prepared'/n);history=c.journal(actual['grants.gsr'],cap['root'],n);prior=c.journal(files['grants.gsr'],cap['root'],n)
            e.need(history[:len(prior)]==prior and [r[0] for r in history[len(prior):]]==['PROMISE','BASIS'],'cross-view fresh grant history')
            promise,basis=history[-2:];identifier=promise[2]['basisId'];e.need(str(uuid.UUID(identifier))==identifier and identifier not in {r[2].get('basisId') for r in prior},'cross-view fresh source identity')
            fields=dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),ballot=ballot,basisId=identifier)
            same(promise[2],fields,'cross-view fresh promise');same(basis[2],dict(fields,voter=n,cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),inventory=e.digest(packet['indexBytes']),accepted=None),'cross-view fresh basis')
            source='sources/'+identifier;expected=dict(files,**{'grants.gsr':files['grants.gsr']+promise[1]+basis[1],source:None,source+'/source.gscp':members['source.gscp']})
            expected.update({source+'/'+h+'.image':members[h+'.image'] for h in packet['images']})
            if n==names[0]:expected['allocator.gsr']=e.f.encode('records','ALLOCATOR',dict(root=cap['root'],node=n,counter=counter))
            prepared[n]=expected;rows[n]=(promise,basis)
        self.snapshot(f'campaign-{counter}-prepared',prepared);context.majority(cap['cut']['view'],names)
        selected=e.f.encode('records','SELECTED',dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),ballot=ballot,cut=cap['cut'],nextEntry=None,sources=[dict(voter=n,basisId=rows[n][1][2]['basisId'],basisDigest=e.digest(rows[n][1][1])) for n in names]))
        chosen=dict(prepared);installed=dict(prepared)
        for n in names:
            chosen[n]=dict(prepared[n],**{'grants.gsr':prepared[n]['grants.gsr']+selected})
            prefix,old,_=c.current(self.group[n]);files=dict(zip(('promise.gsr','basis.gsr','selected.gsr','selected-sources.gsr','source.gscp'),(rows[n][0][1],rows[n][1][1],selected,b''.join(rows[v][1][1] for v in names),members['source.gscp'])))
            files.update({h+'.image':members[h+'.image'] for h in packet['images']});selector,generation=c.generation(files,cap,n,'b' if prefix=='generations/a/' else 'a',None)
            installed[n]=dict(chosen[n],**generation,**{'selector.gsr':selector})
        self.snapshot(f'campaign-{counter}-selected',chosen);self.snapshot(f'campaign-{counter}-installed',installed)
        self.group=self.settle(f'campaign-{counter}-settled',installed,names);self.first=None
        for phase in ('prepare','select','install'):self.phase(f'{phase}-{counter}',names)

    def removed(self,number,node):
        files=self.group[node];prefix,old,packet=c.current(files);members,remote,cap,_=self.state();slot='b' if prefix=='generations/a/' else 'a'
        cert=remote['objects'][cap['items'][-1]['certificate']];certificate=e.f.decode(cert,'records','CERTIFICATE')
        # The removed voter did not capture/select the joint ballot. Adoption must
        # force the certified newer ballot before installing the removed view.
        promise=e.f.encode('records','PROMISE',dict(root=cap['root'],view=certificate['authority'],ballot=certificate['ballot'],basisId=None))
        values={'promise.gsr':promise,'source.gscp':members['source.gscp'],'adopted-certificate.gsr':cert}
        values.update({h+'.image':members[h+'.image'] for h in remote['images']})
        manifest=e.f.encode('records','GENERATION',dict(root=cap['root'],node=node,generation=slot,cut=cap['cut'],catalog=cap['catalog'],application=cap['application'],capsule=e.digest(remote['capsuleBytes']),promise=e.digest(promise),basis=None,selection=None,ownedTail=None,files=[dict(path=k,size=len(v),sha256=e.digest(v)) for k,v in sorted(values.items())]))
        values['generation.gsr']=manifest;selector=e.f.encode('records','SELECTOR',dict(root=cap['root'],node=node,generation=slot,digest=e.digest(manifest)))
        self.group[node]=dict(files,**{'selector.gsr':selector,'grants.gsr':files['grants.gsr']+promise,'generations/'+slot:None},**{'generations/'+slot+'/'+k:v for k,v in values.items()})
        self.snapshot(f'removed-{number}-adopted',self.group);self.snapshot(f'removed-{number}-refused',self.group)
        self.phase(f'removed-adopt-{number}',[node]);self.phase(f'removed-refusal-{number}',[node])


def validate_case(root,size,backup):
    w=Walk(root,size,backup);w.publish('BARRIER');number=1
    while len(w.active)>3:
        members,packet,cap,state=w.state();next_nodes=w.active[:-1];removed=w.active[-1]
        identities={v['node']:v for v in state['identities']};request=dict(root=cap['root'],expected=e.authority(cap['root'],cap['cut']['view']),number=number,kind='REMOVE',target=[identities[n] for n in next_nodes])
        w.publish('RESERVE',dict(request=request));w.publish('PREPARE',dict(number=number,revision=1));w.publish('READY',dict(number=number,receipt=None));w.publish('SEAL',dict(number=number))
        operation=w.state()[3]['results'][-1];w.publish('INTENT',dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}));w.campaign(next_nodes)
        w.publish('FINAL',dict(binding=operation['binding']),next_nodes);w.active=next_nodes;w.removed(number,removed);w.campaign();w.publish('BARRIER');w.publish('RETIRE',dict(through=number));number+=1
    text=b'707:after-removal';payload=b'\x01'+struct.pack('>HIII',1,1,4,707)+struct.pack('>I',len(text))+text
    w.publish('DATA',payload);w.publish('BARRIER')
    for node in w.active:
        _,members,packet=c.current(w.group[node]);name='typed-'+node;w.required.add(name);b.typed_image(w.root/name,members[packet['capsule']['application']+'.image'])
    observed=read(w.root/'observations.json');e.need(len(observed)==len(w.observed) and {e.f.canonical(v) for v in observed}==w.observed,'cross-view exact observations')
    calls=read(w.root/'calls.json')
    critical={'accept':['ACCEPT_ACTIVE_FORCED','ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN'],'proof':['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'],
              'certificate':['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'],'apply':['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN'],
              'publish':['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN'],'prepare':['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'],
              'select':['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],'install':['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN'],
              'removed-adopt':['ADOPTION_INSTALL_VALIDATED','PROMISE_FORCED','ADOPTION_INSTALL_FENCED','INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','ADOPTION_INSTALL_BEFORE_RETURN'],
              'removed-refusal':[]}
    for label,nodes in w.phases.items():
        selected=[v for v in calls if v['operation']==label];e.need([v['node'] for v in selected]==nodes,'cross-view force owner coverage');required=critical[label.rsplit('-',1)[0]]
        for value in selected:e.need([v for v in value['events'] if v in set(required)]==required,'cross-view force before return')
        if label.startswith('removed-refusal-'):
            e.need(not any(event.startswith(('PROMISE_','BASIS_','SELECTED_')) for v in selected for event in v['events']),'cross-view removed voter emitted grant')
    selection.layout(w.root,w.required,'cross-view profile')
    return dict(case=w.root.name,status='PASS',slots=w.slot,generations=size-3,peakImages=7)


def validate(root):
    root=Path(root);names=['size-'+str(size)+'-'+('backup' if backup else 'empty') for size in (5,4) for backup in (False,True)]
    selection.layout(root,{'receipt.json',*names},'cross-view matrix')
    rows=[validate_case(root/name,size,backup) for name,(size,backup) in zip(names,[(s,b) for s in (5,4) for b in (False,True)])]
    same(read(root/'receipt.json'),dict(schema='gse-v53-admitted-cross-view-v1',status='PASS',cases=rows,publicBootstrap=True,publicRuntime=False),'cross-view receipt')
    return dict(status='PASS',profiles=4,removals=6,slots=sum(v['slots'] for v in rows),publicBootstrap=True,publicRuntime=False,originalFirst=True)


VARIANTS={
    'initial-admission':'admitted original public bootstrap',
    'old-authority-vote':'admitted exact slot-1-accepted: node-1',
    'hidden-intent-parent':'admitted exact slot-6-published: node-1',
    'joint-grant-source':'admitted exact campaign-3-prepared: node-1',
    'joint-final-vote':'admitted exact slot-7-proved: node-1',
    'removed-fence':'admitted exact removed-1-adopted: node-5',
    'removed-regrant':'admitted exact removed-1-refused: node-5',
    'new-stable-source':'admitted exact campaign-4-prepared: node-1',
    'control-image':'cross-view control image changed',
    'data-sequence':'cross-view application sequence/documents',
    'data-document':'cross-view application document bytes',
    'observations':'cross-view exact observations',
    'force':'cross-view force before return',
    'removed-force':'cross-view force before return',
    'extra-voter':'context selection admitted publication voters inventory',
    'public-runtime':'cross-view receipt',
}


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    for name,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-cross-view-negative-') as temp:
            moved=Path(temp)/'case'
            if name=='public-runtime':
                shutil.copytree(root,moved);path=moved/'receipt.json';value=read(path);value['publicRuntime']=True;path.write_bytes(e.f.canonical(value))
            else:
                shutil.copytree(root/'size-5-empty',moved)
                direct={
                    'initial-admission':'initial/target-0/bootstrap-admission.gsbp',
                    'old-authority-vote':'slot-1-accepted/node-1/pending.accept',
                    'joint-final-vote':'slot-7-proved/node-1/pending.accept',
                    'removed-fence':'removed-1-adopted/node-5/grants.gsr',
                    'removed-regrant':'removed-1-refused/node-5/grants.gsr',
                    'control-image':'slot-1-applied/node-1/applied-end/application.image',
                }
                if name in direct:
                    path=moved/direct[name];path.write_bytes(path.read_bytes()+b'changed')
                elif name=='hidden-intent-parent':
                    path=moved/'slot-6-published/node-1';prefix,_,_=c.current(c.inventory(path));(path/prefix/'ancestry.gsr').write_bytes(b'')
                elif name in ('joint-grant-source','new-stable-source'):
                    path=moved/('campaign-3-prepared' if name=='joint-grant-source' else 'campaign-4-prepared')/'node-1';files=c.inventory(path)
                    root_hash=c.current(files)[2]['capsule']['root'];rows=c.journal(files['grants.gsr'],root_hash,'node-1');identifier=rows[-1][2]['basisId'];(path/'sources'/identifier/'source.gscp').write_bytes(b'changed')
                elif name in ('data-sequence','data-document'):
                    path=moved/'slot-18-applied/node-1/applied-end/application.image';raw=path.read_bytes();size=int.from_bytes(raw[12:16],'big');checkpoint=bytearray(raw[16:16+size])
                    if name=='data-sequence':struct.pack_into('>q',checkpoint,60,0)
                    else:
                        offset=checkpoint.index(b'707:after-removal');checkpoint[offset+4]^=1
                    checkpoint[-4:]=struct.pack('>I',core.crc32c(checkpoint[:-4]));path.write_bytes(raw[:16]+checkpoint+raw[16+size:])
                elif name in ('force','removed-force'):
                    path=moved/'calls.json';values=read(path);label,event=('accept-7','ACCEPT_ACTIVE_FORCED') if name=='force' else ('removed-adopt-1','PROMISE_FORCED')
                    next(v for v in values if v['operation']==label)['events'].remove(event);path.write_bytes(e.f.canonical(values))
                elif name=='observations':
                    path=moved/'observations.json';path.write_bytes(e.f.canonical(read(path)[1:]))
                elif name=='extra-voter':(moved/'slot-7-proved/node-extra').mkdir()
            try:
                if name=='public-runtime':validate(moved)
                else:validate_case(moved,5,False)
            except ValueError as error:e.need(str(error)==reason,'cross-view wrong negative: '+name+': '+str(error))
            else:raise ValueError('cross-view mutation accepted: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-cross-view-portable-') as temp:
        moved=Path(temp)/'raw';shutil.copytree(root,moved);same(validate(moved),result,'cross-view portable replay')
    return dict(**result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
