"""Exact local CERTIFICATE over real local ACCEPT and PROOF quorums, no publication."""
from pathlib import Path
from . import pending_proof_evidence as p
from .pending_proof_evidence import a,c,g,capture,need,inventory
CUTS=tuple(v.replace('PROOF','CERTIFICATE') for v in p.CUTS)
SEAL=tuple(v.replace('PROOF','CERTIFICATE') for v in p.SEAL)
RECOVERY=('CERTIFICATE_RECOVERY_VALIDATED',)+CUTS[2:-1]
ACTIVE=p.ACTIVE;NEXT=p.NEXT

def cases():
    result=[]
    for original in p.cases():
        row=dict(original);row['cut']=row['cut'].replace('PROOF','CERTIFICATE');row['name']=row['name'].replace('proof_','certificate_');result.append(row)
    return result

def validate_case(directory,case):
    root=Path(directory);record=g.a.load(root/'case.json');need(record['case']==case,'certificate case identity')
    need(record['execution']=='private-pending-certificate' and record['runtimeEnabled'] is False and record['localVotersVerified'] is True and record['networkAck'] is False,'certificate evidence scope')
    state,history,accepts,returned=p.model(root,case,certificate=True);clean=case['mode']=='clean';repeat=case['mode'].startswith('repeat-');mode=case['mode'].removeprefix('repeat-')
    names={'init','install','accept-all','prove-all','capture','inspect'}|({'first','duplicate','accept-duplicate','proof-duplicate'} if clean else {'fault','resume'})|({'recovery-fault'} if repeat else set())
    snapshots={'provisioned','installed','accepted','proven','final','authority'}|({'original','duplicate'} if clean else {'crash','resumed'})|({'recovery-crash'} if repeat else set())
    need(set(record['processes'])==names and {v.name for v in root.iterdir()}=={'case.json',*snapshots}|{n+x for n in names for x in ('.stdout','.stderr')},'certificate case inventory')
    def output(name,command,code=0):
        # Existing driver is strict about complete stdout, exits and no early terminal result.
        return a.output(root,record,name,command,code)
    for name in ('init','install'):need(output(name,name)==[dict(status='PASS',command=name)],'certificate fixture initialization')
    import json
    rows=[json.loads(line) for line in g.read(root/'accept-all.stdout',65536).splitlines()]
    expected=[]
    for node,value in accepts.items():expected.extend([dict(event=event,node=node) for event in a.OPEN+a.CUTS]+[value])
    need(record['processes']['accept-all']==dict(exitCode=0) and g.read(root/'accept-all.stderr',65536)==b'' and rows==expected+[dict(status='PASS',command='accept-all')],'certificate actual ACCEPT force/return order')
    rows=[json.loads(line) for line in g.read(root/'prove-all.stdout',65536).splitlines()];expected=[]
    for node,value in accepts.items():
        actual=dict(value);actual.pop('accepted');actual['proof']=returned['proof']
        expected.extend([dict(event=event,node=node) for event in a.OPEN+p.CUTS]+[actual])
    need(record['processes']['prove-all']==dict(exitCode=0) and g.read(root/'prove-all.stderr',65536)==b'' and rows==expected+[dict(status='PASS',command='prove-all')],'certificate actual PROOF force/return order')
    def success(rows,advanced=False):
        basis=history[-1] if advanced else history[2]
        need(rows[-1]==dict(status='PASS',command=rows[-1]['command'],**returned,basis=c.sha(basis[1]),captured=basis[2]['accepted']),'certificate returned original binding')
    if clean:
        rows=output('first','certify');need(g.events(rows)==list(c.OPEN+p.SEAL+CUTS),'certificate force order');success(rows)
        rows=output('duplicate','certify');need(g.events(rows)==list(c.OPEN+SEAL+('CERTIFICATE_BEFORE_RETURN',)),'certificate duplicate order');success(rows)
        rows=output('accept-duplicate','accept-duplicate');need(g.events(rows)==list(c.OPEN+SEAL+('ACCEPT_BEFORE_RETURN',)),'certificate ACCEPT duplicate order');success(rows)
        rows=output('proof-duplicate','proof-duplicate');need(g.events(rows)==list(c.OPEN+SEAL+('PROOF_BEFORE_RETURN',)),'certificate PROOF duplicate order');success(rows)
        need(inventory(root/'original')==inventory(root/'duplicate')==state(),'certificate preserved duplicate bytes')
    else:
        point='CERTIFICATE_CANDIDATE_WRITTEN' if repeat else case['cut'];rows=output('fault','certify',73 if repeat or mode=='halt' else -9);order=c.OPEN+p.SEAL+CUTS
        need(g.events(rows)==list(order[:order.index(point)+1])+(['AWAITING_KILL'] if not repeat and mode=='kill' else []),'certificate crash order')
        if not repeat and mode=='kill':need(rows[-1]==dict(event='AWAITING_KILL',cut=point),'certificate kill handshake')
        need(inventory(root/'crash')==state(point),'certificate exact crash snapshot');position=CUTS.index(point)
        if repeat:
            rows=output('recovery-fault','certify',73 if mode=='halt' else -9);order=c.OPEN+RECOVERY+SEAL+('CERTIFICATE_BEFORE_RETURN',)
            need(g.events(rows)==list(order[:order.index(case['cut'])+1])+(['AWAITING_KILL'] if mode=='kill' else []),'certificate recovery order')
            if mode=='kill':need(rows[-1]==dict(event='AWAITING_KILL',cut=case['cut']),'certificate recovery kill handshake')
            position=3 if case['cut'] in RECOVERY[:4] else CUTS.index(case['cut']) if case['cut'] in CUTS else len(CUTS)
            need(inventory(root/'recovery-crash')==state(None if position>=len(CUTS) else CUTS[position]),'certificate exact recovery snapshot')
        rows=output('resume','certify')
        if position>=CUTS.index('CERTIFICATE_RENAMED'):order=c.OPEN+SEAL+('CERTIFICATE_BEFORE_RETURN',)
        elif position>=3:order=c.OPEN+RECOVERY+SEAL+('CERTIFICATE_BEFORE_RETURN',)
        elif position>=1:order=c.OPEN+p.SEAL+('CERTIFICATE_VALIDATED',)+CUTS[2:]
        else:order=c.OPEN+p.SEAL+CUTS
        need(g.events(rows)==list(order),'certificate resume order');success(rows);need(inventory(root/'resumed')==state(),'certificate resumed bytes')
    rows=output('capture','capture');need(g.events(rows)==list(c.OPEN+SEAL+capture.ORDER[len(c.OPEN):]),'certificate capture order');success(rows,True)
    rows=output('inspect','inspect');need(g.events(rows)==list(c.OPEN+SEAL),'certificate inspect order');success(rows,True)
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,networkAck=False)


def validate(root):
    root=Path(root);need({v.name for v in root.iterdir()}=={v['name'] for v in cases()},'certificate complete case set')
    return dict(status='PASS',execution='private-pending-certificate',cases=[validate_case(root/v['name'],v) for v in cases()])
