"""Caller-selected source policy and independent reader construction boundaries."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from . import bootstrap_replay_contract as policy
from . import joining_catalog_evidence as catalog
from . import joining_publication_evidence as publication
from . import joining_network_evidence as network
from . import joining_profile_export_evidence as exports
from . import joining_profile_control_evidence as controls
from . import required_four_evidence as semantic
from . import required_four_physical as physical
from . import required_four_network as four_network
from . import required_four_exports as four_exports
from . import required_four_maintenance as maintenance
from . import required_four_ledgers as ledgers
from . import joined_handoff_resources as handoff
from . import publication_resource_evidence as resources
from . import native_resource_evidence as native


class BootstrapReplayContractTest(unittest.TestCase):
    def test_only_explicit_source_enums_and_no_receipt_inference(self):
        for value in (None, True, 1, {}, {'bootstrapSource':policy.BACKUP}, 'backup', ''):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'explicit bootstrap source'):
                policy.options(value)
        self.assertEqual({}, policy.options(policy.EMPTY))
        self.assertEqual({'bootstrap_source':policy.BACKUP}, policy.options(policy.BACKUP))

    def test_empty_receipts_remain_unchanged_and_sources_are_not_interchangeable(self):
        original={'status':'PASS'}
        self.assertIs(original, policy.receipt(original, policy.EMPTY))
        backup=policy.receipt(original, policy.BACKUP)
        self.assertEqual({'status':'PASS'}, original)
        self.assertEqual({'status':'PASS','bootstrapSource':policy.BACKUP}, backup)
        policy.check_receipt(original, policy.EMPTY); policy.check_receipt(backup, policy.BACKUP)
        for value, source in ((backup,policy.EMPTY),(original,policy.BACKUP),
                              (dict(backup,bootstrapSource='EMPTY'),policy.BACKUP)):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'source receipt'):
                policy.check_receipt(value,source)
        with self.assertRaisesRegex(ValueError,'source receipt'):policy.receipt(backup,policy.EMPTY)

    def test_invalid_source_rejected_before_opening_any_original(self):
        calls=[(catalog.Replay,()),(catalog.validate,()),(publication.validate,()),(network.network,()),
               (exports.context,('5-REPLACE',)),(exports.replay,('5-REPLACE',)),(controls.Replay,('5-REPLACE',)),
               (semantic.validate,()),(physical.replay,()),(physical.validate,()),
               (four_network.replay,()),(four_network.validate,()),(four_exports.context,()),
               (four_exports.control_reader,()),(four_exports.content,()),(four_exports.controls,({},)),
               (four_exports.validate,()),(maintenance.Replay,()),(maintenance.replay,()),(maintenance.validate,()),
               *((reader,()) for reader in ledgers.READERS.values()),(ledgers.replay,()),(ledgers.validate,()),
               (handoff.original,()),(resources.original,('5-REPLACE-required-four',)),(resources.validate,()),(native.validate,())]
        for call,args in calls:
            with self.subTest(call=call),self.assertRaisesRegex(ValueError,'explicit bootstrap source'):
                call('/absent-original',*args,bootstrap_source='from-receipt')

    def test_backup_source_does_not_expand_unrelated_resource_profiles(self):
        for call in (resources.original,resources.validate,native.validate):
            for profile in ('stable','5-REPLACE'):
                with self.subTest(call=call,profile=profile),self.assertRaisesRegex(ValueError,'source profile'):
                    call('/absent-original',profile,bootstrap_source=policy.BACKUP)

    def test_source_reaches_reconstructed_semantic_readers(self):
        # A sentinel at the real constructor boundary proves propagation without
        # fabricating a complete native history or accepting a summary as proof.
        calls=[(lambda:network.network('/original',size=5,kind='REPLACE',required_four=True,bootstrap_source=policy.BACKUP)),
               (lambda:exports.context('/original','5-REPLACE',required_four=True,bootstrap_source=policy.BACKUP)),
               (lambda:physical.replay('/original',bootstrap_source=policy.BACKUP)),
               (lambda:handoff.original('/original',bootstrap_source=policy.BACKUP))]
        for call in calls:
            with self.subTest(call=call),ExitStack() as stack:
                stack.enter_context(patch.object(catalog.collection,'read_json',return_value=[]))
                stack.enter_context(patch.object(physical.p,'Captures'))
                stack.enter_context(patch.object(physical,'Retirements'))
                reader=stack.enter_context(patch.object(catalog,'Replay',side_effect=ValueError('reader reached')))
                with self.assertRaisesRegex(ValueError,'^reader reached$'):call()
                self.assertEqual(policy.BACKUP,reader.call_args.kwargs['bootstrap_source'])
                self.assertTrue(reader.call_args.kwargs['required_four'])

    def test_export_and_maintenance_adapters_keep_source_through_each_constructor(self):
        routes=[(four_exports.context,(),exports,'context'),(four_exports.content,(),exports,'replay'),
                (four_exports.control_reader,(),controls,'Replay'),
                (four_exports.controls,({},),four_exports,'control_reader'),
                (maintenance.Replay,(),four_exports,'control_reader'),
                (maintenance.replay,(),maintenance,'Replay'),
                (controls.Replay,('5-REPLACE',),exports,'context'),
                (exports.replay,('5-REPLACE',),exports,'context')]
        for call,args,module,name in routes:
            with self.subTest(call=call),patch.object(module,name,side_effect=ValueError('reader reached')) as reader:
                with self.assertRaisesRegex(ValueError,'^reader reached$'):
                    call('/original',*args,bootstrap_source=policy.BACKUP)
                self.assertEqual(policy.BACKUP,reader.call_args.kwargs['bootstrap_source'])

    def test_shared_ledger_context_cannot_mix_source_policies(self):
        for reader in ledgers.READERS.values():
            for actual,requested in ((policy.EMPTY,policy.BACKUP),(policy.BACKUP,policy.EMPTY)):
                base=SimpleNamespace(model=SimpleNamespace(bootstrap_source=actual))
                with self.subTest(reader=reader,source=requested),self.assertRaisesRegex(ValueError,'shared bootstrap source'):
                    reader('/original',base=base,bootstrap_source=requested)

    def test_matching_ledger_context_is_reused_without_rereading_or_relabeling(self):
        base=SimpleNamespace(model=SimpleNamespace(bootstrap_source=policy.BACKUP))
        for reader,parent in ((ledgers.LearnerReplay,ledgers.learner.Replay),
                              (ledgers.FutureReplay,ledgers.future.Replay),
                              (ledgers.BallotReplay,ledgers.ballot_profile.ballot.Replay)):
            with self.subTest(reader=reader),patch.object(parent,'__init__',return_value=None) as init,\
                 patch.object(maintenance,'Replay') as reread:
                reader('/original',base=base,bootstrap_source=policy.BACKUP)
                init.assert_called_once_with('/original',base=base);reread.assert_not_called()

    def test_native_requires_same_source_physical_and_ledger_preconditions(self):
        for stop in ('physical','ledger'):
            with self.subTest(stop=stop),patch.object(native.collection,'inventory',return_value={}),\
                 patch.object(resources,'validate',return_value={}) as physical_gate,\
                 patch.object(ledgers,'validate',side_effect=ValueError('ledger reached')) as ledger_gate,\
                 patch.object(native,'load') as load:
                if stop=='physical':physical_gate.side_effect=ValueError('physical reached')
                with self.assertRaisesRegex(ValueError,stop+' reached'):
                    native.validate('/original','5-REPLACE-required-four',bootstrap_source=policy.BACKUP)
                self.assertEqual(policy.BACKUP,physical_gate.call_args.kwargs['bootstrap_source'])
                if stop=='ledger':self.assertEqual(policy.BACKUP,ledger_gate.call_args.kwargs['bootstrap_source'])
                else:ledger_gate.assert_not_called()
                load.assert_not_called()

    def test_backup_validation_receipt_is_marked_and_empty_invocations_unchanged(self):
        # Test both precondition and independently reconstructed physical pass.
        for source in (policy.EMPTY,policy.BACKUP):
            with self.subTest(source=source),patch.object(catalog.collection,'inventory',return_value={}),\
                 patch.object(semantic,'validate',return_value={}) as first,\
                 patch.object(physical,'replay',return_value={}) as second:
                observer=object()
                result=physical.validate('/original',publication_observer=observer,bootstrap_source=source)
                first.assert_called_once_with(Path('/original'),publication_observer=observer,**policy.options(source))
                second.assert_called_once_with(Path('/original'),**policy.options(source))
                policy.check_receipt(result,source)
                self.assertFalse(result['phase3Complete']);self.assertFalse(result['finalSourceCohortQualified'])

    def test_native_later_resource_projections_keep_the_same_selected_source(self):
        from . import test_native_resource_evidence as fixture
        from . import owner_close_evidence, publication_generation_resources, control_close_evidence, native_control_closes
        from . import transport_resource_evidence, floor_resource_evidence, receive_resource_evidence, basis_resource_evidence
        from . import published_prefix_probe_evidence
        data=fixture.NativeResourceEvidenceTest().original(6)
        index,traces,boundaries,events,identities,authority=data
        for source in (policy.EMPTY,policy.BACKUP):
            with self.subTest(source=source),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root=Path(temp);(root/'control-close-captures').mkdir()
                reader=SimpleNamespace(model=SimpleNamespace(states=[{'identities':list(identities.values())}],
                    root=authority,joining='node-6',bootstrap_source=source),events=events,run=lambda *args:None)
                methods=[(native.collection,'inventory',{}),(native.collection,'read_json',[]),
                    (resources,'validate',{}),(ledgers,'validate',{}),(four_exports,'control_reader',reader),
                    (native,'load',data[:4]),(owner_close_evidence,'replay',{}),
                    (resources,'collect',[]),(publication_generation_resources,'replay',{}),
                    (control_close_evidence,'load',[]),(native_control_closes,'replay',{'status':'PASS','precondition':{}}),
                    (transport_resource_evidence,'replay',{}),(maintenance,'Replay',reader),
                    (floor_resource_evidence,'plans',{}),(floor_resource_evidence,'replay',{}),
                    (receive_resource_evidence,'derive',{}),(receive_resource_evidence,'replay',{}),
                    (basis_resource_evidence,'derive',{}),(basis_resource_evidence,'replay',{}),
                    (handoff,'original',object()),(handoff,'project',{}),(handoff,'replay',{}),
                    (four_exports,'content',{}),(published_prefix_probe_evidence,'replay',{})]
                calls={(module,name):stack.enter_context(patch.object(module,name,return_value=value))
                       for module,name,value in methods}
                result=native.validate(root,'5-REPLACE-required-four',control_closes=True,
                    export_ownership=True,published_probe=True,bootstrap_source=source)
                for module,name in ((four_exports,'control_reader'),(maintenance,'Replay'),
                                    (handoff,'original'),(four_exports,'content')):
                    calls[module,name].assert_called_once_with(root,**policy.options(source))
                policy.check_receipt(result,source)
                self.assertFalse(result['wholeRuntimeResourcesQualified'])


if __name__=='__main__':unittest.main()
