#!/usr/bin/env python3
"""Strict, checksummed V4.4 Phase 1 evidence bundles."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "gse-v44-final-durable-evidence-v1"
SUITE = "v4.4-final-durable-suite-v1"
PRESET = "v4.4-final-durable-v1"
CHECKSUMS = "artifact-checksums.sha256"
SOURCE = re.compile(r"[0-9a-f]{40}")
PROFILES = {"local-scaffold", "experiment", "canonical", "failure-drill"}
TOP_LEVEL = {
    "schemaVersion", "kind", "status", "sourceCommit", "sourceState",
    "suite", "preset", "profile", "case", "configuration", "authority",
    "process", "lifecycle", "measurements", "cleanup", "logs", "result",
}


class EvidenceError(ValueError):
    """Evidence is malformed, unbounded, or internally inconsistent."""


def canonical_json(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_source(value: object) -> str:
    if not isinstance(value, str) or SOURCE.fullmatch(value) is None:
        raise EvidenceError("source commit must be a full lowercase SHA")
    return value


def write_bundle(directory: Path, document: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    value = dict(document)
    value["schemaVersion"] = SCHEMA
    evidence = directory / "evidence.json"
    evidence.write_bytes(canonical_json(value))
    (directory / CHECKSUMS).write_text(
        f"{sha256(evidence)}  evidence.json\n", encoding="ascii")


def validate_bundle(directory: Path) -> dict[str, Any]:
    if not directory.is_dir() or directory.is_symlink():
        raise EvidenceError("evidence path must be a non-symbolic directory")
    if {path.name for path in directory.iterdir()} != {"evidence.json", CHECKSUMS}:
        raise EvidenceError("evidence inventory differs")
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file():
            raise EvidenceError("evidence member is not a regular file")
    evidence = directory / "evidence.json"
    if evidence.stat().st_size > 1024 * 1024:
        raise EvidenceError("evidence exceeds one MiB")
    if (directory / CHECKSUMS).read_text(encoding="ascii") != \
            f"{sha256(evidence)}  evidence.json\n":
        raise EvidenceError("artifact checksum mismatch")
    try:
        document = json.loads(evidence.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as failure:
        raise EvidenceError("invalid evidence JSON") from failure
    if set(document) != TOP_LEVEL or document.get("schemaVersion") != SCHEMA:
        raise EvidenceError("evidence schema differs")
    if document.get("suite") != SUITE or document.get("preset") != PRESET:
        raise EvidenceError("suite or preset identity differs")
    if document.get("profile") not in PROFILES:
        raise EvidenceError("invalid evidence profile")
    validate_source(document.get("sourceCommit"))
    if document.get("sourceState") not in {"clean", "dirty"}:
        raise EvidenceError("invalid source state")
    for field in ("case", "configuration", "authority", "process",
                  "measurements", "cleanup", "logs", "result"):
        if not isinstance(document.get(field), dict):
            raise EvidenceError(f"{field} must be an object")
    if not isinstance(document.get("lifecycle"), list):
        raise EvidenceError("lifecycle must be ordered")
    logs = document["logs"]
    limit = logs.get("limitBytesPerStream")
    if not isinstance(limit, int) or not 0 < limit <= 65_536:
        raise EvidenceError("invalid log bound")
    for name in ("stdoutTail", "stderrTail"):
        value = logs.get(name)
        if not isinstance(value, str) or len(value.encode()) > limit:
            raise EvidenceError("log is not bounded")
    if document.get("status") == "PASS":
        canonical = document["authority"].get("canonical")
        if canonical != "VALID" and not (
                canonical in {"ABSENT_EXPECTED", "INVALID_EXPECTED"}
                and document["result"].get("expectedBoundaryObserved") is True):
            raise EvidenceError("passing evidence has an invalid authority result")
        if document["cleanup"].get("status") != "PASS" \
                or document["cleanup"].get("leftovers") != []:
            raise EvidenceError("passing evidence requires exact cleanup")
    elif document.get("status") != "FAIL":
        raise EvidenceError("invalid status")
    return document


def base_document(source: str, source_state: str, profile: str) -> dict[str, Any]:
    return {
        "kind": "phase1-scaffold", "status": "PASS", "sourceCommit": source,
        "sourceState": source_state, "suite": SUITE, "preset": PRESET,
        "profile": profile, "case": {},
        "configuration": {"productionChange": False, "paidExecution": False},
        "authority": {"canonical": "VALID", "derived": "ABSENT"},
        "process": {}, "lifecycle": [], "measurements": {},
        "cleanup": {"status": "PASS", "leftovers": []},
        "logs": {"stdoutTail": "", "stderrTail": "",
                 "limitBytesPerStream": 4096},
        "result": {"productionChange": False, "paidExecution": False},
    }
