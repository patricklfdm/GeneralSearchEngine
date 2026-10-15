"""Full M01 controller; admission and physical qualification are separate.

No CLI is exposed before the complete machine execution freeze. Tests inject a
virtual clock/consumer; they never qualify a simulated history as a measurement.
"""
import time
from pathlib import Path
from . import measurement_model as model,measurement_load as load,measurement_window as window
from . import measurement_runtime as runtime
from . import measurement_options as options
from .evidence import need

MARKERS=(dict(name='warmup-start',offsetNanos=0),dict(name='measured-start',offsetNanos=60_000_000_000),
         dict(name='measured-end',offsetNanos=180_000_000_000))
ACTIVATION_SECONDS=40
DRAIN_SECONDS=35


def profile(mode,repetition):
    need(mode in model.MODES and type(repetition) is int and 1<=repetition<=3,'measurement M01 mode/repetition')
    return dict(schema='gse-v52-m01-controller-v1',family='M01',mode=mode,repetition=repetition,
                programSha256=model.PLAN_SHA,durationNanos=window.DURATION,markers=[dict(v) for v in MARKERS],
                initialization='initial-strong-read-and-sequence-one-targets',activationSeconds=ACTIVATION_SECONDS,
                publicationSeconds=40,drainSeconds=DRAIN_SECONDS,businessRetries=0)


def observe(root,workers,history,mode,repetition,*,clock=time.monotonic_ns,sleep=time.sleep):
    """Use existing three live consumers; preserve all results even on failure.

    The owning process wrapper must always stop the consumers and retain traces,
    identities, history and close failures. This function never re-elects a read
    target or resubmits a rejected/uncertain business request.
    """
    root=Path(root);plan=profile(mode,repetition);model.load()
    need(set(workers)=={'node-1','node-2','node-3'},'measurement M01 voter set')
    scenario=dict(mode=mode,repetition=repetition,family='M01',stage='activation')
    result=dict(status='FAIL',execution='m01-controller-only',qualifiedMeasurement=False,paidCloud=False,
                mode=mode,repetition=repetition)
    offered=None
    try:
        deadline=clock()+ACTIVATION_SECONDS*1_000_000_000;leader=None
        while clock()<deadline:
            states={node:worker.call('status') for node,worker in workers.items()}
            need(all(v['state']!='FAILED' for v in states.values()),'measurement M01 voter failed')
            ready=[node for node,value in states.items() if value['state']=='LEADER_READY']
            if len(ready)==1:leader=ready[0];break
            sleep(.05)
        need(leader is not None,'measurement M01 activation timeout')
        target=leader if mode.endswith('strong') else sorted(set(workers)-{leader})[-1]
        scenario.update(stage='initialization',leader=leader,readTarget=target)
        runtime.save(root/'scenario.json',scenario)
        initial=workers[leader].call('read',query=model.query(0),setupToken=True)
        scenario['initialRead']=initial['opId']
        prepared=workers[leader].call('status')
        need(prepared['sequence']==1,'measurement M01 unexpected setup mutation')
        baseline=runtime.await_publication({node:workers[node] for node in sorted({leader,target})},
                    prepared['publishedIndex'],1,clock=lambda:clock()/1e9,sleep=sleep)
        scenario.update(baseline=baseline,baselineIndex=prepared['publishedIndex'],stage='offered')
        runtime.save(root/'scenario.json',scenario)
        parameters=dict(minimum=initial['token']) if mode=='candidate-minimum' else {}
        for worker in workers.values():worker.call('sample-start')
        def submit(call):
            if call['kind']=='update':return workers[leader].submit('update',document=call['document'])
            return workers[target].submit('read',query=call['query'],**parameters)
        def mark(name):
            for worker in workers.values():yield worker.submit('sample-mark',marker=name)
        offered,pending=load.dispatch(model.program(),plan['durationNanos'],submit,clock=clock,sleep=sleep,markers=MARKERS,mark=mark)
        # Keep the complete dispatch record before waiting for original futures.
        runtime.save(root/'offered.json',offered)
        load.drain(offered,pending,DRAIN_SECONDS,clock=clock)
        runtime.save(root/'offered.json',offered)
        for worker in workers.values():worker.call('sample-stop')
        checked=window.validate(offered,history,mode,leader,target,initial['opId'],repetition)
        markers=load.validate_markers(offered,MARKERS,history,workers)
        runtime.save(root/'window-ledger.json',checked)
        scenario['stage']='observed'
        result.update(status='OBSERVED',offered=checked['offered'],completed=checked['completed'],markers=markers)
        return result
    except BaseException as error:
        result['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        if offered is not None:runtime.save(root/'offered.json',offered)
        runtime.save(root/'scenario.json',scenario);runtime.save(root/'controller.json',result)


def execute_prepared(root,binding,cp,*,worker_factory=runtime.Worker):
    """Execute one already prepared member; never promote it to qualified PASS."""
    from .public_reads_evidence import read
    root=Path(root).resolve();need(read(root/'binding.json')==binding,'measurement M01 prepared binding changed')
    mode=binding['mode'];p=binding.get('measurementProfile',{})
    need(p==profile(mode,p.get('repetition')) and 'smokeInitialization' not in binding and 'driverExercise' not in binding,
         'measurement M01 preparation profile')
    need(binding.get('readParameters')==options.parameters() and not (root/options.FILE).exists() and
         'faultParameters' not in binding and not (root/'measurement-fault.json').exists(),'measurement M01 preparation parameters')
    return runtime.execute_observer(root,binding,cp,lambda workers,history:observe(root,workers,history,mode,p['repetition']),
                                    worker_factory=worker_factory,label='measurement M01')
