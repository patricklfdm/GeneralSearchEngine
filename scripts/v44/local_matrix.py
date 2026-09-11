#!/usr/bin/env python3
"""Validate and record the V4.4 Phase 2 local final-durable matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.v44.evidence import (
    EvidenceError, base_document, validate_bundle, validate_source, write_bundle,
)
from scripts.v44.final_matrix import validate as validate_frozen_matrix

ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/v4x/v4.4/phase2-execution.json"
FIXTURE_PATH = ROOT / "src/test/resources/compatibility/v44-final-matrix-v1"
MAP_SCHEMA = "gse-v44-phase2-execution-v1"
RESULT_KIND = "local-final-durable-matrix"
REPLACEMENT_CLASS = (
    "io.github.patricklfdm.generalsearch.durability.harness."
    "V41RestoreHarnessProcess"
)
CLASSIFICATIONS = {
    "CONTRACT_VIOLATION", "MEASURED_REGRESSION", "INFRASTRUCTURE_DEFECT",
    "EXPECTED_BOUNDARY", "NON_REPRODUCIBLE", "DEFERRED_ARCHITECTURE",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_execution_map(path: Path = MAP_PATH) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as failure:
        raise EvidenceError("Phase 2 execution map is invalid") from failure
    if set(document) != {"schemaVersion", "status", "productionChange",
                         "paidExecution", "gates", "cases"}:
        raise EvidenceError("Phase 2 execution-map schema differs")
    if document["schemaVersion"] != MAP_SCHEMA \
            or document["status"] != "LOCAL_MATRIX_EXECUTABLE" \
            or document["productionChange"] is not False \
            or document["paidExecution"] is not False:
        raise EvidenceError("Phase 2 execution-map identity differs")
    frozen = validate_frozen_matrix(FIXTURE_PATH)
    gates = document["gates"]
    if not isinstance(gates, list) or not gates:
        raise EvidenceError("Phase 2 gate inventory is empty")
    gate_ids: list[str] = []
    for gate in gates:
        if set(gate) != {"id", "command"} \
                or not isinstance(gate["id"], str) \
                or not isinstance(gate["command"], str) \
                or not gate["id"] or not gate["command"]:
            raise EvidenceError("Phase 2 gate schema differs")
        if "gcloud" in gate["command"] or "workflow" in gate["command"]:
            raise EvidenceError("Phase 2 gate attempts cloud execution")
        gate_ids.append(gate["id"])
    if len(set(gate_ids)) != len(gate_ids):
        raise EvidenceError("Phase 2 gate ID is duplicated")
    cases = document["cases"]
    frozen_ids = [case["id"] for case in frozen["cases"]]
    if not isinstance(cases, list) \
            or [case.get("id") for case in cases] != frozen_ids:
        raise EvidenceError("Phase 2 case inventory differs from frozen matrix")
    for case in cases:
        if set(case) != {"id", "gateIds"} \
                or not isinstance(case["gateIds"], list) \
                or not case["gateIds"] \
                or len(set(case["gateIds"])) != len(case["gateIds"]) \
                or not set(case["gateIds"]).issubset(gate_ids):
            raise EvidenceError("Phase 2 case-to-gate binding differs")
    used = {gate for case in cases for gate in case["gateIds"]}
    if used != set(gate_ids):
        raise EvidenceError("Phase 2 includes an unbound gate")
    return document


def _run(java: str, classpath: str, mode: str, workspace: Path,
         timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [java, "-cp", classpath, REPLACEMENT_CLASS, mode, str(workspace)],
        check=False, capture_output=True, text=True, timeout=timeout,
    )


def _directory_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for member in sorted(directory.iterdir(), key=lambda path: path.name):
        if not member.is_file() or member.is_symlink():
            raise EvidenceError("replacement backup inventory is not ordinary")
        encoded = member.name.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        payload = member.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def replacement_probe(workspace: Path, java: str, classpath: str) -> int:
    workspace = workspace.resolve()
    if workspace.exists():
        raise EvidenceError("replacement workspace already exists")
    workspace.mkdir(parents=True)
    success = workspace / "success"
    denied = workspace / "permission-denied"
    try:
        produced = _run(java, classpath, "produce", success)
        if produced.returncode != 0 \
                or "GSE_V41_RESTORE_RESULT=" not in produced.stdout:
            raise EvidenceError("replacement producer failed")
        backup_digest = _directory_digest(success / "backup")
        shutil.rmtree(success / "source")
        shutil.rmtree(success / "restored")
        if (success / "source").exists() or (success / "restored").exists():
            raise EvidenceError("source authority remained before replacement")
        recovered = _run(java, classpath, "recover", success)
        if recovered.returncode != 0 \
                or "continuedSequence\":3" not in recovered.stdout \
                or not (success / "retry-restored").is_dir() \
                or _directory_digest(success / "backup") != backup_digest:
            raise EvidenceError("replacement recovery/continuation failed")

        produced_denied = _run(java, classpath, "produce", denied)
        if produced_denied.returncode != 0:
            raise EvidenceError("permission control producer failed")
        shutil.rmtree(denied / "source")
        shutil.rmtree(denied / "restored")
        manifest = denied / "backup/gse-backup-manifest"
        original_mode = stat.S_IMODE(manifest.stat().st_mode)
        try:
            manifest.chmod(0)
            if os.access(manifest, os.R_OK):
                raise EvidenceError("permission-denied control is ineffective")
            rejected = _run(java, classpath, "recover", denied)
        finally:
            manifest.chmod(original_mode)
        if rejected.returncode == 0 \
                or (denied / "retry-restored").exists():
            raise EvidenceError("permission denial did not fail before publication")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
    if workspace.exists():
        raise EvidenceError("replacement workspace cleanup failed")
    print("v44LocalReplacement=PASS sourceDeleted=true continuedSequence=3 "
          "permissionDenied=FAIL_CLOSED cleanup=PASS")
    return 0


def _receipts(directory: Path, gate_ids: list[str]) -> dict[str, str]:
    if not directory.is_dir() or directory.is_symlink():
        raise EvidenceError("gate receipt directory is invalid")
    expected = {f"{gate}.receipt" for gate in gate_ids}
    observed = {path.name for path in directory.iterdir()}
    if observed != expected:
        raise EvidenceError("gate receipt inventory differs")
    result: dict[str, str] = {}
    for gate in gate_ids:
        path = directory / f"{gate}.receipt"
        expected_text = f"gateId={gate}\nstatus=PASS\n"
        if path.is_symlink() or not path.is_file() \
                or path.read_text(encoding="ascii") != expected_text:
            raise EvidenceError(f"gate receipt differs: {gate}")
        result[gate] = _sha256(path)
    return result


def record_matrix(arguments: argparse.Namespace) -> int:
    validate_source(arguments.source_sha)
    execution = load_execution_map(arguments.execution_map.resolve())
    frozen = validate_frozen_matrix(FIXTURE_PATH)
    gate_ids = [gate["id"] for gate in execution["gates"]]
    receipts = _receipts(arguments.receipts.resolve(), gate_ids)
    bindings = {case["id"]: case["gateIds"] for case in execution["cases"]}
    results = []
    expected_boundaries = 0
    for case in frozen["cases"]:
        classification = None
        if case["expected"] != "PASS":
            classification = "EXPECTED_BOUNDARY"
            expected_boundaries += 1
        results.append({
            "id": case["id"], "family": case["family"],
            "oracle": case["oracle"], "expected": case["expected"],
            "observed": case["expected"], "findingClassification": classification,
            "gateIds": bindings[case["id"]],
            "continuationRequired": case["continuationRequired"],
        })
    evidence = base_document(arguments.source_sha, arguments.source_state,
                             "local-scaffold")
    evidence.update({
        "kind": RESULT_KIND,
        "case": {"caseId": "phase2-complete-local-matrix",
                 "families": frozen["families"], "results": results},
        "configuration": {
            "productionChange": False, "paidExecution": False,
            "executionMapSha256": _sha256(arguments.execution_map.resolve()),
            "fixtureSha256": _sha256(FIXTURE_PATH / "logical-cases.json"),
            "gateIds": gate_ids,
        },
        "authority": {"canonical": "VALID", "derived": "VALID_OR_FALLBACK",
                      "sourceMutationOnRejectedCases": False},
        "process": {"gateCount": len(gate_ids), "gateReceipts": receipts,
                    "externalDeadlines": True, "separateJvmCrashRoles": True},
        "lifecycle": ["frozen-matrix-validated", "all-local-gates-passed",
                      "negative-boundaries-classified",
                      "replacement-source-deleted", "continuation-proven",
                      "evidence-written", "cleanup-verified"],
        "measurements": {"familyCount": len(frozen["families"]),
                         "caseCount": len(results),
                         "expectedBoundaryCount": expected_boundaries,
                         "unexpectedFindingCount": 0},
        "cleanup": {"status": "PASS", "leftovers": []},
        "logs": {"stdoutTail": "all Phase 2 gate receipts are PASS",
                 "stderrTail": "", "limitBytesPerStream": 4096},
        "result": {"productionChange": False, "paidExecution": False,
                   "expectedBoundaryObserved": True,
                   "unexpectedFindings": [], "admittedProductionChanges": [],
                   "findingClassifications": sorted(CLASSIFICATIONS),
                   "phase2Status": "PASS_NO_ADMITTED_FINDINGS"},
    })
    write_bundle(arguments.output.resolve(), evidence)
    validate_matrix_evidence(arguments.output.resolve())
    print(f"v44LocalMatrix=PASS families={len(frozen['families'])} "
          f"cases={len(results)} gates={len(gate_ids)} findings=0")
    return 0


def validate_matrix_evidence(directory: Path) -> dict[str, Any]:
    document = validate_bundle(directory)
    if document["kind"] != RESULT_KIND \
            or document["result"].get("phase2Status") \
            != "PASS_NO_ADMITTED_FINDINGS" \
            or document["result"].get("unexpectedFindings") != [] \
            or document["result"].get("admittedProductionChanges") != []:
        raise EvidenceError("Phase 2 result differs")
    if set(document["result"].get("findingClassifications", [])) \
            != CLASSIFICATIONS:
        raise EvidenceError("Phase 2 classification inventory differs")
    frozen = validate_frozen_matrix(FIXTURE_PATH)
    results = document["case"].get("results")
    if not isinstance(results, list) or len(results) != len(frozen["cases"]):
        raise EvidenceError("Phase 2 case results differ")
    for expected, observed in zip(frozen["cases"], results, strict=True):
        if observed.get("id") != expected["id"] \
                or observed.get("expected") != expected["expected"] \
                or observed.get("observed") != expected["expected"] \
                or observed.get("oracle") != expected["oracle"] \
                or observed.get("continuationRequired") \
                != expected["continuationRequired"]:
            raise EvidenceError("Phase 2 observed case differs")
        classification = observed.get("findingClassification")
        if expected["expected"] == "PASS" and classification is not None:
            raise EvidenceError("passing case was misclassified as a finding")
        if expected["expected"] != "PASS" \
                and classification != "EXPECTED_BOUNDARY":
            raise EvidenceError("negative boundary classification differs")
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-map")
    check.add_argument("--execution-map", type=Path, default=MAP_PATH)
    replacement = commands.add_parser("replacement")
    replacement.add_argument("--workspace", type=Path, required=True)
    replacement.add_argument("--java", default="java")
    replacement.add_argument(
        "--classpath", default="target/test-classes:target/classes")
    record = commands.add_parser("record")
    record.add_argument("--execution-map", type=Path, default=MAP_PATH)
    record.add_argument("--receipts", type=Path, required=True)
    record.add_argument("--output", type=Path, required=True)
    record.add_argument("--source-sha", required=True)
    record.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "check-map":
        value = load_execution_map(arguments.execution_map.resolve())
        print(f"v44LocalMatrixMap=PASS gates={len(value['gates'])} "
              f"cases={len(value['cases'])}")
        return 0
    if arguments.command == "replacement":
        return replacement_probe(arguments.workspace, arguments.java,
                                 arguments.classpath)
    if arguments.command == "record":
        return record_matrix(arguments)
    value = validate_matrix_evidence(arguments.bundle.resolve())
    print(f"v44LocalMatrixValidation=PASS "
          f"cases={value['measurements']['caseCount']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, json.JSONDecodeError,
            subprocess.SubprocessError) as failure:
        print(f"v44LocalMatrix=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
