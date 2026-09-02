#!/usr/bin/env python3
"""Validated manual workflow plan for the independent V4 durable cloud lane."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.v4.durable_cloud_lane import PRESET, SUITE
from scripts.v4.evidence import EvidenceError, canonical_json, validate_source_commit

PROFILE_REPEATS = {"experiment": 1, "canonical": 3, "failure-drill": 1}
PROFILE_DURATIONS = {
    "experiment": {120, 1800},
    "canonical": {1800, 7200},
    "failure-drill": {120},
}


def validate_inputs(
    profile: str,
    repeats: int,
    duration_seconds: int,
    retention: str,
    machine_type: str,
    provisioning: str,
) -> dict[str, Any]:
    if profile not in PROFILE_REPEATS:
        raise EvidenceError("unsupported V4 durable cloud profile")
    if repeats != PROFILE_REPEATS[profile]:
        raise EvidenceError(
            f"{profile} requires exactly {PROFILE_REPEATS[profile]} member(s)")
    if duration_seconds not in PROFILE_DURATIONS[profile]:
        raise EvidenceError(f"duration is not allowed for {profile}")
    if retention not in {"actions", "gcs"}:
        raise EvidenceError("retention must be actions or gcs")
    if profile in {"canonical", "failure-drill"} and retention != "gcs":
        raise EvidenceError(f"{profile} requires GCS retention")
    if machine_type != "c3d-standard-30":
        raise EvidenceError("V4 durable evidence requires c3d-standard-30")
    if provisioning != "standard":
        raise EvidenceError("V4 durable evidence requires Standard provisioning")
    return {
        "profile": profile,
        "repeats": repeats,
        "durationSeconds": duration_seconds,
        "retention": retention,
        "machineType": machine_type,
        "provisioning": provisioning,
    }


def git_output(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise EvidenceError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def write_github_output(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            if not re.fullmatch(r"[a-z_]+", key) or "\n" in value or "\r" in value:
                raise EvidenceError("invalid GitHub output value")
            stream.write(f"{key}={value}\n")


def plan(arguments: argparse.Namespace) -> int:
    request = validate_inputs(
        arguments.profile,
        arguments.repeats,
        arguments.duration_seconds,
        arguments.retention,
        arguments.machine_type,
        arguments.provisioning,
    )
    root = arguments.repository_root.resolve()
    trusted_sha = validate_source_commit(
        git_output(root, "rev-parse", f"{arguments.trusted_ref}^{{commit}}"))
    requested = arguments.source_commit or arguments.dispatch_sha
    source_commit = validate_source_commit(
        git_output(root, "rev-parse", f"{requested}^{{commit}}"))
    if source_commit != trusted_sha:
        raise EvidenceError(
            "V4 durable cloud source must equal the exact protected-master tip")
    if not re.fullmatch(r"[0-9]+", arguments.run_id):
        raise EvidenceError("run ID must be numeric")
    maximum_runtime = arguments.duration_seconds + 3600
    document = {
        "schemaVersion": "gse-v40-durable-cloud-plan-v1",
        "suite": SUITE,
        "preset": PRESET,
        "sourceCommit": source_commit,
        "trustedRef": arguments.trusted_ref,
        "runId": arguments.run_id,
        "request": request,
        "slots": list(range(1, arguments.repeats + 1)),
        "resources": {
            "diskType": "pd-balanced",
            "diskSizeGiB": 200,
            "filesystem": "ext4",
            "mountOptions": "defaults",
            "maximumRuntimeSeconds": maximum_runtime,
        },
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(canonical_json(document))
    if arguments.github_output is not None:
        write_github_output(arguments.github_output, {
            "source_commit": source_commit,
            "slots": json.dumps(document["slots"], separators=(",", ":")),
            "duration_seconds": str(arguments.duration_seconds),
            "maximum_runtime_seconds": str(maximum_runtime),
            "profile": arguments.profile,
            "retention": arguments.retention,
        })
    print(
        "v40CloudPlan=PASS "
        f"profile={arguments.profile} slots={arguments.repeats} "
        f"source={source_commit}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    command = subparsers.add_parser("plan")
    command.add_argument("--profile", required=True)
    command.add_argument("--repeats", type=int, required=True)
    command.add_argument("--duration-seconds", type=int, required=True)
    command.add_argument("--retention", required=True)
    command.add_argument("--machine-type", required=True)
    command.add_argument("--provisioning", required=True)
    command.add_argument("--source-commit", default="")
    command.add_argument("--dispatch-sha", required=True)
    command.add_argument("--repository-root", type=Path, required=True)
    command.add_argument("--trusted-ref", required=True)
    command.add_argument("--run-id", required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--github-output", type=Path)
    arguments = parser.parse_args()
    return plan(arguments)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as failure:
        print(f"v40CloudPlan=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
