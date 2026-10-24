"""Replay real distinct pending values from admitted owners; no transport claim."""
import argparse
import copy
import json
import shutil
import struct
import tempfile
import uuid
from pathlib import Path
from . import bootstrap_publication_evidence as b

e=b.e;c=b.c;t=b.t;selection=b.selection
match=b.match;settled=b.settled


def payload(identifier,value):
    text=(str(identifier)+':'+value).encode()
    return b'\x01'+struct.pack('>HIII',1,1,4,identifier)+struct.pack('>I',len(text))+text


def entry(group,body,ballot,kind='DATA'):
    _,_,packet=c.current(group['node-1']);cap=packet['capsule']
    return e.f.encode('records','ENTRY',dict(root=cap['root'],authority=e.authority(cap['root'],cap['cut']['view']),
        index=cap['cut']['index']+1,previous=cap['cut']['entry'],origin=ballot,kind=kind,payload=e.digest(body)))


def vote(root,stage,group,names,raw,body,observations):
    result=dict(group);record=e.f.decode(raw,'records','ENTRY')
    for n in names:
        files=group[n];_,members,packet=c.current(files);selected=e.f.decode(members['selected.gsr'],'records','SELECTED')
        accepted=e.f.encode('records','ACCEPT',dict(root=record['root'],authority=record['authority'],ballot=selected['ballot'],entry=e.digest(raw),index=record['index']))
        result[n]=dict(files,**{'pending.accept':e.container([files['selector.gsr'],members['promise.gsr'],members['selected.gsr'],raw,accepted],body)})
        identity=e.f.decode(files['node.gsr'],'records','NODE')['identity']
        observations.append(dict(voter=n,storage=identity['storage'],record=e.digest(accepted),parent=e.digest(e.f.canonical(packet['capsule']['cut']))))
    b.match(root,stage,result);return result


def captured(files):
    prefix,members,packet=c.current(files);objects=dict(packet['objects']);tail=e.f.decode(files[prefix+'generation.gsr'],'records','GENERATION')['ownedTail']
    if files['pending.accept']!=c.EMPTY:
        frames,values=c.pending(files['pending.accept'])
        for kind in ('ENTRY','ACCEPT','PAYLOAD'):objects[e.digest(frames[kind])]=frames[kind]
        if tail is None or values['ACCEPT']['ballot']['counter']>=e.f.decode(objects[tail],'records','ACCEPT')['ballot']['counter']:tail=e.digest(frames['ACCEPT'])
    return e.packet_bytes(packet['capsule'],objects,packet['images']),tail


