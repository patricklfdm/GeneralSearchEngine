"""Exact selected-generation and intermediate-retirement process recovery replay."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_installation_lifetime_evidence as lifetime
from . import context_completion_process_evidence as completion
from . import context_capture_process_evidence as capture_process

installation=lifetime.installation
selection=installation.selection
e,owner,source=lifetime.e,lifetime.owner,lifetime.source
INSTALL_POINTS=(*installation.install.CUTS,'INSTALL_MEMBER_WRITTEN@2')
RETIRE_POINTS=(*installation.retirement.CUTS[:25],'RETIREMENT_FILE_DELETED@2','RETIREMENT_SAVED_FILE_DELETED@2')


def events(names):return [dict(event=name) for name in names]


def trace(path):
    e.need(path.is_file() and not path.is_symlink() and path.stat().st_size<=1024*1024,'generation process trace bound/type')
    raw=path.read_bytes();lines=raw.splitlines()
    e.need(raw.endswith(b'\n') and 0<len(lines)<=4096,'generation process complete trace')
    rows=[e.parse(line) for line in lines]
    e.need(all(type(row) is dict for row in rows) and b''.join(e.f.canonical(row)+b'\n' for row in rows)==raw,'generation process canonical trace')
    return rows


def plan(root):
    lifetime.validate(root/'reference')
    selected=selection.states(root/'reference/round-22/selected')
    installed,dirs=owner.read_snapshot(root/'reference/round-22/installed/node-1')
    _,members,packet=e.current(installed)
    members=dict(members,**{'generation.gsr':installed['generations/a/generation.gsr']})
    install_steps=installation.install_steps(*selected['node-1'],members,installed['selector.gsr'])
    _,old,authority,retire_steps=installation.retirement_steps(installed,dirs)
    clean,clean_dirs=lifetime.retire_generation(installed,dirs)
    accepted_files,_=installation.accepted(clean,clean_dirs)
    vote=accepted_files['pending.accept'];promise=e.f.decode(members['promise.gsr'],'records','PROMISE')
    _,values=e.votes(clean['pending.accept'],packet['capsule']['cut'])
    accepted=e.f.encode('records','ACCEPT',dict(values['ACCEPT'],ballot=promise['ballot']))
    floor=e.f.encode('records','RETIREMENT',dict(root=promise['root'],node='node-1',floor=e.digest(clean['floor-copies/floor.gsr']),
        selector=e.digest(clean['selector.gsr']),files=[dict(path=n,size=len(raw),sha256=e.digest(raw)) for n,raw in sorted(clean.items()) if n.startswith('floor-copies/')]))
    accept_steps=completion.a.transition(retire_steps[-1][1],vote,floor,acknowledge=True)
    return selected,install_steps,retire_steps,old,authority,accepted,accept_steps,e.digest(members['generation.gsr'])


def validate(root):
    root=Path(root);cases=[(operation,mode,point) for operation,points in [('install',INSTALL_POINTS),('retire',RETIRE_POINTS)] for mode in ('halt','kill') for point in points]
    selection.layout(root,{'reference','inputs.json','receipt.json'}|{'-'.join(v) for v in cases},'generation process')
    selected,installs,retires,old,authority,accepted,accepts,manifest=plan(root)
    initial=selected['node-1'][0];full=capture_process.retain_seal(initial)
    opening=list(selection.CURRENT)+full+['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED','OPEN_RETURNED']
    second=list(selection.CURRENT)+['CONTEXT_OWNER_VALIDATED']+capture_process.source_seal(initial)
    inputs=source.load(root/'inputs.json');e.exact(inputs,'observations')
    e.need(type(inputs['observations']) is list and len(inputs['observations'])<=512,'generation process observation bound')
    for row in inputs['observations']:
        e.exact(row,'voter storage record parent')
        for key,kind in (('voter','node'),('storage','uuid'),('record','hash'),('parent','hash')):e.f.check_type(row[key],kind,{})
    rows=[]
    for operation,mode,point in cases:
        name='-'.join((operation,mode,point));case=root/name
        selection.layout(case,{'store','peers','crash','recovery-crash','recovered','final'}|
                         {label+ext for label in ('fault','recovery','resume') for ext in ('.stdout','.stderr')},'generation process member')
        selection.layout(case/'peers',{'node-2','node-3'},'generation process peers')
        for node in ('node-2','node-3'):selection.capture.match(case/'peers'/node,*selected[node],'generation process exact peer')
        for label in ('fault','recovery','resume'):
            path=case/(label+'.stderr');e.need(path.is_file() and not path.is_symlink() and path.stat().st_size==0,'generation process stderr')
        fault,recovery,resume=[trace(case/(label+'.stdout')) for label in ('fault','recovery','resume')]
        steps=installs if operation=='install' else retires
        at=completion.stop([(s[0],None) for s in steps],point)
        physical=selection.retirement.inventory(*steps[at][1:]) if operation=='install' else steps[at][1]
        e.need(source.state(case/'crash')==physical,'generation process first physical prefix')
        e.need(source.state(case/'recovery-crash')==physical,'generation process second physical prefix')
        first=events(opening+([] if operation=='install' else full)+[s[0] for s in steps[:at+1]])
        if mode=='kill':first.append(dict(event='AWAITING_KILL',cut=point))
        e.need(fault==first,'generation process first force/death order')
        e.need(recovery==events(second),'generation process second force/death order')
        e.need(source.state(case/'recovered')==retires[-1][1],'generation process recovered authority')
        e.need(source.state(case/'final')==source.state(case/'store')==accepts[-1][1],'generation process final successor')
        expected=events(opening)
        if operation=='install':
            persisted=at>=next(i for i,s in enumerate(installs) if s[0]=='INSTALL_SELECTOR_RENAMED')
            if not persisted:expected+=events([s[0] for s in installs])
            expected+=[dict(event='RETURNED_INSTALL',manifest=manifest)]*2
            retirement_steps=retires
        else:retirement_steps=installation.retirement.transaction(physical,old,authority,slot='b')[0]
        expected+=events(full+[s[0] for s in retirement_steps])+[dict(event='RETURNED_RETIRE')]*2
        expected+=events(full+['RECOVERED']+[s[0] for s in accepts])
        returned=dict(event='RETURNED_ACCEPT',record=e.digest(accepted))
        expected += [returned,dict(event='ACCEPT_BEFORE_RETURN'),returned,dict(status='PASS',accept=e.digest(accepted),peakImages=7,runtimeEnabled=False)]
        e.need(resume==expected,'generation process resume force/ack order')
        rows.append(dict(case=name,operation=operation,mode=mode,cut=point,status='PASS',exitCodes=[73 if mode=='halt' else 137,73,0]))
    expected=dict(schema='gse-v53-context-generation-process-v1',status='PASS',cases=rows,expectedCases=84,freshProcesses=252,lockProbes=42,
                  inputsSha256=e.digest((root/'inputs.json').read_bytes()),historicalBootstrap='conditional-fixture',powerLoss=False,runtimeEnabled=False)
    e.need(source.load(root/'receipt.json')==expected,'generation process receipt scope/inputs')
    return dict(status='PASS',cases=84,installationCases=30,retirementCases=54,freshProcesses=252,lockProbes=42,originalFirst=True,
                originalVote=20,installedBallot=22,peakReservedImages=7,powerLoss=False,runtimeEnabled=False,historicalBootstrap='conditional-fixture')


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'reference':'context publication exact source-retired: node-1','missing':'context selection generation process inventory',
              'peer':'context capture exact generation process exact peer',
              'first-install':'generation process first physical prefix','first-retire':'generation process first physical prefix',
              'second':'generation process second physical prefix','recovered':'generation process recovered authority',
              'final':'generation process final successor','source':'generation process final successor',
              'first-force':'generation process first force/death order','second-force':'generation process second force/death order',
              'resume-force':'generation process resume force/ack order','early-ack':'generation process second force/death order',
              'wrong-install':'generation process resume force/ack order','wrong-accept':'generation process resume force/ack order',
              'scope':'generation process receipt scope/inputs','inputs':'generation process receipt scope/inputs',
              'capacity':'generation process resume force/ack order','stderr':'generation process stderr','link':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-generation-process-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'install-halt-INSTALL_RESERVED'
            if name=='reference':(moved/'reference/reference/carried-snapshots/source-retired/node-1/pending.accept').write_bytes(b'changed')
            elif name=='missing':shutil.rmtree(case)
            elif name=='peer':(case/'peers/node-2/pending.accept').write_bytes(b'changed')
            elif name in ('first-install','first-retire','second','recovered','final'):
                if name=='first-retire':case=moved/'retire-halt-RETIREMENT_OLD_FILES_FORCED'
                directory='crash' if name.startswith('first-') else 'recovery-crash' if name=='second' else name
                (case/directory/'pending.accept').write_bytes(b'changed')
            elif name=='source':next((case/'final/sources').glob('*/source.gscp')).unlink()
            elif name in ('first-force','second-force','resume-force','early-ack','wrong-install','wrong-accept','capacity'):
                label='fault' if name=='first-force' else 'recovery' if name in ('second-force','early-ack') else 'resume'
                path=case/(label+'.stdout');values=trace(path)
                if name=='first-force':values.remove(dict(event='INSTALL_RESERVED'))
                elif name=='second-force':values.remove(dict(event='CONTEXT_SOURCE_PARENT_FORCED'))
                elif name=='resume-force':values.remove(dict(event='INSTALL_PARENT_FORCED'))
                elif name=='early-ack':values.append(dict(event='RETURNED_INSTALL',manifest='0'*64))
                elif name=='wrong-install':next(row for row in values if row.get('event')=='RETURNED_INSTALL')['manifest']='0'*64
                elif name=='wrong-accept':next(row for row in values if row.get('event')=='RETURNED_ACCEPT')['record']='0'*64
                else:values[-1]['peakImages']=8
                path.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in values))
            elif name in ('scope','inputs'):
                path=moved/('receipt.json' if name=='scope' else 'inputs.json');value=source.load(path)
                if name=='scope':value['freshProcesses']=251
                else:value['observations'].reverse()
                path.write_bytes(e.f.canonical(value))
            elif name=='stderr':(case/'fault.stderr').write_bytes(b'error')
            else:
                path=case/'final/pending.accept';path.unlink();path.symlink_to((root/'reference/round-22/selected/node-1/pending.accept').resolve())
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong generation process negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted generation process mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-generation-process-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'generation process portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
