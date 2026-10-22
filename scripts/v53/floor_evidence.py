"""Original-byte floor-copy replay. Historical membership certificates remain fixtures.

Local and peer generation force order is observed in real owned directories;
this component neither exercises a transport nor authorizes deletion.
"""
from pathlib import Path
from . import current_generation_evidence as c
from . import durable_selection_evidence as d
from . import basis_sources_evidence as s
from . import grant_evidence as g
from .membership_model import need

CUTS=('FLOOR_RESERVED','FLOOR_DIRECTORY_CREATED','FLOOR_PROPOSAL_WRITTEN','FLOOR_PROPOSAL_FORCED',
      'FLOOR_COPY_CREATED','FLOOR_MANIFEST_WRITTEN','FLOOR_MANIFEST_FORCED','FLOOR_IMAGE_WRITTEN','FLOOR_IMAGE_FORCED',
      'FLOOR_MEMBER_WRITTEN','FLOOR_MEMBER_FORCED','FLOOR_COPY_DIRECTORY_FORCED','FLOOR_COPIES_FORCED',
      'FLOOR_AUTHORITY_WRITTEN','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN')


def cases():
    return [dict(name=f'{size}-{through}-{mode}-{cut.lower()}',size=size,through=through,mode=mode,cut=cut)
            for size in (3,4,5) for through in (0,6,7)
            for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]]