def campaign(root,group,counter,names):
    proposer=names[-1];identity=e.f.decode(group[proposer]['node.gsr'],'records','NODE')['identity']
    ballot=dict(counter=counter,proposer=proposer,incarnation=identity['storage']);prepared=dict(group);rows={};packets={};tails={};identifiers=set()
    for n in names:
        files=group[n];raw,tail=captured(files);packet=e.p.decode(raw);cap=packet['capsule'];_,members,_=c.current(files)
        actual=c.inventory(root/f'round-{counter}-prepared'/n);history=c.journal(actual['grants.gsr'],cap['root'],n);prior=c.journal(files['grants.gsr'],cap['root'],n)
        e.need(history[:len(prior)]==prior and [r[0] for r in history[len(prior):]]==['PROMISE','BASIS'],'minority exact grant extension')
        promise,basis=history[-2:];identifier=promise[2]['basisId']
        e.need(str(uuid.UUID(identifier))==identifier and identifier not in identifiers and all(r[2].get('basisId')!=identifier for r in prior),'minority new source UUID');identifiers.add(identifier)
        expected=dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),ballot=ballot,basisId=identifier)
        e.need(promise[2]==expected and basis[2]==dict(expected,voter=n,cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),inventory=e.digest(packet['indexBytes']),accepted=tail),'minority exact source binding')
        prefix='sources/'+identifier;changed=dict(files,**{'grants.gsr':files['grants.gsr']+promise[1]+basis[1],prefix:None,prefix+'/source.gscp':raw})
        for h in packet['images']:changed[prefix+'/'+h+'.image']=members[h+'.image']
        if n==proposer:changed['allocator.gsr']=e.f.encode('records','ALLOCATOR',dict(root=cap['root'],node=n,counter=counter))
        prepared[n]=changed;rows[n]=(promise,basis);packets[n]=packet;tails[n]=tail
    b.match(root,f'round-{counter}-prepared',prepared)
    original=packets[proposer];cap=original['capsule'];choices=[]
    for n in names:
        e.need(c.anchor(packets[n]['capsule'])==c.anchor(cap),'minority common proven parent')
        if tails[n] is not None:
            raw=packets[n]['objects'][tails[n]];accept=e.f.decode(raw,'records','ACCEPT');choices.append((accept['ballot']['counter'],n,accept,raw))
    carried=max(choices,key=lambda x:x[0]) if choices else None
    for candidate in choices:
        if candidate[0]==carried[0]:e.need(candidate[2]['entry']==carried[2]['entry'],'minority equal ballot conflict')
    selected=e.f.encode('records','SELECTED',dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),ballot=ballot,cut=cap['cut'],nextEntry=carried[2]['entry'] if carried else None,
        sources=[dict(voter=n,basisId=rows[n][1][2]['basisId'],basisDigest=e.digest(rows[n][1][1])) for n in names]))
    chosen=dict(prepared)
    for n in names:chosen[n]=dict(prepared[n],**{'grants.gsr':prepared[n]['grants.gsr']+selected})
    b.match(root,f'round-{counter}-selected',chosen)
    objects=dict(original['objects']);tail=None
    if carried:
        _,n,accept,raw=carried;tail=e.digest(raw);original_entry=e.f.decode(packets[n]['objects'][accept['entry']],'records','ENTRY')
        for h in (tail,accept['entry'],original_entry['payload']):objects[h]=packets[n]['objects'][h]
    raw=e.packet_bytes(cap,objects,original['images']);installed=dict(chosen)
    for n in names:
        prefix,old,_=c.current(group[n]);members={'promise.gsr':rows[n][0][1],'basis.gsr':rows[n][1][1],'selected.gsr':selected,
            'selected-sources.gsr':b''.join(rows[k][1][1] for k in names),'source.gscp':raw}
        if tail:members['owned-tail.gsr']=objects[tail]
        members.update({h+'.image':old[h+'.image'] for h in original['images']})
        selector,generation=c.generation(members,e.p.decode(raw)['capsule'],n,'b' if prefix=='generations/a/' else 'a',tail)
        installed[n]=dict(chosen[n],**generation,**{'selector.gsr':selector})
    b.match(root,f'round-{counter}-installed',installed);return installed,ballot


def settle(root,stage,group,names):
    result=dict(group);result.update(b.settled({n:group[n] for n in names}));b.match(root,stage,result);return result
