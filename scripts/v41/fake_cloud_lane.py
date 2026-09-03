#!/usr/bin/env python3
"""No-GCP lifecycle model for the V4.1 source-loss lane."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.v41.evidence import EvidenceError, validate_bundle, validate_source, write_bundle
from scripts.v41.operational_harness import base_document

PROFILES = {"experiment": 1, "canonical": 3, "failure-drill": 1}
PLAN = {
    "documents": 100_000,
    "tokensPerDocument": 16,
    "preBackupMutations": 10_000,
    "continuedMutations": 1_000,
    "durationSeconds": 1_800,
    "maximumMemberRuntimeSeconds": 5_400,
    "machineType": "c3d-standard-30",
    "provisioning": "standard",
    "diskType": "pd-balanced",
    "sourceDiskGiB": 200,
    "restoreDiskGiB": 200,
    "filesystem": "ext4",
    "mountOptions": "defaults",
    "maximumRunCostUsd": 25,
    "gcsLayout": (
        "v4.1-operational-safety/<source-sha>/<run-id>-<attempt>/"
        "<profile>/member-<slot>/"
    ),
}


def fake_run(arguments: argparse.Namespace) -> int:
    validate_source(arguments.source_sha)
    if arguments.output.exists():
        raise EvidenceError("output already exists")
    slots = PROFILES[arguments.profile]
    lifecycle = [
        "exact-source-validated",
        "budget-ceiling-validated",
        "source-disk-created",
        "source-vm-created",
        "source-store-mutated",
        "backup-cut-selected",
        "backup-structurally-verified",
        "bundle-upload-simulated",
        "source-vm-deleted",
        "source-disk-deleted",
        "source-unavailable-proven",
        "restore-disk-created",
        "replacement-vm-created",
        "bundle-download-simulated",
        "independent-byte-verification-passed",
        "new-history-restore-model-passed",
        "continued-mutation-model-passed",
        "second-reopen-model-passed",
        "evidence-upload-simulated",
        "replacement-vm-deleted",
        "restore-disk-deleted",
        "staging-object-deleted",
        "cleanup-verified",
    ]
    evidence = base_document(
        arguments.source_sha, arguments.source_state, arguments.profile)
    evidence.update({
        "kind": "fake-cloud-operational-safety",
        "case": {"caseId": f"fake-{arguments.profile}", "memberCount": slots,
                 "serialMembers": True, "sourceLoss": True},
        "configuration": dict(PLAN),
        "backup": {"status": "MODEL_PASS", "format": "gse-backup (1,0)",
                   "sequence": 10_000,
                   "contentIdentity": "gse-backup-v1-" + "4" * 64,
                   "transport": "SIMULATED_GCS"},
        "verification": {"status": "SCAFFOLD_PASS", "parser": "independent",
                         "structural": "PASS", "semantic": "MODEL_PASS"},
        "restore": {"status": "MODEL_PASS", "newHistory": True,
                    "sourceVmAvailable": False, "sourceDiskAvailable": False,
                    "continuedMutation": "MODEL_PASS", "secondReopen": "MODEL_PASS"},
        "process": {"provider": "fake-gcp", "serialMembers": slots,
                    "paidExecution": False},
        "lifecycle": lifecycle,
        "cleanup": {"status": "PASS", "leftovers": [],
                    "sourceVmDeleted": True, "sourceDiskDeleted": True,
                    "replacementVmDeleted": True, "restoreDiskDeleted": True,
                    "stagingObjectDeleted": True},
        "result": {"paidExecution": False, "sourceLossProven": True,
                   "quotaSafeSerialExecution": True, "members": slots,
                   "cleanup": "PASS"},
    })
    write_bundle(arguments.output, evidence)
    validate_bundle(arguments.output)
    print(f"v41FakeCloud=PASS profile={arguments.profile} members={slots}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    arguments = parser.parse_args()
    return fake_run(arguments)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as failure:
        print(f"v41FakeCloud=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
