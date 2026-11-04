"""Replay explicit original-copy completion of the failed native floor.

The storage transition is derived from the diagnosed original proposal and the
admitted generation inventories. It is not autonomous discovery of missing copies
or independent full replay of the subsequent native continuation.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import combined_resource_probe as probe
from . import combined_recovery_observations as observed

h,c,e,f,need=probe.h,probe.c,probe.e,probe.f,probe.need
read=probe.history.d.read
NODES=observed.NODES


def validate(directory):
    root=Path(directory);inventory=h.inventory(root)
    need({p.name for p in root.iterdir()}=={'pressure','storage-resume','recovery','lineage.json','receipt.json'},'partial floor exact history inventory')
    probe.same(read(root/'receipt.json'),dict(schema='gse-v53-partial-floor-resume-v1',status='PASS',profile='4-REMOVE',pressureOutcome='FAIL',sameDirectories=True,
        partialFloorRecoveryQualified=False,automaticRuntimeReachabilityQualified=False,phase3Complete=False),'partial floor explicit recovery scope')
    diagnosis=probe.diagnose(root/'pressure');old=root/'pressure/4-REMOVE/history';storage=root/'storage-resume';native=root/'recovery'
    need({p.name for p in storage.iterdir()}=={'before','after-rejection','resumed','reopened','original-copies','original-proposal.gsr','rejection.json','result.json','calls.json','usage.json'},
         'partial floor storage inventory')
    walk=probe.history.a.prelude(old,'INTENT',size=4)
    installed=probe.history.install(old,walk.group,1,probe.history.topology(4)[0][1],current_maintenance=True)
    initial={n:c.inventory(old/'after-close'/n) for n in NODES}
    probe.history.b.match(storage,'before',initial);probe.history.b.match(storage,'after-rejection',initial)
    # The claimed originals must be each admitted original current generation,
    # including its complete image; retained snapshot hashes alone are not votes.
    need({p.name for p in (storage/'original-copies').iterdir()}==set(NODES),'partial floor complete original copy observations')
    offered={};references=[]
    for node in NODES:
        prefix,members,packet=c.current(installed[node]);manifest=installed[node][prefix+'generation.gsr']
        copies=dict(members,**{'generation.gsr':manifest})
        need(c.inventory(storage/'original-copies'/node)==copies,'partial floor admitted original generation copy')
        # Any prefix maintenance before failure may change ancillary directories,
        # but cannot silently substitute a different selected current generation.
        actual_prefix,actual_members,_=c.current(initial[node])
        need(initial[node][actual_prefix+'generation.gsr']==manifest and actual_members==members,'partial floor original current generation retained')
        if node!='node-4':
            offered[e.digest(manifest)]=copies
            references.append(dict(voter=node,generation=e.digest(manifest),catalog=packet['capsule']['catalog'],snapshot=packet['capsule']['application']))
    cap=c.current(installed['node-2'])[2]['capsule']
    proposal=f.encode('records','FLOOR',dict(root=cap['root'],node='node-2',cut=cap['cut'],sources=references))
    need((storage/'original-proposal.gsr').read_bytes()==initial['node-2']['floor-copies/proposal.gsr']==proposal,'partial floor exact original proposal')
    events,files,_,directories=probe.floor.transaction(offered,proposal)
    complete=dict(initial['node-2'],**{k:None for k in directories},**files)
    result=dict(initial,**{'node-2':complete})
    probe.history.b.match(storage,'resumed',result);probe.history.b.match(storage,'reopened',result)
    need(sum(k.endswith('.image') for k in complete)==7,'partial floor seven original physical images')
    need(initial['node-1']['pending.accept']==result['node-1']['pending.accept'] and initial['node-1']['pending.accept']!=c.EMPTY,
         'partial floor unresolved ACCEPT preserved')
    first=next(k.split('/')[1] for k in initial['node-2'] if k.startswith('floor-copies/') and k.endswith('/generation.gsr'))
    first_owner=f.decode(offered[first]['generation.gsr'],'records','GENERATION')['node']
    rejection='unrelated retained floor files' if first_owner=='node-3' else 'floor requires exact original proposal'
    probe.same(read(storage/'rejection.json'),dict(kind='java.lang.IllegalArgumentException',message=rejection),'partial floor original wrong-cohort rejection')
    calls=read(storage/'calls.json')
    need([(v['node'],v['operation']) for v in calls]==[(n,'original-copy') for n in NODES]+[('node-2',name) for name in ('wrong-cohort','exact-resume','cold-inspect')],
         'partial floor original storage calls')
    need(not any(event.startswith('FLOOR_') and event!='FLOOR_COPY_BEFORE_RETURN' for event in calls[4]['events']),
         'partial floor refused cohort cannot start a transaction')
    need([v for v in calls[5]['events'] if v.startswith('FLOOR_')]==['FLOOR_COPY_BEFORE_RETURN',*[v['event'] for v in events]],
         'partial floor exact resumed force order')
    usage=read(storage/'usage.json');expected=[(call['operation'],event) for call in calls if call['node']=='node-2' for event in call['events']]
    need(type(usage) is list and [(v['operation'],v['event']) for v in usage]==expected,'partial floor complete resource observations')
    for row in usage:
        value=row['usage'];need(type(value) is dict and set(value)=={'metadata','staging','queued','leases','counts'} and type(value['counts']) is dict and
            set(value['counts'])<=set(('GENERATION','SOURCE','LEARNER','JOURNAL','CATALOG','MISC','APPLICATION','CONTROL','WAITER')) and
            all(type(value[k]) is int and value[k]>=0 for k in ('metadata','staging','queued','leases')) and
            all(type(v) is int and v>0 for v in value['counts'].values()) and value['leases']==sum(value['counts'].values()) and
            value['counts'].get('APPLICATION',0)<=7 and value['counts'].get('SOURCE',0)<=6 and value['metadata']<=384*e.MIB and value['staging']<=512*e.MIB,
            'partial floor bounded resource observation')
    at_floor=[v for v in usage if v['operation']=='exact-resume' and v['event']=='FLOOR_BEFORE_RETURN']
    need(len(at_floor)==1 and at_floor[0]['usage']['counts']['APPLICATION']==7,'partial floor physical reservation retained')
    probe.same(read(storage/'result.json'),dict(status='PASS',originalCopies=3,applicationImages=7,explicitOriginalCopyRecovery=True,automaticRecovery=False,pendingAcceptPreserved=True),
               'partial floor component result scope')
    # Continuation remains an observation, not storage/transfer/cohort admission.
    probe.history.b.match(native,'before-network',result)
    for i,cohort in enumerate((('node-1','node-2','node-3'),('node-1','node-2','node-3'),('node-1','node-2')),1):
        selected=f.decode((native/f'selected-{i}.gsr').read_bytes(),'records','SELECTED')
        need(tuple(v['voter'] for v in selected['sources'])==cohort,'partial floor resumed voter in each cohort')
    need((native/'native-entry-5.gsr').read_bytes()==(old/'native-entry-5.gsr').read_bytes() and
         (native/'native-payload-5.bin').read_bytes()==(old/'native-payload-5.bin').read_bytes(),'partial floor continuation retains original command')
    for node in ('node-1','node-2'):
        state=c.current(c.inventory(native/'after-close'/node))[2]['capsule']
        need(state['root']==cap['root'] and state['cut']['index']==7 and state['cut']['view']['operation'] is None,'partial floor required voter observed stable barrier')
    probe.same(read(native/'result.json'),dict(status='PASS',activations=3,internalReady=True,publicReady=False),'partial floor native result scope')
    need(h.inventory(root)==inventory,'partial floor original changed')
    return dict(status='PASS',scope='explicit-original-copy-storage-resume',pressureOutcome='FAIL',wrongCohortRefused=True,
        forcedOriginalCopies=3,physicalImages=7,originalPendingAcceptPreserved=True,requiredVoterContinuation='OBSERVED',
        automaticRecoveryQualified=False,completeContinuationReplayQualified=False,phase3Complete=False,originalPreserved=True)


NEGATIVES={
    'scope':'partial floor explicit recovery scope','original-copy':'partial floor admitted original generation copy',
    'proposal':'partial floor exact original proposal','wrong-rejection':'partial floor original wrong-cohort rejection',
    'changed-refusal':'admitted exact after-rejection: node-2','lost-copy':'admitted exact resumed: node-2',
    'lost-accept':'admitted exact resumed: node-1','changed-cold-floor':'admitted exact reopened: node-2',
    'lost-force':'partial floor exact resumed force order','false-automatic':'partial floor component result scope',
    'lost-usage':'partial floor complete resource observations','invented-headroom':'partial floor physical reservation retained',
    'invented-resource':'partial floor bounded resource observation',
}

def mutate(root,name):
    storage=root/'storage-resume'
    if name=='original-copy':(storage/'original-copies/node-3/source.gscp').write_bytes(b'changed');return
    if name=='proposal':(storage/'original-proposal.gsr').write_bytes(b'changed');return
    if name=='changed-refusal':(storage/'after-rejection/node-2/allocator.gsr').write_bytes(b'changed');return
    if name=='lost-copy':next((storage/'resumed/node-2/floor-copies').glob('*/generation.gsr')).unlink();return
    if name=='lost-accept':(storage/'resumed/node-1/pending.accept').write_bytes(c.EMPTY);return
    if name=='changed-cold-floor':(storage/'reopened/node-2/floor-copies/floor.gsr').write_bytes(b'changed');return
    need(name in NEGATIVES,'partial floor declared mutation')
    path=root/'receipt.json' if name=='scope' else storage/('rejection.json' if name=='wrong-rejection' else 'calls.json' if name=='lost-force' else
        'result.json' if name=='false-automatic' else 'usage.json')
    value=read(path)
    if name=='scope':value['partialFloorRecoveryQualified']=True
    elif name=='wrong-rejection':value['message']='unrelated'
    elif name=='lost-force':value[5]['events'].remove('FLOOR_AUTHORITY_FORCED')
    elif name=='false-automatic':value['automaticRecovery']=True
    elif name=='lost-usage':value.pop()
    elif name=='invented-resource':value[0]['usage']['counts']['INVENTED']=1;value[0]['usage']['leases']+=1
    else:
        row=next(v for v in value if v['operation']=='exact-resume' and v['event']=='FLOOR_BEFORE_RETURN')['usage']
        row['counts']['APPLICATION']-=1;row['leases']-=1
    h.save(path,value)


def qualify(directory):
    root=Path(directory);before=h.inventory(root);original=validate(root);rows=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-partial-floor-negative-') as tmp:
            copy=Path(tmp)/'raw';shutil.copytree(root,copy);mutate(copy,name)
            try:validate(copy)
            except ValueError as error:need(str(error)==reason,'partial floor unrelated rejection: '+name+': '+str(error))
            else:raise ValueError('partial floor accepted mutation: '+name)
            rows.append(dict(case=name,status='REJECTED',reason=reason))
    need(h.inventory(root)==before,'partial floor original changed during negatives')
    return dict(storage=original,negatives=rows,originalPreserved=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
