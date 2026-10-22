"""Independent original-source retirement: exact files, journal, force order and crash replay."""
from pathlib import Path
from . import retirement_evidence as r
from . import current_generation_evidence as c
from . import durable_selection_evidence as d
from . import basis_sources_evidence as s
from . import grant_evidence as g
from . import source_packet as p
from .membership_model import need

AUTHORITY='sources.retirement.gsr'
ROTATION='grants.rotation.gsr'
CUTS=('SOURCE_RETIREMENT_CREATED','SOURCE_RETIREMENT_WRITTEN','SOURCE_RETIREMENT_FORCED','SOURCE_RETIREMENT_PARENT_FORCED',
      'JOURNAL_ROTATION_CREATED','JOURNAL_ROTATION_WRITTEN','JOURNAL_ROTATION_FORCED','JOURNAL_ROTATION_RENAMED','JOURNAL_ROTATION_PARENT_FORCED',
      'SOURCE_RETIREMENT_JOURNAL_PRUNED','SOURCE_RETIREMENT_FILE_DELETED','SOURCE_RETIREMENT_FILE_DELETED@2',
      'SOURCE_RETIREMENT_DIRECTORY_DELETED','SOURCE_RETIREMENT_CLEARED','SOURCE_RETIREMENT_BEFORE_RETURN')


def cases():
    return [dict(name=f'{size}-{through}-{mode}-{cut.lower()}',size=size,through=through,mode=mode,cut=cut)
            for size in (3,4,5) for through in (0,6,7)
            for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]
            +[(m,'SOURCE_RETIREMENT_FORCED') for m in ('repeat-halt','repeat-kill')]]


