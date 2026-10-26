"""Rebuild unequal original publications, exact source choices and ancestry transfers.

The physical oracle derives historical ACKs from original application phases. It
never treats a received historical copy as a new force observation.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import struct
import tempfile
import uuid
from . import native_activation_evidence as n
from . import distinct_minority_evidence as minority
from .owned_cross_view_evidence import same
from .adoption_fence_evidence import quorum
b=n.b;e=b.e;c=b.c;t=b.t;p=n.p;read=n.read;match=b.match
PROFILES=tuple((s,b,l) for s in (3,4,5) for b in (False,True) for l in (1,2))
TAIL_PROFILES=((3,False,1),(3,True,2))
def name(size,backup,lower):return n.name(size,backup)+f'-lower-{lower}'

def partial_publication(root,group,first,observations,lower):
    slot=2
    names=[n for n in sorted(group) if n!=lower];quorum(c.current(group[names[0]])[2]['capsule']['cut']['view'],names);
    _,members,packet=c.current(group['node-1']);cap=packet['capsule'];r=cap['root'];selected=e.f.decode(members['selected.gsr'],'records','SELECTED')
    text=b'404:majority-selected';payload=b'\x01'+struct.pack('>HIII',1,1,4,404)+struct.pack('>I',len(text))+text if slot==2 else b''
    entry=e.f.encode('records','ENTRY',dict(root=r,authority=selected['view'],index=slot,previous=cap['cut']['entry'],origin=selected['ballot'],kind='DATA' if slot==2 else 'BARRIER',payload=e.digest(payload)))
    e.need(t.plans.read(root/f'entry-{slot}.gsr',8192)==entry and t.plans.read(root/f'payload-{slot}.bin',e.MIB)==payload,'admitted exact requested operation')
    accept=e.f.encode('records','ACCEPT',dict(root=r,authority=selected['view'],ballot=selected['ballot'],index=slot,entry=e.digest(entry)))
    ids={n:e.f.decode(files['node.gsr'],'records','NODE')['identity']['storage'] for n,files in group.items()}
    def witnesses(raw,kind):return [dict(voter=n,incarnation=ids[n],receipt=e.digest(e.f.canonical(dict(root=r,voter=n,incarnation=ids[n],phase=kind,record=e.digest(raw))))) for n in names]
    proof=e.f.encode('records','PROOF',dict(e.f.decode(accept,'records','ACCEPT'),accepts=witnesses(accept,'ACCEPT')))
    certificate=e.f.encode('records','CERTIFICATE',dict(e.f.decode(proof,'records','PROOF'),proofs=witnesses(proof,'PROOF')))
    phases={n:v for n,v in group.items() if n not in names}
    for label,extra in [('accepted',[]),('proved',[proof]),('certified',[proof,certificate])]:
        phases={n:v for n,v in group.items() if n not in names}
        for node in names:
            files=group[node]
            _,local,_=c.current(files);vote=e.container([files['selector.gsr'],local['promise.gsr'],local['selected.gsr'],entry,accept],payload)+b''.join(extra)
            vote=vote[:8]+struct.pack('>I',len(vote))+vote[12:]
            phases[node]=dict(files,**{'pending.accept':vote})
        match(root,f'slot-{slot}-{label}',phases)
    for node in names:
        for record in (accept,proof):observations.append(dict(voter=node,storage=ids[node],record=e.digest(record),parent=e.digest(e.f.canonical(cap['cut']))))
    image=t.plans.read(root/f'slot-{slot}-applied/{names[0]}/applied-end/application.image',64*e.MIB)
    after=copy.deepcopy(e.f.decode(packet['objects'][cap['catalog']],'records','CATALOG'));after['cut']=dict(cap['cut'],index=slot,entry=e.digest(entry))
    if slot==2:after.update(application=e.digest(image),applicationSequence=after['applicationSequence']+1,lastDataIndex=slot)
    else:e.need(image==members[cap['application']+'.image'],'admitted BARRIER exact image')
    catalog=e.f.encode('records','CATALOG',after)
    start=e.f.decode(packet['objects'][cap['items'][0]['statement']],'records','CHECKPOINT') if cap['items'] else dict(root=r,scope='RANGE',start=cap['cut'],catalogBefore=cap['catalog'],applicationBefore=cap['application'])
    statement=dict(start,end=after['cut'],catalogAfter=e.digest(catalog),applicationAfter=after['application']);statement_raw=e.f.encode('records','CHECKPOINT',statement)
    lower=c.anchor(cap) if slot>1 else None;lower_raw=e.f.encode('records','CHECKPOINT',dict(statement,start=lower['cut'],catalogBefore=lower['catalog'],applicationBefore=lower['application'])) if lower else None
    acks=[];lower_acks=[];applied={n:v for n,v in group.items() if n not in names}
    for node in names:
        files=phases[node]
        def ack(raw):return e.f.encode('records','CHECKPOINT_ACK',dict(root=r,voter=node,incarnation=ids[node],cut=after['cut'],statement=e.digest(raw)))
        end=dict(zip(('selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','application.image','ack.gsr'),(files['selector.gsr'],certificate,catalog,statement_raw,image,ack(statement_raw))))
        acks.append(end['ack.gsr'])
        if lower:end['parent-statement.gsr']=lower_raw;end['parent-ack.gsr']=ack(lower_raw);lower_acks.append(end['parent-ack.gsr'])
        for record in [end['ack.gsr']]+([end['parent-ack.gsr']] if lower else []):observations.append(dict(voter=node,storage=ids[node],record=e.digest(record),parent=e.digest(e.f.canonical(after['cut']))))
        end['plan.json']=e.f.canonical(dict(schema='gse-v53-applied-end/1.3',root=r,node=node,files=[dict(path=k,**e.info(v)) for k,v in sorted(end.items())]))
        applied[node]=dict(files,**{'applied-end':None},**{'applied-end/'+k:v for k,v in end.items()})
    match(root,f'slot-{slot}-applied',applied)
    objects={e.digest(group['node-1'][k]):group['node-1'][k] for k in ('root.gsr','genesis.gsr')}
    proof_objects={e.digest(v):v for v in (entry,accept,proof,certificate,payload)}
    for raw in (catalog,statement_raw,*acks,*proof_objects.values(),*([lower_raw,*lower_acks] if lower else [])):objects[e.digest(raw)]=raw
    if first:objects.update(first['proof'])
    item=dict(kind='RANGE',statement=e.digest(statement_raw),endorsements=[e.digest(v) for v in acks],certificate=None,descriptor=None)
    raw_packet=e.packet_bytes(dict(cap,cut=after['cut'],catalog=e.digest(catalog),application=after['application'],items=[item]),objects,{after['application']:len(image)})
    coverage=dict(schema='gse-v53-round-coverage/1.3' if first else 'gse-v53-selected-coverage/1.3',selection=e.digest(members['selected.gsr']),parent=c.anchor(cap),certificate=e.digest(certificate))
    if first:coverage['first']={k:first[k] for k in ('parent','end','certificate')}
    else:first=dict(parent=c.anchor(cap),end=dict(cut=after['cut'],catalog=e.digest(catalog),application=after['application']),certificate=e.digest(certificate),proof=proof_objects)
    published={n:v for n,v in group.items() if n not in names}
    for node in names:
        files=group[node]
        prefix,local,_=c.current(files);new={k:local[k] for k in ('promise.gsr','basis.gsr','selected.gsr','selected-sources.gsr')}
        new.update({'source.gscp':raw_packet,c.COVERAGE:e.f.canonical(coverage),after['application']+'.image':image})
        if lower:new['ancestry.gsr']=lower_raw+b''.join(lower_acks)
        selector,generation=c.generation(new,e.p.decode(raw_packet)['capsule'],node,'b' if prefix=='generations/a/' else 'a',None)
        published[node]=dict(files,**generation,**{'selector.gsr':selector,'pending.accept':c.EMPTY})
    match(root,f'slot-{slot}-published',published);result=dict(group);result.update(b.settled({n:published[n] for n in names}));match(root,f'slot-{slot}-settled',result)
    return result,first


def original_calls(root,names,lower,carry=False):
    expected=[('node-1','allocate-1')]
    for label in ('prepare-1','select-1','install-1','round-1-settled-copy','round-1-settled-maintain'):
        expected.extend((node,label) for node in names)
    for slot in (1,2):
        expected.append(('node-1','entry-1') if slot==1 else (names[-1],'entry'))
        participants=names if slot==1 else [node for node in names if node!=lower]
        for label in ('accept','proof','certificate','apply','publish'):
            expected.extend((node,f'{label}-{slot}') for node in participants)
        for label in (f'slot-{slot}-settled-copy',f'slot-{slot}-settled-maintain',f'inspect-{slot}'):
            expected.extend((node,label) for node in participants)
    if carry:expected.extend([(names[-1],'entry'),('node-2' if lower=='node-1' else 'node-1','tail-accept')])
    actual=read(root/'calls.json')
    e.need(type(actual) is list and len(actual)==len(expected),'native ancestry original calls')
    required={
        'allocate':['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN'],
        'prepare':['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'],
        'select':['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],
        'install':['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN'],
        'accept':['ACCEPT_ACTIVE_FORCED','ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN'],
        'proof':['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'],
        'certificate':['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'],
        'apply':['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN']*2,
        'publish':['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN'],
    }
    for row,(node,operation) in zip(actual,expected):
        e.exact(row,'node operation events');events=row['events'];phase='accept' if operation=='tail-accept' else operation.split('-')[0]
        e.need((row['node'],row['operation'])==(node,operation) and type(events) is list
               and 0<len(events)<=4096 and all(type(v) is str for v in events),'native ancestry original call order')
        if phase in required:
            e.need([v for v in events if v in set(required[phase])]==required[phase],'native ancestry original force: '+phase)


def original(root,size,backup,lower,carry=False):
    names=[f'node-{v}' for v in range(1,size+1)];lagging=f'node-{lower}'
    expected={'original-plan.gsbp','original-application.image','initial','calls.json','observations.json',
              'before-network','after-network','after-reopen'}
    expected|={f'round-1-{stage}' for stage in ('prepared','selected','installed','settled')}
    expected|={f'slot-{slot}-{stage}' for slot in (1,2) for stage in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'typed-{slot}-{node}' for slot in (1,2) for node in names if slot==1 or node!=lagging}
    expected|={f'{kind}-{slot}.{ext}' for slot in (1,2) for kind,ext in (('entry','gsr'),('payload','bin'))}
    if carry:expected|={'tail-accepted','entry-3.gsr','payload-3.bin'}
    b.selection.layout(root,expected,'native ancestry original inventory')
    group=b.original(root,size,backup);history=e.f.decode(group['node-1']['root.gsr'],'records','ROOT')['historyId']
    base=41 if backup else 0;documents=[(7,'original'),(2,'你好')] if backup else []
    n.image.application(t.plans.read(root/'original-application.image',64*e.MIB),history,base,documents)
    group=b.campaign(root,group,1);observations=[]
    group,first=b.publication(root,group,1,None,observations)
    for node,files in group.items():
        _,members,packet=c.current(files);typed=members[packet['capsule']['application']+'.image']
        b.typed_image(root/f'typed-1-{node}',typed);n.image.application(typed,history,base,documents)
    group,_=partial_publication(root,group,first,observations,lagging)
    for node,files in group.items():
        _,members,packet=c.current(files);cap=packet['capsule'];typed=members[cap['application']+'.image']
        if node!=lagging:b.typed_image(root/f'typed-2-{node}',typed)
        n.image.application(typed,history,base+(node!=lagging),documents+([] if node==lagging else [(404,'majority-selected')]))
        catalog=e.f.decode(packet['objects'][cap['catalog']],'records','CATALOG')
        e.need(cap['cut']['index']==(1 if node==lagging else 2) and catalog['applicationSequence']==base+(node!=lagging),'native ancestry original cut/sequence')
    if carry:
        source='node-2' if lower==1 else 'node-1';members=c.current(group[source])[1]
        body=minority.payload(405,'uncommitted-original');ballot=e.f.decode(members['selected.gsr'],'records','SELECTED')['ballot']
        raw=minority.entry({'node-1':group[source]},body,ballot)
        e.need(t.plans.read(root/'entry-3.gsr',8192)==raw and t.plans.read(root/'payload-3.bin',e.MIB)==body,'native ancestry original tail')
        group=minority.vote(root,'tail-accepted',group,[source],raw,body,observations)
    actual=read(root/'observations.json')
    e.need(type(actual) is list and sorted(map(e.f.canonical,actual))==sorted(map(e.f.canonical,observations)),
           'native ancestry original observations')
    original_calls(root,names,lagging,carry);b.match(root,'before-network',group)
    return group,history


def installation(root,before,lower):
    selected=t.plans.read(root/'selected.gsr',65536);selection=e.f.decode(selected,'records','SELECTED')
    names=[v['voter'] for v in selection['sources']];expected_names=[f'node-{n}' for n in range(1,len(before)//2+2)]
    e.need(names==expected_names and f'node-{lower}' in names,'native ancestry first eligible source set')
    b.selection.layout(root/'history/after-network',set(before),'native ancestry voters')
    actual={n:c.inventory(root/'history/after-network'/n) for n in before}
    prefix={n:c.current(files) for n,files in before.items()};longest='node-1'
    for node in names:
        if prefix[node][2]['capsule']['cut']['index']>prefix[longest][2]['capsule']['cut']['index']:longest=node
    captures={n:minority.captured(v) for n,v in before.items()}
    cap=prefix[longest][2]['capsule'];r=cap['root']
    identities={n:e.f.decode(v['node.gsr'],'records','NODE')['identity'] for n,v in before.items()}
    ballot=dict(counter=3,proposer='node-1',incarnation=identities['node-1']['storage'])
    bases={};promises={};prepared={};seen=set()
    old_ids={row[2]['basisId'] for node,files in before.items() for row in c.journal(files['grants.gsr'],r,node) if row[0]=='BASIS'}
    for node,files in before.items():
        if node not in names:e.need(actual[node]==files,'native ancestry unselected voter changed');continue
        initial=prefix[node][1];capture,tail=captures[node];packet=e.p.decode(capture);own=packet['capsule']
        prior=c.journal(files['grants.gsr'],r,node);rows=c.journal(actual[node]['grants.gsr'],r,node)
        e.need(rows[:len(prior)]==prior and [v[0] for v in rows[len(prior):]]==['PROMISE','BASIS','SELECTED'],'native ancestry original grant sequence')
        promise,basis=rows[-3:-1];identifier=promise[2]['basisId']
        e.need(str(uuid.UUID(identifier))==identifier and identifier not in seen|old_ids,'native ancestry fresh grant UUID');seen.add(identifier)
        expected=dict(root=r,view=e.authority(r,own['cut']['view']),ballot=ballot,basisId=identifier)
        same(promise[2],expected,'native ancestry original promise')
        same(basis[2],dict(expected,voter=node,cut=own['cut'],capsule=e.digest(packet['capsuleBytes']),
                          inventory=e.digest(packet['indexBytes']),accepted=tail),'native ancestry original basis')
        promises[node]=promise[1];bases[node]=basis[1];source='sources/'+identifier
        changed=dict(files,**{'grants.gsr':files['grants.gsr']+promise[1]+basis[1],source:None,source+'/source.gscp':capture})
        changed.update({source+'/'+h+'.image':initial[h+'.image'] for h in packet['images']})
        if node=='node-1':changed['allocator.gsr']=e.f.encode('records','ALLOCATOR',dict(root=r,node=node,counter=3))
        prepared[node]=changed
    carried=[]
    for node in names:
        if captures[node][1] is not None:
            packet=e.p.decode(captures[node][0]);accept=e.f.decode(packet['objects'][captures[node][1]],'records','ACCEPT')
            if accept['index']>cap['cut']['index']:carried.append((accept['ballot']['counter'],node,accept))
    carried=max(carried) if carried else None
    if carried:
        for node in names:
            if captures[node][1] is None:continue
            packet=e.p.decode(captures[node][0]);accept=e.f.decode(packet['objects'][captures[node][1]],'records','ACCEPT')
            if accept['index']>cap['cut']['index'] and accept['ballot']['counter']==carried[0]:
                e.need(accept['entry']==carried[2]['entry'],'native ancestry equal ballot tail conflict')
    expected=dict(root=r,view=e.authority(r,cap['cut']['view']),ballot=ballot,cut=cap['cut'],nextEntry=carried[2]['entry'] if carried else None,
                  sources=[dict(voter=n,basisId=e.f.decode(bases[n],'records','BASIS')['basisId'],basisDigest=e.digest(bases[n])) for n in names])
    e.need(selected==e.f.encode('records','SELECTED',expected),'native ancestry fixed selection')
    installed=dict(before);initial=prefix[longest][1];packet=e.p.decode(captures[longest][0]);objects=dict(packet['objects']);tail=None
    if carried:
        _,node,accept=carried;source=e.p.decode(captures[node][0]);tail=captures[node][1]
        entry=e.f.decode(source['objects'][accept['entry']],'records','ENTRY')
        for h in (tail,accept['entry'],entry['payload']):objects[h]=source['objects'][h]
    materialized=e.packet_bytes(packet['capsule'],objects,packet['images'])
    for node in names:
        files=prepared[node];files['grants.gsr']+=selected
        members={'source.gscp':materialized,'promise.gsr':promises[node],'basis.gsr':bases[node],
                 'selected.gsr':selected,'selected-sources.gsr':b''.join(bases[n] for n in names),'ancestry.gsr':initial['ancestry.gsr']}
        members.update({h+'.image':initial[h+'.image'] for h in packet['images']})
        if tail:members['owned-tail.gsr']=objects[tail]
        selector,generation=c.generation(members,e.p.decode(materialized)['capsule'],node,'b' if prefix[node][0]=='generations/a/' else 'a',tail)
        installed[node]=dict(files,**generation,**{'selector.gsr':selector})
    b.match(root/'history','after-network',installed);b.match(root/'history','after-reopen',installed)
    return selection,selected,identities,promises,bases,prefix,installed,longest,captures


def control_attempts(rows):
    """Count only byte-identical bounded control retries as the same exchange.

    Installed storage and force events are separately reconstructed; duplicate ACKs
    do not manufacture another grant or selected installation.
    """
    original={};counts={}
    for row in rows:
        sequence=p.t.wire(row['request'])[1]['sequence']
        if sequence in original:e.need(row==original[sequence],'native ancestry changed control retry')
        else:original[sequence]=row
        counts[sequence]=counts.get(sequence,0)+1;e.need(counts[sequence]<=3,'native ancestry control retry limit')
    return [original[n] for n in sorted(original)]


def network(root,selection,selected,identities,promises,bases,prefix,installed,longest,captures):
    names=[v['voter'] for v in selection['sources']];rows=read(root/'wire.json');groups={}
    e.need(type(rows) is list and 0<len(rows)<=4096,'native ancestry wire inventory')
    for row in rows:
        e.exact(row,'request response');_,request=p.t.wire(row['request']);groups.setdefault(request['trace'],[]).append(row)
    controls=[trace for trace,items in groups.items() if any(p.t.wire(v['request'])[0] in ('PREPARE','SELECTED') for v in items)]
    e.need(len(controls)==1,'native ancestry control trace');trace=controls[0]
    control=control_attempts(groups.pop(trace))
    e.need(len(control)==2*(len(names)-1),'native ancestry control inventory')
    e.need(str(uuid.UUID(trace))==trace and uuid.UUID(trace).int!=0,'native ancestry control UUID')
    installation_order=[node for node in names[1:] if node!=longest]+([longest] if longest!='node-1' else [])
    for index,row in enumerate(control):
        install=index>=len(names)-1;node=installation_order[index-len(names)+1] if install else names[index+1]
        kind,answer=('SELECTED','INSTALL_ACK') if install else ('PREPARE','PROMISE')
        request=e.f.decode(base64.b64decode(row['request'],validate=True),'wire',kind)
        response=e.f.decode(base64.b64decode(row['response'],validate=True),'wire',answer)
        fields=dict(root=selection['root'],view=selection['view'],ballot=selection['ballot'],trace=trace,sequence=index+1)
        payload=dict(selection=e.digest(selected)) if install else dict(promise=e.digest(promises['node-1']))
        reply=dict(selection=e.digest(selected),cut=selection['cut']) if install else dict(basis=e.digest(bases[node]))
        same(request,dict(fields,sender=identities['node-1'],recipient=identities[node],payload=payload),'native ancestry control request')
        same(response,dict(fields,sender=identities[node],recipient=identities['node-1'],payload=reply),'native ancestry control response')
    expected={}
    for receiver in names[1:]:
        for raw in (promises['node-1'],selected):expected[(receiver,'node-1',e.digest(raw))]=[[(e.digest(raw),raw,'RECORD')]]
        for reader,source in [('node-1',receiver)]+[(receiver,source) for source in names if source!=receiver]:
            initial=prefix[source][1];capture=captures[source][0];packet=e.p.decode(capture)
            # Every old image here was independently reconstructed as a complete
            # local retained original before any network observations are examined.
            local_images={path.rsplit('/',1)[-1][:-6] for path,raw in installed[reader].items()
                          if path.startswith('sources/') and path.endswith('.image') and raw is not None}
            values=[(e.digest(raw),raw,'RECORD') for raw in (bases[source],promises[source])]
            values.append((e.digest(packet['capsuleBytes']),capture,'CAPSULE'))
            values.extend((h,initial[h+'.image'],'APPLICATION') for h in sorted(packet['images']) if h not in local_images)
            expected[(reader,source,values[0][0])]=[values]
    for reader in names:
        if reader==longest:continue
        old_prefix,initial,packet=prefix[longest];cap=packet['capsule']
        reference=e.digest(e.f.canonical(cap['cut']))
        expected[(reader,longest,reference)]=[[(reference,initial['source.gscp'],'CAPSULE')]]
        reference=e.digest(e.f.canonical(dict(root=cap['root'],cut=cap['cut'],scope='retained-current-ancestry')))
        # The longest source installs only after the other receivers have ACKed.
        # Its original manifest, not any equal-cut replacement, must serve this read.
        manifests=[installed[longest][old_prefix+'generation.gsr']]
        expected[(reader,longest,reference)]=[[(reference,manifest,'RECORD'),(e.digest(initial['ancestry.gsr']),initial['ancestry.gsr'],'RECORD')] for manifest in manifests]
    count=0
    for items in groups.values():
        kind,request=p.t.wire(items[0]['request']);e.need(kind=='CHUNK','native ancestry transfer first kind')
        key=(request['sender']['node'],request['recipient']['node'],request['payload']['digest'])
        e.need(key in expected,'native ancestry unexpected transfer');alternatives=expected.pop(key)
        offer=p.t.wire(items[0]['response'])[1]['payload']
        matching=[v for v in alternatives if e.digest(v[0][1])==offer['digest']]
        e.need(bool(matching),'native ancestry original transfer offer')
        count+=p.transcript(items,matching[0],selection['root'],selection['view'],selection['ballot'],
                            identities[key[0]],identities[key[1]],'native ancestry source',chunk_bytes=4*e.MIB)
    e.need(not expected,'native ancestry missing transfer');return count


def case(root,size,backup,lower,carry=False):
    root=Path(root);b.selection.layout(root,{'history','receipt.json','selected.gsr','wire.json','events.json','native-final.json'},'native ancestry case')
    before,history=original(root/'history',size,backup,lower,carry)
    values=installation(root,before,lower);selection=values[0]
    count=network(root,*values);selected=[v['voter'] for v in selection['sources']];n.forces(root,sorted(before),selected)
    same(read(root/'receipt.json'),dict(schema='gse-v53-native-ancestry-tail-v1' if carry else 'gse-v53-native-ancestry-v1',status='PASS',size=size,backup=backup,lower=lower,campaigns=1,
         historicalObservationsSupplied=False,network=True,publicRuntime=False),'native ancestry receipt')
    return dict(case=name(size,backup,lower),history=history,selected=len(selected),installed=len(selected),sourceExchanges=count)


def validate(directory):
    root=Path(directory);b.selection.layout(root,{name(*p) for p in PROFILES},'native ancestry profiles')
    cases=[case(root/name(*profile),*profile) for profile in PROFILES]
    e.need(len({v['history'] for v in cases})==len(PROFILES),'native ancestry distinct histories')
    return dict(status='PASS',profiles=len(cases),installed=sum(v['installed'] for v in cases),
                sourceExchanges=sum(v['sourceExchanges'] for v in cases),independentImageSemantics=True,
                historicalObservationsSupplied=False,publicRuntime=False)


def validate_tails(directory):
    root=Path(directory);b.selection.layout(root,{name(*p) for p in TAIL_PROFILES},'native ancestry tail profiles')
    cases=[case(root/name(*profile),*profile,carry=True) for profile in TAIL_PROFILES]
    e.need(len({v['history'] for v in cases})==len(TAIL_PROFILES),'native ancestry distinct tail histories')
    return dict(status='PASS',profiles=len(cases),installed=sum(v['installed'] for v in cases),
                sourceExchanges=sum(v['sourceExchanges'] for v in cases),unpublishedTailPreserved=True,
                historicalObservationsSupplied=False,publicRuntime=False)

VARIANTS={
    'original-proof':'admitted exact slot-2-proved: node-2',
    'original-observation':'native ancestry original observations',
    'original-force':'native ancestry original force: proof',
    'selection':'native ancestry fixed selection',
    'unselected':'native ancestry unselected voter changed',
    'installed':'admitted exact after-network: node-2',
    'installed-ancestry':'admitted exact after-network: node-1',
    'reopened':'admitted exact after-reopen: node-1',
    'force':'native activation force order',
    'reopen-events':'native activation reopen events',
    'missing-ack':'native ancestry control inventory',
    'reply':'native ancestry control response',
    'missing-source':'native ancestry missing transfer',
    'source-data':'native ancestry source exact data',
    'scope':'native ancestry receipt',
    'missing-ancestry':'native ancestry missing transfer',
    'manifest':'native ancestry original transfer offer',
    'ancestry-data':'native ancestry source exact data',
    'ancestry-commit':'native ancestry source exact commit',
    'prefix-extra':'native ancestry source complete transcript',
    'control-retry-change':'native ancestry changed control retry',
    'control-retry-exhausted':'native ancestry control retry limit',
}
TAIL_VARIANTS={
    'tail-original':'admitted exact tail-accepted: node-2',
    'tail-payload':'native ancestry original tail',
    'tail-selection':'native ancestry fixed selection',
    'tail-installed':'admitted exact after-network: node-1',
    'tail-reopened':'admitted exact after-reopen: node-1',
}


def mutate(root,variant):
    if variant in {'tail-original','tail-payload'}:
        path='history/tail-accepted/node-2/pending.accept' if variant=='tail-original' else 'history/payload-3.bin'
        (root/path).write_bytes(b'changed');return
    if variant=='tail-selection':
        path=root/'selected.gsr';fields=e.f.decode(path.read_bytes(),'records','SELECTED');fields['nextEntry']=None
        path.write_bytes(e.f.encode('records','SELECTED',fields));return
    if variant in {'tail-installed','tail-reopened'}:
        node=root/'history'/('after-network' if variant=='tail-installed' else 'after-reopen')/'node-1'
        prefix=c.current(c.inventory(node))[0];(node/prefix/'owned-tail.gsr').write_bytes(b'changed');return
    paths={'original-proof':'history/slot-2-proved/node-2/pending.accept',
           'unselected':'history/after-network/node-3/allocator.gsr','installed':'history/after-network/node-2/selector.gsr',
           'reopened':'history/after-reopen/node-1/selector.gsr'}
    if variant in paths:(root/paths[variant]).write_bytes(b'changed');return
    if variant=='installed-ancestry':
        prefix=c.current(c.inventory(root/'history/after-network/node-1'))[0]
        (root/'history/after-network/node-1'/prefix/'ancestry.gsr').write_bytes(b'changed');return
    if variant in {'original-observation','original-force','selection','force','reopen-events','scope',
                   'missing-ack','reply','missing-source','source-data'}:
        n.mutate(root,variant);return
    path=root/'wire.json';rows=read(path)
    if variant.startswith('control-retry-'):
        row=next(row for row in rows if p.t.wire(row['request'])[0]=='SELECTED')
        if variant=='control-retry-exhausted':rows.extend([copy.deepcopy(row) for _ in range(3)])
        else:
            changed=copy.deepcopy(row);kind,frame=p.t.wire(changed['response']);frame['payload']['selection']='a'*64
            changed['response']=base64.b64encode(e.f.encode('wire',kind,frame)).decode();rows.append(changed)
        path.write_bytes(e.f.canonical(rows));return
    packet=c.current(c.inventory(root/'history/before-network/node-2'))[2];cap=packet['capsule']
    reference=e.digest(e.f.canonical(dict(root=cap['root'],cut=cap['cut'],scope='retained-current-ancestry')))
    ancestry_trace=next(p.t.wire(row['request'])[1]['trace'] for row in rows if p.t.wire(row['request'])[1]['payload'].get('digest')==reference)
    if variant=='missing-ancestry':rows=[row for row in rows if p.t.wire(row['request'])[1]['trace']!=ancestry_trace]
    elif variant=='prefix-extra':
        reference=e.digest(e.f.canonical(cap['cut']))
        trace=next(p.t.wire(row['request'])[1]['trace'] for row in rows if p.t.wire(row['request'])[1]['payload'].get('digest')==reference)
        rows.append(next(row for row in reversed(rows) if p.t.wire(row['request'])[1]['trace']==trace))
    else:
        member=[row for row in rows if p.t.wire(row['request'])[1]['trace']==ancestry_trace]
        row=member[0] if variant=='manifest' else member[-1] if variant=='ancestry-commit' else member[-2]
        kind,frame=p.t.wire(row['response'])
        if variant in {'manifest','ancestry-commit'}:frame['payload']['digest']='a'*64
        else:frame['payload'].update(bytes=base64.b64encode(b'changed').decode(),digest=e.digest(b'changed'))
        row['response']=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
    path.write_bytes(e.f.canonical(rows))


def qualify(directory):
    original=validate(directory);results=[]
    for variant,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-native-ancestry-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(Path(directory)/name(3,False,1),target);mutate(target,variant)
            try:case(target,3,False,1)
            except ValueError as error:e.need(str(error)==reason,'native ancestry unrelated negative: '+variant+': '+str(error))
            else:raise ValueError('native ancestry accepted negative: '+variant)
            results.append(dict(case=variant,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


def qualify_tails(directory):
    original=validate_tails(directory);results=[]
    for variant,reason in (VARIANTS|TAIL_VARIANTS).items():
        with tempfile.TemporaryDirectory(prefix='v53-native-tail-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(Path(directory)/name(3,False,1),target);mutate(target,variant)
            try:case(target,3,False,1,carry=True)
            except ValueError as error:e.need(str(error)==reason,'native ancestry unrelated tail negative: '+variant+': '+str(error))
            else:raise ValueError('native ancestry accepted tail negative: '+variant)
            results.append(dict(case=variant,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');parser.add_argument('--tails',action='store_true');args=parser.parse_args()
    action=(qualify_tails if args.qualify else validate_tails) if args.tails else (qualify if args.qualify else validate)
    print(json.dumps(action(args.directory),sort_keys=True))
