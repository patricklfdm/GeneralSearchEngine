"""Derive admitted bootstrap, voting, publication and reclamation from originals.

Only original bootstrap inputs, fresh source UUIDs and typed DATA image bytes
are observations. No synthetic ownership is introduced; no power-loss/runtime claim.
"""
import argparse
import copy
import json
import shutil
import struct
import tempfile
import uuid
from pathlib import Path
from . import bootstrap_transaction_evidence as t
from . import bootstrap_admission_evidence as a
from . import carried_publication_evidence as c
from . import context_selection_evidence as selection

e=t.e


def match(root,stage,group):
    selection.layout(root/stage,set(group),'admitted publication voters')
    for node,files in group.items():e.need(c.inventory(root/stage/node)==files,'admitted exact '+stage+': '+node)


def original(root,size,backup):
    raw=t.plans.read(root/'original-plan.gsbp',2*e.MIB);image=t.plans.read(root/'original-application.image',64*e.MIB)
    data=t.derived(raw,image,size=size,source='VERIFIED_DURABLE_BACKUP' if backup else 'EMPTY')
    admission=a.envelope(data['receipt'],data['rows'][2],data['rows'][3]);group={}
    physical={'operation':None,'operation/operation.lock':b'','operation/plan.gsbp':raw,'operation/application.image':image,
              'operation/'+t.JOURNAL:b''.join(data['rows']),'operation/'+t.RECEIPT:data['receipt']}
    for i,payload in enumerate(data['payloads']):
        files=dict(payload,**{t.PREPARED:data['preps'][i],t.SEAL:data['seals'][i],'bootstrap-admission.gsbp':admission,
                             'generations':None,'generations/a':None,'sources':None})
        group['node-'+str(i+1)]=files;prefix='target-'+str(2*i);physical[prefix]=None
        physical.update({prefix+'/'+k:v for k,v in files.items()})
    e.need(c.inventory(root/'initial')==physical,'admitted original public bootstrap')
    return group


def settled(group):
    result={}
    for node,files in group.items():
        prefix,members,packet=c.current(files);basis=e.f.decode(members['basis.gsr'],'records','BASIS');source='sources/'+basis['basisId']
        result[node]={k:v for k,v in files.items() if (not k.startswith('generations/') or k==prefix[:-1] or k.startswith(prefix))
                      and (not k.startswith('sources/') or k==source or k.startswith(source+'/'))}
        result[node]['grants.gsr']=b''.join(members[k+'.gsr'] for k in ('promise','basis','selected'))
    return result


def campaign(root,group,round):
    names=sorted(group);prepared={};rows={};old_source_ids=set()
    local=e.f.decode(group['node-1']['node.gsr'],'records','NODE')['identity']
    ballot=dict(counter=round+1,proposer='node-1',incarnation=local['storage'])
    for node,files in group.items():
        _,members,packet=c.current(files);cap=packet['capsule'];actual=c.inventory(root/f'round-{round}-prepared'/node)
        history=c.journal(actual['grants.gsr'],cap['root'],node);prior=c.journal(files['grants.gsr'],cap['root'],node)
        e.need(history[:len(prior)]==prior and [r[0] for r in history[len(prior):]]==['PROMISE','BASIS'],'admitted fresh grant journal')
        promise,basis=history[-2:];identifier=promise[2]['basisId'];e.need(str(uuid.UUID(identifier))==identifier and identifier not in old_source_ids,'admitted distinct source UUID')
        e.need(all(r[2].get('basisId')!=identifier for r in prior),'admitted reused original source UUID');old_source_ids.add(identifier)
        expected=dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),ballot=ballot,basisId=identifier)
        e.need(promise[2]==expected,'admitted fresh promise identity')
        expected_basis=dict(expected,voter=node,cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),inventory=e.digest(packet['indexBytes']),accepted=None)
        e.need(basis[2]==expected_basis,'admitted actual source basis')
        source='sources/'+identifier;changed=dict(files,**{'grants.gsr':files['grants.gsr']+promise[1]+basis[1],source:None,source+'/source.gscp':members['source.gscp']})
        for h in packet['images']:changed[source+'/'+h+'.image']=members[h+'.image']
        if node=='node-1':changed['allocator.gsr']=e.f.encode('records','ALLOCATOR',dict(root=cap['root'],node=node,counter=round+1))
        prepared[node]=changed;rows[node]=(promise,basis)
    match(root,f'round-{round}-prepared',prepared)
    base=c.current(group['node-1'])[2];cap=base['capsule']
    raw=e.f.encode('records','SELECTED',dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),ballot=ballot,cut=cap['cut'],nextEntry=None,
        sources=[dict(voter=n,basisId=rows[n][1][2]['basisId'],basisDigest=e.digest(rows[n][1][1])) for n in names]))
    selected={n:dict(files,**{'grants.gsr':files['grants.gsr']+raw}) for n,files in prepared.items()};match(root,f'round-{round}-selected',selected)
    installed={}
    for node,files in selected.items():
        prefix,old,packet=c.current(group[node]);e.need(old['source.gscp']==c.current(group['node-1'])[1]['source.gscp'],'admitted same captured parent')
        members={'promise.gsr':rows[node][0][1],'basis.gsr':rows[node][1][1],'selected.gsr':raw,
                 'selected-sources.gsr':b''.join(rows[n][1][1] for n in names),'source.gscp':old['source.gscp']}
        members.update({h+'.image':old[h+'.image'] for h in packet['images']})
        selector,generation=c.generation(members,cap,node,'b' if prefix=='generations/a/' else 'a',None)
        installed[node]=dict(files,**generation,**{'selector.gsr':selector})
    match(root,f'round-{round}-installed',installed);result=settled(installed);match(root,f'round-{round}-settled',result)
    return result


