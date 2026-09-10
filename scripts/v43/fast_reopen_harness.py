#!/usr/bin/env python3
"""Separate-JVM V4.3 fast-reopen crash-harness scaffold."""

from __future__ import annotations

import argparse
import hashlib
import json
import selectors
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.v43.evidence import (
    EvidenceError, base_document, validate_bundle, validate_source, write_bundle,
)

PROCESS_CLASS = (
    "io.github.patricklfdm.generalsearch.durability.harness."
    "V43FastReopenHarnessProcess"
)
BARRIER = "v43-phase1-derived-plan-no-output-v1"


def _line(process: subprocess.Popen[str], timeout: float) -> str:
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
    store = workspace / "store"
    mode = "child-halt" if arguments.termination == "internal-halt" else "child-wait"
    child = subprocess.Popen(
        [arguments.java, "-cp", arguments.classpath, PROCESS_CLASS,
         mode, str(store), BARRIER], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True)
    line = _line(child, arguments.timeout)
    prefix = "GSE_V43_BARRIER_READY="
    if not line.startswith(prefix):
        child.kill()
        child.wait(timeout=5)
        raise EvidenceError("invalid barrier acknowledgement")
    acknowledgement = json.loads(line[len(prefix):])
    if acknowledgement.get("barrierId") != BARRIER \
            or acknowledgement.get("derivedMembersCreated") is not False:
        child.kill()
        child.wait(timeout=5)
        raise EvidenceError("barrier identity or derived state differs")
    canonical = store / "v43-phase1-canonical.properties"
    before = hashlib.sha256(canonical.read_bytes()).hexdigest()
    if arguments.termination == "external-kill":
        child.kill()
    stdout, stderr = child.communicate(timeout=arguments.timeout)
    expected = 89 if arguments.termination == "internal-halt" else -9
    if child.returncode != expected:
        raise EvidenceError(f"unexpected abrupt exit: {child.returncode}")
    verifier = subprocess.run(
        [arguments.java, "-cp", arguments.classpath, PROCESS_CLASS,
         "verify", str(store), BARRIER], check=False, capture_output=True,
        text=True, timeout=arguments.timeout)
    verify_prefix = "GSE_V43_VERIFY_RESULT="
    if verifier.returncode != 0 or not verifier.stdout.startswith(verify_prefix):
        raise EvidenceError("separate verifier JVM failed")
    verified = json.loads(verifier.stdout[len(verify_prefix):])
    after = hashlib.sha256(canonical.read_bytes()).hexdigest()
    if before != after or verified.get("canonicalAuthority") != "VALID" \
            or verified.get("derivedState") != "ABSENT":
        raise EvidenceError("canonical or derived state differs")
    shutil.rmtree(store)
    evidence = base_document(arguments.source_sha, arguments.source_state,
                             "local-scaffold")
    evidence.update({
        "kind": "local-fast-reopen-crash-scaffold",
        "case": {"caseId": arguments.termination, "barrierId": BARRIER,
                 "acknowledgement": acknowledgement},
        "canonical": {"authority": "VALID", "beforeSha256": before,
                      "afterSha256": after, "bytesUnchanged": True},
        "derived": {"classification": "ABSENT", "productionBytes": False,
                    "componentCount": 0},
        "process": {"termination": arguments.termination,
                    "exitCode": child.returncode, "gracefulCloseRan": False,
                    "verifierJvm": "PASS"},
        "lifecycle": ["child-started", "canonical-model-written",
                      "derived-plan-no-output-barrier-acknowledged", "abrupt-death",
                      "independent-inspection-passed", "replacement-jvm-passed",
                      "workspace-cleaned"],
        "logs": {"stdoutTail": stdout[-4096:],
                 "stderrTail": (stderr + verifier.stderr)[-4096:],
                 "limitBytesPerStream": 4096},
    })
    write_bundle(workspace / "evidence", evidence)
    validate_bundle(workspace / "evidence")
    print(f"v43FastReopenHarness=PASS termination={arguments.termination}")
    return 0


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
        print(f"v43FastReopenEvidenceValidation=PASS kind={value['kind']}")
        return 0
    return run_case(arguments)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, subprocess.SubprocessError) as failure:
        print(f"v43FastReopenHarness=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
