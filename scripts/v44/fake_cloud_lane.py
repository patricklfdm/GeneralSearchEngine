#!/usr/bin/env python3
"""No-GCP serial control-plane model for V4.4 final durable evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.v44.evidence import (
    EvidenceError, base_document, validate_bundle, validate_source, write_bundle,
)

PLAN_PATH = Path(__file__).resolve().parents[2] / "docs/v4x/v4.4/phase1-plan.json"
PROFILES = {"experiment": 1, "canonical": 3, "failure-drill": 1}


def load_plan() -> dict[str, object]:
    value = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    if value.get("schemaVersion") != "gse-v44-phase1-plan-v1":
        raise EvidenceError("plan identity differs")
    return value


def fake_run(arguments: argparse.Namespace) -> int:
    validate_source(arguments.source_sha)
    if arguments.output.exists():
        raise EvidenceError("output already exists")
    plan = load_plan()
    members = PROFILES[arguments.profile]
    lifecycle = [
        "exact-source-and-published-control-validated",
        "budget-quota-retention-and-toolchain-validated",
        "member-started-after-prior-cleanup",
        "source-disk-created", "source-host-created",
        "authority-and-pre-interruption-oracle-materialized",
        "source-host-deleted", "independent-pre-open-inspection-recorded",
        "replacement-host-created", "recovery-restore-migration-matrix-recorded",
        "continued-mutation-checkpoint-close-second-reopen-recorded",
        "replacement-host-deleted", "target-disk-deleted",
        "source-disk-deleted", "staging-objects-deleted",
        "cleanup-verified-before-next-member",
    ]
    evidence = base_document(arguments.source_sha, arguments.source_state,
                             arguments.profile)
    evidence.update({
        "kind": "fake-cloud-final-durable",
        "case": {"caseId": f"fake-{arguments.profile}",
                 "memberCount": members, "serialMembers": True,
                 "matrixFamilies": plan["matrixFamilies"]},
        "configuration": {"productionChange": False, "paidExecution": False,
                          "plan": plan},
        "authority": {"canonical": "VALID", "derived": "MODELLED",
                      "published43Control": "MODEL_PASS",
                      "continuation": "MODEL_PASS"},
        "process": {"provider": "fake-gcp", "members": members,
                    "serial": True, "replacementHost": True,
                    "sourceHostDeleted": True},
        "lifecycle": lifecycle,
        "measurements": {"members": members, "paidExecution": False,
                         "peakProjectVcpus": plan["cloud"]["peakProjectVcpus"],
                         "peakProvisionedDiskGiB":
                             plan["cloud"]["peakProvisionedDiskGiB"]},
        "cleanup": {"status": "PASS", "leftovers": [],
                    "sourceVmDeleted": True, "replacementVmDeleted": True,
                    "sourceDiskDeleted": True, "targetDiskDeleted": True,
                    "stagingObjectsDeleted": True,
                    "verifiedBeforeNextMember": True},
        "logs": {"stdoutTail": "", "stderrTail": "",
                 "limitBytesPerStream": 4096},
        "result": {"productionChange": False, "paidExecution": False,
                   "quotaSafeSerialExecution": True, "cleanup": "PASS"},
    })
    write_bundle(arguments.output, evidence)
    validate_bundle(arguments.output)
    print(f"v44FakeCloud=PASS profile={arguments.profile} members={members}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    parser.add_argument("--profile", choices=tuple(PROFILES), required=True)
    return fake_run(parser.parse_args())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, json.JSONDecodeError) as failure:
        print(f"v44FakeCloud=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
