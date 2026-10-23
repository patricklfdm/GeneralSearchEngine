"""Independent exact-plan/force replay for private local generation installation.

Remote authenticated history remains a fixture input, not a physical remote vote.
The candidate is recomputed from original inputs, never trusted from its manifest.
"""
from pathlib import Path
import struct
from . import current_generation_evidence as c
from . import durable_selection_evidence as d
from . import basis_sources_evidence as s
from . import grant_evidence as g
from . import source_packet as p
from .membership_model import need
from . import selected_sources_evidence as selected_originals

CUTS=('INSTALL_RESERVED','INSTALL_DIRECTORY_CREATED','INSTALL_MANIFEST_WRITTEN','INSTALL_MANIFEST_FORCED',
      'INSTALL_MEMBER_WRITTEN','INSTALL_MEMBER_FORCED','INSTALL_IMAGE_WRITTEN','INSTALL_IMAGE_FORCED',
      'INSTALL_GENERATION_FORCED','INSTALL_SELECTOR_WRITTEN','INSTALL_SELECTOR_FORCED','INSTALL_SELECTOR_RENAMED',
      'INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN')


def cases():
    return [dict(name=f'{size}-{str(tail).lower()}-{mode}-{cut.lower()}',size=size,tail=tail,mode=mode,cut=cut)
            for size in (3,4,5) for tail in (False,True) for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]]


def packet_bytes(capsule,objects,images):
    index=g.f.canonical(dict(schema='gse-membership-source-index/1.3',objects=[dict(sha256=h,bytes=len(v)) for h,v in sorted(objects.items())],
                            images=[dict(sha256=h,bytes=v) for h,v in sorted(images.items())]))
    cap=dict(capsule,inventory=c.sha(index));cap=g.f.encode('records','CAPSULE',cap)
    body=b''.join(struct.pack('>I',len(v))+v for v in (cap,index))+b''.join(v for _,v in sorted(objects.items()))
    header=struct.pack('>4sHHHHI',b'GSCP',1,3,0,0,len(body))
    return header+bytes.fromhex(c.sha(header+body))+body


