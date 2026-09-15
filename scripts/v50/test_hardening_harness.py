"""Admission recovery must not hide other faults or unbounded capacity failures."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.v50 import hardening_harness as harness


class Clock:
    def __init__(self):
        self.now = 0
        self.delays = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.delays.append(seconds)
        self.now += seconds


class PressureCatchupTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.worker = Mock()
        self.group = SimpleNamespace(case=Path(self.directory.name), workers=[self.worker])
        self.clock = Clock()
        for name in ("monotonic", "sleep"):
            mock = patch.object(harness.time, name, getattr(self.clock, name))
            mock.start()
            self.addCleanup(mock.stop)

    @staticmethod
    def capacity(**changes):
        return {"accepted": False, "reason": "CAPACITY_EXCEEDED", "state": "READY",
                "writeQuorum": True, "appliedIndex": 19, **changes}

    def evidence(self):
        return json.loads((self.group.case / "catchup-after-pressure-node-3.json").read_text())

    def test_transient_capacity_then_success_retains_every_outcome(self):
        success = {"accepted": True, "appliedIndex": 19}
        self.worker.command.side_effect = [self.capacity(), self.capacity(), success]
        self.assertEqual(success, harness.catchup_after_pressure(self.group, "node-3"))
        self.assertEqual([False, False, True], [item["result"]["accepted"] for item in self.evidence()["attempts"]])
        self.assertEqual([0.05, 0.05], self.clock.delays)
        self.assertTrue(all(call.args == ("catchup",) and call.kwargs == {"peer": "node-3"}
                            for call in self.worker.command.call_args_list))

    def test_immediate_success_does_not_sleep(self):
        self.worker.command.return_value = {"accepted": True}
        harness.catchup_after_pressure(self.group, "node-3")
        self.assertEqual(1, self.worker.command.call_count)
        self.assertEqual([], self.clock.delays)

    def test_other_failures_are_not_retried(self):
        for reason in ("QUORUM_UNAVAILABLE", "CONFLICTING_HISTORY", "STORAGE_FAILURE", "INTEGRITY_FAILURE", "CLOSED"):
            with self.subTest(reason=reason):
                self.worker.reset_mock()
                self.worker.command.return_value = self.capacity(reason=reason)
                with self.assertRaisesRegex(AssertionError, "catchup failed after pressure release"):
                    harness.catchup_after_pressure(self.group, "node-3")
                self.assertEqual(1, self.worker.command.call_count)
                self.assertEqual(reason, self.evidence()["attempts"][0]["result"]["reason"])

    def test_capacity_with_lost_leader_availability_is_not_retried(self):
        for changes in ({"state": "FAILED"}, {"writeQuorum": False}):
            with self.subTest(changes=changes):
                self.worker.reset_mock()
                self.worker.command.return_value = self.capacity(**changes)
                with self.assertRaisesRegex(AssertionError, "changed leader availability"):
                    harness.catchup_after_pressure(self.group, "node-3")
                self.assertEqual(1, self.worker.command.call_count)

    def test_persistent_capacity_hits_attempt_bound(self):
        self.worker.command.return_value = self.capacity()
        with self.assertRaisesRegex(AssertionError, "capacity did not recover"):
            harness.catchup_after_pressure(self.group, "node-3")
        self.assertEqual(harness.PRESSURE_CATCHUP_ATTEMPTS, self.worker.command.call_count)
        self.assertEqual(harness.PRESSURE_CATCHUP_ATTEMPTS, len(self.evidence()["attempts"]))

    def test_elapsed_window_prevents_another_attempt(self):
        def slow_rejection(*args, **kwargs):
            self.clock.now += harness.PRESSURE_CATCHUP_SECONDS
            return self.capacity()
        self.worker.command.side_effect = slow_rejection
        with self.assertRaisesRegex(AssertionError, "capacity did not recover"):
            harness.catchup_after_pressure(self.group, "node-3")
        self.assertEqual(1, self.worker.command.call_count)
        self.assertEqual([], self.clock.delays)

    def test_worker_timeout_propagates_and_retains_evidence(self):
        self.worker.command.side_effect = AssertionError("worker response timed out")
        with self.assertRaisesRegex(AssertionError, "worker response timed out"):
            harness.catchup_after_pressure(self.group, "node-3")
        self.assertEqual(1, self.worker.command.call_count)
        self.assertEqual([], self.evidence()["attempts"])


if __name__ == "__main__":
    unittest.main()
