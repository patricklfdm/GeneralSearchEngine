from __future__ import annotations

import json
import os
import subprocess
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
from scripts.v41.operational_evidence import validate_properties


def valid_operational_properties() -> tuple[dict[str, str], dict[str, str]]:
    common = {
        "schemaVersion": "gse-v41-operational-properties-v1",
        "status": "PASS",
        "profile": "smoke",
        "documents": "1000",
        "tokensPerDocument": "16",
        "preBackupMutations": "100",
        "continuedMutations": "20",
        "measurementSeconds": "1",
        "codecId": "v41-operational-codec-v1",
        "codecVersion": "1",
        "storageIdentity": "v41-operational-store-v1",
        "schemaIdentity": "v41-operational-schema-v1",
        "processCpuNanosAtStart": "0",
        "processCpuNanosAtEnd": "1",
    }
    source = {
        **common,
        "stage": "source",
        "backup.elapsedNanos": "1",
        "backup.totalBytes": "10",
        "backup.peakObservedBytes": "20",
        "backup.semanticDocuments": "1000",
        "backup.status": "PASS",
        "backup.structuralStatus": "VALID",
        "backup.semanticStatus": "SEMANTICALLY_VALID",
        "backup.sequence": "5",
        "backup.contentIdentity": "gse-backup-v1-" + "a" * 64,
        "backup.sourceHistory": "source-history",
        "source.loadNanos": "1",
        "source.preBackupMutationNanos": "1",
        "source.afterCutMutationNanos": "1",
        "source.impactReads": "1",
        "source.impactWrites": "1",
        "source.impactReadNanos": "1",
        "source.bytesBeforeBackup": "10",
        "source.retainedBytes": "1",
        "source.heapUsedBytes": "1",
        "source.totalNanos": "1",
        "source.afterCutSequence": "6",
        "oracle.cutChecksum": "b" * 64,
    }
    restore = {
        **common,
        "stage": "restore",
        "verification.elapsedNanos": "1",
        "verification.semanticDocuments": "1000",
        "verification.structuralStatus": "VALID",
        "verification.semanticStatus": "SEMANTICALLY_VALID",
        "restore.elapsedNanos": "1",
        "restore.authoritativeBytes": "1",
        "restore.firstOpenNanos": "1",
        "restore.continuedMutationNanos": "1",
        "restore.checkpointNanos": "1",
        "restore.retainedBytes": "1",
        "restore.heapUsedBytes": "1",
        "restore.secondOpenNanos": "1",
        "restore.finalDirectoryBytes": "1",
        "restore.sequence": "5",
        "restore.finalSequence": "6",
        "restore.sourceHistory": "source-history",
        "restore.newHistory": "restore-history",
        "measurement.reads": "1",
        "measurement.durationNanos": "1000000000",
        "measurement.readsPerSecondMicros": "1",
        "oracle.restoredChecksum": "b" * 64,
        "oracle.continuedChecksum": "c" * 64,
    }
    return source, restore


class Phase6EvidenceTest(unittest.TestCase):
    def test_synchronous_byte_baseline_is_required_and_bounds_peak(self) -> None:
        source, restore = valid_operational_properties()
        source_metrics, _ = validate_properties(source, restore, "smoke", 1)
        self.assertEqual(10, source_metrics["bytesBeforeBackup"])

        invalid_sources = []
        missing = dict(source)
        del missing["source.bytesBeforeBackup"]
        invalid_sources.append(missing)
        zero = dict(source)
        zero["source.bytesBeforeBackup"] = "0"
        invalid_sources.append(zero)
        peak_below_baseline = dict(source)
        peak_below_baseline["backup.peakObservedBytes"] = "9"
        invalid_sources.append(peak_below_baseline)
        for invalid in invalid_sources:
            with self.subTest(invalid=invalid):
                with self.assertRaises(EvidenceError):
                    validate_properties(invalid, restore, "smoke", 1)

    def test_delete_permission_failure_precedes_compute_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_gcloud = fake_bin / "gcloud"
            fake_gcloud.write_text("""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$FAKE_GCLOUD_LOG"
if [[ "$1 $2 $3" == "compute instances describe" \
    || "$1 $2 $3" == "compute disks describe" \
    || "$1 $2 $3" == "storage objects describe" ]]; then
  exit 1
fi
if [[ "$1 $2" == "storage cp" ]]; then
  if [[ "$3" == gs://* ]]; then
    cp "$FAKE_GCS_OBJECT" "$4"
  else
    cp "$3" "$FAKE_GCS_OBJECT"
  fi
  exit 0
fi
if [[ "$1 $2" == "storage rm" ]]; then
  exit 1
fi
echo "unexpected fake gcloud command: $*" >&2
exit 99
""", encoding="utf-8")
            fake_gcloud.chmod(0o755)
            log = root / "gcloud.log"
            output = root / "output"
            environment = dict(os.environ)
            environment.update({
                "PATH": f"{fake_bin}:{environment['PATH']}",
                "FAKE_GCLOUD_LOG": str(log),
                "FAKE_GCS_OBJECT": str(root / "object"),
                "GSE_V41_GCP_PROJECT": "gse-benchmark",
                "GSE_V41_GCP_ZONE": "us-west4-a",
                "GSE_V41_CLOUD_IMAGE": "ubuntu-test-image",
                "GSE_V41_GCS_BUCKET": "gs://gse-test-bucket",
                "GSE_V41_SOURCE_SHA": "c" * 40,
                "GSE_V41_RUN_ID": "123456789",
                "GSE_V41_RUN_ATTEMPT": "1",
                "GSE_V41_SLOT": "1",
                "GSE_V41_PROFILE": "experiment",
                "GSE_V41_DURATION_SECONDS": "1800",
                "GSE_V41_OUTPUT": str(output),
            })
            runner = (Path(__file__).resolve().parents[2] / "scripts" / "v41" /
                      "run_operational_cloud_member.sh")
            completed = subprocess.run(
                [str(runner), "--confirm-paid-run"], env=environment,
                check=False, capture_output=True, text=True)
            self.assertEqual(2, completed.returncode, completed.stderr)
            calls = log.read_text("utf-8")
            self.assertNotIn("compute disks create", calls)
            self.assertNotIn("compute instances create", calls)
            receipt = (output / "cloud-member.properties").read_text("ascii")
            self.assertIn("runStatus=FAIL", receipt)
            self.assertIn("stagingObjectDeleted=FAIL", receipt)
            self.assertIn("cleanup=FAIL", receipt)
            self.assertFalse((output / "gcs-transport-permission-probe.txt").exists())

    def test_early_remote_failure_treats_uncreated_resources_as_clean(self) -> None:
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
elif [[ "$1 $2 $3" == "compute instances create" ]]; then
  touch "$(state_name instance "$4")"
