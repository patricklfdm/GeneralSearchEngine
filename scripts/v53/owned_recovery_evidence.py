"""Replay actual admitted publications before checking new-process grants/reopens.

No history supplied by a worker is an oracle. Original physical reconstruction
is reused without weakening its exact inventories, force order or image checks.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import bootstrap_publication_evidence as b
from . import owned_generation_evidence as selected
from . import retirement_evidence as retirement
e=b.e;c=b.c


def same(actual,expected):
    return e.f.canonical(actual)==e.f.canonical(expected)


def load(path):
    return e.parse(b.t.plans.read(path,65536))


def worker(path,files,source,events=None,counter=None,basis=None):
    actual=load(path);prefix,members,packet=c.current(files)
    expected=dict(status='PASS',cut=packet['capsule']['cut'],manifest=e.digest(files[prefix+'generation.gsr']),
                  sourceCut=source,copiedObservations=0,events=actual.get('events'))
    if counter is not None:expected['counter']=counter
    if basis is not None:expected['basis']=basis
    ev=actual.get('events')
    e.need(type(ev) is list and 0<len(ev)<=4096 and all(type(v) is str for v in ev),'owned recovery worker events')
    if events is not None:e.need(ev==events,'owned recovery original worker calls')
    e.need(same(actual,expected),'owned recovery exact worker receipt')


def profile(root,children,size,backup):
    # Full physical replay first, including actual original votes and typed images.
    final=b.validate_case(root,size,backup);calls=e.parse(b.t.plans.read(root/'calls.json',8*e.MIB))
    names=sorted(final);expected={'allocate.json','ballot.json'}
    expected|={f'{kind}-{n}.json' for n in range(1,size+1) for kind in ('prepare','inspect')}
    b.selection.layout(children,expected,'owned recovery processes')
    before={n:c.inventory(root/'slot-2-settled'/n) for n in names}
    prepared={n:c.inventory(root/'round-2-prepared'/n) for n in names}
    identity=e.f.decode(before['node-1']['node.gsr'],'records','NODE')['identity']
    e.need(same(load(children/'ballot.json'),dict(counter=3,proposer='node-1',incarnation=identity['storage'])),'owned recovery original ballot')
    def events(node,operation):return next(r['events'] for r in calls if r['node']==node and r['operation']==operation)
    _,members,packet=c.current(before['node-1']);old=e.f.decode(members['basis.gsr'],'records','BASIS')
    worker(children/'allocate.json',before['node-1'],old['cut'],events('node-1','allocate-2'),counter=3)
    for number,node in enumerate(names,1):
        _,_,packet=c.current(prepared[node]);journal=c.journal(prepared[node]['grants.gsr'],packet['capsule']['root'],node)
        kind,raw,basis=journal[-1];e.need(kind=='BASIS','owned recovery original basis')
        worker(children/f'prepare-{number}.json',prepared[node],basis['cut'],events(node,'prepare-2'),basis=e.digest(raw))
        worker(children/f'inspect-{number}.json',final[node],basis['cut'])
    return final


def validate(directory):
    root=Path(directory);b.selection.layout(root,{'histories','processes','receipt.json'},'owned recovery root')
    names=[f'size-{n}-{source}' for n in (3,4,5) for source in ('empty','backup')]
    b.selection.layout(root/'histories',set(names)|{'receipt.json'},'owned recovery histories')
    b.selection.layout(root/'processes',set(names),'owned recovery process profiles')
    receipts=load(root/'histories/receipt.json');e.exact(receipts,'schema status cases publicBootstrap publicRuntime freshProcesses syntheticObservations')
    e.need(same(receipts,dict(schema='gse-v53-owned-recovery-histories-v1',status='PASS',cases=receipts['cases'],publicBootstrap=True,
                         publicRuntime=False,freshProcesses=True,syntheticObservations=False)),'owned recovery history scope')
    e.need(type(receipts['cases']) is list and len(receipts['cases'])==6,'owned recovery complete profiles')
    histories=set()
    for row,name in zip(receipts['cases'],names):
        size=int(name[5]);backup=name.endswith('backup');group=profile(root/'histories'/name,root/'processes'/name,size,backup)
        identity=e.f.decode(group['node-1']['root.gsr'],'records','ROOT')['historyId']
        e.need(uuid.UUID(identity).version==4 and identity not in histories,'owned recovery distinct histories');histories.add(identity)
        e.exact(row,'case status voters publications sequence peakImages peakMetadata peakStaging')
        e.need(same({k:row[k] for k in ('case','status','voters','publications','sequence')},dict(case=name,status='PASS',voters=size,publications=3,sequence=42 if backup else 1)),'owned recovery case receipt')
        e.need(all(type(row[k]) is int and 0<row[k]<=maximum for k,maximum in [('peakImages',7),('peakMetadata',384*e.MIB),('peakStaging',512*e.MIB)]),'owned recovery reservation limits')
    expected=dict(schema='gse-v53-owned-recovery-v1',status='PASS',profiles=6,freshProcesses=54,historicalObservationsSupplied=False,publicRuntime=False)
    e.need(same(load(root/'receipt.json'),expected),'owned recovery scope receipt')
    return dict(status='PASS',profiles=6,freshProcesses=54,nodePublications=72,publicRuntime=False)


def qualify(directory):
    original=validate(directory);negatives=[]
    variants=[('scope','owned recovery scope receipt'),('missing-worker','context selection owned recovery processes inventory'),
              ('ballot','owned recovery original ballot'),('worker-basis','owned recovery exact worker receipt'),
              ('worker-source','owned recovery exact worker receipt'),('worker-manifest','owned recovery exact worker receipt'),
              ('worker-vote','owned recovery exact worker receipt'),('worker-events','owned recovery original worker calls'),
              ('prepared','admitted exact round-2-prepared'),('selected','admitted exact round-2-selected'),
              ('published','admitted exact slot-3-published'),('retired-source','admitted exact round-2-settled')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-owned-recovery-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(directory,target)
            root=target/'histories/size-3-empty';children=target/'processes/size-3-empty'
            if name=='scope':
                path=target/'receipt.json';value=load(path);value['publicRuntime']=True;path.write_bytes(e.f.canonical(value))
            elif name=='missing-worker':(children/'inspect-3.json').unlink()
            elif name=='ballot':
                path=children/'ballot.json';value=load(path);value['counter']=4;path.write_bytes(e.f.canonical(value))
            elif name.startswith('worker-'):
                path=children/'prepare-1.json';value=load(path)
                key={'worker-basis':'basis','worker-source':'sourceCut','worker-manifest':'manifest','worker-vote':'copiedObservations','worker-events':'events'}[name]
                value[key]=['invented'] if key=='events' else 1 if key=='copiedObservations' else {} if key=='sourceCut' else 'a'*64
                path.write_bytes(e.f.canonical(value))
            else:
                stage={'prepared':'round-2-prepared','selected':'round-2-selected','published':'slot-3-published','retired-source':'round-2-settled'}[name]
                if name=='prepared':
                    path=root/stage/'node-1/allocator.gsr';value=e.f.decode(path.read_bytes(),'records','ALLOCATOR');value['counter']+=1
                    path.write_bytes(e.f.encode('records','ALLOCATOR',value))
                else:(root/stage/'node-1/grants.gsr').write_bytes(b'changed')
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'owned recovery unrelated negative: '+name+': '+str(error))
            else:raise ValueError('owned recovery accepted negative: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


CUTS=('RETIREMENT_SOURCE_FORCED','RETIREMENT_PARENT_FORCED','RETIREMENT_FILE_DELETED','RETIREMENT_FILE_DELETED')


def validate_crashes(directory):
    root=Path(directory);extra={f'round-2-{stage}' for stage in ('prepared','selected','installed','settled')}|{'calls.json','observations.json'}
    b.selection.layout(root,{'history','states','receipt.json','recovered.json'}|{f'death-{n}.log' for n in range(4)},'owned recovery crash root')
    group=selected.publication(root/'history',3,extra);b.campaign(root/'history',group,2)
    installed={node:c.inventory(root/'history/round-2-installed'/node) for node in group}
    # Derive the exact floor copies from the validated original installed generations.
    state=dict(installed['node-1']);state['floor-copies']=None;refs=[]
    for node in ('node-1','node-2'):
        prefix,members,packet=c.current(installed[node]);manifest=installed[node][prefix+'generation.gsr'];value=e.f.decode(manifest,'records','GENERATION')
        digest=e.digest(manifest);base='floor-copies/'+digest;state[base]=None
        state.update({base+'/'+name:raw for name,raw in dict(members,**{'generation.gsr':manifest}).items()})
        refs.append(dict(voter=node,generation=digest,catalog=value['catalog'],snapshot=value['application']))
    prefix,_,packet=c.current(installed['node-1']);floor=e.f.encode('records','FLOOR',dict(root=packet['capsule']['root'],node='node-1',cut=packet['capsule']['cut'],sources=refs))
    state['floor-copies/floor.gsr']=floor;state['floor-copies/proposal.gsr']=floor
    b.selection.layout(root/'states',{'before','recovered'}|{f'death-{n}' for n in range(4)},'owned recovery crash states')
    e.need(c.inventory(root/'states/before')==state,'owned recovery original pre-retirement state')
    old_prefix,old_members,_=c.current(group['node-1']);original=dict(old_members,**{'generation.gsr':group['node-1'][old_prefix+'generation.gsr']})
    record=e.f.encode('records','RETIREMENT',dict(root=packet['capsule']['root'],node='node-1',floor=e.digest(floor),selector=e.digest(state['selector.gsr']),
                files=[dict(path=old_prefix+n,size=len(raw),sha256=e.digest(raw)) for n,raw in sorted(original.items())]))
    state={name:dict(directory=True) if raw is None else retirement.entry(raw) for name,raw in state.items()};cases=[]
    for ordinal,cut in enumerate(CUTS):
        mode='halt' if ordinal%2==0 else 'kill';steps,_=retirement.transaction(state,original,record,slot=old_prefix.split('/')[1])
        state=steps[retirement.cut_position(steps,cut)][1];retirement.snapshot(root/f'states/death-{ordinal}',state)
        e.need(b.t.plans.read(root/f'death-{ordinal}.log',65536)==('CUT '+cut+'\n').encode(),'owned recovery original crash cut')
        cases.append(dict(ordinal=ordinal,cut=cut,mode=mode,exit=23 if mode=='halt' else 137))
    steps,_=retirement.transaction(state,original,record,slot=old_prefix.split('/')[1]);retirement.snapshot(root/'states/recovered',steps[-1][1])
    worker(root/'recovered.json',installed['node-1'],packet['capsule']['cut'])
    expected=dict(schema='gse-v53-owned-recovery-crashes-v1',status='PASS',cases=cases,publicRuntime=False,powerLoss=False)
    e.need(same(load(root/'receipt.json'),expected),'owned recovery crash receipt')
    return dict(status='PASS',cases=4,freshProcesses=5,publicRuntime=False,powerLoss=False)


def qualify_crashes(directory):
    original=validate_crashes(directory);negatives=[]
    for name,reason in [('before','owned recovery original pre-retirement state'),('death','retirement exact physical snapshot'),
                        ('recovered','retirement exact physical snapshot'),('cut','owned recovery original crash cut'),
                        ('receipt','owned recovery crash receipt'),('source','owned recovery exact worker receipt')]:
        with tempfile.TemporaryDirectory(prefix='v53-owned-recovery-crash-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(directory,target)
            if name in ('before','death','recovered'):
                stage='death-2' if name=='death' else name;(target/'states'/stage/'grants.gsr').write_bytes(b'changed')
            elif name=='cut':(target/'death-0.log').write_text('CUT WRONG\n')
            else:
                path=target/('receipt.json' if name=='receipt' else 'recovered.json');value=load(path)
                if name=='receipt':value['cases'][0]['exit']=0
                else:value['sourceCut']={}
                path.write_bytes(e.f.canonical(value))
            try:validate_crashes(target)
            except ValueError as error:e.need(reason in str(error),'owned recovery unrelated crash negative: '+name+': '+str(error))
            else:raise ValueError('owned recovery accepted crash negative: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');p.add_argument('--crashes',action='store_true');a=p.parse_args()
    check=(qualify_crashes if a.qualify else validate_crashes) if a.crashes else (qualify if a.qualify else validate)
    print(json.dumps(check(a.directory),sort_keys=True))
