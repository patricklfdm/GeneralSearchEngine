"""Independent selected-generation/capture binding; no remote ownership or installation claim."""
from pathlib import Path
import hashlib
from . import basis_sources_evidence as s
from . import grant_evidence as g
from . import source_packet as packet
from . import format_fixture as f
from .membership_model import need

OPEN=('CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED')
CAPTURE='CURRENT_BEFORE_CAPTURE'
ORDER=OPEN+(CAPTURE,)+s.ORDER
CUTS=OPEN+(CAPTURE,'GRANT_BEFORE_RETURN')


def cases():
    return [dict(name=f'{size}-{str(tail).lower()}-{mode}-{cut.lower()}',size=size,tail=tail,mode=mode,cut=cut)
            for size in (3,4,5) for tail in (False,True) for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]]


def sha(raw):return hashlib.sha256(raw).hexdigest()


def current(path,size):
    path=Path(path);files,rows=s.state(path,size,extra_names={'selector.gsr','generations'})
    values,_=g.state(path,size,{'sources','selector.gsr','generations'});root=values['root.gsr'][16:48].hex()
    selector=f.decode(g.read(path/'selector.gsr',4096),'records','SELECTOR',root)
    need(selector['node']=='node-1','current selector node');name=selector['generation']
    need({p.name for p in (path/'generations').iterdir()}=={name},'current selected inventory')
    prefix=f'generations/{name}/';directory=path/'generations'/name
    raw=g.read(directory/'generation.gsr',65536);generation=f.decode(raw,'records','GENERATION',root)
    need(sha(raw)==selector['digest'] and generation['generation']==name and generation['node']=='node-1','current selector manifest binding')
    need(generation['basis'] is None and generation['selection'] is None,'unsupported selected installation')
    expected={};previous=None;metadata=len(raw)
    for item in generation['files']:
        file=item['path'];need(previous is None or previous<file,'current file order');previous=file
        need(file in ('source.gscp','promise.gsr','owned-tail.gsr') or len(file)==70 and file.endswith('.image') and all(c in '0123456789abcdef' for c in file[:64]),'current file path')
        maximum=64*1024*1024 if file.endswith('.image') else g.LIMIT if file=='source.gscp' else 8192
        need(0<item['size']<=maximum,'current file capacity')
        expected[file]=dict(bytes=item['size'],sha256=item['sha256'])
        if not file.endswith('.image'):metadata+=item['size']
    need({p.name for p in directory.iterdir()}==set(expected)|{'generation.gsr'},'current file inventory')
    need(all(files.get(prefix+file)==value for file,value in expected.items()),'current file bytes')
    data=packet.decode(g.read(directory/'source.gscp',g.LIMIT));cap=data['capsule']
    need(data['objects'].get(sha(values['root.gsr']))==values['root.gsr'],'current original root')
    need(all(generation[k]==cap[k] for k in ('root','cut','catalog','application')) and generation['capsule']==sha(data['capsuleBytes']),'current capsule binding')
    promise_bytes=g.read(directory/'promise.gsr',8192);promise=f.decode(promise_bytes,'records','PROMISE',root)
    need(sha(promise_bytes)==generation['promise'] and any(k=='PROMISE' and raw==promise_bytes for k,raw,_ in rows),'current promise journal binding')
    need(promise['view']==sha(f.canonical(dict(root=root,**cap['cut']['view']))),'current promise view')
    need(all(v['cut']==cap['cut'] for k,_,v in rows if k=='BASIS'),'current differs from original grant cut')
    names={'source.gscp','promise.gsr'}|{h+'.image' for h in data['images']}
    if generation['ownedTail'] is not None:names.add('owned-tail.gsr')
    need(set(expected)==names,'current materialization inventory')
    for h,size in data['images'].items():need(expected[h+'.image']==dict(bytes=size,sha256=h),'current image binding')
    if generation['ownedTail'] is not None:
        tail=g.read(directory/'owned-tail.gsr',8192)
        need(sha(tail)==generation['ownedTail'] and data['objects'].get(sha(tail))==tail,'current owned tail copy')
        basis=dict(promise,voter='node-1',cut=cap['cut'],capsule=sha(data['capsuleBytes']),inventory=sha(data['indexBytes']),accepted=generation['ownedTail'])
        packet.bind(data,f.encode('records','BASIS',basis))
    need(metadata<=g.LIMIT and sum(p.endswith('.image') for p in files)<=7,'current combined resource capacity')
    return files,rows,generation,data


