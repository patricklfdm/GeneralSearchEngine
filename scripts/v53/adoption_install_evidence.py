"""Original-first physical replay for certificate-fenced membership installation.

Remote force ownership is still conditional. Local journal, generations, selector,
cut/force order and subsequent new-view grant are checked from retained bytes.
"""
from pathlib import Path
from . import adoption_fence_evidence as a
from . import generation_install_evidence as i
from . import current_generation_evidence as c
from . import durable_selection_evidence as d
from . import basis_sources_evidence as s
from . import grant_evidence as g
from . import source_packet as p
from .membership_model import need

PREFIX=('ADOPTION_INSTALL_VALIDATED','PROMISE_BEFORE_WRITE','PROMISE_WRITTEN','PROMISE_FORCED','ADOPTION_INSTALL_FENCED')
CUTS=PREFIX+i.CUTS[:-1]+('ADOPTION_INSTALL_BEFORE_RETURN',)


def cases():
    return [dict(name=f'{size}-{through}-{mode}-{cut.lower()}',size=size,through=through,mode=mode,cut=cut)
            for size in (3,4,5) for through in (6,7) for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]]


def plan(directory,initial,case):
    directory=Path(directory);fence,value=a.original_fence(directory,initial,case)
    raw=g.read(directory/'inputs/source.gscp',g.LIMIT);data=p.decode(raw);cap=data['capsule'];objects=data['objects']
    certificates=[objects[row['certificate']] for row in cap['items'] if row['kind']=='MEMBERSHIP']
    certificate=max(enumerate(certificates),key=lambda row:(g.order(g.f.decode(row[1],'records','CERTIFICATE')['ballot']),row[0]))[1]
    files={'source.gscp':raw,'promise.gsr':fence,'adopted-certificate.gsr':certificate,
           **{h+'.image':g.read(directory/'inputs'/(h+'.image'),count) for h,count in data['images'].items()}}
    manifest=dict(root=initial['root'],node='node-1',generation='b',cut=cap['cut'],catalog=cap['catalog'],application=cap['application'],
                  capsule=c.sha(data['capsuleBytes']),promise=c.sha(fence),basis=None,selection=None,ownedTail=None,
                  files=[dict(path=name,size=len(raw),sha256=c.sha(raw)) for name,raw in sorted(files.items())])
    files['generation.gsr']=g.f.encode('records','GENERATION',manifest)
    selector=g.f.encode('records','SELECTOR',dict(root=initial['root'],node='node-1',generation='b',digest=c.sha(files['generation.gsr'])))
    return fence,value,files,selector,manifest,data


def snapshot(path,case,initial,original,fence,files,selector,position,events,writes,written=True,advanced=False):
    path=Path(path);extras={'selector.gsr','generations'}|({'selector.pending.gsr'} if (path/'selector.pending.gsr').exists() else set())
    actual,rows=s.state(path,case['size'],extra_names=extras)
    prefix=original+([('PROMISE',fence,g.f.decode(fence,'records','PROMISE'))] if written else [])
    need(rows[:len(prefix)]==prefix and (advanced or rows==prefix),'adopt install journal changed')
    expected=dict(initial);journal=b''.join(r[1] for r in prefix);expected['grants.gsr']=dict(bytes=len(journal),sha256=c.sha(journal))
    if position>=1:expected['generations/b']=dict(directory=True)
    for name,index in writes.items():
        if position>=index:expected['generations/b/'+name]=dict(bytes=len(files[name]),sha256=c.sha(files[name]))
    if position>=events.index('INSTALL_SELECTOR_RENAMED'):expected['selector.gsr']=dict(bytes=len(selector),sha256=c.sha(selector))
    elif position>=events.index('INSTALL_SELECTOR_WRITTEN'):expected['selector.pending.gsr']=dict(bytes=len(selector),sha256=c.sha(selector))
    if advanced:
        need([r[0] for r in rows[len(prefix):]]==['PROMISE','BASIS'] and rows[-1][2]['ballot']['counter']==50,'adopt install next grant')
        basis=rows[-1];data=p.decode(files['source.gscp']);p.bind(data,basis[1]);identity=basis[2]['basisId']
        need(basis[2]['cut']==data['capsule']['cut'] and basis[2]['view']==c.sha(g.f.canonical(dict(root=basis[2]['root'],**basis[2]['cut']['view']))),'adopt install obsolete grant')
        raw=b''.join(r[1] for r in rows);expected['grants.gsr']=dict(bytes=len(raw),sha256=c.sha(raw));expected['sources/'+identity]=dict(directory=True)
        for name in ['source.gscp',*[h+'.image' for h in data['images']]]:
            expected['sources/'+identity+'/'+name]=dict(bytes=len(files[name]),sha256=c.sha(files[name]))
    need(actual==expected,'adopt install physical snapshot')
    need(sum(name.endswith('.image') for name in actual)<=7,'adopt install shared image count')
    return actual,rows


