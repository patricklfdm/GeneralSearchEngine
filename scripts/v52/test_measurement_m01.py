import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import measurement_m01 as m,measurement_model as model,measurement_runtime as runtime


class World:
    def __init__(self,mode,*,leader='node-2',failed_ordinal=None,transport_at=None,marker_failure=False):
        self.now=10_000_000_000;self.mode=mode;self.leader=leader;self.history=[];self.pending=[];self.business=[]
        self.failed_ordinal=failed_ordinal;self.transport_at=transport_at;self.marker_failure=marker_failure;self.high_water=0
        self.workers={f'node-{i}':Consumer(self,f'node-{i}') for i in (1,2,3)}
    def clock(self):self.now+=1;return self.now
    def sleep(self,seconds):self.now+=round(seconds*1e9)
    def complete(self):
        for future,call in self.pending:
            call['endNanos']=self.clock();call['response']['apiEndNanos']=self.now+7_000_000_000
            future.set_result(call['response'])
        self.pending=[]
    def run(self,root,repetition=1):return m.observe(root,self.workers,self.history,self.mode,repetition,clock=self.clock,sleep=self.sleep)


class Consumer:
    def __init__(self,world,node):self.world=world;self.node=node;self.serial=0
    def call(self,kind,**values):return self.submit(kind,**values)[1].result()
    def submit(self,kind,**values):
        w=self.world;business=kind=='update' or kind=='read' and not values.get('setupToken')
        if business and w.transport_at==len(w.business):
            w.complete();raise OSError('injected transport disconnect')
        if kind=='sample-mark' and w.marker_failure and self.node=='node-2':raise OSError('injected marker disconnect')
        self.serial+=1;identity=self.node+'-'+str(self.serial);start=w.clock();outcome='SUCCESS';extra={}
        if kind=='status':extra=dict(state='LEADER_READY' if self.node==w.leader else 'FOLLOWER',publishedIndex=1,sequence=1)
        elif kind=='read':extra=dict(token='initial-progress-token',answer={})
        if business and w.failed_ordinal==len(w.business):
            outcome='NOT_APPLICABLE' if kind=='read' else 'INDETERMINATE';extra=dict(reasonCode='QUORUM_UNAVAILABLE',reason='injected rejection')
        response=dict(opId=identity,kind=kind,outcome=outcome,receivedNanos=start+7_000_000_000,
                      apiStartNanos=start+7_000_000_001,apiEndNanos=start+7_000_000_002,**extra)
        call=dict(opId=identity,node=self.node,kind=kind,startNanos=start,endNanos=None,outcome=outcome,response=response,**values)
        w.history.append(call);future=concurrent.futures.Future()
        if business:
            w.business.append(call);w.pending.append((future,call));w.high_water=max(w.high_water,len(w.pending))
        else:
            if kind=='sample-mark' and values['marker']=='measured-end':w.complete()
            call['endNanos']=w.clock();future.set_result(response)
        return identity,future


