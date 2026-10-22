"""Exact interrupted BASIS append recovery, extending retained capture evidence v1."""
from pathlib import Path
from . import capture_recovery_evidence as base
from . import current_generation_evidence as current
from . import basis_sources_evidence as sources
from . import grant_evidence as g
from .membership_model import need

AUTHORITY=base.AUTHORITY
CUTS=base.CUTS[:base.CUTS.index('BASIS_WRITTEN')]+('BASIS_PREFIX_WRITTEN',)+base.CUTS[base.CUTS.index('BASIS_WRITTEN'):]
ORDER=current.OPEN+('CURRENT_BEFORE_CAPTURE',)+g.CUTS[:3]+CUTS
RECOVERY=('BASIS_RECOVERY_VALIDATED','BASIS_RECOVERY_PREFIX_WRITTEN','BASIS_RECOVERY_WRITTEN','BASIS_RECOVERY_FORCED','BASIS_RECOVERY_PARENT_FORCED')


def cases():
    result=base.cases()
    for mode in ('halt','kill'):result.append(dict(size=3,through=1,tail=True,mode=mode,cut='BASIS_PREFIX_WRITTEN'))
    for mode in ('recover-halt','recover-kill'):
        for cut in RECOVERY+base.CLEAR:result.append(dict(size=5,through=6,tail=True,mode=mode,cut=cut))
    for c in result:c['name']=f"{c['size']}-{c['through']}-{str(c['tail']).lower()}-{c['mode']}-{c['cut'].lower()}"
    return result


def insert_prefix(events):
    events=list(events)
    if 'BASIS_WRITTEN' in events:events.insert(events.index('BASIS_WRITTEN'),'BASIS_PREFIX_WRITTEN')
    return events


def model(root,case):
    state,rows,intent,identity=base.model(root,case);prefix=b''.join(r[1] for r in rows[:2]);basis=rows[-1][1]
    def snapshot(point=None):
        if point not in ('BASIS_PREFIX_WRITTEN',*RECOVERY):return state(point)
        expected=state('BASIS_BEFORE_WRITE');half=len(basis)//2
        size=half if point in ('BASIS_PREFIX_WRITTEN','BASIS_RECOVERY_VALIDATED') else half+(len(basis)-half)//2 if point=='BASIS_RECOVERY_PREFIX_WRITTEN' else len(basis)
        expected['grants.gsr']=base.info(prefix+basis[:size]);return expected
    def resume(snapshot):
        length=snapshot['grants.gsr']['bytes']
        if len(prefix)<length<len(prefix)+len(basis):return list(current.OPEN+RECOVERY+base.CLEAR)
        return insert_prefix(base.recovery_order(snapshot,identity,length==len(prefix)+len(basis)))
    return snapshot,resume,rows


def validate_case(directory,case):
    root=Path(directory);record=g.a.load(root/'case.json');need(record['case']==case,'capture case identity')
    need(record['execution']=='private-capture-recovery' and record['runtimeEnabled'] is False and record['historicalOwnershipVerified'] is False and record['networkAck'] is False and record.get('journalRecovery') is True,'capture scope')
    state,recovery_order,rows=model(root,case);clean=case['mode']=='clean';repeat=case['mode'].startswith('repeat-');recover=case['mode'].startswith('recover-');second=repeat or recover
    names={'init','first','duplicate','inspect'} if clean else {'init','fault','resume','inspect'}|({'recovery-fault'} if second else set())
    snapshots={'initial','original','duplicate','final','authority'} if clean else {'initial','crash','resumed','final','authority'}|({'recovery-crash'} if second else set())
    need(set(record['processes'])==names,'capture process inventory')
    need({p.name for p in root.iterdir()}=={'case.json',*snapshots}|{n+s for n in names for s in ('.stdout','.stderr')},'capture case inventory')
    need(base.process(root,record,'init',0,'init')==[dict(command='init',status='PASS')],'capture initialization')
    def returned(output):
        need(output[-1]==dict(status='PASS',command=output[-1]['command'],basis=base.digest(rows[-1][1]),accepted=rows[-1][2]['accepted'],cut=case['through'],sourceCount=1),'capture returned binding')
    if clean:
        output=base.process(root,record,'first',0,'prepare');need(g.events(output)==list(ORDER),'capture force order');returned(output)
        duplicate=base.process(root,record,'duplicate',0,'prepare');need(g.events(duplicate)==list(current.OPEN+('CURRENT_BEFORE_CAPTURE',)),'capture duplicate wrote bytes');returned(duplicate)
        need(sources.inventory(root/'original')==sources.inventory(root/'duplicate')==state(),'capture original/duplicate snapshot')
    else:
        mode=case['mode'].split('-')[-1];point='BASIS_PREFIX_WRITTEN' if recover else 'SOURCE_PACKET_PREFIX_WRITTEN' if repeat else case['cut']
        fault=base.process(root,record,'fault',73 if second or mode=='halt' else -9,'prepare')
        expected=list(ORDER[:ORDER.index(point)+1])+(['AWAITING_KILL'] if not second and mode=='kill' else [])
        need(g.events(fault)==expected,'capture crash force order')
        if not second and mode=='kill':need(fault[-1]==dict(event='AWAITING_KILL',cut=point),'capture kill handshake')
        crash=sources.inventory(root/'crash');need(crash==state(point),'capture exact crash snapshot')
        if second:
            output=base.process(root,record,'recovery-fault',73 if mode=='halt' else -9,'prepare');order=recovery_order(crash)
            need(g.events(output)==order[:order.index(case['cut'])+1]+(['AWAITING_KILL'] if mode=='kill' else []),'capture repeated recovery force order')
            if mode=='kill':need(output[-1]==dict(event='AWAITING_KILL',cut=case['cut']),'capture repeated kill handshake')
            crash=sources.inventory(root/'recovery-crash');need(crash==state(case['cut']),'capture exact recovery crash snapshot')
        output=base.process(root,record,'resume',0,'prepare');need(g.events(output)==recovery_order(crash)+['CURRENT_BEFORE_CAPTURE'],'capture recovery force order');returned(output)
        need(sources.inventory(root/'resumed')==state(),'capture resumed snapshot')
    output=base.process(root,record,'inspect',0,'inspect');need(g.events(output)==list(current.OPEN),'capture inspect wrote authority');returned(output)
    need(sources.inventory(root/'authority')==state(),'capture final source snapshot')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,historicalOwnershipVerified=False,journalRecovery=True)


def validate(root):
    root=Path(root);need({p.name for p in root.iterdir()}=={c['name'] for c in cases()},'capture journal complete case inventory')
    return dict(status='PASS',execution='private-capture-recovery',journalRecovery=True,cases=[validate_case(root/c['name'],c) for c in cases()])
