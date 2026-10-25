"""Exact interrupted adoption from independently replayed admitted originals."""
from pathlib import Path
from scripts.v53 import admitted_cross_view_evidence as q
from scripts.v53 import generation_install_evidence as install
from scripts.v53 import adoption_install_evidence as adoption
from scripts.v53.covered_context_process_evidence import force_trace
from scripts.v53.retirement_source_process_evidence import same,read,trace

e,c,t,selection=q.e,q.c,q.t,q.selection
CUTS=adoption.CUTS
OPEN=list(install.c.OPEN)+['ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED']


def target_paths(descriptor,node):
    # Verified backup plans include the immutable source path after the operation
    # directory. It is not a target. Bind by the original identity, not list size.
    identities=[v['node'] for v in descriptor['identities']]
    e.need(identities.count(node)==1,'admitted adoption target identity')
    offset=1+(descriptor['source']!='EMPTY')+2*identities.index(node)
    paths=descriptor['paths']
    return dict(node=paths[offset]['path'],materialization=paths[offset+1]['path'])


def original(root,size,backup):
    # A complete original reference must pass before any interruption is evaluated.
    q.validate_case(root/'reference',size,backup)
    w=q.Walk(root/'reference',size,backup);w.publish('BARRIER')
    members,packet,cap,state=w.state();next_nodes=w.active[:-1];removed=w.active[-1]
    identities={v['node']:v for v in state['identities']}
    request=dict(root=cap['root'],expected=e.authority(cap['root'],cap['cut']['view']),number=1,kind='REMOVE',target=[identities[n] for n in next_nodes])
    w.publish('RESERVE',dict(request=request));w.publish('PREPARE',dict(number=1,revision=1));w.publish('READY',dict(number=1,receipt=None));w.publish('SEAL',dict(number=1))
    operation=w.state()[3]['results'][-1]
    w.publish('INTENT',dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}));w.campaign(next_nodes)
    w.publish('FINAL',dict(binding=operation['binding']),next_nodes);w.active=next_nodes
    initial=w.group[removed]
    _,members,packet=c.current(w.group[next_nodes[0]])
    expected_remote={'source.gscp':members['source.gscp'],**{h+'.image':members[h+'.image'] for h in packet['images']}}
    e.need(c.inventory(root/'remote')==expected_remote,'admitted adoption original remote')
    inputs=read(root/'inputs.json');e.exact(inputs,'node materialization observations')
    plan=t.plans.decode((w.root/'original-plan.gsbp').read_bytes(),(w.root/'original-application.image').read_bytes(),details=True,size=size,source='VERIFIED_DURABLE_BACKUP' if backup else 'EMPTY')
    same({k:inputs[k] for k in ('node','materialization')},target_paths(plan['plan']['descriptor'],removed),'admitted adoption original paths')
    e.need(type(inputs['observations']) is list and len(inputs['observations'])==len(w.observed) and {e.f.canonical(v) for v in inputs['observations']}==w.observed,'admitted adoption original observations')
    w.removed(1,removed)
    return initial,w.group[removed],inputs


