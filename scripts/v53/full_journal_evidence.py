"""Full shared journal boundary; declared PROMISE fixture, actual admitted rotation.

This does not claim the large fixture was produced by that many actual votes.
Every retained source and new grant is replayed from the original public bootstrap.
"""
import argparse
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from . import bootstrap_publication_evidence as b
from . import journal_rotation_evidence as rotation
from . import capture_recovery_evidence as capture
from .retirement_source_process_evidence import same, read, trace

e,c,t,selection=b.e,b.c,b.t,b.selection
MAXIMUM=32*e.MIB
ALLOWANCE=2*4096+8*16384+2*e.MIB+7*2048+16384+8192+24
LIMIT=MAXIMUM-ALLOWANCE
CUTS=rotation.CUTS
OPEN=[*capture.current.OPEN,'ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED']


def promise(base,counter):
    return e.f.encode('records','PROMISE',dict(base,ballot=dict(base['ballot'],counter=counter),
                     basisId=str(uuid.UUID(int=(0x1353000000000000<<64)|counter))))


def filled(original,base,limit):
    small=len(promise(base,1_000_000));large=len(promise(base,10_000_000))
    e.need(large==small+1,'full journal fixture frame sizes')
    remaining=limit-len(original);n=remaining%small or small;m=(remaining-n*large)//small
    e.need(m>0 and m<9_000_000 and m*small+n*large==remaining,'full journal fixture count')
    rows=[promise(base,1_000_000+i) for i in range(m)]+[promise(base,10_000_000+i) for i in range(n)]
    return original+b''.join(rows),rows[-1],m+n


def derive(root):
    ref=root/'reference';paths={'original-plan.gsbp','original-application.image','initial'}|{'round-1-'+s for s in ('prepared','selected','installed','settled')}
    selection.layout(ref,paths,'full journal reference')
    group=b.campaign(ref,b.original(ref,3,False),1);seed=group['node-1'];_,members,packet=c.current(seed)
    original=seed['grants.gsr'];base=e.f.decode(members['promise.gsr'],'records','PROMISE')
    full,last,count=filled(original,base,LIMIT)
    e.need(t.plans.read(root/'full-journal.gsr',MAXIMUM)==full,'full journal exact fixture')
    for limit in (LIMIT+1,MAXIMUM+1):
        path=root/('refused-'+str(limit));selection.layout(path,{'before','after','result.json'},'full journal refusal')
        data,_,_=filled(original,base,limit);expected=dict(seed,**{'grants.gsr':data})
        for stage in ('before','after'):e.need(c.inventory(path/stage)==expected,'full journal refusal changed bytes')
        same(read(path/'result.json'),dict(type='IllegalArgumentException' if limit==LIMIT+1 else 'ReplicationException',
              message='combined pending/grant journal capacity' if limit==LIMIT+1 else 'authority member exceeds bound'),'full journal refusal reason')
    inputs=read(root/'inputs.json');plan=t.plans.decode((ref/'original-plan.gsbp').read_bytes(),(ref/'original-application.image').read_bytes(),details=True,size=3,source='EMPTY')
    paths=plan['plan']['descriptor']['paths'];next_ballot=dict(base['ballot'],counter=20_000_000)
    same(inputs,dict(node=paths[1]['path'],materialization=paths[2]['path'],observations=[],next=next_ballot,
         sharedMaximum=MAXIMUM,reservedBytes=ALLOWANCE,fixtureHistory='preconstructed-complete-abandoned-promises'),'full journal inputs')
    compact=original+last
    return dict(seed=seed,initial=dict(seed,**{'grants.gsr':full}),compact=compact,ballot=next_ballot,node=inputs['node'],fixtureFrames=count)


