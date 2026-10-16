"""M02/M03 controllers. Complete physical admission and the machine freeze are separate."""
import base64
import time
from pathlib import Path
from . import measurement_model as model,measurement_options as options,measurement_runtime as runtime
from . import measurement_load as load,token
from .evidence import need

CASES=tuple(f'm02-{relation}-{wait}' for relation in ('below','equal','above') for wait in (0,1000,5000))+('m03-p4','m03-p65')
MODE='candidate-minimum'


def profile(case):
    need(case in CASES,'measurement minimum case')
    if case.startswith('m02-'):
        _,relation,wait=case.split('-');parameters=options.parameters('M02',wait=int(wait));reads=30
    else:
        relation='above';parameters=options.parameters('M03',wait=60000,pending=int(case.split('p')[1]));reads=min(64,parameters['pendingLimit']-1)
    return dict(schema='gse-v52-minimum-controller-v1',case=case,family=parameters['family'],mode=MODE,parameters=parameters,
                programSha256=model.PLAN_SHA,relation=relation,readCount=reads,setupUpdates=3,
                readTarget='initial-leader' if parameters['family']=='M03' else 'selected-quorum-follower',
                releaseUpdate=parameters['family']=='M03' or relation=='above' and parameters['waitTimeoutMillis']>0,
                releaseDelayNanos=250_000_000 if parameters['family']=='M02' and relation=='above' and parameters['waitTimeoutMillis']>0 else 0,
                activationSeconds=40,floorSeconds=80,gateSeconds=10,pollIntervalNanos=100_000_000,
                drainSeconds=75 if parameters['family']=='M03' else 35,businessRetries=0)


def selected_follower(leader,queues):
    """Freeze the voting follower, not the passive snapshot recipient."""
    nodes=('node-1','node-2','node-3');mask=queues.get('selectedVotersObserved');epoch=queues.get('selectedEpochObserved')
    need(leader in nodes and type(mask) is int and mask in (3,5,6) and
         mask & (1<<nodes.index(leader)) and type(epoch) is int and epoch>0,
         'measurement minimum selected quorum unavailable')
    return next(n for i,n in enumerate(nodes) if n!=leader and mask & (1<<i))


def lower_bound(carried,index,relation):
    value=token.decode(base64.b64decode(carried,validate=True))
    need(type(index) is int and index>=value['index']>0 and relation in ('below','equal','above'),'measurement minimum baseline index/relation')
    value['index']=index+{'below':-1,'equal':0,'above':1}[relation]
    return base64.b64encode(token.encode(value)).decode()


def prepare(root,case):
    plan=profile(case);binding,cp,control=runtime.prepare(root,MODE,read_profile=plan['parameters'])
    binding.pop('readConfigurationOnly');binding['measurementProfile']=plan
    runtime.save(root/'binding.json',binding);return binding,cp,control


