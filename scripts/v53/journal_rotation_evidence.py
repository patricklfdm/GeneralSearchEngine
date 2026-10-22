"""Exact-frame bounded grant-journal rotation; source/floor deletion is excluded."""
from pathlib import Path
from . import retirement_evidence as r
from . import current_generation_evidence as c
from . import durable_selection_evidence as d
from . import grant_evidence as g
from .membership_model import need

CUTS=('JOURNAL_ROTATION_CREATED','JOURNAL_ROTATION_WRITTEN','JOURNAL_ROTATION_FORCED',
      'JOURNAL_ROTATION_RENAMED','JOURNAL_ROTATION_PARENT_FORCED','JOURNAL_ROTATION_BEFORE_RETURN')
PENDING='grants.rotation.gsr'


def cases():
    return [dict(name=f'{size}-{through}-{mode}-{cut.lower()}',size=size,through=through,mode=mode,cut=cut)
            for size in (3,4,5) for through in (0,6,7)
            for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]
                +[(m,'JOURNAL_ROTATION_FORCED') for m in ('repeat-halt','repeat-kill')]]


def plan(directory,case):
    directory=Path(directory);seed,_,_,_,_=r.plan(directory,case,initial_name='seed')
    initial=directory/'initial';values,rows=g.state(initial,case['size'],{'sources','generations','selector.gsr','floor-copies'})
    raw=g.read(directory/'seed/grants.gsr',g.LIMIT);prior=g.journal(raw,values['root.gsr'][16:48].hex(),'node-1')
    need(rows[:4]==prior and len(rows)==10 and all(k=='PROMISE' for k,_,_ in rows[4:]),'rotation initial journal')
    reference=prior[1][2]
    for counter,(_,_,promise) in enumerate(rows[4:],101):
        need(all(promise[k]==reference[k] for k in ('root','view')) and promise['ballot']==dict(reference['ballot'],counter=counter)
             and promise['basisId'] is not None,'rotation interrupted grant')
    need(len({row[2]['basisId'] for row in rows if row[0]=='PROMISE'})==8,'rotation reused basis identity')
    expected={n:v for n,v in seed.items() if n!='generations/a' and not n.startswith('generations/a/')}
    expected['grants.gsr']=r.entry(b''.join(row[1] for row in rows));r.snapshot(initial,expected)
    # The frozen seed references PROMISE10 in its local floor and PROMISE100 in B.
    # Keep all actual original grant/selection frames and the last incomplete promise.
    compact=b''.join(row[1] for row in [*prior,rows[-1]])
    need(len(compact)<expected['grants.gsr']['bytes'] and len(compact)<=565248,'rotation compact bound')
    return expected,compact,c.sha(rows[-1][1])


def transaction(initial,compact):
    state=dict(initial);steps=[]
    def event(name):steps.append((name,dict(state)))
    if PENDING not in state and state['grants.gsr']==r.entry(compact):return steps
    if PENDING not in state:state[PENDING]=r.entry(b'');event('JOURNAL_ROTATION_CREATED')
    state[PENDING]=r.entry(compact);event('JOURNAL_ROTATION_WRITTEN');event('JOURNAL_ROTATION_FORCED')
    state.pop(PENDING);state['grants.gsr']=r.entry(compact);event('JOURNAL_ROTATION_RENAMED')
    event('JOURNAL_ROTATION_PARENT_FORCED');event('JOURNAL_ROTATION_BEFORE_RETURN');return steps


def result(rows,compact,promise):
    need(rows[-1]['journal']==c.sha(compact) and rows[-1]['promise']==promise and rows[-1]['networkAck'] is False,'rotation returned binding')


def validate_case(directory,case):
    directory=Path(directory);record=g.a.load(directory/'case.json');need(record['case']==case,'rotation case identity')
    need(record['execution']=='private-journal-rotation' and all(record[k] is False for k in ('runtimeEnabled','historicalOwnershipVerified','networkAck')),'rotation scope')
    initial,compact,promise=plan(directory,case);d.process(directory,record,'init','init',0)
    processes={'init'};snapshots={'initial','seed','final','authority'}
    def call(label,state,mode='none',cut='none'):
        steps=transaction(state,compact);fault=mode!='none';position=r.cut_position(steps,cut) if fault else len(steps)-1
        rows=d.process(directory,record,label,'rotate',73 if mode=='halt' else -9 if mode=='kill' else 0)
        expected=[dict(event=name) for name in c.OPEN]+[dict(event=name) for name,_ in steps[:position+1]]
        if mode=='kill':expected.append(dict(event='AWAITING_KILL',cut=cut))
        need((rows if fault else rows[:-1])==expected,'rotation crash order' if fault else 'rotation force order')
        if not fault:result(rows,compact,promise)
        processes.add(label);return steps[position][1] if steps else state
    def snapshot(name,state):snapshots.add(name);r.snapshot(directory/name,state)
    if case['mode']=='clean':
        final=call('first',initial);snapshot('original',final);snapshot('duplicate',call('duplicate',final))
    else:
        repeated=case['mode'].startswith('repeat-');mode=case['mode'].removeprefix('repeat-')
        crash=call('fault',initial,'halt' if repeated else mode,'JOURNAL_ROTATION_CREATED' if repeated else case['cut']);snapshot('crash',crash)
        if repeated:crash=call('recovery-fault',crash,mode,case['cut']);snapshot('recovery-crash',crash)
        final=call('resume',crash);snapshot('resumed',final)
    rows=d.process(directory,record,'inspect','inspect',0);need(rows[:-1]==[dict(event=name) for name in c.OPEN],'rotation inspect force order')
    result(rows,compact,promise);processes.add('inspect');r.snapshot(directory/'final',final);r.snapshot(directory/'authority',final)
    need(set(record['processes'])==processes and {v.name for v in directory.iterdir()}=={'case.json','inputs',*snapshots}|{n+s for n in processes for s in ('.stdout','.stderr')},'rotation case inventory')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,networkAck=False)


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={c['name'] for c in cases()},'rotation complete cases')
    return dict(status='PASS',execution='private-journal-rotation',runtimeEnabled=False,cases=[validate_case(directory/c['name'],c) for c in cases()])