def plan(directory,initial_rows,initial_generation,case,selected_source_frames=False):
    directory=Path(directory);root=initial_generation['root'];inputs=directory/'inputs';size=case['size']
    promise=next(r for r in initial_rows if r[0]=='PROMISE' and r[2]['ballot']['counter']==20)
    basis=next(r for r in initial_rows if r[0]=='BASIS');selected=next(r for r in initial_rows if r[0]=='SELECTED')
    local=p.decode(g.read(directory/'initial/sources'/basis[2]['basisId']/'source.gscp',g.LIMIT))
    sources=[(basis[1],basis[2],local)];names=set();images={}
    for node in range(2,2+size//2):
        name=f'node-{node}';names|={name+'.basis',name+'.gscp'}
        raw=g.read(inputs/(name+'.basis'),16384);value=g.f.decode(raw,'records','BASIS',root)
        data=p.decode(g.read(inputs/(name+'.gscp'),g.LIMIT));p.bind(data,raw)
        need(value['voter']==name and value['ballot']==basis[2]['ballot'] and value['view']==basis[2]['view'],'install remote identity')
        need(value['cut']['index']==1 and data['objects'].get(c.sha(g.read(directory/'initial/root.gsr',16384)))==g.read(directory/'initial/root.gsr',16384),'install remote root/cut')
        sources.append((raw,value,data));images.update(data['images'])
    names|={h+'.image' for h in images}
    need(inputs.is_dir() and not inputs.is_symlink() and {v.name for v in inputs.iterdir()}==names,'install input inventory')
    image_bytes={h:g.read(inputs/(h+'.image'),count) for h,count in images.items()}
    need(all(len(image_bytes[h])==count and c.sha(image_bytes[h])==h for h,count in images.items()),'install input image')
    refs=[dict(voter=b['voter'],basisId=b['basisId'],basisDigest=c.sha(raw)) for raw,b,_ in sources]
    need(len({b['basisId'] for _,b,_ in sources})==len(sources) and selected[2]['sources']==refs,'install original selection references')
    longest=max(sources,key=lambda s:s[1]['cut']['index']);cut=longest[1]['cut'];chosen=None
    need(all(b['cut']==cut for _,b,_ in sources if b['cut']['index']==cut['index']),'install conflicting longest cut')
    for _,b,data in sources:
        if b['accepted'] is None:continue
        accept=g.f.decode(data['objects'][b['accepted']],'records','ACCEPT',root)
        if accept['index']<=cut['index']:continue
        need(accept['index']==cut['index']+1,'install next-slot gap')
        if chosen is None or g.order(accept['ballot'])>g.order(chosen[0]['ballot']):chosen=(accept,data,b['accepted'])
        elif g.order(accept['ballot'])==g.order(chosen[0]['ballot']):need(accept['entry']==chosen[0]['entry'],'install conflicting tail')
    need(selected[2]['cut']==cut and selected[2]['nextEntry']==(None if chosen is None else chosen[0]['entry']),'install selected parent/tail')
    need((chosen is not None)==case['tail'],'install tail profile')
    objects=dict(longest[2]['objects']);owned=None
    if chosen is not None:
        accept,data,owned=chosen;entry=g.f.decode(data['objects'][accept['entry']],'records','ENTRY',root)
        for h in (owned,accept['entry'],entry['payload']):objects[h]=data['objects'][h]
    source=packet_bytes(longest[2]['capsule'],objects,longest[2]['images']);data=p.decode(source)
    synthetic=dict(promise[2],voter='node-1',cut=cut,capsule=c.sha(data['capsuleBytes']),inventory=c.sha(data['indexBytes']),accepted=owned)
    p.bind(data,g.f.encode('records','BASIS',synthetic))
    files={'source.gscp':source,'promise.gsr':promise[1],'basis.gsr':basis[1],'selected.gsr':selected[1],
           **{h+'.image':image_bytes[h] for h in data['images']}}
    if selected_source_frames:
        originals=b''.join(raw for raw,_,_ in sources);selected_originals.cuts(originals,selected[2])
        files[selected_originals.FILE]=originals
    if owned is not None:files['owned-tail.gsr']=objects[owned]
    cap=data['capsule'];manifest=dict(root=root,node='node-1',generation='b',cut=cut,application=cap['application'],catalog=cap['catalog'],
        capsule=c.sha(data['capsuleBytes']),promise=c.sha(promise[1]),basis=c.sha(basis[1]),selection=c.sha(selected[1]),ownedTail=owned,
        files=[dict(path=name,size=len(raw),sha256=c.sha(raw)) for name,raw in sorted(files.items())])
    files['generation.gsr']=g.f.encode('records','GENERATION',manifest)
    selector=g.f.encode('records','SELECTOR',dict(root=root,node='node-1',generation='b',digest=c.sha(files['generation.gsr'])))
    return files,selector,manifest,data


def transaction(files):
    events=['INSTALL_RESERVED','INSTALL_DIRECTORY_CREATED','INSTALL_MANIFEST_WRITTEN','INSTALL_MANIFEST_FORCED'];writes={'generation.gsr':2}
    for name in sorted(set(files)-{'generation.gsr'}):
        prefix='INSTALL_IMAGE' if name.endswith('.image') else 'INSTALL_MEMBER';writes[name]=len(events)
        events += [prefix+'_WRITTEN',prefix+'_FORCED']
    events += ['INSTALL_GENERATION_FORCED','INSTALL_SELECTOR_WRITTEN','INSTALL_SELECTOR_FORCED','INSTALL_SELECTOR_RENAMED','INSTALL_PARENT_FORCED']
    return events,writes


def snapshot(path,size,initial,rows,files,selector,position,events,writes,advanced=False):
    path=Path(path);extras={'selector.gsr','generations'}|({'selector.pending.gsr'} if (path/'selector.pending.gsr').exists() else set())
    actual,journal=s.state(path,size,extra_names=extras)
    need(journal[:len(rows)]==rows and (advanced or journal==rows),'install journal rewritten')
    expected=dict(initial)
    if position>=1:expected['generations/b']=dict(directory=True)
    for name,index in writes.items():
        if position>=index:expected['generations/b/'+name]=dict(bytes=len(files[name]),sha256=c.sha(files[name]))
    renamed=position>=events.index('INSTALL_SELECTOR_RENAMED')
    if renamed:expected['selector.gsr']=dict(bytes=len(selector),sha256=c.sha(selector))
    elif position>=events.index('INSTALL_SELECTOR_WRITTEN'):expected['selector.pending.gsr']=dict(bytes=len(selector),sha256=c.sha(selector))
    if advanced:
        need([k for k,_,_ in journal[len(rows):]]==['PROMISE','BASIS'] and journal[-1][2]['ballot']['counter']==21,'install next grant history')
        next_basis=journal[-1];data=p.decode(files['source.gscp']);p.bind(data,next_basis[1]);identity=next_basis[2]['basisId']
        need(g.read(path/'sources'/identity/'source.gscp',g.LIMIT)==files['source.gscp'],'install next source resampled')
        expected['grants.gsr']=dict(bytes=sum(len(r[1]) for r in journal),sha256=c.sha(b''.join(r[1] for r in journal)))
        expected['sources/'+identity]=dict(directory=True)
        for name in ['source.gscp',*[h+'.image' for h in data['images']]]:expected['sources/'+identity+'/'+name]=dict(bytes=len(files[name]),sha256=c.sha(files[name]))
    need(actual==expected,'install physical snapshot')
    need(sum(name.endswith('.image') for name in actual)<=7,'install shared image count')
    return actual,journal


def result(stdout,files,manifest):
    row=stdout[-1]
    need(row['manifest']==c.sha(files['generation.gsr']) and all(row[k]==manifest[k] for k in ('cut','selection','ownedTail'))
         and row['localInstallation'] is True and row['networkAck'] is False,'install returned binding')


def validate_case(directory,case):
    directory=Path(directory);record=g.a.load(directory/'case.json');need(record['case']==case,'install case identity')
    need(record['execution']=='private-generation-install' and record['runtimeEnabled'] is False and record['remoteOwnershipVerified'] is False,'install runtime scope')
    initial,rows,generation,_=c.current(directory/'initial',case['size'])
    need([k for k,_,_ in rows]==['PROMISE','PROMISE','BASIS','SELECTED'] and generation['cut']['index']==0,'install initial authority')
    frames=record.get('selectedSourceFrames',False);need(type(frames) is bool,'install selected source mode')
    files,selector,manifest,data=plan(directory,rows,generation,case,frames);events,writes=transaction(files)
    order=list(c.OPEN)+events+list(c.OPEN)+['INSTALL_BEFORE_RETURN'];clean=case['mode']=='clean'
    d.process(directory,record,'init','init',0)
    name='original' if clean else 'resumed'
    snapshot(directory/name,case['size'],initial,rows,files,selector,len(events),events,writes)
    if clean:
        stdout=d.process(directory,record,'first','install',0);need(g.events(stdout)==order,'install force order');result(stdout,files,manifest)
        stdout=d.process(directory,record,'duplicate','install',0);need(g.events(stdout)==list(c.OPEN),'install duplicate wrote');result(stdout,files,manifest)
        snapshot(directory/'duplicate',case['size'],initial,rows,files,selector,len(events),events,writes)
    else:
        cut=case['cut'];stdout=d.process(directory,record,'fault','install',73 if case['mode']=='halt' else -9)
        need(g.events(stdout)==order[:order.index(cut)+1]+(['AWAITING_KILL'] if case['mode']=='kill' else []),'install crash cut')
        if case['mode']=='kill':need(stdout[-1]==dict(event='AWAITING_KILL',cut=cut),'install kill handshake')
        position=events.index(cut) if cut in events else len(events)
        snapshot(directory/'crash',case['size'],initial,rows,files,selector,position,events,writes)
        stdout=d.process(directory,record,'resume','install',0)
        need(g.events(stdout)==(list(c.OPEN) if position>=events.index('INSTALL_SELECTOR_RENAMED') else order),'install recovery force order');result(stdout,files,manifest)
    final,history=snapshot(directory/'final',case['size'],initial,rows,files,selector,len(events),events,writes,advanced=True)
    stdout=d.process(directory,record,'next','advance',0);need(g.events(stdout)==list(c.ORDER),'install next capture order')
    need(stdout[-1]['basis']==c.sha(history[-1][1]) and stdout[-1]['cut']==manifest['cut'],'install next returned binding')
    need(snapshot(directory/'authority',case['size'],initial,rows,files,selector,len(events),events,writes,advanced=True)[0]==final,'install final authority')
    processes={'init','first','duplicate','next'} if clean else {'init','fault','resume','next'}
    snapshots={'initial','original','duplicate','final','authority'} if clean else {'initial','crash','resumed','final','authority'}
    need(set(record['processes'])==processes and {p.name for p in directory.iterdir()}=={'case.json','inputs',*snapshots}|{n+s for n in processes for s in ('.stdout','.stderr')},'install case inventory')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,networkAck=False)


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={c['name'] for c in cases()},'install complete cases')
    return dict(status='PASS',execution='private-generation-install',runtimeEnabled=False,networkAck=False,
                cases=[validate_case(directory/c['name'],c) for c in cases()])
