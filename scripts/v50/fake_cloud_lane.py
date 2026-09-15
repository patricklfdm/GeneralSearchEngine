"""No-GCP control plane for the frozen three-voter topology."""

from __future__ import annotations

import argparse
from pathlib import Path
from scripts.v50.evidence import write_bundle


PROFILE_REPEATS = {"experiment": 1, "failure-drill": 1, "canonical": 3}


def plan(profile: str) -> dict:
    if profile not in PROFILE_REPEATS:
        raise ValueError("unsupported profile")
    return {
        "schemaVersion": "gse-v50-cloud-plan-v1",
        "suite": "v5.0-replicated-single-shard-suite-v1",
        "preset": "v5.0-replicated-single-shard-v1",
        "profile": profile,
        "topologyRepeats": PROFILE_REPEATS[profile],
        "repeatsAreSerial": True,
        "votersPerTopology": 3,
        "votersConcurrent": True,
        "resources": {
            "vcpusPerVoter": 8,
            "peakVcpus": 24,
            "dataDiskGiBPerVoter": 100,
            "bootDiskGiBPerVoter": 50,
            "peakProvisionedDiskGiB": 450,
            "privateReplicationOnly": True,
        },
        "limits": {"maximumTopologyRuntimeSeconds": 5400,
                   "maximumCompleteRunCostUsd": 40},
    }


def run(output: Path, source_sha: str, profile: str, failure: str | None) -> None:
    topology = plan(profile)
    cleanup = [
        {"resource": f"node-{index}-vm", "deleted": True}
        for index in range(1, 4)
    ] + [
        {"resource": f"node-{index}-disk", "deleted": True}
        for index in range(1, 4)
    ] + [
        {"resource": "private-replication-firewall", "deleted": True},
        {"resource": "evidence-staging-prefix", "deleted": True},
    ]
    write_bundle(output, {
        "profile": profile,
        "sourceCommit": source_sha,
        "authorityClaim": "fake-control-plane-only",
        "plan": topology,
        "injectedFailure": failure,
        "runStatus": "FAIL" if failure else "PASS",
        "cleanup": cleanup,
        "cleanupStatus": "PASS",
    })
    print(f"v50FakeCloud=PASS profile={profile} cleanup=PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--profile", choices=tuple(PROFILE_REPEATS), required=True)
    parser.add_argument("--inject-failure", choices=("provision-node-2", "run-node-1"))
    args = parser.parse_args()
    run(args.output, args.source_sha, args.profile, args.inject_failure)


if __name__ == "__main__":
    main()
