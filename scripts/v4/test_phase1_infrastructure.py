from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts.v4.durable_cloud_lane import PRESET, SUITE, fake_run
from scripts.v4.durable_harness import run_case_with_failure_evidence
from scripts.v4.evidence import EvidenceError, validate_bundle, write_bundle
from scripts.v4.storage_inspector import inspect_phase1_directory


class Phase1InfrastructureTest(unittest.TestCase):
    def test_checksum_validator_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "bundle"
            write_bundle(bundle, self.document())
            self.assertEqual("PASS", validate_bundle(bundle)["status"])
            (bundle / "evidence.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceError, "checksum"):
                validate_bundle(bundle)

    def test_validator_rejects_malformed_source_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "bundle"
            document = self.document()
            document["sourceCommit"] = "Z" * 40
            write_bundle(bundle, document)
            with self.assertRaisesRegex(EvidenceError, "lowercase hexadecimal"):
                validate_bundle(bundle)

    def test_fake_cloud_preserves_disk_and_cleans_every_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fake-cloud"
            result = fake_run(Namespace(
                output=output,
                source_sha="1" * 40,
                source_state="clean",
                profile="failure-drill",
            ))
            self.assertEqual(0, result)
            evidence = validate_bundle(output)
            self.assertEqual(SUITE, evidence["environment"]["suite"])
            self.assertEqual(PRESET, evidence["environment"]["preset"])
            self.assertTrue(evidence["result"]["persistentDiskSurvivedWriter"])
            self.assertEqual([], evidence["result"]["leftovers"])

    def test_failed_child_start_retains_validated_failure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "failed-case"
            with self.assertRaisesRegex(EvidenceError, "failed evidence retained"):
                run_case_with_failure_evidence(Namespace(
                    workspace=workspace,
                    source_sha="2" * 40,
                    source_state="dirty",
                    termination="internal-halt",
                    barrier="phase1-scaffold-v1",
                    java=str(Path(temporary) / "missing-java"),
                    classpath="target/test-classes:target/classes",
                    timeout=1.0,
                ))
            evidence = validate_bundle(workspace / "evidence")
            self.assertEqual("FAIL", evidence["status"])
            self.assertEqual("PASS", evidence["cleanup"]["status"])
            self.assertFalse((workspace / "engine-directory").exists())

    def test_phase1_inspector_rejects_production_storage_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            engine = Path(temporary)
            (engine / "phase1-scaffold.properties").write_text(
                "schemaVersion=1\nbarrierId=phase1-scaffold-v1\n"
                "productionStorage=false\n",
                encoding="utf-8",
            )
            self.assertEqual(
                "NO_PRODUCTION_STORAGE_EXPECTED",
                inspect_phase1_directory(
                    engine, "phase1-scaffold-v1")["classification"],
            )
            (engine / "wal-0001").write_bytes(b"not-authorized")
            with self.assertRaisesRegex(EvidenceError, "production storage"):
                inspect_phase1_directory(engine, "phase1-scaffold-v1")

    @staticmethod
    def document() -> dict[str, object]:
        return {
            "kind": "unit-test",
            "status": "PASS",
            "sourceCommit": "0" * 40,
            "environment": {"sourceState": "clean"},
            "configuration": {},
            "case": {},
            "submittedHistory": [],
            "futureOutcomes": [],
            "process": {},
            "inspection": {},
            "recovery": {},
            "logs": {
                "stdoutTail": "",
                "stderrTail": "",
                "limitBytesPerStream": 4096,
            },
            "cleanup": {"status": "PASS"},
            "lifecycle": [],
            "result": json.loads('{"ok":true}'),
        }


if __name__ == "__main__":
    unittest.main()
