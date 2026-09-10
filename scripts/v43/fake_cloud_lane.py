#!/usr/bin/env python3
"""No-GCP serial control-plane model for the V4.3 fast-reopen lane."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.v43.evidence import (
    EvidenceError, base_document, validate_bundle, validate_source, write_bundle,
)

PROFILES = {"experiment": 1, "canonical": 3, "failure-drill": 1}
CELLS = [
    "published-4.2-forced-canonical-rebuild",
    "current-1.2-forced-full-rebuild",
    "complete-warm-reopen",
    "structured-component-partial-fallback",
    "text-component-partial-fallback",
    "catalog-full-fallback",
    "complete-warm-checkpoint-plus-wal",
    "restored-target-cold-then-warm",
    "migrated-target-cold-then-replacement-warm",
    "continued-mutation-index-lifecycle-reopen",
]
PLAN = {
    "documents": 100_000,
    "tokensPerDocument": 16,
    "indexes": ["equality", "range", "prefix", "simple-text"],
    "mutations": 10_000,
    "measurementSeconds": 1_800,
    "maximumMemberRuntimeSeconds": 5_400,
    "machineType": "c3d-standard-30",
    "provisioning": "standard",
    "diskType": "pd-balanced",
    "dataDiskGiB": 200,
    "transientTargetDiskGiB": 200,
    "bootDiskGiB": 100,
    "peakDataDiskGiB": 400,
    "peakProvisionedDiskGiB": 500,
    "peakProjectVcpus": 30,
    "filesystem": "ext4",
    "mountOptions": "defaults",
    "maximumCompleteRunCostUsd": 25,
    "retention": {"experiment": "actions", "canonical": "gcs",
                  "failure-drill": "actions"},
    "gcsLayout": (
        "v4.3-fast-reopen/<source-sha>/<run-id>-<attempt>/"
        "<profile>/member-<slot>/"
    ),
    "workflowRef": (
        "patricklfdm/GeneralSearchEngine/.github/workflows/"
        "v43-fast-reopen-evidence.yml@refs/heads/master"
    ),
    "environment": "cloud-benchmark",
    "publishedControlVersion": "4.2.0",
    "artifactSchema": "gse-v43-fast-reopen-evidence-v1",
    "warmMedianMaximumRatio": 0.50,
    "warmMemberMaximumRatio": 0.65,
    "cells": CELLS,
}


def fake_run(arguments: argparse.Namespace) -> int:
    validate_source(arguments.source_sha)
    if arguments.output.exists():
        raise EvidenceError("output already exists")
    members = PROFILES[arguments.profile]
    lifecycle = [
        "exact-source-validated",
        "cost-quota-and-retention-validated",
        "member-started-after-prior-cleanup",
        "fresh-data-disk-created",
        "source-host-created",
        "canonical-store-materialized",
        "forced-cold-control-recorded",
        "source-host-deleted",
        "data-disk-preserved",
        "replacement-host-created",
        "warm-and-fallback-model-cells-recorded",
        "replacement-host-deleted",
        "transient-restore-migration-disks-run-serially",
        "evidence-upload-simulated",
        "all-disks-deleted",
        "staging-objects-deleted",
        "cleanup-verified-before-next-member",
    ]
    evidence = base_document(arguments.source_sha, arguments.source_state,
                             arguments.profile)
    evidence.update({
        "kind": "fake-cloud-fast-reopen",
        "case": {"caseId": f"fake-{arguments.profile}",
                 "memberCount": members, "serialMembers": True,
                 "cells": list(CELLS)},
        "configuration": dict(PLAN),
        "canonical": {"authority": "VALID", "bytesUnchanged": True,
                      "published42Control": "MODEL_PASS",
                      "walContinuity": "MODEL_PASS"},
        "derived": {"classification": "MODEL_MATRIX",
                    "productionBytes": False,
                    "outcomes": ["COMPLETE_WARM", "PARTIAL_FALLBACK",
                                 "FULL_FALLBACK", "NOT_APPLICABLE"],
                    "forcedRebuildControlIsBenchmarkOnly": True},
        "process": {"provider": "fake-gcp", "members": members,
                    "serial": True, "replacementHost": True,
                    "paidExecution": False},
        "lifecycle": lifecycle,
        "cleanup": {"status": "PASS", "leftovers": [],
                    "sourceVmDeleted": True, "replacementVmDeleted": True,
                    "dataDiskDeleted": True, "transientDisksDeleted": True,
                    "stagingObjectsDeleted": True,
                    "verifiedBeforeNextMember": True},
        "result": {"paidExecution": False, "productionDerivedState": False,
                   "quotaSafeSerialExecution": True, "members": members,
                   "cleanup": "PASS"},
    })
    write_bundle(arguments.output, evidence)
    validate_bundle(arguments.output)
    print(f"v43FakeCloud=PASS profile={arguments.profile} members={members}")
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
        print(f"v43FakeCloud=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
