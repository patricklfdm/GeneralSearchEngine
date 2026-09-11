#!/usr/bin/env python3
"""Independent validator for the frozen V4.4 final-hardening matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "gse-v44-final-matrix-v1"
FORMATS = ["1.0", "1.1", "1.2"]
CLASSIFICATIONS = [
    "CONTRACT_VIOLATION", "MEASURED_REGRESSION", "INFRASTRUCTURE_DEFECT",
    "EXPECTED_BOUNDARY", "NON_REPRODUCIBLE", "DEFERRED_ARCHITECTURE",
]
EXPECTED_FILES = ["README.md", "logical-cases.json"]


class MatrixError(ValueError):
    """The frozen independent matrix is incomplete or has drifted."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_inventory(root: Path) -> None:
    lines = (root / "fixture-checksums.sha256").read_text(
        encoding="ascii").splitlines()
    if len(lines) != len(EXPECTED_FILES):
        raise MatrixError("checksum inventory differs")
    names: list[str] = []
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)", line)
        if match is None:
            raise MatrixError("invalid checksum line")
        name = match.group(2)
        names.append(name)
        if not (root / name).is_file() or _sha256(root / name) != match.group(1):
            raise MatrixError(f"fixture checksum differs: {name}")
    if names != EXPECTED_FILES:
        raise MatrixError("fixture member order differs")
    observed = sorted(path.name for path in root.iterdir()
                      if path.name != "fixture-checksums.sha256")
    if observed != sorted(EXPECTED_FILES):
        raise MatrixError("unexpected fixture member")


def validate(root: Path) -> dict[str, object]:
    _check_inventory(root)
    try:
        document = json.loads((root / "logical-cases.json").read_text(
            encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as failure:
        raise MatrixError("logical cases are not valid JSON") from failure
    if set(document) != {"schemaVersion", "status", "formats",
                         "classifications", "families", "cases"}:
        raise MatrixError("matrix schema differs")
    if document["schemaVersion"] != SCHEMA or document["status"] != "PHASE2_PENDING":
        raise MatrixError("matrix identity differs")
    if document["formats"] != FORMATS or document["classifications"] != CLASSIFICATIONS:
        raise MatrixError("format or classification inventory differs")
    families = document["families"]
    if not isinstance(families, list) or len(families) != 10 \
            or len(set(families)) != len(families):
        raise MatrixError("exact family inventory differs")
    cases = document["cases"]
    if not isinstance(cases, list) or len(cases) < 18:
        raise MatrixError("bounded case inventory is incomplete")
    identifiers: set[str] = set()
    seen_families: set[str] = set()
    for case in cases:
        if set(case) != {"id", "family", "oracle", "fault", "expected",
                         "continuationRequired"}:
            raise MatrixError("case schema differs")
        if case["id"] in identifiers or case["family"] not in families:
            raise MatrixError("duplicate case or unknown family")
        if case["expected"] not in {
                "PASS", "FAIL_CLOSED", "FALLBACK", "REJECT_BEFORE_MUTATION"}:
            raise MatrixError("unknown expected result")
        if case["oracle"] not in {
                "logical-model", "codec-free-parser", "fixture-bytes",
                "published-4.3", "pre-interruption-checksum", "external-inventory"}:
            raise MatrixError("oracle is not independent")
        if not isinstance(case["continuationRequired"], bool):
            raise MatrixError("continuation flag differs")
        identifiers.add(case["id"])
        seen_families.add(case["family"])
    if seen_families != set(families):
        raise MatrixError("not every family has a case")
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    value = validate(args.root.resolve())
    print(f"v44FinalMatrix=PASS families={len(value['families'])} "
          f"cases={len(value['cases'])} status={value['status']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MatrixError as failure:
        print(f"v44FinalMatrix=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
