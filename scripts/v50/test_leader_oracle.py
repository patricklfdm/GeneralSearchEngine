import copy
import unittest

from scripts.v50.leader_oracle import validate
from scripts.v50.replicated_history_model import VOTERS


class LeaderOracleTest(unittest.TestCase):
    def fixture(self):
        entry = {"index": 1, "epoch": 2, "operation": "NO_OP", "payloadDigest": "empty",
                 "incarnationId": "leader-incarnation", "digest": "same-production-entry"}
        proof = {"index": 1, "digest": "same-production-proof", "receiptVoters": ["node-1", "node-2"]}
        reports = {node: {"lastLogIndex": 1, "entries": [copy.deepcopy(entry)], "proofs": [copy.deepcopy(proof)]} for node in VOTERS}
        applied = {node: {"appliedIndex": 1, "applicationSequence": 0} for node in VOTERS}
        return reports, applied

    def test_control_entry_does_not_advance_application_sequence(self):
        reports, applied = self.fixture()
        self.assertEqual(0, validate(reports, applied, [1])["leaderApplicationSequence"])
        applied["node-1"]["applicationSequence"] = 1
        with self.assertRaises(ValueError):
            validate(reports, applied, [1])

    def test_success_without_proof_quorum_is_rejected_even_with_all_entries(self):
        reports, applied = self.fixture()
        reports["node-2"]["proofs"] = []
        reports["node-3"]["proofs"] = []
        with self.assertRaises(ValueError):
            validate(reports, applied, [1])

    def test_conflicting_history_and_receipts_are_rejected(self):
        for modification in ("entry", "proof", "duplicate-voter"):
            reports, applied = self.fixture()
            if modification == "entry":
                reports["node-2"]["entries"][0]["digest"] = "different"
            elif modification == "proof":
                reports["node-2"]["proofs"][0]["digest"] = "different"
            else:
                for report in reports.values():
                    report["proofs"][0]["receiptVoters"] = ["node-1", "node-1"]
            with self.subTest(modification=modification), self.assertRaises(ValueError):
                validate(reports, applied, [1])

    def test_success_requires_publication_but_lost_response_may_be_committed(self):
        reports, applied = self.fixture()
        applied["node-1"]["appliedIndex"] = 0
        with self.assertRaises(ValueError):
            validate(reports, applied, [1])
        self.assertEqual(1, validate(reports, applied, [])["modelCommitIndex"])
