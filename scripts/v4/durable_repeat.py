#!/usr/bin/env python3
"""Repeated same-history crash, inspection, recovery and continuation driver."""

from __future__ import annotations

import argparse
import json
import os
import platform
import selectors
import shutil
import subprocess
import sys
import time
from pathlib import Path

from scripts.v4.evidence import (
    EvidenceError,
    validate_bundle,
    validate_source_commit,
    write_bundle,
)
from scripts.v4.storage_inspector import inspect_phase4_directory

PROCESS_CLASS = (
    "io.github.patricklfdm.generalsearch.durability.harness."
    "V40CrashHarnessProcess"
)
WAL_BARRIER = "v4-wal-before-future-completion-v1"
CHECKPOINT_AUTHORITY_BARRIER = "v4-checkpoint-after-directory-force-v1"
CHECKPOINT_CLEANUP_BARRIER = "v4-checkpoint-after-wal-cleanup-v1"


def wait_for_barrier(process: subprocess.Popen[str], timeout: float) -> dict:
    selector = selectors.DefaultSelector()
    assert process.stdout is not None
    selector.register(process.stdout, selectors.EVENT_READ)
    events = selector.select(timeout)
    selector.close()
    if not events:
        process.kill()
        process.wait(timeout=5)
        raise EvidenceError("repeated-crash barrier timed out")
    line = process.stdout.readline().rstrip("\n")
    prefix = "GSE_BARRIER_READY="
    if not line.startswith(prefix):
        raise EvidenceError("repeated-crash barrier acknowledgement is invalid")
    try:
        acknowledgement = json.loads(line[len(prefix):])
    except json.JSONDecodeError as failure:
        raise EvidenceError("repeated-crash acknowledgement is invalid JSON") \
            from failure
    return acknowledgement


def barrier_for(cycle: int) -> str:
    position = cycle % 4
    if position in {1, 3}:
        return WAL_BARRIER
    if position == 2:
        return CHECKPOINT_AUTHORITY_BARRIER
    return CHECKPOINT_CLEANUP_BARRIER


def parse_recovery(stdout: str) -> dict:
    prefix = "GSE_RECOVERY_RESULT="
    line = stdout.strip()
    if not line.startswith(prefix):
        raise EvidenceError("repeated-crash recovery result is missing")
    try:
        return json.loads(line[len(prefix):])
    except json.JSONDecodeError as failure:
        raise EvidenceError("repeated-crash recovery result is invalid JSON") \
            from failure


