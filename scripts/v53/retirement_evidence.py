"""Independent byte/inventory replay of local floor-authorized retirement.

Historical membership edges are fixtures. This does not qualify network ownership,
public service, floor rotation or power loss.
"""
from pathlib import Path
from . import current_generation_evidence as c
from . import durable_selection_evidence as d
from . import basis_sources_evidence as s
from . import grant_evidence as g
from . import source_packet as p
from .membership_model import need
from . import selected_sources_evidence as selected_originals

CUTS=('RETIREMENT_OLD_FILES_FORCED','RETIREMENT_RESERVED','RETIREMENT_CREATED','RETIREMENT_PROPOSAL_WRITTEN',
      'RETIREMENT_PROPOSAL_FORCED','RETIREMENT_SOURCE_CREATED','RETIREMENT_MANIFEST_WRITTEN','RETIREMENT_MANIFEST_FORCED',
      'RETIREMENT_IMAGE_WRITTEN','RETIREMENT_IMAGE_FORCED','RETIREMENT_MEMBER_WRITTEN','RETIREMENT_MEMBER_FORCED',
      'RETIREMENT_SOURCE_FORCED','RETIREMENT_AUTHORITY_WRITTEN','RETIREMENT_AUTHORITY_FORCED','RETIREMENT_PARENT_FORCED',
      'RETIREMENT_DELETE_VALIDATED','RETIREMENT_FILE_DELETED','RETIREMENT_DIRECTORY_DELETED',
      'RETIREMENT_SAVED_FILE_DELETED','RETIREMENT_SAVED_DIRECTORY_DELETED','RETIREMENT_PROPOSAL_CLEARED',
      'RETIREMENT_AUTHORITY_CLEARED','RETIREMENT_CLEARED','RETIREMENT_BEFORE_RETURN',
      'RETIREMENT_FILE_DELETED@2','RETIREMENT_FILE_DELETED@4',
      'RETIREMENT_SAVED_FILE_DELETED@2','RETIREMENT_SAVED_FILE_DELETED@4')


def cases():
    return [dict(name=f'{size}-{through}-{mode}-{cut.lower()}',size=size,through=through,mode=mode,cut=cut)
            for size in (3,4,5) for through in (0,6,7)
            for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]
                +[(m,'RETIREMENT_AUTHORITY_RESEALED') for m in ('repeat-halt','repeat-kill')]]


def entry(raw):return dict(bytes=len(raw),sha256=c.sha(raw))


def members(path):
    inventory=s.inventory(path)
    need(all('directory' not in row for row in inventory.values()),'retirement generation nested path')
    return {name:g.read(path/name,64*1024*1024) for name in inventory}


def generation(path,root,node,rows,case):
    files=members(path);value=g.f.decode(files['generation.gsr'],'records','GENERATION',root)
    need(value['node']==node and value['generation']=='a' and value['cut']['index']==case['through']
         and all(value[k] is None for k in ('basis','selection','ownedTail')),'retirement original generation profile')
    need(value['files']==[dict(path=n,size=len(raw),sha256=c.sha(raw)) for n,raw in sorted(files.items()) if n!='generation.gsr'],
         'retirement original generation inventory')
    packet=p.decode(files['source.gscp']);cap=packet['capsule']
    need(all(value[k]==cap[k] for k in ('root','cut','catalog','application')) and value['capsule']==c.sha(packet['capsuleBytes']),
         'retirement original capsule binding')
    need(files['promise.gsr']==rows[0][1] and value['promise']==c.sha(rows[0][1]),'retirement original promise')
    need(set(files)=={'generation.gsr','source.gscp','promise.gsr'}|{h+'.image' for h in packet['images']},'retirement original member inventory')
    need(all(entry(files[h+'.image'])==dict(bytes=size,sha256=h) for h,size in packet['images'].items()),'retirement original image')
    need(sum(len(raw) for n,raw in files.items() if not n.endswith('.image'))<=g.LIMIT,'retirement generation capacity')
    return files,value,packet


