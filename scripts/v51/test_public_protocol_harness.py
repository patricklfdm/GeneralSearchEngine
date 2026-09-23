"""Recovery role hints cannot replace a successful, independently checked read."""
from concurrent.futures import Future
import unittest
from unittest.mock import Mock, patch
from . import public_protocol_harness as protocol


class PublicProtocolRecoveryReadTest(unittest.TestCase):
    def setUp(self):
        self.expected = [dict(id=10, value='seed')]
        self.success = dict(outcome='SUCCESS', documents=self.expected)
        leader = patch.object(protocol.fault, 'leader')
        self.leader = leader.start(); self.addCleanup(leader.stop)

    def worker(self, *responses):
        futures = []
        for response in responses:
            future = Future()
            if isinstance(response, Exception): future.set_exception(response)
            else: future.set_result(response)
            futures.append(future)
        return Mock(send=Mock(side_effect=futures))

    def read(self, worker):
        self.leader.return_value = ('node-3', worker)
        return protocol.read_after_recovery({'node-3': worker}, self.expected)

    def test_ci_quorum_rejection_rechecks_leader_before_reading_again(self):
        first = self.worker(dict(outcome='NOT_APPLICABLE', reasonCode='QUORUM_UNAVAILABLE'))
        next_leader = self.worker(self.success)
        workers = {'node-3': first, 'node-2': next_leader}
        self.leader.side_effect = [('node-3', first), ('node-2', next_leader)]
        self.assertEqual(('node-2', next_leader), protocol.read_after_recovery(workers, self.expected))
        self.assertEqual(2, self.leader.call_count)
        first.send.assert_called_once_with('read')
        next_leader.send.assert_called_once_with('read')

    def test_classified_availability_rejections_can_recover(self):
        for reason in ('NOT_LEADER', 'NOT_READY', 'QUORUM_UNAVAILABLE', 'STALE_EPOCH', 'DEADLINE_EXCEEDED'):
            with self.subTest(reason=reason):
                worker = self.worker(dict(outcome='NOT_APPLICABLE', reasonCode=reason), self.success)
                self.assertEqual(('node-3', worker), self.read(worker))
                self.assertEqual(['read', 'read'], [call.args[0] for call in worker.send.call_args_list])

    def test_persistent_unavailability_fails_after_four_reads(self):
        worker = self.worker(*[dict(outcome='NOT_APPLICABLE', reasonCode='QUORUM_UNAVAILABLE') for _ in range(4)], self.success)
        with self.assertRaisesRegex(ValueError, 'did not stabilize.*QUORUM_UNAVAILABLE'): self.read(worker)
        self.assertEqual(4, worker.send.call_count)

    def test_success_with_wrong_projection_fails_without_retry(self):
        worker = self.worker(dict(outcome='SUCCESS', documents=[]), self.success)
        with self.assertRaisesRegex(ValueError, 'projection changed'): self.read(worker)
        worker.send.assert_called_once_with('read')

    def test_integrity_storage_capacity_and_unknown_failures_are_not_retried(self):
        for reason in ('INTEGRITY_FAILURE', 'STORAGE_FAILURE', 'CAPACITY_EXCEEDED', 'CLOSED', 'unknown', None):
            with self.subTest(reason=reason):
                worker = self.worker(dict(outcome='NOT_APPLICABLE', reasonCode=reason), self.success)
                with self.assertRaisesRegex(ValueError, 'unexpected public protocol read failure'): self.read(worker)
                worker.send.assert_called_once_with('read')

    def test_wrong_or_missing_outcome_is_not_retried(self):
        for outcome in ('INDETERMINATE', 'NOT_SUBMITTED', 'PENDING', None):
            with self.subTest(outcome=outcome):
                worker = self.worker(dict(outcome=outcome, reasonCode='QUORUM_UNAVAILABLE'), self.success)
                with self.assertRaisesRegex(ValueError, 'unexpected public protocol read failure'): self.read(worker)
                worker.send.assert_called_once_with('read')

    def test_disconnect_or_unclassified_exception_is_not_retried(self):
        for response, exception in ((None, ValueError), (TimeoutError('worker timeout'), TimeoutError)):
            with self.subTest(response=response):
                worker = self.worker(response, self.success)
                with self.assertRaises(exception): self.read(worker)
                worker.send.assert_called_once_with('read')

    def test_failed_voter_or_missing_leader_is_not_swallowed(self):
        worker = self.worker(self.success)
        self.leader.side_effect = ValueError('public voter failed')
        with self.assertRaisesRegex(ValueError, 'public voter failed'): self.read(worker)
        worker.send.assert_not_called()


    def test_admission_observation_precedes_each_recovery_read_attempt(self):
        worker = self.worker(dict(outcome='NOT_APPLICABLE', reasonCode='QUORUM_UNAVAILABLE'), self.success)
        self.leader.return_value = ('node-3', worker)
        observations = []
        def before_read(active):
            self.assertIs(worker, active); observations.append(worker.send.call_count)
        self.assertEqual(('node-3', worker), protocol.read_after_recovery({'node-3': worker}, self.expected, before_read=before_read))
        self.assertEqual([0, 1], observations)

    def test_admission_wait_failure_does_not_submit_or_retry_a_read(self):
        worker = self.worker(self.success); self.leader.return_value = ('node-3', worker)
        before_read = Mock(side_effect=ValueError('bounds admission did not drain'))
        with self.assertRaisesRegex(ValueError, 'did not drain'):
            protocol.read_after_recovery({'node-3': worker}, self.expected, before_read=before_read)
        before_read.assert_called_once_with(worker); worker.send.assert_not_called()
