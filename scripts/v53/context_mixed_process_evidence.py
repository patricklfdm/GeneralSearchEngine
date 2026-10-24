"""Mixed ACCEPT original authority through two real process deaths per case."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_mixed_recovery_evidence as recovery
from . import context_completion_process_evidence as completion
from . import context_capture_process_evidence as capture

mixed=recovery.mixed
e,owner,source=mixed.e,mixed.owner,mixed.source
ACCEPT_POINTS=(*recovery.acceptance.CUTS,'FLOOR_RELEASE_FILE_DELETED@2')
SOURCE_POINTS=(*source.CUTS,'SOURCE_RETIREMENT_FILE_DELETED@2')
CURRENT=list(mixed.selection.CURRENT)
SEAL=list(recovery.acceptance.accept.SEAL)


def events(names):return [dict(event=n) for n in names]


def validate(root):
    root=Path(root);names={mode+'-'+point for mode in ('halt','kill') for point in (*ACCEPT_POINTS,*SOURCE_POINTS)}
    mixed.selection.layout(root,names|{'reference','inputs.json','receipt.json'},'mixed process')
    mixed.validate(root/'reference');inputs=source.load(root/'inputs.json');e.exact(inputs,'observations')
    e.need(type(inputs['observations']) is list and len(inputs['observations'])<=512,'mixed process observation bound')
    for row in inputs['observations']:
        e.exact(row,'voter storage record parent')
        for key,kind in (('voter','node'),('storage','uuid'),('record','hash'),('parent','hash')):e.f.check_type(row[key],kind,{})
    receipt=[]
    for accept,points in ((True,ACCEPT_POINTS),(False,SOURCE_POINTS)):
        initial,transition=recovery.plan(root,accept);steps=transition(initial,True);final=steps[-1][1]
        original=mixed.carried.inventory(root/'reference'/('round-24/source-retired/node-1' if accept else 'retired/node-2'))
        prefix=CURRENT+capture.retain_seal(original)+(['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED'] if accept else SEAL)
        for mode in ('halt','kill'):
            for point in points:
                name=mode+'-'+point;case=root/name;operation='accept' if accept else 'source-retirement'
                mixed.selection.layout(case,{'store','crash','recovery-crash','final'}|{n+s for n in ('fault','recovery','resume') for s in ('.stdout','.stderr')},'mixed process case')
                for label in ('fault','recovery','resume'):
                    p=case/(label+'.stderr');e.need(p.is_file() and not p.is_symlink() and p.stat().st_size==0,'mixed process stderr')
                fault,second_trace,resume=[completion.trace(case/(label+'.stdout')) for label in ('fault','recovery','resume')]
                at=completion.stop(steps,point);crash=steps[at][1]
                e.need(source.state(case/'crash')==crash,'mixed process first prefix')
                expected=events(prefix+['OPEN_RETURNED']+[n for n,_ in steps[:at+1]])
                if mode=='kill':expected.append(dict(event='AWAITING_KILL',cut=point))
                e.need(fault==expected,'mixed process first force/death order')
                if accept:
                    if owner.ACTIVE in crash:
                        second_steps=transition(crash,False);stop=completion.stop(second_steps,'ACCEPT_ACTIVE_FORCED');second=second_steps[stop][1]
                        partial='pending.accept.next' in crash or crash['pending.accept']!=initial['pending.accept']
                        opening=CURRENT if partial else prefix+['OPEN_RETURNED']
                        second_order=opening+[n for n,_ in second_steps[:stop+1]]
                    else:second=crash;second_order=CURRENT+['ACCEPT_ACTIVE_FORCED']
                else:second=crash;second_order=CURRENT+['CONTEXT_OWNER_VALIDATED']+capture.source_seal(original)
                e.need(source.state(case/'recovery-crash')==second,'mixed process second prefix')
                e.need(second_trace==events(second_order),'mixed process second force/death order')
                e.need(source.state(case/'final')==source.state(case/'store')==final,'mixed process final authority')
                continued=[n for n,_ in transition(second,False)]
                if accept:
                    accepted=mixed.carried.pending(mixed.accept(original)['pending.accept'])[0]['ACCEPT']
                    returned=dict(event='EXPLICIT_ACCEPT_RETURNED',record=e.digest(accepted))
                    if owner.ACTIVE in second:order=CURRENT+continued+SEAL+['OPEN_RETURNED']
                    elif recovery.acceptance.floor.RELEASE in second:order=CURRENT+SEAL+continued+['OPEN_RETURNED']
                    else:order=CURRENT+SEAL+['OPEN_RETURNED']+continued
                    expected=events(order)+[dict(event='ACCEPT_BEFORE_RETURN'),returned,dict(event='ACCEPT_BEFORE_RETURN'),returned]
                else:
                    automatic=bool(second.get(source.release.AUTHORITY,{}).get('bytes',0))
                    order=prefix+(continued if automatic else [])+['OPEN_RETURNED']+([] if automatic else continued)+capture.retain_seal(original)+['EXPLICIT_RETIRE_RETURNED']
                    expected=events(order)
                e.need(resume[:-1]==expected,'mixed process resumed force/return order')
                last=resume[-1];e.exact(last,'status operation peakImages runtimeEnabled')
                e.need(last==dict(status='PASS',operation=operation,peakImages=last['peakImages'],runtimeEnabled=False)
                       and type(last['peakImages']) is int and 5<=last['peakImages']<=7,'mixed process result capacity/scope')
                receipt.append(dict(case=name,operation=operation,mode=mode,cut=point,status='PASS',exitCodes=[73 if mode=='halt' else 137,73,0]))
    expected=dict(schema='gse-v53-context-mixed-process-v1',status='PASS',cases=receipt,expectedCases=84,freshProcesses=252,lockProbes=42,
        inputsSha256=e.digest((root/'inputs.json').read_bytes()),historicalBootstrap='conditional-fixture',powerLoss=False,runtimeEnabled=False)
    e.need(source.load(root/'receipt.json')==expected,'mixed process receipt/inputs')
    return dict(status='PASS',cases=84,freshProcesses=252,lockProbes=42,originalFirst=True,entryOrigin=20,acceptBallot=24,sourceRetirementBallot=21,
                powerLoss=False,runtimeEnabled=False,historicalBootstrap='conditional-fixture',maximalCapacity=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={
        'original':'mixed exact accepted: node-1',
        'missing':'context selection mixed process inventory',
        'accept-first':'mixed process first prefix',
        'accept-second':'mixed process second prefix',
        'accept-final':'mixed process final authority',
        'source-first':'mixed process first prefix',
        'source-second':'mixed process second prefix',
        'source-final':'mixed process final authority',
        'retained-context':'mixed process final authority',
        'retained-floor':'mixed process final authority',
        'lost-source':'mixed process final authority',
        'first-force':'mixed process first force/death order',
        'second-force':'mixed process second force/death order',
        'resume-force':'mixed process resumed force/return order',
        'early-return':'mixed process second force/death order',
        'wrong-return':'mixed process resumed force/return order',
        'wrong-kill-marker':'mixed process first force/death order',
        'capacity':'mixed process result capacity/scope',
        'scope':'mixed process receipt/inputs',
        'inputs':'mixed process receipt/inputs',
        'stderr':'mixed process stderr',
        'linked-vote':'owner context linked/nonregular member',
    }
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-mixed-process-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved)
            case=moved/('halt-'+(SOURCE_POINTS[0] if name.startswith('source-') else ACCEPT_POINTS[0]))
            if name=='original':(moved/'reference/accepted/node-1/allocator.gsr').write_bytes(b'changed')
            elif name=='missing':shutil.rmtree(case)
            elif name.startswith(('accept-','source-')):
                stage={'first':'crash','second':'recovery-crash','final':'final'}[name.split('-')[1]]
                (case/stage/'pending.accept').write_bytes(b'changed')
            elif name=='retained-context':shutil.copyfile(moved/'reference/round-24/source-retired/node-1/pending.context',case/'final/pending.context')
            elif name=='retained-floor':shutil.copytree(moved/'reference/round-24/source-retired/node-1/floor-copies',case/'final/floor-copies')
            elif name=='lost-source':next((case/'final/sources').glob('*/source.gscp')).unlink()
            elif name in ('scope','inputs'):
                path=moved/('receipt.json' if name=='scope' else 'inputs.json');value=source.load(path)
                if name=='scope':value['freshProcesses']=251
                else:value['observations'].reverse()
                path.write_bytes(e.f.canonical(value))
            elif name=='stderr':(case/'fault.stderr').write_bytes(b'error')
            elif name=='linked-vote':
                path=case/'final/pending.accept';path.unlink();path.symlink_to((root/case.name/'final/pending.accept').resolve())
            else:
                if name=='wrong-kill-marker':case=moved/('kill-'+ACCEPT_POINTS[0])
                label='fault' if name in ('first-force','wrong-kill-marker') else 'recovery' if name in ('second-force','early-return') else 'resume'
                path=case/(label+'.stdout');rows=completion.trace(path)
                if name=='first-force':rows.remove(dict(event=ACCEPT_POINTS[0]))
                elif name=='second-force':rows.remove(dict(event='ACCEPT_ACTIVE_FORCED'))
                elif name=='resume-force':rows.remove(dict(event='ACCEPT_ACTIVE_PARENT_FORCED'))
                elif name=='early-return':rows.append(dict(event='EXPLICIT_ACCEPT_RETURNED',record='0'*64))
                elif name=='wrong-return':next(row for row in rows if row.get('event')=='EXPLICIT_ACCEPT_RETURNED')['record']='0'*64
                elif name=='wrong-kill-marker':rows[-1]['cut']='ACCEPT_RENAMED'
                else:rows[-1]['peakImages']=8
                path.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in rows))
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong mixed process negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted mixed process mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-mixed-process-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'mixed process portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
