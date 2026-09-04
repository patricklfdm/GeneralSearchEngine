#!/usr/bin/env python3
"""No-GCP control-plane model for the V4.2 storage-evolution lane."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.v42.evidence import EvidenceError, validate_bundle, validate_source, write_bundle
from scripts.v42.migration_harness import base_document

PROFILES = {"experiment": 1, "canonical": 3, "failure-drill": 1}
PLAN = {
    "documents": 100_000,
    "tokensPerDocument": 16,
    "preMigrationMutations": 10_000,
    "continuedTargetMutations": 1_000,
    "measurementSeconds": 1_800,
    "maximumMemberRuntimeSeconds": 5_400,
    "machineType": "c3d-standard-30",
    "provisioning": "standard",
    "diskType": "pd-balanced",
    "sourceDiskGiB": 200,
    "targetDiskGiB": 200,
    "peakRegionalSsdGiB": 400,
    "peakProjectVcpus": 30,
    "filesystem": "ext4",
    "mountOptions": "defaults",
    "transforms": ["identity-format-v1", "catalog-schema-key-v1"],
    "maximumCompleteRunCostUsd": 25,
    "retention": {"experiment": "actions", "canonical": "gcs",
                  "failure-drill": "actions"},
    "gcsLayout": (
        "v4.2-storage-evolution/<source-sha>/<run-id>-<attempt>/"
        "<profile>/member-<slot>/"
    ),
    "workflowRef": (
        "patricklfdm/GeneralSearchEngine/.github/workflows/"
        "v42-storage-evolution-evidence.yml@refs/heads/master"
    ),
    "environment": "cloud-benchmark",
    "publishedRollbackVersion": "4.1.0",
}


def fake_run(arguments: argparse.Namespace) -> int:
    validate_source(arguments.source_sha)
    if arguments.output.exists():
        raise EvidenceError("output already exists")
    slots = PROFILES[arguments.profile]
    lifecycle = [
        "exact-source-validated",
        "cost-and-quota-plan-validated",
        "source-disk-created",
        "source-vm-created",
        "published-compatible-source-materialized",
        "source-mutated-checkpointed-closed",
        "source-backup-verified",
        "source-before-identity-recorded",
        "source-writer-stopped",
        "target-disk-created",
        "migration-plan-model-validated",
        "migration-apply-model-validated",
        "source-after-identity-matched",
        "target-writer-vm-created",
        "target-independent-verification-passed",
        "target-writer-vm-deleted",
        "target-disk-preserved",
        "replacement-target-vm-created",
        "target-disk-attached-replacement",
        "target-reopen-and-continued-mutation-passed",
        "replacement-target-vm-deleted",
        "target-writer-stopped-before-rollback",
        "published-4.1-source-rollback-model-passed",
        "evidence-upload-simulated",
        "target-disk-deleted",
        "source-disk-deleted",
        "staging-objects-deleted",
        "local-artifacts-deleted",
        "cleanup-verified-before-next-member",
    ]
    evidence = base_document(
        arguments.source_sha, arguments.source_state, arguments.profile)
    evidence.update({
        "kind": "fake-cloud-storage-evolution",
        "case": {"caseId": f"fake-{arguments.profile}",
                 "memberCount": slots, "serialMembers": True,
                 "sourceAndTargetWritersConcurrent": False},
        "configuration": dict(PLAN),
        "source": {"format": "gse-durable (1,0)",
                   "history": "SOURCE_MODEL", "sequence": 10_000,
                   "beforeSha256": "1" * 64, "afterSha256": "1" * 64,
                   "bytesUnchanged": True, "backup": "MODEL_PASS",
                   "published41Rollback": "MODEL_PASS"},
        "target": {"format": "gse-durable (1,1)",
                   "history": "DISTINCT_TARGET_MODEL", "sequence": 10_000,
                   "replacementHost": True,
                   "continuedMutations": 1_000,
                   "secondReopen": "MODEL_PASS"},
        "migration": {"plan": "MODEL_PASS", "apply": "MODEL_PASS",
                      "transformIdentities": list(PLAN["transforms"]),
                      "sourcePreserved": True,
                      "productionOperations": False},
        "rollback": {"publishedVersion": "4.1.0",
                     "targetWriterStopped": True,
                     "untouchedSourceReopened": "MODEL_PASS",
                     "targetOnlyWritesMerged": False},
        "process": {"provider": "fake-gcp", "members": slots,
                    "serial": True, "paidExecution": False},
        "lifecycle": lifecycle,
        "cleanup": {"status": "PASS", "leftovers": [],
                    "sourceVmDeleted": True, "targetVmDeleted": True,
                    "replacementTargetVmDeleted": True,
                    "sourceDiskDeleted": True, "targetDiskDeleted": True,
                    "stagingObjectsDeleted": True,
                    "localArtifactsDeleted": True,
                    "verifiedBeforeNextMember": True},
        "result": {"paidExecution": False, "productionMigration": False,
                   "quotaSafeSerialExecution": True, "members": slots,
                   "cleanup": "PASS"},
    })
    write_bundle(arguments.output, evidence)
    validate_bundle(arguments.output)
    print(f"v42FakeCloud=PASS profile={arguments.profile} members={slots}")
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
        print(f"v42FakeCloud=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
