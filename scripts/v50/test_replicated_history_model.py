import unittest

from scripts.v50.replicated_history_model import Entry, ReplicatedHistory


class ReplicatedHistoryTest(unittest.TestCase):
    def entry(self, index, epoch, predecessor="GENESIS", payload="payload"):
        return Entry(index, epoch, "UPSERT", payload, predecessor)

    def test_commit_requires_entry_and_proof_quorums_before_apply(self):
        model = ReplicatedHistory()
        model.promise(1, ("node-1", "node-2"))
        entry = self.entry(1, 1)
        receipts = {node: model.append(node, entry) for node in ("node-1", "node-2")}
        proof = model.commit(entry, receipts, ("node-1", "node-2"))
        model.apply("node-1", 1)
        self.assertEqual(1, model.commit_index)
        self.assertEqual(1, model.application_sequence)
        self.assertEqual(1, model.recovery_floor())
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


if __name__ == "__main__":
    unittest.main()
