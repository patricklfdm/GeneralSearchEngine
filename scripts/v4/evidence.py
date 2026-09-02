#!/usr/bin/env python3
"""Checksummed Phase 1 evidence bundles shared by local and fake-cloud lanes."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "gse-v4-durable-evidence-v1"
CHECKSUMS = "artifact-checksums.sha256"
MAX_EVIDENCE_BYTES = 1024 * 1024


class EvidenceError(ValueError):
    """Raised when an evidence bundle violates its frozen Phase 1 shape."""


def canonical_json(document: dict[str, Any]) -> bytes:
    return (json.dumps(
        document,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n").encode("utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_source_commit(source: object) -> str:
    if not isinstance(source, str) or re.fullmatch(r"[0-9a-f]{40}", source) is None:
        raise EvidenceError("source commit must be a full lowercase hexadecimal SHA")
    return source


def write_bundle(directory: Path, document: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    evidence = dict(document)
    evidence["schemaVersion"] = SCHEMA
    evidence_path = directory / "evidence.json"
    evidence_path.write_bytes(canonical_json(evidence))
    checksum = f"{sha256(evidence_path)}  evidence.json\n"
    (directory / CHECKSUMS).write_text(checksum, encoding="ascii")


def validate_bundle(directory: Path) -> dict[str, Any]:
    if not directory.is_dir() or directory.is_symlink():
        raise EvidenceError("evidence path must be a regular directory")
    expected_names = {"evidence.json", CHECKSUMS}
    actual = {entry.name for entry in directory.iterdir()}
    if actual != expected_names:
        raise EvidenceError(f"unexpected evidence members: {sorted(actual)}")
    for entry in directory.iterdir():
        if not entry.is_file() or entry.is_symlink():
            raise EvidenceError(f"non-regular evidence member: {entry.name}")
    evidence_path = directory / "evidence.json"
    if evidence_path.stat().st_size > MAX_EVIDENCE_BYTES:
        raise EvidenceError("evidence JSON exceeds the one MiB artifact limit")
    checksum_line = (directory / CHECKSUMS).read_text(encoding="ascii")
    expected_line = f"{sha256(evidence_path)}  evidence.json\n"
    if checksum_line != expected_line:
        raise EvidenceError("artifact checksum mismatch")
    try:
        document = json.loads(evidence_path.read_text("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as failure:
        raise EvidenceError("evidence JSON is invalid") from failure
    required = {
        "schemaVersion",
        "kind",
        "status",
        "sourceCommit",
        "environment",
        "configuration",
        "case",
        "submittedHistory",
        "futureOutcomes",
        "process",
        "inspection",
        "recovery",
        "logs",
        "cleanup",
        "lifecycle",
        "result",
    }
    missing = sorted(required.difference(document))
    if missing:
        raise EvidenceError(f"missing evidence fields: {missing}")
    if document["schemaVersion"] != SCHEMA:
        raise EvidenceError("unsupported evidence schema")
    if document["status"] not in {"PASS", "FAIL"}:
        raise EvidenceError("invalid evidence status")
    validate_source_commit(document["sourceCommit"])
    environment = document["environment"]
    if not isinstance(environment, dict):
        raise EvidenceError("environment must be an object")
    if environment.get("sourceState") not in {"clean", "dirty"}:
        raise EvidenceError("environment sourceState must be clean or dirty")
    for field in (
            "configuration", "case", "process", "inspection", "recovery",
            "logs", "cleanup", "result"):
        if not isinstance(document[field], dict):
            raise EvidenceError(f"{field} must be an object")
    for field in ("submittedHistory", "futureOutcomes", "lifecycle"):
        if not isinstance(document[field], list):
            raise EvidenceError(f"{field} must be an ordered list")
    if (document["status"] == "PASS"
            and document["cleanup"].get("status") != "PASS"):
        raise EvidenceError("passing evidence requires verified cleanup")
    logs = document["logs"]
    limit = logs.get("limitBytesPerStream")
    if not isinstance(limit, int) or not 0 < limit <= MAX_EVIDENCE_BYTES:
        raise EvidenceError("invalid bounded-log limit")
    for stream in ("stdoutTail", "stderrTail"):
        value = logs.get(stream)
        if not isinstance(value, str) or len(value.encode("utf-8")) > limit:
            raise EvidenceError(f"{stream} exceeds its evidence limit")
    return document
