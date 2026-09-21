"""Maintenance retries must preserve classified failures and their finite bound."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from .public_runtime_harness import checkpoint_when_available


def capacity(**values):
    return dict(command='checkpoint', accepted=False, reasonCode='CAPACITY_EXCEEDED', outcome='NOT_APPLICABLE', **values)


class PublicCheckpointTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'checkpoint.json'; self.now = 0
        def sleep(seconds): self.now += seconds
        for target, value in [('monotonic', lambda: self.now), ('sleep', sleep)]:
            mock = patch('scripts.v51.public_runtime_harness.time.' + target, value); mock.start(); self.addCleanup(mock.stop)

    def worker(self, responses):
        test = self
        class Worker:
            calls = 0
            def request(self, name, timeout):
                test.assertEqual('checkpoint', name); test.assertGreater(timeout, 0)
                value = responses[min(self.calls, len(responses) - 1)]; self.calls += 1
                if isinstance(value, Exception): raise value
                return value
        return Worker()

    def retained(self): return json.loads(self.output.read_text())

    def test_only_capacity_waits_then_records_actual_success(self):
        worker = self.worker([capacity(), capacity(), dict(command='checkpoint', accepted=True, sequence=3)])
        result = checkpoint_when_available(worker, self.output, timeout=1)
        self.assertEqual(3, worker.calls); self.assertEqual('PASS', result['status'])
        self.assertEqual([False, False, True], [a['result']['accepted'] for a in result['attempts']])
        self.assertEqual(result, self.retained())

    def test_other_failures_are_never_retried(self):
        for reason in ['INTEGRITY_FAILURE', 'STORAGE_FAILURE', 'NOT_READY', 'DEADLINE_EXCEEDED']:
            with self.subTest(reason=reason):
                response = capacity(); response['reasonCode'] = reason; worker = self.worker([response])
                with self.assertRaisesRegex(ValueError, 'public checkpoint failed'):
                    checkpoint_when_available(worker, self.output)
                self.assertEqual(1, worker.calls); self.assertEqual('FAIL', self.retained()['status'])

    def test_unclassified_or_uncertain_capacity_is_not_retried(self):
        for outcome in [None, 'INDETERMINATE', 'NOT_SUBMITTED']:
            with self.subTest(outcome=outcome):
                response = capacity(); response['outcome'] = outcome; worker = self.worker([response])
                with self.assertRaisesRegex(ValueError, 'public checkpoint failed'):
                    checkpoint_when_available(worker, self.output)
                self.assertEqual(1, worker.calls)

    def test_capacity_cannot_extend_the_total_deadline(self):
        worker = self.worker([capacity()])
        with self.assertRaisesRegex(ValueError, 'capacity timeout'):
            checkpoint_when_available(worker, self.output, timeout=.5)
        self.assertEqual(.5, self.now); self.assertEqual(2, worker.calls)
        record = self.retained(); self.assertEqual('FAIL', record['status']); self.assertEqual(2, len(record['attempts']))

    def test_lost_response_is_not_retried_and_keeps_pending_attempt(self):
        worker = self.worker([TimeoutError('response missing')])
        with self.assertRaisesRegex(TimeoutError, 'response missing'):
            checkpoint_when_available(worker, self.output)
        self.assertEqual(1, worker.calls); record = self.retained()
        self.assertEqual('FAIL', record['status']); self.assertEqual('response missing', record['failure'])
        self.assertNotIn('result', record['attempts'][0])


if __name__ == '__main__': unittest.main()