class MeasurementM01Test(unittest.TestCase):
    def test_all_fifteen_members_keep_full_clock_calls_targets_and_unresolved_futures(self):
        for mode in model.MODES:
            for repetition in (1,2,3):
                with self.subTest(mode=mode,repetition=repetition),tempfile.TemporaryDirectory() as directory:
                    w=World(mode);root=Path(directory);result=w.run(root,repetition)
                    self.assertEqual('OBSERVED',result['status']);self.assertFalse(result['qualifiedMeasurement'])
                    self.assertEqual(1980,w.high_water);self.assertFalse(w.pending)
                    offered=json.loads((root/'offered.json').read_text());self.assertEqual(180_000_000_000,offered['durationNanos'])
                    self.assertEqual([0,60_000_000_000,180_000_000_000],[r['spec']['offsetNanos'] for r in offered['markers']])
                    scenario=json.loads((root/'scenario.json').read_text());target='node-2' if mode.endswith('strong') else 'node-3'
                    self.assertEqual(target,scenario['readTarget']);self.assertEqual('node-2',scenario['leader'])
                    self.assertEqual(1,sum(c.get('setupToken') is True for c in w.history))
                    self.assertEqual(180,sum(c['kind']=='update' for c in w.history))
                    self.assertEqual(1801,sum(c['kind']=='read' for c in w.history))
                    for call in w.business:
                        self.assertEqual('node-2' if call['kind']=='update' else target,call['node'])
                        self.assertEqual(mode=='candidate-minimum' and call['kind']=='read','minimum' in call)
                    report=json.loads((root/'window-ledger.json').read_text())
                    self.assertEqual(600,report['windows']['warmup']['operations']['read']['completedAfterWindow'])

    def test_failed_business_result_is_retained_once_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            w=World('candidate-minimum',failed_ordinal=40);w.run(directory)
            rows=[r for r in w.business if r['outcome']!='SUCCESS'];self.assertEqual(1,len(rows))
            report=json.loads((Path(directory)/'window-ledger.json').read_text())
            self.assertEqual(1,report['windows']['warmup']['operations']['read']['outcomes']['NOT_APPLICABLE'])
            self.assertEqual(1980,len(w.business))

    def test_partial_dispatch_keeps_observed_calls_and_undispatched_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            w=World('candidate-stale',transport_at=40)
            with self.assertRaisesRegex(ValueError,'incomplete dispatch'):w.run(directory)
            offered=json.loads((Path(directory)/'offered.json').read_text())
            self.assertEqual(40,len(w.business));self.assertEqual('DISPATCH_FAILED',offered['offers'][40]['status'])
            self.assertTrue(all(r['status']=='NOT_DISPATCHED' for r in offered['offers'][41:]))
            self.assertTrue(all(r['completionStatus']=='OBSERVED' for r in offered['offers'][:40]))
            self.assertFalse(w.pending)
            result=json.loads((Path(directory)/'controller.json').read_text());self.assertEqual('FAIL',result['status'])

    def test_partial_marker_does_not_discard_first_target_or_offer_business(self):
        with tempfile.TemporaryDirectory() as directory:
            w=World('candidate-stale',marker_failure=True)
            with self.assertRaisesRegex(ValueError,'incomplete dispatch'):w.run(directory)
            offered=json.loads((Path(directory)/'offered.json').read_text())
            self.assertEqual([],w.business);self.assertEqual(1,len(offered['markers'][0]['operations']))
            self.assertEqual('OBSERVED',offered['markers'][0]['operations'][0]['completionStatus'])

    def test_initial_mutation_or_unavailable_group_prevents_window(self):
        for problem in ('mutation','unavailable'):
            with self.subTest(problem=problem),tempfile.TemporaryDirectory() as directory:
                w=World('candidate-stale');original=Consumer.submit
                def changed(worker,kind,**values):
                    identity,future=original(worker,kind,**values)
                    if kind=='status':future.result()['sequence' if problem=='mutation' else 'state']=2 if problem=='mutation' else 'FOLLOWER'
                    return identity,future
                with patch.object(Consumer,'submit',changed),self.assertRaisesRegex(ValueError,'setup mutation|activation timeout'):w.run(directory)
                self.assertEqual([],w.business);self.assertFalse((Path(directory)/'offered.json').exists())

    def test_profiles_are_closed_and_smoke_cannot_execute_as_m01(self):
        for mode,repetition in (('other',1),('candidate-stale',True),('candidate-stale',0),('candidate-stale',4)):
            with self.assertRaisesRegex(ValueError,'mode/repetition'):m.profile(mode,repetition)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);binding=dict(mode='candidate-stale',measurementProfile=m.profile('candidate-stale',1),driverExercise=True)
            runtime.save(root/'binding.json',binding)
            with self.assertRaisesRegex(ValueError,'preparation profile'):m.execute_prepared(root,binding,'unused')

    def test_every_worker_stops_and_original_failure_survives_close_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);artifacts=root/'artifacts';artifacts.mkdir();jar=artifacts/'runtime.jar';jar.write_bytes(b'fixture')
            binding=dict(mode='candidate-stale',measurementProfile=m.profile('candidate-stale',1),artifacts={'runtime.jar':runtime.digest(jar.read_bytes())})
            runtime.save(root/'binding.json',binding);stopped=[]
            class Worker:
                def __init__(self,root,node,cp,mode,history):
                    self.node=node;self.generation=1;self.identity=dict(coreSource=str(jar),replicationSource=str(jar))
                    self.proc=type('Process',(),dict(pid=int(node[-1]),returncode=None))()
                def stop(self):
                    stopped.append(self.node);self.proc.returncode=0
                    if self.node=='node-2':raise ValueError('secondary close failure')
            with patch.object(m,'observe',side_effect=OSError('original execution failure')):
                with self.assertRaisesRegex(OSError,'original execution failure'):m.execute_prepared(root,binding,'unused',worker_factory=Worker)
            self.assertEqual(['node-1','node-2','node-3'],stopped)
            result=json.loads((root/'execution.json').read_text());self.assertEqual('OSError',result['failure']['type'])
            self.assertEqual(1,len(result['closeErrors']));self.assertEqual(3,len(json.loads((root/'processes.json').read_text())))


if __name__=='__main__':unittest.main()
