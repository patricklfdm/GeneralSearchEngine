"""Portable replay of one indivisible PREPARE 1–6 learner history.

Native states are reduced from the original bootstrap, independently of the
learner copies. Recorded paths are data only. This focused reader cannot qualify
the complete network/process/profile matrix or confer voting authority.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
from . import learner_cycle_bytes as states
from . import learner_cycle_forces as forces
from . import learner_typed_evidence as t
from . import remove_maintenance_evidence as maintenance

b,c,d,a,e,f,need=t.b,t.c,t.d,t.a,t.e,t.f,t.need
STAGES=('before-seed-handoff','selected-seed-head','retired-seed-predecessor',
        'before-slot-selection','selected-slot-head','retired-slot-seed','reopened-slot-head')+tuple(
    f'cycle-{revision}-{stage}' for revision in range(4,7) for stage in
    ('before-transfer','installed','before-selection','selected','retired','reopened'))
COPIES={1:'revision-one',2:'revision-two',3:'revision-three',**{i:f'cycle-{i}-received' for i in range(4,7)}}


def inventory(root):
    need(root.is_dir() and not root.is_symlink(),'learner cycles evidence directory')
    total=count=0;pending=[root]
    while pending:
        for path in pending.pop().iterdir():
            count+=1
            need(count<=65536 and not path.is_symlink() and (path.is_file() or path.is_dir()),'learner cycles regular bounded inventory')
            if path.is_dir():pending.append(path)
            else:
                size=path.stat().st_size;total+=size
                need(path.stat().st_nlink==1 and size<=64*e.MIB and total<=512*e.MIB,'learner cycles file capacity')
    names={'original-plan.gsbp','original-application.image','initial','before-network','installed','selected.gsr','after-close',
           'calls.json','events.json','wire.json','failures.json','learner-reserve-payload.bin','current-receipt.gsr','third-receipt.gsr',
           'retired-successor','retired-typed','installed-slot','installed-slot-typed','before-current-head',
           'after-current-retirement','after-third-acquisition','current-head-result.json','current-head-events.json',
           'current-head-wire.json','current-head-stages.json'}|set(STAGES)|set(COPIES.values())
    names|={f'{stage}-{i}' for stage in ('applied','published') for i in range(1,17)}
    names|={f'installed-{i}' for i in range(2,9)}|{f'selected-{i}.gsr' for i in range(2,9)}
    names|={f'cycle-{i}-{stage}' for i in range(4,7) for stage in ('before-prepare','after-prepare','receipt.gsr')}
    b.selection.layout(root,names,'learner cycles')


def reconcile(root,model,ordinal):
    """Reduce a fresh renewal campaign and its BARRIER from original grants."""
    model.group=maintenance.maintenance(model.group,t.VOTERS)
    group={n:model.group[n] for n in t.VOTERS};stage='installed-'+str(ordinal)
    _,_,installed=d.s.campaign(root,group,ordinal+1,stage,selected_prefix=d.slot.prefix,
        merge_ledgers=lambda before,sources:maintenance.merge(model.group,before,sources))
    for node,files in installed.items():
        prefix,members,packet=c.current(files);_,prior,_=c.current(group[node]);cuts={}
        def add(cut):
            index=cut['index']
            need(index not in cuts or cuts[index]==cut,'learner cycles conflicting retained cut');cuts[index]=cut
        for name,raw in group[node].items():
            if name.startswith('sources/') and name.endswith('/source.gscp'):add(e.p.decode(raw)['capsule']['cut'])
        for original in group.values():
            for row in d.s.r.decode(original[d.s.FILE])['plan']['peers']:
                for point in [*row['possible'],*row.get('renewals',[])]:add(point['cut'])
        ancestry=b''.join(a.x.retained_campaign_ancestry(prior,packet,cuts[index]) for index in sorted(cuts))
        if ancestry:
            members=dict(members,**{'ancestry.gsr':ancestry})
            selector,generation=c.generation(members,packet['capsule'],node,prefix.split('/')[1],None)
            files.update(generation);files['selector.gsr']=selector
    model.group.update(installed);b.match(root,stage,model.group)
    need((root/f'selected-{ordinal}.gsr').read_bytes()==c.current(model.group['node-1'])[1]['selected.gsr'],
         'learner cycles exact renewal selection')
    model.counter=ordinal+1;model.first=None
    model.group=maintenance.maintenance(model.group,t.VOTERS);model.publish('BARRIER',None)


def physical(root):
    group=d.s.initialize(b.original(root,3,False))
    group={n:dict(v,**{d.future.FILE:d.future.frame(d.future.initial(v),{})}) for n,v in group.items()}
    b.match(root,'before-network',group)
    _,_,installed=d.s.campaign(root,{n:group[n] for n in t.VOTERS},2,'installed',selected_prefix=d.slot.prefix)
    group.update(installed);b.match(root,'installed',group)
    need((root/'selected.gsr').read_bytes()==c.current(group['node-1'])[1]['selected.gsr'],'learner cycles original selection')
    model=t.source.r.CurrentSlot.__new__(t.source.r.CurrentSlot)
    model.root=root;model.group=group;model.active=list(t.VOTERS);model.voters=t.VOTERS
    model.required=set();model.slot=0;model.counter=2;model.first=None
    model.observed=set();model.phases={};model.documents=[]
    model.history=f.decode(group['node-1']['root.gsr'],'records','ROOT')['historyId']
    supplied=states.record((root/'learner-reserve-payload.bin').read_bytes(),8192);request=supplied.get('request')
    need(set(supplied)=={'request'} and type(request) is dict and request.get('kind')=='ADD' and request.get('number')==1
         and type(request.get('target')) is list and len(request['target'])==4,'learner cycles native request')
    joining=[v for v in request['target'] if v['node']=='node-4'];need(len(joining)==1,'learner cycles joining identity');learner=joining[0]
    def publish(kind,payload):
        model.group=maintenance.maintenance(model.group,t.VOTERS);model.publish(kind,payload)
    publish('BARRIER',None);publish('RESERVE',supplied)
    revisions={};receipts={};originals={}
    for revision in range(1,7):
        if revision>=4:b.match(root,f'cycle-{revision}-before-prepare',model.group)
        reconcile(root,model,revision+1)
        publish('PREPARE',dict(number=1,revision=revision));revisions[revision]=copy.deepcopy(model.group)
        if revision<=3:b.match(root,{1:'before-current-head',2:'after-current-retirement',3:'after-third-acquisition'}[revision],model.group)
        else:b.match(root,f'cycle-{revision}-after-prepare',model.group)
        prefix,files,packet=c.current(model.group['node-1'])
        catalog=f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG');operation=catalog['results'][0]
        need(catalog['active']==1 and operation['phase']=='PREPARING' and operation['revision']==revision
             and operation['request']==request,'learner cycles native preparation')
        receipt=dict(root=request['root'],number=1,request=e.digest(f.canonical(request)),identity=learner,
                     image=operation['prepared']['application'],prepared=operation['prepared'])
        receipts[revision]=f.encode('records','LEARNER',dict(root=request['root'],receipt=receipt))
        originals[revision]=dict(files,**{'generation.gsr':model.group['node-1'][prefix+'generation.gsr']})
        if revision>1:
            name={2:'current-receipt.gsr',3:'third-receipt.gsr'}.get(revision,f'cycle-{revision}-receipt.gsr')
            need((root/name).read_bytes()==receipts[revision],'learner cycles exact native receipt')
    reconcile(root,model,8)
    publish('CANCEL',dict(number=1));b.match(root,'after-close',model.group)
    need(d.read(root/'failures.json')==[],'learner cycles native failures')
    descriptor=e.parse((root/'original-plan.gsbp').read_bytes()[48:])['descriptor']
    return revisions,originals,receipts,request,learner,{k:descriptor[k] for k in ('application','core')}


def acquisitions(rows):
    """Six whole ROOT/status/prefix/generation sessions, never arbitrary slices."""
    need(type(rows) is list and 0<len(rows)<=32768,'learner cycles bounded wire')
    traces=[];starts=[]
    for index,row in enumerate(rows):
        need(type(row) is dict and set(row)=={'request','response'},'learner cycles wire row')
        trace=t.source.t.t.wire(row['request'])[1]['trace']
        if not traces or trace!=traces[-1]:
            need(trace not in traces,'learner cycles reused trace');traces.append(trace);starts.append(index)
    need(len(starts)==24,'learner cycles six complete acquisitions')
    starts.append(len(rows))
    return [(starts[i],starts[i+4]) for i in range(0,24,4)]


def boundaries(root,wire):
    events=d.read(root/'current-head-events.json');positions=d.read(root/'current-head-stages.json')
    need(type(events) is list and len(events)<=4096 and all(type(v) is str and 0<len(v)<=128 for v in events),'learner cycles bounded events')
    need(type(positions) is dict and set(positions)==set(STAGES),'learner cycles exact stages')
    previous=dict(events=0,exchanges=0)
    for name in STAGES:
        value=positions[name]
        need(type(value) is dict and set(value)=={'events','exchanges'} and
             all(type(value[k]) is int and previous[k]<=value[k]<=limit for k,limit in [('events',len(events)),('exchanges',len(wire))]),
             'learner cycles monotonic stage offsets')
        previous=value
    need(previous==dict(events=len(events),exchanges=len(wire)),'learner cycles unaccounted trailing observation')
    return events,positions


def replay_snapshots(root,originals,receipts,request,learner,root_bytes,descriptor):
    snapshots={name:states.s.read(root/name) for name in STAGES}
    model=states.States(originals,receipts,request,learner,root_bytes,descriptor)
    model.initial(snapshots[STAGES[0]]);model.seed_selected(snapshots[STAGES[1]]);model.seed_retired(snapshots[STAGES[2]])
    model.installed(snapshots[STAGES[3]],1,already_typed=True);model.selected(snapshots[STAGES[4]],1)
    model.retired(snapshots[STAGES[5]]);model.reopened(snapshots[STAGES[6]])
    for revision in range(4,7):
        prefix=f'cycle-{revision}-';sequence=revision-2
        model.reopened(snapshots[prefix+'before-transfer']);model.installed(snapshots[prefix+'installed'],sequence)
        model.prepared(snapshots[prefix+'before-selection'],sequence);model.selected(snapshots[prefix+'selected'],sequence)
        model.retired(snapshots[prefix+'retired']);model.reopened(snapshots[prefix+'reopened'])
    # Earlier convenience copies remain exact views of the same original history.
    for directory,stage,owner in [('retired-typed',STAGES[2],'seed-typed'),('installed-slot',STAGES[3],'slots'),('installed-slot-typed',STAGES[3],'slot-typed')]:
        need(c.inventory(root/directory)=={k:v for k,v in snapshots[stage].files[owner].items() if k!='.'},'learner cycles original auxiliary copy')
    old=snapshots[STAGES[2]];plan=states.record(old.files['seed']['install.json'],256*1024)
    identity=f.canonical(dict(directoryKey=plan['directoryKey'],sourceKey=plan['sourceKey'],files=[dict(path=row['path'],key=row['key']) for row in plan['files']]))
    need(c.inventory(root/'retired-successor')==dict({k:v for k,v in old.files['seed'].items() if k!='.'},**{'identity.json':identity}),
         'learner cycles original auxiliary copy')
    return snapshots


def validate(root):
    root=Path(root);inventory(root)
    revisions,originals,receipts,request,learner,descriptor=physical(root)
    wire=d.read(root/'current-head-wire.json');ranges=acquisitions(wire);server=d.read(root/'wire.json')
    events,positions=boundaries(root,wire)
    for revision,(start,end) in enumerate(ranges,1):
        t.source.network_rows(wire[start:end],server,revisions[revision],request,learner,c.inventory(root/COPIES[revision]),
                              preceding=wire[:start],following=wire[end:])
    snapshots=replay_snapshots(root,originals,receipts,request,learner,revisions[1]['node-1']['root.gsr'],descriptor)
    forces.validate(events,positions,originals,snapshots)
    for name in STAGES:
        if name in STAGES[:3]:expected=ranges[1][1]
        elif name in STAGES[3:7]:expected=ranges[2][1]
        else:
            revision=int(name.split('-')[1]);expected=ranges[revision-1][0 if name.endswith('before-transfer') else 1]
        need(positions[name]['exchanges']==expected,'learner cycles exact stage wire boundary')
    cycles=[dict(revision=i,sequence=i-2,slot='a' if i%2==0 else 'b',source=e.digest(originals[i]['source.gscp']),
                 generation=e.digest(originals[i]['generation.gsr']),receipt=e.digest(receipts[i]),wireStart=ranges[i-1][0],wireEnd=ranges[i-1][1]) for i in range(4,7)]
    expected_result=dict(status='PASS',scope='native-alternating-learner-slots',installedThirdRevision=True,
         voter=False,publicReady=False,phase3Complete=False,testBudgetSeconds=900,selectedThirdRevision=True,seedRetired=True,
         cycles=cycles,lastRevision=6,independentReplayQualified=False)
    need((root/'current-head-result.json').read_bytes()==f.canonical(expected_result),'learner cycles result scope')
    return dict(status='PASS',scope='native-six-revision-learner-history',revisions=6,snapshots=len(snapshots),exchanges=len(wire),
                physicalQualification=True,learnerAcquisitionQualified=True,selectedHeadQualified=True,forceOrderQualified=True,
                fullNetworkQualification=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES={
    'extra-file':'context selection learner cycles inventory',
    'native-receipt':'learner cycles exact native receipt',
    'original-published':'admitted exact published-6: node-1',
    'received-generation':'learner source exact original generation',
    'missing-stage':'learner cycles exact stages',
    'boolean-offset':'learner cycles monotonic stage offsets',
    'snapshot-bytes':'learner snapshot original bytes',
    'snapshot-capacity':'learner snapshot resource counts',
    'cold-inode':'learner cycles unchanged original identity',
    'missing-force':'learner cycles exact force interval: cycle-5-selected',
    'early-release':'learner cycles exact force interval: cycle-5-retired',
    'false-ready':'learner cycles result scope',
}


def mutate(root,name):
    def change(path,action):
        path=root/path;value=d.read(path);action(value);path.write_bytes(f.canonical(value))
    if name=='extra-file':(root/'extra').write_bytes(b'foreign')
    elif name=='native-receipt':(root/'cycle-5-receipt.gsr').write_bytes(b'changed')
    elif name=='original-published':(root/'published-6/node-1/selector.gsr').write_bytes(b'changed')
    elif name=='received-generation':(root/'cycle-5-received/generation.gsr').write_bytes(b'changed')
    elif name=='missing-stage':change('current-head-stages.json',lambda v:v.pop('cycle-5-retired'))
    elif name=='boolean-offset':change('current-head-stages.json',lambda v:v['cycle-5-retired'].update(events=True))
    elif name=='snapshot-bytes':(root/'cycle-5-selected/slot-typed/learner.gsr').write_bytes(b'changed')
    elif name=='snapshot-capacity':change('cycle-5-retired/resources.json',lambda v:v['counts'].update(GENERATION=3))
    elif name=='cold-inode':change('cycle-5-reopened/original-identities.json',lambda v:v['operation']['members']['operation.lock'].update(key='different-original-inode'))
    elif name in ('missing-force','early-release'):
        events=d.read(root/'current-head-events.json');positions=d.read(root/'current-head-stages.json')
        if name=='missing-force':
            start=positions['cycle-5-before-selection']['events'];end=positions['cycle-5-selected']['events']
            index=events.index('LEARNER_SLOT_HEAD_ACTIVE_FORCED',start,end);events.pop(index)
            for row in positions.values():
                if row['events']>index:row['events']-=1
        else:
            start=positions['cycle-5-selected']['events'];end=positions['cycle-5-retired']['events']
            index=events.index('LEARNER_SLOT_RETIRE_RELEASED',start,end);events.insert(start,events.pop(index))
        (root/'current-head-events.json').write_bytes(f.canonical(events));(root/'current-head-stages.json').write_bytes(f.canonical(positions))
    elif name=='false-ready':change('current-head-result.json',lambda v:v.update(publicReady=True))
    else:raise ValueError('unknown learner cycle negative: '+name)


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-learner-cycle-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target);mutate(target,name)
            try:validate(target)
            except ValueError as error:need(str(error)==reason,'learner cycles unrelated negative: '+name+': '+str(error))
            else:raise ValueError('learner cycles accepted negative: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
