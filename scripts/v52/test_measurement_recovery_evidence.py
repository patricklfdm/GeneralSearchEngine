import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import measurement_recovery_evidence as e,measurement_recovery_ledger as ledger,measurement_recovery as controller
from .test_measurement_recovery import World
from .test_measurement_samples import rows as sample_rows


class MeasurementRecoveryEvidenceTest(unittest.TestCase):
    def test_authority_budget_runs_before_general_collectors(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);world=World(controller.CASES[1]);world.run(root);scenario=e.reads.read(root/'scenario.json')
            binding=dict(measurementProfile=controller.profile(controller.CASES[1]));(root/'node-1').mkdir();(root/'node-1/manifest.gsr').write_bytes(b'x'*48)
            stopped=dict(status='STOPPED',qualifiedMeasurement=False,paidCloud=False,failure=None,closeErrors=[])
            with patch.object(e,'identity',return_value=(binding,[],None)),patch.object(e,'metadata',return_value=stopped),\
                 patch.object(e.physical.f,'inspect',return_value={}),patch.object(e.budget,'validate',side_effect=ValueError('over budget')),\
                 patch.object(e.physical,'validate') as physical,patch.object(e.reads,'context') as context:
                with self.assertRaisesRegex(ValueError,'over budget'):e.validate(root,binding,history=world.history,scenario=scenario,traces={})
                physical.assert_not_called();context.assert_not_called()

    def test_portable_result_and_negative_set_must_match_exactly(self):
        for issue,reason in [('different','relocated result'),('missing','incomplete negative')]:
            with self.subTest(issue=issue),tempfile.TemporaryDirectory() as directory:
                parent=Path(directory);root=parent/'source';root.mkdir();world=World(controller.CASES[1]);world.run(root)
                scenario=e.reads.read(root/'scenario.json');plan=controller.profile(controller.CASES[1]);(root/'node-1').mkdir();(root/'node-1/manifest.gsr').write_bytes(b'fixture')
                result=dict(status='PASS',negatives=[dict(case=v[0],status='REJECTED',reason=v[4]) for v in e.negative_cases(plan,scenario)])
                if issue=='missing':result['negatives'].pop()
                relocated=copy.deepcopy(result)
                if issue=='different':relocated['negatives'][0]['reason']='unrelated error'
                with patch.object(e,'replay',side_effect=[result,relocated]),self.assertRaisesRegex(ValueError,reason):
                    e.portable_member(root,dict(measurementProfile=plan),parent/'output')
                self.assertEqual('FAIL',e.reads.read(parent/'output/receipt.json')['status'])
                self.assertTrue((parent/'output/history.tar.gz').is_file())

    def test_changed_inventory_cannot_be_rebaselined_before_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory);root=parent/'source';root.mkdir();(root/'one').write_bytes(b'original')
            (root/e.bundle.INDEX).write_bytes(e.encoded(e.bundle.members(root))+b'\n');(root/'one').write_bytes(b'changed')
            with patch.object(e,'replay') as replay,self.assertRaisesRegex(ValueError,'inventory/hash differs'):
                e.portable_member(root,{},parent/'output')
            replay.assert_not_called()

    def test_closed_schedules_bind_every_original_business_call_and_token(self):
        for case in controller.CASES:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as directory:
                world=World(case);world.run(directory);scenario=e.reads.read(Path(directory)/'scenario.json')
                if 'crash' in scenario:scenario['crash'].update(generation=1)
                result=ledger.schedule(world.history,scenario,controller.profile(case))
                self.assertEqual(4,len(result['reads']));self.assertEqual(5,result['initialIndex'])

    def test_injected_business_token_target_and_milestone_changes_are_rejected(self):
        for case in controller.CASES:
            with tempfile.TemporaryDirectory() as directory:
                world=World(case);world.run(directory);scenario=e.reads.read(Path(directory)/'scenario.json')
                if 'crash' in scenario:scenario['crash'].update(generation=1)
                plan=controller.profile(case);ledger.schedule(world.history,scenario,plan)
                for name,predicate,_,mutate,reason in e.negative_cases(plan,scenario):
                    if predicate is not None or name in ('changed-crash-pid','changed-retained-inventory'):continue
                    h=copy.deepcopy(world.history);s=copy.deepcopy(scenario);mutate(h,s)
                    with self.subTest(case=case,negative=name),self.assertRaisesRegex(ValueError,reason):ledger.schedule(h,s,plan)

    def test_invalid_original_does_not_count_as_successful_negatives(self):
        with patch.object(e,'validate',side_effect=ValueError('original invalid')),patch.object(e,'negative_cases') as negatives:
            with self.assertRaisesRegex(ValueError,'original invalid'):e.negatives('unused',{}, {})
            negatives.assert_not_called()

    def test_sigkill_samples_preserve_prefix_without_fabricating_stop(self):
        rows=sample_rows()
        prefix=rows[:-1]
        result=e.samples.validate(prefix,'candidate-minimum',abrupt=True)
        self.assertFalse(result['completeSession']);self.assertEqual('SIGKILL',result['termination'])
        self.assertIn('observed-prefix-only',result['semantics'])
        with self.assertRaisesRegex(ValueError,'start/stop coverage'):e.samples.validate(prefix,'candidate-minimum')
        with self.assertRaisesRegex(ValueError,'start/stop coverage'):e.samples.validate(rows,'candidate-minimum',abrupt=True)
        changed=copy.deepcopy(prefix);changed[0]['sampleOrdinal']=1
        with self.assertRaisesRegex(ValueError,'missing/duplicate ordinal'):e.samples.validate(changed,'candidate-minimum',abrupt=True)


if __name__=='__main__':unittest.main()
