from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.v43.derived_format_v12 import fixture
from scripts.v43.evidence import EvidenceError, canonical_json, sha256, write_bundle
from scripts.v43.fast_reopen_cloud_set import assemble, validate_set
from scripts.v43.fast_reopen_cloud_workflow import (
    PRESET, RESOURCES, SCHEMA, SUITE, render_summary, validate_inputs, validate_plan,
)
from scripts.v43.fast_reopen_performance import (
    build_document, validate_fast_reopen_bundle,
)

SOURCE = "a" * 40
ORACLE = "b" * 64
FINAL = "c" * 64
PROJECT = Path(__file__).resolve().parents[2]


def properties() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    common = {"status": "PASS", "profile": "smoke", "documents": "1000",
              "tokensPerDocument": "16", "samples": "3"}
    published = {**common, "schemaVersion": "gse-v43-published-v42-properties-v1",
                 "publishedVersion": "4.2.0", "open.samplesNanos": "30,20,10",
                 "open.medianNanos": "20", "open.minNanos": "10",
                 "open.maxNanos": "30", "oracleChecksum": ORACLE,
                 "pageCacheState": "uncontrolled-os-cache"}
    source = {**common, "schemaVersion": "gse-v43-fast-reopen-properties-v1",
              "stage": "source", "mutations": "100",
              "processCpuNanosAtStart": "0", "processCpuNanosAtEnd": "10",
              "pageCacheState": "uncontrolled-os-cache",
              "source.loadCheckpointNanos": "100", "source.sequence": "7",
              "source.initialChecksum": ORACLE,
              "backup.elapsedNanos": "100", "backup.sequence": "7",
              "backup.totalBytes": "100", "backup.contentIdentity": "",
              "forced.samplesNanos": "100,110,120", "forced.medianNanos": "110",
              "forced.recoveryReadyMedianNanos": "10", "forced.refreshMedianNanos": "90",
              "forced.checksum": ORACLE, "warm.samplesNanos": "40,50,60",
              "warm.medianNanos": "50", "warm.derivedReadMedianBytes": "100",
              "warm.checksum": ORACLE, "warm.ratioMicros": "454545",
              "restore.coldOpenNanos": "100", "restore.warmOpenNanos": "40",
              "restore.checksum": ORACLE, "restore.coldOutcome": "FULL_FALLBACK",
              "restore.warmOutcome": "COMPLETE_WARM", "migration.planNanos": "10",
              "migration.applyNanos": "20", "migration.coldOpenNanos": "100",
              "migration.coldOutcome": "FULL_FALLBACK", "migration.checksum": ORACLE,
              "migration.planDigest": "gse-migration-plan-v1-" + "d" * 64,
              "migration.targetHistory": "00000000-0000-0000-0000-000000000001",
              "source.canonicalBytes": "100", "source.derivedBytes": "100",
              "source.directoryBytes": "200", "source.temporaryPeakBytes": "300",
              "source.heapUsedBytes": "100", "source.gcCount": "0",
              "source.gcTimeMillis": "0", "source.totalNanos": "1000"}
    replacement = {**common, "schemaVersion": "gse-v43-fast-reopen-properties-v1",
                   "stage": "replacement", "mutations": "100",
                   "processCpuNanosAtStart": "0", "processCpuNanosAtEnd": "10",
                   "pageCacheState": "uncontrolled-os-cache",
                   "replacement.primaryWarmNanos": "40", "replacement.primaryChecksum": ORACLE,
                   "replacement.migratedWarmNanos": "40", "replacement.migratedChecksum": ORACLE,
                   "fallback.structuredOpenNanos": "80", "fallback.structuredChecksum": ORACLE,
                   "fallback.structuredLoaded": "3", "fallback.structuredRebuilt": "1",
                   "fallback.textOpenNanos": "80", "fallback.textChecksum": ORACLE,
                   "fallback.textLoaded": "3", "fallback.textRebuilt": "1",
                   "fallback.catalogOpenNanos": "100", "fallback.catalogChecksum": ORACLE,
                   "fallback.catalogRebuilt": "4", "wal.openNanos": "50",
                   "wal.checksum": FINAL, "wal.replayCreatedIndexes": "0",
                   "wal.recoveredSequence": "8", "lifecycle.elapsedNanos": "100",
                   "lifecycle.reopenNanos": "40", "lifecycle.checksum": FINAL,
                   "lifecycle.sequence": "10", "measurement.reads": "100",
                   "measurement.durationNanos": "1000000000",
                   "measurement.readsPerSecondMicros": "100000000",
                   "measurement.processCpuNanos": "10", "measurement.readBytes": "0",
                   "measurement.writeBytes": "0", "measurement.gcCount": "0",
                   "measurement.gcTimeMillis": "0", "measurementSeconds": "1",
                   "replacement.heapUsedBytes": "100", "replacement.canonicalBytes": "100",
                   "replacement.derivedBytes": "100", "replacement.directoryBytes": "200"}
    return published, source, replacement


def production_properties() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    published, source, replacement = properties()
    for values in (published, source, replacement):
        values.update({"profile": "production", "documents": "100000",
                       "samples": "5"})
    source.update({
        "mutations": "10000", "forced.samplesNanos": "100,105,110,115,120",
        "warm.samplesNanos": "40,45,50,55,60",
    })
    replacement.update({
        "mutations": "10000", "measurementSeconds": "1800",
        "measurement.durationNanos": "1800000000000",
    })
    published["open.samplesNanos"] = "10,15,20,25,30"
    return published, source, replacement


