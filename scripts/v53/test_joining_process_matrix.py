"""Synthetic provenance/orchestration coverage; never native qualification."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from . import joining_process_matrix as m
from . import test_joining_process_run as fixture
from .test_process_toolchain import record


def qualification(case):
    prior = dict(case=case, originalPhysicalHistoryVerified=True, observedTransportVerified=True,
                 durableACKsVerified=True, processDeathQualified=False, phase3Complete=False)
    original = dict(case=case, status='PARTIAL', scope='original-joining-process-export-control-and-maintenance',
                    exportControlAuthorityVerified=True, maintenanceAuthorityVerified=True,
                    continuousLedgersQualified=True, ballotCompositionVerified=True,
                    phase3Complete=False, processDeathQualified=False, precondition=prior,
                    exports=dict(boundSessions={'pending-joining-checkpoint': 1}), joiningLearnerWrites=1)
    absent = m.gate.negative_plan(original)
    return dict(authority=dict(status='PASS', original=original, originalPreserved=True, completeNegativeCatalogue=True,
                               phase3Complete=False, processDeathQualified=False,
                               negatives=[dict(case=k, status='NOT_APPLICABLE' if k in absent else 'REJECTED', reason=absent.get(k, v))
                                          for k, v in m.gate.NEGATIVES.items()]),
                physical=dict(original=prior, originalPreserved=True, negatives=m.expected_negatives(m.physical.NEGATIVES)),
                transactionNegatives=m.expected_negatives(m.physical.transaction.NEGATIVES))


class JoiningProcessMemberTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.case = '3-ADD,JOINING_RETENTION_SEED_PREFIX_WRITTEN,halt'
        self.path = self.root/'producer'; work = self.path/'workspace'; work.mkdir(parents=True)
        (work/'reader.py').write_bytes(b'original reader')
        self.reader = dict(files={'reader.py': m.h.digest(b'original reader')}, sha256='f'*64)
        patched = patch.object(m, 'reader_manifest', return_value=self.reader); patched.start(); self.addCleanup(patched.stop)
        m.h.save(self.path/'source.json', dict(head='a'*40, files=self.reader['files']))
        for name in m.BUILDS:
            directory = work/name; directory.mkdir(parents=True); (directory/'original.class').write_bytes(b'compiled original')
        m.h.save(self.path/'build.json', {name: m.h.inventory(work/name) for name in m.BUILDS})
        m.h.save(self.path/'toolchain.json', record()); reports = work/m.h.MODULE/'target/surefire-reports'; reports.mkdir()
        suite = ET.Element('testsuite', dict(name=m.run.CLASS, tests='1', failures='0', errors='0', skipped='0'))
        ET.SubElement(suite, 'testcase', dict(classname=m.run.CLASS, name=m.run.METHOD)); ET.ElementTree(suite).write(reports/'TEST-original.xml')
        helper = fixture.JoiningProcessRunTest(); helper.setUp(); self.addCleanup(helper.doCleanups)
        self.raw = work/m.h.MODULE/'target/v53-native-dispatch/run-00000000-0000-0000-0000-000000000001'
        shutil.copytree(helper.raw(), self.raw); (self.raw/'original-plan.gsbp').write_bytes(b'original plan')
        m.h.save(self.path/'collection.json', m.run.collect(self.raw, self.case))
        m.h.save(self.path/'execution.json', dict(exit=0))
        m.h.save(self.path/'receipt.json', dict(schema=m.run.SCHEMA, status='PARTIAL', executionStatus='PASS', case=self.case,
            collectionComplete=True, physicalHistoryQualified=False, processDeathQualified=False, phase3Complete=False, retries=0,
            execution=dict(exit=0), baseHead='a'*40, command=['mvn', *m.run.command(self.case)], junit=m.run.junit(reports, self.case),
            raw=self.raw.relative_to(self.path).as_posix(), **{key+'Sha256': m.h.digest((self.path/file).read_bytes()) for key, file in
            (('source', 'source.json'), ('build', 'build.json'), ('toolchain', 'toolchain.json'), ('collection', 'collection.json'))}))
        self.pins = [m.h.digest((self.path/name).read_bytes()) for name in ('source.json', 'build.json')]+[
            m.process_toolchain.pin((self.path/'toolchain.json').read_bytes()), self.reader['sha256']]

    def receipt(self, **changes):
        value = m.read(self.path/'receipt.json'); value.update(changes); m.h.save(self.path/'receipt.json', value)

    def member(self, path=None): return m.member(path or self.path, self.case, *self.pins)

    def test_collection_provenance_is_portable_but_does_not_qualify_physical_history(self):
        before = self.member(); copied = self.root/'relocated'; shutil.copytree(self.path, copied)
        after = self.member(copied)
        self.assertEqual({k:v for k,v in before.items() if k != 'raw'}, {k:v for k,v in after.items() if k != 'raw'})
        with self.assertRaises((ValueError, FileNotFoundError)): m.gate.validate(before['raw'], self.case)

    def test_forged_status_command_retry_junit_and_execution_reject(self):
        original = m.read(self.path/'receipt.json')
        for change in (dict(status='PASS'), dict(retries=False), dict(retries=1), dict(phase3Complete=True),
                       dict(processDeathQualified=True), dict(collectionComplete=1), dict(command=['mvn', 'test']),
                       dict(junit={}), dict(execution=dict(exit=False)), dict(case=m.KINDS[0])):
            self.receipt(**dict(original, **change))
            with self.subTest(change=change), self.assertRaises(ValueError): self.member()
        self.receipt(**original); m.h.save(self.path/'execution.json', dict(exit=False))
        with self.assertRaisesRegex(ValueError, 'original execution'): self.member()

    def test_source_build_toolchain_and_reader_drift_reject(self):
        for path in (self.path/'workspace/reader.py', self.path/'workspace/target/classes/original.class', self.path/'toolchain.json'):
            before = path.read_bytes(); path.write_bytes(b'changed')
            with self.subTest(path=path), self.assertRaises(ValueError): self.member()
            path.write_bytes(before)
        self.reader['files']['reader.py'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'reader belongs to producer source'): self.member()

    def test_junit_skips_failures_retries_and_boolean_receipt_reject(self):
        report = self.path/'workspace'/m.h.MODULE/'target/surefire-reports/TEST-original.xml'; before = report.read_bytes()
        for tag in ('error', 'failure', 'skipped', 'flakyFailure', 'flakyError', 'rerunFailure', 'rerunError'):
            suite = ET.fromstring(before); ET.SubElement(suite[0], tag); ET.ElementTree(suite).write(report)
            with self.subTest(tag=tag), self.assertRaisesRegex(ValueError, 'unretried test'): self.member()
        report.write_bytes(before); value = m.read(self.path/'receipt.json')['junit']; value['tests'] = True; self.receipt(junit=value)
        with self.assertRaisesRegex(ValueError, 'exact JUnit receipt'): self.member()

    def test_changed_process_is_recollected_despite_refreshed_inventory(self):
        value = m.read(self.raw/'joining-process/result.json'); value['children'][1]['pid'] = 1
        m.h.save(self.raw/'joining-process/result.json', value)
        collection = m.read(self.path/'collection.json'); collection['inventory'] = m.h.inventory(self.raw)
        m.h.save(self.path/'collection.json', collection); self.receipt(collectionSha256=m.h.digest((self.path/'collection.json').read_bytes()))
        with self.assertRaisesRegex(ValueError, 'distinct children'): self.member()

    def test_escaping_or_linked_history_and_duplicate_metadata_reject(self):
        original = m.read(self.path/'receipt.json'); self.receipt(raw='../escape')
        with self.assertRaisesRegex(ValueError, 'original history path'): self.member()
        self.receipt(**original); moved = self.root/'moved'; self.raw.rename(moved); self.raw.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(ValueError): self.member()
        (self.path/'receipt.json').write_text('{"status":"PASS","status":"PARTIAL"}')
        with self.assertRaisesRegex(ValueError, 'duplicate metadata'): self.member()

    def test_extra_original_directory_and_linked_build_parent_reject(self):
        extra = self.raw.parent/'unexpected'; extra.mkdir()
        with self.assertRaisesRegex(ValueError, 'exact original directory'): self.member()
        extra.rmdir(); classes = self.path/'workspace/target/classes'; moved = self.root/'classes'
        classes.rename(moved); classes.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'linked generated parent'): self.member()

    def test_complete_member_calls_all_readers_and_rechecks_original(self):
        result = qualification(self.case)
        with patch.object(m.gate, 'qualify', return_value=result['authority']) as authority, \
             patch.object(m.physical, 'qualify', return_value=result['physical']) as physical, \
             patch.object(m.physical.transaction, 'negatives', return_value=result['transactionNegatives']) as transaction:
            actual = m.qualify_member(self.path, self.case, *self.pins)
        authority.assert_called_once_with(self.raw, self.case, workers=1, progress=None)
        physical.assert_called_once_with(self.raw, self.case, progress=None); transaction.assert_called_once_with(self.raw, self.case)
        self.assertEqual('PASS', actual['status']); self.assertFalse(actual['phase3Complete'])
        self.assertFalse(actual['declaredJoiningProcessMatrixQualified'])

    def test_original_failure_or_partial_negatives_prevents_later_qualification(self):
        for outcome in ('failure', 'PARTIAL'):
            kwargs = dict(side_effect=ValueError('bad original')) if outcome == 'failure' else dict(return_value=dict(status='PARTIAL'))
            with patch.object(m.gate, 'qualify', **kwargs), patch.object(m.physical, 'qualify') as following, self.assertRaises(ValueError):
                m.qualify_member(self.path, self.case, *self.pins)
            following.assert_not_called()

    def test_parallel_negatives_keep_the_complete_catalogue_and_all_following_gates(self):
        result = qualification(self.case)
        with patch.object(m.gate, 'qualify', return_value=result['authority']) as authority, \
             patch.object(m.physical, 'qualify', return_value=result['physical']) as physical, \
             patch.object(m.physical.transaction, 'negatives', return_value=result['transactionNegatives']) as transaction:
            actual = m.qualify_member(self.path, self.case, *self.pins, negative_workers=3)
        authority.assert_called_once_with(self.raw, self.case, workers=3, progress=None)
        physical.assert_called_once_with(self.raw, self.case, progress=None); transaction.assert_called_once_with(self.raw, self.case)
        self.assertEqual(result, actual['qualification'])
        for workers in (0,4,True,1.5):
            with self.subTest(workers=workers),patch.object(m, 'member') as read,self.assertRaisesRegex(ValueError,'negative workers'):
                m.qualify_member(self.path,self.case,*self.pins,negative_workers=workers)
            read.assert_not_called()

    def test_replay_cannot_change_original_receipt(self):
        result = qualification(self.case)
        def mutate(*_):
            self.receipt(note='changed during qualification'); return result['transactionNegatives']
        with patch.object(m.gate, 'qualify', return_value=result['authority']), \
             patch.object(m.physical, 'qualify', return_value=result['physical']), \
             patch.object(m.physical.transaction, 'negatives', side_effect=mutate), \
             self.assertRaisesRegex(ValueError, 'producer changed during replay'):
            m.qualify_member(self.path, self.case, *self.pins)

    def test_replay_cannot_switch_reader_version(self):
        result = qualification(self.case)
        def mutate(*_):
            self.reader['sha256'] = '0'*64; return result['transactionNegatives']
        with patch.object(m.gate, 'qualify', return_value=result['authority']), \
             patch.object(m.physical, 'qualify', return_value=result['physical']), \
             patch.object(m.physical.transaction, 'negatives', side_effect=mutate), \
             self.assertRaisesRegex(ValueError, 'pinned reader'):
            m.qualify_member(self.path, self.case, *self.pins)


class JoiningProcessMatrixTest(unittest.TestCase):
    def test_connected_original_requires_its_exact_negative_catalogue(self):
        value=qualification(m.KINDS[0]);prior=value['physical']['original']
        prior['transportFormat']='connections'
        value['authority']['original']['precondition']=prior
        with self.assertRaisesRegex(ValueError,'exact physical negatives'):m.check_result(value,m.KINDS[0])
        value['physical']['negatives']=m.expected_negatives(m.physical.negative_reasons('connections'))
        m.check_result(value,m.KINDS[0])
        prior['transportFormat']='unknown'
        with self.assertRaisesRegex(ValueError,'transport format'):m.check_result(value,m.KINDS[0])

    def setUp(self):
        self.pins = ['a'*64, 'b'*64, 'c'*64, 'd'*64]
        self.paths = {case: Path('/synthetic')/m.slug(case) for case in m.KINDS}

    def original(self, path, case, *pins):
        return dict(raw=path, plan=m.h.digest(case.encode()), receiptSha256='e'*64)

    def qualified(self, path, case, *pins): return dict(case=case, status='PASS', phase3Complete=False)

    def matrix(self, paths=None, qualifier=None, observer=None, workers=4):
        with patch.object(m, 'check_pins'), patch.object(m, 'member', side_effect=observer or self.original), \
             patch.object(m, 'qualify_member', side_effect=qualifier or self.qualified), patch.object(m, 'ProcessPoolExecutor', ThreadPoolExecutor):
            return m.validate(self.paths if paths is None else paths, *self.pins, workers=workers)

    def test_catalogue_contains_every_whole_profile_cut_mode_and_all_150_negatives(self):
        self.assertEqual(360, len(m.KINDS)); self.assertEqual(360, len(set(m.KINDS)))
        self.assertEqual(360, len({m.slug(v) for v in m.KINDS}))
        for profile in m.run.profiles.PROFILES:
            for point in m.run.POINTS:
                for mode in ('halt', 'kill'): self.assertIn(','.join((profile, point, mode)), m.KINDS)
        self.assertEqual(150, len(m.gate.NEGATIVES)+len(m.physical.NEGATIVES)+len(m.physical.transaction.NEGATIVES))
        for case in m.KINDS: m.check_result(qualification(case), case)

    def test_all_360_members_are_replayed_once_and_scope_is_not_phase_closure(self):
        calls = []
        def qualified(path, case, *pins): calls.append(case); return self.qualified(path, case, *pins)
        result = self.matrix(qualifier=qualified)
        self.assertCountEqual(m.KINDS, calls); self.assertEqual('PASS', result['status'])
        self.assertTrue(result['declaredJoiningProcessMatrixQualified']); self.assertEqual(360, result['wholeHistories'])
        self.assertFalse(result['allMembershipProfilesQualified']); self.assertFalse(result['phase3Complete'])

    def test_missing_extra_aliased_and_duplicate_histories_fail_before_replay(self):
        case = m.KINDS[0]
        for paths in ({k:v for k,v in self.paths.items() if k != case}, dict(self.paths, extra=Path('/extra')),
                      dict(self.paths, **{m.KINDS[1]: self.paths[case]})):
            with self.subTest(count=len(paths)), self.assertRaises(ValueError): self.matrix(paths)
        def copied(path, case, *pins): return dict(raw=path, plan='e'*64)
        with self.assertRaisesRegex(ValueError, 'distinct original histories'): self.matrix(observer=copied)

    def test_failed_member_is_retained_without_retry_or_skipping_other_359(self):
        calls = []
        def qualified(path, case, *pins):
            calls.append(case)
            if case == m.KINDS[0]: raise ValueError('original physical failure')
            return self.qualified(path, case, *pins)
        result = self.matrix(qualifier=qualified)
        self.assertCountEqual(m.KINDS, calls); self.assertEqual('FAIL', result['status'])
        self.assertEqual(359, sum(v['status'] == 'PASS' for v in result['cases']))
        self.assertEqual('original physical failure', result['cases'][0]['failure']['message'])
        self.assertFalse(result['declaredJoiningProcessMatrixQualified'])

    def test_prior_member_change_is_detected_at_final_inventory_pass(self):
        count = 0
        def observed(path, case, *pins):
            nonlocal count
            count += 1
            value = self.original(path, case, *pins)
            if count > len(m.KINDS): value['receiptSha256'] = 'changed'
            return value
        with self.assertRaisesRegex(ValueError, 'changed before completion'): self.matrix(observer=observed)

    def test_incomplete_wrong_reason_wrong_original_and_false_absence_reject(self):
        case = m.KINDS[0]
        for kind in ('subset', 'reason', 'physical', 'transaction', 'scope', 'prior', 'absence', 'duplicate'):
            value = qualification(case)
            if kind == 'subset': value['authority']['negatives'].pop()
            elif kind == 'reason': value['authority']['negatives'][0]['reason'] = 'unrelated failure'
            elif kind == 'physical': value['physical']['negatives'].pop()
            elif kind == 'transaction': value['transactionNegatives'].pop()
            elif kind == 'scope': value['authority']['original']['phase3Complete'] = True
            elif kind == 'prior': value['physical']['original'] = dict(other='different history')
            elif kind == 'absence': value['authority']['negatives'][0]['status'] = 'NOT_APPLICABLE'
            else: value['authority']['negatives'].append(value['authority']['negatives'][0])
            with self.subTest(kind=kind), self.assertRaises(ValueError): m.check_result(value, case)

    def test_explicit_original_absences_require_exact_reasons_and_reject_false_skips(self):
        case = '5-REPLACE,JOINING_RETENTION_DONE_RENAMED,kill'; value = qualification(case)
        original = value['authority']['original']; original['exports']['boundSessions'] = {}; original['joiningLearnerWrites'] = 0
        absent = m.gate.negative_plan(original)
        value['authority']['negatives'] = [dict(case=k, status='NOT_APPLICABLE' if k in absent else 'REJECTED', reason=absent.get(k, v))
                                           for k,v in m.gate.NEGATIVES.items()]
        self.assertEqual(3, len(absent)); m.check_result(value, case)
        original['joiningLearnerWrites'] = 1
        with self.assertRaisesRegex(ValueError, 'exact authority negatives'): m.check_result(value, case)

    def test_boolean_and_negative_absence_observations_are_not_counts(self):
        for field in ('joiningLearnerWrites', 'pending'):
            for count in (False, -1, '0'):
                value = qualification(m.KINDS[0]); original = value['authority']['original']
                if field == 'pending': original['exports']['boundSessions']['pending-joining-checkpoint'] = count
                else: original[field] = count
                with self.subTest(field=field, count=count), self.assertRaisesRegex(ValueError, 'original absence observations'):
                    m.check_result(value, m.KINDS[0])

    def test_invalid_pins_workers_and_case_reject(self):
        for i in range(4):
            pins = list(self.pins); pins[i] = 'master'
            with self.assertRaisesRegex(ValueError, 'pinned hashes'): m.check_pins(*pins)
        with patch.object(m, 'reader_manifest', return_value=dict(sha256='e'*64)):
            with self.assertRaisesRegex(ValueError, 'pinned reader'): m.check_pins(*self.pins)
        for workers in (0, 5, True, 1.5):
            with self.assertRaisesRegex(ValueError, 'replay workers'): self.matrix(workers=workers)
        with self.assertRaisesRegex(ValueError, 'exact case'): m.slug('3-ADD,FOREIGN,halt')

    def test_failed_cli_retains_receipt_without_overwriting_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'result'
            args = ['matrix', 'member', str(output), '--producer', 'original', '--case', m.KINDS[0]]
            for name, value in zip(('source', 'build', 'toolchain', 'reader'), self.pins): args += ['--'+name+'-sha256', value]
            with patch('sys.argv', args), patch.object(m, 'qualify_member', side_effect=ValueError('bad original')), self.assertRaises(ValueError): m.main()
            self.assertEqual('FAIL', m.read(output/'receipt.json')['status']); before = (output/'receipt.json').read_bytes()
            with patch('sys.argv', args), self.assertRaises(FileExistsError): m.main()
            self.assertEqual(before, (output/'receipt.json').read_bytes())


if __name__ == '__main__': unittest.main()
