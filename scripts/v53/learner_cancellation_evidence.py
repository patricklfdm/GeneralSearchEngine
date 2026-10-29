"""Original native READY/CANCEL and same-original learner cold recovery.

Reduce voter authority before examining learner copies. Recorded paths/inodes
are evidence data, never paths to open. Successful explicit recovery neither
qualifies process death nor grants a vote, INTENT or autonomous continuation.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import learner_typed_evidence as t
from . import learner_slot_snapshot as snap
from . import learner_cycle_bytes as state
from . import learner_cycle_forces as forces
from .ancestry_pruning_evidence import frames

b,c,d,e,f,need=t.b,t.c,t.d,t.e,t.f,t.need
ROOTS=frozenset(('operation','replica','initial-typed','cancellation'))
STAGES=('learner-prepared','learner-cancelled','learner-closed','learner-reopened')


def inventory(root,*,diagnostic=False):
    need(root.is_dir() and not root.is_symlink(),'learner cancellation evidence directory')
    total=count=0;pending=[root]
    while pending:
        for path in pending.pop().iterdir():
            count+=1
            need(count<=65536 and not path.is_symlink() and (path.is_file() or path.is_dir()),
                 'learner cancellation regular bounded inventory')
            if path.is_dir():pending.append(path)
            else:
                size=path.stat().st_size;total+=size
                need(path.stat().st_nlink==1 and size<=64*e.MIB and total<=512*e.MIB,'learner cancellation file capacity')
    names={'initial','original-plan.gsbp','original-application.image','before-network','installed','selected.gsr',
           'after-close','calls.json','events.json','wire.json','failures.json','before-learner-source',
           'after-learner-source','after-cancel','learner-reserve-payload.bin','learner-ready-payload.bin',
           'learner-plan.gslp','learner-receipt.gsr','learner-source-copy','learner-progress-copy','cancelled-original',
           'learner-source-wire.json','learner-progress-wire.json','learner-initial-events.json',
           'learner-cancel-events.json','learner-resume-events.json','learner-cancellation-result.json'}|set(STAGES)
    names|={f'{stage}-{i}' for stage in ('applied','published') for i in range(1,6)}
    if diagnostic:names-={'learner-progress-copy',*STAGES[1:]}
    b.selection.layout(root,names,'learner cancellation')


def native_failures(root):
    # The unselected original third voter refuses the campaign's future intent.
    # Match the existing native-dispatch fixture contract, at most three tries
    # per each of five slots. Do not silently ignore arbitrary server failures.
    rows=d.read(root/'failures.json')
    need(type(rows) is list and len(rows)<=15 and all(type(v) is dict and set(v)=={'node','kind','request','failure'}
         and v['node']=='node-3' and v['kind']=='FUTURE_RETENTION_INTENT'
         and v['failure']=='java.lang.IllegalArgumentException: higher ballot observed; fresh campaign required'
         and type(v['request']) is str and len(v['request'])==64 and all(c in '0123456789abcdef' for c in v['request']) for v in rows),
         'learner cancellation unexpected native failure')
    return len(rows)


def ancestry(original,terminal):
    """Locate the exact prepared endpoint in already independently reduced
    native original bytes. A same/higher index cannot substitute its full state.
    This function alone is not a certificate or ancestry verifier."""
    before=state.terminal(original);after=state.terminal(terminal)
    wanted={k:before[k] for k in ('cut','catalog','application')}
    available=[{k:after[k] for k in wanted}]
    packet=state.source_packet.decode(terminal['source.gscp'])
    statements=[f.decode(packet['objects'][item['statement']],'records','CHECKPOINT') for item in packet['capsule']['items']]
    if terminal.get('ancestry.gsr'):
        statements += [f.decode(raw,'records','CHECKPOINT') for raw in frames(terminal['ancestry.gsr'])
                       if int.from_bytes(raw[8:10],'big')==f.catalog()['records']['CHECKPOINT']['id']]
    for row in statements:
        for point,suffix in [('start','Before'),('end','After')]:
            available.append(dict(cut=row[point],catalog=row['catalog'+suffix],application=row['application'+suffix]))
    return wanted in available,sorted({v['cut']['index'] for v in available})


def diagnose(root):
    """Preserve a failed original as a verified diagnosis, never a PASS receipt.
    This profile is specific to refusal after complete transfer and before any
    cancellation write. It cannot stand in for validate() or qualify()."""
    root=Path(root);inventory(root,diagnostic=True)
    prepared,cancelled,request,learner,_=t.physical_history(root);b.match(root,'after-cancel',cancelled)
    rejected=native_failures(root)
    original=c.inventory(root/'learner-source-copy');terminal=c.inventory(root/'cancelled-original')
    first=d.read(root/'learner-source-wire.json');second=d.read(root/'learner-progress-wire.json');server=d.read(root/'wire.json')
    t.source.network_rows(first,server,prepared,request,learner,original,following=second)
    t.source.network_rows(second,server,cancelled,request,learner,terminal,preceding=first,progress=True)
    present,indices=ancestry(original,terminal)
    need(not present,'learner cancellation diagnostic requires missing original ancestor')
    need(d.read(root/'learner-cancel-events.json')==[] and d.read(root/'learner-resume-events.json')==[],
         'learner cancellation diagnostic unexpected writes')
    need(d.read(root/'learner-cancellation-result.json')==dict(status='FAIL',scope='native-learner-cancellation',voter=False,
         liveCore=False,publicReady=False,phase3Complete=False,independentReplayQualified=False,testBudgetSeconds=600),
         'learner cancellation diagnostic original failure')
    return dict(status='PARTIAL',scope='failed-native-cancellation-diagnosis',nativeSlots=5,exchanges=len(first)+len(second),
                preparedIndex=state.terminal(original)['cut']['index'],terminalIndex=state.terminal(terminal)['cut']['index'],
                availableAnchorIndices=indices,missingPreparedAncestor=True,unselectedRefusals=rejected,
                physicalQualification=True,cancellationQualified=False,processDeathQualified=False,phase3Complete=False)


def snapshots(root,prepared,original,terminal,request,learner,receipt):
    observed={name:snap.read(root/name,roots=ROOTS,required=ROOTS-{'cancellation'}) for name in STAGES}
    first=observed[STAGES[0]];raw=(root/'learner-plan.gslp').read_bytes();summary=e.digest(raw)
    peer=next(v for v in request['target'] if v['node']=='node-1')
    root_bytes=prepared['node-1']['root.gsr'];plan=t.s.p.plan(raw,root_bytes,original,request,learner,peer)
    paths={k:snap.original_path(v['path']) for k,v in first.identities.items()}
    need({t.binding(v) for v in plan['paths']}=={paths['operation'],paths['replica']},'learner cancellation admission paths')
    parent=paths['operation'].parent
    need(paths['initial-typed']==parent/('.gse-v53-learner-'+summary)
         and paths['cancellation']==parent/('.gse-v53-learner-cancel-'+summary),'learner cancellation deterministic roots')
    retained=first.files['operation'].get(t.s.RETAIN);decision=t.s.retention(retained,raw,plan)
    replica_ids=first.identities['replica']['members']
    need(decision['directoryKey']==replica_ids['learner']['key'] and decision['files']==[
        dict(v,key=replica_ids['learner/'+v['path']]['key']) for v in plan['files']],
        'learner cancellation retained source identities')
    expected={'operation':{'.':None,'operation.lock':b'','learner.gslp':raw,t.s.RETAIN:retained},
              'replica':{'.':None,'replica.lock':b'','root.gsr':root_bytes,
                         'node.gsr':f.encode('records','NODE',dict(root=request['root'],identity=learner)),
                         t.s.ADMISSION:retained,**state.source_tree(original,'learner')},'cancellation':{}}
    typed={k:v for k,v in first.files['initial-typed'].items() if k!='.'}
    t.sidecar(root,typed,plan,original,request,receipt,raw,selected=True)
    metadata=e.parse(typed['preparation.json'])
    need(t.binding(metadata['path'])==paths['initial-typed'] and metadata['directoryKey']==
         first.identities['initial-typed']['members']['.']['key'],'learner cancellation typed original identity')
    core=t.binding(metadata['materialization'])
    need(all(core!=p and core not in p.parents and p not in core.parents for p in paths.values()),
         'learner cancellation disjoint core')
    expected['initial-typed']={'.':None,**typed}
    need(first.files==expected,'learner cancellation exact prepared bytes')
    cancelled=observed[STAGES[1]];data=cancelled.files['cancellation'];value=state.record(data.get('cancellation.json'),64*1024)
    path=t.binding(value.get('path'));staging=t.binding(value.get('staging'))
    need(path==paths['cancellation'] and all(staging!=p and staging not in p.parents and p not in staging.parents for p in [*paths.values(),core]),
         'learner cancellation original staging path')
    # All same-parent bindings refer to the original same filesystem directory.
    bindings=[*plan['paths'],metadata['path'],metadata['materialization'],value['path'],value['staging'],decision['staging']]
    for i,left in enumerate(bindings):
        for right in bindings[i+1:]:
            if left['parentRealPath']==right['parentRealPath']:
                need({k:v for k,v in left.items() if k!='path'}=={k:v for k,v in right.items() if k!='path'},
                     'learner cancellation original parent identity')
    ids=cancelled.identities['cancellation']['members']
    expected_plan=dict(schema='gse-v53-learner-cancellation/1.3',plan=summary,request=request,learner=learner,
                       anchor=state.terminal(original),peer=peer,path=value['path'],staging=value['staging'],
                       sourceKey=ids['source']['key'],files=[dict(path=n,size=len(v),sha256=e.digest(v),
                           key=ids['source/'+n]['key']) for n,v in sorted(terminal.items())])
    need(value==expected_plan,'learner cancellation original terminal plan')
    expected['cancellation']={'.':None,'cancellation.json':f.canonical(expected_plan),**state.source_tree(terminal,'source')}
    for name in STAGES[1:]:
        row=observed[name]
        need(row.files==expected,'learner cancellation exact terminal bytes')
        need({k:snap.original_path(v['path']) for k,v in row.identities.items()}==paths,'learner cancellation fixed paths')
        previous=first if name==STAGES[1] else cancelled
        for owner,members in previous.identities.items():
            for member,identity in members['members'].items():
                need(row.identities[owner]['members'][member]==identity,'learner cancellation unchanged original inode')
    def counts(name,generations,learners,applications):
        actual=observed[name].resources['counts']
        need(actual.get('GENERATION',0)==generations and actual.get('LEARNER',0)==learners
             and actual.get('APPLICATION',0)==applications,'learner cancellation retained resources')
    images=lambda files:sum(n.endswith('.image') for n in files)
    counts(STAGES[0],1,0,images(original)+1)
    for name in (STAGES[1],STAGES[3]):counts(name,1,1,images(original)+1+images(terminal))
    need(observed[STAGES[2]].resources==dict(counts={},leases=0,metadata=0,staging=0,queued=0),
         'learner cancellation closed resources')
    return plan,retained


def cancel_trace(members,*,resume=False):
    trace=[] if resume else ['LEARNER_CANCEL_DIRECTORY_FORCED']+forces.write('LEARNER_CANCEL_PLAN')+[
        'LEARNER_CANCEL_RESEAL_FORCED','LEARNER_CANCEL_PLAN_RENAMED']
    trace+=['LEARNER_CANCEL_ACTIVE_PLAN_FORCED']
    if not resume:trace+=['LEARNER_CANCEL_SOURCE_MOVED']
    return trace+['LEARNER_CANCEL_SOURCE_MEMBER_FORCED']*members+[
        'LEARNER_CANCEL_SOURCE_PARENTS_FORCED','LEARNER_CANCEL_BEFORE_RETURN']


def traces(root,original,terminal):
    prepared=lambda resume:forces.write('LEARNER_PREPARED',resume=resume)+[
        'LEARNER_PREPARED_BEFORE_SELECT','LEARNER_PREPARED_BEFORE_RETURN']
    start=list(t.s.p.CUTS)+forces.source(original)+forces.admission()[:3]+forces.write('LEARNER_RETENTION')+[
        'LEARNER_RETENTION_RESEAL_FORCED','LEARNER_RETENTION_RESEAL_PARENT_FORCED','LEARNER_RETENTION_RENAMED']+forces.admission()[3:]+[
        'LEARNER_REPLICA_CREATED','LEARNER_REPLICA_LOCKED']+forces.write('LEARNER_ROOT')+forces.write('LEARNER_NODE')+[
        'LEARNER_SOURCE_MOVED','LEARNER_SOURCE_RETAINED_DIRECTORY_FORCED','LEARNER_SOURCE_MOVE_PARENTS_FORCED']+forces.write('LEARNER_ADMISSION')+[
        'LEARNER_STORE_BEFORE_RETURN']+t.trace(False)+prepared(False)
    reopen=forces.admission()+['LEARNER_REPLICA_LOCKED']+forces.write('LEARNER_ROOT',resume=True)+forces.write('LEARNER_NODE',resume=True)+[
        'LEARNER_SOURCE_RETAINED_DIRECTORY_FORCED','LEARNER_SOURCE_MOVE_PARENTS_FORCED']+forces.write('LEARNER_ADMISSION',resume=True)+[
        'LEARNER_STORE_BEFORE_RETURN']+t.trace(True)+prepared(True)+cancel_trace(len(terminal),resume=True)
    for name,expected in [('initial',start),('cancel',forces.source(terminal)+cancel_trace(len(terminal))),('resume',reopen)]:
        need(d.read(root/('learner-'+name+'-events.json'))==expected,'learner cancellation exact '+name+' force order')


def validate(root):
    root=Path(root);inventory(root)
    prepared,cancelled,request,learner,receipt=t.physical_history(root)
    b.match(root,'after-cancel',cancelled)
    native_failures(root)
    original=c.inventory(root/'learner-source-copy');terminal=c.inventory(root/'learner-progress-copy')
    need(c.inventory(root/'cancelled-original')==terminal,'learner cancellation original export')
    first=d.read(root/'learner-source-wire.json');second=d.read(root/'learner-progress-wire.json');server=d.read(root/'wire.json')
    acquisition=t.source.network_rows(first,server,prepared,request,learner,original,following=second)
    progress=t.source.network_rows(second,server,cancelled,request,learner,terminal,preceding=first,progress=True)
    need(ancestry(original,terminal)[0],'learner cancellation missing original ancestor')
    snapshots(root,prepared,original,terminal,request,learner,receipt);traces(root,original,terminal)
    need(d.read(root/'learner-cancellation-result.json')==dict(status='PASS',scope='native-learner-cancellation',voter=False,
         liveCore=False,publicReady=False,phase3Complete=False,independentReplayQualified=False,testBudgetSeconds=600),
         'learner cancellation result scope')
    return dict(status='PASS',scope='native-learner-cancellation',acquisition=acquisition,progress=progress,
                physicalQualification=True,forceOrderQualified=True,coldReopenQualified=True,
                processDeathQualified=False,autonomous=False,phase3Complete=False)


NEGATIVES={
    'extra-file':'context selection learner cancellation inventory',
    'receipt':'learner typed exact receipt',
    'native-terminal':'admitted exact after-cancel: node-1',
    'received-terminal':'learner cancellation original export',
    'missing-exchange':'learner source exact received trace',
    'changed-snapshot':'learner snapshot original bytes',
    'cold-inode':'learner cancellation unchanged original inode',
    'missing-force':'learner cancellation exact cancel force order',
    'early-return':'learner cancellation exact cancel force order',
    'resume-force':'learner cancellation exact resume force order',
    'closed-leases':'learner cancellation closed resources',
    'false-voter':'learner cancellation result scope',
}


def mutate(root,name):
    def change(path,action):
        path=root/path;value=d.read(path);action(value);path.write_bytes(f.canonical(value))
    if name=='extra-file':(root/'extra').write_bytes(b'foreign')
    elif name=='receipt':(root/'learner-receipt.gsr').write_bytes(b'bad')
    elif name=='native-terminal':(root/'after-cancel/node-1/selector.gsr').write_bytes(b'bad')
    elif name=='received-terminal':(root/'learner-progress-copy/generation.gsr').write_bytes(b'bad')
    elif name=='missing-exchange':change('learner-progress-wire.json',lambda v:v.pop())
    elif name=='changed-snapshot':(root/'learner-reopened/cancellation/cancellation.json').write_bytes(b'bad')
    elif name=='cold-inode':change('learner-reopened/original-identities.json',lambda v:v['cancellation']['members']['cancellation.json'].update(key='foreign-original'))
    elif name=='missing-force':change('learner-cancel-events.json',lambda v:v.remove('LEARNER_CANCEL_SOURCE_MEMBER_FORCED'))
    elif name=='early-return':change('learner-cancel-events.json',lambda v:v.insert(0,v.pop()))
    elif name=='resume-force':change('learner-resume-events.json',lambda v:v.remove('LEARNER_CANCEL_ACTIVE_PLAN_FORCED'))
    elif name=='closed-leases':change('learner-closed/resources.json',lambda v:v.update(counts=dict(LEARNER=1),leases=1))
    elif name=='false-voter':change('learner-cancellation-result.json',lambda v:v.update(voter=True))
    else:raise ValueError('unknown learner cancellation negative: '+name)


def qualify(root):
    root=Path(root);original=validate(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-learner-cancellation-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target);mutate(target,name)
            try:validate(target)
            except ValueError as error:need(str(error)==reason,'learner cancellation unrelated negative: '+name+': '+str(error))
            else:raise ValueError('learner cancellation accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--qualify',action='store_true');mode.add_argument('--diagnose',action='store_true');args=parser.parse_args()
    print(json.dumps((diagnose if args.diagnose else qualify if args.qualify else validate)(args.root)))
