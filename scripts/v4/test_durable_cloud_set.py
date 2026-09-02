from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts.v4.durable_cloud_set import (
    BASELINE_NAME,
    assemble,
    read_registry,
    register,
    validate_set,
)
from scripts.v4.evidence import EvidenceError, write_bundle
from scripts.v4.test_phase6_performance import Phase6PerformanceTest


class DurableCloudSetTest(unittest.TestCase):
    def test_three_comparable_members_form_one_registerable_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            members = root / "members"
            for slot in range(1, 4):
                self.write_member(members / str(slot) / "evidence", slot)
            output = root / "set"
            self.assertEqual(0, assemble(Namespace(
                members_root=members,
                profile="canonical",
                expected_members=3,
                output=output,
            )))
            evidence = validate_set(output)
            self.assertTrue(evidence["result"]["canonicalEligible"])

            registry = root / "registry.json"
            self.assertEqual(0, register(Namespace(
                registry=registry,
                set_bundle=output,
                name=BASELINE_NAME,
            )))
            entries = read_registry(registry)["baselines"]
            self.assertEqual(1, len(entries))
            self.assertEqual("4" * 40, entries[0]["sourceCommit"])
            with self.assertRaisesRegex(EvidenceError, "already registered"):
                register(Namespace(
                    registry=registry,
                    set_bundle=output,
                    name=BASELINE_NAME,
                ))

    def test_canonical_rejects_missing_member(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for slot in range(1, 3):
                self.write_member(root / "members" / str(slot) / "evidence", slot)
            with self.assertRaisesRegex(EvidenceError, "found 2"):
                assemble(Namespace(
                    members_root=root / "members",
                    profile="canonical",
                    expected_members=3,
                    output=root / "set",
                ))

    @staticmethod
    def write_member(path: Path, slot: int) -> None:
        properties = Phase6PerformanceTest.properties()
        properties["profile"] = "production"
        document = {
            "kind": "v4-durable-performance",
            "status": "PASS",
            "sourceCommit": "4" * 40,
            "environment": {
                "sourceState": "clean",
                "provider": "local-process",
                "suite": "v4.0-durable-single-node-suite-v1",
                "preset": "v4.0-durable-single-node-v1",
                "profile": "production",
                "evidenceProfile": "canonical",
                "cloudProvider": "gcp",
                "cloudMachineType": "c3d-standard-30",
                "cloudImage": "pinned-image",
                "cloudZone": "us-west4-a",
                "filesystem": "ext4",
                "device": f"disk-{slot}",
            },
            "configuration": {
                "durationSeconds": 1800,
                "codecIdentity": "v40-performance-codec-v1",
                "schemaIdentity": "v40-performance-schema-v1",
                "storageIdentity": "v40-performance-store-v1",
            },
            "case": {},
            "submittedHistory": [],
            "futureOutcomes": [],
            "process": {},
            "inspection": {
                "propertiesSchema": properties["schemaVersion"],
                "properties": properties,
            },
            "recovery": {},
            "logs": {
                "stdoutTail": "",
                "stderrTail": "",
                "limitBytesPerStream": 4096,
            },
            "cleanup": {"status": "PASS", "leftovers": []},
            "lifecycle": [],
            "result": {
                "status": "PASS",
                "paidExecution": True,
                "metrics": properties,
            },
        }
        write_bundle(path, document)
        (path.parent / "cloud-member.properties").write_text(
            "sourceCommit=" + "4" * 40 + "\n"
            "profile=canonical\n"
            "slot=" + str(slot) + "\n"
            "runStatus=PASS\n"
            "cleanup=PASS\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
