"""Synthetic orchestration and real owning aggregate contracts, not JVM evidence."""
from contextlib import redirect_stdout
import importlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from . import phase3_history_cohort as c
from . import test_phase3_seed_cohort as seed_fixture


class OfflineAggregateTest(unittest.TestCase):
    def test_all_twelve_owners_keep_exact_checks_and_offline_scope(self):
        for name, adapter in c.seeds.adapters().items():
            with self.subTest(cohort=name):
                module = importlib.import_module('.test_'+adapter.__name__.split('.')[-1], __package__)
                cls, = [v for v in vars(module).values() if isinstance(v, type) and
                        issubclass(v, unittest.TestCase) and v.__module__ == module.__name__]
                fixture = cls()
                try:
                    fixture.setUp()
                    bundle = getattr(fixture, 'bundle', getattr(fixture, 'seed_bundle', None))
                    inputs = getattr(fixture, 'verified', getattr(fixture, 'verifier_inputs', None))()
                    online = adapter.aggregate(bundle, inputs, fixture.root/'online', fixture.ctx, 'success', 'success')
                    offline = adapter.aggregate(bundle, inputs, fixture.root/'offline', fixture.ctx, None, None, offline_replay=True)
                    self.assertEqual('PASS', online['status']); self.assertEqual('PARTIAL', offline['status'])
                    self.assertIs(False, offline['phase3Complete']); self.assertIs(False, offline['workflowExecutionAttested'])
                    self.assertIs(True, offline['offlineEvidenceOnly'])
                    self.assertEqual(offline, c.seeds.read(fixture.root/'offline/receipt.json'))
                    ignored = {'status', 'acceptanceAuthority', 'offlineEvidenceOnly', 'workflowExecutionAttested'}
                    self.assertEqual({k:v for k,v in online.items() if k not in ignored},
                                     {k:v for k,v in offline.items() if k not in ignored})
                    for i, args in enumerate(((None, None, False), ('success', 'success', True), (None, None, 1))):
                        with self.assertRaises(ValueError):
                            adapter.aggregate(bundle, inputs, fixture.root/f'refused-{i}', fixture.ctx,
                                              args[0], args[1], offline_replay=args[2])
                    path = next(inputs.iterdir())/'receipt.json'; receipt = c.seeds.read(path)
                    receipt['status'] = 'FAIL'; c.h.save(path, receipt)
                    with self.assertRaises(ValueError):
                        adapter.aggregate(bundle, inputs, fixture.root/'invalid', fixture.ctx, None, None, offline_replay=True)
                    self.assertEqual('FAIL', c.seeds.read(fixture.root/'invalid/receipt.json')['status'])
                finally: fixture.doCleanups()


