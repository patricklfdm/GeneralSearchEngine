"""Caller-bound layout and original-first admission; synthetic cases are not evidence."""
import copy
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import bootstrap_replay_contract as p
from . import wire_archive as wire
from . import test_bootstrap_replay_contract as routes
from . import test_backup_required_four_resources as backup
from . import test_wire_archive as fixtures

m=backup.m


class SegmentedBackupReplayTest(unittest.TestCase):
    def test_layout_is_explicit_and_requires_backup_before_opening_original(self):
        calls=[(routes.catalog.Replay,()),(routes.catalog.validate,()),(routes.publication.validate,()),
               (routes.network.network,()),(routes.exports.context,('5-REPLACE',)),
               (routes.controls.Replay,('5-REPLACE',)),(routes.semantic.validate,()),
               (routes.physical.replay,()),(routes.physical.validate,()),
               (routes.four_network.replay,()),(routes.four_network.validate,()),
               (routes.four_exports.validate,()),(routes.maintenance.Replay,()),
               *((r,()) for r in routes.ledgers.READERS.values()),
               (routes.ledgers.validate,()),(routes.handoff.original,()),
               (routes.resources.validate,()),(routes.native.validate,())]
        for call,args in calls:
            for source,layout,reason in ((p.EMPTY,p.SEGMENTED,'requires backup'),
                                         (p.BACKUP,{'wireLayout':p.SEGMENTED},'explicit wire layout')):
                with self.subTest(call=call,layout=layout),self.assertRaisesRegex(ValueError,reason):
                    call('/absent-original',*args,bootstrap_source=source,wire_layout=layout)

    def test_receipts_cannot_choose_layout_or_be_reused_across_layouts(self):
        plain=p.receipt({'status':'PASS'},p.BACKUP)
        segmented=p.receipt({'status':'PASS'},p.BACKUP,p.SEGMENTED)
        self.assertNotIn('wireLayout',plain)
        self.assertEqual(p.SEGMENTED,segmented['wireLayout'])
        p.check_receipt(segmented,p.BACKUP,p.SEGMENTED)
        for value,layout in ((plain,p.SEGMENTED),(segmented,p.JSON),
                              (dict(segmented,wireLayout='JSON'),p.SEGMENTED)):
            with self.subTest(layout=layout),self.assertRaisesRegex(ValueError,'wire layout receipt'):
                p.check_receipt(value,p.BACKUP,layout)
        with self.assertRaisesRegex(ValueError,'wire layout receipt'):p.receipt(segmented,p.BACKUP)
        self.assertEqual({},p.options(p.EMPTY))
        self.assertEqual({'bootstrap_source':p.BACKUP},p.options(p.BACKUP))
        self.assertEqual({'bootstrap_source':p.BACKUP,'wire_layout':p.SEGMENTED},p.options(p.BACKUP,p.SEGMENTED))

    def test_layout_reaches_each_reconstructed_semantic_reader(self):
        calls=[(routes.network.network,(),dict(size=5,kind='REPLACE',required_four=True)),
               (routes.exports.context,('5-REPLACE',),dict(required_four=True)),
               (routes.physical.replay,(),{}),(routes.handoff.original,(),{})]
        for call,args,kwargs in calls:
            with self.subTest(call=call),ExitStack() as stack:
                stack.enter_context(patch.object(routes.catalog.collection,'read_json',return_value=[]))
                stack.enter_context(patch.object(routes.physical.p,'Captures'))
                stack.enter_context(patch.object(routes.physical,'Retirements'))
                model=stack.enter_context(patch.object(routes.catalog,'Replay',side_effect=ValueError('reader reached')))
                with self.assertRaisesRegex(ValueError,'^reader reached$'):
                    call('/original',*args,bootstrap_source=p.BACKUP,wire_layout=p.SEGMENTED,**kwargs)
                self.assertEqual(p.BACKUP,model.call_args.kwargs['bootstrap_source'])
                self.assertEqual(p.SEGMENTED,model.call_args.kwargs['wire_layout'])

    def test_adapters_forward_layout_and_shared_ledgers_cannot_mix_layouts(self):
        adapters=[(routes.four_exports.context,(),routes.exports,'context'),
                  (routes.four_exports.content,(),routes.exports,'replay'),
                  (routes.four_exports.control_reader,(),routes.controls,'Replay'),
                  (routes.four_exports.controls,({},),routes.four_exports,'control_reader'),
                  (routes.maintenance.Replay,(),routes.four_exports,'control_reader'),
                  (routes.maintenance.replay,(),routes.maintenance,'Replay'),
                  (routes.controls.Replay,('5-REPLACE',),routes.exports,'context'),
                  (routes.exports.replay,('5-REPLACE',),routes.exports,'context')]
        for call,args,module,name in adapters:
            with self.subTest(call=call),patch.object(module,name,side_effect=ValueError('reader reached')) as reader:
                with self.assertRaisesRegex(ValueError,'^reader reached$'):
                    call('/original',*args,bootstrap_source=p.BACKUP,wire_layout=p.SEGMENTED)
                self.assertEqual(p.SEGMENTED,reader.call_args.kwargs['wire_layout'])
        for reader in routes.ledgers.READERS.values():
            for actual,requested in ((p.JSON,p.SEGMENTED),(p.SEGMENTED,p.JSON)):
                base=SimpleNamespace(model=SimpleNamespace(bootstrap_source=p.BACKUP,wire_layout=actual))
                with self.subTest(reader=reader),self.assertRaisesRegex(ValueError,'shared wire layout'):
                    reader('/original',base=base,bootstrap_source=p.BACKUP,wire_layout=requested)

    def setup_gate(self,stack):
        order,inventory,validate,original,probe=backup.BackupRequiredFourResourcesTest().setup_gate(stack)
        from . import maximum_transition_inventory as large
        def whole_original(root, *, maximum):
            self.assertEqual(128*1024**3,maximum)
            return inventory(root)
        stack.enter_context(patch.object(large,'inventory',side_effect=whole_original))
        previous=validate.side_effect
        def validation(*args,**kwargs):
            self.assertEqual(p.SEGMENTED,kwargs.pop('wire_layout'))
            return p.receipt(previous(*args,**kwargs),p.BACKUP,p.SEGMENTED)
        validate.side_effect=validation
        def read(root,name,*,bootstrap_source,layout=p.JSON):
            self.assertEqual((Path('/synthetic'),'wire.json',p.BACKUP),(root,name,bootstrap_source))
            if layout==p.SEGMENTED:return []
            order.append('wire-layout');raise ValueError(m.LAYOUT_NEGATIVE['reason'])
        read=stack.enter_context(patch.object(wire,'read',side_effect=read))
        return order,inventory,validate,original,probe,read

    def test_segmented_gate_keeps_all_negatives_and_binds_layout_to_original(self):
        with ExitStack() as stack:
            order,_,_,_,_,read=self.setup_gate(stack)
            result=m.qualify_backup('/synthetic',wire_layout=p.SEGMENTED)
        self.assertEqual(['original',*m.NEGATIVES,'bootstrap-source','wire-layout'],order)
        self.assertEqual(149,sum(map(len,result['negatives'].values())))
        self.assertEqual(p.SEGMENTED,result['original']['wireLayout'])
        self.assertEqual(2,read.call_count)
        m.check_backup_result(result,wire_layout=p.SEGMENTED)
        with self.assertRaisesRegex(ValueError,'qualification scope'):m.check_backup_result(result)
        for mutation in ('original-layout','negative-missing','negative-reason'):
            bad=copy.deepcopy(result)
            if mutation=='original-layout':bad['original'].pop('wireLayout')
            elif mutation=='negative-missing':bad['negatives'].pop('wire-layout')
            else:bad['negatives']['wire-layout'][0]['reason']='unrelated'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                m.check_backup_result(bad,wire_layout=p.SEGMENTED)

    def test_bad_original_layout_stops_before_negative_qualification(self):
        with ExitStack() as stack:
            order,_,validate,_,probe,_=self.setup_gate(stack);prior=validate.side_effect
            def validation(*args,**kwargs):
                result=prior(*args,**kwargs);result.pop('wireLayout');return result
            validate.side_effect=validation
            with self.assertRaisesRegex(ValueError,'wire layout receipt'):
                m.qualify_backup('/synthetic',wire_layout=p.SEGMENTED)
            self.assertEqual(['original'],order);probe.assert_not_called()

    def test_segmented_gate_checks_the_whole_original_again_after_negatives(self):
        with ExitStack() as stack:
            _,inventory,_,_,_,_=self.setup_gate(stack)
            inventory.side_effect=[{'files':{'original':'a'}},{'files':{'original':'changed'}}]
            with self.assertRaisesRegex(ValueError,'^required-four resources original changed$'):
                m.qualify_backup('/synthetic',wire_layout=p.SEGMENTED)
            self.assertEqual(2,inventory.call_count)

    def test_default_layout_probe_must_fail_for_the_exact_reason(self):
        for error in (None,ValueError('unrelated')):
            with self.subTest(error=error),ExitStack() as stack:
                *_,read=self.setup_gate(stack)
                def wrong(*args,**kwargs):
                    if kwargs.get('layout')==p.SEGMENTED:return []
                    if error:raise error
                    return []
                read.side_effect=wrong
                with self.assertRaisesRegex(ValueError,'exact layout rejection|accepted by JSON contract'):
                    m.qualify_backup('/synthetic',wire_layout=p.SEGMENTED)

    def test_semantic_model_reads_only_its_explicit_layout_and_original_cut(self):
        helper=fixtures.WireArchiveTest();helper.setUp();self.addCleanup(helper.doCleanups)
        helper.original()
        model=SimpleNamespace(bootstrap_source=p.BACKUP,wire_layout=p.SEGMENTED)
        for name in wire.LIMITS:
            rows=wire.from_model(helper.root,model,name)
            self.assertEqual(2 if name=='wire.json' else 1,len(rows))
        for wrong in (SimpleNamespace(),SimpleNamespace(bootstrap_source=p.BACKUP),
                      SimpleNamespace(wire_layout=p.SEGMENTED)):
            with self.assertRaises(ValueError):wire.from_model(helper.root,wrong)
        # Resource negatives copy observations, never mutate the retained files.
        rows=wire.from_model(helper.root,model)
        copied=copy.deepcopy(rows);copied[0]['first']=False
        self.assertEqual({'first':True},rows[0]);copied.check_unchanged()


if __name__=='__main__':unittest.main()
