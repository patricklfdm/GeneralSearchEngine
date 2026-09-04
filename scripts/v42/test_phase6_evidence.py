from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts.v42.evidence import EvidenceError, write_bundle
from scripts.v42.fake_cloud_lane import PLAN
from scripts.v42.migration_cloud_set import (
    BASELINE,
    assemble,
    read_registry,
    register,
    validate_set,
)
from scripts.v42.migration_cloud_workflow import (
    PRESET,
    SCHEMA,
    SUITE,
    render_summary,
    validate_inputs,
    validate_plan,
)
from scripts.v42.migration_performance import validate_properties


def valid_properties() -> tuple[dict[str, str], ...]:
    common = {
        "schemaVersion": "gse-v42-migration-properties-v1",
        "status": "PASS",
        "profile": "smoke",
        "documents": "1000",
        "tokensPerDocument": "16",
        "preMigrationMutations": "100",
        "continuedTargetMutations": "20",
        "processCpuNanosAtStart": "0",
        "processCpuNanosAtEnd": "1",
    }
    source = {
        **common,
        "stage": "source",
        "source.loadNanos": "1",
        "source.mutationNanos": "1",
        "source.checkpointNanos": "1",
        "source.sequence": "2",
        "source.oracleChecksum": "a" * 64,
        "source.directorySha256": "b" * 64,
        "backup.elapsedNanos": "1",
        "backup.sequence": "2",
        "backup.totalBytes": "1",
        "backup.contentIdentity": "gse-backup-v1-" + "c" * 64,
        "source.retainedBytes": "1",
        "source.heapUsedBytes": "1",
        "source.directoryBytes": "1",
        "source.totalNanos": "1",
    }
    migration = {
        **common,
        "stage": "migration",
        "migration.planNanos": "1",
        "migration.applyNanos": "1",
        "migration.predictedTargetBytes": "1",
        "migration.peakTargetBytes": "1",
        "migration.sourceSequence": "2",
        "migration.authoritativeBytes": "1",
        "migration.heapUsedBytes": "1",
        "migration.planDigest": "gse-migration-plan-v1-" + "d" * 64,
        "migration.projectionDigest": "gse-migration-projection-v1-" + "e" * 64,
        "migration.sourceAuthorityIdentity": "gse-migration-source-v1-" + "f" * 64,
        "migration.sourceDirectorySha256After": "b" * 64,
        "migration.sourceHistory": "source-history",
        "migration.targetHistory": "target-history",
        "target.initialSequence": "2",
        "target.initialChecksum": "1" * 64,
        "target.directoryBytes": "1",
        "target.directorySha256": "2" * 64,
    }
    target = {
        **common,
        "stage": "target",
        "target.firstOpenNanos": "1",
        "target.continuedMutationNanos": "1",
        "target.checkpointNanos": "1",
        "target.secondOpenNanos": "1",
        "target.finalSequence": "3",
        "target.finalDirectoryBytes": "1",
        "target.retainedBytes": "1",
        "target.heapUsedBytes": "1",
        "target.finalChecksum": "3" * 64,
        "target.finalDirectorySha256": "4" * 64,
        "measurement.reads": "1",
        "measurement.durationNanos": "1000000000",
        "measurement.readsPerSecondMicros": "1",
        "measurementSeconds": "1",
    }
    rollback = {
        "schemaVersion": "gse-v42-published-rollback-properties-v1",
        "status": "PASS",
        "profile": "smoke",
        "publishedVersion": "4.1.0",
        "sourceDirectorySha256": "b" * 64,
        "sourceSequence": "2",
        "sourceOracleChecksum": "a" * 64,
    }
    return source, migration, target, rollback


def valid_member(source: str, slot: int) -> dict[str, object]:
    configuration = dict(PLAN)
    configuration.update({
        "javaProfile": "production",
        "durationSeconds": 1800,
        "slot": slot,
    })
    return {
        "kind": "v42-storage-evolution-replacement-host",
        "status": "PASS",
        "sourceCommit": source,
        "sourceState": "clean",
        "suite": SUITE,
        "preset": PRESET,
        "profile": "canonical",
        "case": {"caseId": f"migration-member-{slot}", "slot": slot,
                 "serial": True, "replacementHost": True},
        "configuration": configuration,
        "source": {"bytesUnchanged": True},
        "target": {},
        "migration": {
            "sourcePreserved": True,
            "planDigest": "gse-migration-plan-v1-" + str(slot) * 64,
            "targetHistory": f"target-history-{slot}",
        },
        "rollback": {"publishedVersion": "4.1.0",
                     "untouchedSourceReopened": True},
        "process": {"provider": "gcp"},
        "lifecycle": [
            "source-before-identity-recorded",
            "migration-planned",
            "migration-applied-to-absent-target",
            "source-after-identity-matched",
            "target-continued-and-checkpointed",
            "target-second-reopen-passed",
            "published-4.1-source-reopen-passed",
            "cleanup-verified-before-next-member",
        ],
        "cleanup": {
            "status": "PASS", "leftovers": [],
            "sourceVmDeleted": True,
            "replacementTargetVmDeleted": True,
            "rollbackVmDeleted": True,
            "sourceDiskDeleted": True,
            "targetDiskDeleted": True,
            "stagingObjectDeleted": True,
        },
        "logs": {"stdoutTail": "", "stderrTail": "",
                 "limitBytesPerStream": 16384},
        "result": {"replacementHostProven": True,
                   "eligibleForCanonicalRegistration": True},
    }


