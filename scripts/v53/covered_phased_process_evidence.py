"""Fresh-process replay for unpublished phased votes behind a proven prefix."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import covered_phased_vote_evidence as model
from .retirement_source_process_evidence import same,read,trace

e=model.e;c=model.c;t=model.t;selection=model.selection


def validate(root):
    root=Path(root);selection.layout(root,{'PROOF','CERTIFICATE','receipt.json'},'phased process');rows=[]
    for phase in ('PROOF','CERTIFICATE'):
        base=root/phase;selection.layout(base,{'reference','inputs.json'}|{mode+'-'+cut for mode in ('halt','kill') for cut in model.model.CUTS},'phased process phase')
        ref=base/'reference';p,names,lagging,majority=model.layout(ref,'prepared')
        same(p,dict(size=3,backup=False,phase=phase),'phased process exact original profile')
        before,after,observed=model.prefix(ref,p,names,lagging,majority);model.model.observations(ref,observed);model.calls(ref,p,names,lagging,majority,before,after,False)
        raw=t.plans.read(base/'inputs.json',e.MIB);inputs=e.parse(raw);e.exact(inputs,'targets observations')
        original=t.plans.decode(t.plans.read(ref/'original-plan.gsbp',2*e.MIB),t.plans.read(ref/'original-application.image',64*e.MIB),details=True,size=3,source='EMPTY')
        paths=original['plan']['descriptor']['paths'];targets=[dict(node=paths[1+2*i]['path'],materialization=paths[2+2*i]['path']) for i in range(3)]
        same(inputs['targets'],targets,'phased process exact admitted paths');same(inputs['observations'],read(ref/'observations.json'),'phased process exact observations')
        for mode in ('halt','kill'):
            for cut in model.model.CUTS:
                name=mode+'-'+cut;case=base/name;members={'first','second','final'}|{label+ext for label in ('fault','recovery','resume') for ext in ('.stdout','.stderr','.exit.json')}
                if mode=='kill':members|={'lock.stdout','lock.stderr','lock.exit.json'}
                selection.layout(case,members,'phased process case')
                second=phase+'_ACTIVE_FORCED' if cut=='INSTALL_MANIFEST_FORCED' else 'ACCEPT_ACTIVE_FORCED' if cut in ('SETTLED_VOTE_RENAMED','SETTLED_VOTE_PARENT_FORCED','SETTLED_VOTE_BEFORE_RETURN') else 'SETTLED_VOTE_CANDIDATE_PARENT_FORCED'
                state=before['node-1']
                for stage,label,point,death in [('first','fault',cut,mode),('second','recovery',second,'halt'),('final','resume',None,'none')]:
                    e.need(t.plans.read(case/(label+'.stderr'),e.MIB)==b'','phased process stderr')
                    state,events=model.model.transaction(state,after['node-1'],point,phase=phase)
                    e.need(c.inventory(case/stage)==state,'phased process exact '+stage+' snapshot')
                    e.need(sum(n.endswith('.image') for n in state)<=7,'phased process image capacity')
                    actual=trace(case/(label+'.stdout'));expected=[dict(event=v) for v in events]
                    if death=='kill':expected.append(dict(event='AWAITING_KILL',cut=cut))
                    if label=='resume':
                        e.need(len(actual)>0,'phased process missing return');result=actual[-1];e.exact(result,'status peakImages runtimeEnabled')
                        e.need(type(result['peakImages']) is int and 0<result['peakImages']<=7,'phased process capacity/scope')
                        same(result,dict(status='PASS',peakImages=result['peakImages'],runtimeEnabled=False),'phased process capacity/scope');expected.append(result)
                    same(actual,expected,'phased process exact '+stage+' force/death order')
                    same(read(case/(label+'.exit.json')),dict(exitCode=73 if death=='halt' else 137 if death=='kill' else 0,cut=point or 'none',mode=death),'phased process exact '+stage+' exit')
                e.need(state==after['node-1'],'phased process final originals')
                if mode=='kill':
                    e.need(t.plans.read(case/'lock.stderr',e.MIB)==b'','phased process lock stderr')
                    same(trace(case/'lock.stdout'),[dict(event='LOCK_HELD',path=targets[0]['node']+'/replica.lock')],'phased process exact lock probe')
                    same(read(case/'lock.exit.json'),dict(exitCode=0),'phased process lock exit')
                rows.append(dict(phase=phase,case=name,mode=mode,cut=cut,second=second,status='PASS',exitCodes=[73 if mode=='halt' else 137,73,0],inputsSha256=e.digest(raw)))
    expected=dict(schema='gse-v53-covered-phased-process-v1',status='PASS',cases=rows,freshProcesses=144,lockProbes=24,publicBootstrap=True,powerLoss=False,runtimeEnabled=False)
    same(read(root/'receipt.json'),expected,'phased process exact receipt')
    return dict(status='PASS',cases=48,freshProcesses=144,lockProbes=24,publicBootstrap=True,powerLoss=False,runtimeEnabled=False,maximalCapacity=False)


VARIANTS={
    'original-proof':'admitted exact lagging-proved: node-1',
    'original-certificate':'admitted exact lagging-certified: node-1',
    'missing-case':'context selection phased process phase inventory',
    'first-prefix':'phased process exact first snapshot',
    'second-prefix':'phased process exact second snapshot',
    'final-vote':'phased process exact final snapshot',
    'retained-source':'phased process exact final snapshot',
    'first-force':'phased process exact first force/death order',
    'second-force':'phased process exact second force/death order',
    'final-force':'phased process exact final force/death order',
    'kill-handshake':'phased process exact first force/death order',
    'false-return':'phased process exact second force/death order',
    'capacity':'phased process capacity/scope',
    'runtime-flag':'phased process capacity/scope',
    'receipt-flag':'phased process exact receipt',
    'exit-code':'phased process exact first exit',
    'exit-cut':'phased process exact second exit',
    'lock-path':'phased process exact lock probe',
    'lock-exit':'phased process lock exit',
    'lock-stderr':'phased process lock stderr',
    'admitted-path':'phased process exact admitted paths',
    'observations':'phased process exact observations',
    'stderr':'phased process stderr',
}


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    for name,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-phased-process-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);base=moved/'PROOF';case=base/'halt-INSTALL_MANIFEST_FORCED'
            if name=='original-proof':(base/'reference/lagging-proved/node-1/pending.accept').write_bytes(c.EMPTY)
            elif name=='original-certificate':(moved/'CERTIFICATE/reference/lagging-certified/node-1/pending.accept').write_bytes(c.EMPTY)
            elif name=='missing-case':shutil.rmtree(case)
            elif name in ('first-prefix','second-prefix','final-vote'):
                stage={'first-prefix':'first','second-prefix':'second','final-vote':'final'}[name];(case/stage/'pending.accept').write_bytes(b'changed')
            elif name=='retained-source':next((case/'final/sources').glob('*/source.gscp')).unlink()
            elif name in ('stderr','lock-stderr'):
                if name=='lock-stderr':case=base/'kill-INSTALL_MANIFEST_FORCED'
                (case/('lock.stderr' if name=='lock-stderr' else 'fault.stderr')).write_bytes(b'error')
            elif name in ('receipt-flag','admitted-path','observations','exit-code','exit-cut','lock-exit'):
                if name=='lock-exit':case=base/'kill-INSTALL_MANIFEST_FORCED'
                path=moved/'receipt.json' if name=='receipt-flag' else base/'inputs.json' if name in ('admitted-path','observations') else case/('lock.exit.json' if name=='lock-exit' else 'recovery.exit.json' if name=='exit-cut' else 'fault.exit.json')
                value=read(path)
                if name=='receipt-flag':value['publicBootstrap']=1
                elif name=='admitted-path':value['targets'][0]['node']+='/other'
                elif name=='observations':value['observations'].pop()
                elif name=='exit-cut':value['cut']='ACCEPT_ACTIVE_FORCED'
                else:value['exitCode']=2
                path.write_bytes(e.f.canonical(value))
            else:
                label='fault' if name in ('first-force','kill-handshake') else 'recovery' if name in ('second-force','false-return') else 'lock' if name=='lock-path' else 'resume'
                if name in ('kill-handshake','lock-path'):case=base/'kill-INSTALL_MANIFEST_FORCED'
                path=case/(label+'.stdout');rows=trace(path)
                if name=='first-force':rows.remove(dict(event='PROOF_ACTIVE_FORCED'))
                elif name=='second-force':rows[-1]['event']='ACCEPT_ACTIVE_FORCED'
                elif name=='final-force':rows.remove(dict(event='SETTLED_VOTE_PARENT_FORCED'))
                elif name=='kill-handshake':rows[-1]['cut']='SETTLED_VOTE_RENAMED'
                elif name=='false-return':rows.append(dict(status='PASS',peakImages=7,runtimeEnabled=False))
                elif name=='runtime-flag':rows[-1]['runtimeEnabled']=0
                elif name=='lock-path':rows[0]['path']+='/other'
                else:rows[-1]['peakImages']=8
                path.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in rows))
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong phased process rejection: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted phased process mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-phased-process-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'phased process portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();print(json.dumps(qualify(a.root),sort_keys=True))