def new_grant(path,model):
    actual=c.inventory(path);old=model['seed'];_,members,packet=c.current(old);cap=packet['capsule']
    rows=c.journal(actual['grants.gsr'],cap['root'],'node-1');prefix=model['compact']
    e.need(len(rows)==6 and b''.join(r[1] for r in rows[:-2])==prefix and [r[0] for r in rows[-2:]]==['PROMISE','BASIS'],'full journal new grant history')
    promised,basis=rows[-2:];identifier=promised[2]['basisId']
    e.need(str(uuid.UUID(identifier))==identifier and identifier not in {r[2].get('basisId') for r in rows[:-2]},'full journal fresh source identity')
    fields=dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),ballot=model['ballot'],basisId=identifier)
    same(promised[2],fields,'full journal exact promise')
    same(basis[2],dict(fields,voter='node-1',cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),inventory=e.digest(packet['indexBytes']),accepted=None),'full journal exact basis')
    source='sources/'+identifier;expected=dict(old,**{'grants.gsr':prefix+promised[1]+basis[1],source:None,source+'/source.gscp':members['source.gscp']})
    expected.update({source+'/'+h+'.image':members[h+'.image'] for h in packet['images']})
    e.need(actual==expected,'full journal exact new source')
    return expected,e.digest(basis[1])


def rotate(state,compact,cut=None):
    # Exact-prefix recovery preserves a retained empty or already-written candidate.
    events=[];state=dict(state)
    if rotation.PENDING in state or state['grants.gsr']!=compact:
        if rotation.PENDING not in state:
            state[rotation.PENDING]=b'';events.append('JOURNAL_ROTATION_CREATED')
            if cut==events[-1]:return state,events
        for event in CUTS[1:]:
            if event=='JOURNAL_ROTATION_WRITTEN':state[rotation.PENDING]=compact
            if event=='JOURNAL_ROTATION_RENAMED':state.pop(rotation.PENDING);state['grants.gsr']=compact
            events.append(event)
            if cut==event:return state,events
    e.need(cut is None,'full journal absent rotation cut')
    return state,events


def output(path,label,events,mode,cut,final=None):
    e.need(t.plans.read(path/(label+'.stderr'),e.MIB)==b'','full journal stderr');rows=trace(path/(label+'.stdout'))
    if final:
        expected,basis=final
        same(rows[-1],dict(status='PASS',peakImages=3,basis=basis,journalBytes=len(expected['grants.gsr']),runtimeEnabled=False),'full journal result');rows=rows[:-1]
    if mode=='kill':
        same(rows[-1],dict(event='AWAITING_KILL',cut=cut),'full journal kill handshake');rows=rows[:-1]
    same(rows,[dict(event=v) for v in events],'full journal force order')
    same(read(path/(label+'.exit.json')),dict(exitCode=73 if mode=='halt' else 137 if mode=='kill' else 0,cut=cut or 'none',mode=mode),'full journal exit')


def grant_events():
    # Caller already entered CURRENT_BEFORE_CAPTURE before automatic rotation.
    events=[*capture.g.CUTS[:3],*capture.CUTS,'CURRENT_BEFORE_CAPTURE']
    events.insert(events.index('BASIS_WRITTEN'),'BASIS_PREFIX_WRITTEN')
    return events


def clean(path,model):
    selection.layout(path,{'first','duplicate'}|{s+x for s in ('first','duplicate') for x in ('.stdout','.stderr','.exit.json')},'full journal clean')
    final,basis=new_grant(path/'first',model);e.need(c.inventory(path/'duplicate')==final,'full journal duplicate bytes')
    output(path,'first',[*OPEN,'CURRENT_BEFORE_CAPTURE',*CUTS,*grant_events()],'none',None,(final,basis))
    output(path,'duplicate',[*OPEN,'CURRENT_BEFORE_CAPTURE','CURRENT_BEFORE_CAPTURE'],'none',None,(final,basis))


def case(path,model,mode,cut):
    members={'first','second','final'}|{s+x for s in ('fault','recovery','resume') for x in ('.stdout','.stderr','.exit.json')}
    if mode=='kill':members|={'lock.stdout','lock.stderr','lock.exit.json'}
    selection.layout(path,members,'full journal case')
    first,events=rotate(model['initial'],model['compact'],cut)
    e.need(c.inventory(path/'first')==first,'full journal first snapshot')
    output(path,'fault',[*OPEN,'CURRENT_BEFORE_CAPTURE',*events],mode,cut)
    point='JOURNAL_ROTATION_FORCED' if CUTS.index(cut)<3 else 'ACCEPT_ACTIVE_FORCED'
    if point=='JOURNAL_ROTATION_FORCED':second,events=rotate(first,model['compact'],point);events=OPEN+events
    else:second=first;events=OPEN[:-1]
    e.need(c.inventory(path/'second')==second,'full journal second snapshot');output(path,'recovery',events,'halt',point)
    _,events=rotate(second,model['compact']);final,basis=new_grant(path/'final',model)
    output(path,'resume',[*OPEN,*events,'CURRENT_BEFORE_CAPTURE',*grant_events()],'none',None,(final,basis))
    if mode=='kill':
        e.need((path/'lock.stderr').read_bytes()==b'','full journal lock stderr')
        same(trace(path/'lock.stdout'),[dict(event='LOCK_HELD',path=model['node']+'/replica.lock')],'full journal lock binding')
        same(read(path/'lock.exit.json'),dict(exitCode=0),'full journal lock exit')
    return dict(case=mode+'-'+cut,cut=cut,mode=mode,second=point,exitCodes=[73 if mode=='halt' else 137,73,0],status='PASS')


