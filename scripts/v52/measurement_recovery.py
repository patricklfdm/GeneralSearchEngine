"""Closed M04 recovery schedules; full process-generation evidence is separate."""
from pathlib import Path
import base64
import shutil
import time
from . import measurement_model as model,measurement_options as options
from . import measurement_runtime as runtime,measurement_bundle as bundle,token
from .evidence import need

CASES=('leader-sigkill-retained-restart','follower-snapshot-carried-token')
FILE='measurement-fault.json'


def fault_parameters(case):
    need(case in CASES,'measurement recovery case')
    return dict(schema='gse-v52-recovery-fault-v1',case=case)


def profile(case):
    return dict(schema='gse-v52-recovery-controller-v1',family='M04',case=case,mode='candidate-minimum',
                faultParameters=fault_parameters(case),readParameters=options.parameters(),programSha256=model.PLAN_SHA,
                setupUpdates=3,activationSeconds=40,recoverySeconds=80,pollIntervalNanos=100_000_000,businessRetries=0,
                resourceSampling='per-process-start-stop-or-declared-sigkill-prefix')


def partition(root,node=None):
    """Atomically install only a complete bidirectional single-voter cut."""
    need(node is None or node in ('node-1','node-2','node-3'),'measurement recovery blocked voter')
    rows=[] if node is None else sorted(f'{a} {b}' for a in ('node-1','node-2','node-3') for b in ('node-1','node-2','node-3')
                                      if a!=b and node in (a,b))
    root=Path(root);temporary=root/'network-blocks.pending';temporary.write_text(''.join(r+'\n' for r in rows))
    temporary.replace(root/'network-blocks.txt')


def prepare(root,case):return runtime.prepare(Path(root),'candidate-minimum',recovery_case=case)


def observe(root,workers,history,case,crash,restart,*,clock=time.monotonic_ns,sleep=time.sleep,partition_control=None):
    root=Path(root);plan=profile(case);details=dict(case=case,family='M04',stage='activation')
    cut=partition_control if partition_control is not None else lambda node=None:partition(root,node)
    receipt=dict(status='FAIL',execution='recovery-controller-only',qualifiedMeasurement=False,paidCloud=False,case=case)
    def wait(probe,label,seconds):
        until=clock()+seconds*1_000_000_000
        while clock()<until:
            value=probe()
            if value:return value
            sleep(plan['pollIntervalNanos']/1e9)
        raise ValueError('measurement recovery '+label)
    def ready(selected):
        values={n:workers[n].call('status') for n in sorted(selected)}
        need(all(v['state']!='FAILED' for v in values.values()),'measurement recovery failed voter')
        leaders=[n for n,v in values.items() if v['state']=='LEADER_READY']
        return (leaders[0],values) if len(leaders)==1 else None
    def floors(selected,index):
        values={n:workers[n].call('probe') for n in sorted(selected)}
        return values if all(v['queues']['recoveryFloorObserved']>=index for v in values.values()) else None
    def published(node,index,sequence,installed=False):
        state=workers[node].call('status');need(state['state']!='FAILED','measurement recovery failed target')
        probe=workers[node].call('probe') if installed else None
        return dict(status=state,probe=probe) if (state['state'] in ('FOLLOWER','LEADER_READY') and state['publishedIndex']>=index and
            state['sequence']==sequence and (not installed or probe['queues']['snapshotInstalledIndexObserved']>=index)) else None
    try:
        need(set(workers)=={'node-1','node-2','node-3'},'measurement recovery voter set')
        leader,states=wait(lambda:ready(set(workers)),'initial activation',plan['activationSeconds']);active=workers[leader]
        details.update(leader=leader,initialStatus=states,stage='initialization')
        updates=[c['document'] for c in model.program() if c['kind']=='update']
        details['setupUpdates']=[active.call('update',document=d)['opId'] for d in updates[:3]]
        initial=active.call('read',query=model.query(0),setupToken=True);details['initialRead']=initial['opId']
        need(initial['sequence']==4,'measurement recovery setup sequence')
        index=token.decode(base64.b64decode(initial['token'],validate=True))['index']
        details['baseline']=runtime.await_publication(workers,index,4,clock=lambda:clock()/1e9,sleep=sleep)
        details['baselineFloors']=wait(lambda:floors(set(workers),index),'baseline floor',plan['recoverySeconds'])
        details['sampleStarts']=[worker.call('sample-start')['opId'] for worker in workers.values()]
        details['carriedToken']=initial['token'];details['stage']='fault';runtime.save(root/'scenario.json',details)
        if case=='leader-sigkill-retained-restart':
            details['killIssuedNanos']=clock();details['crash']=crash(leader);details['exitObservedNanos']=clock()
            successor,states=wait(lambda:ready(set(workers)),'successor activation',plan['recoverySeconds']);service=workers[successor]
            details.update(successor=successor,successorStatus=states,readyObservedNanos=clock())
            write=service.call('update',document=updates[3]);details.update(progressWrite=write['opId'],writeObservedNanos=clock())
            strong=service.call('read',query=model.query(1),setupToken=True);details.update(successorStrong=strong['opId'],strongObservedNanos=clock())
            minimum=service.call('read',query=model.query(2),minimum=initial['token']);details.update(successorMinimum=minimum['opId'],minimumObservedNanos=clock())
            details['restartIssuedNanos']=clock();restart(leader);details['restartStartedNanos']=clock()
            details['sampleStarts'].append(workers[leader].call('sample-start')['opId'])
            later=token.decode(base64.b64decode(strong['token'],validate=True))['index']
            details['recovered']=wait(lambda:published(leader,later,5),'retained restart publication',plan['recoverySeconds'])
            observed=workers[leader].call('read',query=model.query(3),minimum=initial['token'])
            details.update(restartedMinimum=observed['opId'],restartedReadObservedNanos=clock())
        else:
            probe=active.call('probe');status=active.call('status');mask=probe['queues']['selectedVotersObserved']
            need(status['state']=='LEADER_READY' and probe['queues']['selectedEpochObserved']==status['epoch'] and
                 type(mask) is int and mask in (3,5,6) and mask&(1<<(int(leader[-1])-1)),
                 'measurement recovery selected pair changed')
            follower=next(n for n in workers if not mask&(1<<(int(n[-1])-1)));target=workers[follower]
            details.update(target=follower,selectedProbe=probe['opId'],selectedStatus=status['opId'])
            cut(follower);details['partitionNanos']=clock();details['isolatedStatus']=target.call('status')
            write=active.call('update',document=updates[3]);details['progressWrite']=write['opId']
            later=active.call('read',query=model.query(1),setupToken=True);details['laterStrong']=later['opId']
            later_index=token.decode(base64.b64decode(later['token'],validate=True))['index']
            details['sourceFloors']=wait(lambda:floors(set(workers)-{follower},later_index),'snapshot source floor',plan['recoverySeconds'])
            held=target.call('status');need(held['sequence']==4 and held['publishedIndex']<later_index,'measurement recovery target did not lag')
            details['heldStatus']=held;details['healIssuedNanos']=clock();cut();details['healCompletedNanos']=clock()
            details['installed']=wait(lambda:published(follower,later_index,5,True),'snapshot install/publication',plan['recoverySeconds'])
            need(details['installed']['status']['state']=='FOLLOWER','measurement recovery snapshot target became leader')
            details['publicationObservedNanos']=clock()
            old=target.call('read',query=model.query(2),minimum=initial['token']);details['oldMinimum']=old['opId']
            new=target.call('read',query=model.query(3),minimum=later['token']);details.update(newMinimum=new['opId'],minimumObservedNanos=clock())
        details['sampleStops']=[worker.call('sample-stop')['opId'] for worker in workers.values()]
        details['stage']='observed';receipt.update(status='OBSERVED');return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:runtime.save(root/'scenario.json',details);runtime.save(root/'controller.json',receipt)


