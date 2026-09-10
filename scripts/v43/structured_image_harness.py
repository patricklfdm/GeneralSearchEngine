#!/usr/bin/env python3
"""Separate-JVM crash harness for V4.3 production structured images."""

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
BARRIERS = (
    "v43-derived-before-component-rename-v1",
    "v43-derived-after-component-parent-force-v1",
    "v43-derived-before-catalog-publication-v1",
    "v43-derived-after-catalog-parent-force-v1",
)


def _line(process: subprocess.Popen[str], timeout: float) -> str:
    assert process.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    ready = selector.select(timeout)
    selector.close()
    if not ready:
        process.kill()
        process.wait(timeout=5)
        raise EvidenceError("production barrier acknowledgement timed out")
    value = process.stdout.readline().rstrip("\n")
    if not value:
        raise EvidenceError("child exited before production barrier")
    return value


def _canonical_hashes(store: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(store.iterdir()):
        if not path.is_file() or path.is_symlink() \
                or path.name.startswith("gse-derived-") \
                or path.name == "gse-lock":
            continue
        result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def run_case(arguments: argparse.Namespace) -> int:
    validate_source(arguments.source_sha)
    if arguments.barrier not in BARRIERS:
        raise EvidenceError("unsupported Phase 3 barrier")
    workspace = arguments.workspace.resolve()
    if workspace.exists():
        raise EvidenceError("workspace already exists")
    workspace.mkdir(parents=True)
    store = workspace / "store"
    action = "halt" if arguments.termination == "internal-halt" else "wait"
    command = [
        arguments.java,
        f"-Dgse.v4.crashBarrier={arguments.barrier}",
        f"-Dgse.v4.crashAction={action}",
        "-cp", arguments.classpath, PROCESS_CLASS,
        "phase3-crash", str(store), arguments.barrier,
    ]
    child = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    line = _line(child, arguments.timeout)
    prefix = "GSE_BARRIER_READY="
    if not line.startswith(prefix):
        child.kill()
        child.wait(timeout=5)
        raise EvidenceError("invalid production barrier acknowledgement")
    acknowledgement = json.loads(line[len(prefix):])
    if acknowledgement.get("barrierId") != arguments.barrier:
        child.kill()
        child.wait(timeout=5)
        raise EvidenceError("production barrier identity differs")
    if arguments.termination == "external-kill":
        child.kill()
    stdout, stderr = child.communicate(timeout=arguments.timeout)
    expected = 86 if arguments.termination == "internal-halt" else -9
    if child.returncode != expected:
        raise EvidenceError(f"unexpected abrupt exit: {child.returncode}")
    before = _canonical_hashes(store)
    inspector = subprocess.run(
        [arguments.java, "-cp", arguments.classpath, PROCESS_CLASS,
         "phase3-inspect", str(store), arguments.barrier],
        check=False, capture_output=True, text=True, timeout=arguments.timeout,
    )
    inspect_prefix = "GSE_V43_INSPECTION_RESULT="
    if inspector.returncode != 0 or not inspector.stdout.startswith(inspect_prefix):
        raise EvidenceError(
            "independent pre-open inspection failed: " + inspector.stderr[-1024:])
    inspected = json.loads(inspector.stdout[len(inspect_prefix):])
    if inspected.get("canonicalAuthority") != "VALID":
        raise EvidenceError("pre-open canonical authority differs")
    verifier = subprocess.run(
        [arguments.java, "-cp", arguments.classpath, PROCESS_CLASS,
         "phase3-verify", str(store), arguments.barrier],
        check=False, capture_output=True, text=True, timeout=arguments.timeout,
    )
    verify_prefix = "GSE_V43_VERIFY_RESULT="
    if verifier.returncode != 0 or not verifier.stdout.startswith(verify_prefix):
        raise EvidenceError(
            "replacement verifier JVM failed: " + verifier.stderr[-1024:])
    verified = json.loads(verifier.stdout[len(verify_prefix):])
    after = _canonical_hashes(store)
    if before != after or verified.get("canonicalAuthority") != "VALID" \
            or verified.get("derivedState") != "VALID":
        raise EvidenceError("canonical authority or refreshed image differs")
    shutil.rmtree(store)
    evidence = base_document(
        arguments.source_sha, arguments.source_state, "local-scaffold")
    evidence.update({
        "kind": "local-structured-image-crash",
        "case": {
            "caseId": f"{arguments.barrier}:{arguments.termination}",
            "barrierId": arguments.barrier,
            "acknowledgement": acknowledgement,
        },
        "configuration": {
            "productionFormat12": True,
            "productionDerivedState": True,
            "paidExecution": False,
        },
        "canonical": {
            "authority": "VALID", "bytesUnchanged": True,
            "memberSha256": after,
        },
        "derived": {
            "classification": "VALID", "productionBytes": True,
            "preOpenClassification": inspected["derivedState"],
            "reopenOutcome": verified["reopenOutcome"],
            "refreshAttempted": verified["refreshAttempted"],
            "refreshSucceeded": verified["refreshSucceeded"],
        },
        "process": {
            "termination": arguments.termination,
            "exitCode": child.returncode,
            "gracefulCloseRan": False,
            "inspectorJvm": "PASS", "verifierJvm": "PASS",
        },
        "lifecycle": [
            "production-store-created", "canonical-checkpoint-published",
            "derived-barrier-acknowledged", "abrupt-death",
            "independent-pre-open-inspection-passed",
            "replacement-jvm-recovered", "canonical-bytes-matched",
            "valid-derived-generation-observed", "workspace-cleaned",
        ],
        "logs": {
            "stdoutTail": stdout[-4096:],
            "stderrTail": (stderr + inspector.stderr + verifier.stderr)[-4096:],
            "limitBytesPerStream": 4096,
        },
        "result": {
            "paidExecution": False, "productionDerivedState": True,
        },
    })
    write_bundle(workspace / "evidence", evidence)
    validate_bundle(workspace / "evidence")
    print("v43StructuredImageHarness=PASS "
          f"barrier={arguments.barrier} termination={arguments.termination}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--workspace", type=Path, required=True)
    run.add_argument("--source-sha", required=True)
    run.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    run.add_argument("--barrier", choices=BARRIERS, required=True)
    run.add_argument("--termination", choices=("internal-halt", "external-kill"),
                     required=True)
    run.add_argument("--java", default="java")
    run.add_argument("--classpath", default="target/test-classes:target/classes")
    run.add_argument("--timeout", type=float, default=30.0)
    validate = subparsers.add_parser("validate")
    validate.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "validate":
        value = validate_bundle(arguments.bundle)
        print(f"v43StructuredImageEvidenceValidation=PASS kind={value['kind']}")
        return 0
    return run_case(arguments)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, subprocess.SubprocessError) as failure:
        print(f"v43StructuredImageHarness=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
