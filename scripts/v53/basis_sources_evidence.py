"""Independent local original-source retention replay, not remote owned-observation authority."""
import hashlib
from pathlib import Path
from . import grant_evidence as g
from . import source_packet as packet
from . import format_fixture as f
from .membership_model import need

SOURCE_CUTS=('SOURCE_BEFORE_CREATE','SOURCE_CREATED','SOURCE_PACKET_WRITTEN','SOURCE_PACKET_FORCED',
             'SOURCE_IMAGE_WRITTEN','SOURCE_IMAGE_FORCED','SOURCE_FILES_DIRECTORY_FORCED','SOURCE_DIRECTORY_FORCED')
ORDER=g.CUTS[:3]+SOURCE_CUTS+g.CUTS[3:]
CUTS=SOURCE_CUTS+g.CUTS[4:]
PARTIAL={'SOURCE_CREATED','SOURCE_PACKET_WRITTEN','SOURCE_PACKET_FORCED'}


def cases():
    return [dict(name=f'{size}-{mode}-{cut.lower()}',size=size,mode=mode,cut=cut) for size in (3,4,5)
            for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]]


def inventory(path):
    path=Path(path);need(path.is_dir() and not path.is_symlink(),'source directory type')
    result={};count=0
    for p in path.rglob('*'):
        count+=1;need(count<=80,'source evidence file count')
        need(not p.is_symlink() and (p.is_file() or p.is_dir()),'source file type')
        if p.is_file():
            need(p.stat().st_nlink==1 and p.stat().st_size<=64*1024*1024,'source file type/limit')
            sha=hashlib.sha256();size=0
            with p.open('rb') as stream:
                while chunk:=stream.read(65536):
                    size+=len(chunk);need(size<=64*1024*1024,'source file type/limit');sha.update(chunk)
            need(size==p.stat().st_size,'source file changed')
            result[p.relative_to(path).as_posix()]=dict(bytes=size,sha256=sha.hexdigest())
        else:result[p.relative_to(path).as_posix()]=dict(directory=True)
    return result


def state(path,size,partial=False):
    path=Path(path);files=inventory(path);values,rows=g.state(path,size,{'sources'})
    promises={v['basisId']:v for kind,_,v in rows if kind=='PROMISE'}
    need(len(promises)==sum(kind=='PROMISE' for kind,_,_ in rows),'reused source identity')
    bases={v['basisId']:raw for kind,raw,v in rows if kind=='BASIS'}
    need(not partial or not bases,'partial source with completed basis')
    source_dir=path/'sources';need(source_dir.is_dir() and not source_dir.is_symlink(),'source directory type')
    ids={p.name for p in source_dir.iterdir()}
    need(len(ids)<=6 and ids<=promises.keys() and bases.keys()<=ids,'missing or unbound original source')
    images=0;metadata=0;staging=0
    for identity in ids:
        directory=source_dir/identity;need(directory.is_dir() and not directory.is_symlink(),'source directory type')
        names={p.name for p in directory.iterdir()}
        if partial and names==set():continue
        raw=g.read(directory/'source.gscp',g.LIMIT);data=packet.decode(raw);promise=promises[identity]
        need(data['objects'].get(hashlib.sha256(values['root.gsr']).hexdigest())==values['root.gsr'],'retained original root')
        need(data['capsule']['root']==promise['root'] and hashlib.sha256(f.canonical(dict(root=promise['root'],**data['capsule']['cut']['view']))).hexdigest()==promise['view'],'retained promise view')
        if identity in bases:packet.bind(data,bases[identity])
        expected={'source.gscp'}|{h+'.image' for h in data['images']}
        need(names==expected or partial and names=={'source.gscp'},'retained source file inventory')
        for h,s in data['images'].items():
            if partial and names=={'source.gscp'}:continue
            need(files[f'sources/{identity}/{h}.image']==dict(bytes=s,sha256=h),'retained image integrity')
            images+=1;staging+=s
        metadata+=len(raw);staging+=len(raw)
    need(images<=7 and metadata<=6*g.LIMIT and staging<=512*1024*1024,'retained source capacity')
    return files,rows


def partial_refusal(result,cut,identity):
    if cut=='SOURCE_CREATED':
        need(result['type']=='ReplicationException' and result['reason'].startswith('authority member is not a single regular file: ')
             and result['reason'].endswith('/sources/'+identity+'/source.gscp'),'source partial refusal')
    else:need(result['type']=='IllegalArgumentException' and result['reason']=='retained source file inventory','source partial refusal')