def transaction(initial,final,cut=None):
    state=dict(initial);events=[]
    def emit(event):events.append((event,dict(state)))
    for event in OPEN:emit(event)
    if state['selector.gsr']!=final['selector.gsr']:
        emit('ADOPTION_INSTALL_VALIDATED')
        if state['grants.gsr']!=final['grants.gsr']:
            e.need(final['grants.gsr'].startswith(state['grants.gsr']),'admitted adoption retained journal prefix')
            added=final['grants.gsr'][len(state['grants.gsr']):];e.f.decode(added,'records','PROMISE')
            emit('PROMISE_BEFORE_WRITE');state['grants.gsr']=final['grants.gsr'];emit('PROMISE_WRITTEN');emit('PROMISE_FORCED')
        emit('ADOPTION_INSTALL_FENCED');emit('INSTALL_RESERVED')
        selected=e.f.decode(final['selector.gsr'],'records','SELECTOR');directory='generations/'+selected['generation'];prefix=directory+'/'
        state[directory]=None;emit('INSTALL_DIRECTORY_CREATED')
        members={k[len(prefix):]:v for k,v in final.items() if k.startswith(prefix)}
        state[prefix+'generation.gsr']=members['generation.gsr'];emit('INSTALL_MANIFEST_WRITTEN');emit('INSTALL_MANIFEST_FORCED')
        for name in sorted(set(members)-{'generation.gsr'}):
            kind='INSTALL_IMAGE' if name.endswith('.image') else 'INSTALL_MEMBER'
            state[prefix+name]=members[name];emit(kind+'_WRITTEN');emit(kind+'_FORCED')
        emit('INSTALL_GENERATION_FORCED');state['selector.pending.gsr']=final['selector.gsr'];emit('INSTALL_SELECTOR_WRITTEN');emit('INSTALL_SELECTOR_FORCED')
        state['selector.gsr']=state.pop('selector.pending.gsr');emit('INSTALL_SELECTOR_RENAMED');emit('INSTALL_PARENT_FORCED')
        for event in install.c.OPEN:emit(event)
        emit('ADOPTION_INSTALL_BEFORE_RETURN')
    # The removed voter's fresh grant is refused without changing any authority.
    emit('CURRENT_BEFORE_CAPTURE');e.need(state==final,'admitted adoption final transaction')
    if cut is not None:
        found=[i for i,(event,_) in enumerate(events) if event==cut];e.need(bool(found),'admitted adoption missing cut');events=events[:found[0]+1]
    return events[-1][1],[event for event,_ in events]


def validate_case(root,initial,final,inputs,mode,cut):
    name=mode+'-'+cut;case=root/name
    files={'first','second','final'}|{label+ext for label in ('fault','recovery','resume') for ext in ('.stdout','.stderr','.exit.json')}
    if mode=='kill':files|={'lock.stdout','lock.stderr','lock.exit.json'}
    selection.layout(case,files,'admitted adoption process case')
    second='ACCEPT_ACTIVE_FORCED' if cut in ('INSTALL_SELECTOR_RENAMED','INSTALL_PARENT_FORCED','ADOPTION_INSTALL_BEFORE_RETURN') else 'INSTALL_SELECTOR_FORCED'
    state=initial;peak=None
    for stage,label,point,death in [('first','fault',cut,mode),('second','recovery',second,'halt'),('final','resume',None,'none')]:
        e.need(t.plans.read(case/(label+'.stderr'),e.MIB)==b'','admitted adoption stderr')
        state,events=transaction(state,final,point);e.need(c.inventory(case/stage)==state,'admitted adoption exact '+stage)
        e.need(sum(n.endswith('.image') for n in state)<=7,'admitted adoption image count')
        value=force_trace(trace(case/(label+'.stdout')),events,death,point,stage=='final')
        if value is not None:peak=value
        same(read(case/(label+'.exit.json')),dict(exitCode=73 if death=='halt' else 137 if death=='kill' else 0,cut=point or 'none',mode=death),'admitted adoption exact '+stage+' exit')
    if mode=='kill':
        e.need(t.plans.read(case/'lock.stderr',e.MIB)==b'','admitted adoption lock stderr')
        same(trace(case/'lock.stdout'),[dict(event='LOCK_HELD',path=inputs['node']+'/replica.lock')],'admitted adoption lock path')
        same(read(case/'lock.exit.json'),dict(exitCode=0),'admitted adoption lock exit')
    return dict(case=name,mode=mode,cut=cut,second=second,status='PASS',exitCodes=[73 if mode=='halt' else 137,73,0]),peak


def validate_profile(root,size,backup):
    expected={'reference','remote','inputs.json','receipt.json'}|{m+'-'+cut for m in ('halt','kill') for cut in CUTS}
    selection.layout(root,expected,'admitted adoption profile')
    initial,final,inputs=original(root,size,backup);rows=[];peaks=[]
    for mode in ('halt','kill'):
        for cut in CUTS:
            row,peak=validate_case(root,initial,final,inputs,mode,cut);rows.append(row);peaks.append(peak)
    same(read(root/'receipt.json'),dict(schema='gse-v53-admitted-adoption-process-v1',status='PASS',cases=rows,
         freshProcesses=114,lockProbes=19,inputsSha256=e.digest((root/'inputs.json').read_bytes()),publicBootstrap=True,powerLoss=False,runtimeEnabled=False),'admitted adoption receipt')
    return dict(case=root.name,status='PASS',cases=38),max(peaks),(initial,final,inputs)


