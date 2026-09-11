from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.v43.test_phase6_evidence import production_properties
from scripts.v44.cloud_evidence import build_document, parse_paired, validate_evidence
from scripts.v44.cloud_set import assemble, validate_set
from scripts.v44.cloud_workflow import (
    PRESET,
    RESOURCES,
    SCHEMA,
    SUITE,
    render_summary,
    validate_inputs,
    validate_plan,
)
from scripts.v44.evidence import EvidenceError, canonical_json, sha256, write_bundle

SOURCE = "d" * 40
ORACLE = "b" * 64
ROOT = Path(__file__).resolve().parents[2]


def paired(label: str, multiplier: int = 1) -> dict[str, object]:
    return {"label": label, "documents": 20_000,
            "writeNanos": 100 * multiplier,
            "reopenMedianNanos": 50 * multiplier,
            "semanticDigest": ORACLE}


def raw_properties(identity: str) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    published, source, replacement = production_properties()
    source["backup.contentIdentity"] = identity
    replacement["measurementSeconds"] = "3600"
    replacement["measurement.durationNanos"] = "3600000000000"
    return published, source, replacement


def document(slot: int, profile: str = "canonical") -> dict[str, object]:
    identity = "gse-backup-v3-" + str(slot) * 64
    published, source, replacement = raw_properties(identity)
    return build_document(
        source_sha=SOURCE, source_state="clean", profile=profile, slot=slot,
        duration_seconds=3_600, published42=published, source=source,
        replacement=replacement,
        inspection={"status": "VALID", "sequence": int(source["backup.sequence"]),
                    "contentIdentity": identity},
        published43=paired("published-4-3"),
        current=paired("current-source"),
        cleanup={"status": "PASS", "leftovers": [],
                 "sourceVmDeleted": True, "replacementVmDeleted": True,
                 "dataDiskDeleted": True, "targetDiskDeleted": True,
                 "stagingObjectsDeleted": True}, stdout="ok", stderr="")


