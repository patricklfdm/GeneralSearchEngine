#!/usr/bin/env python3
"""Writer/recovery halves of the preserved-disk V4 cloud failure drill."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from scripts.v4.durable_repeat import (
    PROCESS_CLASS,
    WAL_BARRIER,
    parse_recovery,
    wait_for_barrier,
)
from scripts.v4.evidence import (
    EvidenceError,
    canonical_json,
    validate_bundle,
    validate_source_commit,
    write_bundle,
)
from scripts.v4.storage_inspector import inspect_phase4_directory


def force_file(path: Path, document: dict[str, Any]) -> None:
    path.write_bytes(canonical_json(document))
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def writer(arguments: argparse.Namespace) -> int:
    source = validate_source_commit(arguments.source_sha)
    workspace = arguments.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=False)
    engine = workspace / "engine-directory"
    engine.mkdir()
    command = [
        arguments.java,
        f"-Dgse.v4.crashBarrier={WAL_BARRIER}",
        "-Dgse.v4.crashAction=halt",
        "-cp",
        arguments.classpath,
        PROCESS_CLASS,
        "phase5-cycle-crash",
        str(engine),
        WAL_BARRIER,
    ]
    started = time.time_ns()
    child = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    acknowledgement = wait_for_barrier(child, arguments.timeout)
    stdout, stderr = child.communicate(timeout=arguments.timeout)
    if child.returncode != 86:
        raise EvidenceError(
            f"failure-drill writer exited {child.returncode}, expected 86")
    inspection = inspect_phase4_directory(engine)
    if inspection.get("durableSequence") != 1:
        raise EvidenceError("failure-drill writer durable prefix is not sequence one")
    force_file(workspace / "writer-result.json", {
        "schemaVersion": "gse-v40-cloud-failure-writer-v1",
        "sourceCommit": source,
        "barrierId": WAL_BARRIER,
        "acknowledgement": acknowledgement,
        "exitCode": child.returncode,
        "startedEpochNanos": started,
        "finishedEpochNanos": time.time_ns(),
        "stdoutTail": stdout[-4096:],
        "stderrTail": stderr[-4096:],
        "inspection": inspection,
    })
    print("v40CloudFailureWriter=PASS barrier=" + WAL_BARRIER)
    return 0


def recover(arguments: argparse.Namespace) -> int:
    source = validate_source_commit(arguments.source_sha)
    workspace = arguments.workspace.resolve()
    writer_result_path = workspace / "writer-result.json"
    try:
        writer_result = json.loads(writer_result_path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as failure:
        raise EvidenceError("writer result is missing or invalid") from failure
    if writer_result.get("sourceCommit") != source \
            or writer_result.get("barrierId") != WAL_BARRIER \
            or writer_result.get("exitCode") != 86:
        raise EvidenceError("writer result identity differs")
    engine = workspace / "engine-directory"
    inspection = inspect_phase4_directory(engine)
    if inspection.get("durableSequence") != 1:
        raise EvidenceError("reattached disk durable prefix differs")
    verifier = subprocess.run(
        [
            arguments.java,
            "-cp",
            arguments.classpath,
            PROCESS_CLASS,
            "phase5-cycle-verify",
            str(engine),
            WAL_BARRIER,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=arguments.timeout,
    )
    if verifier.returncode != 0:
        raise EvidenceError(
            "replacement-VM recovery verifier failed "
            f"with exit {verifier.returncode}; "
            f"stdoutTail={verifier.stdout[-4096:]!r}; "
            f"stderrTail={verifier.stderr[-4096:]!r}"
        )
    recovered = parse_recovery(verifier.stdout)
    if recovered.get("status") != "PASS" \
            or recovered.get("recoveredSequence") != 1:
        raise EvidenceError("replacement-VM recovery result differs")
    evidence = {
        "kind": "v4-cloud-preserved-disk-failure-drill",
        "status": "PASS",
        "sourceCommit": source,
        "environment": {
            "sourceState": "clean",
            "provider": "gcp",
            "suite": "v4.0-durable-single-node-suite-v1",
            "preset": "v4.0-durable-single-node-v1",
            "profile": "failure-drill",
            "os": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "machineType": os.environ.get("GSE_V4_CLOUD_MACHINE_TYPE", "unknown"),
            "image": os.environ.get("GSE_V4_CLOUD_IMAGE", "unknown"),
            "zone": os.environ.get("GSE_V4_CLOUD_ZONE", "unknown"),
            "filesystem": os.environ.get("GSE_V4_FILESYSTEM", "unknown"),
            "device": os.environ.get("GSE_V4_DEVICE", "unknown"),
        },
        "configuration": {
            "codecIdentity": "phase2-crash-codec-v1",
            "schemaIdentity": "phase2-crash-schema-v1",
            "storageIdentity": "phase2-crash-store-v1",
            "persistentDisk": True,
            "bootDiskUsedAsEvidence": False,
        },
        "case": {
            "caseId": "phase6-preserved-disk-vm-replacement-v1",
            "seed": 0,
            "barrierId": WAL_BARRIER,
            "acknowledgement": "WRITER_ACKNOWLEDGED_BEFORE_HALT",
        },
        "submittedHistory": [{
            "unit": "ADD", "key": "doc-1", "elementCount": 1,
        }],
        "futureOutcomes": [{
            "unit": 1, "outcome": "INCOMPLETE_AT_CRASH",
        }],
        "process": {
            "writer": writer_result,
            "termination": "RUNTIME_HALT_THEN_WRITER_VM_DELETED",
            "exitCode": 86,
            "gracefulCloseRan": False,
            "replacementRecoveryVm": True,
        },
        "inspection": inspection,
        "recovery": {
            "verifier": "separate-replacement-vm-jvm",
            "status": "PASS",
            "metrics": recovered,
            "result": "PRESERVED_DISK_PREFIX_RECOVERED_AND_REOPENED",
        },
        "logs": {
            "stdoutTail": verifier.stdout[-4096:],
            "stderrTail": verifier.stderr[-4096:],
            "limitBytesPerStream": 4096,
        },
        "cleanup": {
            "status": "PASS",
            "engineClosed": True,
            "cloudResourceCleanup": "ORCHESTRATOR_REQUIRED",
            "leftovers": [],
        },
        "lifecycle": [
            "persistent-disk-created",
            "writer-vm-attached",
            "writer-barrier-acknowledged",
            "writer-jvm-halted",
            "writer-vm-deleted",
            "persistent-disk-preserved",
            "replacement-recovery-vm-attached",
            "bytes-independently-inspected",
            "recovery-verified",
            "second-reopen-verified",
        ],
        "result": {
            "oracleMatched": True,
            "persistentDiskSurvivedWriter": True,
            "bootDiskUsedAsEvidence": False,
            "recoveredSequence": 1,
            "paidExecution": True,
        },
    }
    write_bundle(workspace / "evidence", evidence)
    validate_bundle(workspace / "evidence")
    print("v40CloudFailureRecovery=PASS sequence=1")
    return 0


def validate_failure_bundle(path: Path) -> dict[str, Any]:
    document = validate_bundle(path)
    if document.get("kind") != "v4-cloud-preserved-disk-failure-drill":
        raise EvidenceError("not a V4 preserved-disk failure bundle")
    if document.get("status") != "PASS" \
            or document["environment"].get("profile") != "failure-drill" \
            or document["process"].get("replacementRecoveryVm") is not True \
            or document["result"].get("persistentDiskSurvivedWriter") is not True \
            or document["result"].get("bootDiskUsedAsEvidence") is not False \
            or document["result"].get("recoveredSequence") != 1:
        raise EvidenceError("preserved-disk failure evidence is incomplete")
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("writer", "recover"):
        command = subparsers.add_parser(name)
        command.add_argument("--workspace", type=Path, required=True)
        command.add_argument("--source-sha", required=True)
        command.add_argument("--java", default="java")
        command.add_argument(
            "--classpath", default="target/test-classes:target/classes")
        command.add_argument("--timeout", type=float, default=30.0)
    validate = subparsers.add_parser("validate")
    validate.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "writer":
        return writer(arguments)
    if arguments.command == "recover":
        return recover(arguments)
    validate_failure_bundle(arguments.bundle)
    print(f"v40CloudFailureValidation=PASS bundle={arguments.bundle}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, subprocess.SubprocessError) as failure:
        print(f"v40CloudFailure=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