def publication(root,group,slot,first,observations):
    names=sorted(group);_,members,packet=c.current(group['node-1']);cap=packet['capsule'];r=cap['root'];selected=e.f.decode(members['selected.gsr'],'records','SELECTED')
    text=b'303:admitted-original';payload=b'\x01'+struct.pack('>HIII',1,1,4,303)+struct.pack('>I',len(text))+text if slot==2 else b''
    entry=e.f.encode('records','ENTRY',dict(root=r,authority=selected['view'],index=slot,previous=cap['cut']['entry'],origin=selected['ballot'],kind='DATA' if slot==2 else 'BARRIER',payload=e.digest(payload)))
    e.need(t.plans.read(root/f'entry-{slot}.gsr',8192)==entry and t.plans.read(root/f'payload-{slot}.bin',e.MIB)==payload,'admitted exact requested operation')
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
    if slot==2:after.update(application=e.digest(image),applicationSequence=after['applicationSequence']+1,lastDataIndex=slot)
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


def typed_image(path,image):
    e.need(24<=len(image)<=64*e.MIB and struct.unpack('>4sHHI',image[:12])==(b'GSAI',1,3,len(image)-12),'admitted typed image framing')
    offset=12;members={}
    for name in ('gse-backup-checkpoint','gse-backup-manifest','gse-backup-metadata'):
        e.need(offset+4<=len(image),'admitted typed image length');size=int.from_bytes(image[offset:offset+4],'big');offset+=4
        e.need(0<size<=len(image)-offset,'admitted typed image member');members[name]=image[offset:offset+size];offset+=size
    e.need(offset==len(image) and c.inventory(path)==members,'admitted exact typed inspection image')


