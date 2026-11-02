"""Original joining initialization bytes and force-prefix replay.

This component checks one retained initialization transaction. It does not
qualify the preceding native history, network delivery or later FINAL/BARRIER.
Those readers must still compose with this process history before admission.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import joining_process_run as run
from . import joining_retention_evidence as ledgers

need=run.h.need
ACTIVE=(ledgers.DECISION,*ledgers.LEDGERS,ledgers.DONE)
NEXT=('joining-retention.next.gsjr','peer-retention.next.gspr','future-retention.next.gsft',
      'learner-retention.next.gslr','joining-retention.done.next.gsjr')
LABELS=tuple('JOINING_RETENTION_'+v for v in ('SEED','PEERS','FUTURE','LEARNER','DONE'))
MEMBERS=frozenset((*ACTIVE,*NEXT))


def steps(final, *, initial=None):
    """Pure state/force model; bytes and original file keys are already derived."""
    need(set(final)==set(ACTIVE) and all(type(v) is tuple and len(v)==2 and type(v[0]) is str and v[0]
         and type(v[1]) is bytes and len(v[1])>1 for v in final.values()),'joining initialization model frames')
    need(len({v[0] for v in final.values()})==len(ACTIVE),'joining initialization model inode alias')
    state={} if initial is None else dict(initial);result=[]
    need(set(state)<=MEMBERS,'joining initialization unknown transaction file')
    for active,next_name in zip(ACTIVE,NEXT):
        need(not (active in state and next_name in state),'joining initialization candidate overlap')
        for name in (active,next_name):
            if name in state:
                key,data=state[name]
                need(key==final[active][0] and final[active][1].startswith(data) and
                     (name!=active or data==final[active][1]),'joining initialization changed original prefix')
    def emit(label):result.append((label,dict(state)))
    def force(label):emit(label+'_FORCED');emit(label+'_PARENT_FORCED')
    def finish(active,next_name,label):
        key,expected=final[active]
        if next_name not in state:state[next_name]=(key,b'');emit(label+'_CREATED')
        if len(state[next_name][1])<len(expected)//2:
            state[next_name]=(key,expected[:len(expected)//2]);emit(label+'_PREFIX_WRITTEN')
        state[next_name]=(key,expected);emit(label+'_WRITTEN');emit(label+'_FORCED');emit(label+'_CANDIDATE_PARENT_FORCED')
        state[active]=state.pop(next_name);emit(label+'_RENAMED');emit(label+'_PARENT_FORCED')
    if ledgers.DONE in state:
        need(state==final,'joining initialization completed state')
        force(LABELS[0]+'_RECOVERY');force(LABELS[-1]+'_RECOVERY')
        return result
    if ledgers.DECISION in state:force(LABELS[0]+'_RECOVERY')
    else:
        need(set(state)<= {NEXT[0]},'joining initialization ledgers before decision')
        finish(ACTIVE[0],NEXT[0],LABELS[0])
    for active,next_name,label in zip(ACTIVE[1:4],NEXT[1:4],LABELS[1:4]):
        if active in state:force(label+'_RECOVERY')
        else:finish(active,next_name,label)
    finish(ACTIVE[-1],NEXT[-1],LABELS[-1]);emit('JOINING_RETENTION_BEFORE_RETURN')
    need(state==final,'joining initialization final projection')
    return result


def files(snap):
    return {v['name']:(v['identity']['key'],snap.member('replica',v['name']))
            for v in snap.identities['replica']['files'] if 'directory' not in v['identity']}


def unchanged_custody(before,other):
    """Read only retained copies. Original absolute paths remain data."""
    for family in before.identities:
        a,b=before.identities[family],other.identities[family]
        need(a['path']==b['path'] and a['present']==b['present'],'joining initialization original root changed')
        if not a['present']:continue
        aa=[v for v in a['files'] if family!='replica' or v['name'] not in MEMBERS]
        bb=[v for v in b['files'] if family!='replica' or v['name'] not in MEMBERS]
        need(aa==bb,'joining initialization unrelated custody changed')
        for v in aa:
            if 'directory' not in v['identity']:
                need(before.member(family,v['name'])==other.member(family,v['name']),
                     'joining initialization unrelated original bytes changed')


def callbacks(trace,mode,node):
    events=[row['value']['value'] for row in trace if row['origin']==mode and row['value']['kind']=='EVENT']
    matching=[v for v in events if str(v.get('event','')).startswith('JOINING_RETENTION_')]
    need(all(set(v)=={'node','scope','event'} and v['node']==node and v['scope']=='initialization-'+mode for v in matching),
         'joining initialization callback owner')
    return [v['event'] for v in matching]


def validate(raw,case):
    raw=Path(raw);original=run.h.inventory(raw);collection=run.collect(raw,case);selected=run.selected(case)
    snapshots={stage:ledgers.snapshot.read(raw/('joining-process-'+stage))
               for stage in ('before-process','interrupted','resumed-active','resumed-closed')}
    before=snapshots['before-process'];interrupted=snapshots['interrupted'];active=snapshots['resumed-active']
    need(not set(files(before))&MEMBERS,'joining initialization already started')
    for snap in snapshots.values():unchanged_custody(before,snap)
    seed,initial,old_sources=ledgers.original_derivation(raw,active,confirmed_peers=True)
    ledgers.transaction(active,seed,initial);ledgers.transaction(snapshots['resumed-closed'],seed,initial)
    expected=ledgers.transaction_frames(active,seed,initial)
    keys={v['name']:v['identity']['key'] for v in active.identities['replica']['files']}
    final={name:(keys[name],expected[name]) for name in ACTIVE}
    first=steps(final);need([v[0] for v in first]==list(run.POINTS),'joining initialization callback catalogue')
    at=run.POINTS.index(selected['point']);prefix=first[at][1]
    need({k:v for k,v in files(interrupted).items() if k in MEMBERS}==prefix,'joining initialization interrupted bytes or inode')
    for stage in ('resumed-active','resumed-closed'):
        need({k:v for k,v in files(snapshots[stage]).items() if k in MEMBERS}==final,'joining initialization resumed bytes or inode')
    trace=run.lines(raw/'process-trace.jsonl')
    joined=ledgers.snapshot.s.e.parse(active.member('placement','joined.json'));node=joined['identity']['node']
    ready=run.metadata.read(raw/'joining-process/result.json')['children'][1]['ready']
    need(ledgers.f.canonical(ready['cut'])==ledgers.f.canonical(joined['cut']),'joining initialization recovered cut')
    need(callbacks(trace,selected['mode'],node)==[v[0] for v in first[:at+1]],'joining initialization first force prefix')
    recovery=steps(final,initial=prefix)
    need(callbacks(trace,'resume',node)==[v[0] for v in recovery],'joining initialization recovery force sequence')
    need(run.h.inventory(raw)==original==collection['inventory'],'joining initialization original changed during replay')
    return dict(status='PARTIAL',scope='original-joining-initialization-transaction',case=case,
                originalTransactionVerified=True,originalInodesPreserved=True,forcePrefixVerified=True,
                oldSources=old_sources,firstCallbacks=at+1,recoveryCallbacks=len(recovery),seedSha256=ledgers.sha(seed),
                nativeHistoryQualified=False,networkQualified=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES={
    'changed-prefix':'joining initialization interrupted bytes or inode',
    'replaced-inode':'joining initialization interrupted bytes or inode',
    'missing-first-callback':'joining initialization first force prefix',
    'reordered-recovery':'joining initialization recovery force sequence',
    'wrong-callback-owner':'joining initialization callback owner',
    'changed-initial-ledger':'joining derivation exact initial ledger: future-retention.gsft',
    'changed-closed-custody':'joining initialization unrelated custody changed',
    'premature-public-ready':'joining process recovered endpoint observation',
    'changed-ready-cut':'joining initialization recovered cut',
}


def mutate(raw,case,negative):
    """Change copied observations consistently so semantic checks must reject."""
    need(negative in NEGATIVES,'joining initialization negative selector');raw=Path(raw)
    def save(path,value):path.write_bytes(ledgers.f.canonical(value))
    def change_snapshot(stage,name,*,inode=False):
        path=raw/('joining-process-'+stage);rows=run.metadata.read(path/'inventory.json')
        replica=next(v for v in rows if v['name']=='replica')
        if name is None:name=next(v['name'] for v in replica['files'] if v['name'] in MEMBERS)
        identity=next(v['identity'] for v in replica['files'] if v['name']==name)
        if inode:identity['key']='replaced-original-inode'
        else:
            file=path/'replica'/name;data=file.read_bytes()
            changed=data[:-1]+bytes([data[-1]^1]) if data else b'changed-empty-prefix'
            file.write_bytes(changed);identity.update(size=len(changed),sha256=ledgers.sha(changed))
        save(path/'inventory.json',rows)
    if negative in ('changed-prefix','replaced-inode'):
        change_snapshot('interrupted',None,inode=negative=='replaced-inode');return
    if negative=='changed-initial-ledger':change_snapshot('resumed-active',ledgers.LEDGERS[1]);return
    if negative=='changed-closed-custody':change_snapshot('resumed-closed','node.gsr');return
    mode=run.selected(case)['mode'];trace=run.lines(raw/'process-trace.jsonl')
    def positions(origin):
        return [i for i,v in enumerate(trace) if v['origin']==origin and v['value']['kind']=='EVENT'
                and str(v['value']['value'].get('event','')).startswith('JOINING_RETENTION_')]
    if negative=='missing-first-callback':del trace[positions(mode)[-1]]
    elif negative=='reordered-recovery':
        a,b=positions('resume')[:2];trace[a],trace[b]=trace[b],trace[a]
    elif negative=='wrong-callback-owner':trace[positions(mode)[0]]['value']['value']['node']='node-foreign'
    else:
        ready=next(v['value']['value'] for v in trace if v['origin']=='resume' and v['value']['kind']=='READY')
        if negative=='changed-ready-cut':ready['cut']={}
        else:ready['publicReady']=True
        path=raw/'joining-process/result.json';result=run.metadata.read(path)
        result['children'][1]['ready']=ready;save(path,result)
    def write_lines(path,rows):path.write_bytes(b''.join(ledgers.f.canonical(v)+b'\n' for v in rows))
    write_lines(raw/'process-trace.jsonl',trace)
    for origin in (mode,'resume'):
        write_lines(raw/'joining-process'/origin/'stdout',[v['value'] for v in trace if v['origin']==origin])


def negatives(raw,case):
    raw=Path(raw);before=run.h.inventory(raw);validate(raw,case);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-init-negative-') as directory:
            copied=Path(directory)/'raw';shutil.copytree(raw,copied);mutate(copied,case,name)
            try:validate(copied,case)
            except ValueError as error:need(str(error)==reason,'joining initialization unrelated negative: '+name+': '+str(error))
            else:raise ValueError('joining initialization accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(run.h.inventory(raw)==before,'joining initialization negatives changed original')
    return results


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('raw');p.add_argument('--case',required=True,choices=run.CASES)
    p.add_argument('--negatives',action='store_true');a=p.parse_args()
    print(json.dumps(negatives(a.raw,a.case) if a.negatives else validate(a.raw,a.case),sort_keys=True))
