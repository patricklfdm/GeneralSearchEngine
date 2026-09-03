#!/usr/bin/env python3
"""Separate-JVM V4.1 operational crash-harness scaffold."""

from __future__ import annotations

import argparse
import json
import selectors
import shutil
import subprocess
import sys
import time
from pathlib import Path

from scripts.v41.evidence import EvidenceError, validate_bundle, validate_source, write_bundle

PROCESS_CLASS = (
    "io.github.patricklfdm.generalsearch.durability.harness."
    "V41OperationalCrashHarnessProcess"
)
SUITE = "v4.1-operational-safety-suite-v1"
PRESET = "v4.1-operational-safety-v1"
BARRIER = "v41-phase1-operational-scaffold-v1"


def read_line(process: subprocess.Popen[str], timeout: float) -> str:
    assert process.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    ready = selector.select(timeout)
    selector.close()
    if not ready:
        process.kill()
        process.wait(timeout=5)
        raise EvidenceError("barrier acknowledgement timed out")
    value = process.stdout.readline().rstrip("\n")
    if not value:
        raise EvidenceError("child exited before barrier")
    return value


def run_case(arguments: argparse.Namespace) -> int:
    validate_source(arguments.source_sha)
    workspace = arguments.workspace.resolve()
    if workspace.exists():
        raise EvidenceError("workspace already exists")
    workspace.mkdir(parents=True)
    engine = workspace / "engine-directory"
    engine.mkdir()
    mode = "child-halt" if arguments.termination == "internal-halt" else "child-wait"
    command = [arguments.java, "-cp", arguments.classpath, PROCESS_CLASS,
               mode, str(engine), BARRIER]
    started = time.time_ns()
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
    line = read_line(child, arguments.timeout)
    prefix = "GSE_V41_BARRIER_READY="
    if not line.startswith(prefix):
        child.kill()
        child.wait(timeout=5)
        raise EvidenceError("invalid barrier acknowledgement")
    acknowledgement = json.loads(line[len(prefix):])
    if acknowledgement.get("barrierId") != BARRIER:
        child.kill()
        child.wait(timeout=5)
        raise EvidenceError("barrier identity mismatch")
    if arguments.termination == "external-kill":
        child.kill()
    stdout, stderr = child.communicate(timeout=arguments.timeout)
    expected = 87 if arguments.termination == "internal-halt" else -9
    if child.returncode != expected:
        raise EvidenceError(f"unexpected abrupt exit: {child.returncode}")
    verifier = subprocess.run(
        [arguments.java, "-cp", arguments.classpath, PROCESS_CLASS,
         "verify", str(engine), BARRIER],
        check=False, capture_output=True, text=True, timeout=arguments.timeout)
    if verifier.returncode != 0 or not verifier.stdout.startswith(
            "GSE_V41_VERIFY_RESULT="):
        raise EvidenceError("separate verifier JVM failed")
    members = sorted(path.name for path in engine.iterdir())
    if members != ["v41-phase1-scaffold.properties"]:
        raise EvidenceError(f"unexpected scaffold members: {members}")
    shutil.rmtree(engine)
    finished = time.time_ns()
    evidence = base_document(arguments.source_sha, arguments.source_state,
                             "local-scaffold")
    evidence.update({
        "kind": "local-operational-crash-scaffold",
        "case": {"caseId": arguments.termination, "barrierId": BARRIER,
                 "acknowledgement": acknowledgement},
        "process": {"termination": arguments.termination,
                    "exitCode": child.returncode, "gracefulCloseRan": False,
                    "startedEpochNanos": started, "finishedEpochNanos": finished,
                    "verifierJvm": "PASS"},
        "lifecycle": ["child-started", "barrier-acknowledged", "abrupt-death",
                      "separate-verifier-passed", "workspace-cleaned"],
        "logs": {"stdoutTail": stdout[-4096:],
                 "stderrTail": (stderr + verifier.stderr)[-4096:],
                 "limitBytesPerStream": 4096},
    })
    write_bundle(workspace / "evidence", evidence)
    validate_bundle(workspace / "evidence")
    print(f"v41OperationalHarness=PASS termination={arguments.termination}")
    return 0


def base_document(source: str, source_state: str, profile: str) -> dict[str, object]:
    return {
        "kind": "phase1-scaffold", "status": "PASS", "sourceCommit": source,
        "sourceState": source_state, "suite": SUITE, "preset": PRESET,
        "profile": profile,
        "case": {},
        "configuration": {"productionOperations": False},
        "backup": {"status": "MODEL_ONLY", "format": "gse-backup (1,0)"},
        "verification": {"status": "SCAFFOLD_PASS", "parser": "independent"},
        "restore": {"status": "MODEL_ONLY", "newHistory": True},
        "process": {}, "lifecycle": [],
        "cleanup": {"status": "PASS", "leftovers": []},
        "logs": {"stdoutTail": "", "stderrTail": "", "limitBytesPerStream": 4096},
        "result": {"paidExecution": False, "productionOperations": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--workspace", type=Path, required=True)
    run.add_argument("--source-sha", required=True)
    run.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    run.add_argument("--termination", choices=("internal-halt", "external-kill"),
                     required=True)
    run.add_argument("--java", default="java")
    run.add_argument("--classpath", default="target/test-classes:target/classes")
    run.add_argument("--timeout", type=float, default=15.0)
    validate = subparsers.add_parser("validate")
    validate.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "validate":
        value = validate_bundle(arguments.bundle)
        print(f"v41OperationalEvidenceValidation=PASS kind={value['kind']}")
        return 0
    return run_case(arguments)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, subprocess.SubprocessError) as failure:
        print(f"v41OperationalHarness=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