def validate_case(directory,case):
    directory=Path(directory);record=g.a.load(directory/'case.json');need(record['case']==case,'adopt install case identity')
    need(record['execution']=='private-adoption-install' and record['runtimeEnabled'] is False and record['remoteOwnershipVerified'] is False
         and record['networkAck'] is False,'adopt install scope')
    initial,rows,generation,_=c.current(directory/'initial',case['size']);need([r[0] for r in rows]==['PROMISE','PROMISE','BASIS'] and generation['cut']['index']==0,'adopt install initial authority')
    fence,value,files,selector,manifest,_=plan(directory,generation,case);events,writes=i.transaction(files)
    order=list(c.OPEN+PREFIX)+events+list(c.OPEN)+['ADOPTION_INSTALL_BEFORE_RETURN'];clean=case['mode']=='clean'
    d.process(directory,record,'init','init',0)
    def state(name,position=len(events),written=True,advanced=False):return snapshot(directory/name,case,initial,rows,fence,files,selector,position,events,writes,written,advanced)
    state('original' if clean else 'resumed')
    if clean:
        stdout=d.process(directory,record,'first','adopt',0);need(g.events(stdout)==order,'adopt install force order');i.result(stdout,files,manifest)
        stdout=d.process(directory,record,'duplicate','adopt',0);need(g.events(stdout)==list(c.OPEN),'adopt install duplicate wrote');i.result(stdout,files,manifest);state('duplicate')
    else:
        cut=case['cut'];stdout=d.process(directory,record,'fault','adopt',73 if case['mode']=='halt' else -9)
        need(g.events(stdout)==order[:order.index(cut)+1]+(['AWAITING_KILL'] if case['mode']=='kill' else []),'adopt install crash cut')
        if case['mode']=='kill':need(stdout[-1]==dict(event='AWAITING_KILL',cut=cut),'adopt install kill handshake')
        written=order.index(cut)>=order.index('PROMISE_WRITTEN');position=events.index(cut) if cut in events else len(events) if cut=='ADOPTION_INSTALL_BEFORE_RETURN' else -1
        state('crash',position,written)
        stdout=d.process(directory,record,'resume','adopt',0)
        expected=list(c.OPEN) if position>=events.index('INSTALL_SELECTOR_RENAMED') else [event for event in order if not written or event not in ('PROMISE_BEFORE_WRITE','PROMISE_WRITTEN','PROMISE_FORCED')]
        need(g.events(stdout)==expected,'adopt install recovery force order');i.result(stdout,files,manifest)
    stdout=d.process(directory,record,'same','same',2);need(g.events(stdout)==list(c.OPEN+(c.CAPTURE,)) and stdout[-1]['reason']=='duplicate grant changed configuration','adopt install same-ballot refusal');state('same')
    _,history=state('final',advanced=True);stdout=d.process(directory,record,'next','advance',0)
    need(g.events(stdout)==list(c.ORDER) and stdout[-1]['basis']==c.sha(history[-1][1]) and stdout[-1]['cut']==manifest['cut'],'adopt install fresh capture')
    state('authority',advanced=True)
    processes={'init','first','duplicate','same','next'} if clean else {'init','fault','resume','same','next'}
    snapshots={'initial','original','duplicate','same','final','authority'} if clean else {'initial','crash','resumed','same','final','authority'}
    need(set(record['processes'])==processes and {v.name for v in directory.iterdir()}=={'case.json','inputs',*snapshots}|{n+s for n in processes for s in ('.stdout','.stderr')},'adopt install case inventory')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,networkAck=False)


def validate(directory):
    directory=Path(directory);need({v.name for v in directory.iterdir()}=={c['name'] for c in cases()},'adopt install complete cases')
    return dict(status='PASS',execution='private-adoption-install',runtimeEnabled=False,cases=[validate_case(directory/c['name'],c) for c in cases()])
