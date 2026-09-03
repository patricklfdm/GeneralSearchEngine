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


class Phase6EvidenceTest(unittest.TestCase):
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
