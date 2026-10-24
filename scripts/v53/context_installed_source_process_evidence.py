"""Fresh-process recovery of an obsolete installed source and exact successor vote."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_installation_lifetime_evidence as lifetime
from . import context_completion_process_evidence as completion
from . import context_capture_process_evidence as capture_process

selection=lifetime.selection
e,owner,source=lifetime.e,lifetime.owner,lifetime.source
backing=selection.retirement
POINTS=(*source.CUTS,'SOURCE_RETIREMENT_FILE_DELETED@2')


def events(names):return [dict(event=name) for name in names]


def plan(root):
    lifetime.validate(root/'reference')
    initial,dirs=owner.read_snapshot(root/'reference/round-23/generation-retired/node-1')
    selection.capture.match(root/'initial',initial,dirs,'installed process seed')
    prior=e.decode((root/'reference/round-22/source-retired/node-1/pending.context').read_bytes())[0][3]
    old=e.f.decode(prior,'records','BASIS')['basisId']
    authority,compact,steps=backing.retirement(initial,dirs,old)
    clean,clean_dirs=owner.read_snapshot(root/'reference/round-23/source-retired/node-1')
    e.need(backing.inventory(clean,clean_dirs)==steps[-1][1],'installed process reference reclamation')
    accepted_files,_=lifetime.installation.accepted(clean,clean_dirs)
    vote=accepted_files['pending.accept'];_,installed,packet=e.current(clean)
    promise=e.f.decode(installed['promise.gsr'],'records','PROMISE')
    _,values=e.votes(clean['pending.accept'],packet['capsule']['cut'])
    new_accept=e.f.encode('records','ACCEPT',dict(values['ACCEPT'],ballot=promise['ballot']))
    release=e.f.encode('records','RETIREMENT',dict(root=promise['root'],node='node-1',floor=e.digest(clean['floor-copies/floor.gsr']),
        selector=e.digest(clean['selector.gsr']),files=[dict(path=n,size=len(raw),sha256=e.digest(raw)) for n,raw in sorted(clean.items()) if n.startswith('floor-copies/')]))
    accept_steps=completion.a.transition(steps[-1][1],vote,release,acknowledge=True)
    return initial,dirs,authority,compact,old,steps,accept_steps,new_accept


def validate(root):
    root=Path(root);names={mode+'-'+point for mode in ('halt','kill') for point in POINTS}
    selection.layout(root,names|{'reference','initial','inputs.json','receipt.json'},'installed source process')
    initial,dirs,authority,compact,old,steps,accept_steps,new_accept=plan(root)
    inputs=source.load(root/'inputs.json');e.exact(inputs,'observations')
    e.need(type(inputs['observations']) is list and len(inputs['observations'])<=512,'installed process observation bound')
    for row in inputs['observations']:
        e.exact(row,'voter storage record parent')
        for key,kind in (('voter','node'),('storage','uuid'),('record','hash'),('parent','hash')):e.f.check_type(row[key],kind,{})
    receipt_rows=[]
    prefix=list(selection.CURRENT)+capture_process.retain_seal(initial)+['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED']
    for mode in ('halt','kill'):
        for point in POINTS:
            name=mode+'-'+point;case=root/name
            selection.layout(case,{'store','crash','recovery-crash','recovered','final'}|
                             {label+ext for label in ('fault','recovery','resume') for ext in ('.stdout','.stderr')},'installed source process member')
            for label in ('fault','recovery','resume'):
                path=case/(label+'.stderr');e.need(path.is_file() and not path.is_symlink() and path.stat().st_size==0,'installed process stderr')
            fault,recovery,resume=[completion.trace(case/(label+'.stdout')) for label in ('fault','recovery','resume')]
            at=completion.stop(steps,point);crash=steps[at][1]
            e.need(source.state(case/'crash')==crash,'installed process first physical prefix')
            e.need(source.state(case/'recovery-crash')==crash,'installed process second physical prefix')
            expected=events(prefix+['OPEN_RETURNED']+[name for name,_ in steps[:at+1]])
            if mode=='kill':expected.append(dict(event='AWAITING_KILL',cut=point))
            e.need(fault==expected,'installed process first force/death order')
            second=list(selection.CURRENT)+['CONTEXT_OWNER_VALIDATED']+capture_process.source_seal(initial)
            e.need(recovery==events(second),'installed process second force/death order')
            e.need(source.state(case/'recovered')==steps[-1][1],'installed process recovered authority')
            e.need(source.state(case/'final')==source.state(case/'store')==accept_steps[-1][1],'installed process final successor')
            resumed=backing.release.transaction(crash,authority,compact,old)
            crash_files,_=owner.read_snapshot(case/'crash');automatic=bool(crash_files.get(backing.release.AUTHORITY,b''))
            order=prefix+([name for name,_ in resumed] if automatic else [])+['OPEN_RETURNED']
            if not automatic:order += [name for name,_ in resumed]
            order+=capture_process.retain_seal(initial)+['RECOVERED']+[name for name,_ in accept_steps]
            returned=dict(event='RETURNED_ACCEPT',record=e.digest(new_accept))
            expected=events(order)+[returned,dict(event='ACCEPT_BEFORE_RETURN'),returned,
                                  dict(status='PASS',accept=e.digest(new_accept),peakImages=7,runtimeEnabled=False)]
            e.need(resume==expected,'installed process resume force/ack order')
            receipt_rows.append(dict(case=name,mode=mode,cut=point,status='PASS',exitCodes=[73 if mode=='halt' else 137,73,0]))
    expected=dict(schema='gse-v53-context-installed-source-process-v1',status='PASS',cases=receipt_rows,expectedCases=30,freshProcesses=90,lockProbes=15,
                  inputsSha256=e.digest((root/'inputs.json').read_bytes()),historicalBootstrap='conditional-fixture',powerLoss=False,runtimeEnabled=False)
    e.need(source.load(root/'receipt.json')==expected,'installed process receipt scope/inputs')
    return dict(status='PASS',cases=30,freshProcesses=90,lockProbes=15,originalFirst=True,originalVote=20,installedBallot=23,retiredSourceBallot=22,
                peakReservedImages=7,powerLoss=False,runtimeEnabled=False,historicalBootstrap='conditional-fixture')


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'reference':'context publication exact source-retired: node-1','missing':'context selection installed source process inventory',
              'initial':'context capture exact installed process seed','first':'installed process first physical prefix',
              'second':'installed process second physical prefix','recovered':'installed process recovered authority',
              'final':'installed process final successor','source':'installed process final successor',
              'first-force':'installed process first force/death order','second-force':'installed process second force/death order',
              'resume-force':'installed process resume force/ack order','early-ack':'installed process second force/death order',
              'wrong-ack':'installed process resume force/ack order','scope':'installed process receipt scope/inputs',
              'inputs':'installed process receipt scope/inputs','capacity':'installed process resume force/ack order',
              'stderr':'installed process stderr','link':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-installed-source-process-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'halt-SOURCE_RETIREMENT_CREATED'
            if name=='reference':(moved/'reference/reference/carried-snapshots/source-retired/node-1/pending.accept').write_bytes(b'changed')
            elif name=='missing':shutil.rmtree(case)
            elif name in ('initial','first','second','recovered','final'):
                path=moved/'initial' if name=='initial' else case/{'first':'crash','second':'recovery-crash','recovered':'recovered','final':'final'}[name]
                (path/'pending.accept').write_bytes(b'changed')
            elif name=='source':next((case/'final/sources').glob('*/source.gscp')).unlink()
            elif name in ('first-force','second-force','resume-force','early-ack','wrong-ack','capacity'):
                label='fault' if name=='first-force' else 'recovery' if name in ('second-force','early-ack') else 'resume'
                path=case/(label+'.stdout');rows=completion.trace(path)
                if name=='first-force':rows.remove(dict(event='SOURCE_RETIREMENT_CREATED'))
                elif name=='second-force':rows.remove(dict(event='CONTEXT_SOURCE_PARENT_FORCED'))
                elif name=='resume-force':rows.remove(dict(event='SOURCE_RETIREMENT_FORCED'))
                elif name=='early-ack':rows.append(dict(event='RETURNED_ACCEPT',record='0'*64))
                elif name=='wrong-ack':next(row for row in rows if row.get('event')=='RETURNED_ACCEPT')['record']='0'*64
                else:rows[-1]['peakImages']=8
                path.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in rows))
            elif name in ('scope','inputs'):
                path=moved/('receipt.json' if name=='scope' else 'inputs.json');value=source.load(path)
                if name=='scope':value['freshProcesses']=89
                else:value['observations'].reverse()
                path.write_bytes(e.f.canonical(value))
            elif name=='stderr':(case/'fault.stderr').write_bytes(b'error')
            else:
                path=case/'final/pending.accept';path.unlink();path.symlink_to((root/'initial/pending.accept').resolve())
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong installed process negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted installed process mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-installed-source-process-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'installed source process portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
