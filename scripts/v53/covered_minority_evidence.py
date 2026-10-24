"""Independent replay of a bare minority vote covered by actual majority publication.

This reader derives physical authority; typed DATA semantics remain a Java
producer check. No process-death, cross-view or maximum-capacity claim.
"""
import argparse
import copy
import json
import shutil
import struct
import tempfile
import uuid
from pathlib import Path
from . import distinct_minority_evidence as d
from . import generation_install_evidence as installation
b=d.b;e=d.e;c=d.c;t=d.t;selection=d.selection
match=b.match


def publication(root,group,slot,entry,payload,observations,names,first=None):
    representative=names[0];_,members,packet=c.current(group[representative]);cap=packet['capsule'];r=cap['root'];selected=e.f.decode(members['selected.gsr'],'records','SELECTED')
    accept=e.f.encode('records','ACCEPT',dict(root=r,authority=selected['view'],ballot=selected['ballot'],index=slot,entry=e.digest(entry)))
    ids={n:e.f.decode(files['node.gsr'],'records','NODE')['identity']['storage'] for n,files in group.items() if n in names}
    def witnesses(raw,kind):return [dict(voter=n,incarnation=ids[n],receipt=e.digest(e.f.canonical(dict(root=r,voter=n,incarnation=ids[n],phase=kind,record=e.digest(raw))))) for n in names]
    proof=e.f.encode('records','PROOF',dict(e.f.decode(accept,'records','ACCEPT'),accepts=witnesses(accept,'ACCEPT')))
    certificate=e.f.encode('records','CERTIFICATE',dict(e.f.decode(proof,'records','PROOF'),proofs=witnesses(proof,'PROOF')))
    phases={}
    for label,extra in [('accepted',[]),('proved',[proof]),('certified',[proof,certificate])]:
        phases=dict(group)
        for node in names:
            files=group[node]
            _,local,_=c.current(files);vote=e.container([files['selector.gsr'],local['promise.gsr'],local['selected.gsr'],entry,accept],payload)+b''.join(extra)
            vote=vote[:8]+struct.pack('>I',len(vote))+vote[12:]
            phases[node]=dict(files,**{'pending.accept':vote})
        match(root,f'slot-{slot}-{label}',phases)
    for node in names:
        for record in (accept,proof):observations.append(dict(voter=node,storage=ids[node],record=e.digest(record),parent=e.digest(e.f.canonical(cap['cut']))))
    image=t.plans.read(root/f'slot-{slot}-applied/{representative}/applied-end/application.image',64*e.MIB)
    after=copy.deepcopy(e.f.decode(packet['objects'][cap['catalog']],'records','CATALOG'));after['cut']=dict(cap['cut'],index=slot,entry=e.digest(entry))
    if slot==1:after.update(application=e.digest(image),applicationSequence=after['applicationSequence']+1,lastDataIndex=slot)
    else:e.need(image==members[cap['application']+'.image'],'admitted BARRIER exact image')
    catalog=e.f.encode('records','CATALOG',after)
    start=e.f.decode(packet['objects'][cap['items'][0]['statement']],'records','CHECKPOINT') if cap['items'] else dict(root=r,scope='RANGE',start=cap['cut'],catalogBefore=cap['catalog'],applicationBefore=cap['application'])
    statement=dict(start,end=after['cut'],catalogAfter=e.digest(catalog),applicationAfter=after['application']);statement_raw=e.f.encode('records','CHECKPOINT',statement)
    lower=c.anchor(cap) if slot>1 else None;lower_raw=e.f.encode('records','CHECKPOINT',dict(statement,start=lower['cut'],catalogBefore=lower['catalog'],applicationBefore=lower['application'])) if lower else None
    acks=[];lower_acks=[];applied=dict(group)
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
    objects={e.digest(group[representative][k]):group[representative][k] for k in ('root.gsr','genesis.gsr')}
    proof_objects={e.digest(v):v for v in (entry,accept,proof,certificate,payload)}
    for raw in (catalog,statement_raw,*acks,*proof_objects.values(),*([lower_raw,*lower_acks] if lower else [])):objects[e.digest(raw)]=raw
    if first:objects.update(first['proof'])
    item=dict(kind='RANGE',statement=e.digest(statement_raw),endorsements=[e.digest(v) for v in acks],certificate=None,descriptor=None)
    raw_packet=e.packet_bytes(dict(cap,cut=after['cut'],catalog=e.digest(catalog),application=after['application'],items=[item]),objects,{after['application']:len(image)})
    coverage=dict(schema='gse-v53-round-coverage/1.3' if first else 'gse-v53-selected-coverage/1.3',selection=e.digest(members['selected.gsr']),parent=c.anchor(cap),certificate=e.digest(certificate))
    if first:coverage['first']={k:first[k] for k in ('parent','end','certificate')}
    else:first=dict(parent=c.anchor(cap),end=dict(cut=after['cut'],catalog=e.digest(catalog),application=after['application']),certificate=e.digest(certificate),proof=proof_objects)
    published=dict(group)
    for node in names:
        files=group[node]
        prefix,local,_=c.current(files);new={k:local[k] for k in ('promise.gsr','basis.gsr','selected.gsr','selected-sources.gsr')}
        new.update({'source.gscp':raw_packet,c.COVERAGE:e.f.canonical(coverage),after['application']+'.image':image})
        if lower:new['ancestry.gsr']=lower_raw+b''.join(lower_acks)
        selector,generation=c.generation(new,e.p.decode(raw_packet)['capsule'],node,'b' if prefix=='generations/a/' else 'a',None)
        published[node]=dict(files,**generation,**{'selector.gsr':selector,'pending.accept':c.EMPTY})
    match(root,f'slot-{slot}-published',published);result=d.settle(root,f'slot-{slot}-settled',published,names)
    return result,first


