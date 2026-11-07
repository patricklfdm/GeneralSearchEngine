"""Separate backup orchestration contract; synthetic fixtures are not evidence."""
import copy
from contextlib import ExitStack
import unittest
from unittest.mock import patch
from . import required_four_resources as m
from . import bootstrap_replay_contract as policy
from . import test_required_four_resources as fixtures


class BackupRequiredFourResourcesTest(unittest.TestCase):
    def setup_gate(self,stack,progress=None):
        helper=fixtures.RequiredFourResourcesTest()
        order,inventory,validate,original=helper.setup_gate(stack,progress=progress)
        old=validate.side_effect
        def validation(*args,**kwargs):
            self.assertEqual(policy.BACKUP,kwargs.pop('bootstrap_source'))
            return policy.receipt(old(*args,**kwargs),policy.BACKUP)
        validate.side_effect=validation
        def source_probe(*args,**kwargs):
            self.assertEqual(['original',*m.NEGATIVES],order)
            order.append('bootstrap-source');raise ValueError(m.SOURCE_NEGATIVE['reason'])
        probe=stack.enter_context(patch.object(m.bootstrap_catalog,'Replay',side_effect=source_probe))
        return order,inventory,validate,original,probe

    def test_backup_keeps_147_negatives_and_adds_exact_default_source_rejection(self):
        updates=[];progress=updates.append
        with ExitStack() as stack:
            order,inventory,validate,_,probe=self.setup_gate(stack,progress)
            result=m.qualify_backup('/synthetic',progress)
            self.assertEqual(policy.BACKUP,m.handoff.r.original.call_args.kwargs['bootstrap_source'])
            self.assertEqual(policy.BACKUP,m.files.maintenance.Replay.call_args.kwargs['bootstrap_source'])
        self.assertEqual(['original',*m.NEGATIVES,'bootstrap-source'],order)
        self.assertEqual(1,validate.call_count);self.assertEqual(2,inventory.call_count)
        self.assertEqual(148,sum(map(len,result['negatives'].values())))
        probe.assert_called_once_with(m.Path('/synthetic'),size=5,kind='REPLACE',required_four=True)
        self.assertEqual(m.BACKUP_SCHEMA,result['schema']);self.assertEqual(m.BACKUP_PROFILE,result['profile'])
        self.assertFalse(result['combinedResourcesQualified']);self.assertFalse(result['phase3Complete'])
        m.check_backup_result(result)
        with self.assertRaisesRegex(ValueError,'qualification scope'):m.check_result(result)

    def test_legacy_receipt_cannot_supply_backup_original_or_source_qualification(self):
        value=fixtures.replay()
        with self.assertRaisesRegex(ValueError,'qualification scope'):m.check_backup_result(value)
        value.update(schema=m.BACKUP_SCHEMA,profile=m.BACKUP_PROFILE,bootstrapSource=policy.BACKUP)
        value['negatives']['bootstrap-source']=[dict(m.SOURCE_NEGATIVE)]
        with self.assertRaisesRegex(ValueError,'source receipt'):m.check_backup_result(value)
        value['original']['bootstrapSource']=policy.BACKUP
        m.check_backup_result(value)
        for mutation in ('missing','reason','status','extra'):
            bad=copy.deepcopy(value)
            if mutation=='missing':bad['negatives'].pop('bootstrap-source')
            elif mutation=='extra':bad['negatives']['bootstrap-source'].append(dict(m.SOURCE_NEGATIVE))
            else:bad['negatives']['bootstrap-source'][0][mutation]='unrelated'
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'exact negative families'):
                m.check_backup_result(bad)

    def test_invalid_original_stops_before_source_probe_or_any_negatives(self):
        with patch.object(m.native.collection,'inventory',return_value={}),\
             patch.object(m.native,'validate',side_effect=ValueError('bad physical original')),\
             patch.object(m.native,'load') as load,patch.object(m.accounting,'replay') as negatives,\
             patch.object(m.bootstrap_catalog,'Replay') as probe:
            with self.assertRaisesRegex(ValueError,'bad physical original'):m.qualify_backup('/synthetic')
            load.assert_not_called();negatives.assert_not_called();probe.assert_not_called()

    def test_source_marker_is_required_before_loading_or_counting_negatives(self):
        with ExitStack() as stack:
            order,_,validate,_,probe=self.setup_gate(stack);good=validate.side_effect
            def missing(*args,**kwargs):
                value=good(*args,**kwargs);value.pop('bootstrapSource');return value
            validate.side_effect=missing
            with self.assertRaisesRegex(ValueError,'source receipt'):m.qualify_backup('/synthetic')
            self.assertEqual(['original'],order);probe.assert_not_called()

    def test_unrelated_default_failure_cannot_count_as_source_rejection(self):
        with ExitStack() as stack:
            *_,probe=self.setup_gate(stack);probe.side_effect=ValueError('unrelated damaged original')
            with self.assertRaisesRegex(ValueError,'exact source rejection'):m.qualify_backup('/synthetic')

    def test_default_acceptance_cannot_count_as_source_rejection(self):
        with ExitStack() as stack:
            *_,probe=self.setup_gate(stack);probe.side_effect=None
            with self.assertRaisesRegex(ValueError,'accepted by EMPTY contract'):m.qualify_backup('/synthetic')

    def test_backup_original_must_remain_unchanged_after_all_negatives(self):
        with ExitStack() as stack:
            _,inventory,*_=self.setup_gate(stack);inventory.side_effect=[{'before':1},{'after':2}]
            with self.assertRaisesRegex(ValueError,'original changed'):m.qualify_backup('/synthetic')


if __name__=='__main__':unittest.main()
