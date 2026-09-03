from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts.v41.evidence import EvidenceError, write_bundle
from scripts.v41.fake_cloud_lane import PLAN
from scripts.v41.operational_cloud_set import (
    BASELINE,
    assemble,
    read_registry,
    register,
    validate_set,
)
from scripts.v41.operational_cloud_workflow import (
    PRESET,
    SCHEMA,
    SUITE,
    render_summary,
    validate_inputs,
    validate_plan,
)


class Phase6EvidenceTest(unittest.TestCase):
    def test_frozen_profiles_and_retention(self) -> None:
        self.assertEqual(1, validate_inputs(
            "experiment", 1, 1800, "actions", "c3d-standard-30",
            "standard")["repeats"])
        self.assertEqual(3, validate_inputs(
            "canonical", 3, 1800, "gcs", "c3d-standard-30",
            "standard")["repeats"])
        self.assertEqual(1, validate_inputs(
            "failure-drill", 1, 1800, "gcs", "c3d-standard-30",
            "standard")["repeats"])
        for values in (
            ("canonical", 1, 1800, "gcs"),
            ("canonical", 3, 120, "gcs"),
            ("canonical", 3, 1800, "actions"),
            ("experiment", 1, 120, "actions"),
        ):
            with self.assertRaises(EvidenceError):
                validate_inputs(*values, "c3d-standard-30", "standard")

    def test_exact_plan_and_readable_summary(self) -> None:
        document = {
            "schemaVersion": SCHEMA, "suite": SUITE, "preset": PRESET,
            "sourceCommit": "a" * 40, "trustedRef": "origin/master",
            "runId": "1234",
            "request": {
                "profile": "canonical", "repeats": 3,
                "durationSeconds": 1800, "retention": "gcs",
                "machineType": "c3d-standard-30", "provisioning": "standard",
            },
            "slots": [1, 2, 3],
            "resources": {
                "sourceDiskType": "pd-balanced", "sourceDiskGiB": 200,
                "restoreDiskType": "pd-balanced", "restoreDiskGiB": 200,
                "filesystem": "ext4", "mountOptions": "defaults",
                "maximumMemberRuntimeSeconds": 5400,
                "maximumRunCostUsd": 25, "serialMembers": True,
            },
        }
        self.assertEqual(document, validate_plan(document))
        summary = render_summary(document)
        self.assertIn("| Run | `1234` |", summary)
        self.assertIn("source VM and disk before", summary)
        changed = json.loads(json.dumps(document))
        changed["resources"]["restoreDiskGiB"] = 201
        with self.assertRaises(EvidenceError):
            validate_plan(changed)

    def test_canonical_set_and_append_only_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = "b" * 40
            lifecycle = [
                "bundle-uploaded", "source-vm-deleted", "source-disk-deleted",
                "source-unavailable-proven", "restore-disk-created",
                "replacement-vm-created", "bundle-downloaded",
                "independent-byte-verification-passed",
                "new-history-restore-passed", "continued-mutation-passed",
                "second-reopen-passed",
            ]
            for slot in range(1, 4):
                member = root / "members" / f"member-{slot}"
                configuration = dict(PLAN)
                configuration.update({
                    "javaProfile": "production", "durationSeconds": 1800,
                    "measurementSeconds": 1800, "slot": slot,
                })
                write_bundle(member / "evidence", {
                    "kind": "v41-source-loss-replacement-host",
                    "status": "PASS", "sourceCommit": source,
                    "sourceState": "clean",
                    "suite": SUITE, "preset": PRESET, "profile": "canonical",
                    "case": {"slot": slot, "sourceLoss": True},
                    "configuration": configuration,
                    "backup": {
                        "contentIdentity": "gse-backup-v1-" + str(slot) * 64,
                        "transport": "GCS",
                    },
                    "verification": {},
                    "restore": {"newHistory": f"history-{slot}"},
                    "process": {"provider": "gcp"},
                    "lifecycle": lifecycle,
                    "cleanup": {
                        "status": "PASS", "leftovers": [],
                        "sourceVmDeleted": True, "sourceDiskDeleted": True,
                        "replacementVmDeleted": True, "restoreDiskDeleted": True,
                        "stagingObjectDeleted": True,
                    },
                    "logs": {"stdoutTail": "", "stderrTail": "",
                             "limitBytesPerStream": 16384},
                    "result": {
                        "sourceLossProven": True, "fullOracle": "PASS",
                        "replacementHostProven": True,
                        "eligibleForCanonicalRegistration": True,
                    },
                })
                (member / "cloud-member.properties").write_text(
                    f"sourceCommit={source}\nprofile=canonical\nslot={slot}\n"
                    "runStatus=PASS\nsourceVmDeleted=PASS\n"
                    "sourceDiskDeleted=PASS\nreplacementVmDeleted=PASS\n"
                    "restoreDiskDeleted=PASS\nstagingObjectDeleted=PASS\n"
                    "cleanup=PASS\n", encoding="ascii")
            set_bundle = root / "set"
            self.assertEqual(0, assemble(Namespace(
                members_root=root / "members", profile="canonical",
                expected_members=3, output=set_bundle)))
            self.assertTrue(validate_set(set_bundle)["canonicalEligible"])
            registry = root / "registry.json"
            registration = Namespace(
                name=BASELINE, set_bundle=set_bundle, registry=registry)
            self.assertEqual(0, register(registration))
            self.assertEqual(BASELINE, read_registry(registry)["baselines"][0]["name"])
            with self.assertRaises(EvidenceError):
                register(registration)


if __name__ == "__main__":
    unittest.main()