class Phase5CloudReadinessTest(unittest.TestCase):
    def test_remote_bootstrap_and_runner_contract_are_exact(self) -> None:
        remote = (ROOT / "scripts/v44/remote_final_durable_stage.sh").read_text(
            encoding="utf-8")
        normalized = " ".join(remote.replace("\\\n", " ").split())
        self.assertIn(
            "openjdk-21-jdk-headless git ca-certificates python3 unzip curl",
            normalized)
        self.assertLess(normalized.index(" unzip "), normalized.index(" ./mvnw "))
        self.assertIn("21.0.12", (ROOT /
            "docs/v4x/v4.4/release-toolchain.json").read_text())
        self.assertIn("general-search-engine-4.3.0.jar", remote)
        self.assertIn("c5ecf5cf311c734481e95f14bdcfffb466fa132dde424a2b6b4a58fe41778583",
                      remote)
        self.assertIn('[[ "$duration" == 3600', remote)
        self.assertIn("v44-source-output.tar.gz", remote)
        self.assertIn("v44-replacement-output.tar.gz", remote)
        self.assertNotIn("gcloud ", remote)

        runner = (ROOT /
            "scripts/v44/run_final_durable_cloud_member.sh").read_text(
                encoding="utf-8")
        self.assertIn("/v4.4-final-durable/", runner)
        self.assertNotIn("/v4.3-fast-reopen/", runner)
        self.assertIn("--max-run-duration=10800s", runner)
        self.assertIn("ubuntu-2404-noble-amd64-v20260906", runner)
        self.assertIn("--data-disk-deleted", runner)

    def test_workflow_is_manual_serial_and_failure_retaining(self) -> None:
        workflow = (ROOT /
            ".github/workflows/v44-final-durable-evidence.yml").read_text(
                encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("\n  push:", workflow)
        self.assertNotIn("\n  schedule:", workflow)
        self.assertIn("max-parallel: 1", workflow)
        self.assertIn("environment: cloud-benchmark", workflow)
        self.assertIn("if: ${{ always() }}", workflow)
        self.assertIn("/v4.4-final-durable/", workflow)
        self.assertNotIn("/v4.3-fast-reopen/", workflow)

    def test_exact_plan_and_readable_summary(self) -> None:
        request = validate_inputs("canonical", 3, 3_600, "gcs",
                                  "c3d-standard-30", "standard")
        plan = {"schemaVersion": SCHEMA, "suite": SUITE, "preset": PRESET,
                "sourceCommit": SOURCE, "trustedRef": "origin/master",
                "runId": "123", "request": request, "slots": [1, 2, 3],
                "resources": dict(RESOURCES)}
        self.assertEqual(plan, validate_plan(plan))
        summary = render_summary(plan)
        self.assertIn("| Run | `123` |", summary)
        self.assertIn("| Measurement | `3600 seconds` |", summary)
        with self.assertRaises(EvidenceError):
            validate_inputs("canonical", 3, 3_600, "actions",
                            "c3d-standard-30", "standard")

    def test_paired_output_parser_is_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "paired.txt"
            path.write_text(
                "v44PairedControl=PASS label=published-4-3 documents=20000 "
                "indexes=4 writeNanos=100 reopenMedianNanos=50 "
                f"semanticDigest={ORACLE}\n", encoding="ascii")
            self.assertEqual(100, parse_paired(path, "published-4-3")["writeNanos"])
            path.write_text(path.read_text() + "unexpected\n")
            with self.assertRaisesRegex(EvidenceError, "output differs"):
                parse_paired(path, "published-4-3")

    def test_member_and_three_member_set_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            members = root / "members"
            for slot in (1, 2, 3):
                member = members / f"member-{slot}"
                write_bundle(member / "evidence", document(slot))
                (member / "cloud-member.properties").write_text(
                    f"sourceCommit={SOURCE}\nprofile=canonical\nslot={slot}\n"
                    "runStatus=PASS\nsourceVmDeleted=PASS\n"
                    "replacementVmDeleted=PASS\ndataDiskDeleted=PASS\n"
                    "targetDiskDeleted=PASS\nstagingObjectDeleted=PASS\n"
                    "cleanup=PASS\n", encoding="ascii")
                self.assertEqual(slot,
                    validate_evidence(member / "evidence")["case"]["slot"])
            arguments = type("Arguments", (), {
                "profile": "canonical", "expected_members": 3,
                "members_root": members, "output": root / "set"})()
            self.assertEqual(0, assemble(arguments))
            self.assertTrue(validate_set(root / "set")["canonicalEligible"])

    def test_member_threshold_and_set_tamper_fail_closed(self) -> None:
        published, source, replacement = raw_properties("gse-backup-v3-" + "9" * 64)
        with self.assertRaisesRegex(EvidenceError, "1.35"):
            build_document(
                source_sha=SOURCE, source_state="clean", profile="canonical", slot=1,
                duration_seconds=3_600, published42=published, source=source,
                replacement=replacement,
                inspection={"status": "VALID",
                            "sequence": int(source["backup.sequence"]),
                            "contentIdentity": source["backup.contentIdentity"]},
                published43=paired("published-4-3"),
                current=paired("current-source", 2),
                cleanup={"status": "PASS", "leftovers": [],
                         "sourceVmDeleted": True, "replacementVmDeleted": True,
                         "dataDiskDeleted": True, "targetDiskDeleted": True,
                         "stagingObjectsDeleted": True}, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "member"
            write_bundle(path, document(1, "experiment"))
            evidence = path / "evidence.json"
            value = json.loads(evidence.read_text())
            value["cleanup"]["leftovers"] = ["disk"]
            evidence.write_bytes(canonical_json(value))
            (path / "artifact-checksums.sha256").write_text(
                f"{sha256(evidence)}  evidence.json\n", encoding="ascii")
            with self.assertRaises(EvidenceError):
                validate_evidence(path)


if __name__ == "__main__":
    unittest.main()