def plan(directory,case):
    directory=Path(directory);initial=directory/'initial';values,rows=g.state(initial,case['size'],{'sources','generations','selector.gsr','floor-copies'})
    root=values['root.gsr'][16:48].hex();definition=g.f.decode(values['root.gsr'],'records','ROOT')
    need([v[0] for v in rows]==['PROMISE','PROMISE','BASIS','PROMISE','BASIS'] and
         [v[2]['ballot']['counter'] for v in rows]==[10,20,20,21,21],'source release initial journal')
    peers=[f'node-{i}' for i in range(2,case['size']//2+2)]
    need((directory/'inputs').is_dir() and not (directory/'inputs').is_symlink() and {v.name for v in (directory/'inputs').iterdir()}==set(peers),'source release peer inventory')
    copies={};references=[];expected=None;own_manifest=None;packet=None;source_files=None
    for ordinal,node in enumerate(['node-1',*peers]):
        owner=initial if ordinal==0 else directory/'inputs'/node
        history=rows if ordinal==0 else g.journal(g.read(owner/'grants.gsr',g.LIMIT),root,node)
        if ordinal:need(len(history)==1 and history[0][1]==rows[0][1],'source release peer promise')
        files,manifest,data=r.generation(owner/'generations/a',root,node,history,case)
        need(data['objects'].get(c.sha(values['root.gsr']))==values['root.gsr'],'source release original root')
        base={n:r.entry(raw) for n,raw in values.items() if n not in ('node.gsr','allocator.gsr','grants.gsr')}
        base.update({'node.gsr':r.entry(g.f.encode('records','NODE',dict(root=root,identity=definition['initial'][ordinal]))),
                     'allocator.gsr':r.entry(g.f.encode('records','ALLOCATOR',dict(root=root,node=node,counter=0))),
                     'grants.gsr':r.entry(b''.join(row[1] for row in history)),
                     'generations':dict(directory=True),'generations/a':dict(directory=True),'sources':dict(directory=True),
                     'selector.gsr':r.entry(g.f.encode('records','SELECTOR',dict(root=root,node=node,generation='a',digest=c.sha(files['generation.gsr']))))})
        base.update({'generations/a/'+n:r.entry(raw) for n,raw in files.items()})
        copies[c.sha(files['generation.gsr'])]=files
        references.append(dict(voter=node,generation=c.sha(files['generation.gsr']),catalog=manifest['catalog'],snapshot=manifest['application']))
        if ordinal==0:expected,own_manifest,packet,source_files=base,manifest,data,{n:raw for n,raw in files.items() if n=='source.gscp' or n.endswith('.image')}
        else:
            need(all(manifest[k]==own_manifest[k] for k in ('root','cut','catalog','application','capsule','promise')),'source release peer cut')
            need(s.inventory(owner)==base,'source release peer exact bytes')
    old=[v['node'] for v in definition['initial']];new=old[:-1]+['node-6'];view=own_manifest['cut']['view'];voters={v['voter'] for v in references}
    need(view['old']==(new if case['through']==7 else old) and view['new']==(old if case['through']==0 else new)
         and all(len(voters&set(view[k]))>len(view[k])//2 for k in ('old','new')),'source release governing quorum')
    for _,raw,basis in (rows[2],rows[4]):
        p.bind(packet,raw);need(basis['accepted'] is None,'source release fixture tail')
        prefix='sources/'+basis['basisId'];expected[prefix]=dict(directory=True)
        expected.update({prefix+'/'+name:r.entry(value) for name,value in source_files.items()})
    need(rows[2][2]['basisId']!=rows[4][2]['basisId'],'source release original identity reused')
    floor=g.f.encode('records','FLOOR',dict(root=root,node='node-1',cut=own_manifest['cut'],sources=references))
    expected.update({'floor-copies':dict(directory=True),'floor-copies/floor.gsr':r.entry(floor),'floor-copies/proposal.gsr':r.entry(floor)})
    for digest,files in copies.items():
        expected['floor-copies/'+digest]=dict(directory=True)
        expected.update({'floor-copies/'+digest+'/'+name:r.entry(raw) for name,raw in files.items()})
    r.snapshot(initial,expected);id=rows[2][2]['basisId'];need(g.a.load(directory/'fixture.json')==dict(basisId=id),'source release fixture identity')
    record=g.f.encode('records','RETIREMENT',dict(root=root,node='node-1',floor=c.sha(floor),selector=expected['selector.gsr']['sha256'],
           files=[dict(path='sources/'+id+'/'+name,size=len(raw),sha256=c.sha(raw)) for name,raw in sorted(source_files.items())]))
    authority=record+rows[1][1]+rows[2][1]+packet['capsuleBytes'];compact=b''.join(row[1] for row in (rows[0],rows[3],rows[4]))
    need(len(authority)<=65536+8192+16384+1024*1024 and len(compact)<=565248,'source release auxiliary capacity')
    return expected,authority,compact,id


def transaction(initial,authority,compact,id):
    state=dict(initial);steps=[];prefix='sources/'+id
    def event(name):steps.append((name,dict(state)))
    if prefix not in state and AUTHORITY not in state:return steps
    if AUTHORITY not in state:state[AUTHORITY]=r.entry(b'');event('SOURCE_RETIREMENT_CREATED')
    state[AUTHORITY]=r.entry(authority);event('SOURCE_RETIREMENT_WRITTEN');event('SOURCE_RETIREMENT_FORCED');event('SOURCE_RETIREMENT_PARENT_FORCED')
    if ROTATION in state or state['grants.gsr']!=r.entry(compact):
        if ROTATION not in state:state[ROTATION]=r.entry(b'');event('JOURNAL_ROTATION_CREATED')
        state[ROTATION]=r.entry(compact);event('JOURNAL_ROTATION_WRITTEN');event('JOURNAL_ROTATION_FORCED')
        state.pop(ROTATION);state['grants.gsr']=r.entry(compact);event('JOURNAL_ROTATION_RENAMED');event('JOURNAL_ROTATION_PARENT_FORCED')
    event('SOURCE_RETIREMENT_JOURNAL_PRUNED')
    for name in sorted(state):
        if name.startswith(prefix+'/'):state.pop(name);event('SOURCE_RETIREMENT_FILE_DELETED')
    if prefix in state:state.pop(prefix);event('SOURCE_RETIREMENT_DIRECTORY_DELETED')
    state.pop(AUTHORITY);event('SOURCE_RETIREMENT_CLEARED');event('SOURCE_RETIREMENT_BEFORE_RETURN');return steps


def result(rows,initial,compact):
    row=rows[-1];need(row['retired'] is True and row['journal']==c.sha(compact) and row['selector']==initial['selector.gsr']['sha256']
       and row['floor']==initial['floor-copies/floor.gsr']['sha256'] and row['networkAck'] is False,'source release returned binding')


def validate_case(directory,case,*,plan_builder=plan,execution="private-source-retirement"):
    directory=Path(directory);receipt=g.a.load(directory/'case.json');need(receipt['case']==case,'source release case identity')
    need(receipt['execution']==execution and all(receipt[k] is False for k in ('runtimeEnabled','historicalOwnershipVerified','networkAck')),'source release scope')
    initial,authority,compact,id=plan_builder(directory,case);d.process(directory,receipt,'init','init',0);processes={'init'};snapshots={'initial','final','authority'}
    def call(label,state,mode='none',cut='none'):
        steps=transaction(state,authority,compact,id);fault=mode!='none';position=r.cut_position(steps,cut) if fault else len(steps)-1
        rows=d.process(directory,receipt,label,'retire',73 if mode=='halt' else -9 if mode=='kill' else 0)
        expected=[dict(event=name) for name in c.OPEN]+[dict(event=name) for name,_ in steps[:position+1]]
        if mode=='kill':expected.append(dict(event='AWAITING_KILL',cut=cut))
        need((rows if fault else rows[:-1])==expected,'source release crash order' if fault else 'source release force order')
        if not fault:result(rows,initial,compact)
        processes.add(label);return steps[position][1] if steps else state
    def snapshot(name,state):snapshots.add(name);r.snapshot(directory/name,state)
    if case['mode']=='clean':final=call('first',initial);snapshot('original',final);snapshot('duplicate',call('duplicate',final))
    else:
        repeated=case['mode'].startswith('repeat-');mode=case['mode'].removeprefix('repeat-')
        crash=call('fault',initial,'halt' if repeated else mode,'SOURCE_RETIREMENT_FILE_DELETED' if repeated else case['cut']);snapshot('crash',crash)
        if repeated:crash=call('recovery-fault',crash,mode,case['cut']);snapshot('recovery-crash',crash)
        final=call('resume',crash);snapshot('resumed',final)
    rows=d.process(directory,receipt,'inspect','inspect',0);need(rows[:-1]==[dict(event=name) for name in c.OPEN],'source release inspect force order')
    result(rows,initial,compact);processes.add('inspect');r.snapshot(directory/'final',final);r.snapshot(directory/'authority',final)
    need(set(receipt['processes'])==processes and {v.name for v in directory.iterdir()}=={'case.json','inputs','fixture.json',*snapshots}|{n+s for n in processes for s in ('.stdout','.stderr')},'source release case inventory')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,networkAck=False)


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={v['name'] for v in cases()},'source release complete cases')
    return dict(status='PASS',execution='private-source-retirement',runtimeEnabled=False,cases=[validate_case(directory/v['name'],v) for v in cases()])