def calls(root,names):
    expected=[]
    def many(label):expected.extend((n,label) for n in names)
    def campaign_order(round):
        expected.append(('node-1',f'allocate-{round}'))
        for label in ('prepare','select','install'):many(f'{label}-{round}')
        many(f'round-{round}-settled-copy');many(f'round-{round}-settled-maintain')
    def publication_order(slot):
        expected.append(('node-1',f'entry-{slot}'))
        for label in ('accept','proof','certificate','apply','publish'):many(f'{label}-{slot}')
        many(f'slot-{slot}-settled-copy');many(f'slot-{slot}-settled-maintain');many(f'inspect-{slot}')
    campaign_order(1);publication_order(1);publication_order(2);campaign_order(2);publication_order(3)
    actual=e.parse(t.plans.read(root/'calls.json',8*e.MIB))
    e.need(type(actual) is list and len(actual)==len(expected),'admitted complete owner calls')
    for row,(node,operation) in zip(actual,expected):
        e.exact(row,'node operation events');ev=row['events']
        e.need(row['node']==node and row['operation']==operation and type(ev) is list and 0<len(ev)<=4096 and all(type(v) is str for v in ev),'admitted exact owner call order')
        phase=operation.split('-')[0]
        required={'allocate':['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN'],
                  'prepare':['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'],
                  'select':['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],
                  'install':['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN'],
                  'accept':['ACCEPT_ACTIVE_FORCED','ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN'],
                  'proof':['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'],
                  'certificate':['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'],
                  'apply':['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN'],
                  'publish':['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN']}.get(phase)
        if required:e.need([v for v in ev if v in set(required)]==required,'admitted force before response: '+phase)


def validate_case(root,size,backup):
    names=['node-'+str(i+1) for i in range(size)]
    required={'original-plan.gsbp','original-application.image','initial','calls.json','observations.json'}
    required|={f'round-{r}-{s}' for r in (1,2) for s in ('prepared','selected','installed','settled')}
    required|={f'slot-{r}-{s}' for r in (1,2,3) for s in ('accepted','proved','certified','applied','published','settled')}
    required|={f'entry-{s}.gsr' for s in (1,2,3)}|{f'payload-{s}.bin' for s in (1,2,3)}|{f'typed-{s}-{n}' for s in (1,2,3) for n in names}
    selection.layout(root,required,'admitted publication member');group=original(root,size,backup);observations=[]
    group=campaign(root,group,1);group,first=publication(root,group,1,None,observations);group,_=publication(root,group,2,first,observations)
    group=campaign(root,group,2);group,_=publication(root,group,3,None,observations)
    actual=e.parse(t.plans.read(root/'observations.json',e.MIB))
    e.need(type(actual) is list and len(actual)==len(observations) and sorted(map(e.f.canonical,actual))==sorted(map(e.f.canonical,observations)),'admitted actual owner observations')
    calls(root,names)
    for slot in (1,2,3):
        for node in names:
            _,members,packet=c.current(c.inventory(root/f'slot-{slot}-settled'/node))
            typed_image(root/f'typed-{slot}-{node}',members[packet['capsule']['application']+'.image'])
    return group


def validate(root):
    root=Path(root);names={f'size-{n}-{s}' for n in (3,4,5) for s in ('empty','backup')};selection.layout(root,names|{'receipt.json'},'admitted publication cases')
    receipt=e.parse(t.plans.read(root/'receipt.json',65536));e.exact(receipt,'schema status cases publicBootstrap publicRuntime freshProcesses syntheticObservations')
    rows=[];histories=set();roots=set()
    for size in (3,4,5):
        for backup in (False,True):
            name=f"size-{size}-{'backup' if backup else 'empty'}";group=validate_case(root/name,size,backup);rows.append((name,size,42 if backup else 1))
            raw_root=group['node-1']['root.gsr'];record=e.f.decode(raw_root,'records','ROOT');history=record['historyId']
            e.need(uuid.UUID(history).version==4 and history not in histories and raw_root[16:48].hex() not in roots,'admitted distinct new histories')
            histories.add(history);roots.add(raw_root[16:48].hex())
    e.need(e.f.canonical(receipt)==e.f.canonical(dict(schema='gse-v53-bootstrap-publication-v1',status='PASS',cases=receipt['cases'],publicBootstrap=True,publicRuntime=False,freshProcesses=False,syntheticObservations=False)),'admitted receipt scope')
    e.need(type(receipt['cases']) is list and len(receipt['cases'])==6,'admitted receipt complete cases')
    for row,(name,size,sequence) in zip(receipt['cases'],rows):
        e.exact(row,'case status voters publications sequence peakImages peakMetadata peakStaging')
        e.need(all(type(row[k]) is int and 0<row[k]<=limit for k,limit in [('peakImages',7),('peakMetadata',384*e.MIB),('peakStaging',512*e.MIB)]),'admitted reported reservation bounds')
        e.need(e.f.canonical({k:row[k] for k in ('case','status','voters','publications','sequence')})==e.f.canonical(dict(case=name,status='PASS',voters=size,publications=3,sequence=sequence)),'admitted receipt case identity')
    return dict(status='PASS',cases=6,voters=24,nodePublications=72,publicBootstrap=True,syntheticObservations=False,publicRuntime=False,freshProcesses=False,independentImageSemantics=False,maximalCapacity=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={
        'missing-case':'context selection admitted publication cases inventory',
        'extra-stage':'context selection admitted publication member inventory',
        'original-plan':'bootstrap original plan checksum',
        'original-image':'bootstrap original image binding',
        'initial-admission':'admitted original public bootstrap',
        'prepared-counter':'admitted exact round-1-prepared: node-1',
        'prepared-source':'admitted exact round-1-prepared: node-1',
        'selected-journal':'admitted exact round-1-selected: node-1',
        'installed-old-generation':'admitted exact round-1-installed: node-1',
        'retained-source':'admitted exact round-2-settled: node-1',
        'accept':'admitted exact slot-2-accepted: node-1',
        'proof':'admitted exact slot-2-proved: node-1',
        'certificate':'admitted exact slot-2-certified: node-1',
        'applied-ack':'admitted exact slot-2-applied: node-2',
        'peer-image':'admitted exact slot-2-applied: node-2',
        'publication':'admitted exact slot-2-published: node-1',
        'final-vote':'admitted exact slot-3-settled: node-1',
        'typed-image':'admitted exact typed inspection image',
        'observations':'admitted actual owner observations',
        'calls':'admitted complete owner calls',
        'force-order':'admitted force before response: proof',
        'scope':'admitted receipt scope',
        'numeric-flag':'admitted receipt scope',
        'peak':'admitted reported reservation bounds',
        'link':'application evidence inventory bound',
    }
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-admitted-publication-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'size-3-empty'
            if name=='missing-case':shutil.rmtree(case)
            elif name=='extra-stage':(case/'unplanned').mkdir()
            elif name=='original-plan':
                path=case/'original-plan.gsbp';raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name=='original-image':(case/'original-application.image').write_bytes(b'changed')
            elif name=='initial-admission':(case/'initial/target-0/bootstrap-admission.gsbp').unlink()
            elif name=='prepared-counter':(case/'round-1-prepared/node-1/allocator.gsr').write_bytes((case/'initial/target-0/allocator.gsr').read_bytes())
            elif name=='prepared-source':next((case/'round-1-prepared/node-1/sources').glob('*/source.gscp')).write_bytes(b'changed')
            elif name=='selected-journal':(case/'round-1-selected/node-1/grants.gsr').write_bytes(b'changed')
            elif name=='installed-old-generation':shutil.rmtree(case/'round-1-installed/node-1/generations/a')
            elif name=='retained-source':(case/'round-2-settled/node-1/sources/obsolete').mkdir()
            elif name in ('accept','proof','certificate'):
                stage={'accept':'accepted','proof':'proved','certificate':'certified'}[name];(case/f'slot-2-{stage}/node-1/pending.accept').write_bytes(c.EMPTY)
            elif name in ('applied-ack','peer-image'):(case/'slot-2-applied/node-2/applied-end'/('ack.gsr' if name=='applied-ack' else 'application.image')).write_bytes(b'changed')
            elif name=='publication':
                node=case/'slot-2-published/node-1';prefix,_,_=c.current(c.inventory(node));(node/prefix/c.COVERAGE).write_bytes(b'{}')
            elif name=='final-vote':(case/'slot-3-settled/node-1/pending.accept').write_bytes((case/'slot-3-certified/node-1/pending.accept').read_bytes())
            elif name=='typed-image':(case/'typed-2-node-1/gse-backup-checkpoint').write_bytes(b'changed')
            elif name=='observations':
                path=case/'observations.json';rows=e.parse(path.read_bytes());rows.pop();path.write_bytes(e.f.canonical(rows))
            elif name in ('calls','force-order'):
                path=case/'calls.json';rows=e.parse(path.read_bytes())
                if name=='calls':rows.pop()
                else:next(row for row in rows if row['operation']=='proof-1')['events'].remove('PROOF_CANDIDATE_FORCED')
                path.write_bytes(e.f.canonical(rows))
            elif name in ('scope','peak','numeric-flag'):
                path=moved/'receipt.json';value=e.parse(path.read_bytes())
                if name=='scope':value['syntheticObservations']=True
                elif name=='numeric-flag':value['publicBootstrap']=1
                else:value['cases'][0]['peakImages']=8
                path.write_bytes(e.f.canonical(value))
            else:
                path=case/'initial/target-0/bootstrap-seal.gsbp';path.unlink();path.symlink_to((root/'size-3-empty/initial/target-0/bootstrap-seal.gsbp').resolve())
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong admitted publication negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted admitted publication mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-admitted-publication-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'admitted publication portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