class Phase6EvidenceTest(unittest.TestCase):
    def test_frozen_profiles_plan_and_summary(self) -> None:
        self.assertEqual(1, validate_inputs(
            "experiment", 1, 1800, "actions", "c3d-standard-30",
            "standard")["repeats"])
        self.assertEqual(3, validate_inputs(
            "canonical", 3, 1800, "gcs", "c3d-standard-30",
            "standard")["repeats"])
        self.assertEqual(1, validate_inputs(
            "failure-drill", 1, 1800, "actions", "c3d-standard-30",
            "standard")["repeats"])
        document = {
            "schemaVersion": SCHEMA, "suite": SUITE, "preset": PRESET,
            "sourceCommit": "a" * 40, "trustedRef": "origin/master",
            "runId": "1234",
            "request": {"profile": "canonical", "repeats": 3,
                        "durationSeconds": 1800, "retention": "gcs",
                        "machineType": "c3d-standard-30",
                        "provisioning": "standard"},
            "slots": [1, 2, 3],
            "resources": {
                "sourceDiskType": "pd-balanced", "sourceDiskGiB": 200,
                "targetDiskType": "pd-balanced", "targetDiskGiB": 200,
                "peakRegionalSsdGiB": 400, "peakProjectVcpus": 30,
                "filesystem": "ext4", "mountOptions": "defaults",
                "maximumMemberRuntimeSeconds": 5400,
                "maximumRunCostUsd": 25, "serialMembers": True,
                "publishedRollbackVersion": "4.1.0",
            },
        }
        self.assertEqual(document, validate_plan(document))
        summary = render_summary(document)
        self.assertIn("| Run | `1234` |", summary)
        self.assertIn("| Peak quota | `30 vCPU / 400 GiB regional SSD` |", summary)
        for changed in (("canonical", 1, 1800, "gcs"),
                        ("canonical", 3, 120, "gcs"),
                        ("canonical", 3, 1800, "actions"),
                        ("failure-drill", 1, 1800, "gcs")):
            with self.assertRaises(EvidenceError):
                validate_inputs(*changed, "c3d-standard-30", "standard")

    def test_stage_properties_bind_source_target_and_published_rollback(self) -> None:
        source, migration, target, rollback = valid_properties()
        self.assertEqual(1000, validate_properties(
            source, migration, target, rollback, "smoke", 1)["documents"])
        changed = dict(rollback)
        changed["publishedVersion"] = "4.2.0-SNAPSHOT"
        with self.assertRaises(EvidenceError):
            validate_properties(source, migration, target, changed, "smoke", 1)
        changed_source = dict(migration)
        changed_source["migration.sourceDirectorySha256After"] = "9" * 64
        with self.assertRaises(EvidenceError):
            validate_properties(source, changed_source, target, rollback, "smoke", 1)

    def test_partial_disk_creation_failure_is_owned_and_cleaned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_gcloud = fake_bin / "gcloud"
            fake_gcloud.write_text("""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$FAKE_GCLOUD_LOG"
state_name() { printf '%s/%s-%s' "$FAKE_GCLOUD_STATE" "$1" "$2"; }
if [[ "$1 $2 $3" == "compute instances describe" ]]; then
  test -f "$(state_name instance "$4")"
elif [[ "$1 $2 $3" == "compute disks describe" ]]; then
  test -f "$(state_name disk "$4")"
elif [[ "$1 $2 $3" == "compute disks create" ]]; then
  touch "$(state_name disk "$4")"
  exit 1
elif [[ "$1 $2 $3" == "compute disks delete" ]]; then
  rm -f "$(state_name disk "$4")"
elif [[ "$1 $2 $3" == "storage objects describe" ]]; then
  exit 1
elif [[ "$1 $2" == "storage cp" ]]; then
  if [[ "$3" == gs://* ]]; then cp "$FAKE_GCS_OBJECT" "$4"; else cp "$3" "$FAKE_GCS_OBJECT"; fi
elif [[ "$1 $2" == "storage rm" ]]; then
  rm -f "$FAKE_GCS_OBJECT"
elif [[ "$1 $2" == "storage ls" ]]; then
  exit 1
else
  echo "unexpected fake gcloud command: $*" >&2
  exit 99
fi
""", encoding="utf-8")
            fake_gcloud.chmod(0o755)
            state = root / "state"
            state.mkdir()
            output = root / "output"
            environment = dict(os.environ)
            environment.update({
                "PATH": f"{fake_bin}:{environment['PATH']}",
                "FAKE_GCLOUD_LOG": str(root / "gcloud.log"),
                "FAKE_GCLOUD_STATE": str(state),
                "FAKE_GCS_OBJECT": str(root / "object"),
                "GSE_V42_GCP_PROJECT": "gse-benchmark",
                "GSE_V42_GCP_ZONE": "us-west4-a",
                "GSE_V42_CLOUD_IMAGE": "ubuntu-test-image",
                "GSE_V42_GCS_BUCKET": "gs://gse-test-bucket",
                "GSE_V42_SOURCE_SHA": "a" * 40,
                "GSE_V42_RUN_ID": "123456789",
                "GSE_V42_RUN_ATTEMPT": "1",
                "GSE_V42_SLOT": "1",
                "GSE_V42_PROFILE": "experiment",
                "GSE_V42_DURATION_SECONDS": "1800",
                "GSE_V42_OUTPUT": str(output),
            })
            runner = Path(__file__).resolve().parent / \
                "run_storage_evolution_cloud_member.sh"
            completed = subprocess.run(
                [str(runner), "--confirm-paid-run"], env=environment,
                check=False, capture_output=True, text=True)
            self.assertEqual(10, completed.returncode, completed.stderr)
            self.assertEqual([], list(state.iterdir()))
            receipt = (output / "cloud-member.properties").read_text("ascii")
            self.assertIn("sourceDiskDeleted=PASS", receipt)
            self.assertIn("targetDiskDeleted=NOT_APPLICABLE", receipt)
            self.assertIn("cleanup=PASS", receipt)

    def test_runner_and_workflow_preserve_serial_quota_boundary(self) -> None:
        root = Path(__file__).resolve().parents[2]
        runner = (root / "scripts/v42/run_storage_evolution_cloud_member.sh") \
            .read_text("utf-8")
        workflow = (root / ".github/workflows/v42-storage-evolution-evidence.yml") \
            .read_text("utf-8")
        remote = (root / "scripts/v42/remote_storage_evolution_stage.sh") \
            .read_text("utf-8")
        self.assertLess(runner.index('probe_uri="$staging_uri/permission-probe.txt"'),
                        runner.index('if create_disk "$source_disk"'))
        self.assertIn("max-parallel: 1", workflow)
        self.assertIn("peakRegionalSsdGiB", root.joinpath(
            "scripts/v42/migration_cloud_workflow.py").read_text("utf-8"))
        self.assertIn("36aa783cef653ead26d2500a847b70bb1f8222d224c8a83de55419de46814bcb",
                      remote)
        self.assertIn("PublishedV41MigrationCloudProbe", remote)

    def test_canonical_set_and_registration_are_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = "b" * 40
            for slot in range(1, 4):
                member = root / "members" / f"member-{slot}"
                write_bundle(member / "evidence", valid_member(source, slot))
                (member / "cloud-member.properties").write_text(
                    f"sourceCommit={source}\nprofile=canonical\nslot={slot}\n"
                    "runStatus=PASS\nsourceVmDeleted=PASS\n"
                    "replacementTargetVmDeleted=PASS\nrollbackVmDeleted=PASS\n"
                    "sourceDiskDeleted=PASS\ntargetDiskDeleted=PASS\n"
                    "stagingObjectDeleted=PASS\ncleanup=PASS\n",
                    encoding="ascii")
            set_bundle = root / "set"
            self.assertEqual(0, assemble(Namespace(
                members_root=root / "members", profile="canonical",
                expected_members=3, output=set_bundle)))
            self.assertTrue(validate_set(set_bundle)["canonicalEligible"])
            registry = root / "registry.json"
            registration = Namespace(
                name=BASELINE, set_bundle=set_bundle, registry=registry)
            self.assertEqual(0, register(registration))
            self.assertEqual(
                BASELINE, read_registry(registry)["baselines"][0]["name"])
            with self.assertRaises(EvidenceError):
                register(registration)


if __name__ == "__main__":
    unittest.main()
