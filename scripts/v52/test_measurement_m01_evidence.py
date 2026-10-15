import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import measurement_m01_evidence as e,measurement_m01 as m,measurement_model as model
from .test_measurement_window import fixture


class MeasurementM01EvidenceTest(unittest.TestCase):
    def baseline(self):
        history=[dict(opId='setup',kind='read',endNanos=20),dict(opId='status',kind='status',node='node-1',startNanos=21,endNanos=22,
                 response=dict(opId='status',sequence=1,state='LEADER_READY',publishedIndex=5))]
        scenario=dict(leader='node-1',readTarget='node-1',initialRead='setup',baselineIndex=5,baseline={'node-1':history[1]['response']})
        traces={'node-1':[dict(event='PUBLIC_READ_INVOKE',opId='setup',readId=7),dict(event='READ_CAPTURE_VALIDATED',readId=7,index=5,sequence=1)]}
        return history,scenario,dict(startNanos=30),traces,'candidate-legacy-strong'

    def test_initial_target_must_observe_original_strong_cut_without_setup_updates(self):
        result=e.initial_publication(*self.baseline());self.assertEqual(dict(index=5,preparedThrough=5,sequence=1),result)
        for change,reason in (
            (lambda x:x[3]['node-1'][1].__setitem__('sequence',4),'changed initial cut'),
            (lambda x:x[1].__setitem__('baselineIndex',4),'below initial cut'),
            (lambda x:x[1]['baseline']['node-1'].__setitem__('publishedIndex',4),'target publication'),
            (lambda x:x[0][1].__setitem__('endNanos',40),'ledger binding'),
            (lambda x:x[1].__setitem__('readTarget','node-3'),'target set')):
            data=self.baseline();change(data)
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):e.initial_publication(*data)

    def test_metadata_is_bounded_and_symlinks_are_not_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'a.json').write_text('{"a":1}')
            self.assertEqual({'a':1},e.metadata(root,'a.json',7))
            with self.assertRaisesRegex(ValueError,'metadata bound'):e.metadata(root,'a.json',6)
            (root/'b.json').symlink_to(root/'a.json')
            with self.assertRaisesRegex(ValueError,'metadata bound'):e.metadata(root,'b.json',100)

    def test_aggregate_admission_precedes_every_general_physical_collector(self):
        offered,history,mode,leader,target,initial,repetition=fixture()
        scenario=dict(family='M01',stage='observed',mode=mode,repetition=repetition,leader=leader,readTarget=target,initialRead=initial)
        binding=dict(mode=mode,measurementProfile=m.profile(mode,repetition))
        execution=dict(status='STOPPED',qualifiedMeasurement=False,paidCloud=False,failure=None,closeErrors=[])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'node-1').mkdir();(root/'node-1/manifest.gsr').write_bytes(b'x'*48)
            with patch.object(e,'identity',return_value=(binding,[])),patch.object(e,'metadata',return_value=execution),\
                 patch.object(e.physical.f,'inspect',return_value={'groupId':'group'}),\
                 patch.object(e.budget,'validate',side_effect=ValueError('oversized retained state')) as guard,\
                 patch.object(e.physical,'validate') as physical,patch.object(e.reads,'context') as context:
                with self.assertRaisesRegex(ValueError,'oversized retained state'):
                    e.validate(root,binding,traces={'node-1':[]},history=history,offered=offered,scenario=scenario)
                guard.assert_called_once();physical.assert_not_called();context.assert_not_called()

    def test_short_history_and_incomplete_processes_cannot_reach_physical_qualification(self):
        offered,history,mode,leader,target,initial,repetition=fixture()
        scenario=dict(family='M01',stage='observed',mode=mode,repetition=repetition,leader=leader,readTarget=target,initialRead=initial)
        binding=dict(mode=mode,measurementProfile=m.profile(mode,repetition))
        stopped=dict(status='STOPPED',qualifiedMeasurement=False,paidCloud=False,failure=None,closeErrors=[])
        for change,reason in (('short','offered count'),('close','incomplete process')):
            value=copy.deepcopy(offered);execution=copy.deepcopy(stopped)
            if change=='short':value['offers']=value['offers'][:10]
            else:execution['closeErrors']=['injected failure']
            with patch.object(e,'identity',return_value=(binding,[])),patch.object(e,'metadata',return_value=execution),\
                 patch.object(e.physical,'validate') as physical:
                with self.subTest(change=change),self.assertRaisesRegex(ValueError,reason):
                    e.validate('unused',binding,traces={},history=history,offered=value,scenario=scenario)
                physical.assert_not_called()

    def test_invalid_original_is_never_reported_as_successful_negative_qualification(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(e,'negative_cases') as cases:
            with self.assertRaisesRegex(ValueError,'invalid original'):e.negatives('unused',{}, {})
            cases.assert_not_called()

    def test_window_negatives_hit_declared_errors_for_all_modes(self):
        for mode in model.MODES:
            for name,predicate,change,mutate,reason in e.negative_cases(mode,'setup','node-1'):
                if predicate is not None or name=='changed-controller-answer':continue
                offered,history,_,leader,target,initial,repetition=fixture(mode)
                mutate(history,offered,{})
                with self.subTest(mode=mode,negative=name),self.assertRaisesRegex(ValueError,reason):
                    e.window.validate(offered,history,mode,leader,target,initial,repetition)

    def test_artifact_loader_jvm_and_profile_bindings_reject_substitution(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'artifacts').mkdir();(root/'consumer').mkdir()
            names=['general-search-engine-5.2.0-SNAPSHOT.jar','general-search-engine-replication-5.2.0-SNAPSHOT.jar','general-search-engine-4.4.0.jar']
            for name in names:(root/'artifacts'/name).write_bytes(name.encode())
            (root/'consumer/Fixture.class').write_bytes(b'class-fixture')
            binding=dict(mode='candidate-stale',measurementProfile=m.profile('candidate-stale',1),programSha256=model.PLAN_SHA,
                readParameters=e.options.parameters(),
                publicationAuthority='forced-generation-v1',origin='/original',java={'java.runtime.version':'21-test','java.vendor':'vendor'},
                artifacts={n:e.digest(n.encode()) for n in names},classes={'consumer/Fixture.class':e.digest(b'class-fixture')})
            processes=[dict(node=f'node-{i}',pid=i,generation=1,exitCode=0,identity=dict(node=f'node-{i}',pid=i,mode='candidate-stale',
                javaRuntime='21-test',javaVendor='vendor',readParameters=e.options.parameters(),coreSource='/original/artifacts/'+names[0],replicationSource='/original/artifacts/'+names[1])) for i in (1,2,3)]
            def write(b,p):
                (root/'binding.json').write_bytes(e.encoded(b));(root/'processes.json').write_bytes(e.encoded(p))
                (root/e.bundle.INDEX).write_bytes(e.encoded(e.bundle.members(root)))
            write(binding,processes);self.assertEqual((binding,processes),e.identity(root,binding))
            for change,reason in (
                (lambda b,p:b.__setitem__('driverExercise',True),'full preparation profile'),
                (lambda b,p:b['artifacts'].__setitem__(names[0],'0'*64),'artifact binding'),
                (lambda b,p:b['classes'].__setitem__('consumer/Fixture.class','0'*64),'consumer binding'),
                (lambda b,p:p[0]['identity'].__setitem__('javaRuntime','different'),'JVM differs'),
                (lambda b,p:b['readParameters'].__setitem__('pendingLimit',65),'read parameters changed'),
                (lambda b,p:p[0]['identity']['readParameters'].__setitem__('waitTimeoutMillis',0),'observed read parameters differ'),
                (lambda b,p:p[0]['identity'].__setitem__('coreSource','/other/runtime.jar'),'loaded artifact source'),
                (lambda b,p:p[0].__setitem__('exitCode',1),'stopped JVMs')):
                b=copy.deepcopy(binding);p=copy.deepcopy(processes);change(b,p);write(b,p)
                with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):e.identity(root,b)


if __name__=='__main__':unittest.main()
