"""Independent byte/event replay for the private physical ballot allocator probe."""
import json
from pathlib import Path
from . import format_fixture as f
from .membership_model import need

CUTS=('ALLOCATOR_BEFORE_WRITE','ALLOCATOR_CREATED','ALLOCATOR_WRITTEN','ALLOCATOR_FORCED',
      'ALLOCATOR_RENAMED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN')
NAMES={'replica.lock','root.gsr','genesis.gsr','node.gsr','allocator.gsr'}


def cases():
    return [dict(name=f'{size}-{mode}-{cut.lower()}',size=size,mode=mode,cut=cut)
            for size in (3,4,5) for mode,cut in [('clean','none'),('lock','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]]


def load(path):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=65536,'missing/linked/large allocator evidence')
    return json.loads(path.read_bytes())


def files(path):
    need(path.is_dir() and not path.is_symlink(),'allocator snapshot directory')
    rows={p.name:p for p in path.iterdir()}
    need(set(rows) in (NAMES,NAMES|{'allocator.pending.gsr'}),'allocator snapshot inventory')
    values={}
    for name,p in rows.items():
        bound=65536 if name=='genesis.gsr' else 16384 if name=='root.gsr' else 4096
        need(p.is_file() and not p.is_symlink() and p.stat().st_size<=bound,'allocator snapshot bound/type')
        values[name]=p.read_bytes()
    need(values['replica.lock']==b'','allocator lock bytes');return values


def state(path,size,counter,pending=None):
    values=files(path);root=f.decode(values['root.gsr'],'records','ROOT');root_hash=values['root.gsr'][16:48].hex()
    genesis=f.decode(values['genesis.gsr'],'records','GENESIS')
    import hashlib
    need(hashlib.sha256(values['genesis.gsr']).hexdigest()==root['genesis'],'allocator genesis identity')
    need(all(root[k]==genesis[k] for k in ('groupId','historyId','baseSequence','schema','indexes')),'allocator genesis context')
    need(root['limits']==hashlib.sha256(f.canonical(f.catalog()['resources'])).hexdigest(),'allocator resource contract')
    need(len(root['initial'])==size and [r['node'] for r in root['initial']]==[f'node-{i}' for i in range(1,size+1)],'allocator initial membership')
    node=f.decode(values['node.gsr'],'records','NODE',root_hash)
    need(node['identity']==root['initial'][0],'allocator local identity')
    def check(raw,expected):
        record=f.decode(raw,'records','ALLOCATOR',root_hash)
        need(record['node']==node['identity']['node'],'allocator record owner')
        need(record['counter']==expected,'allocator durable counter')
    check(values['allocator.gsr'],counter)
    if pending is None:need('allocator.pending.gsr' not in values,'unexpected allocator pending')
    elif pending=='torn':need(values.get('allocator.pending.gsr')==b'','expected empty interrupted pending')
    else:check(values['allocator.pending.gsr'],pending)
    return values


def process(directory,record,name,code,counter=None):
    row=record['processes'][name];need(type(row['exitCode']) is int and row['exitCode']==code,'allocator process outcome')
    path=directory/(name+'.stdout');need(path.is_file() and not path.is_symlink() and path.stat().st_size<=65536,'allocator stdout bound')
    err=directory/(name+'.stderr');need(err.is_file() and not err.is_symlink() and err.stat().st_size==0,'unexpected allocator stderr')
    events=[json.loads(line) for line in path.read_text().splitlines()]
    need(all('status' not in row for row in events[:-1]),'multiple allocator terminal results')
    if code==0:
        need(events and events[-1].get('status')=='PASS','allocator process success')
        if counter is not None:need(events[-1].get('counter')==counter,'allocator returned counter')
    elif code==2:need(events and events[-1].get('status')=='FAIL','allocator refusal receipt')
    else:need(not any(e.get('status')=='PASS' for e in events),'allocator callback after crash')
    if code in (0,2):
        command='init' if name=='init' else 'reserve' if name in ('first','second','next') else 'inspect'
        need(events[-1].get('command')==command,'allocator result command')
    return events


def success_order(events):
    need([e['event'] for e in events if 'event' in e]==list(CUTS),'allocator return before complete forces')


def validate_case(directory,case):
    directory=Path(directory);record=load(directory/'case.json');need(record['case']==case,'allocator case identity')
    need(record['execution']=='private-storage-process' and record['runtimeEnabled'] is False,'allocator runtime scope')
    size,mode,cut=case['size'],case['mode'],case['cut'];initial=state(directory/'initial',size,0);process(directory,record,'init',0)
    names={'init','first','second','inspect'} if mode=='clean' else {'init','holder','contender','inspect'} if mode=='lock' else {'init','fault','resume'}|({'next'} if cut!='ALLOCATOR_CREATED' else set())
    need(set(record['processes'])==names,'allocator process inventory')
    if mode=='clean':
        success_order(process(directory,record,'first',0,10));success_order(process(directory,record,'second',0,11))
        process(directory,record,'inspect',0,11);final=state(directory/'final',size,11)
    elif mode=='lock':
        events=process(directory,record,'holder',-9);need(events==[{'event':'HELD'}],'missing live owner observation')
        rejected=process(directory,record,'contender',2);need('owned' in rejected[-1]['reason'],'unrelated lock refusal')
        need(files(directory/'blocked')==initial,'lock conflict changed bytes');process(directory,record,'inspect',0,0)
        final=state(directory/'final',size,0)
    else:
        events=process(directory,record,'fault',73 if mode=='halt' else -9)
        actual=[e['event'] for e in events if 'event' in e and e['event']!='AWAITING_KILL']
        need(actual==list(CUTS[:CUTS.index(cut)+1]),'allocator crash cut mismatch')
        if mode=='kill':need(events[-1]==dict(event='AWAITING_KILL',cut=cut),'missing external kill handshake')
        pending='torn' if cut=='ALLOCATOR_CREATED' else 10 if cut in ('ALLOCATOR_WRITTEN','ALLOCATOR_FORCED') else None
        current=0 if CUTS.index(cut)<4 else 10
        crash=state(directory/'crash',size,current,pending)
        need(all(initial[n]==crash[n] for n in ('root.gsr','genesis.gsr','node.gsr','replica.lock')),'crash changed immutable allocator authority')
        if pending=='torn':
            rejected=process(directory,record,'resume',2);need('truncated header' in rejected[-1]['reason'],'unrelated torn-pending refusal')
            final=state(directory/'final',size,0,'torn');need(final==crash,'refusal repaired original bytes')
        else:
            recovered=0 if cut==CUTS[0] else 10
            process(directory,record,'resume',0,recovered);success_order(process(directory,record,'next',0,recovered+1))
            final=state(directory/'final',size,recovered+1)
    snapshots={'initial','final','authority'}|({'blocked'} if mode=='lock' else {'crash'} if mode in ('kill','halt') else set())
    expected={'case.json'}|snapshots|{n+suffix for n in names for suffix in ('.stdout','.stderr')}
    need({p.name for p in directory.iterdir()}==expected and not any(p.is_symlink() for p in directory.rglob('*')),'allocator case file inventory')
    need(files(directory/'authority')==final,'allocator final source differs from snapshot')
    need(all(initial[n]==final[n] for n in ('root.gsr','genesis.gsr','node.gsr','replica.lock')),'immutable allocator authority changed')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False)


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={c['name'] for c in cases()},'allocator complete case inventory')
    rows=[validate_case(directory/c['name'],c) for c in cases()]
    return dict(status='PASS',execution='private-storage-process',runtimeEnabled=False,cases=rows)