def execute_prepared(root,binding,cp,*,worker_factory=runtime.Worker):
    from .public_reads_evidence import read
    root=Path(root).resolve();plan=profile(binding.get('measurementProfile',{}).get('case'))
    need(read(root/'binding.json')==binding and binding['measurementProfile']==plan and binding['mode']=='candidate-minimum' and
         binding['readParameters']==options.parameters() and binding['faultParameters']==read(root/FILE)==plan['faultParameters'] and
         not (root/options.FILE).exists() and not {'driverExercise','smokeInitialization','readConfigurationOnly'}&set(binding),
         'measurement recovery prepared binding/profile')
    workers={};history=[];processes=[];failure=None;close_errors=[]
    def record(worker):
        processes.append(dict(node=worker.node,pid=worker.proc.pid,generation=worker.generation,
                              exitCode=worker.proc.returncode,identity=worker.identity))
    def start(node,generation):
        worker=worker_factory(root,node,cp,binding['mode'],history,generation=generation);workers[node]=worker
        for component in ('core','replication'):
            path=Path(worker.identity[component+'Source'])
            need(path.parent==root/'artifacts' and runtime.digest(path.read_bytes())==binding['artifacts'][path.name],
                 'measurement recovery loaded artifact')
        need(worker.identity['readParameters']==binding['readParameters'],'measurement recovery observed read parameters')
    def crash(node):
        worker=workers[node];worker.proc.kill();error=None
        try:
            need(worker.proc.wait(timeout=10)==-9,'measurement recovery unexpected abrupt exit')
        except BaseException as problem:error=problem
        try:worker.stop(kill=True)
        except BaseException as problem:
            if error is None:error=problem
            else:close_errors.append(dict(node=node,type=type(problem).__name__,message=str(problem)))
        finally:record(worker);workers.pop(node)
        if error is not None:raise error
        before=root/'pre-reopen'/node;shutil.copytree(root/node,before)
        return dict(node=node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode,preReopen=bundle.members(before))
    try:
        for i in (1,2,3):start(f'node-{i}',1)
        return observe(root,workers,history,plan['case'],crash,lambda node:start(node,2))
    except BaseException as error:failure=dict(type=type(error).__name__,message=str(error));raise
    finally:
        if plan['case']=='follower-snapshot-carried-token':
            try:partition(root)
            except BaseException as error:close_errors.append(dict(node='network-controls',type=type(error).__name__,message=str(error)))
        for node,worker in workers.items():
            try:worker.stop()
            except BaseException as error:close_errors.append(dict(node=node,type=type(error).__name__,message=str(error)))
            record(worker)
        runtime.save(root/'history.json',history);runtime.save(root/'processes.json',processes)
        runtime.save(root/'execution.json',dict(status='STOPPED' if failure is None and not close_errors else 'FAIL',
            qualifiedMeasurement=False,paidCloud=False,failure=failure,closeErrors=close_errors))
        if close_errors and failure is None:raise ValueError('measurement recovery close failures: '+str(close_errors))
