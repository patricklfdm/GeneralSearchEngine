#!/usr/bin/env python3
"""Separate-JVM Phase 3 migration crash checks over production bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import selectors
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.v42.evidence import (
    EvidenceError,
    PRESET,
    SUITE,
    validate_bundle,
    validate_source,
    write_bundle,
)

PROCESS_CLASSES = {
    "identity": (
        "io.github.patricklfdm.generalsearch.durability.harness."
        "V42ProductionMigrationHarnessProcess"
    ),
    "catalog": (
        "io.github.patricklfdm.generalsearch.durability.harness."
        "V42TransformMigrationHarnessProcess"
    ),
}
BARRIERS = {
    "v42-migration-before-final-rename-v1": False,
    "v42-migration-after-parent-force-v1": True,
}


def tree_digest(directory: Path) -> str:
    digest = hashlib.sha256(b"gse-v42-source-tree-v1\x00")
    for member in sorted(directory.iterdir(), key=lambda path: path.name):
        if not member.is_file() or member.is_symlink():
            raise EvidenceError("source inventory is not regular")
        name = member.name.encode("utf-8")
        value = member.read_bytes()
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(hashlib.sha256(value).digest())
    return digest.hexdigest()


def barrier_line(process: subprocess.Popen[str], timeout: float) -> str:
    assert process.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    ready = selector.select(timeout)
    selector.close()
    if not ready:
        process.kill()
        process.wait(timeout=5)
        raise EvidenceError("production migration barrier timed out")
    return process.stdout.readline().rstrip("\n")


def run(arguments: argparse.Namespace) -> int:
    validate_source(arguments.source_sha)
    if arguments.barrier not in BARRIERS:
        raise EvidenceError("unsupported Phase 3 barrier")
    workspace = arguments.workspace.resolve()
    if workspace.exists():
        raise EvidenceError("workspace already exists")
    workspace.mkdir(parents=True)
    source = workspace / "source"
    target = workspace / "target"
    command = [arguments.java, "-cp", arguments.classpath,
               PROCESS_CLASSES[arguments.scenario]]
    prepared = subprocess.run(
        command + ["prepare", str(source), str(target), arguments.barrier],
        check=False, capture_output=True, text=True, timeout=arguments.timeout)
    if prepared.returncode != 0 \
            or "GSE_V42_PREPARE_RESULT=PASS" not in prepared.stdout:
        raise EvidenceError("production source preparation failed")
    before = tree_digest(source)
    child = subprocess.Popen(
        command + ["apply-halt", str(source), str(target), arguments.barrier],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True)
    line = barrier_line(child, arguments.timeout)
    prefix = "GSE_BARRIER_READY="
    if not line.startswith(prefix):
        child.kill()
        child.wait(timeout=5)
        raise EvidenceError("invalid production barrier acknowledgement")
    acknowledgement = json.loads(line[len(prefix):])
    if acknowledgement.get("barrierId") != arguments.barrier:
        raise EvidenceError("production barrier identity mismatch")
    stdout, stderr = child.communicate(timeout=arguments.timeout)
    if child.returncode != 86:
        raise EvidenceError(f"unexpected production child exit: {child.returncode}")
    verified = subprocess.run(
        command + ["verify", str(source), str(target), arguments.barrier],
        check=False, capture_output=True, text=True, timeout=arguments.timeout)
    if verified.returncode != 0 \
            or not verified.stdout.startswith("GSE_V42_VERIFY_RESULT="):
        raise EvidenceError("separate production verifier failed")
    after = tree_digest(source)
    if before != after:
        raise EvidenceError("migration crash changed source bytes")
    target_published = BARRIERS[arguments.barrier]
    if target.exists() != target_published:
        raise EvidenceError("target authority state disagrees with barrier")
    shutil.rmtree(workspace)
    workspace.mkdir()
    evidence = {
        "schemaVersion": "placeholder",
        "kind": ("local-production-migration-crash"
                 if arguments.scenario == "identity"
                 else "local-production-transform-migration-crash"),
        "status": "PASS",
        "sourceCommit": arguments.source_sha,
        "sourceState": "clean",
        "suite": SUITE,
        "preset": PRESET,
        "profile": "failure-drill",
        "case": {"barrierId": arguments.barrier,
                 "acknowledgement": acknowledgement},
        "configuration": {"productionFormat11": True,
                          "productionMigration": True,
                          "transformScenario": arguments.scenario,
                          "paidExecution": False},
        "source": {"format": "gse-durable (1,0)",
                   "beforeSha256": before, "afterSha256": after,
                   "bytesUnchanged": True},
        "target": {"format": "gse-durable (1,1)",
                   "state": "VALID" if target_published else "ABSENT"},
        "migration": {"plan": "PRODUCTION_PASS",
                      "transform": ("identity-format-v1"
                                    if arguments.scenario == "identity"
                                    else "catalog-schema-key-v1"),
                      "apply": "INTERRUPTED_AT_BARRIER"},
        "rollback": {"publishedVersion": "4.1.0",
                     "status": "SOURCE_BYTES_PRESERVED"},
        "process": {"termination": "internal-halt", "exitCode": 86,
                    "verifierJvm": "PASS"},
        "lifecycle": ["source-prepared", "plan-completed",
                      "apply-barrier-acknowledged", "abrupt-death",
                      "separate-verifier-passed", "source-identity-matched",
                      "workspace-cleaned"],
        "cleanup": {"status": "PASS", "leftovers": []},
        "logs": {"stdoutTail": stdout[-4096:],
                 "stderrTail": (stderr + verified.stderr)[-4096:],
                 "limitBytesPerStream": 4096},
        "result": {"paidExecution": False, "productionMigration": True,
                   "targetPublished": target_published},
    }
    write_bundle(workspace / "evidence", evidence)
    validate_bundle(workspace / "evidence")
    print("v42ProductionMigrationCrash=PASS "
          f"scenario={arguments.scenario} barrier={arguments.barrier}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    execute = subparsers.add_parser("run")
    execute.add_argument("--workspace", type=Path, required=True)
    execute.add_argument("--source-sha", required=True)
    execute.add_argument("--barrier", choices=tuple(BARRIERS), required=True)
    execute.add_argument("--scenario", choices=tuple(PROCESS_CLASSES),
                         default="identity")
    execute.add_argument("--java", default="java")
    execute.add_argument(
        "--classpath", default="target/test-classes:target/classes")
    execute.add_argument("--timeout", type=float, default=30.0)
    validate = subparsers.add_parser("validate")
    validate.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "validate":
        value = validate_bundle(arguments.bundle)
        print(f"v42MigrationEvidenceValidation=PASS kind={value['kind']}")
        return 0
    return run(arguments)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, subprocess.SubprocessError) as failure:
        print(f"v42ProductionMigrationCrash=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