def plan(directory,case):
    directory=Path(directory);initial,rows,manifest,data=c.current(directory/'initial',case['size'])
    need([r[0] for r in rows]==['PROMISE'] and rows[0][2]['ballot']['counter']==10,'floor initial promise')
    need(manifest['cut']['index']==case['through'] and manifest['ownedTail'] is None,'floor case cut')
    original=directory/'initial';root=g.f.decode(g.read(original/'root.gsr',16384),'records','ROOT')
    view=manifest['cut']['view'];old=[i['node'] for i in root['initial']];new=old[:-1]+['node-6']
    need(view['old']==(new if case['through']==7 else old) and view['new']==(old if case['through']==0 else new),'floor governing cut')
    inputs=directory/'inputs';peers=[f'node-{i}' for i in range(2,case['size']//2+2)]
    need(inputs.is_dir() and not inputs.is_symlink() and {p.name for p in inputs.iterdir()}==set(peers),'floor peer inventory')
    copies={};references=[]
    for ordinal,node in enumerate(['node-1',*peers]):
        value=dict(manifest,node=node);raw=g.f.encode('records','GENERATION',value)
        actual=original if ordinal==0 else inputs/node
        if ordinal:
            expected=dict(initial)
            replacements={'node.gsr':g.f.encode('records','NODE',dict(root=manifest['root'],identity=root['initial'][ordinal])),
                          'allocator.gsr':g.f.encode('records','ALLOCATOR',dict(root=manifest['root'],node=node,counter=0)),
                          'generations/a/generation.gsr':raw,
                          'selector.gsr':g.f.encode('records','SELECTOR',dict(root=manifest['root'],node=node,generation='a',digest=c.sha(raw)))}
            expected.update({k:dict(bytes=len(v),sha256=c.sha(v)) for k,v in replacements.items()})
            need(s.inventory(actual)==expected,'floor peer original generation')
        members={p.name:g.read(p,64*1024*1024) for p in (actual/'generations/a').iterdir()}
        need(members['generation.gsr']==raw,'floor original manifest')
        copies[c.sha(raw)]=members
        references.append(dict(voter=node,generation=c.sha(raw),catalog=value['catalog'],snapshot=value['application']))
    voters={r['voter'] for r in references}
    need('node-1' in voters and all(len(voters&set(view[k]))>len(view[k])//2 for k in ('old','new')),'floor governing quorum')
    floor=g.f.encode('records','FLOOR',dict(root=manifest['root'],node='node-1',cut=manifest['cut'],sources=references))
    return initial,manifest,peers,copies,floor


def transaction(copies,floor):
    events=[];writes={};directories={};files={}
    def event(name):events.append(dict(event=name,node='node-1'))
    def write(name,raw,prefix):
        writes[name]=len(events);files[name]=raw;event(prefix+'_WRITTEN');event(prefix+'_FORCED')
    event('FLOOR_RESERVED');directories['floor-copies']=len(events);event('FLOOR_DIRECTORY_CREATED')
    write('floor-copies/proposal.gsr',floor,'FLOOR_PROPOSAL')
    for identity,members in sorted(copies.items()):
        prefix='floor-copies/'+identity+'/';directories[prefix[:-1]]=len(events);event('FLOOR_COPY_CREATED')
        write(prefix+'generation.gsr',members['generation.gsr'],'FLOOR_MANIFEST')
        for name,raw in sorted(members.items()):
            if name!='generation.gsr':write(prefix+name,raw,'FLOOR_IMAGE' if name.endswith('.image') else 'FLOOR_MEMBER')
        event('FLOOR_COPY_DIRECTORY_FORCED')
    event('FLOOR_COPIES_FORCED');write('floor-copies/floor.gsr',floor,'FLOOR_AUTHORITY')
    event('FLOOR_PARENT_FORCED');event('FLOOR_BEFORE_RETURN')
    return events,files,writes,directories


def opened(peers,inspect=False):
    def observed(node,events):return [dict(node=node,event=e) for e in events]
    rows=observed('node-1',c.OPEN)
    if inspect:return rows
    rows+=observed('node-1',['FLOOR_COPY_BEFORE_RETURN'])
    for node in peers:rows+=observed(node,[*c.OPEN,'FLOOR_COPY_BEFORE_RETURN'])
    return rows+observed('node-1',['FLOOR_COPY_BEFORE_RETURN'])


def snapshot(path,initial,files,writes,directories,position):
    expected=dict(initial)
    expected.update({name:dict(directory=True) for name,index in directories.items() if index<=position})
    expected.update({name:dict(bytes=len(files[name]),sha256=c.sha(files[name])) for name,index in writes.items() if index<=position})
    actual=s.inventory(Path(path));need(actual==expected,'floor exact physical snapshot')
    need(sum(n.endswith('.image') for n in actual)<=7,'floor shared image capacity')
    return actual


def result(rows,manifest,floor):
    row=rows[-1]
    need(row['floor']==c.sha(floor) and row['cut']==manifest['cut'] and row['networkAck'] is False and row['deletion'] is False,'floor returned binding')


def validate_case(directory,case):
    directory=Path(directory);record=g.a.load(directory/'case.json');need(record['case']==case,'floor case identity')
    need(record['execution']=='private-governing-floor' and record['runtimeEnabled'] is False and record['networkAck'] is False
         and record['deletion'] is False and record['historicalOwnershipVerified'] is False,'floor scope')
    initial,manifest,peers,copies,floor=plan(directory,case);events,files,writes,dirs=transaction(copies,floor)
    order=opened(peers)+events;clean=case['mode']=='clean'
    d.process(directory,record,'init','init',0)
    def state(name,position=len(events)):return snapshot(directory/name,initial,files,writes,dirs,position)
    name='original' if clean else 'resumed';state(name)
    if clean:
        rows=d.process(directory,record,'first','floor',0);need(rows[:-1]==order,'floor force order');result(rows,manifest,floor)
        rows=d.process(directory,record,'duplicate','floor',0);need(rows[:-1]==order,'floor duplicate force order');result(rows,manifest,floor);state('duplicate')
    else:
        rows=d.process(directory,record,'fault','floor',73 if case['mode']=='halt' else -9)
        position=next(i for i,row in enumerate(events) if row['event']==case['cut']);expected=opened(peers)+events[:position+1]
        if case['mode']=='kill':expected.append(dict(event='AWAITING_KILL',cut=case['cut']))
        need(rows==expected,'floor crash cut');state('crash',position)
        rows=d.process(directory,record,'resume','floor',0);need(rows[:-1]==order,'floor recovery force order');result(rows,manifest,floor)
    rows=d.process(directory,record,'inspect','inspect',0);need(rows[:-1]==opened(peers,inspect=True),'floor reopen force order');result(rows,manifest,floor)
    state('final');state('authority')
    processes={'init','first','duplicate','inspect'} if clean else {'init','fault','resume','inspect'}
    snapshots={'initial','original','duplicate','final','authority'} if clean else {'initial','crash','resumed','final','authority'}
    need(set(record['processes'])==processes and {v.name for v in directory.iterdir()}=={'case.json','inputs',*snapshots}|{n+s for n in processes for s in ('.stdout','.stderr')},'floor case inventory')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,networkAck=False,deletion=False)


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={c['name'] for c in cases()},'floor complete cases')
    return dict(status='PASS',execution='private-governing-floor',runtimeEnabled=False,cases=[validate_case(directory/c['name'],c) for c in cases()])
