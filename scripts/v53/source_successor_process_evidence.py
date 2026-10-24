"""Admitted forced-successor reclamation under repeated fresh-process death."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import source_successor_recovery_evidence as q
from .covered_context_process_evidence import force_trace
from .retirement_source_process_evidence import same, read, trace

e,c,t,selection=q.e,q.c,q.m.t,q.b.selection
CUTS=q.release.CUTS


def transaction(initial,authority,compact,identifier,cut=None):
    opening=[*q.q.covered.OPEN,*q.q.covered.SEAL]
    steps=[(event,dict(initial)) for event in opening]+q.release.transaction(initial,authority,compact,identifier)
    if cut is not None:steps=steps[:q.release.r.cut_position(steps,cut)+1]
    return steps[-1][1],[event for event,_ in steps]


def original_inputs(root,files,identifier):
    raw=t.plans.read(root/'inputs.json',e.MIB);inputs=e.parse(raw)
    e.exact(inputs,'node materialization source voteSha256 observations')
    ref=root/'reference'
    plan=t.plans.decode(t.plans.read(ref/'original-plan.gsbp',2*e.MIB),t.plans.read(ref/'original-application.image',64*e.MIB),details=True,size=4,source='EMPTY')
    paths=plan['plan']['descriptor']['paths']
    same({k:inputs[k] for k in ('node','materialization','source','voteSha256')},dict(node=paths[1]['path'],materialization=paths[2]['path'],source=identifier,voteSha256=e.digest(files['pending.accept'])),'successor process admitted inputs')
    _,names,majority,_,observed,_,_,_=q.q.initial(ref)
    for stage,nodes in [('mixed-reaccepted',majority),('headroom-reaccepted',[n for n in names if n not in majority])]:
        for node in nodes:
            files=c.inventory(ref/stage/node);_,_,packet=c.current(files);frames,_=c.pending(files['pending.accept'],())
            observed.append(dict(voter=node,storage=e.f.decode(files['node.gsr'],'records','NODE')['identity']['storage'],record=e.digest(frames['ACCEPT']),parent=e.digest(e.f.canonical(packet['capsule']['cut']))))
    # The producer sorts a set of actual observations, not an order of calls.
    expected={e.f.canonical(v) for v in observed}
    e.need(type(inputs['observations']) is list and len(inputs['observations'])==len(expected) and {e.f.canonical(v) for v in inputs['observations']}==expected,'successor process original observations')
    return raw,inputs


def validate(root):
    root=Path(root);selection.layout(root,{'reference','inputs.json','receipt.json'}|{m+'-'+c for m in ('halt','kill') for c in CUTS},'successor process')
    files,initial,authority,compact,identifier,final=q.plan(root);raw,inputs=original_inputs(root,files,identifier);rows=[];peaks=[]
    for mode in ('halt','kill'):
        for cut in CUTS:
            name=mode+'-'+cut;case=root/name
            members={'first','second','final'}|{label+ext for label in ('fault','recovery','resume') for ext in ('.stdout','.stderr','.exit.json')}
            if mode=='kill':members|={'lock.stdout','lock.stderr','lock.exit.json'}
            selection.layout(case,members,'successor process case')
            second='ACCEPT_ACTIVE_FORCED' if cut in ('SOURCE_RETIREMENT_CLEARED','SOURCE_RETIREMENT_BEFORE_RETURN') else 'SOURCE_RETIREMENT_JOURNAL_PRUNED'
            current=initial
            for stage,label,point,death in [('first','fault',cut,mode),('second','recovery',second,'halt'),('final','resume',None,'none')]:
                e.need(t.plans.read(case/(label+'.stderr'),e.MIB)==b'','successor process stderr')
                current,events=transaction(current,authority,compact,identifier,point)
                same(q.release.s.inventory(case/stage),current,'successor process exact '+stage)
                e.need(sum(p.endswith('.image') for p in current)<=7,'successor process physical images')
                peak=force_trace(trace(case/(label+'.stdout')),events,death,point,stage=='final')
                if peak is not None:peaks.append(peak)
                same(read(case/(label+'.exit.json')),dict(exitCode=73 if death=='halt' else 137 if death=='kill' else 0,cut=point or 'none',mode=death),'successor process exact '+stage+' exit')
            same(current,final,'successor process final authority')
            if mode=='kill':
                e.need(t.plans.read(case/'lock.stderr',e.MIB)==b'','successor process lock stderr')
                same(trace(case/'lock.stdout'),[dict(event='LOCK_HELD',path=inputs['node']+'/replica.lock')],'successor process lock path')
                same(read(case/'lock.exit.json'),dict(exitCode=0),'successor process lock exit')
            rows.append(dict(case=name,mode=mode,cut=cut,second=second,status='PASS',exitCodes=[73 if mode=='halt' else 137,73,0]))
    same(read(root/'receipt.json'),dict(schema='gse-v53-source-successor-process-v1',status='PASS',cases=rows,freshProcesses=90,lockProbes=15,inputsSha256=e.digest(raw),publicBootstrap=True,powerLoss=False,runtimeEnabled=False),'successor process exact receipt')
    return dict(status='PASS',cases=30,freshProcesses=90,lockProbes=15,peakImages=max(peaks),publicBootstrap=True,publicRuntime=False,powerLoss=False,maximalCapacity=False,originalFirst=True)


VARIANTS={'reference-vote':'admitted exact headroom-floors: node-1','first-vote':'successor process exact first',
          'second-journal':'successor process exact second','final-extra':'successor process exact final',
          'force':'context process exact force/death order','kill-handshake':'context process kill handshake',
          'returned-runtime':'context process result scope','exit-code':'successor process exact first exit',
          'stderr':'successor process stderr','lock-path':'successor process lock path',
          'lock-exit':'successor process lock exit','lock-stderr':'successor process lock stderr',
          'admitted-path':'successor process admitted inputs','observations':'successor process original observations',
          'receipt':'successor process exact receipt'}


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    for name,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-successor-process-negative-') as tmp:
            moved=Path(tmp)/'raw';shutil.copytree(root,moved);case=moved/'halt-SOURCE_RETIREMENT_FORCED'
            if name=='reference-vote':(moved/'reference/headroom-floors/node-1/pending.accept').write_bytes(c.EMPTY)
            elif name=='first-vote':(case/'first/pending.accept').write_bytes(c.EMPTY)
            elif name=='second-journal':(case/'second/grants.gsr').write_bytes(b'')
            elif name=='final-extra':(case/'final/extra').write_bytes(b'undeleted')
            elif name=='stderr':(case/'fault.stderr').write_bytes(b'error')
            elif name in ('lock-path','lock-exit','lock-stderr','kill-handshake'):
                case=moved/'kill-SOURCE_RETIREMENT_FORCED'
                if name=='lock-stderr':(case/'lock.stderr').write_bytes(b'error')
                elif name=='lock-exit':(case/'lock.exit.json').write_bytes(e.f.canonical(dict(exitCode=2)))
                else:
                    p=case/('lock.stdout' if name=='lock-path' else 'fault.stdout');values=trace(p)
                    if name=='lock-path':values[0]['path']+='/wrong'
                    else:values.pop()
                    p.write_bytes(b''.join(e.f.canonical(v)+b'\n' for v in values))
            elif name in ('force','returned-runtime'):
                p=case/('fault.stdout' if name=='force' else 'resume.stdout');values=trace(p)
                if name=='force':values.pop()
                else:values[-1]['runtimeEnabled']=True
                p.write_bytes(b''.join(e.f.canonical(v)+b'\n' for v in values))
            else:
                p=moved/'inputs.json' if name in ('admitted-path','observations') else moved/'receipt.json' if name=='receipt' else case/'fault.exit.json'
                value=read(p)
                if name=='admitted-path':value['node']+='/other'
                elif name=='observations':value['observations'].pop()
                elif name=='receipt':value['publicBootstrap']=1
                else:value['exitCode']=0
                p.write_bytes(e.f.canonical(value))
            try:validate(moved)
            except ValueError as error:e.need(str(error)==reason,'successor process wrong negative: '+name+': '+str(error))
            else:raise ValueError('successor process mutation accepted: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-successor-process-portable-') as tmp:
        moved=Path(tmp)/'raw';shutil.copytree(root,moved);same(validate(moved),result,'successor process portable replay')
    return dict(**result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