def advanced_campaign(root,group,counter,names,installed=True,phases=()):
    proposer=names[-1];identity=e.f.decode(group[proposer]['node.gsr'],'records','NODE')['identity']
    ballot=dict(counter=counter,proposer=proposer,incarnation=identity['storage']);prepared=dict(group);rows={};packets={};identifiers=set()
    for node in names:
        files=group[node];raw,tail=d.captured(files,phases);packet=e.p.decode(raw);cap=packet['capsule'];_,members,_=c.current(files)
        actual=c.inventory(root/f'round-{counter}-prepared'/node);history=c.journal(actual['grants.gsr'],cap['root'],node);prior=c.journal(files['grants.gsr'],cap['root'],node)
        e.need(history[:len(prior)]==prior and [r[0] for r in history[len(prior):]]==['PROMISE','BASIS'],'covered exact grant extension')
        promise,basis=history[-2:];identifier=promise[2]['basisId']
        e.need(str(uuid.UUID(identifier))==identifier and identifier not in identifiers and all(r[2].get('basisId')!=identifier for r in prior),'covered fresh source UUID');identifiers.add(identifier)
        expected=dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),ballot=ballot,basisId=identifier)
        e.need(promise[2]==expected and basis[2]==dict(expected,voter=node,cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),inventory=e.digest(packet['indexBytes']),accepted=tail),'covered exact source binding')
        prefix='sources/'+identifier;changed=dict(files,**{'grants.gsr':files['grants.gsr']+promise[1]+basis[1],prefix:None,prefix+'/source.gscp':raw})
        for h in packet['images']:changed[prefix+'/'+h+'.image']=members[h+'.image']
        if node==proposer:changed['allocator.gsr']=e.f.encode('records','ALLOCATOR',dict(root=cap['root'],node=node,counter=counter))
        prepared[node]=changed;rows[node]=(promise,basis);packets[node]=packet
    match(root,f'round-{counter}-prepared',prepared)
    longest=max(reversed(names),key=lambda n:packets[n]['capsule']['cut']['index']);packet=packets[longest];cap=packet['capsule']
    for node in names:
        local=packets[node]['capsule']
        e.need(local['root']==cap['root'] and local['cut']['view']==cap['cut']['view'] and cap['cut']['view']['operation'] is None,'covered stable authority')
        if local['cut']['index']==cap['cut']['index']:e.need(c.anchor(local)==c.anchor(cap),'covered conflicting published prefix')
        else:
            e.need(len(cap['items'])==1 and cap['items'][0]['kind']=='RANGE','covered exact prefix range')
            statement=e.f.decode(packet['objects'][cap['items'][0]['statement']],'records','CHECKPOINT')
            e.need(dict(cut=statement['start'],catalog=statement['catalogBefore'],application=statement['applicationBefore'])==c.anchor(local),'covered original authenticated parent')
        tail=rows[node][1][2]['accepted']
        if tail is not None:
            accepted=e.f.decode(packets[node]['objects'][tail],'records','ACCEPT')
            e.need(accepted['index']<=cap['cut']['index'],'covered original slot not covered')
    selected=e.f.encode('records','SELECTED',dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),ballot=ballot,cut=cap['cut'],nextEntry=None,
        sources=[dict(voter=n,basisId=rows[n][1][2]['basisId'],basisDigest=e.digest(rows[n][1][1])) for n in names]))
    chosen={n:dict(files,**{'grants.gsr':files['grants.gsr']+selected}) for n,files in prepared.items()};match(root,f'round-{counter}-selected',chosen)
    result=dict(chosen);images=c.current(group[longest])[1]
    for node in names:
        prefix,_,_=c.current(group[node]);members={'promise.gsr':rows[node][0][1],'basis.gsr':rows[node][1][1],'selected.gsr':selected,
            'selected-sources.gsr':b''.join(rows[n][1][1] for n in names),'source.gscp':e.packet_bytes(cap,packet['objects'],packet['images'])}
        members.update({h+'.image':images[h+'.image'] for h in packet['images']})
        selector,generation=c.generation(members,cap,node,'b' if prefix=='generations/a/' else 'a',None)
        result[node]=dict(chosen[node],**generation,**{'selector.gsr':selector,'pending.accept':c.EMPTY})
    if installed:match(root,f'round-{counter}-installed',result)
    return chosen,result,ballot