def publication(root,group,slot,entry,payload,observations):
    first=None
    names=sorted(group);_,members,packet=c.current(group['node-1']);cap=packet['capsule'];r=cap['root'];selected=e.f.decode(members['selected.gsr'],'records','SELECTED')
    accept=e.f.encode('records','ACCEPT',dict(root=r,authority=selected['view'],ballot=selected['ballot'],index=slot,entry=e.digest(entry)))
    ids={n:e.f.decode(files['node.gsr'],'records','NODE')['identity']['storage'] for n,files in group.items()}
    def witnesses(raw,kind):return [dict(voter=n,incarnation=ids[n],receipt=e.digest(e.f.canonical(dict(root=r,voter=n,incarnation=ids[n],phase=kind,record=e.digest(raw))))) for n in names]
    proof=e.f.encode('records','PROOF',dict(e.f.decode(accept,'records','ACCEPT'),accepts=witnesses(accept,'ACCEPT')))
    certificate=e.f.encode('records','CERTIFICATE',dict(e.f.decode(proof,'records','PROOF'),proofs=witnesses(proof,'PROOF')))
    phases={}
    for label,extra in [('accepted',[]),('proved',[proof]),('certified',[proof,certificate])]:
        phases={}
        for node,files in group.items():
            _,local,_=c.current(files);vote=e.container([files['selector.gsr'],local['promise.gsr'],local['selected.gsr'],entry,accept],payload)+b''.join(extra)
            vote=vote[:8]+struct.pack('>I',len(vote))+vote[12:]
            phases[node]=dict(files,**{'pending.accept':vote})
        match(root,f'slot-{slot}-{label}',phases)
    for node in names:
        for record in (accept,proof):observations.append(dict(voter=node,storage=ids[node],record=e.digest(record),parent=e.digest(e.f.canonical(cap['cut']))))
    image=t.plans.read(root/f'slot-{slot}-applied/node-1/applied-end/application.image',64*e.MIB)
    after=copy.deepcopy(e.f.decode(packet['objects'][cap['catalog']],'records','CATALOG'));after['cut']=dict(cap['cut'],index=slot,entry=e.digest(entry))
    if slot==1:after.update(application=e.digest(image),applicationSequence=after['applicationSequence']+1,lastDataIndex=slot)
    else:e.need(image==members[cap['application']+'.image'],'admitted BARRIER exact image')
    catalog=e.f.encode('records','CATALOG',after)
    start=e.f.decode(packet['objects'][cap['items'][0]['statement']],'records','CHECKPOINT') if cap['items'] else dict(root=r,scope='RANGE',start=cap['cut'],catalogBefore=cap['catalog'],applicationBefore=cap['application'])
    statement=dict(start,end=after['cut'],catalogAfter=e.digest(catalog),applicationAfter=after['application']);statement_raw=e.f.encode('records','CHECKPOINT',statement)
    lower=c.anchor(cap) if slot>1 else None;lower_raw=e.f.encode('records','CHECKPOINT',dict(statement,start=lower['cut'],catalogBefore=lower['catalog'],applicationBefore=lower['application'])) if lower else None
    acks=[];lower_acks=[];applied={}
    for node,files in phases.items():
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
    published={}
    for node,files in group.items():
        prefix,local,_=c.current(files);new={k:local[k] for k in ('promise.gsr','basis.gsr','selected.gsr','selected-sources.gsr')}
        new.update({'source.gscp':raw_packet,c.COVERAGE:e.f.canonical(coverage),after['application']+'.image':image})
        if lower:new['ancestry.gsr']=lower_raw+b''.join(lower_acks)
        selector,generation=c.generation(new,e.p.decode(raw_packet)['capsule'],node,'b' if prefix=='generations/a/' else 'a',None)
        published[node]=dict(files,**generation,**{'selector.gsr':selector,'pending.accept':c.EMPTY})
    match(root,f'slot-{slot}-published',published);result=settled(published);match(root,f'slot-{slot}-settled',result)
    return result,first


