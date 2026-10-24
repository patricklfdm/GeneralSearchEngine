"""Replay admitted covered-minority authority through repeated fresh-process death."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import covered_minority_evidence as model
from .context_generation_process_evidence import trace

e=model.e;c=model.c;t=model.t;selection=model.selection


def reference(root):
    required={'original-plan.gsbp','original-application.image','initial','observations.json','minority-entry.gsr','minority-payload.bin','selected-entry.gsr','selected-payload.bin','minority-accepted','before-install'}
    required|={f'round-{r}-{s}' for r in (1,3) for s in ('prepared','selected','installed','settled')}
    required|={'round-4-prepared','round-4-selected'}|{f'slot-1-{s}' for s in ('accepted','proved','certified','applied','published','settled')}
    required|={'typed-1-node-2','typed-1-node-3'};selection.layout(root,required,'covered process reference')
    before,after,observed=model.prefix(root);model.observations(root,observed)
    for node in ('node-2','node-3'):
        _,members,packet=c.current(c.inventory(root/'slot-1-settled'/node));model.b.typed_image(root/f'typed-1-{node}',members[packet['capsule']['application']+'.image'])
    return before['node-1'],after['node-1'],observed


def validate(root):
    root=Path(root);names={mode+'-'+point for mode in ('halt','kill') for point in model.CUTS}
    selection.layout(root,names|{'reference','inputs.json','receipt.json'},'covered process')
    before,after,observed=reference(root/'reference');inputs_raw=t.plans.read(root/'inputs.json',e.MIB);inputs=e.parse(inputs_raw);e.exact(inputs,'targets observations')
    expected=set(map(e.f.canonical,observed));actual=inputs['observations']
    e.need(type(actual) is list and len(actual)==len(expected) and set(map(e.f.canonical,actual))==expected,'covered process actual observations')
    original=t.plans.decode(t.plans.read(root/'reference/original-plan.gsbp',2*e.MIB),t.plans.read(root/'reference/original-application.image',64*e.MIB),details=True,size=3,source='EMPTY')
    paths=original['plan']['descriptor']['paths'];targets=[dict(node=paths[1+2*i]['path'],materialization=paths[2+2*i]['path']) for i in range(3)]
    e.need(e.f.canonical(inputs['targets'])==e.f.canonical(targets),'covered process exact admitted paths')
    rows=[]
    for mode in ('halt','kill'):
        for cut in model.CUTS:
            name=mode+'-'+cut;case=root/name;selection.layout(case,{'first','second','final'}|{n+s for n in ('fault','recovery','resume') for s in ('.stdout','.stderr')},'covered process case')
            second='ACCEPT_ACTIVE_FORCED' if cut in ('INSTALL_MANIFEST_FORCED','SETTLED_VOTE_RENAMED','SETTLED_VOTE_PARENT_FORCED','SETTLED_VOTE_BEFORE_RETURN') else 'SETTLED_VOTE_CANDIDATE_PARENT_FORCED'
            state=before
            for stage,label,point in [('first','fault',cut),('second','recovery',second),('final','resume',None)]:
                e.need(t.plans.read(case/(label+'.stderr'),e.MIB)==b'','covered process stderr')
                state,events=model.transaction(state,after,point)
                e.need(c.inventory(case/stage)==state,'covered process exact '+stage+' snapshot')
                actual=trace(case/(label+'.stdout'));expected=[dict(event=v) for v in events]
                if label=='fault' and mode=='kill':expected.append(dict(event='AWAITING_KILL',cut=cut))
                if label=='resume':
                    e.need(len(actual)>0,'covered process missing return');result=actual[-1];e.exact(result,'status peakImages runtimeEnabled')
                    e.need(type(result['peakImages']) is int and 0<result['peakImages']<=7 and e.f.canonical(result)==e.f.canonical(dict(status='PASS',peakImages=result['peakImages'],runtimeEnabled=False)),'covered process capacity/scope')
                    expected.append(result)
                e.need(actual==expected,'covered process exact '+stage+' force/death order')
            e.need(state==after,'covered process final originals')
            rows.append(dict(case=name,mode=mode,cut=cut,second=second,status='PASS',exitCodes=[73 if mode=='halt' else 137,73,0]))
    expected=dict(schema='gse-v53-covered-minority-process-v1',status='PASS',cases=rows,freshProcesses=72,lockProbes=12,inputsSha256=e.digest(inputs_raw),publicBootstrap=True,powerLoss=False,runtimeEnabled=False)
    e.need(e.f.canonical(e.parse(t.plans.read(root/'receipt.json',65536)))==e.f.canonical(expected),'covered process exact receipt')
    return dict(status='PASS',cases=24,freshProcesses=72,lockProbes=12,publicBootstrap=True,powerLoss=False,runtimeEnabled=False,maximalCapacity=False)


VARIANTS={
    'original-vote':'admitted exact minority-accepted: node-1',
    'missing-case':'context selection covered process inventory',
    'first-prefix':'covered process exact first snapshot',
    'second-prefix':'covered process exact second snapshot',
    'final-vote':'covered process exact final snapshot',
    'retained-source':'covered process exact final snapshot',
    'retained-generation':'covered process exact final snapshot',
    'first-force':'covered process exact first force/death order',
    'second-force':'covered process exact second force/death order',
    'final-force':'covered process exact final force/death order',
    'kill-handshake':'covered process exact first force/death order',
    'false-return':'covered process exact second force/death order',
    'capacity':'covered process capacity/scope',
    'runtime-flag':'covered process capacity/scope',
    'receipt-flag':'covered process exact receipt',
    'exit-code':'covered process exact receipt',
    'admitted-path':'covered process exact admitted paths',
    'observations':'covered process actual observations',
    'stderr':'covered process stderr',
}


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    for name,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-covered-process-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'halt-INSTALL_MANIFEST_FORCED'
            if name=='original-vote':(moved/'reference/minority-accepted/node-1/pending.accept').write_bytes(c.EMPTY)
            elif name=='missing-case':shutil.rmtree(case)
            elif name in ('first-prefix','second-prefix','final-vote'):
                stage={'first-prefix':'first','second-prefix':'second','final-vote':'final'}[name];(case/stage/'pending.accept').write_bytes(b'changed')
            elif name=='retained-source':next((case/'final/sources').glob('*/source.gscp')).unlink()
            elif name=='retained-generation':
                prefix=c.current(c.inventory(moved/'reference/before-install/node-1'))[0];shutil.rmtree(case/'final'/prefix)
            elif name=='stderr':(case/'fault.stderr').write_bytes(b'error')
            elif name in ('receipt-flag','exit-code','admitted-path','observations'):
                path=moved/('receipt.json' if name in ('receipt-flag','exit-code') else 'inputs.json');value=e.parse(path.read_bytes())
                if name=='receipt-flag':value['publicBootstrap']=1
                elif name=='exit-code':value['cases'][0]['exitCodes'][0]=0
                elif name=='admitted-path':value['targets'][0]['node']+='/other'
                else:value['observations'].pop()
                path.write_bytes(e.f.canonical(value))
            else:
                label='fault' if name in ('first-force','kill-handshake') else 'recovery' if name in ('second-force','false-return') else 'resume'
                if name=='kill-handshake':case=moved/'kill-INSTALL_MANIFEST_FORCED'
                path=case/(label+'.stdout');rows=trace(path)
                if name=='first-force':rows.remove(dict(event='INSTALL_MANIFEST_FORCED'))
                elif name=='second-force':rows.remove(dict(event='ACCEPT_ACTIVE_FORCED'))
                elif name=='final-force':rows.remove(dict(event='SETTLED_VOTE_PARENT_FORCED'))
                elif name=='kill-handshake':rows[-1]['cut']='SETTLED_VOTE_RENAMED'
                elif name=='false-return':rows.append(dict(status='PASS',peakImages=3,runtimeEnabled=False))
                elif name=='runtime-flag':rows[-1]['runtimeEnabled']=0
                elif name=='capacity':rows[-1]['peakImages']=8
                path.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in rows))
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong covered process rejection: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted covered process mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-covered-process-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'covered process portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
