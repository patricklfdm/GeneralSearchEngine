#!/usr/bin/env python3
"""Independent validator for the V4.2 Phase 1 logical format fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA = "gse-v42-logical-format-fixture-v1"
CHECKSUMS = "fixture-checksums.sha256"
JSON_MEMBERS = (
    "backup-v1.1.json",
    "migration-plan.json",
    "source-v1.0.json",
    "target-v1.1.json",
)
INVENTORY = {*JSON_MEMBERS, CHECKSUMS, "README.md"}
SHA256 = re.compile(r"[0-9a-f]{64}")
REQUIRED_CAPABILITIES = [
    "canonical-documents-v1",
    "checkpoint-authority-v1",
    "crc32c-wal-v1",
    "logical-index-config-v1",
    "sha256-profile-binding-v1",
]


class FixtureError(ValueError):
    """A fixture is missing, mutated, malformed, or logically inconsistent."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_fixture(directory: Path) -> dict[str, dict[str, Any]]:
    if not directory.is_dir() or directory.is_symlink():
        raise FixtureError("fixture path must be a non-symbolic directory")
    members = {entry.name for entry in directory.iterdir()}
    if members != INVENTORY:
        raise FixtureError(f"unexpected fixture inventory: {sorted(members)}")
    for entry in directory.iterdir():
        if entry.is_symlink() or not entry.is_file():
            raise FixtureError(f"non-regular fixture member: {entry.name}")
    expected = "".join(
        f"{sha256(directory / name)}  {name}\n" for name in JSON_MEMBERS)
    actual = (directory / CHECKSUMS).read_text(encoding="ascii")
    if actual != expected:
        raise FixtureError("fixture checksum inventory mismatch")
    documents: dict[str, dict[str, Any]] = {}
    for name in JSON_MEMBERS:
        path = directory / name
        if path.stat().st_size > 64 * 1024:
            raise FixtureError(f"fixture is unbounded: {name}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError) as failure:
            raise FixtureError(f"invalid fixture JSON: {name}") from failure
        if not isinstance(value, dict) or value.get("schemaVersion") != SCHEMA:
            raise FixtureError(f"invalid fixture schema: {name}")
        documents[name] = value
    validate_documents(documents)
    return documents


def validate_documents(documents: dict[str, dict[str, Any]]) -> None:
    source = documents["source-v1.0.json"]
    target = documents["target-v1.1.json"]
    backup = documents["backup-v1.1.json"]
    plan = documents["migration-plan.json"]
    require_format(source.get("format"), "gse-durable", 1, 0, "source")
    require_format(target.get("format"), "gse-durable", 1, 1, "target")
    require_format(backup.get("format"), "gse-backup", 1, 1, "backup")
    require_format(backup.get("sourceFormat"), "gse-durable", 1, 1,
                   "backup source")
    require_format(plan.get("sourceFormat"), "gse-durable", 1, 0,
                   "plan source")
    require_format(plan.get("targetFormat"), "gse-durable", 1, 1,
                   "plan target")
    if source.get("physicalEncodingStatus") != "PUBLISHED_V41_BYTES_REFERENCED":
        raise FixtureError("source must retain the published V4.1 physical boundary")
    for name, value in (("target", target), ("backup", backup), ("plan", plan)):
        if value.get("physicalEncodingStatus") != "PHASE2_PENDING":
            raise FixtureError(f"{name} prematurely claims frozen physical bytes")
    profile = target.get("formatProfile")
    if not isinstance(profile, dict) \
            or profile.get("required") != REQUIRED_CAPABILITIES \
            or profile.get("optional") != []:
        raise FixtureError("target format profile is not canonical")
    source_records = require_records(source, "source")
    target_records = require_records(target, "target")
    if source_records != target_records:
        raise FixtureError("identity migration projection changed records")
    if source.get("sequence") != target.get("sequence") \
            or source.get("nextDocId") != target.get("nextDocId"):
        raise FixtureError("target sequence or nextDocId changed")
    if source.get("history") == target.get("history"):
        raise FixtureError("target history must differ from source")
    if plan.get("sourceHistory") != source.get("history") \
            or plan.get("targetHistory") != target.get("history") \
            or plan.get("sequence") != source.get("sequence") \
            or plan.get("nextDocId") != source.get("nextDocId") \
            or plan.get("documentCount") != len(source_records) \
            or plan.get("sourceUnchanged") is not True:
        raise FixtureError("plan is not bound to the logical source and target")
    transform = plan.get("transform")
    if transform != {"identifier": "identity-format-v1", "version": 1}:
        raise FixtureError("transform descriptor mismatch")
    if plan.get("planIdentityDomain") != "gse-migration-plan-v1" \
            or plan.get("projectionIdentityDomain") != \
            "gse-migration-projection-v1":
        raise FixtureError("migration identity domain mismatch")
    if backup.get("memberInventory") != [
            "gse-backup-checkpoint", "gse-backup-manifest",
            "gse-backup-metadata"]:
        raise FixtureError("backup member inventory mismatch")
    if backup.get("sourceHistory") != target.get("history") \
            or backup.get("sequence") != target.get("sequence") \
            or backup.get("contentIdentityDomain") != "gse-backup-content-v2" \
            or backup.get("identityPrefix") != "gse-backup-v2-":
        raise FixtureError("backup is not bound to the target model")


def require_format(value: object, family: str, major: int, minor: int,
                   label: str) -> None:
    if value != {"family": family, "major": major, "minor": minor}:
        raise FixtureError(f"{label} format mismatch")


def require_records(document: dict[str, Any], label: str) -> list[dict[str, Any]]:
    records = document.get("records")
    if not isinstance(records, list):
        raise FixtureError(f"{label} records must be a list")
    previous = -1
    keys: set[str] = set()
    for record in records:
        if not isinstance(record, dict) \
                or set(record) != {"slot", "key", "document"}:
            raise FixtureError(f"{label} record shape mismatch")
        slot = record["slot"]
        key = record["key"]
        if not isinstance(slot, int) or slot <= previous:
            raise FixtureError(f"{label} slots are not canonical")
        if not isinstance(key, str) or key in keys:
            raise FixtureError(f"{label} keys are invalid or duplicate")
        if not isinstance(record["document"], str):
            raise FixtureError(f"{label} document must be a string")
        previous = slot
        keys.add(key)
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    arguments = parser.parse_args()
    documents = load_fixture(arguments.directory)
    source = documents["source-v1.0.json"]
    target = documents["target-v1.1.json"]
    print("v42StorageFixture=PASS "
          f"source={source['format']['major']}.{source['format']['minor']} "
          f"target={target['format']['major']}.{target['format']['minor']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FixtureError, OSError) as failure:
        print(f"v42StorageFixture=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
