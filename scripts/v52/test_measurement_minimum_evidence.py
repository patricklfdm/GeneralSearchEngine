import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import measurement_minimum_evidence as e,measurement_minimum_ledger as gates
from . import measurement_model as model,measurement_minimum as controller
from .test_measurement_minimum import World


def schedule_fixture(case,directory):
    w=World(case);w.run(directory);root=Path(directory)
    return w.history,e.reads.read(root/'scenario.json'),e.reads.read(root/'observed.json'),w.plan


class MeasurementMinimumEvidenceTest(unittest.TestCase):
    def test_every_declared_controller_schedule_has_complete_independent_ledger(self):
        for case in controller.CASES:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as directory:
                history,scenario,observed,plan=schedule_fixture(case,directory)
                result=gates.schedule(history,scenario,observed,plan)
                self.assertEqual(plan['readCount'],len(result['read_calls']))
                self.assertEqual(7,result['baseline_index'])
                self.assertEqual(plan['releaseUpdate'],result['release'] is not None)

    def test_all_metadata_negatives_reject_for_the_declared_reason(self):
        for case in ('m02-above-0','m02-above-1000','m03-p4','m03-p65'):
            with tempfile.TemporaryDirectory() as directory:
                history,scenario,observed,plan=schedule_fixture(case,directory)
                for name,predicate,_,mutate,reason in e.negative_cases(plan,scenario):
                    if predicate is not None:continue
                    h=copy.deepcopy(history);s=copy.deepcopy(scenario);o=copy.deepcopy(observed);mutate(h,s,o)
                    with self.subTest(case=case,negative=name),self.assertRaisesRegex(ValueError,reason):gates.schedule(h,s,o,plan)

    def test_capacity_rejection_waiter_success_and_reserved_slot_are_not_substituted(self):
        with tempfile.TemporaryDirectory() as directory:
            original=schedule_fixture('m03-p4',directory)
            for kind,reason in (('excess','excess capacity rejection'),('read','saturation waiter failed'),('release-update','failed progress write')):
                h,s,o,p=copy.deepcopy(original);row=next(r for r in o['operations'] if r['kind']==kind);call=next(c for c in h if c['opId']==row['opId'])
                outcome='SUCCESS' if kind=='excess' else 'NOT_APPLICABLE';call['outcome']=outcome;call['response']['outcome']=outcome;row['response']['outcome']=outcome
                with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,reason):gates.schedule(h,s,o,p)

    def test_changed_query_target_token_relation_and_missing_query_coverage_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            original=schedule_fixture('m02-below-1000',directory)
            for fault,reason in (('query','changed offered read'),('target','changed frozen target'),('relation','changed bound relation'),('coverage','query coverage')):
                h,s,o,p=copy.deepcopy(original)
                if fault=='query':next(c for c in h if c['opId']==s['readOps'][0])['query']=model.query(1)
                if fault=='target':s['readTarget']=s['leader']
                if fault=='relation':s['minimum']=controller.lower_bound(next(c for c in h if c['opId']==s['initialRead'])['response']['token'],7,'above')
                if fault=='coverage':
                    for row in o['operations']:
                        c=next(c for c in h if c['opId']==row['opId'])
                        if c['query']['kind']=='get':c['outcome']='NOT_APPLICABLE';c['response']['outcome']='NOT_APPLICABLE';row['response']['outcome']='NOT_APPLICABLE'
                with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,reason):gates.schedule(h,s,o,p)

    def test_routing_hint_must_match_retained_selected_bases_and_epoch(self):
        chosen=dict(bases=[dict(node='node-1'),dict(node='node-2')],ballot=dict(epoch=3))
        queues=dict(selectedVotersObserved=3,selectedEpochObserved=3)
        with patch.object(gates.physical,'frame',return_value=chosen) as decode:
            gates.selected_quorum(dict(selected='actual-selected-record'),queues,{'manifest':'binding'})
            decode.assert_called_once_with('actual-selected-record','SELECTED',{'manifest':'binding'})
            for field,value in (('selectedVotersObserved',6),('selectedVotersObserved',True),('selectedEpochObserved',6)):
                with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'fabricated selected quorum'):
                    gates.selected_quorum(dict(selected='actual-selected-record'),dict(queues,**{field:value}),{})
            with self.assertRaisesRegex(ValueError,'missing selected quorum'):gates.selected_quorum(None,queues,{})

    def test_invalid_original_cannot_qualify_negative_cases(self):
        with patch.object(e,'validate',side_effect=ValueError('original invalid')),patch.object(e,'negative_cases') as cases:
            with self.assertRaisesRegex(ValueError,'original invalid'):e.negatives('unused',{}, {})
            cases.assert_not_called()

    def test_resource_budget_precedes_general_authority_collectors(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);history,scenario,observed,plan=schedule_fixture('m03-p4',root)
            (root/'node-1').mkdir();(root/'node-1/manifest.gsr').write_bytes(b'x'*48)
            binding=dict(measurementProfile=plan);execution=dict(status='STOPPED',qualifiedMeasurement=False,paidCloud=False,failure=None,closeErrors=[])
            with patch.object(e,'identity',return_value=(binding,[])),patch.object(e,'metadata',return_value=execution),\
                 patch.object(e.physical.f,'inspect',return_value={}),patch.object(e.budget,'validate',side_effect=ValueError('over budget')),\
                 patch.object(e.physical,'validate') as physical,patch.object(e.reads,'context') as context:
                with self.assertRaisesRegex(ValueError,'over budget'):e.validate(root,binding,history=history,scenario=scenario,observed=observed,traces={})
                physical.assert_not_called();context.assert_not_called()

    def test_missing_offer_and_incomplete_close_fail_before_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            history,scenario,observed,plan=schedule_fixture('m02-equal-0',directory);binding=dict(measurementProfile=plan)
            complete=dict(status='STOPPED',qualifiedMeasurement=False,paidCloud=False,failure=None,closeErrors=[])
            for issue in ('offer','close'):
                o=copy.deepcopy(observed);execution=copy.deepcopy(complete)
                if issue=='offer':o['operations'].pop()
                else:execution['closeErrors']=['bad close']
                with patch.object(e,'identity',return_value=(binding,[])),patch.object(e,'metadata',return_value=execution),patch.object(e.budget,'validate') as budget:
                    with self.subTest(issue=issue),self.assertRaisesRegex(ValueError,'incomplete offered ledger|incomplete process'):
                        e.validate(directory,binding,history=history,scenario=scenario,observed=o,traces={})
                    budget.assert_not_called()

    def test_configuration_file_profile_and_observed_jvm_must_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'artifacts').mkdir();(root/'consumer').mkdir()
            names=['general-search-engine-5.2.0-SNAPSHOT.jar','general-search-engine-replication-5.2.0-SNAPSHOT.jar','general-search-engine-4.4.0.jar']
            for name in names:(root/'artifacts'/name).write_bytes(name.encode())
            (root/'consumer/Fixture.class').write_bytes(b'class-fixture');plan=controller.profile('m02-above-0')
            binding=dict(mode='candidate-minimum',measurementProfile=plan,programSha256=model.PLAN_SHA,readParameters=plan['parameters'],
                publicationAuthority='forced-generation-v1',origin='/original',java={'java.runtime.version':'21-test','java.vendor':'vendor'},
                artifacts={n:e.digest(n.encode()) for n in names},classes={'consumer/Fixture.class':e.digest(b'class-fixture')})
            processes=[dict(node=f'node-{i}',pid=i,generation=1,exitCode=0,identity=dict(node=f'node-{i}',pid=i,mode='candidate-minimum',
                javaRuntime='21-test',javaVendor='vendor',readParameters=copy.deepcopy(plan['parameters']),
                coreSource='/original/artifacts/'+names[0],replicationSource='/original/artifacts/'+names[1])) for i in (1,2,3)]
            def write(b,p,config):
                (root/'binding.json').write_bytes(e.encoded(b));(root/'processes.json').write_bytes(e.encoded(p))
                if config is None:(root/e.options.FILE).unlink(missing_ok=True)
                else:(root/e.options.FILE).write_bytes(e.encoded(config))
                (root/e.bundle.INDEX).write_bytes(e.encoded(e.bundle.members(root)))
            write(binding,processes,plan['parameters']);self.assertEqual((binding,processes),e.identity(root,binding))
            for change,reason in (
                (lambda b,p,c:b.__setitem__('readConfigurationOnly',True),'preparation profile'),
                (lambda b,p,c:b.__setitem__('mode','candidate-stale'),'preparation profile'),
                (lambda b,p,c:c.__setitem__('waitTimeoutMillis',1000),'parameter binding'),
                (lambda b,p,c:p[0]['identity']['readParameters'].__setitem__('waitTimeoutMillis',1000),'observed read parameters differ')):
                b=copy.deepcopy(binding);p=copy.deepcopy(processes);c=copy.deepcopy(plan['parameters']);change(b,p,c);write(b,p,c)
                with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):e.identity(root,b)
            write(binding,processes,None)
            with self.assertRaisesRegex(ValueError,'parameter binding'):e.identity(root,binding)

    def test_portable_replay_requires_identical_results_and_exact_negative_set(self):
        for issue,reason in [('different','relocated result'),('missing','incomplete negative')]:
            with self.subTest(issue=issue),tempfile.TemporaryDirectory() as directory:
                parent=Path(directory);root=parent/'source';root.mkdir();_,scenario,_,plan=schedule_fixture('m03-p4',root)
                (root/'node-1').mkdir();(root/'node-1/manifest.gsr').write_bytes(b'fixture')
                cases=e.negative_cases(plan,scenario);result=dict(status='PASS',negatives=[dict(case=v[0],status='REJECTED',reason=v[4]) for v in cases])
                if issue=='missing':result['negatives'].pop()
                relocated=copy.deepcopy(result)
                if issue=='different':relocated['negatives'][0]['reason']='unrelated error'
                with patch.object(e,'replay',side_effect=[result,relocated]),self.assertRaisesRegex(ValueError,reason):
                    e.portable_member(root,dict(measurementProfile=plan),parent/'output')
                self.assertEqual('FAIL',e.reads.read(parent/'output/receipt.json')['status'])
                self.assertTrue((parent/'output/history.tar.gz').is_file());self.assertTrue((parent/'output/relocated/node-1/manifest.gsr').is_file())

    def test_existing_inventory_cannot_be_rebaselined_to_hide_changed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory);root=parent/'source';root.mkdir();(root/'one').write_bytes(b'original')
            (root/e.bundle.INDEX).write_bytes(e.encoded(e.bundle.members(root))+b'\n');(root/'one').write_bytes(b'changed')
            with patch.object(e,'replay') as replay,self.assertRaisesRegex(ValueError,'inventory/hash differs'):
                e.portable_member(root,{},parent/'output')
            replay.assert_not_called();self.assertFalse((parent/'output/history.tar.gz').exists())


if __name__=='__main__':unittest.main()