def validate_case(directory,case):
    directory=Path(directory);record=g.a.load(directory/'case.json');need(record['case']==case,'source case identity')
    need(record['execution']=='private-retained-grants' and record['runtimeEnabled'] is False and record['remoteOwnershipVerified'] is False,'source runtime scope')
    size,mode,cut=case['size'],case['mode'],case['cut'];clean=mode=='clean';partial=cut in PARTIAL
    initial,empty=state(directory/'initial',size);need(not empty and initial['grants.gsr']['bytes']==0,'source initial journal');g.process(directory,record,'init',0)
    if clean:
        original,rows=state(directory/'original',size);duplicate,again=state(directory/'duplicate',size)
        need(original==duplicate and rows==again,'original source resampled')
        need([k for k,_,_ in rows]==['PROMISE','BASIS'] and rows[-1][2]['cut']['index']==0,'source first grant')
        first=g.process(directory,record,'first',0);need(g.events(first)==list(ORDER),'source force order');g.result(first,rows[-1])
        repeated=g.process(directory,record,'duplicate',0);need(g.events(repeated)==[],'original source resampled');g.result(repeated,rows[-1])
    else:
        fault=g.process(directory,record,'fault',73 if mode=='halt' else -9)
        need(g.events(fault)==list(ORDER[:ORDER.index(cut)+1])+(['AWAITING_KILL'] if mode=='kill' else []),'source crash cut')
        if mode=='kill':need(fault[-1]==dict(event='AWAITING_KILL',cut=cut),'source kill handshake')
        crash,rows=state(directory/'crash',size,partial=partial)
        complete=cut in g.CUTS[4:];need([k for k,_,_ in rows]==(['PROMISE','BASIS'] if complete else ['PROMISE']),'source interrupted journal')
        resume=g.process(directory,record,'resume',0 if complete else 2)
        after,again=state(directory/'resumed',size,partial=partial)
        need(after==crash and again==rows,'recovery rewrote original source');need(g.events(resume)==[],'recovery resampled source')
        if complete:g.result(resume,rows[-1])
        elif not partial:need('incomplete original basis' in resume[-1]['reason'],'source incomplete refusal')
        else:partial_refusal(resume[-1],cut,rows[0][2]['basisId'])
        # Exact crash-stage inventory: the worker cut is after a whole file write, never a fabricated empty response.
        original={k:v for k,v in crash.items() if k.startswith('sources/')}
        if cut=='SOURCE_BEFORE_CREATE':need(not original,'source before-create bytes')
        elif cut=='SOURCE_CREATED':need(len(original)==1 and all('directory' in v for v in original.values()),'source created bytes')
        elif partial:need(len(original)==2,'source partial file inventory')
    prefix=rows;need(all(v['ballot']['counter']==20 for _,_,v in prefix),'source original ballot')
    final,rows=state(directory/'final',size,partial=partial)
    need(rows[:len(prefix)]==prefix,'source original journal replaced')
    if not partial:
        latest=g.process(directory,record,'next',0);need(g.events(latest)==list(ORDER),'source force order');g.result(latest,rows[-1])
        need(rows[-1][2]['ballot']['counter']==21 and rows[-1][2]['cut']['index']==1,'source next grant')
        original=state(directory/('original' if clean else 'crash'),size)[0]
        need(all(final.get(k)==v for k,v in original.items() if k.startswith('sources/')),'original source lost after progress')
        need(len(rows)==len(prefix)+2,'source extra grant history')
    else:need(final==crash,'partial source rewritten')
    need(state(directory/'authority',size,partial=partial)==(final,rows),'source final snapshot')
    names={'init','first','duplicate','next'} if clean else {'init','fault','resume'}|({'next'} if not partial else set())
    snapshots={'initial','original','duplicate','final','authority'} if clean else {'initial','crash','resumed','final','authority'}
    need(set(record['processes'])==names,'source process inventory')
    need({p.name for p in directory.iterdir()}=={'case.json',*snapshots}|{n+s for n in names for s in ('.stdout','.stderr')},'source case inventory')
    for name in snapshots:
        values=inventory(directory/name);need(all(values[n]==initial[n] for n in g.a.NAMES),'source immutable authority changed')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,remoteOwnershipVerified=False)


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={c['name'] for c in cases()},'source complete case inventory')
    return dict(status='PASS',execution='private-retained-grants',runtimeEnabled=False,remoteOwnershipVerified=False,
                cases=[validate_case(directory/c['name'],c) for c in cases()])