def observe(root,workers,history,case,*,clock=time.monotonic_ns,sleep=time.sleep):
    root=Path(root);plan=profile(case);model.load();p=plan['parameters'];details=dict(case=case,family=plan['family'],stage='activation')
    receipt=dict(status='FAIL',execution='minimum-controller-only',qualifiedMeasurement=False,paidCloud=False,case=case)
    operations=[];observed=dict(operations=[],drained=False)
    def submit(worker,row,kind,**values):
        row.update(offerNanos=clock(),completionStatus='NOT_OBSERVED')
        try:
            identity,future=worker.submit(kind,**values)
            row.update(opId=identity,submittedNanos=clock(),status='DISPATCHED');operations.append((row,future));return identity,future
        except BaseException as error:
            row.update(submittedNanos=clock(),status='DISPATCH_FAILED',failure=dict(type=type(error).__name__,message=str(error)));raise
    def until(due):
        while clock()<due:sleep(max(0,(due-clock())/1e9))
    def check_gate(probe,description,seconds,futures=()):
        end=clock()+seconds*1_000_000_000
        while clock()<end:
            result=probe()
            if result:return result
            need(not futures or not all(f.done() for f in futures),description+'; all original calls completed before gate')
            sleep(plan['pollIntervalNanos']/1e9)
        raise ValueError(description)
    try:
        need(set(workers)=={'node-1','node-2','node-3'},'measurement minimum voter set')
        def ready():
            states={n:w.call('status') for n,w in workers.items()}
            need(all(v['state']!='FAILED' for v in states.values()),'measurement minimum voter failed')
            leaders=[n for n,v in states.items() if v['state']=='LEADER_READY']
            return leaders[0] if len(leaders)==1 else None
        leader=check_gate(ready,'measurement minimum activation timeout',plan['activationSeconds'])
        active=workers[leader]
        updates=[c['document'] for c in model.program() if c['kind']=='update'];details.update(leader=leader,stage='initialization')
        details['setupUpdates']=[active.call('update',document=doc)['opId'] for doc in updates[:3]]
        initial=active.call('read',query=model.query(0),setupToken=True);details['initialRead']=initial['opId']
        need(initial['sequence']==4,'measurement minimum setup application sequence')
        initial_index=token.decode(base64.b64decode(initial['token'],validate=True))['index']
        details['baseline']=runtime.await_publication(workers,initial_index,4,clock=lambda:clock()/1e9,sleep=sleep)
        def floors():
            probes={n:w.call('probe') for n,w in workers.items()}
            return probes if all(v['queues']['recoveryFloorObserved']>=initial_index for v in probes.values()) else None
        details['floorProbes']=check_gate(floors,'measurement minimum baseline recovery floor',plan['floorSeconds'])
        target=leader if plan['family']=='M03' else selected_follower(leader,details['floorProbes'][leader]['queues'])
        reader=workers[target];details['readTarget']=target
        actual=reader.call('status');need(actual['sequence']==4 and actual['publishedIndex']>=initial_index and
            actual['state']==('LEADER_READY' if target==leader else 'FOLLOWER'),'measurement minimum prepared target changed')
        leader_status=active.call('status')
        need(leader_status['state']=='LEADER_READY' and leader_status['epoch']==details['floorProbes'][leader]['queues']['selectedEpochObserved'],
             'measurement minimum initial leader changed')
        baseline=reader.call('probe');count=baseline['queues']['readAdmissionsObserved']
        minimum=lower_bound(initial['token'],actual['publishedIndex'],plan['relation'])
        details.update(baselineStatus=actual,baselineProbe=baseline['opId'],minimum=minimum,stage='reads',readOps=[])
        offered=[dict(kind='read',ordinal=i,status='NOT_DISPATCHED') for i in range(plan['readCount'])]
        if plan['family']=='M03':offered.append(dict(kind='excess',status='NOT_DISPATCHED'))
        if plan['releaseUpdate']:offered.append(dict(kind='release-update',status='NOT_DISPATCHED'))
        observed['operations']=offered
        runtime.save(root/'scenario.json',details)
        for worker in workers.values():worker.call('sample-start')
        for ordinal in range(plan['readCount']):
            identity,_=submit(reader,offered[ordinal],'read',query=model.query(ordinal),minimum=minimum)
            details['readOps'].append(identity)
        expected=count+plan['readCount']
        def admitted():
            result=reader.call('probe');queues=result['queues']
            need(queues['readAdmissionsObserved']<=expected,'measurement minimum undeclared admission')
            if plan['family']=='M03':
                need(not any(f.done() for row,f in operations if row['kind']=='read'),'measurement saturation waiter settled before full gate')
                settled=(queues['readsOwned']==queues['readsWaiting']==queues['readsAlarms']==plan['readCount'] and
                         queues['readsCaptured']==queues['readsSettling']==0 and queues['admissionAvailable']==1)
            else:settled=True
            return result if queues['readAdmissionsObserved']==expected and settled else None
        gate=check_gate(admitted,'measurement minimum requests not admitted',plan['gateSeconds'],[f for _,f in operations])
        details['admittedProbe']=gate['opId'];details['gateNanos']=clock()
        held=reader.call('status');need(held['publishedIndex']==actual['publishedIndex'] and held['sequence']==4,
                                     'measurement minimum unplanned publication progress')
        details['heldStatus']=held
        if plan['family']=='M03':
            identity,future=submit(reader,offered[plan['readCount']],'read',query=model.query(plan['readCount']),minimum=minimum)
            details['excessRead']=identity
            excess=future.result(timeout=10)
            need(excess is not None and excess['outcome']=='NOT_APPLICABLE' and excess.get('reasonCode')=='CAPACITY_EXCEEDED',
                 'measurement saturation excess was not rejected')
            rejected=admitted();need(rejected is not None,'measurement saturation changed after excess rejection')
            details['rejectedProbe']=rejected['opId']
        if plan['releaseUpdate']:
            until(details['gateNanos']+plan['releaseDelayNanos']);details['releaseOfferNanos']=clock()
            identity,_=submit(active,offered[-1],'update',document=updates[3]);details['releaseUpdate']=identity
        details['stage']='drain';runtime.save(root/'scenario.json',details)
        load.drain(observed,operations,plan['drainSeconds'],clock=clock);observed['drained']=True
        need(observed['unobserved']==0 and all(row['completionStatus']=='OBSERVED' and row['response'] is not None for row,_ in operations),
             'measurement minimum incomplete original futures')
        if plan['family']=='M03':
            need(all(row['response']['outcome']=='SUCCESS' for row,_ in operations if row['kind']!='excess'),
                 'measurement reserved writer/waiter did not complete')
        elif plan['releaseUpdate']:
            need(operations[-1][0]['response']['outcome']=='SUCCESS','measurement minimum release update failed')
        def idle():
            result=reader.call('probe');v=result['queues']
            return result if v['admissionAvailable']==p['pendingLimit'] and all(v[k]==0 for k in
                ('readsOwned','readsWaiting','readsCaptured','readsSettling','readsAlarms','readsMarker')) else None
        details['finalProbe']=check_gate(idle,'measurement minimum ownership did not drain',plan['gateSeconds'])['opId']
        for worker in workers.values():worker.call('sample-stop')
        details['stage']='observed';receipt.update(status='OBSERVED',reads=plan['readCount'],operations=len(operations));return receipt
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        runtime.save(root/'scenario.json',details)
        runtime.save(root/'observed.json',observed)
        runtime.save(root/'controller.json',receipt)


def execute_prepared(root,binding,cp,*,worker_factory=runtime.Worker):
    from .public_reads_evidence import read
    root=Path(root).resolve();need(read(root/'binding.json')==binding,'measurement minimum prepared binding changed')
    plan=profile(binding.get('measurementProfile',{}).get('case'))
    need(binding['mode']==MODE and binding['measurementProfile']==plan and binding['readParameters']==plan['parameters'] and
         read(root/options.FILE)==plan['parameters'] and 'readConfigurationOnly' not in binding,'measurement minimum prepared profile')
    need('faultParameters' not in binding and not (root/'measurement-fault.json').exists(),'measurement minimum undeclared fault controls')
    return runtime.execute_observer(root,binding,cp,lambda workers,history:observe(root,workers,history,plan['case']),
                                    worker_factory=worker_factory,label='measurement minimum')