def prefix(root,size=3,backup=False):
    e.need(type(size) is int and size in (3,4,5) and type(backup) is bool,'covered initial profile')
    names=['node-'+str(i+1) for i in range(size)];minority=names[:size-(size//2+1)];majority=names[len(minority):];observations=[]
    group=b.original(root,size,backup);group=b.campaign(root,group,1)
    ballot=e.f.decode(c.current(group['node-1'])[1]['promise.gsr'],'records','PROMISE')['ballot']
    body=d.payload(403,'minority-original');entry=d.entry(group,body,ballot)
    e.need(t.plans.read(root/'minority-entry.gsr',16384)==entry and t.plans.read(root/'minority-payload.bin',e.MIB)==body,'covered original minority ENTRY')
    group=d.vote(root,'minority-accepted',group,minority,entry,body,observations)
    group,ballot=d.campaign(root,group,3,majority);group=d.settle(root,'round-3-settled',group,majority)
    body=d.payload(404,'majority-selected');entry=d.entry(group,body,ballot)
    e.need(t.plans.read(root/'selected-entry.gsr',16384)==entry and t.plans.read(root/'selected-payload.bin',e.MIB)==body,'covered distinct majority ENTRY')
    group,_=publication(root,group,1,entry,body,observations,majority)
    before,after,_=advanced_campaign(root,group,4,names,False);match(root,'before-install',before)
    return before,after,observations


def observations(root,expected):
    actual=e.parse(t.plans.read(root/'observations.json',e.MIB));expected=set(map(e.f.canonical,expected))
    e.need(type(actual) is list and len(actual)==len(expected) and set(map(e.f.canonical,actual))==expected,'covered actual owner observations')


def clean(root,size=3,backup=False):
    e.need(type(size) is int and size in (3,4,5) and type(backup) is bool,'covered initial profile')
    root=Path(root);names=['node-'+str(i+1) for i in range(size)];majority=names[size-(size//2+1):]
    required={'original-plan.gsbp','original-application.image','initial','calls.json','observations.json','minority-entry.gsr','minority-payload.bin','selected-entry.gsr','selected-payload.bin','barrier.gsr','minority-accepted','before-install'}
    required|={f'round-{r}-{s}' for r in (1,3,4,5) for s in ('prepared','selected','installed','settled')}
    required|={f'slot-{r}-{s}' for r in (1,2) for s in ('accepted','proved','certified','applied','published','settled')}
    required|={f'typed-{s}-{n}' for s,targets in [(1,majority),(2,names)] for n in targets};selection.layout(root,required,'covered minority clean')
    _,group,observed=prefix(root,size,backup);match(root,'round-4-installed',group);group=d.settle(root,'round-4-settled',group,names)
    _,group,ballot=advanced_campaign(root,group,5,names);group=d.settle(root,'round-5-settled',group,names)
    barrier=d.entry(group,b'',ballot,'BARRIER');e.need(t.plans.read(root/'barrier.gsr',16384)==barrier,'covered continuation BARRIER')
    group,_=publication(root,group,2,barrier,b'',observed,names);observations(root,observed);calls(root,size)
    for slot,targets in [(1,majority),(2,names)]:
        for node in targets:
            _,members,packet=c.current(c.inventory(root/f'slot-{slot}-settled'/node));b.typed_image(root/f'typed-{slot}-{node}',members[packet['capsule']['application']+'.image'])
    return dict(status='PASS',voters=size,nodePublications=size+len(majority),publicBootstrap=True,freshProcesses=False,publicRuntime=False,maximalCapacity=False,independentImageSemantics=False)

OPEN=list(installation.c.OPEN)
SEAL=['ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED']
SETTLE=['SETTLED_VOTE_VALIDATED','SETTLED_VOTE_CANDIDATE_CREATED','SETTLED_VOTE_PREFIX_WRITTEN',
        'SETTLED_VOTE_CANDIDATE_WRITTEN','SETTLED_VOTE_CANDIDATE_FORCED','SETTLED_VOTE_CANDIDATE_PARENT_FORCED',
        'SETTLED_VOTE_RENAMED','SETTLED_VOTE_PARENT_FORCED','SETTLED_VOTE_BEFORE_RETURN']
CUTS=('INSTALL_MANIFEST_FORCED','INSTALL_SELECTOR_RENAMED','INSTALL_SELECTOR_FORCED',*SETTLE)


def transaction(before,after,cut=None,floor=True,phase='ACCEPT'):
    """Derive exact write prefixes across reopen, selector install and empty replacement."""
    e.need(phase in ('ACCEPT','PROOF','CERTIFICATE'),'covered opening vote phase')
    state=dict(before);trace=[]
    class Stop(Exception):pass
    def event(name):
        trace.append(name)
        if cut==name:raise Stop()
    def events(names):
        for name in names:event(name)
    def clear():
        event('SETTLED_VOTE_VALIDATED');next_file='pending.accept.next'
        if next_file not in state:state[next_file]=b'';event('SETTLED_VOTE_CANDIDATE_CREATED')
        offset=len(state[next_file]);state[next_file]=c.EMPTY[:offset+(len(c.EMPTY)-offset)//2];event('SETTLED_VOTE_PREFIX_WRITTEN')
        state[next_file]=c.EMPTY;events(SETTLE[3:6]);state['pending.accept']=state.pop(next_file);events(SETTLE[6:])
    try:
        events(OPEN)
        advanced=state['selector.gsr']==after['selector.gsr']
        if advanced and state['pending.accept']!=c.EMPTY:clear()
        opening='ACCEPT' if advanced else phase
        events([opening+'_ACTIVE_FORCED',opening+'_ACTIVE_PARENT_FORCED'])
        if not advanced:
            prefix,members,_=c.current(after);members=dict(members,**{'generation.gsr':after[prefix+'generation.gsr']});order,writes=installation.transaction(members)
            for i,name in enumerate(order):
                if name=='INSTALL_DIRECTORY_CREATED':state[prefix[:-1]]=None
                for member,index in writes.items():
                    if index==i:state[prefix+member]=members[member]
                if name=='INSTALL_SELECTOR_WRITTEN':state['selector.pending.gsr']=after['selector.gsr']
                if name=='INSTALL_SELECTOR_RENAMED':state['selector.gsr']=state.pop('selector.pending.gsr')
                event(name)
            events(OPEN);clear();event('INSTALL_BEFORE_RETURN')
        if floor:event('FLOOR_COPY_BEFORE_RETURN')
    except Stop:return state,trace
    e.need(cut is None,'covered interruption not reached')
    return state,trace


def calls(root,size=3):
    names=['node-'+str(i+1) for i in range(size)];minority=names[:size-(size//2+1)];majority=names[len(minority):];expected=[]
    def many(nodes,label):expected.extend((n,label) for n in nodes)
    def maintenance(nodes,label):many(nodes,label+'-copy');many(nodes,label+'-maintain')
    def campaign(counter,nodes,install=True):
        expected.append((nodes[-1] if counter!=1 else 'node-1',f'allocate-{counter}'))
        for phase in ('prepare','select','install') if install else ('prepare','select'):many(nodes,f'{phase}-{counter}')
    def publish(slot,nodes):
        for phase in ('accept','proof','certificate','apply','publish'):many(nodes,f'{phase}-{slot}')
        maintenance(nodes,f'slot-{slot}-settled');many(nodes,f'inspect-{slot}')
    campaign(1,names);maintenance(names,'round-1-settled');expected.append((names[-1],'entry'));many(minority,'minority-vote')
    campaign(3,majority);maintenance(majority,'round-3-settled');expected.append((names[-1],'entry'));publish(1,majority)
    campaign(4,names);many(names,'inspect-settlement');maintenance(names,'round-4-settled')
    campaign(5,names);maintenance(names,'round-5-settled');expected.append((names[-1],'entry'));publish(2,names)
    rows=e.parse(t.plans.read(root/'calls.json',8*e.MIB));e.need(type(rows) is list and len(rows)==len(expected),'covered complete owner calls')
    for row,(node,operation) in zip(rows,expected):
        e.exact(row,'node operation events');events=row['events']
        e.need(row['node']==node and row['operation']==operation and type(events) is list and 0<len(events)<=4096 and all(type(v) is str for v in events),'covered exact owner calls')
        phase=operation.split('-')[0]
        required={'allocate':['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN'],
            'prepare':['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'],'select':['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],
            'install':['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN'],
            'proof':['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'],
            'certificate':['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'],
            'apply':['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN'],
            'publish':['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN']}.get(phase)
        if required:e.need([v for v in events if v in set(required)]==required,'covered force before response: '+phase)
        if operation=='minority-vote' or phase=='accept':
            required=['ACCEPT_CANDIDATE_FORCED','ACCEPT_PARENT_FORCED','ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN']
            e.need([v for v in events if v in set(required)]==required,'covered vote force before response')
        if operation=='install-4' and node in minority:
            before=c.inventory(root/'before-install'/node);after=c.inventory(root/'round-4-installed'/node)
            _,order=transaction(before,after,floor=False);e.need(events==order,'covered exact settlement force order')
        elif any(v.startswith('SETTLED_VOTE_') for v in events):raise ValueError('covered unexpected vote settlement')


def interrupted(root):
    root=Path(root);required={'original-plan.gsbp','original-application.image','initial','observations.json','minority-entry.gsr','minority-payload.bin','selected-entry.gsr','selected-payload.bin','minority-accepted','before-install','interruptions.json'}
    required|={f'round-{r}-{s}' for r in (1,3) for s in ('prepared','selected','installed','settled')}
    required|={'round-4-prepared','round-4-selected'}|{f'slot-1-{s}' for s in ('accepted','proved','certified','applied','published','settled')}
    required|={'typed-1-node-2','typed-1-node-3'}|{'interrupted-'+point for point in CUTS};selection.layout(root,required,'covered minority interruptions')
    before,after,observed=prefix(root);observations(root,observed)
    rows=e.parse(t.plans.read(root/'interruptions.json',65536));e.need(type(rows) is list and len(rows)==len(CUTS),'covered interruption inventory')
    for row,cut in zip(rows,CUTS):
        second='ACCEPT_ACTIVE_FORCED' if cut in ('INSTALL_MANIFEST_FORCED','SETTLED_VOTE_RENAMED','SETTLED_VOTE_PARENT_FORCED','SETTLED_VOTE_BEFORE_RETURN') else 'SETTLED_VOTE_CANDIDATE_PARENT_FORCED'
        e.need(e.f.canonical(row)==e.f.canonical(dict(cut=cut,second=second,status='PASS')),'covered exact interruption identity')
        case=root/('interrupted-'+cut);selection.layout(case,{'first','second','final','events.json'},'covered interruption member')
        events=e.parse(t.plans.read(case/'events.json',e.MIB));e.exact(events,'first second final');state=before['node-1']
        for stage,point in [('first',cut),('second',second),('final',None)]:
            state,trace=transaction(state,after['node-1'],point)
            e.need(events[stage]==trace,'covered exact interruption force order: '+stage)
            e.need(c.inventory(case/stage)==state,'covered exact interruption snapshot: '+stage)
        e.need(state==after['node-1'],'covered final exact retained originals')
    for node in ('node-2','node-3'):
        _,members,packet=c.current(c.inventory(root/'slot-1-settled'/node));b.typed_image(root/f'typed-1-{node}',members[packet['capsule']['application']+'.image'])
    return dict(status='PASS',cases=len(CUTS),interruptions=2*len(CUTS),voters=3,publicBootstrap=True,freshProcesses=False,publicRuntime=False,maximalCapacity=False,independentImageSemantics=False)


def validate(clean_root,interrupted_root):
    return dict(status='PASS',clean=clean(clean_root),interrupted=interrupted(interrupted_root),freshProcesses=False)


VARIANTS={
    'missing-stage':('clean','context selection covered minority clean inventory'),
    'extra-stage':('interrupted','context selection covered minority interruptions inventory'),
    'bootstrap-seal':('clean','admitted original public bootstrap'),
    'minority-payload':('clean','covered original minority ENTRY'),
    'majority-entry':('clean','covered distinct majority ENTRY'),
    'unselected-voter':('clean','admitted exact slot-1-accepted: node-1'),
    'published-proof':('clean','admitted exact slot-1-proved: node-2'),
    'published-image':('clean','admitted exact slot-1-applied: node-3'),
    'selected-choice':('clean','admitted exact round-4-selected: node-1'),
    'early-vote-delete':('clean','admitted exact before-install: node-1'),
    'uncleared-vote':('clean','admitted exact round-4-installed: node-1'),
    'lost-old-generation':('clean','admitted exact round-4-installed: node-1'),
    'lost-original-source':('clean','admitted exact round-4-settled: node-1'),
    'stale-image':('clean','admitted exact round-4-installed: node-1'),
    'unretired-source':('clean','admitted exact round-5-settled: node-1'),
    'observations':('clean','covered actual owner observations'),
    'duplicate-observation':('interrupted','covered actual owner observations'),
    'owner-call':('clean','covered complete owner calls'),
    'early-clear-event':('clean','covered exact settlement force order'),
    'false-settlement':('clean','covered unexpected vote settlement'),
    'missing-case':('interrupted','context selection covered minority interruptions inventory'),
    'wrong-second-cut':('interrupted','covered exact interruption identity'),
    'missing-recovery-force':('interrupted','covered exact interruption force order: second'),
    'early-selector':('interrupted','covered exact interruption snapshot: first'),
    'torn-candidate':('interrupted','covered exact interruption snapshot: first'),
    'resumed-old-vote':('interrupted','covered exact interruption snapshot: final'),
    'missing-final-source':('interrupted','covered exact interruption snapshot: final'),
    'false-original-return':('interrupted','covered exact interruption force order: first'),
    'typed-image':('clean','admitted exact typed inspection image'),
    'linked-original':('clean','bootstrap plan evidence file type/capacity'),
}


def mutate(root,name,original):
    def json_edit(relative,action):
        p=root/relative;value=e.parse(p.read_bytes());action(value);p.write_bytes(e.f.canonical(value))
    if name=='missing-stage':shutil.rmtree(root/'round-4-installed')
    elif name=='extra-stage':(root/'extra').mkdir()
    elif name=='bootstrap-seal':(root/'initial/target-0/bootstrap-seal.gsbp').write_bytes(b'changed')
    elif name=='minority-payload':(root/'minority-payload.bin').write_bytes(b'changed')
    elif name=='majority-entry':(root/'selected-entry.gsr').write_bytes((root/'minority-entry.gsr').read_bytes())
    elif name=='unselected-voter':(root/'slot-1-accepted/node-1/pending.accept').write_bytes(c.EMPTY)
    elif name=='published-proof':(root/'slot-1-proved/node-2/pending.accept').write_bytes((root/'slot-1-accepted/node-2/pending.accept').read_bytes())
    elif name=='published-image':(root/'slot-1-applied/node-3/applied-end/application.image').write_bytes(b'changed')
    elif name=='selected-choice':(root/'round-4-selected/node-1/grants.gsr').write_bytes((root/'round-4-prepared/node-1/grants.gsr').read_bytes())
    elif name=='early-vote-delete':(root/'before-install/node-1/pending.accept').write_bytes(c.EMPTY)
    elif name=='uncleared-vote':(root/'round-4-installed/node-1/pending.accept').write_bytes((root/'before-install/node-1/pending.accept').read_bytes())
    elif name=='lost-old-generation':
        old=c.current(c.inventory(root/'before-install/node-1'))[0];shutil.rmtree(root/'round-4-installed/node-1'/old)
    elif name=='lost-original-source':next((root/'round-4-settled/node-1/sources').glob('*/source.gscp')).unlink()
    elif name=='stale-image':
        prefix,members,packet=c.current(c.inventory(root/'round-4-installed/node-1'))
        (root/'round-4-installed/node-1'/prefix/(packet['capsule']['application']+'.image')).write_bytes(b'changed')
    elif name=='unretired-source':(root/'round-5-settled/node-1/sources/obsolete').mkdir()
    elif name=='observations':json_edit('observations.json',lambda rows:rows.pop())
    elif name=='duplicate-observation':json_edit('observations.json',lambda rows:rows.append(rows[0]))
    elif name=='owner-call':json_edit('calls.json',lambda rows:rows.pop())
    elif name=='early-clear-event':
        def change(rows):
            events=next(r['events'] for r in rows if r['operation']=='install-4' and r['node']=='node-1');events.remove('SETTLED_VOTE_RENAMED');events.insert(0,'SETTLED_VOTE_RENAMED')
        json_edit('calls.json',change)
    elif name=='false-settlement':json_edit('calls.json',lambda rows:next(r['events'] for r in rows if r['operation']=='install-4' and r['node']=='node-2').append('SETTLED_VOTE_RENAMED'))
    elif name=='missing-case':shutil.rmtree(root/'interrupted-INSTALL_MANIFEST_FORCED')
    elif name=='wrong-second-cut':json_edit('interruptions.json',lambda rows:rows[0].update(second='SETTLED_VOTE_VALIDATED'))
    elif name=='missing-recovery-force':json_edit('interrupted-INSTALL_SELECTOR_RENAMED/events.json',lambda rows:rows['second'].remove('SETTLED_VOTE_CANDIDATE_FORCED'))
    elif name=='early-selector':(root/'interrupted-INSTALL_MANIFEST_FORCED/first/selector.gsr').write_bytes((root/'interrupted-INSTALL_MANIFEST_FORCED/final/selector.gsr').read_bytes())
    elif name=='torn-candidate':(root/'interrupted-SETTLED_VOTE_PREFIX_WRITTEN/first/pending.accept.next').write_bytes(c.EMPTY)
    elif name=='resumed-old-vote':(root/'interrupted-INSTALL_MANIFEST_FORCED/final/pending.accept').write_bytes((root/'before-install/node-1/pending.accept').read_bytes())
    elif name=='missing-final-source':next((root/'interrupted-INSTALL_MANIFEST_FORCED/final/sources').glob('*/source.gscp')).unlink()
    elif name=='false-original-return':json_edit('interrupted-INSTALL_MANIFEST_FORCED/events.json',lambda rows:rows['first'].append('INSTALL_BEFORE_RETURN'))
    elif name=='typed-image':(root/'typed-2-node-1/gse-backup-checkpoint').write_bytes(b'changed')
    elif name=='linked-original':
        p=root/'original-plan.gsbp';p.unlink();p.symlink_to((original/'original-plan.gsbp').resolve())
    else:raise ValueError('unknown covered mutation: '+name)


def qualify(clean_root,interrupted_root):
    roots=dict(clean=Path(clean_root),interrupted=Path(interrupted_root));result=validate(**{k+'_root':v for k,v in roots.items()});negatives=[]
    validators=dict(clean=clean,interrupted=interrupted)
    for name,(kind,reason) in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-covered-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(roots[kind],moved);mutate(moved,name,roots[kind])
            try:validators[kind](moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong covered rejection: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted covered mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-covered-portable-') as tmp:
        moved={k:Path(tmp)/k for k in roots}
        for k in roots:shutil.copytree(roots[k],moved[k])
        e.need(validate(moved['clean'],moved['interrupted'])==result,'covered portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('clean');parser.add_argument('interrupted');args=parser.parse_args()
    print(json.dumps(qualify(args.clean,args.interrupted),sort_keys=True))
