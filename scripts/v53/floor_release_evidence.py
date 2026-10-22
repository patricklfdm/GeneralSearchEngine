"""Independent inventory replay of relinquished governing-floor copies."""
from pathlib import Path
from . import retirement_evidence as r
from . import current_generation_evidence as c
from . import durable_selection_evidence as d
from . import grant_evidence as g
from .membership_model import need

CUTS=('FLOOR_RELEASE_AUTHORITY_CREATED','FLOOR_RELEASE_AUTHORITY_WRITTEN','FLOOR_RELEASE_AUTHORITY_FORCED','FLOOR_RELEASE_PARENT_FORCED',
      'FLOOR_RELEASE_RELINQUISHED','FLOOR_RELEASE_FILE_DELETED','FLOOR_RELEASE_COPY_DELETED',
      'FLOOR_RELEASE_PROPOSAL_CLEARED','FLOOR_RELEASE_AUTHORITY_CLEARED','FLOOR_RELEASE_CLEARED','FLOOR_RELEASE_BEFORE_RETURN',
      'FLOOR_RELEASE_FILE_DELETED@2','FLOOR_RELEASE_FILE_DELETED@4')
RELEASE='floor-copies/release.gsr'


def cases():
    return [dict(name=f'{size}-{through}-{mode}-{cut.lower()}',size=size,through=through,mode=mode,cut=cut)
            for size in (3,4,5) for through in (0,6,7)
            for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]
                +[(m,'FLOOR_RELEASE_AUTHORITY_FORCED') for m in ('repeat-halt','repeat-kill')]]


def plan(directory,case):
    directory=Path(directory);seed,_,_,floor,selector=r.plan(directory,case,initial_name='seed')
    initial={n:v for n,v in seed.items() if n!='generations/a' and not n.startswith('generations/a/')}
    r.snapshot(directory/'initial',initial)
    root=g.f.decode(floor,'records','FLOOR')['root']
    record=g.f.encode('records','RETIREMENT',dict(root=root,node='node-1',floor=c.sha(floor),selector=c.sha(selector),
           files=[dict(path=n,size=v['bytes'],sha256=v['sha256']) for n,v in sorted(initial.items())
                  if n.startswith('floor-copies/') and 'directory' not in v]))
    return initial,record,selector


def transaction(initial,record):
    state=dict(initial);steps=[]
    def event(name):steps.append((name,dict(state)))
    def remove(name,event_name):state.pop(name);event(event_name)
    if 'floor-copies' not in state:return steps
    if set(n for n in state if n.startswith('floor-copies/')):
        if RELEASE not in state:state[RELEASE]=r.entry(b'');event('FLOOR_RELEASE_AUTHORITY_CREATED')
        state[RELEASE]=r.entry(record);event('FLOOR_RELEASE_AUTHORITY_WRITTEN');event('FLOOR_RELEASE_AUTHORITY_FORCED');event('FLOOR_RELEASE_PARENT_FORCED')
        if 'floor-copies/floor.gsr' in state:remove('floor-copies/floor.gsr','FLOOR_RELEASE_RELINQUISHED')
        for name in sorted(state):
            if name.startswith('floor-copies/') and name.count('/')==2:remove(name,'FLOOR_RELEASE_FILE_DELETED')
        for name in sorted(state):
            if name.startswith('floor-copies/') and state[name].get('directory'):remove(name,'FLOOR_RELEASE_COPY_DELETED')
        if 'floor-copies/proposal.gsr' in state:remove('floor-copies/proposal.gsr','FLOOR_RELEASE_PROPOSAL_CLEARED')
        remove(RELEASE,'FLOOR_RELEASE_AUTHORITY_CLEARED')
    remove('floor-copies','FLOOR_RELEASE_CLEARED');event('FLOOR_RELEASE_BEFORE_RETURN');return steps


def result(rows,initial,selector):
    row=rows[-1]
    need(row['journal']==initial['grants.gsr']['sha256'] and row['selector']==c.sha(selector) and row['floor'] is None
         and row['networkAck'] is False,'floor release returned binding')


def validate_case(directory,case):
    directory=Path(directory);receipt=g.a.load(directory/'case.json');need(receipt['case']==case,'floor release case identity')
    need(receipt['execution']=='private-floor-release' and all(receipt[k] is False for k in ('runtimeEnabled','historicalOwnershipVerified','networkAck')),'floor release scope')
    initial,record,selector=plan(directory,case);d.process(directory,receipt,'init','init',0)
    processes={'init'};snapshots={'seed','initial','final','authority'}
    def call(label,state,mode='none',cut='none'):
        steps=transaction(state,record);fault=mode!='none';position=r.cut_position(steps,cut) if fault else len(steps)-1
        rows=d.process(directory,receipt,label,'release',73 if mode=='halt' else -9 if mode=='kill' else 0)
        expected=[dict(event=name) for name in c.OPEN]+[dict(event=name) for name,_ in steps[:position+1]]
        if mode=='kill':expected.append(dict(event='AWAITING_KILL',cut=cut))
        need((rows if fault else rows[:-1])==expected,'floor release crash order' if fault else 'floor release force order')
        if not fault:result(rows,initial,selector)
        processes.add(label);return steps[position][1] if steps else state
    def snapshot(name,state):snapshots.add(name);r.snapshot(directory/name,state)
    if case['mode']=='clean':
        final=call('first',initial);snapshot('original',final);snapshot('duplicate',call('duplicate',final))
    else:
        repeated=case['mode'].startswith('repeat-');mode=case['mode'].removeprefix('repeat-')
        crash=call('fault',initial,'halt' if repeated else mode,'FLOOR_RELEASE_FILE_DELETED@2' if repeated else case['cut']);snapshot('crash',crash)
        if repeated:crash=call('recovery-fault',crash,mode,case['cut']);snapshot('recovery-crash',crash)
        final=call('resume',crash);snapshot('resumed',final)
    rows=d.process(directory,receipt,'inspect','inspect',0);need(rows[:-1]==[dict(event=name) for name in c.OPEN],'floor release inspect force order')
    result(rows,initial,selector);processes.add('inspect');r.snapshot(directory/'final',final);r.snapshot(directory/'authority',final)
    need(set(receipt['processes'])==processes and {v.name for v in directory.iterdir()}=={'case.json','inputs',*snapshots}|{n+s for n in processes for s in ('.stdout','.stderr')},'floor release case inventory')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,networkAck=False)


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={c['name'] for c in cases()},'floor release complete cases')
    return dict(status='PASS',execution='private-floor-release',runtimeEnabled=False,cases=[validate_case(directory/c['name'],c) for c in cases()])