def validate(root):
    root=Path(root);names=[f'size-{size}-{source}' for size in (5,4) for source in ('empty','backup')]
    selection.layout(root,{'receipt.json',*names},'admitted adoption matrix')
    rows=[];peaks=[];originals={}
    for size in (5,4):
        for backup in (False,True):
            name=f'size-{size}-'+('backup' if backup else 'empty')
            row,peak,original=validate_profile(root/name,size,backup);rows.append(row);peaks.append(peak);originals[name]=original
    same(read(root/'receipt.json'),dict(schema='gse-v53-admitted-adoption-matrix-v1',status='PASS',profiles=rows,cases=152,
         freshProcesses=456,lockProbes=76,publicBootstrap=True,powerLoss=False,runtimeEnabled=False),'admitted adoption matrix receipt')
    return dict(status='PASS',profiles=4,cases=152,freshProcesses=456,lockProbes=76,peakImages=max(peaks),
                publicBootstrap=True,publicRuntime=False,powerLoss=False,maximalCapacity=False,originalFirst=True),originals


# Full original matrix first, then mutate only individual copied cases against
# the cached independently verified originals. Do not duplicate the whole matrix.
VARIANTS={'first-journal':'admitted adoption exact first','second-selector':'admitted adoption exact second',
          'final-extra':'admitted adoption exact final','original-admission':'admitted adoption exact first',
          'force':'context process exact force/death order','kill-handshake':'context process kill handshake',
          'returned-runtime':'context process result scope','exit-code':'admitted adoption exact first exit',
          'stderr':'admitted adoption stderr','lock-path':'admitted adoption lock path',
          'lock-exit':'admitted adoption lock exit','lock-stderr':'admitted adoption lock stderr'}


def qualify(root):
    import tempfile,shutil
    root=Path(root);result,originals=validate(root);negative=[];profile=root/'size-5-empty';initial,final,inputs=originals[profile.name]
    for name,reason in VARIANTS.items():
        mode='kill' if name.startswith('lock-') or name=='kill-handshake' else 'halt';cut='INSTALL_SELECTOR_FORCED';case_name=mode+'-'+cut
        with tempfile.TemporaryDirectory(prefix='v53-admitted-adoption-negative-') as tmp:
            copied=Path(tmp);case=copied/case_name;shutil.copytree(profile/case_name,case)
            if name=='first-journal':(case/'first/grants.gsr').write_bytes(initial['grants.gsr'])
            elif name=='second-selector':(case/'second/selector.gsr').write_bytes(final['selector.gsr'])
            elif name=='final-extra':(case/'final/extra').write_bytes(b'unowned')
            elif name=='original-admission':
                path=next(p for p in (case/'first').iterdir() if 'admission' in p.name);path.write_bytes(b'changed-original')
            elif name in ('stderr','lock-stderr'):(case/('fault.stderr' if name=='stderr' else 'lock.stderr')).write_bytes(b'error')
            elif name in ('force','returned-runtime','kill-handshake','lock-path'):
                path=case/('resume.stdout' if name=='returned-runtime' else 'lock.stdout' if name=='lock-path' else 'fault.stdout');rows=trace(path)
                if name in ('force','kill-handshake'):rows.pop()
                elif name=='returned-runtime':rows[-1]['runtimeEnabled']=True
                else:rows[0]['path']+='/wrong'
                path.write_bytes(b''.join(e.f.canonical(v)+b'\n' for v in rows))
            else:
                path=case/('lock.exit.json' if name=='lock-exit' else 'fault.exit.json');value=read(path);value['exitCode']=2 if name=='lock-exit' else 0;path.write_bytes(e.f.canonical(value))
            try:validate_case(copied,initial,final,inputs,mode,cut)
            except ValueError as error:e.need(str(error)==reason,'admitted adoption unrelated negative: '+name+': '+str(error))
            else:raise ValueError('admitted adoption accepted mutation: '+name)
            negative.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(**result,negativeCases=negative,negativeScope='original-first-case-mutations')


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();print(json.dumps(qualify(a.root),sort_keys=True))
