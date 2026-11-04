"""Derive the resumed floor inventory; native discovery/continuation are observations.

This is not a complete wire/retirement replay or Phase 3 history admission.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import partial_floor_resume_evidence as prior

probe=prior.probe
h,c,e,f,need=prior.h,prior.c,prior.e,prior.f,prior.need
read=prior.read


def resume_events(members):
    events=['FLOOR_RESUME_RESERVED','FLOOR_PROPOSAL_WRITTEN','FLOOR_PROPOSAL_FORCED','FLOOR_COPY_CREATED',
            'FLOOR_MANIFEST_WRITTEN','FLOOR_MANIFEST_FORCED']
    for name in sorted(members):
        if name=='generation.gsr':continue
        kind='IMAGE' if name.endswith('.image') else 'MEMBER'
        events.extend(('FLOOR_'+kind+'_WRITTEN','FLOOR_'+kind+'_FORCED'))
    return events+['FLOOR_COPY_DIRECTORY_FORCED','FLOOR_RESUME_COPY_FORCED']


def validate(directory):
    root=Path(directory);before=h.inventory(root)
    need({p.name for p in root.iterdir()}=={'pressure','recovery','lineage.json','receipt.json','automatic-floor','floor-events.json','floor-usage.json'},
         'automatic floor exact history inventory')
    probe.same(read(root/'receipt.json'),dict(schema='gse-v53-automatic-floor-resume-v1',status='PASS',profile='4-REMOVE',pressureOutcome='FAIL',sameDirectories=True,
        partialFloorRecoveryQualified=False,automaticRuntimeReachabilityQualified=False,phase3Complete=False),'automatic floor bounded scope')
    probe.diagnose(root/'pressure');old=root/'pressure/4-REMOVE/history';native=root/'recovery'
    initial={n:c.inventory(old/'after-close'/n) for n in prior.NODES}
    probe.history.b.match(native,'before-network',initial)
    need(read(native/'calls.json')==[],'automatic floor no explicit storage completion')
    walk=probe.history.a.prelude(old,'INTENT',size=4)
    installed=probe.history.install(old,walk.group,1,probe.history.topology(4)[0][1],current_maintenance=True)
    offered={};by_node={};refs=[]
    for node in prior.NODES[:3]:
        prefix,members,packet=c.current(installed[node]);manifest=installed[node][prefix+'generation.gsr']
        actual_prefix,actual_members,_=c.current(initial[node])
        need(initial[node][actual_prefix+'generation.gsr']==manifest and actual_members==members,'automatic floor original generation retained')
        by_node[node]=dict(members,**{'generation.gsr':manifest});offered[e.digest(manifest)]=by_node[node]
        refs.append(dict(voter=node,generation=e.digest(manifest),catalog=packet['capsule']['catalog'],snapshot=packet['capsule']['application']))
    cap=c.current(installed['node-2'])[2]['capsule']
    proposal=f.encode('records','FLOOR',dict(root=cap['root'],node='node-2',cut=cap['cut'],sources=refs))
    need(initial['node-2']['floor-copies/proposal.gsr']==proposal,'automatic floor exact original proposal')
    events,files,_,directories=probe.floor.transaction(offered,proposal,handoff=True)
    complete=dict(initial['node-2'],**{k:None for k in directories},**files)
    need(c.inventory(root/'automatic-floor')==complete,'automatic floor exact resumed inventory')
    need(sum(k.endswith('.image') for k in complete)==7,'automatic floor seven physical images')
    captured=read(root/'floor-events.json');all_events=read(native/'events.json')
    need(type(captured) is list and captured and captured==all_events[:len(captured)] and captured[-1]==dict(node='node-2',event='FLOOR_BEFORE_RETURN'),
         'automatic floor captured native event prefix')
    own=[row['event'] for row in captured if row.get('node')=='node-2']
    # Each remote original is durably handed off before the next receiver. The
    # local duplicate is last; the existing full transaction writes authority.
    expected=sum((resume_events(by_node[n]) for n in ('node-1','node-3','node-2')),[])+[v['event'] for v in events]
    need([event for event in own if event.startswith('FLOOR_') and event!='FLOOR_COPY_BEFORE_RETURN']==expected,
         'automatic floor exact resume force order')
    usage=read(root/'floor-usage.json')
    # The hook is installed after cold-open validation and before start(). TCP
    # observations have their own NETWORK_ namespace, not storage callbacks.
    storage=own[own.index('FLOOR_COPY_BEFORE_RETURN'):]
    storage=[event for event in storage if not event.startswith('NETWORK_')]
    need(type(usage) is list and [v['event'] for v in usage]==storage,'automatic floor complete resource observations')
    for row in usage:
        value=row['usage'];need(type(value) is dict and set(value)=={'metadata','staging','queued','leases','counts'} and type(value['counts']) is dict and
            set(value['counts'])<=set(('GENERATION','SOURCE','LEARNER','JOURNAL','CATALOG','MISC','APPLICATION','CONTROL','WAITER')) and
            all(type(value[k]) is int and value[k]>=0 for k in ('metadata','staging','queued','leases')) and
            all(type(v) is int and v>0 for v in value['counts'].values()) and value['leases']==sum(value['counts'].values()) and
            value['counts'].get('APPLICATION',0)<=7 and value['counts'].get('SOURCE',0)<=6 and value['metadata']<=384*e.MIB and value['staging']<=512*e.MIB,
            'automatic floor bounded resource observations')
    need(usage[-1]['usage']['counts'].get('APPLICATION')==7,'automatic floor physical copies remain charged')
    # This exact original floor must finish before PREPARE can force its promise.
    need(not any(event.startswith(('PROMISE_','BASIS_','SELECTED_','INSTALL_')) for event in own),
         'automatic floor precedes fresh grant')
    entry=(old/'native-entry-5.gsr').read_bytes();payload=(old/'native-payload-5.bin').read_bytes()
    lineage=read(root/'lineage.json')
    need(type(lineage) is dict and set(lineage)=={'root','directories','retainedEntry','retainedPayload'} and lineage['root']==cap['root'] and
         lineage['retainedEntry']==e.digest(entry) and lineage['retainedPayload']==e.digest(payload),'automatic floor original lineage')
    paths=lineage['directories']
    need(type(paths) is list and len(paths)==4 and all(type(v) is dict and set(v)=={'node','replica','application'} for v in paths) and
         [v['node'] for v in paths]==list(prior.NODES) and all(type(v[k]) is str and Path(v[k]).is_absolute() for v in paths for k in ('replica','application')) and
         len({v[k] for v in paths for k in ('replica','application')})==8,'automatic floor original directory observations')
    need((native/'native-entry-5.gsr').read_bytes()==entry and (native/'native-payload-5.bin').read_bytes()==payload,'automatic floor inherited original command')
    for ordinal,cohort in enumerate((('node-1','node-2','node-3'),('node-1','node-2','node-3'),('node-1','node-2')),1):
        selected=f.decode((native/f'selected-{ordinal}.gsr').read_bytes(),'records','SELECTED')
        need(tuple(v['voter'] for v in selected['sources'])==cohort,'automatic floor required voter continuation')
    for node in ('node-1','node-2'):
        state=c.current(c.inventory(native/'after-close'/node))[2]['capsule']
        need(state['root']==cap['root'] and state['cut']['index']==7 and state['cut']['view']['operation'] is None,'automatic floor stable barrier observation')
    probe.same(read(native/'result.json'),dict(status='PASS',activations=3,internalReady=True,publicReady=False),'automatic floor native result scope')
    need(h.inventory(root)==before,'automatic floor original changed')
    return dict(status='PASS',scope='automatic-floor-storage',pressureOutcome='FAIL',forcedOriginalCopies=3,physicalImages=7,
        automaticDiscovery='OBSERVED',requiredVoterContinuation='OBSERVED',independentRemoteForceReplayQualified=False,
        completeContinuationReplayQualified=False,phase3Complete=False,originalPreserved=True)


NEGATIVES={
    'scope':'automatic floor bounded scope','explicit-resume':'automatic floor no explicit storage completion',
    'lost-floor':'automatic floor exact resumed inventory','lost-copy':'automatic floor exact resumed inventory',
    'changed-before':'admitted exact before-network: node-2','changed-event-prefix':'automatic floor captured native event prefix',
    'lost-force':'automatic floor exact resume force order','lost-usage':'automatic floor complete resource observations',
    'invented-headroom':'automatic floor physical copies remain charged','invented-resource':'automatic floor bounded resource observations',
    'changed-lineage':'automatic floor original lineage','changed-command':'automatic floor inherited original command',
}


def mutate(root,name):
    need(name in NEGATIVES,'automatic floor declared mutation')
    if name=='lost-floor':(root/'automatic-floor/floor-copies/floor.gsr').unlink();return
    if name=='lost-copy':next((root/'automatic-floor/floor-copies').glob('*/generation.gsr')).unlink();return
    if name=='changed-before':(root/'recovery/before-network/node-2/allocator.gsr').write_bytes(b'changed');return
    if name=='changed-command':(root/'recovery/native-payload-5.bin').write_bytes(b'changed');return
    if name=='explicit-resume':h.save(root/'recovery/calls.json',[dict(operation='explicit-resume')]);return
    if name=='lost-force':
        for path in (root/'floor-events.json',root/'recovery/events.json'):
            rows=read(path);rows.remove(next(v for v in rows if v.get('node')=='node-2' and v['event']=='FLOOR_RESUME_COPY_FORCED'));h.save(path,rows)
        return
    path=root/('receipt.json' if name=='scope' else 'floor-events.json' if name=='changed-event-prefix' else 'lineage.json' if name=='changed-lineage' else 'floor-usage.json')
    value=read(path)
    if name=='scope':value['phase3Complete']=True
    elif name=='changed-event-prefix':value.pop()
    elif name=='changed-lineage':value['retainedEntry']='00'*32
    elif name=='lost-usage':value.pop()
    elif name=='invented-resource':value[0]['usage']['counts']['INVENTED']=1;value[0]['usage']['leases']+=1
    else:value[-1]['usage']['counts']['APPLICATION']-=1;value[-1]['usage']['leases']-=1
    h.save(path,value)


def qualify(directory):
    root=Path(directory);before=h.inventory(root);original=validate(root);rows=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-automatic-floor-negative-') as tmp:
            copy=Path(tmp)/'raw';shutil.copytree(root,copy);mutate(copy,name)
            try:validate(copy)
            except ValueError as error:need(str(error)==reason,'automatic floor unrelated rejection: '+name+': '+str(error))
            else:raise ValueError('automatic floor accepted mutation: '+name)
            rows.append(dict(case=name,status='REJECTED',reason=reason))
    need(h.inventory(root)==before,'automatic floor original changed during negatives')
    return dict(storage=original,negatives=rows,originalPreserved=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