class Phase6EvidenceTest(unittest.TestCase):
    def test_remote_bootstrap_installs_wrapper_archive_prerequisite(self) -> None:
        script = (PROJECT / "scripts/v43/remote_fast_reopen_stage.sh").read_text(
            encoding="utf-8")
        normalized = " ".join(script.replace("\\\n", " ").split())
        self.assertIn(
            "openjdk-21-jdk-headless git ca-certificates python3 unzip curl",
            normalized)
        self.assertLess(normalized.index(" unzip "), normalized.index(" ./mvnw "))
        self.assertNotIn('"$primary_mount/current"', script)
        self.assertNotIn('"$target_mount/current"', script)
        self.assertEqual(2, normalized.count(
            '"$java_profile" "$primary_mount" "$target_mount"'))
        self.assertIn(
            'cp -a "$primary_mount/canonical-backup" "$output/backup"',
            normalized)
        self.assertIn(
            'tar -C "$primary_mount" -czf "$HOME/v43-source-output.tar.gz" '
            '"$(basename "$output")"', normalized)
        self.assertIn(
            'tar -C "$primary_mount" -czf '
            '"$HOME/v43-replacement-output.tar.gz" "$(basename "$output")"',
            normalized)

    def test_plan_is_exact_and_summary_has_run_id(self) -> None:
        request = validate_inputs("canonical", 3, 1800, "gcs",
                                  "c3d-standard-30", "standard")
        plan = {"schemaVersion": SCHEMA, "suite": SUITE, "preset": PRESET,
                "sourceCommit": SOURCE, "trustedRef": "origin/master",
                "runId": "123", "request": request, "slots": [1, 2, 3],
                "resources": dict(RESOURCES)}
        self.assertEqual(plan, validate_plan(plan))
        self.assertIn("| Run | `123` |", render_summary(plan))
        with self.assertRaises(EvidenceError):
            validate_inputs("canonical", 3, 1800, "actions",
                            "c3d-standard-30", "standard")

    def test_properties_bundle_and_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); backup = root / "backup"; backup.mkdir()
            frozen = fixture()
            for name, value in frozen.backup.items():
                (backup / name).write_bytes(value)
            published, source, replacement = properties()
            source["backup.contentIdentity"] = frozen.backup_identity
            document = build_document(
                source_sha=SOURCE, source_state="dirty", evidence_profile="local-scaffold",
                java_profile="smoke", duration_seconds=1, slot=1,
                published=published, source=source, replacement=replacement,
                inspection={"status": "VALID", "sequence": 7,
                            "contentIdentity": frozen.backup_identity},
                provider="local", cleanup={"status": "PASS", "leftovers": [],
                                            "localArtifactsDeleted": True},
                stdout="ok", stderr="")
            output = root / "evidence"; write_bundle(output, document)
            self.assertEqual(10, validate_fast_reopen_bundle(output)["result"]["cellCount"])
            data = (output / "evidence.json").read_bytes()
            (output / "evidence.json").write_bytes(data + b" ")
            with self.assertRaises(EvidenceError):
                validate_fast_reopen_bundle(output)
            tampered = copy.deepcopy(document)
            tampered["derived"]["structuredPartial"]["loaded"] = 4
            semantic = root / "semantic-tamper"; write_bundle(semantic, tampered)
            with self.assertRaises(EvidenceError):
                validate_fast_reopen_bundle(semantic)

    def test_canonical_set_and_registration_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); members = root / "members"
            for slot in (1, 2, 3):
                member = members / f"member-{slot}"; evidence = member / "evidence"
                published, source, replacement = production_properties()
                identity = "gse-backup-v3-" + str(slot) * 64
                source["backup.contentIdentity"] = identity
                document = build_document(
                    source_sha=SOURCE, source_state="clean",
                    evidence_profile="canonical", java_profile="production",
                    duration_seconds=1800, slot=slot, published=published,
                    source=source, replacement=replacement,
                    inspection={"status": "VALID", "sequence": 7,
                                "contentIdentity": identity}, provider="gcp",
                    cleanup={"status": "PASS", "leftovers": [],
                             "sourceVmDeleted": True,
                             "replacementVmDeleted": True,
                             "primaryDiskDeleted": True,
                             "targetDiskDeleted": True,
                             "stagingObjectsDeleted": True},
                    stdout="ok", stderr="")
                write_bundle(evidence, document)
                (member / "cloud-member.properties").write_text(
                    f"sourceCommit={SOURCE}\nprofile=canonical\nslot={slot}\n"
                    "runStatus=PASS\nsourceVmDeleted=PASS\nreplacementVmDeleted=PASS\n"
                    "primaryDiskDeleted=PASS\ntargetDiskDeleted=PASS\n"
                    "stagingObjectDeleted=PASS\ncleanup=PASS\n", encoding="ascii")
            arguments = type("Arguments", (), {"profile": "canonical",
                "expected_members": 3, "members_root": members,
                "output": root / "set"})()
            self.assertEqual(0, assemble(arguments))
            self.assertTrue(validate_set(root / "set")["canonicalEligible"])
            evidence = root / "set" / "evidence.json"
            document = json.loads(evidence.read_text("utf-8"))
            document["unexpected"] = True
            evidence.write_bytes(canonical_json(document))
            (root / "set" / "artifact-checksums.sha256").write_text(
                f"{sha256(evidence)}  evidence.json\n", encoding="ascii")
            with self.assertRaises(EvidenceError):
                validate_set(root / "set")


if __name__ == "__main__":
    unittest.main()
