import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from . import guest_session_recovery as r, guest_transport as t, cloud_runner_iap as iap


class PreparationFixtureTest(unittest.TestCase):
    def test_ssh_fixture_can_create_and_query_the_original_session(self):
        from . import guest_preparation_connections_qualification as q
        value,claim=q.session_fixture()
        expected=dict(state='SUCCEEDED',sessionSha256=q.m.sha(q.m.canonical(claim)))
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)/'package'
            self.assertEqual({'state':'NOT_FOUND'},q.session.observe(base,claim,value))
            self.assertEqual(expected,q.session.begin(base,claim,value))
            self.assertEqual(expected,q.session.observe(base,claim,value))
            before=(base.parent/'native-session/request.json').read_bytes()
            self.assertEqual(expected,q.session.begin(base,claim,value))
            self.assertEqual(before,(base.parent/'native-session/request.json').read_bytes())


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.now=100.;self.report={};self.actions=[];self.deadlines=[]
        self.expected=dict(state='SUCCEEDED',sessionSha256='a'*64)

    def run_sequence(self, sequence, *, deadline=1900, duration=0):
        values=iter(sequence)
        def exchange(action,until):
            self.actions.append(action);self.deadlines.append(until);self.now+=duration
            value=next(values)
            if isinstance(value,Exception):raise value
            return value
        def sleep(seconds):self.now+=seconds
        return r.initialize(exchange,self.expected,deadline,self.report,clock=lambda:self.now,sleep=sleep)

    def test_lost_reply_queries_committed_session_without_resubmitting(self):
        self.assertEqual(self.expected,self.run_sequence([t.ProcessError('SSH_DISCONNECTED'),self.expected]))
        self.assertEqual(['begin','query'],self.actions)
        self.assertEqual('PASS',self.report['status'])

    def test_missing_session_after_failed_send_retries_exact_begin(self):
        self.assertEqual(self.expected,self.run_sequence([t.ProcessError('SSH_MASTER_CLOSED'),{'state':'NOT_FOUND'},self.expected]))
        self.assertEqual(['begin','query','begin'],self.actions)
        self.assertEqual(2,self.report['begins'])

    def test_permission_host_key_and_remote_exit_fail_on_first_exchange(self):
        for code in sorted(set(t.FAILURE_DETAILS)-t.TRANSIENT):
            self.setUp()
            with self.subTest(code=code),self.assertRaises(r.RecoveryError) as caught:
                self.run_sequence([t.ProcessError(code)])
            self.assertEqual(code,caught.exception.code);self.assertEqual(['begin'],self.actions)

    def test_unknown_errors_and_authority_drift_are_terminal_and_redacted(self):
        for error in (ConnectionError('secret'),ValueError('lease changed secret'),OSError('secret')):
            self.setUp()
            with self.assertRaises(r.RecoveryError) as caught:self.run_sequence([error])
            self.assertEqual('SESSION_REJECTED',caught.exception.code)
            self.assertEqual(['begin'],self.actions);self.assertNotIn('secret',json.dumps(self.report))

    def test_three_transient_failures_fail_early_even_after_successful_not_found_query(self):
        with self.assertRaises(r.RecoveryError) as caught:
            self.run_sequence([t.ProcessError('SSH_DISCONNECTED'),{'state':'NOT_FOUND'},
                t.ProcessError('SSH_DISCONNECTED'),{'state':'NOT_FOUND'},t.ProcessError('SSH_DISCONNECTED')])
        self.assertEqual('SESSION_RETRY_LIMIT',caught.exception.code)
        self.assertEqual(3,self.report['transientFailures']);self.assertLess(self.now,120)

    def test_torn_claim_gets_bounded_queries_and_is_never_recreated(self):
        with self.assertRaises(r.RecoveryError) as caught:self.run_sequence([{'state':'UNCERTAIN'}]*3)
        self.assertEqual('SESSION_UNCERTAIN',caught.exception.code)
        self.assertEqual(['begin','query','query'],self.actions);self.assertLess(self.now,110)

    def test_pending_claim_can_complete_without_resubmitting(self):
        self.assertEqual(self.expected,self.run_sequence([{'state':'UNCERTAIN'},self.expected]))
        self.assertEqual(['begin','query'],self.actions)

    def test_timeouts_query_and_repeated_timeouts_stop_at_threshold(self):
        with self.assertRaises(r.RecoveryError) as caught:self.run_sequence([TimeoutError('private')]*3,duration=30)
        self.assertEqual('SESSION_RETRY_LIMIT',caught.exception.code)
        self.assertEqual(['begin','query','query'],self.actions)
        self.assertLess(self.now,220);self.assertNotIn('private',json.dumps(self.report))

    def test_original_shorter_deadline_cannot_renew_on_retry(self):
        with self.assertRaises(r.RecoveryError) as caught:
            self.run_sequence([t.ProcessError('SSH_DISCONNECTED')],deadline=101,duration=1)
        self.assertEqual('SESSION_RECOVERY_DEADLINE',caught.exception.code)
        self.assertEqual([101],self.deadlines);self.assertEqual(['begin'],self.actions)

    def test_late_success_is_rejected_and_exchange_has_short_budget(self):
        with self.assertRaises(r.RecoveryError) as caught:self.run_sequence([self.expected],duration=31)
        self.assertEqual('SESSION_RECOVERY_DEADLINE',caught.exception.code)
        self.assertEqual([130],self.deadlines)

    def test_progress_does_not_renew_total_recovery_deadline(self):
        with self.assertRaises(r.RecoveryError) as caught:
            self.run_sequence([t.ProcessError('SSH_DISCONNECTED'),{'state':'NOT_FOUND'},
                t.ProcessError('SSH_DISCONNECTED'),{'state':'UNCERTAIN'},self.expected],duration=25)
        self.assertEqual('SESSION_RECOVERY_DEADLINE',caught.exception.code)
        self.assertEqual(220,self.report['deadlineNanos']/1e9)
        self.assertEqual(220,self.deadlines[-1])

    def test_malformed_or_foreign_receipt_is_terminal(self):
        for value in ({'state':'SUCCEEDED','sessionSha256':'b'*64},{'state':'UNCERTAIN','extra':'secret'},
                      {'state':'FAILED'},None,[],{'state':'NOT_FOUND'}):
            self.setUp()
            # None is not a valid wire state, even though it is the internal lost-reply sentinel.
            with self.subTest(value=value),self.assertRaises(r.RecoveryError):self.run_sequence([value])
            self.assertEqual(['begin'],self.actions)