def run(arguments: argparse.Namespace) -> int:
    workspace = arguments.workspace.resolve()
    if workspace.exists():
        raise EvidenceError("repeated-crash workspace already exists")
    workspace.mkdir(parents=True)
    engine_directory = workspace / "engine-directory"
    engine_directory.mkdir()

    cycles: list[dict] = []
    stdout_log = ""
    stderr_log = ""
    maximum_retained = 0
    started = time.time_ns()
    for cycle in range(1, arguments.cycles + 1):
        barrier = barrier_for(cycle)
        command = [
            arguments.java,
            f"-Dgse.v4.crashBarrier={barrier}",
            "-Dgse.v4.crashAction=halt",
            "-cp",
            arguments.classpath,
            PROCESS_CLASS,
            "phase5-cycle-crash",
            str(engine_directory),
            barrier,
        ]
        child = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        acknowledgement = wait_for_barrier(child, arguments.timeout)
        if acknowledgement.get("barrierId") != barrier:
            child.kill()
            child.wait(timeout=5)
            raise EvidenceError("repeated-crash barrier identity mismatch")
        stdout_tail, stderr_tail = child.communicate(timeout=arguments.timeout)
        stdout_log = (stdout_log + stdout_tail)[-4096:]
        stderr_log = (stderr_log + stderr_tail)[-4096:]
        if child.returncode != 86:
            raise EvidenceError(
                f"cycle {cycle} exited {child.returncode}, expected hard halt 86")

        inspection = inspect_phase4_directory(engine_directory)
        if inspection["durableSequence"] != cycle:
            raise EvidenceError(
                f"cycle {cycle} durable prefix is "
                f"{inspection['durableSequence']}")
        retained = sum((engine_directory / name).stat().st_size
                       for name in inspection["files"])
        maximum_retained = max(maximum_retained, retained)

        verifier = subprocess.run(
            [
                arguments.java,
                "-cp",
                arguments.classpath,
                PROCESS_CLASS,
                "phase5-cycle-verify",
                str(engine_directory),
                barrier,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=arguments.timeout,
        )
        if verifier.returncode != 0:
            raise EvidenceError(f"cycle {cycle} recovery JVM failed")
        recovered = parse_recovery(verifier.stdout)
        if recovered.get("status") != "PASS" \
                or recovered.get("recoveredSequence") != cycle:
            raise EvidenceError(f"cycle {cycle} recovery oracle mismatch")
        cycles.append({
            "cycle": cycle,
            "barrierId": barrier,
            "childPid": acknowledgement.get("pid"),
            "exitCode": child.returncode,
            "durableSequence": inspection["durableSequence"],
            "checkpointSequence": recovered.get("checkpointSequence"),
            "recoverySource": recovered.get("recoverySource"),
            "retainedBytes": retained,
            "walGenerations": len(inspection["wals"]),
            "stagingFiles": inspection["stagingFiles"],
        })

    final_inspection = inspect_phase4_directory(engine_directory)
    finished = time.time_ns()
    device_id = os.stat(engine_directory).st_dev
    shutil.rmtree(engine_directory)
    if engine_directory.exists():
        raise EvidenceError("repeated-crash engine cleanup failed")

    evidence = {
        "kind": "local-phase5-repeated-crash",
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
            "cycles": arguments.cycles,
            "codecIdentity": "phase2-crash-codec-v1",
            "schemaIdentity": "phase2-crash-schema-v1",
            "storageIdentity": "phase2-crash-store-v1",
            "barrierSchedule": [barrier_for(cycle)
                                for cycle in range(1, arguments.cycles + 1)],
            "timeoutSeconds": arguments.timeout,
        },
        "case": {
            "caseId": "phase5-repeated-same-history-crash-v1",
            "seed": 0,
            "barrierId": "mixed-stable-barriers",
            "acknowledgement": "EVERY_CYCLE_ACKNOWLEDGED",
        },
        "submittedHistory": [{
            "unit": "ADD",
            "key": f"doc-{cycle}",
            "elementCount": 1,
        } for cycle in range(1, arguments.cycles + 1)],
        "futureOutcomes": [{
            "unit": cycle,
            "outcome": "INCOMPLETE_AT_CRASH"
            if barrier_for(cycle) == WAL_BARRIER
            else "MUTATION_COMPLETED_CHECKPOINT_INCOMPLETE",
        } for cycle in range(1, arguments.cycles + 1)],
        "process": {
            "startedEpochNanos": started,
            "finishedEpochNanos": finished,
            "termination": "REPEATED_RUNTIME_HALT",
            "exitCode": 86,
            "gracefulCloseRan": False,
            "cycles": cycles,
        },
        "inspection": final_inspection,
        "recovery": {
            "verifier": "separate-jvm-every-cycle",
            "status": "PASS",
            "metrics": {
                "recoveredSequence": arguments.cycles,
                "maximumRetainedBytes": maximum_retained,
                "reopenCount": arguments.cycles * 2,
            },
            "result": "EVERY_PREFIX_RECOVERED_AND_REOPENED_TWICE",
        },
        "logs": {
            "stdoutTail": stdout_log,
            "stderrTail": stderr_log,
            "limitBytesPerStream": 4096,
        },
        "cleanup": {
            "status": "PASS",
            "engineWorkspaceDeleted": True,
            "evidenceRetained": True,
        },
        "lifecycle": [
            "workspace-created",
            "same-history-crash-cycles-completed",
            "every-prefix-independently-inspected",
            "every-cycle-recovered",
            "every-cycle-reopened-twice",
            "engine-workspace-deleted",
        ],
        "result": {
            "oracle": "PHASE5_REPEATED_DURABLE_PREFIX",
            "oracleMatched": True,
            "productionStorage": True,
            "expectedDurableSequence": arguments.cycles,
            "maximumRetainedBytes": maximum_retained,
        },
    }
    write_bundle(workspace / "evidence", evidence)
    validate_bundle(workspace / "evidence")
    print("v40RepeatedCrash=PASS "
          f"cycles={arguments.cycles} sequence={arguments.cycles} "
          f"maxRetainedBytes={maximum_retained}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    parser.add_argument("--cycles", type=int, default=8)
    parser.add_argument("--java", default="java")
    parser.add_argument("--classpath", default="target/test-classes:target/classes")
    parser.add_argument("--timeout", type=float, default=15.0)
    arguments = parser.parse_args()
    validate_source_commit(arguments.source_sha)
    if arguments.cycles < 4 or arguments.cycles > 32:
        raise EvidenceError("repeated-crash cycles must be between 4 and 32")
    return run(arguments)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, subprocess.SubprocessError) as failure:
        print(f"v40RepeatedCrash=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