class RetainedOriginalTest(unittest.TestCase):
    def test_joining_owner_replays_three_originals_and_retains_child_diagnostics(self):
        from .test_joining_process_hosted import JoiningProcessHostedTest
        from . import test_joining_process_matrix as f
        fixture = JoiningProcessHostedTest(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        fixture.execute(); adapter = c.seeds.adapters()['joining-process']
        with patch.object(adapter.m.gate, 'qualify', side_effect=lambda raw,case,**kw: f.qualification(case)['authority']) as replay, \
             patch.object(adapter.m.physical, 'qualify', side_effect=lambda raw,case,**kw: f.qualification(case)['physical']), \
             patch.object(adapter.m.physical.transaction, 'negatives', side_effect=lambda raw,case: f.qualification(case)['transactionNegatives']), \
             redirect_stdout(io.StringIO()):
            value = c.replay_group('joining-process', adapter, fixture.bundle, fixture.root/'execute/artifact',
                                   fixture.root/'joined', fixture.shard, fixture.ctx)
        self.assertEqual(3, replay.call_count); self.assertEqual('PARTIAL', value['status'])
        self.assertEqual(list(fixture.cases), [row['case'] for row in value['cases']])
        self.assertFalse(list((fixture.root/'joined').glob('scratch-*')))
        for case in fixture.cases:
            child = fixture.root/'joined'/adapter.m.slug(case)
            self.assertTrue(c.seeds.read(child/'receipt.json')['originalFirstDownloadedReplay'])
            self.assertTrue((child/'progress.jsonl').is_file())

    def test_owning_verifier_reopens_original_and_failure_keeps_its_receipt(self):
        from .test_remove_process_hosted import HostedRemoveTest
        from . import test_remove_process_matrix as f
        fixture = HostedRemoveTest(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        adapter = c.seeds.adapters()['remove-process']; _, raw = fixture.raw()
        before = c.seeds.bundle_identity(raw)
        with patch.object(adapter.m.gate, 'qualify', side_effect=f.RemoveProcessMatrixTest.replay) as replay:
            value = c.replay_group('remove-process', adapter, fixture.seed_bundle, raw,
                                   fixture.root/'good', fixture.case, fixture.ctx)
        self.assertTrue(value['originalFirstDownloadedReplay']); replay.assert_called_once()
        self.assertIn('/original/data/', str(replay.call_args.args[0]))
        self.assertFalse(list((fixture.root/'good').glob('scratch-*')))
        with patch.object(adapter.m.gate, 'qualify', side_effect=ValueError('original physical failure')) as replay:
            with self.assertRaisesRegex(ValueError, 'original physical failure'):
                c.replay_group('remove-process', adapter, fixture.seed_bundle, raw,
                               fixture.root/'bad', fixture.case, fixture.ctx)
        replay.assert_called_once(); failure = c.seeds.read(fixture.root/'bad/failure.json')
        work = fixture.root/'bad'/failure['retainedScratch']/'replay'
        self.assertEqual('FAIL', c.seeds.read(work/'receipt.json')['status'])
        self.assertTrue((work/'original/data/producer').is_dir())
        self.assertEqual(before, c.seeds.bundle_identity(raw))


class HistoryCohortTest(unittest.TestCase):
    def setUp(self):
        self.f = seed_fixture.Phase3SeedCohortTest(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root; self.inputs = self.root/'originals'; self.inputs.mkdir()
        self.catalogs = c.plan.catalogues(); self.verified = []; self.aggregated = []; self.count = 0
        _, self.witness_plan = c.witnesses.prepare()
        self.bundles = []; self.after_verify = lambda name,key: None
        data = self.root/'tiny-original'; data.mkdir()
        for name, adapter in self.f.modules.items():
            ctx = self.f.index['cohorts'][name]
            for key, cases in c.groups(name, adapter, self.catalogs[name]).items():
                group = self.inputs/name/adapter.artifact_name(ctx, 'raw', key)
                members = [(case, group/adapter.m.slug(case)) for case in cases] if name == 'joining-process' else [(key, group)]
                for case, bundle in members:
                    (data/'synthetic.txt').write_text(name+'/'+case)
                    adapter.pack(data, bundle, ctx, 'raw', case); self.bundles.append(bundle)
            # These stubs stand for expensive owning readers, not successful JVM runs.
            if name == 'joining-process':
                def group(seed, output, key, ctx, *, inputs, maven=None, name=name, adapter=adapter):
                    self.assertIsNone(maven)
                    for i,case in enumerate(adapter.SHARDS[key]):
                        adapter.unpack(inputs/adapter.m.slug(case), Path(output)/f'raw-{i}', ctx, 'raw', case)
                    return self.verifier(name, key, output)
                self.f.stack.enter_context(patch.object(adapter, 'group', side_effect=group))
            else:
                def verify(seed, raw, output, key, ctx, name=name, adapter=adapter):
                    adapter.unpack(raw, Path(output)/'original', ctx, 'raw', key)
                    return self.verifier(name, key, output)
                self.f.stack.enter_context(patch.object(adapter, 'verify', side_effect=verify))
            def aggregate(seed, inputs, output, ctx, execute, verify, *, offline_replay, name=name, adapter=adapter):
                self.assertEqual((None, None, True), (execute, verify, offline_replay))
                c.exact_directory(inputs, [adapter.artifact_name(ctx, 'verified', key)
                                          for key in c.groups(name, adapter, self.catalogs[name])])
                for path in inputs.iterdir():
                    value = c.seeds.read(path/'receipt.json'); self.assertEqual(name, value['owner'])
                self.aggregated.append(name); output.mkdir(parents=True)
                value = dict(status='PARTIAL', phase3Complete=False, offlineEvidenceOnly=True,
                             workflowExecutionAttested=False, wholeHistories=self.catalogs[name]['members'])
                c.h.save(output/'receipt.json', value); return value
            self.f.stack.enter_context(patch.object(adapter, 'aggregate', side_effect=aggregate))
        self.originals = c.raw_inventory(self.inputs, self.f.index, self.f.modules, self.catalogs)

    def verifier(self, name, key, output):
        self.verified.append((name, key)); output.mkdir(parents=True, exist_ok=True)
        value = dict(status='PARTIAL', phase3Complete=False, owner=name, group=key)
        from .test_phase3_witness_observations import group_fixture
        if c.witnesses.selected(self.witness_plan, name, key):
            value.update(group_fixture(name, key, self.f.index['cohorts'][name], self.originals))
        c.h.save(output/'receipt.json', value)
        (output/'progress.jsonl').write_text('{"synthetic":true}\n')
        self.after_verify(name, key)
        return value

    def run_gate(self):
        self.count += 1; self.output = self.root/f'result-{self.count}'
        with redirect_stdout(io.StringIO()):
            return c.run(self.f.index_path, self.f.inputs, self.inputs, self.output)

    def test_all_486_original_archives_route_to_246_whole_groups_and_twelve_owners(self):
        before = c.raw_inventory(self.inputs, self.f.index, self.f.modules, self.catalogs)
        value = self.run_gate()
        self.assertEqual((486, 246, 552), (value['rawArchives'], value['groupsReplayed'], value['historiesReplayed']))
        self.assertEqual(246, len(self.verified)); self.assertEqual(list(self.f.modules), self.aggregated)
        self.assertEqual('PARTIAL', value['status']); self.assertTrue(value['allDeclaredHistoriesReplayed'])
        for key in ('phase3Complete','runtimeQualified','workflowExecutionAttested',
                    'frozenScenarioCoverageQualified','combinedPeakResourcesQualified'):
            self.assertIs(False, value[key])
        self.assertEqual(before, c.raw_inventory(self.inputs, self.f.index, self.f.modules, self.catalogs))
        self.assertFalse(list(self.output.rglob('scratch-*')))
        self.assertEqual(246, len(list(self.output.glob('*/groups/*/progress.jsonl'))))
        coverage = c.seeds.read(self.output/'coverage.json')
        self.assertEqual((17, 3), (coverage['rejected'], coverage['notApplicable']))
        self.assertEqual('PARTIAL', coverage['status']); self.assertFalse(coverage['phase3Complete'])
        self.assertEqual(20, len(coverage['witnesses']))
        self.assertEqual(c.shared.tc.file_hash(self.output/'coverage.json'), value['candidateWitnesses']['sha256'])
        self.assertEqual(c.witnesses.prepare()[0], (self.output/'coverage-plan.json').read_bytes())

    def test_missing_group_extra_group_and_partial_joining_group_refuse_before_readers(self):
        group = self.bundles[0]; moved = self.root/'saved'; group.rename(moved)
        with self.assertRaisesRegex(ValueError, 'exact artifact inventory'): self.run_gate()
        moved.rename(group)
        (self.inputs/'profiles/extra').mkdir()
        with self.assertRaisesRegex(ValueError, 'exact artifact inventory'): self.run_gate()
        (self.inputs/'profiles/extra').rmdir()
        child = next(p for p in self.bundles if p.is_relative_to(self.inputs/'joining-process')); child.rename(moved)
        with self.assertRaisesRegex(ValueError, 'exact artifact inventory'): self.run_gate()
        self.assertFalse(self.verified)

    def test_wrong_attempt_case_and_duplicate_json_keys_refuse_before_readers(self):
        path = self.bundles[0]/'manifest.json'; original = path.read_bytes()
        for field, value in (('case', 'foreign'), ('context', dict(self.f.index['cohorts']['profiles'], attempt='1'))):
            row = c.plan.decode(original); row[field] = value; c.h.save(path, row)
            with self.assertRaisesRegex(ValueError, 'original context/case'): self.run_gate()
        path.write_bytes(b'{"schema":null,'+original[1:])
        with self.assertRaisesRegex(ValueError, 'duplicate key'): self.run_gate()
        self.assertFalse(self.verified)

    def test_links_and_hardlinks_refuse_before_readers(self):
        path = self.bundles[0]/'bundle.tar.gz'; saved = self.root/'saved.gz'; path.rename(saved); path.symlink_to(saved)
        with self.assertRaisesRegex(ValueError, 'linked path'): self.run_gate()
        path.unlink(); path.hardlink_to(saved)
        with self.assertRaisesRegex(ValueError, 'archive capacity/type'): self.run_gate()
        self.assertFalse(self.verified)

    def test_failed_original_stops_without_retry_and_keeps_diagnostics(self):
        def fail(name, key): raise ValueError('original rejected')
        self.after_verify = fail
        with self.assertRaisesRegex(ValueError, 'original rejected'): self.run_gate()
        value = c.seeds.read(self.output/'receipt.json')
        self.assertEqual('FAIL', value['status']); self.assertEqual(1, len(self.verified)); self.assertFalse(self.aggregated)
        self.assertEqual('profiles', value['active']['cohort']); self.assertFalse(value['allDeclaredHistoriesReplayed'])
        self.assertTrue(list(self.output.rglob('scratch-*/replay/receipt.json')))
        self.assertTrue(self.bundles[0].is_dir())
        self.assertFalse((self.output/'coverage.json').exists())
        self.assertFalse((self.output/'witness-observations.json').exists())

    def test_late_original_and_seed_drift_refuse_even_after_all_replays(self):
        for kind in ('raw', 'seed'):
            target = (self.bundles[0] if kind == 'raw' else self.f.inputs/'profiles')/'manifest.json'
            original = target.read_bytes()
            def change(name, key):
                if name == 'joint-floor-process': target.write_bytes(original+b'\n')
            self.after_verify = change
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, '(originals|seed) changed during replay'): self.run_gate()
            self.assertEqual('FAIL', c.seeds.read(self.output/'receipt.json')['status'])
            target.write_bytes(original)

    def test_changed_index_refuses_after_replay(self):
        original = self.f.index_path.read_bytes()
        self.after_verify = lambda name,key: self.f.index_path.write_bytes(original+b'\n')
        with self.assertRaisesRegex(ValueError, 'index/checkout changed'): self.run_gate()

    def test_foreign_compiled_seed_is_rejected_before_original_replay(self):
        path = self.f.data['node-renames']/'producer/workspace/target/classes/test.class'
        path.write_bytes(b'other class'); self.f.refresh('node-renames')
        with self.assertRaisesRegex(ValueError, 'mixed source/build/tools/dependencies'): self.run_gate()
        self.assertFalse(self.verified)

    def test_existing_output_and_overlap_cannot_destroy_inputs(self):
        for output in (self.inputs, self.inputs/'new', self.f.inputs, self.f.inputs/'new', self.f.index_path.parent):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'output overlaps'):
                c.run(self.f.index_path, self.f.inputs, self.inputs, output)
        self.run_gate()
        with self.assertRaises(FileExistsError): c.run(self.f.index_path, self.f.inputs, self.inputs, self.output)


if __name__ == '__main__': unittest.main()
