"""Post-crash progress retains uncertainty and never replays application keys."""
from concurrent.futures import Future
import copy
import unittest
from unittest.mock import Mock
from . import public_qualification_harness as q, public_history


class RecoveryWaveTest(unittest.TestCase):
    def setUp(self):
        self.tag = 0; self.attempts = []; self.calls = []

    def documents(self):
        self.tag += 1
        return [dict(id=self.tag, value=f'unique-{self.tag}')]

    def worker(self, outcomes):
        outcomes = iter(outcomes)
        def send(kind, **values):
            self.calls.append(dict(kind=kind, **values))
            outcome = next(outcomes); future = Future()
            if isinstance(outcome, Exception): future.set_exception(outcome)
            else:
                response = dict(kind=kind, opId=str(len(self.calls)), **values)
                if outcome is None: response = None
                elif isinstance(outcome, dict): response.update(outcome)
                else: response['outcome'] = outcome
                future.set_result(response)
            return future
        return Mock(send=Mock(side_effect=send))

    def run_waves(self, *workers):
        choose = Mock(side_effect=[(f'node-{i+1}', w) for i, w in enumerate(workers)])
        result = q.recovered_wave(choose, self.documents, self.attempts)
        return result, choose

    def test_ci_indeterminate_then_new_leader_uses_fresh_payloads_and_keeps_all_results(self):
        first = self.worker([dict(outcome='INDETERMINATE', reasonCode='QUORUM_UNAVAILABLE'),
                             dict(outcome='NOT_APPLICABLE', reasonCode='QUORUM_UNAVAILABLE'),
                             dict(outcome='NOT_SUBMITTED', reasonCode='QUORUM_UNAVAILABLE'),
                             dict(outcome='NOT_APPLICABLE', reasonCode='QUORUM_UNAVAILABLE')])
        second = self.worker(['SUCCESS'] * 4)
        result, choose = self.run_waves(first, second)
        self.assertEqual(('node-2', second), result); self.assertEqual(2, choose.call_count)
        self.assertEqual(['node-1', 'node-2'], [a['node'] for a in self.attempts])
        self.assertEqual('INDETERMINATE', self.attempts[0]['responses'][0]['outcome'])
        self.assertEqual([1, 2, 3, 4], [c['documents'][0]['id'] for c in self.calls if c['kind']=='addAll'])
        self.assertEqual(list(q.WAVE_KINDS) * 2, [c['kind'] for c in self.calls])

    def test_all_four_are_submitted_before_any_future_is_collected(self):
        class Result:
            def __init__(value, kind): value.kind = kind
            def result(value, timeout):
                self.assertEqual(4, worker.send.call_count)
                return dict(kind=value.kind, outcome='SUCCESS')
        worker = Mock(send=Mock(side_effect=lambda kind, **_: Result(kind)))
        self.assertEqual(('node-1', worker), self.run_waves(worker)[0])

    def test_permanent_unavailability_has_three_wave_limit_and_no_fourth_dispatch(self):
        workers = [self.worker([dict(outcome=('NOT_SUBMITTED' if kind=='addAll' else 'NOT_APPLICABLE'),
                                    reasonCode='NOT_READY') for kind in q.WAVE_KINDS]) for _ in range(4)]
        with self.assertRaisesRegex(ValueError, 'three fresh waves'): self.run_waves(*workers)
        self.assertEqual(3, len(self.attempts)); self.assertEqual(12, len(self.calls))
        workers[3].send.assert_not_called()

    def test_only_classified_availability_can_proceed(self):
        for reason in q.RECOVERY_REASONS:
            with self.subTest(reason=reason):
                self.attempts.clear()
                worker = self.worker([dict(outcome=('NOT_SUBMITTED' if kind=='addAll' else 'NOT_APPLICABLE'), reasonCode=reason)
                                      for kind in q.WAVE_KINDS])
                self.run_waves(worker, self.worker(['SUCCESS'] * 4))
                self.assertEqual(2, len(self.attempts))

    def test_integrity_storage_capacity_closed_and_unknown_failure_stop_immediately(self):
        for reason in ('INTEGRITY_FAILURE', 'STORAGE_FAILURE', 'CAPACITY_EXCEEDED', 'CLOSED', 'unknown', None):
            for at in (0, 1):
                with self.subTest(reason=reason, at=at):
                    replies = ['SUCCESS'] * 4
                    replies[at] = dict(outcome='NOT_SUBMITTED' if at==0 else 'NOT_APPLICABLE', reasonCode=reason)
                    after = self.worker(['SUCCESS'] * 4)
                    with self.assertRaisesRegex(ValueError, 'unexpected recovery wave failure'):
                        self.run_waves(self.worker(replies), after)
                    after.send.assert_not_called()

    def test_invalid_mutation_or_read_outcome_is_not_reclassified(self):
        for at, outcome, reason in [(0, 'NOT_APPLICABLE', 'QUORUM_UNAVAILABLE'),
                                   (0, 'INDETERMINATE', 'NOT_LEADER'), (0, 'INDETERMINATE', 'NOT_READY'),
                                   (0, 'PENDING', 'QUORUM_UNAVAILABLE'), (0, 'CANCELLED', 'QUORUM_UNAVAILABLE'),
                                   (1, 'INDETERMINATE', 'QUORUM_UNAVAILABLE'), (1, 'NOT_SUBMITTED', 'NOT_READY')]:
            with self.subTest(at=at, outcome=outcome, reason=reason):
                replies = ['SUCCESS'] * 4; replies[at] = dict(outcome=outcome, reasonCode=reason)
                with self.assertRaisesRegex(ValueError, 'unexpected recovery wave failure'):
                    self.run_waves(self.worker(replies))

    def test_disconnect_timeout_or_mismatched_response_fails(self):
        for response, error in [(None, ValueError), (TimeoutError('worker stalled'), TimeoutError),
                                (dict(kind='close', outcome='SUCCESS'), ValueError)]:
            with self.subTest(response=response):
                after = self.worker(['SUCCESS'] * 4)
                with self.assertRaises(error): self.run_waves(self.worker([response, *['SUCCESS'] * 3]), after)
                after.send.assert_not_called()

    def test_missing_leader_failure_is_not_swallowed(self):
        choose = Mock(side_effect=ValueError('failed voter'))
        with self.assertRaisesRegex(ValueError, 'failed voter'):
            q.recovered_wave(choose, self.documents, self.attempts)
        self.assertEqual([], self.calls)

    def test_every_wave_is_drained_before_classifying_a_later_failure(self):
        worker = self.worker(['SUCCESS', 'SUCCESS', dict(outcome='NOT_SUBMITTED', reasonCode='STORAGE_FAILURE'), 'SUCCESS'])
        with self.assertRaisesRegex(ValueError, 'unexpected recovery wave failure'): self.run_waves(worker)
        self.assertEqual(4, len(self.attempts[-1]['responses']))

    def test_independent_history_still_checks_uncertain_inclusion_and_lost_acknowledged_data(self):
        first = self.worker([dict(outcome='INDETERMINATE', reasonCode='QUORUM_UNAVAILABLE'),
                             dict(outcome='NOT_APPLICABLE', reasonCode='QUORUM_UNAVAILABLE'),
                             dict(outcome='NOT_SUBMITTED', reasonCode='QUORUM_UNAVAILABLE'),
                             dict(outcome='NOT_APPLICABLE', reasonCode='QUORUM_UNAVAILABLE')])
        _, _ = self.run_waves(first, self.worker(['SUCCESS'] * 4))
        history = [dict(response, startNanos=wave*10, endNanos=wave*10+1)
                   for wave, attempt in enumerate(self.attempts) for response in attempt['responses']]
        expected = [self.calls[i]['documents'][0] for i in (0, 4, 6)]
        for row in history[4:]:
            if row['kind']=='read': row['documents'] = expected
        result = public_history.check(history)
        self.assertTrue(next(v for v in result['witness'] if v['opId']=='1')['included'])
        broken = copy.deepcopy(history)
        broken.append(dict(opId='later', kind='read', outcome='SUCCESS', startNanos=20, endNanos=21, documents=[]))
        with self.assertRaisesRegex(ValueError, 'not linearizable'): public_history.check(broken)


if __name__ == '__main__': unittest.main()
