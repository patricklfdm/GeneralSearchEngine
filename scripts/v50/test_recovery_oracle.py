import copy
import struct
import unittest
from scripts.v50.recovery_oracle import validate
from scripts.v50.storage_format import VOTERS


class RecoveryOracleTest(unittest.TestCase):
    def fixture(self):
        key = struct.pack(">i", 1); document = key + b"shared"
        payload = struct.pack(">Hi", 1, 1) + struct.pack(">i", len(key)) + key + struct.pack(">i", len(document)) + document
        report = {"codecId": "leader-fixture", "voter": True, "commitIndex": 2, "snapshotIndex": 0, "snapshotApplication": None, "recoveryFloor": 0,
                  "entries": [{"index": 1, "operation": "NO_OP", "digest": "first"}, {"index": 2, "operation": "ADD", "digest": "protected"}],
                  "retainedApplicationEntries": [{"index": 1, "operation": "NO_OP", "payloadHex": ""}, {"index": 2, "operation": "ADD", "payloadHex": payload.hex()}]}
        control = {"documents": [{"id": 1, "value": "shared"}], "queryIds": [1], "indexCount": 1}
        observed = {node: {"appliedIndex": 2, "applicationSequence": 1, **copy.deepcopy(control)} for node in VOTERS}
        reports = {node: copy.deepcopy(report) for node in VOTERS}
        return copy.deepcopy(reports), reports, observed, control

    def test_valid_proof_survives_without_an_original_client_success(self):
        before, reports, observed, control = self.fixture()
        self.assertEqual("PASS", validate(before, reports, observed, control, 0)["status"])

    def test_protected_prefix_change_rejects(self):
        before, reports, observed, control = self.fixture()
        reports["node-2"]["entries"][1]["digest"] = "conflicting"
        with self.assertRaisesRegex(ValueError, "valid surviving proof"): validate(before, reports, observed, control)

    def test_application_counter_drift_rejects(self):
        before, reports, observed, control = self.fixture(); observed["node-1"]["applicationSequence"] = 0
        with self.assertRaisesRegex(ValueError, "sequence drift"): validate(before, reports, observed, control)

    def test_published_control_mismatch_rejects(self):
        before, reports, observed, control = self.fixture(); control["documents"][0]["value"] = "wrong"
        with self.assertRaisesRegex(ValueError, "published V4.4 control"): validate(before, reports, observed, control)

    def test_erased_disk_cannot_be_reported_as_recovered_voter(self):
        before, reports, observed, control = self.fixture(); reports["node-2"]["voter"] = False
        with self.assertRaisesRegex(ValueError, "non-voting"): validate(before, reports, observed, control)

    def test_lost_successful_boundary_rejects(self):
        before, reports, observed, control = self.fixture()
        with self.assertRaisesRegex(ValueError, "successful response lost"): validate(before, reports, observed, control, 3)


if __name__ == "__main__": unittest.main()
