"""Fresh-process qualification for an applied endpoint hidden inside a published range."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import covered_staging_evidence as q
from . import hidden_staging_evidence as h
from .covered_staging_process_evidence import force_trace
from .retirement_source_process_evidence import same,read,trace
p=q.phased;m=q.m;e=q.e;c=q.c;t=p.t;selection=q.selection
CUTS=tuple(v for v in q.CUTS if not v.startswith('REPLAY_'))


def original(root):
    profile,names,lagging,majority,before,after,observed,proof=h.prefix(root,None)
    same(profile,dict(size=3,backup=False,phase='CERTIFICATE'),'hidden process original profile')
    h.m.observations(root,observed);h.calls(root,names,lagging,majority,before,after,False)
    return before['node-1'],after['node-1'],proof


def proof_bytes(value):
    e.exact(value,'statement acknowledgements')
    e.need(type(value['statement']) is str and type(value['acknowledgements']) is list and len(value['acknowledgements'])==2 and all(type(v) is str for v in value['acknowledgements']),'hidden process proof fields')
    return bytes.fromhex(value['statement'])+b''.join(bytes.fromhex(v) for v in value['acknowledgements'])


def check_proof(value, expected):
    e.need(proof_bytes(value) == expected, 'hidden process exact offered proof')




def validate(root):
    root=Path(root);selection.layout(root,{'reference','inputs.json','receipt.json'}|{mode+'-'+cut for mode in ('halt','kill') for cut in CUTS},'staging process')
    initial,installed,proof=original(root/'reference');marker=h.authority(initial,installed,proof);raw=t.plans.read(root/'inputs.json',e.MIB);inputs=e.parse(raw);e.exact(inputs,'targets observations appliedAncestry');check_proof(inputs['appliedAncestry'],proof)
    plan=t.plans.decode(t.plans.read(root/'reference/original-plan.gsbp',2*e.MIB),t.plans.read(root/'reference/original-application.image',64*e.MIB),details=True,size=3,source='EMPTY')
    paths=plan['plan']['descriptor']['paths'];targets=[dict(node=paths[1+2*i]['path'],materialization=paths[2+2*i]['path']) for i in range(3)]
    same(inputs['targets'],targets,'staging process admitted paths');same(inputs['observations'],read(root/'reference/observations.json'),'staging process original observations');results=[]
    for mode in ('halt','kill'):
        for cut in CUTS:
            name=mode+'-'+cut;case=root/name;members={'first','second','final'}|{label+ext for label in ('fault','recovery','resume') for ext in ('.stdout','.stderr','.exit.json')}
            if mode=='kill':members|={'lock.stdout','lock.stderr','lock.exit.json'}
            selection.layout(case,members,'staging process case');second='CERTIFICATE_ACTIVE_FORCED' if cut in ('STAGED_RETIREMENT_BEFORE_RETURN','SUPERSEDED_END_DIRECTORY_DELETED') else 'SUPERSEDED_END_AUTHORITY_FORCED'
            state=dict(initial)
            for stage,label,point,death in [('first','fault',cut,mode),('second','recovery',second,'halt'),('final','resume',None,'none')]:
                e.need(t.plans.read(case/(label+'.stderr'),e.MIB)==b'','staging process stderr')
                opening=m.OPEN+['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED']
                if point=='CERTIFICATE_ACTIVE_FORCED':expected=state;events=opening[:-1];cleanup_events=[]
                else:
                    expected,cleanup_events=q.cleanup(state,marker,point);events=opening+cleanup_events
                    if stage=='final':
                        expected,installation=m.transaction(expected,installed,phase='CERTIFICATE');events+=installation[len(opening):]
                e.need(c.inventory(case/stage)==expected,'staging process exact '+stage+' snapshot');e.need(sum(k.endswith('.image') for k in expected)<=7,'staging process image count')
                force_trace(trace(case/(label+'.stdout')),events,cleanup_events,death,cut,stage=='final')
                same(read(case/(label+'.exit.json')),dict(exitCode=73 if death=='halt' else 137 if death=='kill' else 0,cut=point or 'none',mode=death),'staging process exact '+stage+' exit');state=expected
            e.need(state==installed,'staging process final installation')
            if mode=='kill':
                e.need(t.plans.read(case/'lock.stderr',e.MIB)==b'','staging process lock stderr')
                same(trace(case/'lock.stdout'),[dict(event='LOCK_HELD',path=targets[0]['node']+'/replica.lock')],'staging process lock probe')
                same(read(case/'lock.exit.json'),dict(exitCode=0),'staging process lock exit')
            results.append(dict(case=name,mode=mode,cut=cut,second=second,status='PASS',exitCodes=[73 if mode=='halt' else 137,73,0]))
    expected=dict(schema='gse-v53-hidden-staging-process-v1',status='PASS',cases=results,freshProcesses=96,lockProbes=16,inputsSha256=e.digest(raw),publicBootstrap=True,powerLoss=False,runtimeEnabled=False)
    same(read(root/'receipt.json'),expected,'staging process exact receipt')
    return dict(status='PASS',cases=32,freshProcesses=96,lockProbes=16,publicBootstrap=True,powerLoss=False,publicRuntime=False,maximalCapacity=False,replaySemantics='producer-only')

VARIANTS={
    'hidden-proof':'hidden staging exact applied ancestry',
    'offered-proof':'hidden process exact offered proof',
    'original-applied':'admitted exact lagging-applied: node-1',
    'first-marker':'staging process exact first snapshot',
    'second-vote':'staging process exact second snapshot',
    'final-source':'staging process exact final snapshot',
    'cleanup-force':'staging process exact force/death order',
    'replay-force':'staging process replay force order',
    'kill-handshake':'staging process kill handshake',
    'old-ack':'covered staging emitted old ACK',
    'peak-images':'staging process result scope',
    'runtime':'staging process result scope',
    'exit-code':'staging process exact first exit',
    'exit-cut':'staging process exact second exit',
    'stderr':'staging process stderr',
    'lock-path':'staging process lock probe',
    'lock-exit':'staging process lock exit',
    'lock-stderr':'staging process lock stderr',
    'receipt':'staging process exact receipt',
    'admitted-path':'staging process admitted paths',
    'observations':'staging process original observations',
}


def qualify(root):
    root=Path(root);result=validate(root);negative=[]
    for name,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-staging-process-negative-') as temp:
            moved=Path(temp)/'raw';shutil.copytree(root,moved);case=moved/'halt-SUPERSEDED_END_AUTHORITY_FORCED'
            if name=='hidden-proof':(moved/'reference/applied-ancestry.gsr').write_bytes(b'')
            elif name=='offered-proof':
                path=moved/'inputs.json';value=read(path);value['appliedAncestry']['statement']='00';path.write_bytes(e.f.canonical(value))
            elif name=='original-applied':(moved/'reference/lagging-applied/node-1/applied-end/certificate.gsr').write_bytes(b'changed')
            elif name=='first-marker':(case/'first/applied-end/retirement.gsat').unlink()
            elif name=='second-vote':(case/'second/pending.accept').write_bytes(c.EMPTY)
            elif name=='final-source':next((case/'final/sources').glob('*/source.gscp')).unlink()
            elif name in ('stderr','lock-stderr'):
                if name=='lock-stderr':case=moved/'kill-SUPERSEDED_END_AUTHORITY_FORCED'
                (case/('lock.stderr' if name=='lock-stderr' else 'fault.stderr')).write_bytes(b'error')
            elif name in ('receipt','admitted-path','observations','exit-code','exit-cut','lock-exit'):
                if name=='lock-exit':case=moved/'kill-SUPERSEDED_END_AUTHORITY_FORCED'
                path=moved/'receipt.json' if name=='receipt' else moved/'inputs.json' if name in ('admitted-path','observations') else case/('lock.exit.json' if name=='lock-exit' else 'recovery.exit.json' if name=='exit-cut' else 'fault.exit.json')
                value=read(path)
                if name=='receipt':value['publicBootstrap']=1
                elif name=='admitted-path':value['targets'][0]['node']+='/other'
                elif name=='observations':value['observations'].pop()
                elif name=='exit-cut':value['cut']='none'
                else:value['exitCode']=2
                path.write_bytes(e.f.canonical(value))
            else:
                if name in ('kill-handshake','lock-path'):case=moved/'kill-SUPERSEDED_END_AUTHORITY_FORCED'
                path=case/('lock.stdout' if name=='lock-path' else 'resume.stdout' if name in ('peak-images','runtime') else 'fault.stdout');rows=trace(path)
                if name in ('cleanup-force','replay-force'):
                    event='SUPERSEDED_END_AUTHORITY_FORCED' if name=='cleanup-force' else 'REPLAY_CLAIM_FORCED';rows.remove(dict(event=event))
                elif name=='old-ack':rows.append(dict(event='APPLY_BEFORE_RETURN'))
                elif name=='kill-handshake':rows.pop()
                elif name=='lock-path':rows[0]['path']+='/other'
                elif name=='peak-images':rows[-1]['peakImages']=8
                elif name=='runtime':rows[-1]['runtimeEnabled']=True
                path.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in rows))
            try:validate(moved)
            except ValueError as error:e.need(str(error)==reason,'staging process negative wrong reason: '+name+': '+str(error))
            else:raise ValueError('staging process mutation accepted: '+name)
            negative.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(**result,negatives=negative)


def portable(root):
    result=qualify(root)
    with tempfile.TemporaryDirectory(prefix='v53-staging-process-portable-') as temp:
        target=Path(temp)/'evidence';shutil.copytree(root,target);same(qualify(target),result,'staging process portable result')
    return dict(**result,portableReplay='PASS')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');parser.add_argument('--portable',action='store_true');args=parser.parse_args()
    print(json.dumps((portable if args.portable else qualify if args.qualify else validate)(args.root),sort_keys=True))
