#!/usr/bin/env python3
"""No-GCP Phase 1 control-plane model for the V4 durable cloud lane."""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from scripts.v4.evidence import (
    EvidenceError,
    validate_bundle,
    validate_source_commit,
    write_bundle,
)

SUITE = "v4.0-durable-single-node-suite-v1"
PRESET = "v4.0-durable-single-node-v1"
PROFILES = {"experiment": 1, "canonical": 3, "failure-drill": 1}


def fake_run(arguments: argparse.Namespace) -> int:
    if arguments.output.exists():
        raise EvidenceError("fake-cloud output already exists")
    slots = PROFILES[arguments.profile]
    lifecycle = [
        "plan-validated",
        "budget-accepted",
        "persistent-disk-created",
        "writer-vm-created",
        "persistent-disk-attached-writer",
        "writer-barrier-acknowledged",
        "writer-vm-terminated-abruptly",
        "persistent-disk-preserved",
        "recovery-vm-created",
        "persistent-disk-attached-recovery",
        "recovery-verified",
        "evidence-upload-simulated",
        "recovery-vm-deleted",
        "persistent-disk-deleted",
        "cleanup-verified",
    ]
    evidence = {
        "kind": "fake-cloud-durable-lane",
        "status": "PASS",
        "sourceCommit": arguments.source_sha,
        "environment": {
            "sourceState": arguments.source_state,
            "provider": "fake-gcp",
            "suite": SUITE,
            "preset": PRESET,
            "profile": arguments.profile,
            "slots": slots,
            "machine": "c3d-standard-30",
            "disk": "pd-balanced",
            "python": platform.python_version(),
        },
        "configuration": {
            "image": "fake-pinned-image-v1",
            "zone": "fake-zone-a",
            "filesystem": "fake-ext4",
            "mountOptions": "defaults",
            "diskSizeGiB": 100,
            "maximumCostUsd": 0,
            "codecIdentity": "PHASE1_NONE",
            "schemaIdentity": "PHASE1_SCAFFOLD_V1",
            "storageIdentity": "PHASE1_FAKE_PERSISTENT_DISK",
        },
        "case": {
            "caseId": f"phase1-fake-cloud-{arguments.profile}",
            "seed": 0,
            "barrierId": "phase1-fake-writer-barrier-v1",
            "acknowledgement": "SIMULATED",
        },
        "submittedHistory": [],
        "futureOutcomes": [],
        "process": {
            "writerVm": "SIMULATED",
            "recoveryVm": "SIMULATED",
            "termination": "SIMULATED_ABRUPT_VM_TERMINATION",
            "exitCode": "NOT_APPLICABLE",
            "gracefulCloseRan": False,
        },
        "inspection": {
            "persistentDiskSurvivedWriter": True,
            "bootDiskUsedAsEvidence": False,
            "storageBytes": "PHASE1_NONE",
        },
        "recovery": {
            "verifier": "fake-control-plane",
            "status": "PASS",
            "metrics": {},
            "result": "SIMULATED",
        },
        "logs": {
            "stdoutTail": "",
            "stderrTail": "",
            "limitBytesPerStream": 4096,
        },
        "cleanup": {
            "status": "PASS",
            "leftovers": [],
            "verified": True,
        },
        "lifecycle": lifecycle,
        "result": {
            "paidExecution": False,
            "persistentDiskSurvivedWriter": True,
            "bootDiskUsedAsEvidence": False,
            "gcsUpload": "SIMULATED",
            "cleanup": "PASS",
            "leftovers": [],
        },
    }
    write_bundle(arguments.output, evidence)
    validate_bundle(arguments.output)
    print(f"v40FakeCloud=PASS profile={arguments.profile} slots={slots}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    arguments = parser.parse_args()
    validate_source_commit(arguments.source_sha)
    return fake_run(arguments)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as failure:
        print(f"v40FakeCloud=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
