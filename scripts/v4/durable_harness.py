#!/usr/bin/env python3
"""Parent controller for the Phase 1 separate-JVM crash-harness scaffold."""

from __future__ import annotations

import argparse
import json
import os
import platform
import selectors
import shutil
import subprocess
import time
from pathlib import Path

from scripts.v4.evidence import (
    EvidenceError,
    validate_bundle,
    validate_source_commit,
    write_bundle,
)
from scripts.v4.storage_inspector import inspect_phase1_directory

PROCESS_CLASS = (
    "io.github.patricklfdm.generalsearch.durability.harness."
    "V40CrashHarnessProcess"
)


def wait_for_line(process: subprocess.Popen[str], timeout: float) -> str:
    selector = selectors.DefaultSelector()
    assert process.stdout is not None
    selector.register(process.stdout, selectors.EVENT_READ)
    events = selector.select(timeout)
    selector.close()
    if not events:
        process.kill()
        process.wait(timeout=5)
        raise EvidenceError("barrier acknowledgement timed out")
    line = process.stdout.readline()
    if not line:
        raise EvidenceError("child exited before barrier acknowledgement")
    return line.rstrip("\n")


def run_case(arguments: argparse.Namespace) -> int:
    workspace = arguments.workspace.resolve()
    if workspace.exists():
        raise EvidenceError("workspace already exists")
    workspace.mkdir(parents=True)
    arguments.workspace_owned = True
    child_workspace = workspace / "engine-directory"
    child_workspace.mkdir()
    mode = "child-halt" if arguments.termination == "internal-halt" else "child-wait"
    command = [
        arguments.java,
        "-cp",
        arguments.classpath,
        PROCESS_CLASS,
        mode,
        str(child_workspace),
        arguments.barrier,
    ]
    started = time.time_ns()
    child = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    acknowledgement = wait_for_line(child, arguments.timeout)
    prefix = "GSE_BARRIER_READY="
    if not acknowledgement.startswith(prefix):
        child.kill()
        child.wait(timeout=5)
        raise EvidenceError("invalid barrier acknowledgement")
    acknowledged = json.loads(acknowledgement[len(prefix):])
    if acknowledged.get("barrierId") != arguments.barrier:
        child.kill()
        child.wait(timeout=5)
        raise EvidenceError("acknowledged barrier mismatch")
    if arguments.termination == "external-kill":
        child.kill()
    stdout_tail, stderr = child.communicate(timeout=arguments.timeout)
    expected_exit = 86 if arguments.termination == "internal-halt" else -9
    if child.returncode != expected_exit:
        raise EvidenceError(
            f"unexpected abrupt child exit: {child.returncode}, expected {expected_exit}"
        )
    inspection = inspect_phase1_directory(child_workspace, arguments.barrier)
    recovery = subprocess.run(
        [
            arguments.java,
            "-cp",
            arguments.classpath,
            PROCESS_CLASS,
            "recover",
            str(child_workspace),
            arguments.barrier,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=arguments.timeout,
    )
    recovery_prefix = "GSE_RECOVERY_RESULT="
    recovery_line = recovery.stdout.strip()
    if recovery.returncode != 0 or not recovery_line.startswith(recovery_prefix):
        raise EvidenceError("separate recovery JVM failed")
    recovered = json.loads(recovery_line[len(recovery_prefix):])
    if recovered.get("status") != "PASS":
        raise EvidenceError("recovery verifier did not pass")
    finished = time.time_ns()
    device_id = os.stat(child_workspace).st_dev
    shutil.rmtree(child_workspace)
    if child_workspace.exists():
        raise EvidenceError("engine workspace cleanup failed")
    evidence = {
        "kind": "local-crash-scaffold",
        "status": "PASS",
        "sourceCommit": arguments.source_sha,
        "environment": {
            "sourceState": arguments.source_state,
            "os": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "javaCommand": arguments.java,
            "jvmArguments": [],
            "classpath": arguments.classpath,
            "filesystemDeviceId": device_id,
        },
        "configuration": {
            "codecIdentity": "PHASE1_NONE",
            "schemaIdentity": "PHASE1_SCAFFOLD_V1",
            "storageIdentity": "PHASE1_NO_PRODUCTION_STORAGE",
            "timeoutSeconds": arguments.timeout,
        },
        "case": {
            "caseId": f"phase1-{arguments.termination}",
            "seed": 0,
            "barrierId": arguments.barrier,
            "acknowledgement": acknowledged,
        },
        "submittedHistory": [],
        "futureOutcomes": [],
        "process": {
            "childPid": acknowledged["pid"],
            "startedEpochNanos": started,
            "finishedEpochNanos": finished,
            "termination": arguments.termination,
            "exitCode": child.returncode,
            "gracefulCloseRan": False,
        },
        "inspection": inspection,
        "recovery": {
            "verifier": "separate-jvm",
            "status": recovered["status"],
            "metrics": {},
            "result": recovered,
        },
        "logs": {
            "stdoutTail": stdout_tail[-4096:],
            "stderrTail": stderr[-4096:],
            "limitBytesPerStream": 4096,
        },
        "cleanup": {
            "status": "PASS",
            "engineWorkspaceDeleted": True,
            "evidenceRetained": True,
        },
        "lifecycle": [
            "workspace-created",
            "child-launched",
            "barrier-acknowledged",
            arguments.termination,
            "storage-inspected",
            "recovery-jvm-launched",
            "oracle-accepted",
            "engine-workspace-deleted",
        ],
        "result": {
            "oracle": "PHASE1_NO_PRODUCTION_HISTORY",
            "oracleMatched": True,
            "productionStorage": False,
        },
    }
    write_bundle(workspace / "evidence", evidence)
    validate_bundle(workspace / "evidence")
    print(f"v40CrashHarness=PASS termination={arguments.termination} "
          f"barrier={arguments.barrier}")
    return 0


def record_failed_case(arguments: argparse.Namespace, failure: BaseException) -> Path:
    workspace = arguments.workspace.resolve()
    child_workspace = workspace / "engine-directory"
    cleanup_status = "PASS"
    cleanup_failure = ""
    try:
        if child_workspace.exists():
            shutil.rmtree(child_workspace)
    except OSError as problem:
        cleanup_status = "FAIL"
        cleanup_failure = str(problem)
    evidence = {
        "kind": "local-crash-scaffold",
        "status": "FAIL",
        "sourceCommit": arguments.source_sha,
        "environment": {
            "sourceState": arguments.source_state,
            "os": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "javaCommand": arguments.java,
            "jvmArguments": [],
            "classpath": arguments.classpath,
            "filesystemDeviceId": "UNAVAILABLE_AFTER_FAILURE",
        },
        "configuration": {
            "codecIdentity": "PHASE1_NONE",
            "schemaIdentity": "PHASE1_SCAFFOLD_V1",
            "storageIdentity": "PHASE1_NO_PRODUCTION_STORAGE",
            "timeoutSeconds": arguments.timeout,
        },
        "case": {
            "caseId": f"phase1-{arguments.termination}",
            "seed": 0,
            "barrierId": arguments.barrier,
            "acknowledgement": "NOT_REACHED_OR_NOT_RETAINED",
        },
        "submittedHistory": [],
        "futureOutcomes": [],
        "process": {
            "termination": arguments.termination,
            "exitCode": "UNKNOWN",
            "gracefulCloseRan": "UNKNOWN",
        },
        "inspection": {"status": "NOT_COMPLETED"},
        "recovery": {
            "verifier": "separate-jvm",
            "status": "NOT_COMPLETED",
            "metrics": {},
            "result": "NOT_COMPLETED",
        },
        "logs": {
            "stdoutTail": "",
            "stderrTail": "",
            "limitBytesPerStream": 4096,
        },
        "cleanup": {
            "status": cleanup_status,
            "engineWorkspaceDeleted": not child_workspace.exists(),
            "failure": cleanup_failure,
            "evidenceRetained": True,
        },
        "lifecycle": [
            "workspace-created",
            "primary-failure-recorded",
            "cleanup-attempted",
        ],
        "result": {
            "oracle": "NOT_EVALUATED",
            "oracleMatched": False,
            "primaryFailureType": type(failure).__name__,
            "primaryFailure": str(failure)[:4096],
        },
    }
    evidence_path = workspace / "evidence"
    write_bundle(evidence_path, evidence)
    validate_bundle(evidence_path)
    return evidence_path


def run_case_with_failure_evidence(arguments: argparse.Namespace) -> int:
    arguments.workspace_owned = False
    try:
        return run_case(arguments)
    except (EvidenceError, OSError, subprocess.SubprocessError) as failure:
        if arguments.workspace_owned:
            evidence_path = record_failed_case(arguments, failure)
            raise EvidenceError(
                f"{failure}; failed evidence retained at {evidence_path}"
            ) from failure
        if isinstance(failure, EvidenceError):
            raise
        raise EvidenceError(str(failure)) from failure


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--workspace", type=Path, required=True)
    run.add_argument("--source-sha", required=True)
    run.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    run.add_argument("--barrier", default="phase1-scaffold-v1")
    run.add_argument(
        "--termination",
        choices=("internal-halt", "external-kill"),
        required=True,
    )
    run.add_argument("--java", default="java")
    run.add_argument("--classpath", default="target/test-classes:target/classes")
    run.add_argument("--timeout", type=float, default=10.0)
    run.set_defaults(action=run_case_with_failure_evidence)
    validate = commands.add_parser("validate")
    validate.add_argument("directory", type=Path)
    validate.set_defaults(action=lambda args: validate_command(args.directory))
    return root


def validate_command(directory: Path) -> int:
    validate_bundle(directory)
    print("v40EvidenceValidation=PASS")
    return 0


def main() -> int:
    arguments = parser().parse_args()
    if hasattr(arguments, "source_sha"):
        validate_source_commit(arguments.source_sha)
    return arguments.action(arguments)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as failure:
        print(f"v40Harness=FAIL reason={failure}", file=os.sys.stderr)
        raise SystemExit(2) from failure
