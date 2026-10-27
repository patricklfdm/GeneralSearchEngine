"""Exact process snapshots after replay of the original inherited REMOVE chain."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import inherited_adoption_evidence as original
from . import admitted_adoption_process_evidence as prior

u,s,p,c,f,e,need=original.u,original.s,original.p,original.c,original.f,original.e,original.need
CUTS=('ADOPTION_INSTALL_FENCED','INSTALL_SELECTOR_FORCED','INSTALL_SELECTOR_RENAMED',
      'RETENTION_PREFIX_WRITTEN','RETENTION_RENAMED','INHERITED_FUTURE_RETENTION_PROMOTED','ADOPTION_INSTALL_BEFORE_RETURN')


def trace(path):
    return [json.loads(line) for line in p.t.plans.read(path,1024*1024).decode().splitlines()]


def record(path):
    return json.loads(p.t.plans.read(path,1024*1024))


def validate_case(root,inputs,states,mode,cut):
    before,switched,final=states;path=root/(mode+'-'+cut)
    expected={'interrupted','recovered'}|{label+ext for label in ('fault','resume') for ext in ('.stdout','.stderr','.exit.json')}
    if mode=='kill':expected|={'lock.stdout','lock.stderr','lock.exit.json'}
    p.selection.layout(path,expected,'inherited adoption process case')
    need(all((path/(label+'.stderr')).read_bytes()==b'' for label in ('fault','resume')),'inherited adoption process stderr')
    stopped=dict(switched)
    if cut=='ADOPTION_INSTALL_FENCED':stopped=dict(before,**{'grants.gsr':switched['grants.gsr']})
    elif cut=='INSTALL_SELECTOR_FORCED':stopped.update({'selector.gsr':before['selector.gsr'],'selector.pending.gsr':final['selector.gsr']})
    elif cut=='RETENTION_PREFIX_WRITTEN':stopped[s.NEXT]=final[s.FILE][:len(final[s.FILE])//2]
    elif cut in CUTS[4:]:stopped[s.FILE]=final[s.FILE]
    need(c.inventory(path/'interrupted')==stopped,'inherited adoption exact interrupted files')
    need(c.inventory(path/'recovered')==final,'inherited adoption exact recovered files')
    rows=trace(path/'fault.stdout');events=[row.get('event') for row in rows]
    need(bool(rows) and all(set(row)=={'event'} for row in (rows[:-1] if mode=='kill' else rows)),
         'inherited adoption interrupted trace fields')
    if mode=='kill':
        need(rows[-1]==dict(event='AWAITING_KILL',cut=cut),'inherited adoption exact kill marker');events=events[:-1]
    need(events[-1]==cut and not any('status' in row for row in rows),'inherited adoption interrupted before response')
    required=['ADOPTION_INSTALL_VALIDATED','ADOPTION_INSTALL_FENCED']
    if cut!=CUTS[0]:required+=['INSTALL_GENERATION_FORCED','INSTALL_SELECTOR_WRITTEN','INSTALL_SELECTOR_FORCED']
    if cut in CUTS[2:]:required+=['INSTALL_SELECTOR_RENAMED']
    if cut in CUTS[3:]:required+=['INSTALL_PARENT_FORCED','RETENTION_PREFIX_WRITTEN']
    if cut in CUTS[4:]:required+=['RETENTION_FORCED','RETENTION_CANDIDATE_PARENT_FORCED','RETENTION_RENAMED']
    if cut in CUTS[5:]:required+=['RETENTION_PARENT_FORCED','INHERITED_FUTURE_RETENTION_PROMOTED']
    if cut==CUTS[-1]:required+=['ADOPTION_INSTALL_BEFORE_RETURN']
    s.ordered(events,required,'inherited adoption interruption')
    resumed=trace(path/'resume.stdout')
    need(resumed and set(resumed[-1])=={'status','peakImages','runtimeEnabled'} and resumed[-1]['status']=='PASS'
         and resumed[-1]['runtimeEnabled'] is False and type(resumed[-1]['peakImages']) is int and 0<resumed[-1]['peakImages']<=7
         and all(set(row)=={'event'} for row in resumed[:-1]),'inherited adoption resumed response')
    recovery=[row['event'] for row in resumed[:-1]]
    if cut in CUTS[:4]:s.ordered(recovery,['RETENTION_FORCED','RETENTION_PARENT_FORCED','INHERITED_FUTURE_RETENTION_PROMOTED'],'inherited adoption resumed promotion')
    need(record(path/'fault.exit.json')==dict(exitCode=73 if mode=='halt' else 137,cut=cut,mode=mode),'inherited adoption exact death exit')
    need(record(path/'resume.exit.json')==dict(exitCode=0,cut='none',mode='none'),'inherited adoption exact resume exit')
    if mode=='kill':
        need((path/'lock.stderr').read_bytes()==b'' and trace(path/'lock.stdout')==[dict(event='LOCK_HELD',path=inputs['node']+'/replica.lock')]
             and record(path/'lock.exit.json')==dict(exitCode=0),'inherited adoption live ownership lock')
    return dict(mode=mode,cut=cut,status='PASS',exitCodes=[73 if mode=='halt' else 137,0])


def validate(root,with_states=False, *, selected_prefix=None):
    root=Path(root);p.selection.layout(root,{'reference','cases','inputs.json','receipt.json'},'inherited adoption process matrix')
    original_result,states=original.validate(root/'reference',with_states=True,selected_prefix=selected_prefix)
    plan=prior.t.plans.decode((root/'reference/original-plan.gsbp').read_bytes(),(root/'reference/original-application.image').read_bytes(),details=True,size=4,source='EMPTY')
    descriptor=plan['plan']['descriptor'];node=prior.target_paths(descriptor,'node-4');source=prior.target_paths(descriptor,'node-1')
    inputs=record(root/'inputs.json')
    need(inputs==dict(**node,source=source['node'],sourceMaterialization=source['materialization']),'inherited adoption original owner paths')
    p.selection.layout(root/'cases',{mode+'-'+cut for mode in ('halt','kill') for cut in CUTS},'inherited adoption exact cuts')
    rows=[validate_case(root/'cases',inputs,states,mode,cut) for mode in ('halt','kill') for cut in CUTS]
    need(record(root/'receipt.json')==dict(schema='gse-v53-inherited-adoption-process-v1',status='PASS',cases=rows,
         freshProcesses=28,lockProbes=7,publicRuntime=False,powerLoss=False),'inherited adoption process receipt')
    result=dict(status='PASS',original=original_result,cases=14,freshProcesses=28,lockProbes=7,powerLoss=False,phase3Complete=False)
    return (result,inputs,states) if with_states else result


def qualify(root, *, selected_prefix=None):
    root=Path(root);result,inputs,states=validate(root,with_states=True,selected_prefix=selected_prefix);history=original.qualify(root/'reference',selected_prefix=selected_prefix);negatives=[]
    cut='RETENTION_PREFIX_WRITTEN';mode='kill';name=mode+'-'+cut
    variants=[('interrupted-selector','inherited adoption exact interrupted files'),('candidate-ledger','inherited adoption exact interrupted files'),
              ('recovered-proof','inherited adoption exact recovered files'),('force','selected retention force order: inherited adoption interruption'),
              ('lock','inherited adoption live ownership lock'),('exit','inherited adoption exact death exit'),('response','inherited adoption resumed response')]
    for variant,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-inherited-adoption-process-negative-') as temp:
            target=Path(temp);case=target/name;shutil.copytree(root/'cases'/name,case)
            if variant=='interrupted-selector':(case/'interrupted/selector.gsr').write_bytes(states[0]['selector.gsr'])
            elif variant=='candidate-ledger':(case/'interrupted'/s.NEXT).write_bytes(states[0][s.FILE])
            elif variant=='recovered-proof':(case/'recovered'/s.FILE).write_bytes(states[0][s.FILE])
            elif variant=='force':
                path=case/'fault.stdout';rows=trace(path);rows.remove(dict(event='INSTALL_PARENT_FORCED'));path.write_bytes(b''.join(f.canonical(row)+b'\n' for row in rows))
            elif variant=='lock':
                path=case/'lock.stdout';rows=trace(path);rows[0]['path']+='/foreign';path.write_bytes(b''.join(f.canonical(row)+b'\n' for row in rows))
            elif variant=='exit':
                path=case/'fault.exit.json';value=json.loads(path.read_text());value['exitCode']=0;path.write_bytes(f.canonical(value))
            else:
                path=case/'resume.stdout';rows=trace(path);rows[-1]['runtimeEnabled']=True;path.write_bytes(b''.join(f.canonical(row)+b'\n' for row in rows))
            try:validate_case(target,inputs,states,mode,cut)
            except ValueError as error:need(str(error)==reason,'inherited adoption process unrelated negative: '+variant+': '+str(error))
            else:raise ValueError('inherited adoption process accepted negative: '+variant)
        negatives.append(dict(case=variant,status='REJECTED',reason=reason))
    return dict(result,original=history,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');parser.add_argument('--reachable-selection',action='store_true');args=parser.parse_args()
    from .selected_prefix_evidence import prefix
    print(json.dumps((qualify if args.qualify else validate)(args.root,selected_prefix=prefix if args.reachable_selection else None),sort_keys=True))
