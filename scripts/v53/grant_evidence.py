"""Independent replay of private durable grant metadata, not public voting authority."""
import hashlib
import json
from pathlib import Path
from . import allocator_evidence as a
from . import format_fixture as f
from . import source_packet as packet
from .membership_model import need

CUTS=('PROMISE_BEFORE_WRITE','PROMISE_WRITTEN','PROMISE_FORCED','BASIS_BEFORE_WRITE','BASIS_WRITTEN','BASIS_FORCED','GRANT_BEFORE_RETURN')
LIMIT=32*1024*1024


def cases():
    return [dict(name=f'{size}-{mode}-{cut.lower()}',size=size,mode=mode,cut=cut) for size in (3,4,5)
            for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]]


def read(path,maximum):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=maximum,'grant file bound/type')
    return path.read_bytes()


def order(ballot):return ballot['counter'],ballot['proposer'],ballot['incarnation']


def selected_binding(value,promise,basis,basis_raw,node):
    need(promise is not None and basis is not None,'selection without local grant')
    need(all(value[k]==promise[k] for k in ('root','view','ballot')),'selection grant binding')
    cut,own=value['cut'],basis['cut']
    need(cut['view']==own['view'] and own['index']<=cut['index']<=2**63-2,'selection cut/view')
    need(cut['index']!=own['index'] or cut==own,'selection conflicting local parent')
    sources=value['sources'];voters=[s['voter'] for s in sources];view=own['view']
    need(voters==sorted(set(voters)) and set(voters)<=set(view['old'])|set(view['new'])
         and all(len(set(voters)&set(view[k]))>len(view[k])//2 for k in ('old','new')),'selection eligible quorum')
    need(len({s['basisId'] for s in sources})==len(sources),'selection duplicate basis identity')
    need(node in voters and promise['ballot']['proposer'] in voters,'selection missing local voter/proposer')
    local=next(s for s in sources if s['voter']==node)
    need(local['basisId']==basis['basisId'] and local['basisDigest']==hashlib.sha256(basis_raw).hexdigest(),'selection original local basis')


def journal(data,root,node):
    need(len(data)<=LIMIT,'grant journal size');rows=[];offset=0;promise=None;basis=None;basis_raw=None;selected=None
    while offset<len(data):
        need(len(data)-offset>=48,'torn grant journal header')
        kind={3:'PROMISE',4:'BASIS',5:'SELECTED'}.get(int.from_bytes(data[offset+8:offset+10],'big'))
        need(kind is not None,'unknown grant journal record')
        length=48+int.from_bytes(data[offset+12:offset+16],'big')
        need(48<length<=f.catalog()['records'][kind]['maximum'],'grant frame bound')
        need(length<=len(data)-offset,'torn grant journal body')
        raw=data[offset:offset+length];value=f.decode(raw,'records',kind,root);offset+=length
        if kind=='PROMISE':
            need(value['ballot']['counter']<=2**63-2,'grant promise identity/capacity')
            need(promise is None or order(value['ballot'])>order(promise['ballot']),'non-increasing grant promise')
            promise=value;basis=None;basis_raw=None;selected=None
        elif kind=='BASIS':
            need(promise is not None and basis is None,'orphan/duplicate grant basis')
            need(promise['basisId'] is not None,'adoption fence is not a grant')
            need(all(value[k]==promise[k] for k in ('root','view','ballot','basisId')),'grant basis binding')
            need(value['voter']==node,'grant basis owner')
            view=value['cut']['view'];old,new=view['old'],view['new']
            need(view['generation']<=256 and old==sorted(set(old)) and new==sorted(set(new))
                 and len(set(old)|set(new))<=6 and (old==new)==(view['operation'] is None)
                 and len(set(old)-set(new))<=1 and len(set(new)-set(old))<=1,'grant basis membership view')
            need(value['cut']['index']<=2**63-2 and value['view']==hashlib.sha256(f.canonical(dict(root=root,**value['cut']['view']))).hexdigest(),'grant basis cut/view')
            basis=value;basis_raw=raw
        else:
            need(selected is None,'duplicate persisted selection')
            selected_binding(value,promise,basis,basis_raw,node);selected=value
        rows.append((kind,raw,value))
    return rows


def state(path,size,extra_names=frozenset()):
    need(path.is_dir() and not path.is_symlink() and {p.name for p in path.iterdir()}==a.NAMES|{'grants.gsr'}|extra_names,'grant snapshot inventory')
    values={n:read(path/n,LIMIT if n=='grants.gsr' else 65536 if n=='genesis.gsr' else 16384 if n=='root.gsr' else 4096) for n in a.NAMES|{'grants.gsr'}}
    need(values['replica.lock']==b'','grant lock bytes')
    root=f.decode(values['root.gsr'],'records','ROOT');digest=values['root.gsr'][16:48].hex()
    genesis=f.decode(values['genesis.gsr'],'records','GENESIS');need(hashlib.sha256(values['genesis.gsr']).hexdigest()==root['genesis'],'grant genesis identity')
    need(all(genesis[k]==root[k] for k in ('groupId','historyId','baseSequence','schema','indexes')),'grant genesis context')
    need(root['limits']==hashlib.sha256(f.canonical(f.catalog()['resources'])).hexdigest(),'grant resource contract')
    need(len(root['initial'])==size and [v['node'] for v in root['initial']]==[f'node-{i}' for i in range(1,size+1)],'grant initial members')
    node=f.decode(values['node.gsr'],'records','NODE',digest);need(node['identity']==root['initial'][0],'grant local identity')
    counter=f.decode(values['allocator.gsr'],'records','ALLOCATOR',digest);need(counter['node']=='node-1' and counter['counter']==0,'grant independent counter changed')
    return values,journal(values['grants.gsr'],digest,'node-1')


def process(directory,record,name,code):
    need(type(record['processes'][name]['exitCode']) is int and record['processes'][name]['exitCode']==code,'grant process outcome')
    rows=[json.loads(line) for line in read(directory/(name+'.stdout'),65536).splitlines()]
    need(read(directory/(name+'.stderr'),65536)==b'','unexpected grant stderr')
    need(not any('status' in r for r in rows[:-1]),'multiple grant terminal results')
    if code in (0,2):
        need(rows and rows[-1].get('status')==('PASS' if code==0 else 'FAIL') and rows[-1].get('command')==('init' if name=='init' else 'prepare'),'grant terminal result')
    else:need(not any('status' in r for r in rows),'grant return after crash')
    return rows


def events(rows):return [r['event'] for r in rows if 'event' in r]
def result(rows,basis):
    need(rows[-1]['basis']==hashlib.sha256(basis[1]).hexdigest() and rows[-1]['counter']==basis[2]['ballot']['counter']
         and rows[-1]['cut']==basis[2]['cut']['index'],'grant returned original basis')


def validate_case(directory,case):
    directory=Path(directory);record=a.load(directory/'case.json');need(record['case']==case,'grant case identity')
    need(record['execution']=='private-grant-metadata' and record['runtimeEnabled'] is False and record['sourceOwnershipVerified'] is False,'grant runtime scope')
    clean=case['mode']=='clean';size=case['size'];cut=case['cut']
    names={'init','first','duplicate','next'} if clean else {'init','fault','resume','next'}
    snapshots={'initial','original','duplicate','final','authority'} if clean else {'initial','crash','resumed','final','authority'}
    need(set(record['processes'])==names,'grant process inventory')
    initial,zero=state(directory/'initial',size);need(not zero,'grant initial journal');process(directory,record,'init',0)
    final,rows=state(directory/'final',size)
    incomplete=not clean and cut in CUTS[1:4]
    need([k for k,_,_ in rows]==(['PROMISE','PROMISE','BASIS'] if incomplete else ['PROMISE','BASIS','PROMISE','BASIS'])
         and [v['ballot']['counter'] for _,_,v in rows]==([20,21,21] if incomplete else [20,20,21,21]),'grant final history')
    need([v['cut']['index'] for k,_,v in rows if k=='BASIS']==([1] if incomplete else [0,1]),'grant frozen cuts')
    sources={i:packet.decode(read(directory/f'source-c{i}.packet',LIMIT)) for i in (0,1)}
    images={h:s for p in sources.values() for h,s in p['images'].items()}
    for h,s in images.items():
        image=read(directory/f'image-{h}.bin',s);need(len(image)==s and hashlib.sha256(image).hexdigest()==h,'grant fixture image')
    for p in sources.values():need(p['objects'].get(hashlib.sha256(initial['root.gsr']).hexdigest())==initial['root.gsr'],'grant fixture root')
    for kind,raw,b in rows:
        if kind=='BASIS':packet.bind(sources[b['cut']['index']],raw)
    if clean:
        original,old=state(directory/'original',size);duplicate,dup=state(directory/'duplicate',size)
        need(original['grants.gsr']==b''.join(r[1] for r in rows[:2]) and duplicate==original,'duplicate grant changed original bytes')
        first=process(directory,record,'first',0);need(events(first)==list(CUTS),'grant return before complete forces');result(first,old[-1])
        repeated=process(directory,record,'duplicate',0);need(events(repeated)==[],'duplicate grant resampled');result(repeated,old[-1])
    else:
        fault=process(directory,record,'fault',73 if case['mode']=='halt' else -9)
        want=list(CUTS[:CUTS.index(cut)+1])+(['AWAITING_KILL'] if case['mode']=='kill' else [])
        need(events(fault)==want,'grant crash cut mismatch')
        if case['mode']=='kill':need(fault[-1]==dict(event='AWAITING_KILL',cut=cut),'grant kill handshake')
        crash,crashed=state(directory/'crash',size);count=0 if cut==CUTS[0] else 1 if CUTS.index(cut)<4 else 2
        need(len(crashed)==count,'grant interrupted journal state')
        need(crash['grants.gsr']==b''.join(r[1] for r in rows[:count]),'grant original prefix replaced')
        resumed,resume_rows=state(directory/'resumed',size)
        if count==1:
            rejected=process(directory,record,'resume',2);need('incomplete original basis' in rejected[-1]['reason'],'unrelated incomplete grant refusal')
            need(resumed==crash,'incomplete grant resampled')
            # The next fresh ballot supersedes the incomplete promise, so only three frames should remain.
        else:
            repeated=process(directory,record,'resume',0);need(events(repeated)==(list(CUTS) if count==0 else []),'grant resume force order')
            result(repeated,resume_rows[-1]);need(resumed['grants.gsr']==b''.join(r[1] for r in rows[:2]),'grant resumed basis changed')
    next_result=process(directory,record,'next',0);need(events(next_result)==list(CUTS),'grant return before complete forces');result(next_result,rows[-1])
    for name in snapshots:
        data,_=state(directory/name,size)
        need(all(data[n]==initial[n] for n in a.NAMES),'immutable grant authority changed')
    need(state(directory/'authority',size)[0]==final,'grant final source/snapshot mismatch')
    expected={'case.json',*snapshots,'source-c0.packet','source-c1.packet'}|{f'image-{h}.bin' for h in images}|{n+s for n in names for s in ('.stdout','.stderr')}
    need({p.name for p in directory.iterdir()}==expected and not any(p.is_symlink() for p in directory.rglob('*')),'grant case file inventory')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,sourceOwnershipVerified=False)


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={c['name'] for c in cases()},'grant complete case inventory')
    return dict(status='PASS',execution='private-grant-metadata',runtimeEnabled=False,sourceOwnershipVerified=False,
                cases=[validate_case(directory/c['name'],c) for c in cases()])