def calls(root,names,minority,majority):
    expected=[]
    def many(nodes,label):expected.extend((n,label) for n in nodes)
    def maintenance(nodes,label):many(nodes,label+'-copy');many(nodes,label+'-maintain')
    def campaign_order(counter,nodes):
        expected.append((nodes[-1],f'allocate-{counter}'))
        for label in ('prepare','select','install'):many(nodes,f'{label}-{counter}')
    def publication_order(slot):
        for label in ('accept','proof','certificate','apply','publish'):many(names,f'{label}-{slot}')
        maintenance(names,f'slot-{slot}-settled');many(names,f'inspect-{slot}')
    expected.append(('node-1','allocate-1'))
    for label in ('prepare','select','install'):many(names,label+'-1')
    maintenance(names,'round-1-settled');expected.append((names[-1],'entry'));many(minority,'minority-vote')
    campaign_order(3,majority);maintenance(majority,'round-3-settled');expected.append((names[-1],'entry'));many(majority,'majority-vote')
    campaign_order(4,names);many(names,'choice');many(minority,'retention-refusal');many(names,'replacement-vote');maintenance(names,'round-4-settled');publication_order(1)
    campaign_order(5,names);maintenance(names,'round-5-settled');expected.append((names[-1],'entry'));publication_order(2)
    actual=e.parse(t.plans.read(root/'calls.json',8*e.MIB))
    e.need(type(actual) is list and len(actual)==len(expected),'minority complete call inventory')
    for row,(node,operation) in zip(actual,expected):
        e.exact(row,'node operation events');events=row['events']
        e.need(row['node']==node and row['operation']==operation and type(events) is list and 0<len(events)<=4096 and all(type(v) is str for v in events),'minority exact owner calls')
        phase=operation.split('-')[0]
        required={'allocate':['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN'],
            'prepare':['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'],
            'select':['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],
            'install':['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN'],
            'proof':['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'],
            'certificate':['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'],
            'apply':['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN'],
            'publish':['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN']}.get(phase)
        if required:e.need([v for v in events if v in set(required)]==required,'minority force before response: '+phase)
        if operation.endswith('-vote') or phase=='accept':
            required=['ACCEPT_CANDIDATE_FORCED','ACCEPT_PARENT_FORCED'] if operation.endswith('-vote') or operation=='accept-2' else []
            required+=['ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN']
            e.need([v for v in events if v in {'ACCEPT_CANDIDATE_FORCED','ACCEPT_PARENT_FORCED','ACCEPT_BEFORE_RETURN'}]==required,'minority exact vote replacement force')
        if operation=='retention-refusal':e.need('ACCEPT_BEFORE_RETURN' not in events and not any(v.startswith('RETIREMENT_') for v in events),'minority premature retirement or rejected ACK')


def validate_case(root,size,backup):
    names=['node-'+str(i+1) for i in range(size)];count=size-(size//2+1);minority=names[:count];majority=names[count:]
    required={'original-plan.gsbp','original-application.image','initial','calls.json','observations.json','minority-entry.gsr','minority-payload.bin','selected-entry.gsr','selected-payload.bin','barrier.gsr',
        'minority-accepted','majority-accepted','minority-retained','replacement-accepted'}
    required|={f'round-{r}-{s}' for r in (1,3,4,5) for s in ('prepared','selected','installed','settled')}
    required|={f'slot-{r}-{s}' for r in (1,2) for s in ('accepted','proved','certified','applied','published','settled')}
    required|={f'typed-{s}-{n}' for s in (1,2) for n in names};selection.layout(root,required,'distinct minority member')
    group=b.original(root,size,backup);group=b.campaign(root,group,1);observations=[]
    ballot=e.f.decode(c.current(group['node-1'])[1]['promise.gsr'],'records','PROMISE')['ballot']
    rejected_body=payload(403,'minority-original');rejected=entry(group,rejected_body,ballot)
    e.need(t.plans.read(root/'minority-entry.gsr',16384)==rejected and t.plans.read(root/'minority-payload.bin',e.MIB)==rejected_body,'minority exact original ENTRY')
    group=vote(root,'minority-accepted',group,minority,rejected,rejected_body,observations)
    group,ballot=campaign(root,group,3,majority);group=settle(root,'round-3-settled',group,majority)
    selected_body=payload(404,'majority-selected');selected=entry(group,selected_body,ballot)
    e.need(t.plans.read(root/'selected-entry.gsr',16384)==selected and t.plans.read(root/'selected-payload.bin',e.MIB)==selected_body and rejected!=selected,'minority exact alternative ENTRY')
    group=vote(root,'majority-accepted',group,majority,selected,selected_body,observations)
    group,ballot=campaign(root,group,4,names);b.match(root,'minority-retained',group)
    group=vote(root,'replacement-accepted',group,names,selected,selected_body,observations);group=settle(root,'round-4-settled',group,names)
    group,_=publication(root,group,1,selected,selected_body,observations)
    group,ballot=campaign(root,group,5,names);group=settle(root,'round-5-settled',group,names)
    barrier=entry(group,b'',ballot,'BARRIER');e.need(t.plans.read(root/'barrier.gsr',16384)==barrier,'minority continuation BARRIER')
    group,_=publication(root,group,2,barrier,b'',observations)
    actual=e.parse(t.plans.read(root/'observations.json',e.MIB));expected=set(map(e.f.canonical,observations))
    e.need(type(actual) is list and len(actual)==len(expected) and set(map(e.f.canonical,actual))==expected,'minority actual owner observations')
    calls(root,names,minority,majority)
    for slot in (1,2):
        for node in names:
            _,members,packet=c.current(c.inventory(root/f'slot-{slot}-settled'/node));b.typed_image(root/f'typed-{slot}-{node}',members[packet['capsule']['application']+'.image'])
    return group


def validate(root):
    root=Path(root);names={f'size-{n}-{s}' for n in (3,4,5) for s in ('empty','backup')};selection.layout(root,names|{'receipt.json'},'distinct minority cases')
    receipt=e.parse(t.plans.read(root/'receipt.json',65536));e.exact(receipt,'schema status cases publicBootstrap publicRuntime freshProcesses')
    expected=dict(schema='gse-v53-distinct-minority-v1',status='PASS',cases=receipt['cases'],publicBootstrap=True,publicRuntime=False,freshProcesses=False)
    e.need(e.f.canonical(receipt)==e.f.canonical(expected),'minority receipt scope');e.need(type(receipt['cases']) is list and len(receipt['cases'])==6,'minority complete receipt')
    histories=set();ordinal=0
    for size in (3,4,5):
        for backup in (False,True):
            name=f"size-{size}-{'backup' if backup else 'empty'}";group=validate_case(root/name,size,backup);row=receipt['cases'][ordinal];ordinal+=1
            history=e.f.decode(group['node-1']['root.gsr'],'records','ROOT')['historyId'];e.need(uuid.UUID(history).version==4 and history not in histories,'minority distinct histories');histories.add(history)
            e.exact(row,'case status voters minority publications peakImages sequence');e.need(type(row['peakImages']) is int and 0<row['peakImages']<=7,'minority reported image bound')
            expected=dict(case=name,status='PASS',voters=size,minority=size-(size//2+1),publications=2,peakImages=row['peakImages'],sequence=42 if backup else 1)
            e.need(e.f.canonical(row)==e.f.canonical(expected),'minority exact case receipt')
    return dict(status='PASS',cases=6,voters=24,nodePublications=48,publicBootstrap=True,syntheticObservations=False,freshProcesses=False,publicRuntime=False,coveredPrefixRecovery=False,maximalCapacity=False,independentImageSemantics=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={
        'missing-case':'context selection distinct minority cases inventory',
        'extra-stage':'context selection distinct minority member inventory',
        'original-seal':'admitted original public bootstrap',
        'original-entry':'minority exact original ENTRY',
        'alternative-payload':'minority exact alternative ENTRY',
        'minority-vote':'admitted exact minority-accepted: node-1',
        'unselected-node':'admitted exact round-3-prepared: node-1',
        'frozen-tail':'admitted exact round-4-prepared: node-1',
        'selected-choice':'admitted exact round-4-selected: node-1',
        'installed-packet':'admitted exact round-4-installed: node-1',
        'early-delete':'admitted exact minority-retained: node-1',
        'replacement':'admitted exact replacement-accepted: node-1',
        'retained-minority-source':'admitted exact round-4-settled: node-1',
        'proof':'admitted exact slot-1-proved: node-1',
        'checkpoint-ack':'admitted exact slot-1-applied: node-2',
        'retired-source':'admitted exact round-5-settled: node-1',
        'typed-image':'admitted exact typed inspection image',
        'observations':'minority actual owner observations',
        'duplicate-observation':'minority actual owner observations',
        'calls':'minority complete call inventory',
        'force-order':'minority exact vote replacement force',
        'false-ack':'minority premature retirement or rejected ACK',
        'numeric-flag':'minority receipt scope',
        'capacity':'minority reported image bound',
        'link':'application evidence inventory bound',
    }
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-distinct-minority-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'size-3-empty'
            if name=='missing-case':shutil.rmtree(case)
            elif name=='extra-stage':(case/'unplanned').mkdir()
            elif name=='original-seal':(case/'initial/target-0/bootstrap-seal.gsbp').unlink()
            elif name=='original-entry':(case/'minority-entry.gsr').write_bytes((case/'selected-entry.gsr').read_bytes())
            elif name=='alternative-payload':(case/'selected-payload.bin').write_bytes((case/'minority-payload.bin').read_bytes())
            elif name=='minority-vote':(case/'minority-accepted/node-1/pending.accept').write_bytes(c.EMPTY)
            elif name=='unselected-node':(case/'round-3-prepared/node-1/grants.gsr').write_bytes(b'changed')
            elif name=='frozen-tail':
                node=case/'round-4-prepared/node-1';rows=c.journal((node/'grants.gsr').read_bytes(),e.p.decode(next((node/'sources').glob('*/source.gscp')).read_bytes())['capsule']['root'],'node-1')
                (node/'sources'/rows[-1][2]['basisId']/'source.gscp').write_bytes(b'changed')
            elif name=='selected-choice':(case/'round-4-selected/node-1/grants.gsr').write_bytes((case/'round-4-prepared/node-1/grants.gsr').read_bytes())
            elif name=='installed-packet':
                node=case/'round-4-installed/node-1';prefix,_,_=c.current(c.inventory(node));(node/prefix/'source.gscp').write_bytes(b'changed')
            elif name=='early-delete':(case/'minority-retained/node-1/pending.accept').write_bytes(c.EMPTY)
            elif name=='replacement':(case/'replacement-accepted/node-1/pending.accept').write_bytes((case/'minority-retained/node-1/pending.accept').read_bytes())
            elif name=='retained-minority-source':next((case/'round-4-settled/node-1/sources').glob('*/source.gscp')).write_bytes(b'changed')
            elif name=='proof':(case/'slot-1-proved/node-1/pending.accept').write_bytes((case/'slot-1-accepted/node-1/pending.accept').read_bytes())
            elif name=='checkpoint-ack':(case/'slot-1-applied/node-2/applied-end/ack.gsr').write_bytes(b'changed')
            elif name=='retired-source':(case/'round-5-settled/node-1/sources/obsolete').mkdir()
            elif name=='typed-image':(case/'typed-1-node-1/gse-backup-checkpoint').write_bytes(b'changed')
            elif name in ('observations','duplicate-observation'):
                path=case/'observations.json';rows=e.parse(path.read_bytes())
                if name=='observations':rows.pop()
                else:rows.append(rows[0])
                path.write_bytes(e.f.canonical(rows))
            elif name in ('calls','force-order','false-ack'):
                path=case/'calls.json';rows=e.parse(path.read_bytes())
                if name=='calls':rows.pop()
                elif name=='force-order':next(r for r in rows if r['operation']=='replacement-vote')['events'].remove('ACCEPT_CANDIDATE_FORCED')
                else:next(r for r in rows if r['operation']=='retention-refusal')['events'].append('ACCEPT_BEFORE_RETURN')
                path.write_bytes(e.f.canonical(rows))
            elif name in ('numeric-flag','capacity'):
                path=moved/'receipt.json';value=e.parse(path.read_bytes())
                if name=='numeric-flag':value['publicBootstrap']=1
                else:value['cases'][0]['peakImages']=8
                path.write_bytes(e.f.canonical(value))
            else:
                path=case/'initial/target-0/bootstrap-seal.gsbp';path.unlink();path.symlink_to((root/'size-3-empty/initial/target-0/bootstrap-seal.gsbp').resolve())
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong minority negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted minority mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-distinct-minority-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'minority portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))

