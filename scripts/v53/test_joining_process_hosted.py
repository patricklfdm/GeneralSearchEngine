"""Synthetic hosted orchestration; no native or GitHub execution claim."""
from contextlib import redirect_stdout
import copy
import io
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from . import joining_process_hosted as w
from . import test_joining_process_matrix as fixtures
from .test_process_toolchain import record


class JoiningProcessHostedTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.JoiningProcessMemberTest(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root; self.pins = self.fixture.pins; self.shard = next(iter(w.SHARDS)); self.cases = w.selected(self.shard)
        self.ctx = dict(kind='synthetic', repository='patricklfdm/GeneralSearchEngine', source='a'*40,
                        ref=w.BRANCH, event='push', run='17', attempt='2', workflow=w.WORKFLOW)
        data = self.root/'seed-data'; data.mkdir(); shutil.copytree(self.fixture.path, data/'producer')
        repo = data/'repository'; repo.mkdir(); (repo/'surefire.jar').write_bytes(b'original dependency'); (repo/'plugin.pom').write_bytes(b'original pom')
        self.seed = dict(schema=w.SCHEMA, context=self.ctx, status='PARTIAL', phase3Complete=False, cases=list(w.m.KINDS),
                         groups={k:list(v) for k,v in w.SHARDS.items()}, reader=self.fixture.reader,
                         **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'), self.pins)},
                         repositorySha256=w.shared.dependencies(repo))
        w.h.save(data/'seed.json', self.seed); self.bundle = self.root/'seed-bundle'; self.manifest = w.pack(data, self.bundle, self.ctx, 'seed')

    def produce(self, output, maven, case, *, source_from):
        self.assertTrue((source_from/'source.json').is_file()); shutil.copytree(self.fixture.path, output)
        receipt = w.m.read(output/'receipt.json'); raw = output/receipt['raw']; expected = w.m.run.selected(case); mode = expected['mode']
        value = w.m.read(raw/'joining-process/result.json'); value.update(mode=mode, point=expected['point'])
        value['children'][0].update(mode=mode, exit=73 if mode == 'halt' else 137)
        w.h.save(raw/'joining-process/result.json', value)
        trace = w.m.run.lines(raw/'process-trace.jsonl')
        for row in trace:
            if row['origin'] == 'halt':
                row['origin'] = mode; row['value']['value']['mode'] = mode
                if row['value']['kind'] == 'CUT': row['value']['value']['point'] = expected['point']
        if mode != 'halt': (raw/'joining-process/halt').rename(raw/'joining-process'/mode)
        w.m.physical.save_trace(raw, trace)
        value = w.m.read(raw/'joining-continuation-result.json'); value['profile'] = expected['profile']; w.h.save(raw/'joining-continuation-result.json', value)
        (raw/'original-plan.gsbp').write_bytes(case.encode()); w.h.save(output/'collection.json', w.m.run.collect(raw, case))
        receipt.update(case=case, command=['mvn', *w.m.run.command(case)], collectionSha256=w.h.digest((output/'collection.json').read_bytes()))
        w.h.save(output/'receipt.json', receipt)

    def execute(self, output=None, producer=None):
        output = output or self.root/'execute'
        with patch.object(w.tc, 'capture', return_value=record()), patch.object(w.m.run, 'run', side_effect=producer or self.produce) as called, redirect_stdout(io.StringIO()):
            result = w.group(self.bundle, output, self.shard, self.ctx, maven='mvn')
        return result, called

    def verify(self, output=None):
        def authority(raw, case, **kwargs): return fixtures.qualification(case)['authority']
        def physical(raw, case, **kwargs): return fixtures.qualification(case)['physical']
        def transaction(raw, case): return fixtures.qualification(case)['transactionNegatives']
        with patch.object(w.m.gate, 'qualify', side_effect=authority) as called, \
             patch.object(w.m.physical, 'qualify', side_effect=physical), patch.object(w.m.physical.transaction, 'negatives', side_effect=transaction), \
             redirect_stdout(io.StringIO()):
            result = w.group(self.bundle, output or self.root/'verify', self.shard, self.ctx, inputs=self.root/'execute/artifact')
        return result, called

    def verified(self):
        root = self.root/'verifiers'; root.mkdir()
        for shard, cases in w.SHARDS.items():
            members = []
            for case in cases:
                member = dict(schema=w.m.SCHEMA, case=case, status='PASS', phase3Complete=False, declaredJoiningProcessMatrixQualified=False,
                              qualification=fixtures.qualification(case), producerReceiptSha256=w.h.digest((case+'receipt').encode()),
                              originalPlanSha256=w.h.digest((case+'plan').encode()),
                              **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'), self.pins)})
                members.append(dict(schema=w.SCHEMA, context=self.ctx, case=case, status='PARTIAL', phase3Complete=False,
                                    seedArchiveSha256=self.manifest['archiveSha256'], rawArchiveSha256=w.h.digest((case+'archive').encode()),
                                    originalFirstDownloadedReplay=True, member=member))
            value = dict(schema=w.SCHEMA, context=self.ctx, shard=shard, stage='verify', status='PARTIAL', phase3Complete=False,
                         cases=members, seedArchiveSha256=self.manifest['archiveSha256'],
                         **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'), self.pins)})
            directory = root/w.artifact_name(self.ctx, 'verified', shard); directory.mkdir(); w.h.save(directory/'receipt.json', value)
        return root

    def test_groups_cover_exactly_360_cases_without_splitting_or_overlap(self):
        self.assertEqual(120, len(w.SHARDS)); self.assertTrue(all(len(v) == 3 for v in w.SHARDS.values()))
        self.assertEqual(list(w.m.KINDS), [v for cases in w.SHARDS.values() for v in cases])
        self.assertLessEqual(2*len(w.SHARDS), 256)
        for cases in w.SHARDS.values(): self.assertEqual(1, len({case.split(',')[0] for case in cases}))
        with self.assertRaisesRegex(ValueError, 'declared group'): w.selected('group-000')

    def test_three_originals_run_once_then_separate_downloaded_copy_replays_each(self):
        result, calls = self.execute(); self.assertEqual('PARTIAL', result['status'])
        self.assertEqual(list(self.cases), [call.args[2] for call in calls.call_args_list])
        self.assertEqual({w.m.slug(v) for v in self.cases}, {p.name for p in (self.root/'execute/artifact').iterdir()})
        result, calls = self.verify(); self.assertEqual('PARTIAL', result['status']); self.assertEqual(3, calls.call_count)
        for call in calls.call_args_list:
            self.assertIn('original/data/producer', str(call.args[0])); self.assertEqual(3, call.kwargs['workers'])
        self.assertTrue(all(v['originalFirstDownloadedReplay'] for v in result['cases']))

    def test_one_native_failure_is_retained_without_skipping_or_retrying_others(self):
        calls = []
        def produce(output, maven, case, **kwargs):
            calls.append(case)
            if case == self.cases[0]: output.mkdir(); (output/'failed-original').write_text('retained'); raise ValueError('native failure')
            return self.produce(output, maven, case, **kwargs)
        with self.assertRaisesRegex(ValueError, 'failed group members'): self.execute(producer=produce)
        self.assertEqual(list(self.cases), calls); value = w.m.read(self.root/'execute/receipt.json')
        self.assertEqual(['FAIL','PARTIAL','PARTIAL'], [v['status'] for v in value['cases']])
        data,_ = w.unpack(self.root/'execute/artifact'/w.m.slug(self.cases[0]), self.root/'failed-copy', self.ctx, 'raw', self.cases[0])
        self.assertEqual('retained', (data/'producer/failed-original').read_text())
        with self.assertRaisesRegex(ValueError, 'failed group members'): self.verify()
        value = w.m.read(self.root/'verify/receipt.json'); self.assertEqual(['FAIL','PARTIAL','PARTIAL'], [v['status'] for v in value['cases']])

    def test_missing_one_raw_does_not_skip_other_downloaded_members(self):
        self.execute(); shutil.rmtree(self.root/'execute/artifact'/w.m.slug(self.cases[0]))
        with self.assertRaisesRegex(ValueError, 'failed group members'): self.verify()
        value = w.m.read(self.root/'verify/receipt.json'); self.assertEqual(['FAIL','PARTIAL','PARTIAL'], [v['status'] for v in value['cases']])

    def test_copied_other_case_archive_refuses_without_skipping_valid_members(self):
        self.execute(); root = self.root/'execute/artifact'; first, second = (root/w.m.slug(v) for v in self.cases[:2])
        shutil.rmtree(second); shutil.copytree(first, second)
        with self.assertRaisesRegex(ValueError, 'failed group members'): self.verify()
        value = w.m.read(self.root/'verify/receipt.json')
        self.assertEqual(['PARTIAL','FAIL','PARTIAL'], [v['status'] for v in value['cases']])
        self.assertIn('artifact binding', value['cases'][1]['failure']['message'])

    def test_existing_output_is_not_overwritten_or_executed_again(self):
        self.execute(); original = (self.root/'execute/receipt.json').read_bytes()
        with patch.object(w.m.run, 'run') as run, self.assertRaises(FileExistsError):
            w.group(self.bundle, self.root/'execute', self.shard, self.ctx, maven='mvn')
        run.assert_not_called(); self.assertEqual(original, (self.root/'execute/receipt.json').read_bytes())

    def test_cancellation_retains_current_original_without_starting_later_members(self):
        calls = []
        def cancel(output, maven, case, **kwargs):
            calls.append(case); output.mkdir(); (output/'partial-original').write_text('interrupted'); raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.execute(producer=cancel)
        self.assertEqual([self.cases[0]], calls)
        self.assertEqual('FAIL', w.m.read(self.root/'execute/receipt.json')['status'])
        data,_ = w.unpack(self.root/'execute/artifact'/w.m.slug(self.cases[0]), self.root/'cancelled-copy', self.ctx, 'raw', self.cases[0])
        self.assertEqual('interrupted', (data/'producer/partial-original').read_text())

    def test_wrong_tools_refuse_before_any_native_execution(self):
        tools = record(); tools['identity']['binaries']['java/bin/java'] = 'b'*64
        with patch.object(w.tc, 'capture', return_value=tools), patch.object(w.m.run, 'run') as called, redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'failed group members'): w.group(self.bundle, self.root/'wrong-tools', self.shard, self.ctx, maven='mvn')
        called.assert_not_called()
        value = w.m.read(self.root/'wrong-tools/receipt.json'); self.assertEqual(3, len(value['cases']))
        self.assertTrue(all('worker toolchain' in v['failure']['message'] for v in value['cases']))

    def test_archive_context_case_role_and_seed_drift_are_rejected(self):
        for i,ctx in enumerate((dict(self.ctx, attempt='3'), dict(self.ctx, source='b'*40), dict(self.ctx, workflow=w.shared.WORKFLOW))):
            with self.assertRaisesRegex(ValueError, 'artifact binding'): w.unpack(self.bundle, self.root/f'wrong-{i}', ctx, 'seed')
        with self.assertRaisesRegex(ValueError, 'artifact binding'): w.unpack(self.bundle, self.root/'wrong-role', self.ctx, 'raw', self.cases[0])
        for i,name in enumerate(('producer/workspace/reader.py','producer/workspace/target/classes/original.class','repository/surefire.jar')):
            data,_ = w.unpack(self.bundle, self.root/f'drift-{i}', self.ctx, 'seed'); (data/name).write_bytes(b'drift')
            with self.assertRaises(ValueError): w.seed_inputs(data, self.ctx)
        data,_ = w.unpack(self.bundle, self.root/'missing-case', self.ctx, 'seed'); value = w.m.read(data/'seed.json'); value['groups'][self.shard].pop()
        w.h.save(data/'seed.json', value)
        with self.assertRaisesRegex(ValueError, 'seed scope'): w.seed_inputs(data, self.ctx)

    def test_linked_artifact_directory_and_extra_archive_inputs_refuse(self):
        linked = self.root/'linked-bundle'; linked.symlink_to(self.bundle, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'artifact directory'): w.unpack(linked, self.root/'linked-output', self.ctx, 'seed')
        (self.bundle/'unexpected').write_text('unaccounted')
        with self.assertRaisesRegex(ValueError, 'artifact directory'): w.unpack(self.bundle, self.root/'extra-output', self.ctx, 'seed')

    def test_aggregate_requires_all_360_exact_150_slot_qualifications(self):
        result = w.aggregate(self.bundle, self.verified(), self.root/'aggregate', self.ctx, 'success', 'success')
        self.assertEqual('PASS', result['status']); self.assertEqual(360, result['wholeHistories']); self.assertEqual(54000, result['negativeCases'])
        self.assertEqual(54000, result['rejected']+result['notApplicable'])
        self.assertTrue(result['declaredJoiningProcessMatrixQualified']); self.assertFalse(result['phase3Complete'])
        self.assertTrue(all(w.m.hash_field(v['verifierReceiptSha256']) for v in result['cases']))
        self.assertLess((self.root/'aggregate/receipt.json').stat().st_size, 8*w.h.snapshot.MIB)

    def test_failed_stage_missing_or_extra_verifier_never_aggregates(self):
        root = self.verified()
        for i,(execute,verify) in enumerate((('failure','success'),('success','failure'),('success','cancelled'),('skipped','success'),(None,'success'))):
            with self.assertRaisesRegex(ValueError, 'workflow stage'): w.aggregate(self.bundle, root, self.root/f'failed-{i}', self.ctx, execute, verify)
        extra = root/'extra'; extra.mkdir()
        with self.assertRaisesRegex(ValueError, 'verified inventory'): w.aggregate(self.bundle, root, self.root/'extra', self.ctx, 'success', 'success')
        extra.rmdir(); shutil.rmtree(root/w.artifact_name(self.ctx, 'verified', self.shard))
        with self.assertRaisesRegex(ValueError, 'verified inventory'): w.aggregate(self.bundle, root, self.root/'missing', self.ctx, 'success', 'success')

    def test_changed_group_and_member_bindings_and_negative_vectors_refuse(self):
        root = self.verified(); path = root/w.artifact_name(self.ctx, 'verified', self.shard)/'receipt.json'; original = w.m.read(path)
        second = original['cases'][1]
        mutations = [lambda v:v['context'].update(attempt='1'), lambda v:v.update(stage='execute'), lambda v:v.update(shard='group-002'),
                     lambda v:v['cases'].pop(), lambda v:v['cases'].reverse(), lambda v:v.update(seedArchiveSha256='b'*64),
                     lambda v:v['cases'][0].update(originalFirstDownloadedReplay=False),
                     lambda v:v['cases'][0]['member'].update(sourceSha256='b'*64),
                     lambda v:v['cases'][0]['member']['qualification']['authority']['negatives'].pop(),
                     lambda v:v['cases'][0]['member']['qualification']['physical']['negatives'][0].update(reason='unrelated'),
                     lambda v:v['cases'][0]['member']['qualification']['transactionNegatives'].pop(),
                     lambda v:v['cases'][0]['member'].update(originalPlanSha256=second['member']['originalPlanSha256']),
                     lambda v:v['cases'][0].update(rawArchiveSha256=second['rawArchiveSha256'])]
        for i,mutate in enumerate(mutations):
            value = copy.deepcopy(original); mutate(value); w.h.save(path, value)
            with self.subTest(mutation=i), self.assertRaises(ValueError): w.aggregate(self.bundle, root, self.root/f'changed-{i}', self.ctx, 'success', 'success')

    def test_original_replay_failure_is_not_negative_success_and_does_not_retry(self):
        self.execute()
        with patch.object(w.m.gate, 'qualify', side_effect=ValueError('invalid original')) as called, redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'failed group members'):
                w.group(self.bundle, self.root/'failed-verification', self.shard, self.ctx, inputs=self.root/'execute/artifact')
        self.assertEqual(3, called.call_count)
        self.assertTrue(all(v['status'] == 'FAIL' for v in w.m.read(self.root/'failed-verification/receipt.json')['cases']))

    def test_only_dispatch_or_exact_experiment_branch_is_admitted(self):
        env = dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=self.ctx['repository'], GITHUB_SHA=self.ctx['source'], GITHUB_REF=w.BRANCH,
                   GITHUB_EVENT_NAME='push', GITHUB_RUN_ID='17', GITHUB_RUN_ATTEMPT='2', V53_WORKFLOW_SHA=self.ctx['source'],
                   V53_WORKFLOW_REF=self.ctx['repository']+'/'+w.WORKFLOW+'@'+w.BRANCH)
        with patch.dict(os.environ, env, clear=True), patch.object(w.shared.subprocess, 'check_output', return_value=self.ctx['source']+'\n'):
            self.assertEqual(dict(self.ctx, kind='github'), w.context())
            for key,value in (('GITHUB_EVENT_NAME','pull_request'),('GITHUB_REF',w.shared.BRANCH),('V53_WORKFLOW_SHA','b'*40)):
                with patch.dict(os.environ, {key:value}), self.assertRaises(ValueError): w.context()
            with patch.dict(os.environ, {'GITHUB_EVENT_NAME':'workflow_dispatch'}): self.assertEqual('workflow_dispatch', w.context()['event'])

    def test_summary_shows_all_group_cases_and_actual_scope(self):
        path = self.root/'summary.md'; w.summary(path, self.ctx, 'verify', self.shard, dict(status='PARTIAL'))
        text = path.read_text()
        for case in self.cases: self.assertIn(case, text)
        self.assertIn('360', text); self.assertIn('False', text); self.assertIn('17 / 2', text)


if __name__ == '__main__': unittest.main()