def plan(directory,case,initial_name="initial"):
    directory=Path(directory);initial=directory/initial_name;values,rows=g.state(initial,case['size'],{'sources','generations','selector.gsr','floor-copies'})
    root=values['root.gsr'][16:48].hex();definition=g.f.decode(values['root.gsr'],'records','ROOT')
    need([r[0] for r in rows]==['PROMISE','PROMISE','BASIS','SELECTED'],'retirement initial journal')
    peers=[f'node-{i}' for i in range(2,case['size']//2+2)]
    need((directory/'inputs').is_dir() and not (directory/'inputs').is_symlink()
         and {v.name for v in (directory/'inputs').iterdir()}==set(peers),'retirement peer inventory')
    copies={};references=[];basis_refs=[];basis_frames=[];original=None;expected_local=None;old_manifest=None
    for ordinal,node in enumerate(['node-1',*peers]):
        owner=initial if ordinal==0 else directory/'inputs'/node
        inventory=s.inventory(owner)
        history=rows if ordinal==0 else g.journal(g.read(owner/'grants.gsr',g.LIMIT),root,node)
        need([v[0] for v in history]==(['PROMISE','PROMISE','BASIS','SELECTED'] if ordinal==0 else ['PROMISE','PROMISE','BASIS'])
             and [v[2]['ballot']['counter'] for v in history[:3]]==[10,100,100],'retirement owner journal')
        files,manifest,packet=generation(owner/'generations/a',root,node,history,case)
        need(packet['objects'].get(c.sha(values['root.gsr']))==values['root.gsr'],'retirement original root')
        basis=history[2];p.bind(packet,basis[1]);need(basis[2]['accepted'] is None and basis[2]['ballot']==rows[2][2]['ballot'],'retirement original grant')
        basis_refs.append(dict(voter=node,basisId=basis[2]['basisId'],basisDigest=c.sha(basis[1])));basis_frames.append(basis[1])
        copies[c.sha(files['generation.gsr'])]=files
        references.append(dict(voter=node,generation=c.sha(files['generation.gsr']),catalog=manifest['catalog'],snapshot=manifest['application']))
        expected={n:entry(raw) for n,raw in values.items() if n not in ('node.gsr','allocator.gsr','grants.gsr')}
        expected.update({'node.gsr':entry(g.f.encode('records','NODE',dict(root=root,identity=definition['initial'][ordinal]))),
                         'allocator.gsr':entry(g.f.encode('records','ALLOCATOR',dict(root=root,node=node,counter=0))),
                         'grants.gsr':entry(b''.join(r[1] for r in history)),
                         'generations':dict(directory=True),'generations/a':dict(directory=True),'sources':dict(directory=True),
                         'sources/'+basis[2]['basisId']:dict(directory=True)})
        expected.update({'generations/a/'+n:entry(raw) for n,raw in files.items()})
        expected.update({'sources/'+basis[2]['basisId']+'/'+n:entry(files[n]) for n in ['source.gscp',*[h+'.image' for h in packet['images']]]})
        if ordinal==0:original,old_manifest,expected_local=files,manifest,expected
        else:
            need(all(manifest[k]==old_manifest[k] for k in ('root','cut','catalog','application','capsule','promise')),'retirement peer cut')
            expected['selector.gsr']=entry(g.f.encode('records','SELECTOR',dict(root=root,node=node,generation='a',digest=c.sha(files['generation.gsr']))))
            need(inventory==expected,'retirement peer original bytes')
    view=old_manifest['cut']['view'];old=[i['node'] for i in definition['initial']];new=old[:-1]+['node-6']
    need(view['old']==(new if case['through']==7 else old) and view['new']==(old if case['through']==0 else new),'retirement governing view')
    voters={r['voter'] for r in references}
    need(all(len(voters&set(view[k]))>len(view[k])//2 for k in ('old','new')),'retirement governing quorum')
    selected=rows[-1]
    need(selected[2]['sources']==basis_refs and selected[2]['cut']==old_manifest['cut'] and selected[2]['nextEntry'] is None,'retirement original selection')
    # Equal complete sources select exactly this packet; rebuild the installed generation.
    active={n:raw for n,raw in original.items() if n!='generation.gsr'}
    active.update({'promise.gsr':rows[1][1],'basis.gsr':rows[2][1],'selected.gsr':selected[1]})
    if selected_originals.recorded_mode(directory):
        source_frames=b''.join(basis_frames);selected_originals.cuts(source_frames,selected[2])
        active[selected_originals.FILE]=source_frames
    manifest=dict(old_manifest,generation='b',promise=c.sha(rows[1][1]),basis=c.sha(rows[2][1]),selection=c.sha(selected[1]),
                  files=[dict(path=n,size=len(raw),sha256=c.sha(raw)) for n,raw in sorted(active.items())])
    active['generation.gsr']=g.f.encode('records','GENERATION',manifest)
    selector=g.f.encode('records','SELECTOR',dict(root=root,node='node-1',generation='b',digest=c.sha(active['generation.gsr'])))
    floor=g.f.encode('records','FLOOR',dict(root=root,node='node-1',cut=old_manifest['cut'],sources=references))
    expected_local.update({'generations/b':dict(directory=True),'selector.gsr':entry(selector),'floor-copies':dict(directory=True),
                           'floor-copies/proposal.gsr':entry(floor),'floor-copies/floor.gsr':entry(floor)})
    expected_local.update({'generations/b/'+n:entry(raw) for n,raw in active.items()})
    for digest,files in copies.items():
        expected_local['floor-copies/'+digest]=dict(directory=True)
        expected_local.update({'floor-copies/'+digest+'/'+n:entry(raw) for n,raw in files.items()})
    need(s.inventory(initial)==expected_local,'retirement initial physical authority')
    record=g.f.encode('records','RETIREMENT',dict(root=root,node='node-1',floor=c.sha(floor),selector=c.sha(selector),
            files=[dict(path='generations/a/'+n,size=len(raw),sha256=c.sha(raw)) for n,raw in sorted(original.items())]))
    return expected_local,original,record,floor,selector


def transaction(state,original,record):
    """Predict one call from a previously predicted crash state, not its observed log."""
    state=dict(state);steps=[]
    def event(name):steps.append((name,dict(state)))
    def directory(name,point):state[name]=dict(directory=True);event(point)
    def write(name,raw,point):state[name]=entry(raw);event(point+'_WRITTEN');event(point+'_FORCED')
    def remove(name,point):state.pop(name);event(point)
    if 'generations/a' not in state and 'retirement/retirement.gsr' not in state:
        if 'retirement' in state:remove('retirement','RETIREMENT_CLEARED')
        return steps,None
    if 'retirement/retirement.gsr' not in state:
        event('RETIREMENT_OLD_FILES_FORCED');event('RETIREMENT_RESERVED');directory('retirement','RETIREMENT_CREATED')
        write('retirement/proposal.gsr',record,'RETIREMENT_PROPOSAL');directory('retirement/source','RETIREMENT_SOURCE_CREATED')
        write('retirement/source/generation.gsr',original['generation.gsr'],'RETIREMENT_MANIFEST')
        for name,raw in sorted(original.items()):
            if name!='generation.gsr':write('retirement/source/'+name,raw,'RETIREMENT_IMAGE' if name.endswith('.image') else 'RETIREMENT_MEMBER')
        event('RETIREMENT_SOURCE_FORCED');write('retirement/retirement.gsr',record,'RETIREMENT_AUTHORITY');event('RETIREMENT_PARENT_FORCED')
    else:event('RETIREMENT_AUTHORITY_RESEALED')
    if 'generations/a' in state:
        event('RETIREMENT_DELETE_VALIDATED')
        for name in sorted(original):
            if 'generations/a/'+name in state:remove('generations/a/'+name,'RETIREMENT_FILE_DELETED')
        remove('generations/a','RETIREMENT_DIRECTORY_DELETED')
    for name in sorted(original):
        if 'retirement/source/'+name in state:remove('retirement/source/'+name,'RETIREMENT_SAVED_FILE_DELETED')
    if 'retirement/source' in state:remove('retirement/source','RETIREMENT_SAVED_DIRECTORY_DELETED')
    if 'retirement/proposal.gsr' in state:remove('retirement/proposal.gsr','RETIREMENT_PROPOSAL_CLEARED')
    remove('retirement/retirement.gsr','RETIREMENT_AUTHORITY_CLEARED');remove('retirement','RETIREMENT_CLEARED');event('RETIREMENT_BEFORE_RETURN')
    return steps,c.sha(record)


def cut_position(steps,cut):
    parts=cut.split('@');point=parts[0];ordinal=int(parts[1]) if len(parts)==2 else 1
    indices=[i for i,(name,_) in enumerate(steps) if name==point]
    need(0<ordinal<=len(indices),'retirement absent crash cut');return indices[ordinal-1]


def snapshot(path,expected):
    need(s.inventory(path)==expected,'retirement exact physical snapshot')
    need(sum(n.endswith('.image') for n in expected)<=7,'retirement shared image count')
    need(sum(n.startswith('sources/') and n.count('/')==1 for n in expected)
         +sum(n.startswith('floor-copies/') and n.count('/')==1 and 'directory' in v for n,v in expected.items())
         +int('retirement/source' in expected)<=6,'retirement shared source count')


def result(rows,floor,selector,retirement):
    row=rows[-1]
    need(row['floor']==c.sha(floor) and row['selector']==c.sha(selector) and row['retirement']==retirement
         and row['networkAck'] is False,'retirement returned binding')


def validate_case(directory,case):
    directory=Path(directory);record=g.a.load(directory/'case.json');need(record['case']==case,'retirement case identity')
    need(record['execution']=='private-governing-retirement' and all(record[k] is False for k in ('runtimeEnabled','historicalOwnershipVerified','networkAck')),
         'retirement scope')
    initial,original,authority,floor,selector=plan(directory,case);d.process(directory,record,'init','init',0)
    processes={'init'};snapshots={'initial','final','authority'}
    def call(label,state,mode='none',cut='none'):
        steps,returned=transaction(state,original,authority);fault=mode!='none'
        position=cut_position(steps,cut) if fault else len(steps)-1
        rows=d.process(directory,record,label,'retire',73 if mode=='halt' else -9 if mode=='kill' else 0)
        expected=[dict(event=name) for name in c.OPEN]+[dict(event=name) for name,_ in steps[:position+1]]
        if mode=='kill':expected.append(dict(event='AWAITING_KILL',cut=cut))
        need((rows if fault else rows[:-1])==expected,'retirement crash order' if fault else 'retirement force order')
        if not fault:result(rows,floor,selector,returned)
        processes.add(label);return steps[position][1] if steps else state
    def state(name,expected):snapshots.add(name);snapshot(directory/name,expected)
    if case['mode']=='clean':
        final=call('first',initial);state('original',final);state('duplicate',call('duplicate',final))
    else:
        repeated=case['mode'].startswith('repeat-');mode=case['mode'].removeprefix('repeat-')
        crash=call('fault',initial,'halt' if repeated else mode,'RETIREMENT_FILE_DELETED@2' if repeated else case['cut']);state('crash',crash)
        if repeated:
            crash=call('recovery-fault',crash,mode,case['cut']);state('recovery-crash',crash)
        final=call('resume',crash);state('resumed',final)
    rows=d.process(directory,record,'inspect','inspect',0);need(rows[:-1]==[dict(event=name) for name in c.OPEN],'retirement inspect force order')
    result(rows,floor,selector,None);processes.add('inspect')
    snapshot(directory/'final',final);snapshot(directory/'authority',final)
    need(set(record['processes'])==processes and {v.name for v in directory.iterdir()}=={'case.json','inputs',*snapshots}|{n+s for n in processes for s in ('.stdout','.stderr')},
         'retirement case inventory')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,networkAck=False)


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={c['name'] for c in cases()},'retirement complete cases')
    return dict(status='PASS',execution='private-governing-retirement',runtimeEnabled=False,cases=[validate_case(directory/c['name'],c) for c in cases()])