elif [[ "$1 $2 $3" == "compute instances delete" ]]; then
  rm -f "$(state_name instance "$4")"
elif [[ "$1 $2 $3" == "compute disks describe" ]]; then
  test -f "$(state_name disk "$4")"
elif [[ "$1 $2 $3" == "compute disks create" ]]; then
  touch "$(state_name disk "$4")"
elif [[ "$1 $2 $3" == "compute disks delete" ]]; then
  rm -f "$(state_name disk "$4")"
elif [[ "$1 $2 $3" == "storage objects describe" ]]; then
  exit 1
elif [[ "$1 $2" == "storage cp" ]]; then
  if [[ "$3" == gs://* ]]; then
    cp "$FAKE_GCS_OBJECT" "$4"
  else
    cp "$3" "$FAKE_GCS_OBJECT"
  fi
elif [[ "$1 $2" == "storage rm" ]]; then
  rm -f "$FAKE_GCS_OBJECT"
elif [[ "$1 $2" == "storage ls" ]]; then
  exit 1
elif [[ "$1 $2" == "compute scp" ]]; then
  exit 0
elif [[ "$1 $2" == "compute ssh" ]]; then
  for argument in "$@"; do
    [[ "$argument" == "--command=true" ]] && exit 0
  done
  exit 1
else
  echo "unexpected fake gcloud command: $*" >&2
  exit 99
fi
""", encoding="utf-8")
            fake_gcloud.chmod(0o755)
            state = root / "state"
            state.mkdir()
            log = root / "gcloud.log"
            output = root / "output"
            environment = dict(os.environ)
            environment.update({
                "PATH": f"{fake_bin}:{environment['PATH']}",
                "FAKE_GCLOUD_LOG": str(log),
                "FAKE_GCLOUD_STATE": str(state),
                "FAKE_GCS_OBJECT": str(root / "object"),
                "GSE_V41_GCP_PROJECT": "gse-benchmark",
                "GSE_V41_GCP_ZONE": "us-west4-a",
                "GSE_V41_CLOUD_IMAGE": "ubuntu-test-image",
                "GSE_V41_GCS_BUCKET": "gs://gse-test-bucket",
                "GSE_V41_SOURCE_SHA": "d" * 40,
                "GSE_V41_RUN_ID": "123456789",
                "GSE_V41_RUN_ATTEMPT": "1",
                "GSE_V41_SLOT": "1",
                "GSE_V41_PROFILE": "experiment",
                "GSE_V41_DURATION_SECONDS": "1800",
                "GSE_V41_OUTPUT": str(output),
            })
            runner = (Path(__file__).resolve().parents[2] / "scripts" / "v41" /
                      "run_operational_cloud_member.sh")
            completed = subprocess.run(
                [str(runner), "--confirm-paid-run"], env=environment,
                check=False, capture_output=True, text=True)
            self.assertEqual(20, completed.returncode, completed.stderr)
            receipt = (output / "cloud-member.properties").read_text("ascii")
            self.assertIn("runStatus=FAIL", receipt)
            self.assertIn("sourceVmDeleted=PASS", receipt)
            self.assertIn("sourceDiskDeleted=PASS", receipt)
            self.assertIn("replacementVmDeleted=NOT_APPLICABLE", receipt)
            self.assertIn("restoreDiskDeleted=NOT_APPLICABLE", receipt)
            self.assertIn("stagingObjectDeleted=NOT_APPLICABLE", receipt)
            self.assertIn("cleanup=PASS", receipt)
            self.assertEqual([], list(state.iterdir()))

    def test_paid_runner_preflights_transport_and_uses_instance_ssh_metadata(
            self) -> None:
        runner = (Path(__file__).resolve().parents[2] / "scripts" / "v41" /
                  "run_operational_cloud_member.sh").read_text("utf-8")
        probe = runner.index("probe_gcs_transport_permissions ||")
        first_disk = runner.index('if create_disk "$source_disk"')
        self.assertLess(probe, first_disk)
        self.assertIn("v41GcsTransportPermissionProbe=PASS", runner)
        self.assertIn(
            "--metadata=block-project-ssh-keys=TRUE,enable-oslogin=FALSE",
            runner)

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
