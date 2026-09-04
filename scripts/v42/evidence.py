#!/usr/bin/env python3
"""Canonical checksummed V4.2 storage-evolution evidence bundles."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "gse-v42-migration-evidence-v1"
SUITE = "v4.2-storage-evolution-suite-v1"
PRESET = "v4.2-storage-evolution-v1"
CHECKSUMS = "artifact-checksums.sha256"
MAX_BYTES = 1024 * 1024
SOURCE = re.compile(r"[0-9a-f]{40}")
TOP_LEVEL = {
    "schemaVersion", "kind", "status", "sourceCommit", "sourceState",
    "suite", "preset", "profile", "case", "configuration", "source",
    "target", "migration", "rollback", "process", "lifecycle", "cleanup",
    "logs", "result",
}


class EvidenceError(ValueError):
    """Evidence is missing, malformed, unbounded, or internally inconsistent."""


def canonical_json(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_source(source: object) -> str:
    if not isinstance(source, str) or SOURCE.fullmatch(source) is None:
        raise EvidenceError("source commit must be a full lowercase SHA")
    return source


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
    members = {entry.name for entry in directory.iterdir()}
    if members != {"evidence.json", CHECKSUMS}:
        raise EvidenceError(f"unexpected evidence members: {sorted(members)}")
    for entry in directory.iterdir():
        if entry.is_symlink() or not entry.is_file():
            raise EvidenceError(f"non-regular evidence member: {entry.name}")
    evidence = directory / "evidence.json"
    if evidence.stat().st_size > MAX_BYTES:
        raise EvidenceError("evidence exceeds one MiB")
    expected = f"{sha256(evidence)}  evidence.json\n"
    if (directory / CHECKSUMS).read_text(encoding="ascii") != expected:
        raise EvidenceError("artifact checksum mismatch")
    try:
        document = json.loads(evidence.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as failure:
        raise EvidenceError("invalid evidence JSON") from failure
    if set(document) != TOP_LEVEL:
        raise EvidenceError("evidence top-level shape is not exact")
    if document["schemaVersion"] != SCHEMA:
        raise EvidenceError("unsupported evidence schema")
    if document["suite"] != SUITE or document["preset"] != PRESET:
        raise EvidenceError("suite or preset identity mismatch")
    if document["profile"] not in {
            "local-scaffold", "experiment", "canonical", "failure-drill"}:
        raise EvidenceError("invalid evidence profile")
    if document["status"] not in {"PASS", "FAIL"}:
        raise EvidenceError("invalid evidence status")
    validate_source(document["sourceCommit"])
    if document["sourceState"] not in {"clean", "dirty"}:
        raise EvidenceError("invalid source state")
    for field in ("case", "configuration", "source", "target", "migration",
                  "rollback", "process", "cleanup", "logs", "result"):
        if not isinstance(document[field], dict):
            raise EvidenceError(f"{field} must be an object")
    if not isinstance(document["lifecycle"], list):
        raise EvidenceError("lifecycle must be an ordered list")
    logs = document["logs"]
    limit = logs.get("limitBytesPerStream")
    if not isinstance(limit, int) or not 0 < limit <= 65_536:
        raise EvidenceError("invalid bounded log limit")
    for field in ("stdoutTail", "stderrTail"):
        value = logs.get(field)
        if not isinstance(value, str) or len(value.encode("utf-8")) > limit:
            raise EvidenceError(f"{field} is not bounded")
    if document["status"] == "PASS":
        if document["cleanup"].get("status") != "PASS" \
                or document["cleanup"].get("leftovers") != []:
            raise EvidenceError("passing evidence requires exact cleanup")
        if document["source"].get("bytesUnchanged") is not True:
            raise EvidenceError("passing evidence requires source-byte preservation")
    return document
