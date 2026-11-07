"""Explicit staging policy binding; synthetic lifetimes earn no native credit."""
import copy
from contextlib import ExitStack
import unittest
from unittest.mock import patch
from . import native_resource_policy as p
from . import native_resource_evidence as native
from . import native_resource_negatives as accounting
from . import joined_handoff_resources as handoff, joined_handoff_negatives as negatives
from . import required_four_resources as gate
from . import test_native_resource_evidence as native_fixture
from .test_joined_handoff_resources import fixture
from .test_backup_resource_run import replay
from . import test_required_four_resources as gate_fixture


class NativeResourcePolicyTest(unittest.TestCase):
    def test_only_two_explicit_profiles_and_original_receipt_shapes(self):
        self.assertEqual(512*1024**2,p.check(p.SMALL));self.assertEqual(16*1024**3,p.check(p.DEFAULT))
        value={'status':'PASS'};self.assertIs(value,p.receipt(value,p.SMALL));self.assertEqual({},p.options(p.SMALL))
        marked=p.receipt(value,p.DEFAULT);p.check_receipt(marked,p.DEFAULT)
        with self.assertRaises(ValueError):p.check_receipt(marked,p.SMALL)
        with self.assertRaises(ValueError):p.check_receipt(value,p.DEFAULT)
        for field in ('resourceProfile','stagingLimit'):
            bad=copy.deepcopy(marked);bad.pop(field)
            with self.assertRaises(ValueError):p.check_receipt(bad,p.DEFAULT)
        for value in ('maximum',None,True,16*1024**3):
            with self.assertRaises(ValueError):p.check(value)

    def test_default_is_rejected_before_reading_empty_json_or_arbitrary_sources(self):
        with patch.object(native.source_policy,'inventory') as opened:
            for source,layout in ((p.source.EMPTY,p.source.JSON),(p.source.BACKUP,p.source.JSON),(p.source.EMPTY,p.source.SEGMENTED)):
                with self.assertRaises(ValueError):native.validate('/unused',bootstrap_source=source,wire_layout=layout,resource_profile=p.DEFAULT)
            opened.assert_not_called()

    def test_every_native_owner_must_match_the_callers_original_limit(self):
        data=native_fixture.NativeResourceEvidenceTest().original(6)
        for trace in data[1].values():trace['stagingLimit']=p.check(p.DEFAULT)
        result=native.replay(*data,resource_profile=p.DEFAULT);p.check_receipt(result,p.DEFAULT)
        self.assertFalse(result['wholeRuntimeResourcesQualified'])
        with self.assertRaisesRegex(ValueError,'original limits'):native.replay(*data)
        before=copy.deepcopy(data)
        cases=accounting.replay(data[:4],*data[4:],resource_profile=p.DEFAULT)
        self.assertEqual(15,len(cases));self.assertEqual(before,data)
        for node in data[1]:
            data[1][node]['stagingLimit']=p.check(p.SMALL)
            with self.subTest(node=node),self.assertRaisesRegex(ValueError,'original limits'):native.replay(*data,resource_profile=p.DEFAULT)
            data[1][node]['stagingLimit']=p.check(p.DEFAULT)

    def test_joining_custody_keeps_one_declared_pool_through_all_negatives(self):
        data=fixture();data[2]['node-6']['stagingLimit']=p.check(p.DEFAULT);before=copy.deepcopy(data)
        value=handoff.replay(*data,resource_profile=p.DEFAULT);p.check_receipt(value,p.DEFAULT)
        self.assertTrue(value['continuousHandoffQualified']);self.assertFalse(value['physicalPeakQualified'])
        self.assertEqual(len(negatives.NEGATIVES),len(negatives.replay(data,resource_profile=p.DEFAULT)))
        self.assertEqual(before,data)
        with self.assertRaisesRegex(ValueError,'original limits'):handoff.replay(*data)

    def test_150_result_requires_policy_at_every_owning_level_and_all_existing_negatives(self):
        value=replay();value.update(schema=gate.DEFAULT_STAGING_SCHEMA,profile=gate.DEFAULT_STAGING_PROFILE)
        value=p.receipt(value,p.DEFAULT);value['original']=p.receipt(value['original'],p.DEFAULT)
        value['original']['joinedHandoffResources']=p.receipt(value['original']['joinedHandoffResources'],p.DEFAULT)
        value['negatives']['staging-profile']=[dict(gate.STAGING_NEGATIVE)]
        gate.check_default_staging_backup_result(value)
        self.assertEqual(150,sum(map(len,value['negatives'].values())))
        with self.assertRaises(ValueError):gate.check_backup_result(value,wire_layout=p.source.SEGMENTED)
        for selector in (lambda v:v,lambda v:v['original'],lambda v:v['original']['joinedHandoffResources']):
            bad=copy.deepcopy(value);selector(bad).pop('stagingLimit')
            with self.assertRaises(ValueError):gate.check_default_staging_backup_result(bad)
        for family in value['negatives']:
            bad=copy.deepcopy(value);bad['negatives'][family].pop()
            with self.assertRaisesRegex(ValueError,'exact negative families'):gate.check_default_staging_backup_result(bad)

    def setup_gate(self,stack):
        order,inventory,validate,original=gate_fixture.RequiredFourResourcesTest().setup_gate(stack)
        old=validate.side_effect
        def validation(*args,**kwargs):
            self.assertEqual(p.DEFAULT,kwargs.pop('resource_profile'))
            self.assertEqual(p.source.BACKUP,kwargs.pop('bootstrap_source'));self.assertEqual(p.source.SEGMENTED,kwargs.pop('wire_layout'))
            result=old(*args,**kwargs)
            result['joinedHandoffResources']=p.receipt(result['joinedHandoffResources'],p.DEFAULT)
            return p.receipt(p.source.receipt(result,p.source.BACKUP,p.source.SEGMENTED),p.DEFAULT)
        validate.side_effect=validation
        stack.enter_context(patch.object(gate.source_policy,'inventory',return_value={'same':'original'}))
        stack.enter_context(patch.object(gate.bootstrap_catalog,'Replay',side_effect=ValueError(gate.SOURCE_NEGATIVE['reason'])))
        def wire(*args,**kwargs):
            if kwargs.get('layout')==p.source.SEGMENTED:return []
            raise ValueError(gate.LAYOUT_NEGATIVE['reason'])
        stack.enter_context(patch.object(gate.wire_archive,'read',side_effect=wire))
        probe=stack.enter_context(patch.object(gate.native,'replay',side_effect=ValueError(gate.STAGING_NEGATIVE['reason'])))
        return order,validate,probe

    def test_whole_gate_passes_policy_to_original_and_both_negative_owners(self):
        with ExitStack() as stack:
            order,validate,probe=self.setup_gate(stack)
            value=gate.qualify_default_staging_backup('/synthetic')
            self.assertEqual(p.options(p.DEFAULT),gate.accounting.replay.call_args.kwargs)
            self.assertEqual(p.options(p.DEFAULT),gate.handoff.replay.call_args.kwargs)
            self.assertEqual({},probe.call_args.kwargs)
        self.assertEqual(['original',*gate.NEGATIVES],order);validate.assert_called_once()
        gate.check_default_staging_backup_result(value)

    def test_wrong_or_successful_small_profile_probe_cannot_count_as_rejection(self):
        for error in (None,ValueError('unrelated failure')):
            with ExitStack() as stack:
                *_,probe=self.setup_gate(stack);probe.side_effect=error
                with self.assertRaisesRegex(ValueError,'accepted by small|exact staging rejection'):
                    gate.qualify_default_staging_backup('/synthetic')


if __name__=='__main__':unittest.main()