def validate(root):
    root=Path(root);names={'reference','full-journal.gsr','inputs.json','receipt.json','clean','refused-'+str(LIMIT+1),'refused-'+str(MAXIMUM+1)}
    names|={mode+'-'+cut for mode in ('halt','kill') for cut in CUTS};selection.layout(root,names,'full journal')
    model=derive(root);clean(root/'clean',model)
    rows=[case(root/(mode+'-'+cut),model,mode,cut) for mode in ('halt','kill') for cut in CUTS]
    same(read(root/'receipt.json'),dict(schema='gse-v53-full-journal-v1',status='PASS',cases=rows,freshProcesses=38,lockProbes=6,
         journalBytes=LIMIT,sharedMaximum=MAXIMUM,reservedBytes=ALLOWANCE,publicRuntime=False,powerLoss=False),'full journal receipt')
    return dict(status='PASS',cases=12,freshProcesses=38,lockProbes=6,journalBytes=LIMIT,sharedMaximum=MAXIMUM,reservedBytes=ALLOWANCE,
                fixtureFrames=model['fixtureFrames'],fixtureHistory='preconstructed-complete-abandoned-promises',publicBootstrap=True,publicRuntime=False,powerLoss=False,originalFirst=True),model


VARIANTS={'first-journal':'full journal first snapshot','second-candidate':'full journal second snapshot',
          'final-source':'full journal exact new source','force':'full journal force order','exit':'full journal exit',
          'stderr':'full journal stderr','result':'full journal result','kill-marker':'full journal kill handshake',
          'lock-path':'full journal lock binding','lock-stderr':'full journal lock stderr','lock-exit':'full journal lock exit'}


def qualify(root):
    root=Path(root);result,model=validate(root);negatives=[]
    for name,reason in VARIANTS.items():
        mode='kill' if name.startswith(('lock-','kill-')) else 'halt';cut=CUTS[0]
        with tempfile.TemporaryDirectory(prefix='v53-full-journal-negative-') as temp:
            moved=Path(temp)/'case';shutil.copytree(root/(mode+'-'+cut),moved)
            if name=='first-journal':(moved/'first/grants.gsr').write_bytes(model['compact'])
            elif name=='second-candidate':(moved/'second'/rotation.PENDING).write_bytes(b'')
            elif name=='final-source':(moved/'final/extra').write_bytes(b'unexpected')
            elif name in ('stderr','lock-stderr'):(moved/('fault.stderr' if name=='stderr' else 'lock.stderr')).write_bytes(b'error')
            elif name in ('exit','lock-exit'):
                path=moved/('fault.exit.json' if name=='exit' else 'lock.exit.json');value=read(path);value['exitCode']=1;path.write_bytes(e.f.canonical(value))
            else:
                path=moved/('resume.stdout' if name=='result' else 'lock.stdout' if name=='lock-path' else 'fault.stdout');values=trace(path)
                if name=='result':values[-1]['runtimeEnabled']=True
                elif name=='lock-path':values[0]['path']+='/other'
                else:values.pop()
                path.write_bytes(b''.join(e.f.canonical(v)+b'\n' for v in values))
            try:case(moved,model,mode,cut)
            except ValueError as error:e.need(str(error)==reason,'full journal wrong negative: '+name+': '+str(error))
            else:raise ValueError('full journal mutation accepted: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-full-journal-portable-') as temp:
        moved=Path(temp)/'raw';shutil.copytree(root,moved);same(validate(moved)[0],result,'full journal portable replay')
    return dict(**result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
