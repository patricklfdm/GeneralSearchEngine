"""Admitted mixed-ballot context completion under a newer published prefix."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import covered_context_evidence as q
from . import context_mixed_acceptance_evidence as mixed
from .retirement_source_process_evidence import same
e, c, t, b = q.e, q.c, q.t, q.b


def reaccept(group, nodes, observed, phases):
    result = dict(group)
    for node in nodes:
        files = group[node]; _, members, packet = c.current(files)
        frames, values = c.pending(files['pending.accept'], phases[node])
        accept = e.f.encode('records', 'ACCEPT', dict(values['ACCEPT'], ballot=e.f.decode(members['promise.gsr'], 'records', 'PROMISE')['ballot']))
        changed = q.release(files); changed.pop('pending.context')
        changed['pending.accept'] = e.container([files['selector.gsr'], members['promise.gsr'], members['selected.gsr'], frames['ENTRY'], accept], frames['PAYLOAD'])
        result[node] = changed
        observed.append(dict(voter=node, storage=e.f.decode(files['node.gsr'], 'records', 'NODE')['identity']['storage'],
                             record=e.digest(accept), parent=e.digest(e.f.canonical(packet['capsule']['cut']))))
    return result


def floors(group, nodes, peers=None):
    result = dict(group); copies = {}; refs = []
    for node in (nodes if peers is None else peers):
        prefix, members, packet = c.current(group[node]); raw = group[node][prefix+'generation.gsr']
        manifest = e.f.decode(raw, 'records', 'GENERATION'); dest = 'floor-copies/'+e.digest(raw)
        copies[dest] = None; copies.update({dest+'/'+k:v for k,v in dict(members, **{'generation.gsr':raw}).items()})
        refs.append(dict(voter=node, generation=e.digest(raw), catalog=manifest['catalog'], snapshot=manifest['application']))
    for node in nodes:
        packet = c.current(group[node])[2]
        floor = e.f.encode('records', 'FLOOR', dict(root=packet['capsule']['root'], node=node, cut=packet['capsule']['cut'], sources=refs))
        result[node] = dict(group[node], **copies, **{'floor-copies':None, 'floor-copies/floor.gsr':floor, 'floor-copies/proposal.gsr':floor})
    return result


def calls(root, names, minority, majority, headroom):
    expected = []
    def many(nodes, label): expected.extend((node,label) for node in nodes)
    def maintain(nodes, label): many(nodes,label+'-copy'); many(nodes,label+'-maintain')
    def campaign(counter, install=True):
        expected.append((names[-1],f'allocate-{counter}'))
        for op in ('prepare','select')+(('install',) if install else ()): many(names,op+'-'+str(counter))
    def publish(slot,nodes):
        for op in ('accept','proof','certificate','apply','publish'): many(nodes,op+'-'+str(slot))
        maintain(nodes,f'slot-{slot}-settled'); many(nodes,'inspect-'+str(slot))
    expected.append((names[0],'allocate-1'))
    for op in ('prepare','select','install'): many(names,op+'-1')
    maintain(names,'round-1-settled'); expected.append((names[-1],'entry'))
    for op in ('initial-vote','original-proof','original-certificate'): many(names,op)
    campaign(3); many(names,'retain-context'); many(names,'context-retirement'); many(majority,'mixed-reaccept')
    campaign(4); many(names,'mixed-context'); many(majority,'mixed-floor-copy'); many(majority,'mixed-floor')
    many(names,'mixed-retirement'); many(majority,'mixed-source-retirement')
    if headroom:
        for node in minority: many([node,node],'headroom-refusal')
        many(names,'headroom-floor-copy'); many(minority,'headroom-reaccept'); many(minority,'headroom-floor'); many(minority,'headroom-reclaim')
    many(majority,'majority-reaccept'); publish(1,majority)
    campaign(5,False); many(names,'install-5'); many([] if headroom else minority,'release-covered-floor'); maintain(names,'round-5-settled')
    campaign(6); maintain(names,'round-6-settled'); expected.append((names[-1],'entry')); publish(2,names)
    rows = q.read(root/'calls.json',8*e.MIB)
    e.need(type(rows) is list and [(row.get('node'),row.get('operation')) for row in rows] == expected,'mixed covered call inventory')
    for row in rows:
        e.exact(row,'node operation events'); events = row['events']
        e.need(type(events) is list and all(type(v) is str for v in events),'mixed covered force type')
        if row['operation'] == 'install-5' and row['node'] in minority and not headroom:
            required = ['INSTALL_SELECTOR_RENAMED','INSTALL_PARENT_FORCED','CONTEXT_SETTLEMENT_VALIDATED','SETTLED_VOTE_RENAMED',
                        'SETTLED_VOTE_PARENT_FORCED','CONTEXT_SETTLEMENT_EMPTY_FORCED','CONTEXT_REDUNDANT_DELETED','CONTEXT_REDUNDANT_PARENT_FORCED','CONTEXT_SETTLEMENT_CLEARED','INSTALL_BEFORE_RETURN']
            same([v for v in events if v in required],required,'mixed covered cleanup force order')
        if row['operation']=='headroom-refusal':
            e.need(not any(v.startswith('PROMISE_') or v=='GRANT_BEFORE_RETURN' for v in events),'mixed covered refusal wrote grant')
        if row['operation']=='headroom-reclaim':
            required=['SOURCE_RETIREMENT_BEFORE_RETURN','FLOOR_RELEASE_CLEARED']
            same([v for v in events if v in required],required,'mixed covered headroom force order')
        if row['operation']=='headroom-floor':
            same([v for v in events if v=='FLOOR_BEFORE_RETURN'],['FLOOR_BEFORE_RETURN'],'mixed covered headroom floor force')


def clean(root):
    root = Path(root); p,names,majority,group,observed,entry,payload,phases = q.initial(root); minority = [n for n in names if n not in majority]
    e.need(p['phase']=='CERTIFICATE','mixed covered original phase')
    own_phases = {n:phases for n in names}
    group = reaccept(group,majority,observed,own_phases); b.match(root,'mixed-reaccepted',group)
    own_phases.update({n:() for n in majority}); old = group
    _,group,_ = q.campaign(root,group,4,own_phases,True); b.match(root,'round-4-installed',group)
    group.update(q.retain({n:group[n] for n in majority},old,())); b.match(root,'mixed-contexts',group)
    group = floors(group,majority); b.match(root,'mixed-floors',group)
    group = {n:mixed.retire_generation(files) for n,files in group.items()}; b.match(root,'mixed-retired',group)
    for node in majority:
        basis = e.f.decode(c.current(old[node])[1]['basis.gsr'],'records','BASIS')
        group[node] = mixed.retire_source(group[node],basis)
    b.match(root,'mixed-sources-retired',group); headroom=p['size']>3
    if headroom:
        b.match(root,'headroom-refused',group)
        rows=[dict(node=node,attempt=attempt,reason='CAPACITY_EXCEEDED',outcome='NOT_SUBMITTED',status='PASS') for node in minority for attempt in (1,2)]
        same(q.read(root/'headroom-refusals.json'),rows,'mixed covered capacity refusal')
        for node in minority:
            e.need(sum(k.endswith('.image') for k in group[node])==6,'mixed covered refusal physical images')
        group=reaccept(group,minority,observed,own_phases); own_phases.update({n:() for n in minority}); b.match(root,'headroom-reaccepted',group)
        for node in minority:
            peers=sorted([node]+[n for n in names if n!=node][:len(names)//2]);group=floors(group,[node],peers)
        b.match(root,'headroom-floors',group)
        for node in minority:
            basis=e.f.decode(c.current(old[node])[1]['basis.gsr'],'records','BASIS')
            group[node]=q.release(mixed.retire_source(group[node],basis))
        b.match(root,'headroom-reclaimed',group)
    group = reaccept(group,majority,observed,own_phases); b.match(root,'majority-reaccepted',group)
    group,_ = q.covered.publication(root,group,1,entry,payload,observed,majority)
    before,group,_ = q.campaign(root,group,5,own_phases); b.match(root,'advanced-selected',before); b.match(root,'covered-installed',group)
    for node in ([] if headroom else minority):
        group[node] = mixed.retire_generation(q.release(group[node]))
    b.match(root,'floor-released',group); group = q.d.settle(root,'round-5-settled',group,names)
    _,group,ballot = q.campaign(root,group,6,()); b.match(root,'round-6-installed',group); group = q.d.settle(root,'round-6-settled',group,names)
    barrier = q.d.entry(group,b'',ballot,'BARRIER'); e.need(t.plans.read(root/'barrier.gsr',16384)==barrier,'mixed covered continuation')
    group,_ = q.covered.publication(root,group,2,barrier,b'',observed,names); q.covered.observations(root,observed); calls(root,names,minority,majority,headroom)
    paths = {'original-plan.gsbp','original-application.image','initial','profile.json','entry.gsr','payload.bin','calls.json','observations.json',
             'initial-votes','original-proved','original-certified','contexts','original-retired','mixed-reaccepted','mixed-contexts','mixed-floors','mixed-retired',
             'mixed-sources-retired','majority-reaccepted','advanced-selected','covered-installed','floor-released','barrier.gsr'}
    for counter in (1,3,4,5,6):
        paths |= {f'round-{counter}-{s}' for s in (('prepared','selected') if counter==5 else ('prepared','selected','installed'))}
    paths |= {'round-1-settled','round-5-settled','round-6-settled'}; peak = 0
    if headroom: paths |= {'headroom-refused','headroom-refusals.json','headroom-reaccepted','headroom-floors','headroom-reclaimed'}
    for slot,nodes in ((1,majority),(2,names)):
        paths |= {f'slot-{slot}-{s}' for s in ('accepted','proved','certified','applied','published','settled')}
        paths |= {f'typed-{slot}-{node}' for node in nodes}
        for node in nodes:
            _,members,packet = c.current(c.inventory(root/f'slot-{slot}-settled'/node))
            b.typed_image(root/f'typed-{slot}-{node}',members[packet['capsule']['application']+'.image'])
    b.selection.layout(root,paths,'mixed covered evidence')
    for stage in root.iterdir():
        if stage.is_dir() and (stage/names[0]).is_dir():
            for node in names:
                files=c.inventory(stage/node); images=[raw for path,raw in files.items() if path.endswith('.image')]
                e.need(len(images)<=7 and all(len(raw)<=64*e.MIB for raw in images),'mixed covered physical image bound'); peak=max(peak,len(images))
    return dict(status='PASS',**p,originalBallots=[2 if n in minority else 3 for n in names],selectedTailBallot=3,
                coveringBallot=5,continuationBallot=6,coveredProtectedContext=not headroom,headroomRefusals=2*len(minority) if headroom else 0,nodePublications=len(names)+len(majority),peakPhysicalImages=peak)


def validate(root):
    root=Path(root); names=[f'{n}-{kind}' for n in (3,4,5) for kind in ('empty','backup')]
    b.selection.layout(root,set(names)|{'receipt.json'},'mixed covered profiles'); results=[]; rows=[]
    for name in names:
        result=clean(root/name); size=int(name[0]); backup=name.endswith('backup')
        same((result['size'],result['backup']),(size,backup),'mixed covered profile location'); results.append(result)
        rows.append(dict(case=name,status='PASS',size=size,backup=backup))
    same(q.read(root/'receipt.json'),dict(schema='gse-v53-covered-context-mixed-v1',status='PASS',cases=rows),'mixed covered receipt')
    return dict(status='PASS',profiles=results,originalFirst=True,publicBootstrap=True,publicRuntime=False,
                freshProcesses=False,powerLoss=False,maximalCapacity=False,independentImageSemantics=False)


VARIANTS = {stage:'admitted exact '+stage+': node-1' for stage in ('contexts','mixed-reaccepted','round-4-prepared','round-4-selected','round-4-installed',
            'mixed-contexts','mixed-floors','mixed-retired','mixed-sources-retired','majority-reaccepted','advanced-selected','covered-installed','floor-released','round-6-settled')}
VARIANTS.update({'force':'mixed covered cleanup force order','observations':'covered actual owner observations','receipt':'mixed covered receipt',
                 'headroom-refused':'admitted exact headroom-refused: node-1','headroom-reaccepted':'admitted exact headroom-reaccepted: node-1',
                 'headroom-reclaimed':'admitted exact headroom-reclaimed: node-1','headroom-outcome':'mixed covered capacity refusal',
                 'headroom-force':'mixed covered headroom force order','headroom-floor':'admitted exact headroom-floors: node-1'})


def qualify(root):
    root=Path(root);result=validate(root); negatives=[]
    for name,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-mixed-covered-negative-') as tmp:
            moved=Path(tmp)/'raw'; shutil.copytree(root,moved);profile=moved/('4-empty' if name.startswith('headroom-') else '3-empty')
            if name=='headroom-outcome':
                path=profile/'headroom-refusals.json';rows=q.read(path);rows[0]['outcome']='INDETERMINATE';path.write_bytes(e.f.canonical(rows))
            elif name=='headroom-force':
                path=profile/'calls.json';rows=q.read(path,8*e.MIB)
                next(v for v in rows if v['node']=='node-1' and v['operation']=='headroom-reclaim')['events'].remove('SOURCE_RETIREMENT_BEFORE_RETURN')
                path.write_bytes(e.f.canonical(rows))
            elif name=='force':
                path=profile/'calls.json'; rows=q.read(path,8*e.MIB)
                next(v for v in rows if v['node']=='node-1' and v['operation']=='install-5')['events'].remove('SETTLED_VOTE_PARENT_FORCED')
                path.write_bytes(e.f.canonical(rows))
            elif name=='observations':
                path=profile/'observations.json';rows=q.read(path);rows.pop();path.write_bytes(e.f.canonical(rows))
            elif name=='receipt':
                path=moved/'receipt.json';rows=q.read(path);rows['cases'][0]['backup']=0;path.write_bytes(e.f.canonical(rows))
            else:(profile/('headroom-floors' if name=='headroom-floor' else name)/'node-1/pending.accept').write_bytes(b'changed')
            try:validate(moved)
            except ValueError as error:e.need(str(error)==reason,'mixed covered wrong negative: '+name+': '+str(error))
            else:raise ValueError('mixed covered mutation accepted: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-mixed-covered-portable-') as tmp:
        moved=Path(tmp)/'raw';shutil.copytree(root,moved);same(validate(moved),result,'mixed covered portable result')
    return dict(**result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