class ClassificationTest(unittest.TestCase):
    def test_receiver_rejections_keep_only_closed_codes_and_remain_terminal(self):
        for reason, code in t.RECEIVER_REJECTIONS.items():
            with self.subTest(code=code):
                # Real Python traceback, including private diagnostic text that
                # must never enter an exception or the native admission evidence.
                with self.assertRaises(t.ProcessError) as caught:
                    t.process([sys.executable, '-c',
                        'import sys;sys.stderr.write("private-secret\\n");raise ValueError('+repr(reason)+')'],
                        b'', time.monotonic()+5)
                self.assertEqual(code, caught.exception.code)
                self.assertFalse(caught.exception.retryable)
                self.assertNotIn('private-secret', str(caught.exception))
                with self.assertRaises(t.ProcessRejected) as native:
                    with iap._sanitized(False): raise caught.exception
                self.assertEqual(code, native.exception.code)
                self.assertNotIsInstance(native.exception, ConnectionError)
                raw = ('Traceback (most recent call last):\nprivate-secret\nValueError: '+reason+'\n').encode()
                self.assertEqual(code, t.exit_error(1, raw, ssh=True).code)

    def test_unknown_or_embedded_receiver_reason_cannot_qualify_specific_rejection(self):
        exact = b'ValueError: root metadata identity'
        for raw in (exact+b'\n', b'Traceback (most recent call last):\n'+exact+b' private-secret\n',
                    b'Traceback (most recent call last):\n'+exact+b'\nRuntimeError: unrelated\n',
                    b'Traceback (most recent call last):\nRuntimeError: root metadata identity\n'):
            for ssh, expected in ((False, 'LOCAL_PROCESS_EXIT'), (True, 'REMOTE_EXIT')):
                with self.subTest(raw=raw, ssh=ssh):
                    error = t.exit_error(1, raw, ssh=ssh)
                    self.assertEqual(expected, error.code)
                    self.assertFalse(error.retryable)
                    self.assertNotIn('private-secret', str(error))

    def test_receiver_reason_cannot_override_signal_or_ssh_connection_exit(self):
        raw = b'Traceback (most recent call last):\nValueError: root metadata identity\n'
        self.assertEqual('LOCAL_PROCESS_EXIT', t.exit_error(-9, raw, ssh=False).code)
        self.assertEqual('REMOTE_EXIT', t.exit_error(7, raw, ssh=True).code)
        self.assertEqual('SSH_UNCLASSIFIED', t.exit_error(255, raw, ssh=True).code)
        self.assertEqual('SSH_AUTHENTICATION', t.exit_error(255, b'Permission denied (publickey).\n'+raw, ssh=True).code)

    def test_remote_python_error_is_not_transient_even_if_text_mentions_connection(self):
        error=t.exit_error(1,b'Traceback: Connection closed secret',ssh=True)
        self.assertEqual('REMOTE_EXIT',error.code);self.assertFalse(error.retryable)
        self.assertNotIn('secret',str(error))

    def test_denial_beats_connection_closed_and_unknown_is_terminal(self):
        for diagnostic,code in [(b'Permission denied (publickey). Connection closed', 'SSH_AUTHENTICATION'),
                               (b'REMOTE HOST IDENTIFICATION HAS CHANGED! Broken pipe','SSH_HOST_KEY'),
                               (b'PERMISSION_DENIED: 403; Connection closed','IAP_PERMISSION'),
                               (b'unrecognized secret failure','SSH_UNCLASSIFIED')]:
            error=t.exit_error(255,diagnostic,ssh=True)
            self.assertEqual(code,error.code);self.assertFalse(error.retryable)
            with self.assertRaises(t.ProcessRejected) as caught:
                with iap._sanitized(False):raise error
            self.assertEqual(code,caught.exception.code);self.assertNotIn('secret',str(caught.exception))
            self.assertNotIsInstance(caught.exception,ConnectionError)

    def test_actual_child_exit_is_bounded_and_does_not_retain_stderr(self):
        with self.assertRaises(t.ProcessError) as caught:
            t.process([sys.executable,'-c','import sys;sys.stderr.write("private-secret");sys.exit(1)'],b'',time.monotonic()+5)
        self.assertEqual('LOCAL_PROCESS_EXIT',caught.exception.code)
        self.assertNotIn('private-secret',str(caught.exception))

    def test_child_that_closes_pipes_but_does_not_exit_is_a_bounded_timeout(self):
        with self.assertRaises(TimeoutError):
            t.process([sys.executable,'-c','import os,time;os.close(1);os.close(2);time.sleep(60)'],
                      b'',time.monotonic()+.2)


if __name__=='__main__':unittest.main()
