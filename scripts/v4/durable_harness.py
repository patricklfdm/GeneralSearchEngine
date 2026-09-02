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
from scripts.v4.storage_inspector import (
    inspect_phase1_directory,
    inspect_phase2_directory,
    inspect_phase3_directory,
)

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
    scenario = getattr(arguments, "scenario", "phase1-scaffold")
    workspace = arguments.workspace.resolve()
    if workspace.exists():
        raise EvidenceError("workspace already exists")
    workspace.mkdir(parents=True)
    arguments.workspace_owned = True
    child_workspace = workspace / "engine-directory"
    child_workspace.mkdir()
    if scenario == "phase1-scaffold":
        mode = "child-halt" \
            if arguments.termination == "internal-halt" else "child-wait"
        java_options: list[str] = []
    else:
        mode = "phase3-open-crash" \
            if scenario == "phase3-open-recovery" else "phase2-write"
        action = "halt" \
            if arguments.termination == "internal-halt" else "wait"
        java_options = [
            f"-Dgse.v4.crashBarrier={arguments.barrier}",
            f"-Dgse.v4.crashAction={action}",
        ]
    command = [
        arguments.java,
        *java_options,
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
    if scenario == "phase1-scaffold":
        inspection = inspect_phase1_directory(child_workspace, arguments.barrier)
    elif scenario == "phase2-wal":
        inspection = inspect_phase2_directory(child_workspace)
    else:
        inspection = inspect_phase3_directory(child_workspace)
    recovery_mode = {
        "phase1-scaffold": "recover",
        "phase2-wal": "phase2-verify",
        "phase3-recovery": "phase3-recover",
        "phase3-open-recovery": "phase3-recover",
    }[scenario]
    recovery = subprocess.run(
        [
            arguments.java,
            "-cp",
            arguments.classpath,
            PROCESS_CLASS,
            recovery_mode,
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
    expected_recovery = "DEFERRED_PHASE3" \
        if scenario == "phase2-wal" else "PASS"
    if recovered.get("status") != expected_recovery:
        raise EvidenceError("recovery verifier did not pass")
    expected_sequence = expected_wal_sequence(arguments.barrier) \
        if scenario == "phase2-wal" else 0
    if scenario in {"phase3-recovery", "phase3-open-recovery"}:
        expected_sequence = expected_wal_sequence(arguments.barrier)
    inspected_sequence = inspection.get("wal", {}).get(
        "lastCompleteSequence", 0)
    if inspected_sequence != expected_sequence:
        raise EvidenceError(
            f"durable-prefix mismatch: expected {expected_sequence}, "
            f"inspected {inspected_sequence}")
    if scenario in {"phase3-recovery", "phase3-open-recovery"}:
        if recovered.get("recoveredSequence") != expected_sequence:
            raise EvidenceError("production recovery sequence mismatch")
        if recovered.get("continuedSequence") != expected_sequence + 1:
            raise EvidenceError("post-recovery continued sequence mismatch")
        if recovered.get("replayedRecords") != expected_sequence:
            raise EvidenceError("production replay metric mismatch")
        expected_truncation = scenario == "phase3-recovery" and \
            arguments.barrier in {
            "v4-wal-partial-header-v1",
            "v4-wal-partial-payload-v1",
            "v4-wal-partial-trailer-v1",
        }
        truncated_bytes = recovered.get("tailTruncatedBytes")
        if expected_truncation != (isinstance(truncated_bytes, int)
                                  and truncated_bytes > 0):
            raise EvidenceError("production tail-truncation diagnostic mismatch")
    finished = time.time_ns()
    device_id = os.stat(child_workspace).st_dev
    shutil.rmtree(child_workspace)
    if child_workspace.exists():
        raise EvidenceError("engine workspace cleanup failed")
    evidence = {
        "kind": {
            "phase1-scaffold": "local-crash-scaffold",
            "phase2-wal": "local-phase2-wal-crash",
            "phase3-recovery": "local-phase3-recovery-crash",
            "phase3-open-recovery": "local-phase3-recovery-crash",
        }[scenario],
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
            "codecIdentity": "PHASE1_NONE"
            if scenario == "phase1-scaffold"
            else "phase2-crash-codec-v1",
            "schemaIdentity": "PHASE1_SCAFFOLD_V1"
            if scenario == "phase1-scaffold"
            else "phase2-crash-schema-v1",
            "storageIdentity": "PHASE1_NO_PRODUCTION_STORAGE"
            if scenario == "phase1-scaffold"
            else "phase2-crash-store-v1",
            "timeoutSeconds": arguments.timeout,
        },
        "case": {
            "caseId": f"{scenario}-{arguments.termination}",
            "seed": 0,
            "barrierId": arguments.barrier,
            "acknowledgement": acknowledged,
        },
        "submittedHistory": [] if scenario == "phase1-scaffold" else [{
            "unit": "ADD",
            "key": "doc-1",
            "elementCount": 1,
        }],
        "futureOutcomes": [] if scenario == "phase1-scaffold" else [{
            "unit": 1,
            "outcome": "INCOMPLETE_AT_CRASH",
        }],
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
            "metrics": {
                "recoveredSequence": recovered.get("recoveredSequence", 0),
                "replayedRecords": recovered.get("replayedRecords", 0),
                "tailTruncatedBytes": recovered.get("tailTruncatedBytes", 0),
            },
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
            "oracle": {
                "phase1-scaffold": "PHASE1_NO_PRODUCTION_HISTORY",
                "phase2-wal": "PHASE2_INSPECTED_DURABLE_PREFIX",
                "phase3-recovery": "PHASE3_RECOVERED_DURABLE_PREFIX",
                "phase3-open-recovery": "PHASE3_RECOVERY_RESTART_PREFIX",
            }[scenario],
            "oracleMatched": True,
            "productionStorage": scenario != "phase1-scaffold",
            "expectedDurableSequence": expected_sequence,
        },
    }
    write_bundle(workspace / "evidence", evidence)
    validate_bundle(workspace / "evidence")
    print(f"v40CrashHarness=PASS termination={arguments.termination} "
          f"barrier={arguments.barrier}")
    return 0


def record_failed_case(arguments: argparse.Namespace, failure: BaseException) -> Path:
    scenario = getattr(arguments, "scenario", "phase1-scaffold")
    phase1 = scenario == "phase1-scaffold"
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
        "kind": "local-crash-scaffold" if phase1 else (
            "local-phase3-recovery-crash"
            if scenario in {"phase3-recovery", "phase3-open-recovery"}
            else "local-phase2-wal-crash"
        ),
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
            "codecIdentity": "PHASE1_NONE" if phase1
            else "phase2-crash-codec-v1",
            "schemaIdentity": "PHASE1_SCAFFOLD_V1" if phase1
            else "phase2-crash-schema-v1",
            "storageIdentity": "PHASE1_NO_PRODUCTION_STORAGE" if phase1
            else "phase2-crash-store-v1",
            "timeoutSeconds": arguments.timeout,
        },
        "case": {
            "caseId": f"{scenario}-{arguments.termination}",
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
    run.add_argument(
        "--scenario",
        choices=(
            "phase1-scaffold",
            "phase2-wal",
            "phase3-recovery",
            "phase3-open-recovery",
        ),
        default="phase1-scaffold",
    )
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


def expected_wal_sequence(barrier: str) -> int:
    zero_sequence = {
        "v4-wal-before-sequence-v1",
        "v4-wal-after-sequence-v1",
        "v4-wal-partial-header-v1",
        "v4-wal-partial-payload-v1",
        "v4-wal-partial-trailer-v1",
    }
    one_sequence = {
        "v4-wal-complete-before-force-v1",
        "v4-wal-after-force-v1",
        "v4-wal-before-publication-v1",
        "v4-wal-after-publication-v1",
        "v4-wal-before-future-completion-v1",
        "v4-recovery-after-tail-truncate-v1",
        "v4-recovery-after-replay-v1",
        "v4-recovery-before-ready-publication-v1",
    }
    if barrier in zero_sequence:
        return 0
    if barrier in one_sequence:
        return 1
    raise EvidenceError(f"unsupported WAL barrier: {barrier}")


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
