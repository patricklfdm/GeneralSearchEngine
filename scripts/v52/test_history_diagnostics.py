"""Failure-path qualification only: no JVM, cloud request or measurement retry."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stderr
from . import history_diagnostics as d, remote_history as h
from . import measurement_load as load

NAME = 'candidate-legacy-strong-r1'
SECRET = 'private-token-and-ssh-key-never-public'


def evidence(owner):
    h.runtime.save(owner.collected/'scenario.json', dict(stage='offered', leader='node-1', readTarget='node-1', secret=SECRET))
    h.runtime.save(owner.collected/'offered.json', dict(offers=[
        dict(status='DISPATCHED', completionStatus='OBSERVED', response={'secret':SECRET}),
        dict(status='DISPATCHED', completionStatus='UNOBSERVED', document={'secret':SECRET})]))
    owner.history.extend([dict(kind='read',node='node-1',outcome='INDETERMINATE',
                              response=dict(reasonCode='QUORUM_UNAVAILABLE',reason=SECRET)),
                          dict(kind='read',node='node-1',outcome='PENDING',query=SECRET)])


def observation_error():
    # Real assertion and traceback, with a counter embedded in the private text.
    load.validate(dict(durationNanos=1, failure=None, startNanos=0, offers=[], dispatchEndNanos=1,
                       drainStartNanos=1, drainEndNanos=2, unobserved=2), [], 1, [])


class DiagnosticTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.owner=h.Receivers(self.root/NAME, NAME, {})
    def run_failure(self, error=observation_error, close_error=None, preparation=False):
        def finish(failure):
            self.original_finish(failure)
            if close_error:raise close_error
        self.original_finish=self.owner.finish
        with patch.object(h, 'source', return_value={}), patch.object(self.owner, 'prepare', side_effect=error if preparation else None), \
             patch.object(self.owner, 'observe', side_effect=None if preparation else error) as observe, \
             patch.object(self.owner, 'finish', side_effect=finish) as close, patch.object(h.cohort,'replay_member') as replay:
            with self.assertRaises(BaseException) as caught:
                h.run(self.owner.root, NAME, {}, receiver_factory=lambda *args:self.owner)
            close.assert_called_once();replay.assert_not_called()
            self.assertEqual(0 if preparation else 1,observe.call_count)
        return caught.exception, d.report(self.root,NAME)
    def test_original_missing_responses_survive_close_and_retain_counts_and_check_site(self):
        evidence(self.owner)
        error,row=self.run_failure()
        self.assertIn('2 original responses missing',str(error))
        self.assertEqual('original-workload',row['stage'])
        self.assertEqual('ORIGINAL_RESPONSES_MISSING',row['failure']['reasonCode'])
        self.assertEqual('measurement_load',row['failure']['origin']['module'])
        self.assertEqual({'OBSERVED':1,'UNOBSERVED':1},row['observations']['offers']['completion'])
        self.assertEqual({'QUORUM_UNAVAILABLE':1,'NONE':1},row['observations']['calls']['reasons'])
        self.assertNotIn(SECRET,json.dumps(row));self.assertFalse(row['fullRemoteQualification'])
        self.assertEqual(row,d.project(row));self.assertLess((self.owner.root/d.FILE).stat().st_size,d.MAX_BYTES)
    def test_late_collection_exception_cannot_replace_original_execution_error(self):
        original,row=self.run_failure(close_error=OSError(SECRET))
        self.assertIsInstance(original,ValueError)
        self.assertEqual('original-workload',row['stage'])
        self.assertEqual('ORIGINAL_RESPONSES_MISSING',row['failure']['reasonCode'])
        self.assertEqual('IO_FAILED',row['cleanupFailure']['reasonCode'])
        self.assertNotIn(SECRET,json.dumps(row))
    def test_preparation_rejection_and_unknown_exception_remain_locatable_without_text(self):
        error,row=self.run_failure(lambda: (_ for _ in ()).throw(ValueError(SECRET)),preparation=True)
        self.assertEqual('preparation',row['stage']);self.assertEqual('VALIDATION_REJECTED',row['failure']['reasonCode'])
        self.assertNotIn(SECRET,json.dumps(row))
    def test_close_only_failure_is_not_mislabelled_as_workload_failure(self):
        _,row=self.run_failure(error=lambda:None,close_error=OSError(SECRET))
        self.assertEqual('receiver-close',row['stage']);self.assertEqual('IO_FAILED',row['failure']['reasonCode'])
    def test_replay_failure_retains_its_stage_and_original_validation_location(self):
        self.owner.binding={};h.runtime.save(self.owner.collected/'binding.json',{})
        with patch.object(h,'source',return_value={}), patch.object(self.owner,'prepare'), patch.object(self.owner,'observe'), \
             patch.object(h.cohort,'replay_member',side_effect=lambda *args:observation_error()):
            with self.assertRaises(ValueError):h.run(self.owner.root,NAME,{},receiver_factory=lambda *args:self.owner)
        row=d.report(self.root,NAME)
        self.assertEqual('physical-replay',row['stage']);self.assertEqual('measurement_load',row['failure']['origin']['module'])
    def test_diagnostic_write_failure_never_bypasses_finish_or_masks_exception(self):
        with patch.object(d.os,'open',side_effect=OSError(SECRET)),redirect_stderr(io.StringIO()) as output:
            error,row=self.run_failure()
        self.assertIn('original responses missing',str(error));self.assertIsNone(row)
        self.assertIn('v52HistoryDiagnosticRetention=FAIL',output.getvalue());self.assertNotIn(SECRET,output.getvalue())
    def test_failed_after_close_replacement_preserves_first_failure_atomically(self):
        replace=d.os.replace;calls=[]
        def write(source,target):
            calls.append(target)
            if len(calls)==2:raise OSError(SECRET)
            return replace(source,target)
        with patch.object(d.os,'replace',side_effect=write),redirect_stderr(io.StringIO()):
            error,row=self.run_failure()
        self.assertEqual(2,len(calls));self.assertIn('original responses missing',str(error))
        self.assertEqual('ORIGINAL_RESPONSES_MISSING',row['failure']['reasonCode'])
        self.assertEqual([],list(self.owner.root.glob('.history-diagnostic-*')))

    def test_unknown_dynamic_text_and_extra_fields_are_never_exported(self):
        evidence(self.owner);_,row=self.run_failure()
        row['secret']=SECRET;row['failure']['secret']=SECRET;row['observations']['offers']['raw']=SECRET
        self.assertNotIn(SECRET,json.dumps(d.project(row)))
        for message,expected in [(SECRET,'VALIDATION_REJECTED'),('measurement public call failed: '+SECRET,'PUBLIC_CALL_REJECTED')]:
            self.assertEqual(expected,d.exception(ValueError(message))['reasonCode'])
        self.owner.history[-1].update(response=dict(reasonCode=SECRET))
        self.assertEqual({'QUORUM_UNAVAILABLE':1,'OTHER':1},d.observations(self.owner)['calls']['reasons'])
    def test_malformed_or_oversized_context_does_not_hide_the_primary_error(self):
        (self.owner.collected/'scenario.json').write_bytes(b'{'*65537)
        private=self.root/'private';private.write_text(SECRET);(self.owner.collected/'offered.json').symlink_to(private)
        _,row=self.run_failure();self.assertEqual({'calls'},set(row['observations']))
        self.assertNotIn(SECRET,json.dumps(row))
    def test_report_rejects_missing_malformed_linked_oversized_or_mismatched_history(self):
        self.assertIsNone(d.report(self.root,NAME));_,row=self.run_failure();path=self.owner.root/d.FILE
        for bad in (b'{',b'x'*(d.MAX_BYTES+1),d.encoded(dict(row,history='candidate-minimum-r1'))):
            path.write_bytes(bad);self.assertIsNone(d.report(self.root,NAME))
        path.unlink();private=self.root/'private';private.write_bytes(d.encoded(row));path.symlink_to(private)
        self.assertIsNone(d.report(self.root,NAME));self.assertIsNone(d.report(self.root,'../private'))
    def test_symlink_output_is_not_overwritten(self):
        private=self.root/'private';private.write_text(SECRET);(self.owner.root/d.FILE).symlink_to(private)
        with redirect_stderr(io.StringIO()):error,row=self.run_failure()
        self.assertIsNone(row);self.assertEqual(SECRET,private.read_text());self.assertIsInstance(error,ValueError)
    def test_project_rejects_forged_codes_counts_or_qualification(self):
        evidence(self.owner);_,original=self.run_failure()
        mutations=[lambda v:v.update(fullRemoteQualification=True),lambda v:v.update(history='../private'),
            lambda v:v.update(stage=SECRET),lambda v:v['failure'].update(reasonCode=SECRET),
            lambda v:v['failure'].update(errorType=SECRET),lambda v:v['failure']['origin'].update(module=SECRET),
            lambda v:v['failure']['origin'].update(line=True),lambda v:v['observations']['offers'].update(total=999999),
            lambda v:v['observations']['offers']['completion'].update(OBSERVED=2),
            lambda v:v['observations']['calls'].update(truncated='false'),
            lambda v:v.update(closure={'processes':[dict(node='node-1',generation=1,exitCode=SECRET)]})]
        for mutate in mutations:
            row=deepcopy(original);mutate(row);self.assertIsNone(d.project(row))
    def test_stopped_workers_and_close_errors_are_bounded_and_sanitized(self):
        worker=Mock(node='node-1',generation=1,identity={'secret':SECRET});worker.proc.pid=123;worker.proc.returncode=-9
        worker.stop.side_effect=TimeoutError(SECRET);self.owner.workers['node-1']=worker
        _,row=self.run_failure()
        self.assertEqual([dict(node='node-1',generation=1,exitCode=-9)],row['closure']['processes'])
        self.assertEqual('TIMEOUT',row['closure']['closeErrors'][0]['reasonCode']);self.assertNotIn(SECRET,json.dumps(row))


if __name__=='__main__':unittest.main()