def returned(rows,expected,generation,root):
    g.result(rows,expected);need(rows[-1]['accepted']==generation['ownedTail'],'current returned tail')
    node=f.decode(g.read(root/'node.gsr',4096),'records','NODE')['identity']
    want=None if generation['ownedTail'] is None else dict(voter='node-1',storage=node['storage'],record=generation['ownedTail'],parent=sha(f.canonical(generation['cut'])))
    need(rows[-1]['ownedTail']==want,'current local ownership observation')


def validate_case(directory,case):
    directory=Path(directory);record=g.a.load(directory/'case.json');need(record['case']==case,'current case identity')
    need(record['execution']=='private-current-generation' and record['runtimeEnabled'] is False and record['remoteOwnershipVerified'] is False,'current runtime scope')
    size,mode,cut=case['size'],case['mode'],case['cut'];clean=mode=='clean';completed=cut=='GRANT_BEFORE_RETURN'
    initial,initial_rows,generation,_=current(directory/'initial',size)
    need([k for k,_,_ in initial_rows]==['PROMISE'] and initial_rows[0][2]['ballot']['counter']==10,'current initial promise')
    need(generation['cut']['index']==1 and (generation['ownedTail'] is not None)==case['tail'],'current fixture profile');g.process(directory,record,'init',0)
    if clean:
        original,old,_,_=current(directory/'original',size);duplicate,again,_,_=current(directory/'duplicate',size)
        need(original==duplicate and old==again,'current duplicate resampled')
        first=g.process(directory,record,'first',0);need(g.events(first)==list(ORDER),'current force order');returned(first,old[-1],generation,directory/'initial')
        repeated=g.process(directory,record,'duplicate',0);need(g.events(repeated)==list(OPEN+(CAPTURE,)),'current duplicate wrote grant');returned(repeated,old[-1],generation,directory/'initial')
    else:
        fault=g.process(directory,record,'fault',73 if mode=='halt' else -9)
        need(g.events(fault)==list(ORDER[:ORDER.index(cut)+1])+(['AWAITING_KILL'] if mode=='kill' else []),'current crash cut')
        if mode=='kill':need(fault[-1]==dict(event='AWAITING_KILL',cut=cut),'current kill handshake')
        crash,old,_,_=current(directory/'crash',size)
        need(len(old)==(3 if completed else 1),'current crash journal')
        if not completed:need(crash==initial,'current open changed authority')
        resume=g.process(directory,record,'resume',0);need(g.events(resume)==list(OPEN+(CAPTURE,) if completed else ORDER),'current resume force order')
        resumed,old,_,_=current(directory/'resumed',size);returned(resume,old[-1],generation,directory/'initial')
        if completed:need(resumed==crash,'current completed grant resampled')
    need([k for k,_,_ in old]==['PROMISE','PROMISE','BASIS'] and old[-1][2]['ballot']['counter']==20,'current first grant')
    final,rows,_,_=current(directory/'final',size)
    need(len(rows)==5 and rows[:3]==old and rows[-1][2]['ballot']['counter']==21,'current next history')
    next_result=g.process(directory,record,'next',0);need(g.events(next_result)==list(ORDER),'current force order');returned(next_result,rows[-1],generation,directory/'initial')
    need(current(directory/'authority',size)==current(directory/'final',size),'current final snapshot')
    names={'init','first','duplicate','next'} if clean else {'init','fault','resume','next'}
    snapshots={'initial','original','duplicate','final','authority'} if clean else {'initial','crash','resumed','final','authority'}
    need(set(record['processes'])==names and {p.name for p in directory.iterdir()}=={'case.json',*snapshots}|{n+s for n in names for s in ('.stdout','.stderr')},'current case inventory')
    for snapshot in snapshots:
        files,_,_,_=current(directory/snapshot,size)
        need(all(files[n]==v for n,v in initial.items() if n!='grants.gsr'),'current selected files changed')
    old_files=s.inventory(directory/('original' if clean else 'resumed'))
    need(all(final.get(n)==v for n,v in old_files.items() if n.startswith('sources/')),'current original source lost')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,remoteOwnershipVerified=False)


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={c['name'] for c in cases()},'current complete case inventory')
    return dict(status='PASS',execution='private-current-generation',runtimeEnabled=False,remoteOwnershipVerified=False,
                cases=[validate_case(directory/c['name'],c) for c in cases()])
