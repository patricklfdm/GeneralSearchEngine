"""Original-first replay of native TCP activation after actual publication.

Rebuild public bootstrap and two committed operations before deriving fresh
grants, selection, transfers and installed files. No historical receipt or copied
vote is treated as a fresh observation. These bounded same-view invocations do
not qualify autonomous elections, cross-view transitions or public READY.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import bootstrap_publication_evidence as b
from . import promised_source_evidence as p
from . import offline_fixture_image as image
from .owned_cross_view_evidence import same

e=b.e;c=b.c
PROFILES=tuple((size,backup) for size in (3,4,5) for backup in (False,True))


def name(size,backup):return f'size-{size}-'+('backup' if backup else 'empty')


def read(path,limit=8*e.MIB):return e.parse(b.t.plans.read(Path(path),limit))


def original_calls(root,names):
    expected=[('node-1','allocate-1')]
    for label in ('prepare-1','select-1','install-1','round-1-settled-copy','round-1-settled-maintain'):
        expected.extend((node,label) for node in names)
    for slot in (1,2):
        expected.append(('node-1',f'entry-{slot}'))
        for label in ('accept','proof','certificate','apply','publish'):
            expected.extend((node,f'{label}-{slot}') for node in names)
        for label in (f'slot-{slot}-settled-copy',f'slot-{slot}-settled-maintain',f'inspect-{slot}'):
            expected.extend((node,label) for node in names)
    actual=read(root/'calls.json')
    e.need(type(actual) is list and len(actual)==len(expected),'native activation original calls')
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
        e.exact(row,'node operation events');events=row['events'];phase=operation.split('-')[0]
        e.need((row['node'],row['operation'])==(node,operation) and type(events) is list
               and 0<len(events)<=4096 and all(type(v) is str for v in events),'native activation original call order')
        if phase in required:
            e.need([v for v in events if v in set(required[phase])]==required[phase],'native activation original force: '+phase)


def original(root,size,backup):
    names=[f'node-{n}' for n in range(1,size+1)]
    expected={'original-plan.gsbp','original-application.image','initial','calls.json','observations.json',
              'before-network','after-network','after-reopen'}
    expected|={f'round-1-{stage}' for stage in ('prepared','selected','installed','settled')}
    expected|={f'slot-{slot}-{stage}' for slot in (1,2) for stage in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'typed-{slot}-{node}' for slot in (1,2) for node in names}
    expected|={f'{kind}-{slot}.{ext}' for slot in (1,2) for kind,ext in (('entry','gsr'),('payload','bin'))}
    b.selection.layout(root,expected,'native activation original inventory')
    group=b.original(root,size,backup);history=e.f.decode(group['node-1']['root.gsr'],'records','ROOT')['historyId']
    base=41 if backup else 0;documents=[(7,'original'),(2,'你好')] if backup else []
    image.application(b.t.plans.read(root/'original-application.image',64*e.MIB),history,base,documents)
    group=b.campaign(root,group,1);first=None;observations=[]
    for slot in (1,2):
        group,first=b.publication(root,group,slot,first,observations)
        if slot==2:documents.append((303,'admitted-original'))
        for node,files in group.items():
            _,members,packet=c.current(files);cap=packet['capsule']
            typed=members[cap['application']+'.image'];b.typed_image(root/f'typed-{slot}-{node}',typed)
            image.application(typed,history,base+(slot==2),documents)
            catalog=e.f.decode(packet['objects'][cap['catalog']],'records','CATALOG')
            e.need(catalog['applicationSequence']==base+(slot==2),'native activation original sequence')
    actual=read(root/'observations.json')
    e.need(type(actual) is list and sorted(map(e.f.canonical,actual))==sorted(map(e.f.canonical,observations)),
           'native activation original observations')
    original_calls(root,names);b.match(root,'before-network',group)
    return group,history


def installation(root,before):
    selected=b.t.plans.read(root/'selected.gsr',65536);selection=e.f.decode(selected,'records','SELECTED')
    names=[v['voter'] for v in selection['sources']]
    e.need(names==sorted(set(names)) and len(names)==len(before)//2+1 and 'node-1' in names
           and set(names)<=set(before),'native activation fixed quorum')
    b.selection.layout(root/'history/after-network',set(before),'native activation voters')
    actual={n:c.inventory(root/'history/after-network'/n) for n in before}
    _,initial,packet=c.current(before['node-1']);cap=packet['capsule'];r=cap['root']
    identities={n:e.f.decode(v['node.gsr'],'records','NODE')['identity'] for n,v in before.items()}
    ballot=dict(counter=3,proposer='node-1',incarnation=identities['node-1']['storage'])
    bases={};promises={};prepared={};seen=set()
    old_ids={row[2]['basisId'] for node,files in before.items() for row in c.journal(files['grants.gsr'],r,node) if row[0]=='BASIS'}
    for node,files in before.items():
        if node not in names:
            e.need(actual[node]==files,'native activation unselected voter changed');continue
        prior=c.journal(files['grants.gsr'],r,node);rows=c.journal(actual[node]['grants.gsr'],r,node)
        e.need(rows[:len(prior)]==prior and [v[0] for v in rows[len(prior):]]==['PROMISE','BASIS','SELECTED'],
               'native activation original grant sequence')
        promise,basis=rows[-3:-1];identifier=promise[2]['basisId']
        e.need(str(uuid.UUID(identifier))==identifier and identifier not in seen|old_ids,'native activation fresh grant UUID');seen.add(identifier)
        expected=dict(root=r,view=e.authority(r,cap['cut']['view']),ballot=ballot,basisId=identifier)
        same(promise[2],expected,'native activation original promise')
        same(basis[2],dict(expected,voter=node,cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),
                          inventory=e.digest(packet['indexBytes']),accepted=None),'native activation original basis')
        promises[node]=promise[1];bases[node]=basis[1];source='sources/'+identifier
        changed=dict(files,**{'grants.gsr':files['grants.gsr']+promise[1]+basis[1],source:None,source+'/source.gscp':initial['source.gscp']})
        changed.update({source+'/'+h+'.image':initial[h+'.image'] for h in packet['images']})
        if node=='node-1':changed['allocator.gsr']=e.f.encode('records','ALLOCATOR',dict(root=r,node=node,counter=3))
        prepared[node]=changed
    expected=dict(root=r,view=e.authority(r,cap['cut']['view']),ballot=ballot,cut=cap['cut'],nextEntry=None,
                  sources=[dict(voter=n,basisId=e.f.decode(bases[n],'records','BASIS')['basisId'],basisDigest=e.digest(bases[n])) for n in names])
    e.need(selected==e.f.encode('records','SELECTED',expected),'native activation fixed selection')
    installed=dict(before)
    for node in names:
        files=prepared[node];files['grants.gsr']+=selected
        members={'source.gscp':initial['source.gscp'],'promise.gsr':promises[node],'basis.gsr':bases[node],
                 'selected.gsr':selected,'selected-sources.gsr':b''.join(bases[n] for n in names)}
        members.update({h+'.image':initial[h+'.image'] for h in packet['images']})
        old_prefix=c.current(before[node])[0]
        selector,generation=c.generation(members,cap,node,'b' if old_prefix=='generations/a/' else 'a',None)
        installed[node]=dict(files,**generation,**{'selector.gsr':selector})
    b.match(root/'history','after-network',installed);b.match(root/'history','after-reopen',installed)
    return selection,selected,identities,promises,bases,initial,packet


def network(root,selection,selected,identities,promises,bases,initial,packet):
    names=[v['voter'] for v in selection['sources']];rows=read(root/'wire.json');groups={}
    e.need(type(rows) is list and 0<len(rows)<=4096,'native activation wire inventory')
    for row in rows:
        e.exact(row,'request response');_,request=p.t.wire(row['request']);groups.setdefault(request['trace'],[]).append(row)
    controls=[trace for trace,items in groups.items() if any(p.t.wire(v['request'])[0] in ('PREPARE','SELECTED') for v in items)]
    e.need(len(controls)==1,'native activation control trace');trace=controls[0]
    control=sorted(groups.pop(trace),key=lambda row:p.t.wire(row['request'])[1]['sequence'])
    e.need(len(control)==2*(len(names)-1),'native activation control inventory')
    e.need(str(uuid.UUID(trace))==trace and uuid.UUID(trace).int!=0,'native activation control UUID')
    for index,row in enumerate(control):
        install=index>=len(names)-1;node=names[1+index%(len(names)-1)]
        kind,answer=('SELECTED','INSTALL_ACK') if install else ('PREPARE','PROMISE')
        request=e.f.decode(base64.b64decode(row['request'],validate=True),'wire',kind)
        response=e.f.decode(base64.b64decode(row['response'],validate=True),'wire',answer)
        fields=dict(root=selection['root'],view=selection['view'],ballot=selection['ballot'],trace=trace,sequence=index+1)
        payload=dict(selection=e.digest(selected)) if install else dict(promise=e.digest(promises['node-1']))
        reply=dict(selection=e.digest(selected),cut=selection['cut']) if install else dict(basis=e.digest(bases[node]))
        same(request,dict(fields,sender=identities['node-1'],recipient=identities[node],payload=payload),'native activation control request')
        same(response,dict(fields,sender=identities[node],recipient=identities['node-1'],payload=reply),'native activation control response')
    expected={}
    for receiver in names[1:]:
        for raw in (promises['node-1'],selected):expected[(receiver,'node-1',e.digest(raw))]=[(e.digest(raw),raw,'RECORD')]
        for reader,source in [('node-1',receiver)]+[(receiver,source) for source in names if source!=receiver]:
            values=[(e.digest(raw),raw,'RECORD') for raw in (bases[source],promises[source])]
            values.append((e.digest(packet['capsuleBytes']),initial['source.gscp'],'CAPSULE'))
            expected[(reader,source,values[0][0])]=values
    count=0
    for items in groups.values():
        kind,request=p.t.wire(items[0]['request']);e.need(kind=='CHUNK','native activation transfer first kind')
        key=(request['sender']['node'],request['recipient']['node'],request['payload']['digest'])
        e.need(key in expected,'native activation unexpected transfer')
        count+=p.transcript(items,expected.pop(key),selection['root'],selection['view'],selection['ballot'],
                            identities[key[0]],identities[key[1]],'native activation source',chunk_bytes=4*e.MIB)
    e.need(not expected,'native activation missing transfer')
    return count


def forces(root,names,selected):
    rows=read(root/'events.json');e.need(type(rows) is list and len(rows)==len(names),'native activation event inventory')
    for node,row in zip(names,rows):
        e.exact(row,'node events');events=row['events']
        e.need(row['node']==node and type(events) is list and len(events)<=4096
               and all(type(v) is str for v in events),'native activation event identity')
        if node not in selected:
            e.need(not any(v in events for v in ('GRANT_BEFORE_RETURN','SELECTED_FORCED','INSTALL_BEFORE_RETURN')),
                   'native activation unselected force');continue
        required=['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN','SELECTED_FORCED','SELECTED_BEFORE_RETURN',
                  'INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN']
        if node=='node-1':required=['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN']+required
        e.need([v for v in events if v in required]==required,'native activation force order')
    reopen=['CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED',
            'CURRENT_DIRECTORY_FORCED','ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED']
    same(read(root/'native-final.json'),[dict(node=n,operation='native-final',events=reopen) for n in names],
         'native activation reopen events')


def case(root,size,backup):
    root=Path(root);b.selection.layout(root,{'history','receipt.json','selected.gsr','wire.json','events.json','native-final.json'},'native activation case')
    before,history=original(root/'history',size,backup)
    values=installation(root,before);selection=values[0]
    count=network(root,*values);selected=[v['voter'] for v in selection['sources']];forces(root,sorted(before),selected)
    same(read(root/'receipt.json'),dict(schema='gse-v53-native-activation-v1',status='PASS',size=size,backup=backup,campaigns=1,
         historicalObservationsSupplied=False,network=True,publicRuntime=False),'native activation receipt')
    return dict(case=name(size,backup),history=history,selected=len(selected),installed=len(selected),sourceExchanges=count)


def validate(directory):
    root=Path(directory);b.selection.layout(root,{name(*p) for p in PROFILES},'native activation profiles')
    cases=[case(root/name(*profile),*profile) for profile in PROFILES]
    e.need(len({v['history'] for v in cases})==len(PROFILES),'native activation distinct histories')
    return dict(status='PASS',profiles=len(cases),nodePublications=48,installed=sum(v['installed'] for v in cases),
                sourceExchanges=sum(v['sourceExchanges'] for v in cases),independentImageSemantics=True,
                historicalObservationsSupplied=False,publicRuntime=False)


VARIANTS={
    'original-proof':'admitted exact slot-2-proved: node-1',
    'original-observation':'native activation original observations',
    'original-force':'native activation original force: proof',
    'selection':'native activation fixed selection',
    'unselected':'native activation unselected voter changed',
    'installed':'admitted exact after-network: node-2',
    'reopened':'admitted exact after-reopen: node-1',
    'force':'native activation force order',
    'reopen-events':'native activation reopen events',
    'missing-ack':'native activation control inventory',
    'reply':'native activation control response',
    'missing-source':'native activation missing transfer',
    'source-data':'native activation source exact data',
    'scope':'native activation receipt',
}


def mutate(root,variant):
    paths={'original-proof':'history/slot-2-proved/node-1/pending.accept',
           'unselected':'history/after-network/node-3/allocator.gsr','installed':'history/after-network/node-2/selector.gsr',
           'reopened':'history/after-reopen/node-1/selector.gsr'}
    if variant in paths:(root/paths[variant]).write_bytes(b'changed');return
    paths={'original-observation':'history/observations.json','original-force':'history/calls.json',
           'selection':'selected.gsr','force':'events.json','reopen-events':'native-final.json','scope':'receipt.json'}
    path=root/paths.get(variant,'wire.json')
    if variant=='selection':
        value=e.f.decode(path.read_bytes(),'records','SELECTED');value['cut']['index']+=1
        path.write_bytes(e.f.encode('records','SELECTED',value));return
    value=read(path)
    if variant=='original-observation':value.pop()
    elif variant=='original-force':next(v for v in value if v['operation']=='proof-1')['events'].remove('PROOF_CANDIDATE_FORCED')
    elif variant=='force':value[1]['events'].remove('INSTALL_PARENT_FORCED')
    elif variant=='reopen-events':value[0]['events'].remove('CURRENT_DIRECTORY_FORCED')
    elif variant=='scope':value['historicalObservationsSupplied']=True
    elif variant=='missing-ack':value=[v for v in value if p.t.wire(v['response'])[0]!='INSTALL_ACK']
    elif variant=='missing-source':
        trace=next(p.t.wire(v['request'])[1]['trace'] for v in value if p.t.wire(v['response'])[0]=='SOURCE_OFFER')
        value=[v for v in value if p.t.wire(v['request'])[1]['trace']!=trace]
    else:
        row=next(v for v in value if p.t.wire(v['response'])[0]==('PROMISE' if variant=='reply' else 'CHUNK'))
        kind,frame=p.t.wire(row['response'])
        if variant=='reply':frame['payload']['basis']='a'*64
        else:frame['payload']['bytes']=base64.b64encode(b'changed').decode();frame['payload']['digest']=e.digest(b'changed')
        row['response']=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
    path.write_bytes(e.f.canonical(value))


def qualify(directory):
    original=validate(directory);results=[]
    for variant,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-native-activation-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(Path(directory)/name(3,False),target);mutate(target,variant)
            try:case(target,3,False)
            except ValueError as error:e.need(str(error)==reason,'native activation unrelated negative: '+variant+': '+str(error))
            else:raise ValueError('native activation accepted negative: '+variant)
            results.append(dict(case=variant,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
