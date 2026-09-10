#!/usr/bin/env python3
"""Independent validator for Phase 1 logical derived-state fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "gse-v43-derived-logical-fixtures-v1"
STATUS_ORDER = [
    "NOT_APPLICABLE", "ABSENT", "VALID", "PARTIAL", "STALE",
    "INCOMPATIBLE", "INCOMPLETE", "CORRUPT",
]
COMPONENT_KINDS = ["EQUALITY", "RANGE", "PREFIX", "TEXT"]
COMPONENT_STATES = {
    "ADMISSIBLE", "MISSING", "STALE", "INCOMPATIBLE", "INCOMPLETE", "CORRUPT",
}
EXPECTED_FILES = ["README.md", "logical-fixtures.json"]


class FixtureError(ValueError):
    """A fixture violates the frozen independent Phase 1 model."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inventory(root: Path) -> dict[str, str]:
    checksum_file = root / "fixture-checksums.sha256"
    if not checksum_file.is_file():
        raise FixtureError("checksum inventory is absent")
    result: dict[str, str] = {}
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)", line)
        if match is None or match.group(2) in result:
            raise FixtureError("invalid checksum inventory")
        result[match.group(2)] = match.group(1)
    if list(result) != EXPECTED_FILES:
        raise FixtureError("fixture inventory differs")
    for name, expected in result.items():
        path = root / name
        if not path.is_file() or _sha256(path) != expected:
            raise FixtureError(f"fixture checksum differs: {name}")
    observed = sorted(path.name for path in root.iterdir()
                      if path.name != "fixture-checksums.sha256")
    if observed != sorted(EXPECTED_FILES):
        raise FixtureError("unexpected fixture member")
    return result


def classify(case: dict[str, object]) -> str:
    if case.get("canonicalAuthority") != "VALID":
        raise FixtureError("Phase 1 derived fixture cannot mask canonical failure")
    minor = case.get("formatMinor")
    if not isinstance(minor, int) or minor < 0:
        raise FixtureError("invalid format minor")
    if minor < 2:
        return "NOT_APPLICABLE"
    if minor != 2:
        raise FixtureError("Phase 1 supports only modeled minor 2")
    catalog = case.get("catalog")
    if catalog == "ABSENT":
        return "ABSENT"
    if catalog in {"STALE", "INCOMPATIBLE", "INCOMPLETE", "CORRUPT"}:
        return str(catalog)
    if catalog != "VALID":
        raise FixtureError("unknown catalog state")
    components = case.get("components")
    if not isinstance(components, list) or len(components) != 4:
        raise FixtureError("valid catalog must enumerate four model components")
    ordinals: list[int] = []
    admissible = 0
    for component in components:
        if not isinstance(component, dict):
            raise FixtureError("component must be an object")
        ordinal = component.get("ordinal")
        kind = component.get("kind")
        status = component.get("status")
        if not isinstance(ordinal, int) or kind not in COMPONENT_KINDS \
                or status not in COMPONENT_STATES:
            raise FixtureError("invalid component identity or status")
        if kind == "TEXT" and component.get("analyzer") != "gse-simple-v1":
            raise FixtureError("text component analyzer is not frozen")
        ordinals.append(ordinal)
        admissible += status == "ADMISSIBLE"
    if ordinals != [0, 1, 2, 3]:
        raise FixtureError("component ordinals are not canonical")
    return "VALID" if admissible == len(components) else "PARTIAL"


def validate(root: Path) -> dict[str, object]:
    root = root.resolve()
    _inventory(root)
    try:
        document = json.loads((root / "logical-fixtures.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as failure:
        raise FixtureError("logical fixture is not valid JSON") from failure
    if document.get("schemaVersion") != SCHEMA \
            or document.get("format") != "PHASE2_PENDING" \
            or document.get("statusOrder") != STATUS_ORDER \
            or document.get("componentKinds") != COMPONENT_KINDS:
        raise FixtureError("fixture header differs")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != 10:
        raise FixtureError("exact case matrix differs")
    identifiers: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise FixtureError("invalid case")
        if case["id"] in identifiers:
            raise FixtureError("duplicate case identifier")
        identifiers.add(case["id"])
        if classify(case) != case.get("expected"):
            raise FixtureError(f"classification differs: {case['id']}")
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    document = validate(arguments.root)
    print(f"v43DerivedFixture=PASS cases={len(document['cases'])} "
          f"format={document['format']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FixtureError as failure:
        print(f"v43DerivedFixture=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
