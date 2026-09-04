#!/usr/bin/env python3
"""Separate-JVM V4.2 migration crash-harness scaffold."""

from __future__ import annotations

import argparse
import hashlib
import json
import selectors
import shutil
import subprocess
import sys
import time
from pathlib import Path

from scripts.v42.evidence import (
    EvidenceError,
    PRESET,
    SUITE,
    validate_bundle,
    validate_source,
    write_bundle,
)

PROCESS_CLASS = (
    "io.github.patricklfdm.generalsearch.durability.harness."
    "V42MigrationHarnessProcess"
)
BARRIER = "v42-phase1-migration-plan-no-output-v1"


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


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(arguments: argparse.Namespace) -> int:
    validate_source(arguments.source_sha)
    workspace = arguments.workspace.resolve()
    if workspace.exists():
        raise EvidenceError("workspace already exists")
    workspace.mkdir(parents=True)
    source = workspace / "source"
    target = workspace / "target"
    mode = "child-halt" if arguments.termination == "internal-halt" else "child-wait"
    command = [arguments.java, "-cp", arguments.classpath, PROCESS_CLASS,
               mode, str(source), str(target), BARRIER]
    started = time.time_ns()
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
    line = read_line(child, arguments.timeout)
    prefix = "GSE_V42_BARRIER_READY="
    if not line.startswith(prefix):
        child.kill()
        child.wait(timeout=5)
        raise EvidenceError("invalid barrier acknowledgement")
    acknowledgement = json.loads(line[len(prefix):])
    if acknowledgement.get("barrierId") != BARRIER \
            or acknowledgement.get("targetCreated") is not False:
        child.kill()
        child.wait(timeout=5)
        raise EvidenceError("barrier identity or target state mismatch")
    source_member = source / "v42-phase1-source.properties"
    before = file_sha256(source_member)
    if arguments.termination == "external-kill":
        child.kill()
    stdout, stderr = child.communicate(timeout=arguments.timeout)
    expected = 88 if arguments.termination == "internal-halt" else -9
    if child.returncode != expected:
        raise EvidenceError(f"unexpected abrupt exit: {child.returncode}")
    verifier = subprocess.run(
        [arguments.java, "-cp", arguments.classpath, PROCESS_CLASS,
         "verify", str(source), str(target), BARRIER],
        check=False, capture_output=True, text=True, timeout=arguments.timeout)
    verifier_prefix = "GSE_V42_VERIFY_RESULT="
    if verifier.returncode != 0 or not verifier.stdout.startswith(verifier_prefix):
        raise EvidenceError("separate verifier JVM failed")
    verified = json.loads(verifier.stdout[len(verifier_prefix):])
    after = file_sha256(source_member)
    if before != after or verified.get("sourceUnchanged") is not True \
            or verified.get("targetAbsent") is not True:
        raise EvidenceError("source changed or target was created")
    shutil.rmtree(source)
    if source.exists() or target.exists():
        raise EvidenceError("model workspace cleanup failed")
    evidence = base_document(arguments.source_sha, arguments.source_state,
                             "local-scaffold")
    evidence.update({
        "kind": "local-migration-crash-scaffold",
        "case": {"caseId": arguments.termination, "barrierId": BARRIER,
                 "acknowledgement": acknowledgement},
        "source": {"format": "gse-durable (1,0)",
                   "beforeSha256": before, "afterSha256": after,
                   "bytesUnchanged": True},
        "target": {"format": "gse-durable (1,1)", "state": "ABSENT",
                   "productionBytes": False},
        "migration": {"plan": "MODEL_ONLY", "apply": "NOT_IMPLEMENTED",
                      "planFilesystemOutput": False},
        "process": {"termination": arguments.termination,
                    "exitCode": child.returncode, "gracefulCloseRan": False,
                    "startedEpochNanos": started,
                    "finishedEpochNanos": time.time_ns(),
                    "verifierJvm": "PASS"},
        "lifecycle": ["child-started", "source-model-written",
                      "plan-no-output-barrier-acknowledged", "abrupt-death",
                      "separate-verifier-passed", "source-identity-matched",
                      "workspace-cleaned"],
        "logs": {"stdoutTail": stdout[-4096:],
                 "stderrTail": (stderr + verifier.stderr)[-4096:],
                 "limitBytesPerStream": 4096},
    })
    write_bundle(workspace / "evidence", evidence)
    validate_bundle(workspace / "evidence")
    print(f"v42MigrationHarness=PASS termination={arguments.termination}")
    return 0


def base_document(source: str, source_state: str, profile: str) -> dict[str, object]:
    return {
        "kind": "phase1-scaffold", "status": "PASS", "sourceCommit": source,
        "sourceState": source_state, "suite": SUITE, "preset": PRESET,
        "profile": profile, "case": {},
        "configuration": {"productionFormat11": False,
                          "productionMigration": False,
                          "paidExecution": False},
        "source": {"bytesUnchanged": True},
        "target": {"state": "ABSENT"},
        "migration": {"plan": "MODEL_ONLY", "apply": "NOT_IMPLEMENTED"},
        "rollback": {"publishedVersion": "4.1.0", "status": "MODEL_ONLY"},
        "process": {}, "lifecycle": [],
        "cleanup": {"status": "PASS", "leftovers": []},
        "logs": {"stdoutTail": "", "stderrTail": "",
                 "limitBytesPerStream": 4096},
        "result": {"paidExecution": False, "productionMigration": False},
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
        print(f"v42MigrationEvidenceValidation=PASS kind={value['kind']}")
        return 0
    return run_case(arguments)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, subprocess.SubprocessError) as failure:
        print(f"v42MigrationHarness=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
