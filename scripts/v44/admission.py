#!/usr/bin/env python3
"""Validate the V4.4 Phase 3 zero-production-change admission decision."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.v44.final_matrix import validate as validate_frozen_matrix
from scripts.v44.local_matrix import FIXTURE_PATH, load_execution_map

ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = ROOT / "docs/v4x/v4.4/phase3-admission.json"
SCHEMA = "gse-v44-phase3-admission-v1"
SOURCE = re.compile(r"[0-9a-f]{40}")
FIELDS = {
    "schemaVersion", "status", "phase2CandidateCommit", "phase2Result",
    "acceptedContractViolations", "acceptedMeasuredRegressions",
    "expectedBoundaryCaseIds", "productionChange", "publicApiChange",
    "formatChange", "authorityChange", "paidExecution", "nextPhase",
}


class AdmissionError(ValueError):
    """The Phase 3 admission record is incomplete or authorizes hidden scope."""


def validate(path: Path = DECISION_PATH) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as failure:
        raise AdmissionError("Phase 3 admission record is invalid") from failure
    if set(document) != FIELDS:
        raise AdmissionError("Phase 3 admission schema differs")
    if document["schemaVersion"] != SCHEMA \
            or document["status"] != "ZERO_PRODUCTION_CHANGE_REQUIRED" \
            or document["phase2Result"] != "PASS_NO_ADMITTED_FINDINGS" \
            or document["nextPhase"] != "PHASE4_MEASUREMENT_ONLY":
        raise AdmissionError("Phase 3 decision identity differs")
    if SOURCE.fullmatch(document["phase2CandidateCommit"]) is None:
        raise AdmissionError("Phase 2 candidate commit is not exact")
    for name in ("productionChange", "publicApiChange", "formatChange",
                 "authorityChange", "paidExecution"):
        if document[name] is not False:
            raise AdmissionError(f"Phase 3 unexpectedly authorizes {name}")
    if document["acceptedContractViolations"] != [] \
            or document["acceptedMeasuredRegressions"] != []:
        raise AdmissionError("Phase 3 contains an unsupported admitted finding")

    load_execution_map()
    frozen = validate_frozen_matrix(FIXTURE_PATH)
    expected_boundaries = [
        case["id"] for case in frozen["cases"] if case["expected"] != "PASS"
    ]
    if document["expectedBoundaryCaseIds"] != expected_boundaries:
        raise AdmissionError("expected-boundary inventory differs")
    return document


def validate_production_delta() -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "src/main"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    if status.stdout:
        raise AdmissionError("Phase 3 working tree changes production sources")
    parent = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^"], cwd=ROOT, check=False,
        capture_output=True, text=True,
    )
    if parent.returncode == 0:
        delta = subprocess.run(
            ["git", "diff", "--quiet", "HEAD^", "HEAD", "--", "src/main"],
            cwd=ROOT, check=False,
        )
        if delta.returncode != 0:
            raise AdmissionError("Phase 3 commit changes production sources")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", type=Path, default=DECISION_PATH)
    parser.add_argument("--check-production-delta", action="store_true")
    arguments = parser.parse_args()
    document = validate(arguments.decision.resolve())
    if arguments.check_production_delta:
        validate_production_delta()
    print("v44Phase3Admission=PASS productionChange=false "
          f"expectedBoundaries={len(document['expectedBoundaryCaseIds'])} "
          "next=PHASE4_MEASUREMENT_ONLY")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AdmissionError, OSError, subprocess.SubprocessError) as failure:
        print(f"v44Phase3Admission=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
