"""Replay exact pinned-source retirement after repeated fresh-process deaths."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import retirement_source_images_evidence as model
from .context_generation_process_evidence import trace

e=model.e;c=model.c;t=model.t;selection=model.selection


def read(path):return e.parse(t.plans.read(path,e.MIB))
def same(left,right,message):e.need(e.f.canonical(left)==e.f.canonical(right),message)


def validate(root):
    root=Path(root);names={mode+'-'+cut for mode in ('halt','kill') for cut in model.CUTS}
    selection.layout(root,{'reference','inputs.json','receipt.json'}|names,'source process')
    selection.layout(root/'reference',{'reference','initial'},'source process originals')
    initial,old,prefix,record,binding,sealing=model.plan(root/'reference')
    inputs_raw=t.plans.read(root/'inputs.json',e.MIB);inputs=e.parse(inputs_raw);e.exact(inputs,'node materialization observations')
    ref=root/'reference/reference'
    original=t.plans.decode(t.plans.read(ref/'original-plan.gsbp',2*e.MIB),t.plans.read(ref/'original-application.image',64*e.MIB),details=True,size=4,source='EMPTY')
    paths=original['plan']['descriptor']['paths']
    same(dict(node=inputs['node'],materialization=inputs['materialization']),dict(node=paths[1]['path'],materialization=paths[2]['path']),'source process exact admitted paths')
    same(inputs['observations'],read(ref/'observations.json'),'source process actual observations')
    rows=[]
    for mode in ('halt','kill'):
        for cut in model.CUTS:
            name=mode+'-'+cut;case=root/name;members={'first','second','final'}|{label+ext for label in ('fault','recovery','resume') for ext in ('.stdout','.stderr','.exit.json')}
            if mode=='kill':members|={'lock.stdout','lock.stderr','lock.exit.json'}
            selection.layout(case,members,'source process case')
            first,_=model.transaction(initial,old,prefix,record,binding,sealing,cut)
            second='RETIREMENT_AUTHORITY_RESEALED' if 'retirement/retirement.gsr' in first else 'ACCEPT_ACTIVE_FORCED'
            state=initial
            for stage,label,point,death in [('first','fault',cut,mode),('second','recovery',second,'halt'),('final','resume',None,'none')]:
                e.need(t.plans.read(case/(label+'.stderr'),e.MIB)==b'','source process stderr')
                state,events=model.transaction(state,old,prefix,record,binding,sealing,point)
                e.need(c.inventory(case/stage)==state,'source process exact '+stage+' snapshot')
                images=sum(n.endswith('.image') for n in state)
                sources=sum(n.startswith(('sources/','floor-copies/')) and n.count('/')==1 and v is None for n,v in state.items())+int(model.BINDING in state or 'retirement/source' in state)
                e.need(images<=7 and sources<=6,'source process physical capacity')
                actual=trace(case/(label+'.stdout'));expected=[dict(event=v) for v in events]
                if death=='kill':expected.append(dict(event='AWAITING_KILL',cut=cut))
                if label=='resume':
                    e.need(len(actual)>0,'source process missing return');result=actual[-1];e.exact(result,'status peakImages peakSources runtimeEnabled')
                    e.need(type(result['peakImages']) is int and 0<result['peakImages']<=7 and type(result['peakSources']) is int and 0<result['peakSources']<=6,'source process capacity/scope')
                    same(result,dict(status='PASS',peakImages=result['peakImages'],peakSources=result['peakSources'],runtimeEnabled=False),'source process capacity/scope');expected.append(result)
                same(actual,expected,'source process exact '+stage+' force/death order')
                same(read(case/(label+'.exit.json')),dict(exitCode=73 if death=='halt' else 137 if death=='kill' else 0,cut=point or 'none',mode=death),'source process exact '+stage+' exit')
            if mode=='kill':
                e.need(t.plans.read(case/'lock.stderr',e.MIB)==b'','source process lock stderr')
                same(trace(case/'lock.stdout'),[dict(event='LOCK_HELD',path=inputs['node']+'/replica.lock')],'source process exact lock probe')
                same(read(case/'lock.exit.json'),dict(exitCode=0),'source process lock exit')
            e.need(state=={n:v for n,v in initial.items() if not n.startswith(prefix) and n!=prefix[:-1]},'source process protected final originals')
            rows.append(dict(case=name,mode=mode,cut=cut,second=second,status='PASS',exitCodes=[73 if mode=='halt' else 137,73,0]))
    expected=dict(schema='gse-v53-retirement-source-process-v1',status='PASS',cases=rows,freshProcesses=192,lockProbes=32,inputsSha256=e.digest(inputs_raw),publicBootstrap=True,powerLoss=False,runtimeEnabled=False)
    same(read(root/'receipt.json'),expected,'source process exact receipt')
    return dict(status='PASS',cases=64,freshProcesses=192,lockProbes=32,publicBootstrap=True,powerLoss=False,runtimeEnabled=False,maximumImages=7,maximumSources=6,maximalBytes=False)


VARIANTS={
    'original-vote':'admitted exact minority-accepted: node-1',
    'floor':'source retirement exact admitted floor',
    'missing-case':'context selection source process inventory',
    'first-prefix':'source process exact first snapshot',
    'second-prefix':'source process exact second snapshot',
    'final-authority':'source process exact final snapshot',
    'backing-source':'source process exact first snapshot',
    'early-delete':'source process exact first snapshot',
    'first-force':'source process exact first force/death order',
    'second-force':'source process exact second force/death order',
    'final-force':'source process exact final force/death order',
    'kill-handshake':'source process exact first force/death order',
    'false-return':'source process exact second force/death order',
    'capacity':'source process capacity/scope',
    'runtime-flag':'source process capacity/scope',
    'receipt-flag':'source process exact receipt',
    'exit-code':'source process exact first exit',
    'exit-cut':'source process exact first exit',
    'lock-path':'source process exact lock probe',
    'lock-exit':'source process lock exit',
    'lock-stderr':'source process lock stderr',
    'admitted-path':'source process exact admitted paths',
    'observations':'source process actual observations',
    'stderr':'source process stderr',
}


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    for name,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-source-process-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'halt-RETIREMENT_PARENT_FORCED'
            if name=='original-vote':(moved/'reference/reference/minority-accepted/node-1/pending.accept').write_bytes(c.EMPTY)
            elif name=='floor':(moved/'reference/initial/floor-copies/floor.gsr').write_bytes(b'changed')
            elif name=='missing-case':shutil.rmtree(case)
            elif name in ('first-prefix','second-prefix','final-authority'):
                stage={'first-prefix':'first','second-prefix':'second','final-authority':'final'}[name];(case/stage/'pending.accept').write_bytes(b'changed')
            elif name=='backing-source':next((case/'first/sources').glob('*/source.gscp')).unlink()
            elif name=='early-delete':
                active=c.current(c.inventory(case/'first'))[0];old='b' if active=='generations/a/' else 'a';next((case/'first/generations'/old).glob('*.image')).unlink()
            elif name in ('stderr','lock-stderr'):
                if name=='lock-stderr':case=moved/'kill-RETIREMENT_PARENT_FORCED'
                (case/('lock.stderr' if name=='lock-stderr' else 'fault.stderr')).write_bytes(b'error')
            elif name in ('receipt-flag','admitted-path','observations','exit-code','exit-cut','lock-exit'):
                if name=='lock-exit':case=moved/'kill-RETIREMENT_PARENT_FORCED'
                path=moved/'receipt.json' if name=='receipt-flag' else moved/'inputs.json' if name in ('admitted-path','observations') else case/('lock.exit.json' if name=='lock-exit' else 'fault.exit.json')
                value=read(path)
                if name=='receipt-flag':value['publicBootstrap']=1
                elif name=='admitted-path':value['node']+='/other'
                elif name=='observations':value['observations'].pop()
                elif name=='exit-cut':value['cut']='RETIREMENT_CLEARED'
                else:value['exitCode']=2
                path.write_bytes(e.f.canonical(value))
            else:
                label='fault' if name in ('first-force','kill-handshake') else 'recovery' if name in ('second-force','false-return') else 'lock' if name=='lock-path' else 'resume'
                if name in ('kill-handshake','lock-path'):case=moved/'kill-RETIREMENT_PARENT_FORCED'
                path=case/(label+'.stdout');rows=trace(path)
                if name=='first-force':rows.remove(dict(event='RETIREMENT_BORROWED_SOURCE_FORCED'))
                elif name=='second-force':rows.remove(dict(event='CONTEXT_SOURCE_PARENT_FORCED'))
                elif name=='final-force':rows.remove(dict(event='RETIREMENT_AUTHORITY_RESEALED'))
                elif name=='kill-handshake':rows[-1]['cut']='RETIREMENT_CLEARED'
                elif name=='false-return':rows.append(dict(status='PASS',peakImages=7,peakSources=6,runtimeEnabled=False))
                elif name=='runtime-flag':rows[-1]['runtimeEnabled']=0
                elif name=='lock-path':rows[0]['path']+='/other'
                else:rows[-1]['peakSources']=7
                path.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in rows))
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong source process rejection: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted source process mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-source-process-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'source process portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
