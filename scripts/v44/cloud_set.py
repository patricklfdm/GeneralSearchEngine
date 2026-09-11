#!/usr/bin/env python3
"""Assemble and validate V4.4 final-durable evidence sets."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

from scripts.v44.cloud_evidence import validate_evidence
from scripts.v44.evidence import EvidenceError, canonical_json, sha256, validate_source

SCHEMA = "gse-v44-final-durable-evidence-set-v1"
SUITE = "v4.4-final-durable-suite-v1"
PRESET = "v4.4-final-durable-v1"


def _discover(root: Path) -> list[Path]:
    paths = sorted({path.parent for path in root.rglob("evidence.json")
                    if path.parent.name == "evidence"})
    if not paths:
        raise EvidenceError("no V4.4 cloud members found")
    return paths


def _receipt(path: Path, source: str, profile: str, slot: int) -> None:
    try:
        lines = (path.parent / "cloud-member.properties").read_text(
            encoding="ascii").splitlines()
        values = dict(line.split("=", 1) for line in lines)
    except (OSError, UnicodeError, ValueError) as failure:
        raise EvidenceError("V4.4 member cleanup receipt is invalid") from failure
    expected = {
        "sourceCommit": source, "profile": profile, "slot": str(slot),
        "runStatus": "PASS", "sourceVmDeleted": "PASS",
        "replacementVmDeleted": "PASS", "dataDiskDeleted": "PASS",
        "targetDiskDeleted": "PASS", "stagingObjectDeleted": "PASS",
        "cleanup": "PASS",
    }
    if len(values) != len(lines) or values != expected:
        raise EvidenceError("V4.4 member cleanup receipt differs")


def _write(path: Path, document: dict[str, Any]) -> None:
    path.mkdir(parents=True, exist_ok=False)
    evidence = path / "evidence.json"
    evidence.write_bytes(canonical_json(document))
    (path / "artifact-checksums.sha256").write_text(
        f"{sha256(evidence)}  evidence.json\n", encoding="ascii")


def validate_set(path: Path) -> dict[str, Any]:
    if not path.is_dir() or path.is_symlink() \
            or {member.name for member in path.iterdir()} != {
                "evidence.json", "artifact-checksums.sha256"}:
        raise EvidenceError("V4.4 set inventory differs")
    evidence = path / "evidence.json"
    if (path / "artifact-checksums.sha256").read_text(encoding="ascii") \
            != f"{sha256(evidence)}  evidence.json\n":
        raise EvidenceError("V4.4 set checksum differs")
    try:
        document = json.loads(evidence.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as failure:
        raise EvidenceError("V4.4 set is invalid JSON") from failure
    expected_keys = {
        "schemaVersion", "status", "suite", "preset", "profile",
        "sourceCommit", "memberCount", "serialMembers", "comparable",
        "allTenFamilies", "published43Control", "replacementHost", "cleanup",
        "medianWriteRatioMicros", "maximumWriteRatioMicros",
        "medianReopenRatioMicros", "maximumReopenRatioMicros",
        "medianThresholdMicros", "memberThresholdMicros",
        "canonicalEligible", "members",
    }
    if not isinstance(document, dict) or set(document) != expected_keys:
        raise EvidenceError("unsupported V4.4 set inventory")
    profile = document.get("profile")
    expected_count = 3 if profile == "canonical" else 1
    members = document.get("members")
    if document.get("schemaVersion") != SCHEMA \
            or document.get("status") != "PASS" \
            or document.get("suite") != SUITE \
            or document.get("preset") != PRESET \
            or profile not in {"experiment", "canonical", "failure-drill"} \
            or document.get("memberCount") != expected_count \
            or not isinstance(members, list) or len(members) != expected_count \
            or document.get("serialMembers") is not True \
            or document.get("comparable") is not True \
            or document.get("allTenFamilies") != "PASS" \
            or document.get("published43Control") != "PASS" \
            or document.get("replacementHost") != "PASS" \
            or document.get("cleanup") != "PASS" \
            or document.get("medianThresholdMicros") != 1_200_000 \
            or document.get("memberThresholdMicros") != 1_350_000 \
            or document.get("canonicalEligible") is not (profile == "canonical"):
        raise EvidenceError("unsupported V4.4 set shape")
    source = validate_source(document.get("sourceCommit"))
    member_keys = {"slot", "sourceCommit", "evidenceSha256",
                   "backupContentIdentity", "writeRatioMicros",
                   "reopenRatioMicros", "result"}
    for member in members:
        if not isinstance(member, dict) or set(member) != member_keys \
                or member.get("sourceCommit") != source \
                or member.get("result") != "PASS" \
                or type(member.get("slot")) is not int:
            raise EvidenceError("V4.4 set member differs")
        for key in ("evidenceSha256",):
            digest = member.get(key, "")
            if len(digest) != 64 \
                    or any(character not in "0123456789abcdef" for character in digest):
                raise EvidenceError("V4.4 member digest differs")
        identity = member.get("backupContentIdentity", "")
        if not identity.startswith("gse-backup-v3-") or len(identity) != 78:
            raise EvidenceError("V4.4 member backup identity differs")
        for key in ("writeRatioMicros", "reopenRatioMicros"):
            if type(member.get(key)) is not int or member[key] <= 0:
                raise EvidenceError("V4.4 member ratio differs")
    if [member["slot"] for member in members] != list(range(1, expected_count + 1)):
        raise EvidenceError("V4.4 set slots differ")
    write_ratios = [member["writeRatioMicros"] for member in members]
    reopen_ratios = [member["reopenRatioMicros"] for member in members]
    aggregates = {
        "medianWriteRatioMicros": int(statistics.median(write_ratios)),
        "maximumWriteRatioMicros": max(write_ratios),
        "medianReopenRatioMicros": int(statistics.median(reopen_ratios)),
        "maximumReopenRatioMicros": max(reopen_ratios),
    }
    if any(document.get(key) != value for key, value in aggregates.items()):
        raise EvidenceError("V4.4 aggregate ratios differ")
    if profile == "canonical" and (
            max(aggregates["medianWriteRatioMicros"],
                aggregates["medianReopenRatioMicros"]) > 1_200_000
            or max(aggregates["maximumWriteRatioMicros"],
                   aggregates["maximumReopenRatioMicros"]) > 1_350_000):
        raise EvidenceError("V4.4 canonical paired threshold failed")
    if len({member["evidenceSha256"] for member in members}) != expected_count \
            or len({member["backupContentIdentity"]
                    for member in members}) != expected_count:
        raise EvidenceError("V4.4 members are not independent")
    return document


def assemble(arguments: argparse.Namespace) -> int:
    expected = 3 if arguments.profile == "canonical" else 1
    if arguments.expected_members != expected:
        raise EvidenceError("V4.4 expected member count differs")
    paths = _discover(arguments.members_root)
    if len(paths) != expected:
        raise EvidenceError(f"found {len(paths)} V4.4 members, expected {expected}")
    documents = [validate_evidence(path) for path in paths]
    sources = {document["sourceCommit"] for document in documents}
    slots = {document["case"]["slot"] for document in documents}
    comparable = {(document["profile"],
                   document["configuration"]["durationSeconds"],
                   document["configuration"]["machineType"])
                  for document in documents}
    if len(sources) != 1 or slots != set(range(1, expected + 1)) \
            or comparable != {(arguments.profile, 3_600, "c3d-standard-30")}:
        raise EvidenceError("V4.4 members are not comparable")
    source = next(iter(sources))
    members = []
    for path, document in sorted(zip(paths, documents, strict=True),
                                 key=lambda item: item[1]["case"]["slot"]):
        slot = document["case"]["slot"]
        _receipt(path, source, arguments.profile, slot)
        members.append({
            "slot": slot, "sourceCommit": source,
            "evidenceSha256": sha256(path / "evidence.json"),
            "backupContentIdentity":
                document["authority"]["backupContentIdentity"],
            "writeRatioMicros": document["measurements"]["writeRatioMicros"],
            "reopenRatioMicros": document["measurements"]["reopenRatioMicros"],
            "result": "PASS",
        })
    write_ratios = [member["writeRatioMicros"] for member in members]
    reopen_ratios = [member["reopenRatioMicros"] for member in members]
    document = {
        "schemaVersion": SCHEMA, "status": "PASS", "suite": SUITE,
        "preset": PRESET, "profile": arguments.profile,
        "sourceCommit": source, "memberCount": expected,
        "serialMembers": True, "comparable": True,
        "allTenFamilies": "PASS", "published43Control": "PASS",
        "replacementHost": "PASS", "cleanup": "PASS",
        "medianWriteRatioMicros": int(statistics.median(write_ratios)),
        "maximumWriteRatioMicros": max(write_ratios),
        "medianReopenRatioMicros": int(statistics.median(reopen_ratios)),
        "maximumReopenRatioMicros": max(reopen_ratios),
        "medianThresholdMicros": 1_200_000,
        "memberThresholdMicros": 1_350_000,
        "canonicalEligible": arguments.profile == "canonical",
        "members": members,
    }
    _write(arguments.output, document)
    validate_set(arguments.output)
    print(f"v44CloudSet=PASS profile={arguments.profile} members={expected} "
          f"eligible={document['canonicalEligible']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    assembly = commands.add_parser("assemble")
    assembly.add_argument("--members-root", type=Path, required=True)
    assembly.add_argument("--profile", choices=("experiment", "canonical", "failure-drill"), required=True)
    assembly.add_argument("--expected-members", type=int, required=True)
    assembly.add_argument("--output", type=Path, required=True)
    validation = commands.add_parser("validate")
    validation.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "assemble":
        return assemble(arguments)
    value = validate_set(arguments.bundle)
    print(f"v44CloudSetValidation=PASS profile={value['profile']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError) as failure:
        print(f"v44CloudSet=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
