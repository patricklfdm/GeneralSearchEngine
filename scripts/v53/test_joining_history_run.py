import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import io
from contextlib import redirect_stdout
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import joining_history_run as h


def rawsave(path, value):
    path.write_bytes(h.snapshot.f.canonical(value))


class JoiningHistoryRunTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def report(self, **changes):
        import xml.etree.ElementTree as ET
        attrs = dict(name=h.CLASS, tests='1', failures='0', errors='0', skipped='0'); attrs.update(changes)
        suite = ET.Element('testsuite', attrs)
        ET.SubElement(suite, 'testcase', dict(classname=h.CLASS, name=h.METHOD))
        ET.ElementTree(suite).write(self.root / 'TEST-joining.xml')
        return suite

    def test_only_the_exact_successful_whole_method_counts(self):
        self.report(); self.assertEqual(1, h.junit(self.root)['tests'])
        for field, value in [('failures', '1'), ('errors', '1'), ('skipped', '1'), ('tests', '0'), ('tests', '2'), ('name', 'Other')]:
            with self.subTest(field=field):
                self.report(**{field: value})
                with self.assertRaisesRegex(ValueError, 'test did not pass'): h.junit(self.root)
        suite = self.report(); suite.find('testcase').set('name', 'shorterJoiningScenario')
        import xml.etree.ElementTree as ET
        ET.ElementTree(suite).write(self.root / 'TEST-joining.xml')
        with self.assertRaisesRegex(ValueError, 'exact test case'): h.junit(self.root)

    def test_missing_duplicate_or_hidden_failed_test_report_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'exact test report'): h.junit(self.root)
        suite = self.report()
        import xml.etree.ElementTree as ET
        ET.SubElement(suite.find('testcase'), 'failure')
        ET.ElementTree(suite).write(self.root / 'TEST-joining.xml')
        with self.assertRaisesRegex(ValueError, 'exact test case'): h.junit(self.root)
        self.report(); (self.root / 'TEST-extra.xml').write_bytes((self.root / 'TEST-joining.xml').read_bytes())
        with self.assertRaisesRegex(ValueError, 'exact test report'): h.junit(self.root)

    def test_inventory_checks_content_empty_directories_links_and_budget(self):
        (self.root / 'empty').mkdir(); data = self.root / 'data'; data.write_bytes(b'abc')
        original = h.inventory(self.root, maximum=3)
        self.assertEqual(['empty'], original['directories'])
        self.assertEqual(h.digest(b'abc'), original['files']['data'])
        data.write_bytes(b'abd'); self.assertNotEqual(original, h.inventory(self.root, maximum=3))
        with self.assertRaisesRegex(ValueError, 'byte capacity'): h.inventory(self.root, maximum=2)
        (self.root / 'link').symlink_to(data)
        with self.assertRaisesRegex(ValueError, 'linked member'): h.inventory(self.root)
        (self.root / 'link').unlink(); os.link(data, self.root / 'hardlink')
        with self.assertRaisesRegex(ValueError, 'regular member'): h.inventory(self.root)

    def test_source_mutation_is_rejected(self):
        p = self.root / 'source'; p.write_bytes(b'original')
        source = dict(files={'source': h.digest(b'original')}); h.check_source(self.root, source)
        p.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'source copy changed'): h.check_source(self.root, source)

    def test_large_trace_keeps_per_message_checks_and_rejects_duplicate_keys(self):
        rows = [dict(node='node-4', event='observed-' + str(i)) for i in range(20000)]
        rawsave(self.root / 'events.json', rows)
        self.assertEqual(rows, h.read_json(self.root, 'events.json', 8 * 1024 * 1024))
        (self.root / 'events.json').write_bytes(b'[{"event":"first","event":"last"}]')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'): h.read_json(self.root, 'events.json', 4096)
        (self.root / 'events.json').write_bytes(b'[ ]')
        with self.assertRaisesRegex(ValueError, 'noncanonical JSON'): h.read_json(self.root, 'events.json', 4096)

    def test_real_failed_command_keeps_output_and_does_not_retry(self):
        log = self.root / 'command.log'
        result = h.execute([sys.executable, '-c', 'print("before-failure", flush=True); raise SystemExit(3)'], self.root, log)
        self.assertEqual(3, result['exit']); self.assertEqual('before-failure\n', log.read_text())
        with self.assertRaises(FileExistsError): h.execute([sys.executable, '-c', 'pass'], self.root, log)

    def test_heartbeat_wait_is_observation_not_a_retry_or_execution_timeout(self):
        from unittest.mock import Mock
        process = Mock(pid=42); process.wait.side_effect = [subprocess.TimeoutExpired('test', 60), 0]
        with patch.object(h.subprocess, 'Popen', return_value=process) as start, redirect_stdout(io.StringIO()) as output:
            result = h.execute(['test'], self.root, self.root / 'progress.log')
        start.assert_called_once(); self.assertEqual(0, result['exit'])
        row = json.loads(output.getvalue()); self.assertEqual('whole-joining', row['stage']); self.assertEqual(42, row['pid'])
        process.terminate.assert_not_called(); process.kill.assert_not_called()

    def test_failed_subprocess_remains_failed_even_with_a_pass_marker(self):
        output = self.root / 'run'
        def copy(repo, work):
            work.mkdir(); (work / 'joining-intent-result.json').write_text('{"status":"PASS"}')
            return dict(head='a' * 40, files={})
        with patch.object(h, 'source_copy', side_effect=copy), patch.object(h, 'execute', return_value=dict(exit=1)), \
             patch.object(h.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='test', stderr='')), \
             patch.object(h, 'junit') as report, patch.object(h, 'collection') as collect:
            with self.assertRaisesRegex(ValueError, 'Maven failed'): h.run(output, 'mvn')
            report.assert_not_called(); collect.assert_not_called()
        receipt = json.loads((output / 'receipt.json').read_text())
        self.assertEqual('FAIL', receipt['executionStatus']); self.assertEqual('FAIL', receipt['status'])
        self.assertFalse(receipt['nativeHistoryQualified'])
        self.assertTrue((output / 'workspace/joining-intent-result.json').exists())
        with self.assertRaises(FileExistsError): h.run(output, 'mvn')

    def minimal_collection(self):
        """Synthetic observations test collection only; no native semantic claim."""
        raw = self.root / 'raw'; raw.mkdir()
        events = [dict(node='node-4', scope=scope, event='OBSERVED') for scope in
            ('learner-plan', 'learner-admission', 'learner-materialization', 'pending-intent', 'published-intent',
             'voter-stage', 'custody', 'placement', 'joined-admission', 'retirement', 'initial-owner',
             'retaining-owner', 'repeated-basis-owner', 'continuation-owner')]
        events += [dict(node='node-4', scope='stable-cold-owner', event=event) for event in
                   ('FIXTURE_OPEN_RETURNED', 'FIXTURE_CLOSE_RETURNED')]
        events += [dict(node='node-1', event='JOINING_SLOT_' + phase, index=cut)
                   for phase in ('APPLIED', 'PUBLISHED', 'FUTURE_QUORUM_COMPLETE') for cut in (2, 3)]
        events += [dict(node='node-4', scope='continuation-endpoint', event='BEFORE_RESPONSE_WRITE')]
        for name, value in dict(events=events, wire=[{}], calls=[{}], failures=[]).items(): rawsave(raw / (name + '.json'), value)
        rawsave(raw / 'joining-intent-result.json', dict(status='PASS'))
        rawsave(raw / 'joining-continuation-result.json', dict(status='PASS', stableColdReopened=True, cut=dict(index=3)))
        groups = [f'{p}-{i}' for p in ('applied', 'published') for i in range(1, 4)]
        groups += ['before-network', 'before-joint-continuation', 'after-close', 'continuation-installed-1', 'continuation-installed-2']
        for group in groups:
            for node in ('node-1', 'node-2', 'node-3'):
                p = raw / group / node; p.mkdir(parents=True); (p / 'original').write_bytes(b'fixture')
        return raw

    def test_collection_stays_partial_and_missing_trace_does_not_reach_ledger_reader(self):
        raw = self.minimal_collection()
        # Snapshot format and semantic ledger replay have their own real-reader
        # tests; here only collection boundaries and refusal ordering are tested.
        with patch.object(h.snapshot, 'read'), patch.object(h.grants, 'validate', return_value={'status':'PARTIAL'}) as grants, \
                patch.object(h.retirements, 'validate', return_value={'status':'PARTIAL'}) as retirements, \
                patch.object(h.ledgers, 'validate', return_value={'status': 'PARTIAL'}) as ledger:
            result = h.collection(raw)
            self.assertEqual('PARTIAL', result['status']); self.assertTrue(result['collectionComplete'])
            self.assertFalse(result['nativeHistoryQualified']); self.assertFalse(result['phase3Complete'])
            grants.assert_called_once_with(raw, json.loads((raw/'events.json').read_bytes()), whole_history=True)
            retirements.assert_called_once_with(raw, json.loads((raw/'events.json').read_bytes()))
            ledger.assert_called_once_with(raw, confirmed_peers=True); ledger.reset_mock()
            rawsave(raw / 'events.json', [])
            with self.assertRaisesRegex(ValueError, 'traces missing'): h.collection(raw)
            ledger.assert_not_called()

    def test_missing_grants_stop_collection_before_ledger_validation(self):
        raw = self.minimal_collection()
        with patch.object(h.snapshot, 'read'), patch.object(h.ledgers, 'validate') as ledger:
            with self.assertRaisesRegex(ValueError, '^grant capture collection missing$'): h.collection(raw)
            ledger.assert_not_called()

    def test_missing_retirement_prefixes_stop_collection_before_ledger_validation(self):
        raw = self.minimal_collection()
        with patch.object(h.snapshot, 'read'), patch.object(h.grants,'validate'), patch.object(h.ledgers,'validate') as ledger:
            with self.assertRaisesRegex(ValueError, '^retirement capture collection missing$'): h.collection(raw)
            ledger.assert_not_called()

    def test_missing_snapshot_scope_or_cold_return_is_not_complete(self):
        raw = self.minimal_collection()
        with patch.object(h.snapshot, 'read'), patch.object(h.ledgers, 'validate') as ledger:
            original = (raw / 'events.json').read_bytes(); rows = json.loads(original)
            for scope, reason in [('continuation-owner', 'callback scope missing'), ('stable-cold-owner', 'cold observations missing')]:
                rawsave(raw / 'events.json', [v for v in rows if v.get('scope') != scope])
                with self.assertRaisesRegex(ValueError, reason): h.collection(raw)
            (raw / 'events.json').write_bytes(original)
            (raw / 'applied-2/node-1/original').unlink()
            with self.assertRaisesRegex(ValueError, 'snapshot missing'): h.collection(raw)
            ledger.assert_not_called()

    def test_preserves_execution_success_but_reports_collection_failure(self):
        output = self.root / 'run'
        def copy(repo, work):
            (work / h.MODULE / 'target/v53-native-dispatch/run-original').mkdir(parents=True)
            for p in ('target/classes', h.MODULE + '/target/classes', h.MODULE + '/target/test-classes'):
                (work / p).mkdir(parents=True)
            return dict(head='a' * 40, files={})
        with patch.object(h, 'source_copy', side_effect=copy), patch.object(h, 'execute', side_effect=[dict(exit=0), dict(exit=2)]) as execute, \
             patch.object(h.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='test', stderr='')), \
             patch.object(h, 'junit', return_value=dict(tests=1)):
            with self.assertRaisesRegex(ValueError, 'collection failed'): h.run(output, 'mvn')
        invocation = execute.call_args_list[1]
        self.assertEqual(output / 'workspace', invocation.args[1])
        self.assertEqual(['-m', 'scripts.v53.joining_history_run'], invocation.args[0][2:4])
        self.assertEqual('collection', invocation.kwargs['stage'])
        receipt = json.loads((output / 'receipt.json').read_text())
        self.assertEqual('PASS', receipt['executionStatus']); self.assertEqual('FAIL', receipt['status'])
        self.assertFalse(receipt['nativeHistoryQualified'])


if __name__ == '__main__': unittest.main()
