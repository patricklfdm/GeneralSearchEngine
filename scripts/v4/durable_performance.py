#!/usr/bin/env python3
"""Run and validate the independent V4 durable operational evidence probe."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.v4.evidence import (
    EvidenceError,
    validate_bundle,
    validate_source_commit,
    write_bundle,
)

PROPERTIES_SCHEMA = "gse-v40-performance-properties-v1"
SUITE = "v4.0-durable-single-node-suite-v1"
PRESET = "v4.0-durable-single-node-v1"
JAVA_MAIN = (
    "io.github.patricklfdm.generalsearch.engine."
    "V40DurableOperationalProbe"
)
LOG_LIMIT = 64 * 1024


def parse_properties(path: Path) -> dict[str, str]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as failure:
        raise EvidenceError(f"cannot read performance properties: {failure}") from failure
    if len(content.encode("utf-8")) > 1024 * 1024:
        raise EvidenceError("performance properties exceed one MiB")
    result: dict[str, str] = {}
    for line_number, line in enumerate(content.splitlines(), start=1):
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise EvidenceError(
                f"invalid performance property at line {line_number}")
        key, value = line.split("=", 1)
        if not key or not value or key in result:
            raise EvidenceError(
                f"duplicate or empty performance property at line {line_number}")
        result[key] = value
    return result


def integer(properties: dict[str, str], key: str) -> int:
    try:
        value = int(properties[key])
    except (KeyError, ValueError) as failure:
        raise EvidenceError(f"missing or invalid integer property: {key}") from failure
    if value < 0:
        raise EvidenceError(f"negative performance property: {key}")
    return value


def validate_properties(
    properties: dict[str, str], expected_profile: str | None = None
) -> dict[str, int | str]:
    if properties.get("schemaVersion") != PROPERTIES_SCHEMA:
        raise EvidenceError("unsupported performance properties schema")
    if properties.get("status") != "PASS":
        raise EvidenceError("performance probe did not pass")
    profile = properties.get("profile")
    if profile not in {"smoke", "production"}:
        raise EvidenceError("performance profile must be smoke or production")
    if expected_profile is not None and profile != expected_profile:
        raise EvidenceError("performance profile differs from request")
    identities = {
        "codecId": "v40-performance-codec-v1",
        "codecVersion": "1",
        "storageIdentity": "v40-performance-store-v1",
        "schemaIdentity": "v40-performance-schema-v1",
    }
    for key, expected in identities.items():
        if properties.get(key) != expected:
            raise EvidenceError(f"performance identity differs: {key}")

    numeric: dict[str, int | str] = {"profile": profile}
    for key in (
        "documents",
        "singleOperations",
        "bulkOperations",
        "bulkSize",
        "producers",
        "producerOperations",
        "longRunSeconds",
    ):
        numeric[key] = integer(properties, key)
        if numeric[key] == 0:
            raise EvidenceError(f"performance dimension must be positive: {key}")

    for prefix in (
        "mutation.inMemory.single",
        "mutation.durable.single",
        "mutation.inMemory.bulk",
        "mutation.durable.bulk",
    ):
        count = integer(properties, f"{prefix}.count")
        ordered = [
            integer(properties, f"{prefix}.p50Nanos"),
            integer(properties, f"{prefix}.p95Nanos"),
            integer(properties, f"{prefix}.p99Nanos"),
            integer(properties, f"{prefix}.maxNanos"),
        ]
        if count == 0 or ordered != sorted(ordered):
            raise EvidenceError(f"invalid latency distribution: {prefix}")
        integer(properties, f"{prefix}.meanNanos")

    if properties.get("compatibility.inMemoryChecksum") != properties.get(
        "compatibility.durableChecksum"
    ):
        raise EvidenceError("in-memory and durable checksums differ")

    groups = integer(properties, "groupCommit.forceGroups")
    units = integer(properties, "groupCommit.forcedUnits")
    expected_units = integer(properties, "producers") * integer(
        properties, "producerOperations"
    )
    maximum_group = integer(properties, "groupCommit.maximumGroupSize")
    if not 0 < groups <= units == expected_units or not 0 < maximum_group <= units:
        raise EvidenceError("invalid force-group evidence")

    retained_after = integer(properties, "checkpoint.retainedAfterBytes")
    temporary_peak = integer(properties, "checkpoint.temporaryPeakBytes")
    encoded = integer(properties, "checkpoint.encodedCorpusBytes")
    if encoded == 0 or temporary_peak < retained_after:
        raise EvidenceError("invalid checkpoint byte evidence")
    for key in (
        "checkpoint.elapsedNanos",
        "checkpoint.processCpuNanos",
        "checkpoint.retainedBeforeBytes",
        "checkpoint.retainedAmplificationMicros",
        "checkpoint.temporaryAmplificationMicros",
        "groupCommit.elapsedNanos",
        "groupCommit.averageGroupSizeMicros",
        "groupCommit.walAppendForceNanos",
    ):
        integer(properties, key)

    recovery_sources = {
        "recovery.walOnly": "WAL_ONLY",
        "recovery.checkpointOnly": "CHECKPOINT_ONLY",
        "recovery.checkpointAndWal": "CHECKPOINT_AND_WAL",
    }
    for prefix, source in recovery_sources.items():
        if properties.get(f"{prefix}.source") != source:
            raise EvidenceError(f"invalid recovery source: {prefix}")
        for suffix in (
            "documents",
            "replayedRecords",
            "totalOpenNanos",
            "reportedRecoveryNanos",
            "storageOpenNanos",
            "checkpointLoadNanos",
            "replayAndRebuildNanos",
            "indexRebuildNanos",
            "retainedBytes",
            "walBytes",
        ):
            integer(properties, f"{prefix}.{suffix}")

    if properties.get("longRun.status") != "OPEN":
        raise EvidenceError("long-run durable engine did not remain open")
    for key in (
        "longRun.elapsedNanos",
        "longRun.reads",
        "longRun.writes",
        "longRun.checkpoints",
        "longRun.maximumRetainedBytes",
        "longRun.finalRetainedBytes",
        "longRun.finalSequence",
    ):
        value = integer(properties, key)
        if key in {"longRun.reads", "longRun.writes", "longRun.checkpoints"} \
                and value == 0:
            raise EvidenceError(f"long-run cell made no progress: {key}")

    return {key: value for key, value in properties.items()}


def tail(value: str) -> str:
    encoded = value.encode("utf-8", errors="replace")
    return encoded[-LOG_LIMIT:].decode("utf-8", errors="replace")


def run_probe(arguments: argparse.Namespace) -> int:
    source_commit = validate_source_commit(arguments.source_sha)
    workspace: Path = arguments.workspace
    if workspace.exists():
        raise EvidenceError("performance workspace already exists")
    workspace.mkdir(parents=True)
    probe_workspace = workspace / "probe"
    command = [
        arguments.java,
        "-cp",
        arguments.classpath,
        JAVA_MAIN,
        arguments.profile,
        str(probe_workspace),
        str(arguments.duration_seconds),
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=arguments.timeout_seconds,
    )
    status = "PASS"
    primary_failure = ""
    properties: dict[str, str] = {}
    try:
        if completed.returncode != 0:
            raise EvidenceError(
                f"operational probe exited with {completed.returncode}")
        properties = parse_properties(probe_workspace / "performance.properties")
        validate_properties(properties, arguments.profile)
    except EvidenceError as failure:
        status = "FAIL"
        primary_failure = str(failure)

    cleanup_status = "PASS"
    cleanup_failure = ""
    try:
        shutil.rmtree(probe_workspace)
        if probe_workspace.exists():
            raise OSError("probe workspace still exists")
    except OSError as failure:
        cleanup_status = "FAIL"
        cleanup_failure = str(failure)
        status = "FAIL"

    document: dict[str, Any] = {
        "kind": "v4-durable-performance",
        "status": status,
        "sourceCommit": source_commit,
        "environment": {
            "sourceState": arguments.source_state,
            "provider": "local-process",
            "suite": SUITE,
            "preset": PRESET,
            "profile": arguments.profile,
            "evidenceProfile": os.environ.get(
                "GSE_V4_EVIDENCE_PROFILE", "local"
            ),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cloudProvider": os.environ.get("GSE_V4_CLOUD_PROVIDER", "none"),
            "cloudMachineType": os.environ.get(
                "GSE_V4_CLOUD_MACHINE_TYPE", "local"
            ),
            "cloudImage": os.environ.get("GSE_V4_CLOUD_IMAGE", "local"),
            "cloudZone": os.environ.get("GSE_V4_CLOUD_ZONE", "local"),
            "filesystem": os.environ.get("GSE_V4_FILESYSTEM", "unknown"),
            "device": os.environ.get("GSE_V4_DEVICE", "unknown"),
        },
        "configuration": {
            "durationSeconds": arguments.duration_seconds,
            "java": arguments.java,
            "classpath": arguments.classpath,
            "codecIdentity": "v40-performance-codec-v1",
            "schemaIdentity": "v40-performance-schema-v1",
            "storageIdentity": "v40-performance-store-v1",
        },
        "case": {
            "caseId": f"phase6-performance-{arguments.profile}",
            "seed": 40,
            "barrierId": "NONE_PERFORMANCE_ONLY",
            "acknowledgement": "NOT_APPLICABLE",
        },
        "submittedHistory": [],
        "futureOutcomes": [],
        "process": {
            "command": command,
            "exitCode": completed.returncode,
            "termination": "NORMAL",
            "gracefulCloseRan": True,
        },
        "inspection": {
            "propertiesSchema": properties.get("schemaVersion", "MISSING"),
            "properties": properties,
        },
        "recovery": {
            "status": status,
            "walOnly": properties.get("recovery.walOnly.source", "MISSING"),
            "checkpointOnly": properties.get(
                "recovery.checkpointOnly.source", "MISSING"
            ),
            "checkpointAndWal": properties.get(
                "recovery.checkpointAndWal.source", "MISSING"
            ),
        },
        "logs": {
            "stdoutTail": tail(completed.stdout),
            "stderrTail": tail(completed.stderr),
            "limitBytesPerStream": LOG_LIMIT,
        },
        "cleanup": {
            "status": cleanup_status,
            "leftovers": [] if cleanup_status == "PASS" else [str(probe_workspace)],
            "failure": cleanup_failure,
        },
        "lifecycle": [
            "plan-validated",
            "probe-started",
            "mutation-cells-completed",
            "checkpoint-cell-completed",
            "recovery-cells-completed",
            "long-run-cell-completed",
            "probe-workspace-cleaned",
        ],
        "result": {
            "status": status,
            "primaryFailure": primary_failure,
            "paidExecution": os.environ.get(
                "GSE_V4_CLOUD_PROVIDER", "none"
            ) == "gcp",
            "metrics": properties,
        },
    }
    write_bundle(workspace / "evidence", document)
    validate_bundle(workspace / "evidence")
    if status != "PASS":
        raise EvidenceError(
            f"performance probe failed; evidence retained at {workspace / 'evidence'}: "
            f"{primary_failure or cleanup_failure}"
        )
    print(
        "v40PerformanceEvidence=PASS "
        f"profile={arguments.profile} output={workspace / 'evidence'}"
    )
    return 0


def validate_performance_bundle(path: Path) -> dict[str, Any]:
    document = validate_bundle(path)
    if document.get("kind") != "v4-durable-performance":
        raise EvidenceError("not a V4 durable performance bundle")
    properties = document["inspection"].get("properties")
    if not isinstance(properties, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in properties.items()
    ):
        raise EvidenceError("performance properties must be a string map")
    expected_profile = document["environment"].get("profile")
    validate_properties(properties, expected_profile)
    if document["status"] != "PASS":
        raise EvidenceError("performance bundle retained a failure")
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--workspace", type=Path, required=True)
    run.add_argument("--source-sha", required=True)
    run.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    run.add_argument("--profile", choices=("smoke", "production"), required=True)
    run.add_argument("--duration-seconds", type=int, required=True)
    run.add_argument("--java", default="java")
    run.add_argument("--classpath", required=True)
    run.add_argument("--timeout-seconds", type=int, default=600)
    validate = subparsers.add_parser("validate")
    validate.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "run":
        if arguments.duration_seconds <= 0 or arguments.timeout_seconds <= 0:
            raise EvidenceError("durations must be positive")
        return run_probe(arguments)
    validate_performance_bundle(arguments.bundle)
    print(f"v40PerformanceEvidenceValidation=PASS bundle={arguments.bundle}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, subprocess.TimeoutExpired) as failure:
        print(f"v40PerformanceEvidence=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
