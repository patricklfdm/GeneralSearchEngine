import unittest
import random
from copy import deepcopy

from scripts.v50.replicated_history_model import (
    APPLICATION_OPERATIONS, CONTROL_OPERATIONS, MAX_EPOCH, Entry, ReplicatedHistory,
)


class ReplicatedHistoryTest(unittest.TestCase):
    def entry(self, index, epoch, predecessor="GENESIS", payload="payload"):
        return Entry(index, epoch, "ADD", payload, predecessor)

    def test_commit_requires_entry_and_proof_quorums_before_apply(self):
        model = ReplicatedHistory()
        model.promise(1, ("node-1", "node-2"))
        entry = self.entry(1, 1)
        receipts = {node: model.append(node, entry) for node in ("node-1", "node-2")}
        proof = model.commit(entry, receipts, ("node-1", "node-2"))
        model.apply("node-1", 1)
        self.assertEqual(1, model.commit_index)
        self.assertEqual(1, model.application_sequence)
        self.assertEqual(0, model.recovery_floor())
        self.assertTrue(proof)

    def test_no_quorum_cannot_commit_or_succeed(self):
        model = ReplicatedHistory()
        model.promise(1, ("node-1", "node-2"))
        entry = self.entry(1, 1)
        receipts = {"node-1": model.append("node-1", entry)}
        with self.assertRaisesRegex(ValueError, "durable quorum"):
            model.commit(entry, receipts, ("node-1", "node-2"))

    def test_conflict_stale_epoch_and_committed_truncation_fail_closed(self):
        model = ReplicatedHistory()
        model.promise(2, ("node-1", "node-2"))
        entry = self.entry(1, 2)
        receipts = {node: model.append(node, entry) for node in ("node-1", "node-2")}
        model.commit(entry, receipts, ("node-1", "node-2"))
        with self.assertRaisesRegex(ValueError, "conflict"):
            model.append("node-1", self.entry(1, 2, payload="other"))
        with self.assertRaisesRegex(ValueError, "epoch"):
            model.append("node-3", self.entry(1, 1))
        with self.assertRaisesRegex(ValueError, "immutable"):
            model.truncate_uncommitted("node-1", 1)

    def test_uncommitted_suffix_may_be_removed(self):
        model = ReplicatedHistory()
        model.promise(1, ("node-1", "node-2"))
        first = self.entry(1, 1)
        receipts = {node: model.append(node, first) for node in ("node-1", "node-2")}
        model.commit(first, receipts, ("node-1", "node-2"))
        second = self.entry(2, 1, first.digest, "later")
        model.append("node-3", first)
        model.append("node-3", second)
        model.truncate_uncommitted("node-3", 2)
        self.assertNotIn(2, model.voters["node-3"].log)

    def committed_model(self, operation="ADD"):
        model = ReplicatedHistory()
        model.promise(1, ("node-1", "node-2"))
        entry = Entry(1, 1, operation, "payload", "GENESIS")
        receipts = {node: model.append(node, entry) for node in ("node-1", "node-2")}
        model.commit(entry, receipts, ("node-1", "node-2"))
        return model, entry

    def test_control_entries_and_atomic_bulk_have_distinct_sequence_semantics(self):
        for operation in sorted(APPLICATION_OPERATIONS | CONTROL_OPERATIONS):
            with self.subTest(operation=operation):
                model, _ = self.committed_model(operation)
                model.apply("node-1", 1)
                model.apply("node-1", 1)
                self.assertEqual(int(operation in APPLICATION_OPERATIONS),
                                 model.application_sequence)

    def test_apply_cannot_regress_or_precede_local_proof(self):
        model, entry = self.committed_model()
        model.apply("node-1", 1)
        with self.assertRaisesRegex(ValueError, "regress"):
            model.apply("node-1", 0)
        model.append("node-3", entry)
        with self.assertRaisesRegex(ValueError, "local durable commit proof"):
            model.apply("node-3", 1)
        self.assertEqual(0, model.voters["node-3"].applied_index)
        model.copy_committed_proof("node-2", "node-3", 1)
        model.apply("node-3", 1)
        self.assertEqual(1, model.voters["node-3"].application_sequence)

    def test_new_promise_fences_old_commit_and_same_epoch_other_incarnation(self):
        model = ReplicatedHistory()
        model.promise(1, ("node-1", "node-2"))
        entry = self.entry(1, 1)
        receipts = {node: model.append(node, entry) for node in ("node-1", "node-2")}
        model.promise(2, ("node-1", "node-2"), incarnation="leader-2")
        with self.assertRaisesRegex(ValueError, "epoch/incarnation"):
            model.commit(entry, receipts, ("node-1", "node-2"))
        with self.assertRaisesRegex(ValueError, "epoch/incarnation"):
            model.append("node-3", self.entry(1, 2))
        self.assertEqual(0, model.commit_index)

    def test_invalid_quorum_or_missing_target_cannot_partially_mutate_model(self):
        model = ReplicatedHistory()
        for nodes in (("node-1", "node-1"), ("node-1", "unknown")):
            with self.assertRaises(ValueError):
                model.promise(1, nodes)
            self.assertEqual(0, model.voters["node-1"].promised_epoch)
        model.promise(1, ("node-1", "node-2"))
        entry = self.entry(1, 1)
        receipts = {node: model.append(node, entry) for node in ("node-1", "node-2")}
        before = deepcopy(model.__dict__)
        for nodes in (("node-1",), ("node-1", "node-3")):
            with self.assertRaises(ValueError):
                model.commit(entry, receipts, nodes)
            self.assertEqual(before, model.__dict__)

    def test_recovery_floor_requires_two_verified_snapshot_holders(self):
        model, _ = self.committed_model()
        self.assertEqual(0, model.recovery_floor())
        for node in ("node-1", "node-2"):
            model.apply(node, 1)
            model.install_snapshot(node, 1)
            self.assertEqual(int(node == "node-2"), model.recovery_floor())
        with self.assertRaises(ValueError):
            model.install_snapshot("node-1", 0)

    def test_lost_proof_ack_does_not_allow_truncating_proven_history(self):
        model = ReplicatedHistory()
        model.promise(1, ("node-1", "node-2"))
        entry = self.entry(1, 1)
        receipts = {node: model.append(node, entry) for node in ("node-1", "node-2")}
        proof = model.prepare_proof(entry, receipts)
        model.persist_proof("node-2", proof)
        self.assertEqual(0, model.commit_index)
        with self.assertRaisesRegex(ValueError, "immutable"):
            model.truncate_uncommitted("node-2", 1)

    def test_unknown_operation_wrong_leader_and_epoch_overflow_fail_closed(self):
        with self.assertRaises(ValueError):
            Entry(1, 1, "CONFIGURATION", "payload", "GENESIS")
        model = ReplicatedHistory()
        for kwargs in ({"leader": "node-2"}, {"incarnation": ""}):
            with self.assertRaises(ValueError):
                model.promise(1, ("node-1", "node-2"), **kwargs)
        with self.assertRaisesRegex(ValueError, "overflow"):
            model.promise(MAX_EPOCH + 1, ("node-1", "node-2"))

    def test_seeded_histories_preserve_prefix_and_application_sequence(self):
        for seed in range(30):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                model = ReplicatedHistory()
                model.promise(1, ("node-1", "node-2", "node-3"))
                predecessor, expected = "GENESIS", 0
                for index in range(1, 25):
                    operation = rng.choice(sorted(APPLICATION_OPERATIONS | CONTROL_OPERATIONS))
                    entry = Entry(index, 1, operation, f"seed={seed}:entry={index}", predecessor)
                    receipts = {node: model.append(node, entry) for node in model.voters}
                    follower = rng.choice(("node-2", "node-3"))
                    model.commit(entry, receipts, ("node-1", follower))
                    other = "node-3" if follower == "node-2" else "node-2"
                    model.copy_committed_proof(follower, other, index)
                    expected += operation in APPLICATION_OPERATIONS
                    for node, voter in model.voters.items():
                        model.apply(node, index)
                        model.apply(node, index)
                        self.assertEqual(expected, voter.application_sequence)
                        self.assertLessEqual(voter.applied_index, model.commit_index)
                        self.assertEqual(entry.digest, voter.log[index].digest)
                    predecessor = entry.digest


if __name__ == "__main__":
    unittest.main()
