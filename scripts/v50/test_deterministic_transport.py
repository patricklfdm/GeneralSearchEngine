import unittest
import json
import random
from dataclasses import asdict
from unittest.mock import patch

from scripts.v50.deterministic_transport import DeterministicTransport
from scripts.v50.model_network import ModelNetwork
from scripts.v50.replicated_history_model import Entry


class DeterministicTransportTest(unittest.TestCase):
    def test_round_trip_preserves_exact_trace(self):
        transport = DeterministicTransport("trace-1")
        transport.schedule("node-1", "node-2", "APPEND", "a", delay_ticks=3)
        transport.schedule("node-1", "node-3", "APPEND", "a", action="duplicate")
        transport.schedule("node-2", "node-1", "ACK", "b", action="drop")
        encoded = transport.to_json()
        replay = DeterministicTransport.from_json(encoded)
        self.assertEqual(encoded, replay.to_json())
        self.assertEqual((1, 2, 0), tuple(item.sequence for item in replay.replay_order()))

    def test_unknown_action_is_rejected(self):
        transport = DeterministicTransport("trace-2")
        with self.assertRaises(ValueError):
            transport.schedule("a", "b", "APPEND", "x", action="corrupt")

    def scenario(self, *, drop_entry_ack=False, drop_proof_ack=False, seed=None):
        trace = DeterministicTransport(f"commit-{seed}")
        nodes = ("node-1", "node-2", "node-3")
        trace.message("node-1", "node-1", "ACTIVATE", {"epoch": 1, "voters": nodes})
        payload = {"entry": asdict(Entry(1, 1, "ADD_ALL", "atomic-bulk", "GENESIS"))}
        rng = random.Random(seed)
        stages = (
            ("APPEND", False), ("DURABLE_ACK", True),
            ("PREPARE_PROOF", False), ("COMMIT_PROOF", False),
            ("COMMIT_PROOF_ACK", True), ("COMMIT", False), ("APPLY", False),
        )
        for stage, (kind, response) in enumerate(stages, 1):
            for node in (("node-1",) if kind in {"COMMIT", "PREPARE_PROOF"} else nodes):
                action = "deliver"
                if seed is not None and node != "node-1":
                    action = rng.choice(("deliver", "duplicate", "drop"))
                if node != "node-1" and (
                        (kind == "DURABLE_ACK" and drop_entry_ack)
                        or (kind == "COMMIT_PROOF_ACK" and drop_proof_ack)):
                    action = "drop"
                trace.message(node if response else "node-1",
                              "node-1" if response else node, kind, payload,
                              action=action, delay_ticks=stage)
        return trace

    def test_faulted_trace_replays_model_and_force_ack_order_exactly(self):
        for seed in [None, *range(40)]:
            with self.subTest(seed=seed):
                trace = self.scenario(seed=seed)
                original = ModelNetwork(trace).run()
                replay = ModelNetwork(DeterministicTransport.from_json(trace.to_json())).run()
                self.assertEqual(original, replay, trace.to_json())
                for voter in replay["voters"].values():
                    self.assertLessEqual(voter["applied_index"], replay["commitIndex"])
                    self.assertEqual(voter["applied_index"], voter["application_sequence"])
                if seed is None:
                    self.assertEqual(1, replay["commitIndex"])
                    self.assertTrue(all(v["applied_index"] == 1 for v in replay["voters"].values()))

    def test_dropped_entry_or_proof_acks_prevent_commit_and_application(self):
        for kwargs in ({"drop_entry_ack": True}, {"drop_proof_ack": True}):
            with self.subTest(**kwargs):
                result = ModelNetwork(self.scenario(**kwargs)).run()
                self.assertEqual(0, result["commitIndex"])
                self.assertTrue(all(v["applied_index"] == 0 for v in result["voters"].values()))
                self.assertTrue(any(e["outcome"] == "rejected" for e in result["transcript"]))

    def test_disconnect_blocks_both_directions_until_reconnect_and_duplicate_delivers_twice(self):
        trace = DeterministicTransport("link")
        for source, target, action in (
                ("a", "b", "disconnect"), ("a", "b", "deliver"),
                ("b", "a", "deliver"), ("a", "b", "reconnect"),
                ("b", "a", "duplicate"), ("a", "b", "drop")):
            trace.schedule(source, target, "APPEND", "x", action=action)
        received = []
        transcript = trace.replay(lambda event: received.append(event.sequence))
        self.assertEqual([4, 4], received)
        self.assertEqual(3, sum(e["outcome"] == "dropped" for e in transcript))

    def test_reordered_append_is_rejected_then_retry_succeeds(self):
        trace = DeterministicTransport("reorder")
        trace.message("node-1", "node-1", "ACTIVATE",
                      {"epoch": 1, "voters": ["node-1", "node-2"]})
        first = Entry(1, 1, "NO_OP", "control", "GENESIS")
        second = Entry(2, 1, "ADD", "document", first.digest)
        for entry, tick in ((second, 1), (first, 2), (second, 3)):
            trace.message("node-1", "node-2", "APPEND", {"entry": asdict(entry)}, delay_ticks=tick)
        result = ModelNetwork(trace).run()
        self.assertEqual("rejected", result["transcript"][1]["outcome"])
        self.assertEqual([1, 2], list(result["voters"]["node-2"]["log"]))
        self.assertEqual(0, result["voters"]["node-2"]["applied_index"])

    def test_payload_corruption_is_rejected_before_model_execution(self):
        raw = json.loads(self.scenario().to_json())
        next(iter(raw["payloads"].values()))["tampered"] = True
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            DeterministicTransport.from_json(json.dumps(raw))

    def test_trace_capacity_rejects_admission_without_partial_mutation(self):
        trace = DeterministicTransport("bounded")
        trace.message("a", "b", "APPEND", {"payload": "x"})
        before = trace.to_json()
        with patch("scripts.v50.deterministic_transport.MAX_TRACE_BYTES", 1024):
            with self.assertRaisesRegex(ValueError, "capacity"):
                trace.message("a", "b", "APPEND", {"payload": "x" * 800})
        self.assertEqual(before, trace.to_json())


if __name__ == "__main__":
    unittest.main()
