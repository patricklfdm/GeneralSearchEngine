#!/usr/bin/env python3
"""Assemble and append-only register V4.3 fast-reopen evidence sets."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

from scripts.v43.evidence import (
    EvidenceError, canonical_json, sha256, validate_source,
)
from scripts.v43.fast_reopen_performance import validate_fast_reopen_bundle

SET_SCHEMA = "gse-v43-fast-reopen-evidence-set-v1"
REGISTRY_SCHEMA = "gse-v43-fast-reopen-baseline-registry-v1"
BASELINE = "v4.3.0-fast-reopen-cloud"
SUITE = "v4.3-fast-reopen-suite-v1"
PRESET = "v4.3-fast-reopen-v1"


def discover(root: Path) -> list[Path]:
    paths = sorted({path.parent for path in root.rglob("evidence.json")
                    if path.parent.name == "evidence"})
    if not paths:
        raise EvidenceError("no V4.3 members found")
    return paths


def receipt(path: Path, source: str, profile: str, slot: int) -> None:
    try:
        lines = (path.parent / "cloud-member.properties").read_text(
            "utf-8").splitlines()
        values = dict(line.split("=", 1) for line in lines)
    except (OSError, UnicodeError, ValueError) as failure:
        raise EvidenceError("member cleanup receipt is missing or invalid") from failure
    expected = {
        "sourceCommit": source, "profile": profile, "slot": str(slot),
        "runStatus": "PASS", "sourceVmDeleted": "PASS",
        "replacementVmDeleted": "PASS", "primaryDiskDeleted": "PASS",
        "targetDiskDeleted": "PASS", "stagingObjectDeleted": "PASS",
        "cleanup": "PASS",
    }
    if len(values) != len(lines) or values != expected:
        raise EvidenceError("member cleanup receipt differs")


def write_set(path: Path, document: dict[str, Any]) -> None:
    path.mkdir(parents=True, exist_ok=False)
    evidence = path / "evidence.json"; evidence.write_bytes(canonical_json(document))
    (path / "artifact-checksums.sha256").write_text(
        f"{sha256(evidence)}  evidence.json\n", encoding="ascii")


def validate_set(path: Path) -> dict[str, Any]:
    if not path.is_dir() or path.is_symlink() \
            or {member.name for member in path.iterdir()} != {
                "evidence.json", "artifact-checksums.sha256"}:
        raise EvidenceError("set bundle inventory differs")
    evidence = path / "evidence.json"
    if (path / "artifact-checksums.sha256").read_text("ascii") \
            != f"{sha256(evidence)}  evidence.json\n":
        raise EvidenceError("set checksum differs")
    try:
        document = json.loads(evidence.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as failure:
        raise EvidenceError("set is invalid JSON") from failure
    expected_keys = {
        "schemaVersion", "status", "suite", "preset", "profile",
        "sourceCommit", "memberCount", "serialMembers", "comparable",
        "published42Control", "allTenCells", "replacementHost", "cleanup",
        "medianRatioMicros", "maximumRatioMicros", "medianThresholdMicros",
        "memberThresholdMicros", "canonicalEligible", "members",
    }
    if not isinstance(document, dict) or set(document) != expected_keys:
        raise EvidenceError("unsupported V4.3 set inventory")
    profile = document.get("profile"); expected = 3 if profile == "canonical" else 1
    members = document.get("members")
    if not isinstance(members, list) \
            or any(not isinstance(member, dict) for member in members):
        raise EvidenceError("V4.3 set members must be objects")
    if document.get("schemaVersion") != SET_SCHEMA \
            or document.get("status") != "PASS" \
            or document.get("suite") != SUITE or document.get("preset") != PRESET \
            or profile not in {"experiment", "canonical", "failure-drill"} \
            or document.get("memberCount") != expected \
            or len(members) != expected \
            or document.get("serialMembers") is not True \
            or document.get("comparable") is not True \
            or document.get("published42Control") != "PASS" \
            or document.get("allTenCells") != "PASS" \
            or document.get("replacementHost") != "PASS" \
            or document.get("cleanup") != "PASS" \
            or document.get("medianThresholdMicros") != 500_000 \
            or document.get("memberThresholdMicros") != 650_000 \
            or document.get("canonicalEligible") is not (profile == "canonical") \
            or [member.get("slot") for member in members] \
            != list(range(1, expected + 1)):
        raise EvidenceError("unsupported V4.3 set shape")
    source = validate_source(document.get("sourceCommit"))
    member_keys = {"slot", "sourceCommit", "evidenceSha256",
                   "backupContentIdentity", "warmToForcedRatioMicros", "result"}
    for member in members:
        digest = member.get("evidenceSha256", "")
        identity = member.get("backupContentIdentity", "")
        if set(member) != member_keys \
                or member.get("sourceCommit") != source \
                or member.get("result") != "PASS" \
                or len(digest) != 64 \
                or any(char not in "0123456789abcdef" for char in digest) \
                or len(identity) != len("gse-backup-v3-") + 64 \
                or not identity.startswith("gse-backup-v3-") \
                or any(char not in "0123456789abcdef" for char in identity[-64:]):
            raise EvidenceError("V4.3 set member differs")
    ratios = [member.get("warmToForcedRatioMicros") for member in members]
    if any(not isinstance(value, int) or value <= 0 for value in ratios):
        raise EvidenceError("member ratio is invalid")
    median = document.get("medianRatioMicros")
    maximum = document.get("maximumRatioMicros")
    if not isinstance(median, int) or not isinstance(maximum, int) \
            or median != int(statistics.median(ratios)) or maximum != max(ratios):
        raise EvidenceError("aggregate ratios differ")
    if profile == "canonical" and any(value > 650_000 for value in ratios):
        raise EvidenceError("canonical member ratio exceeds 0.65")
    if profile == "canonical" and median > 500_000:
        raise EvidenceError("canonical median ratio exceeds 0.50")
    if len({member["evidenceSha256"] for member in members}) != expected \
            or len({member["backupContentIdentity"]
                    for member in members}) != expected:
        raise EvidenceError("set members are not independent")
    return document


def assemble(arguments: argparse.Namespace) -> int:
    expected = 3 if arguments.profile == "canonical" else 1
    if arguments.expected_members != expected:
        raise EvidenceError("expected member count differs")
    paths = discover(arguments.members_root)
    if len(paths) != expected:
        raise EvidenceError(f"found {len(paths)} members, expected {expected}")
    documents = [validate_fast_reopen_bundle(path) for path in paths]
    sources = {document["sourceCommit"] for document in documents}
    slots = {document["case"].get("slot") for document in documents}
    if len(sources) != 1 or slots != set(range(1, expected + 1)):
        raise EvidenceError("member sources or slots differ")
    comparable = {(document["profile"], document["configuration"].get("javaProfile"),
                   document["configuration"].get("documents"),
                   document["configuration"].get("durationSeconds"),
                   document["configuration"].get("machineType"))
                  for document in documents}
    if len(comparable) != 1 or next(iter(comparable))[0] != arguments.profile:
        raise EvidenceError("members are not comparable")
    source = next(iter(sources)); members = []
    identities: set[str] = set(); digests: set[str] = set()
    for path, document in sorted(zip(paths, documents, strict=True),
                                 key=lambda item: item[1]["case"]["slot"]):
        slot = document["case"]["slot"]
        if document["process"].get("provider") != "gcp" \
                or document["result"].get("replacementHostProven") is not True:
            raise EvidenceError("member is not replacement-host evidence")
        receipt(path, source, arguments.profile, slot)
        evidence_digest = sha256(path / "evidence.json")
        identity = document["canonical"]["backupContentIdentity"]
        digests.add(evidence_digest); identities.add(identity)
        members.append({"slot": slot, "sourceCommit": source,
                        "evidenceSha256": evidence_digest,
                        "backupContentIdentity": identity,
                        "warmToForcedRatioMicros":
                            document["result"]["warmToForcedRatioMicros"],
                        "result": "PASS"})
    if len(digests) != expected or len(identities) != expected:
        raise EvidenceError("independent member identities are not distinct")
    ratios = [member["warmToForcedRatioMicros"] for member in members]
    median = int(statistics.median(ratios))
    if arguments.profile == "canonical" \
            and (median > 500_000 or max(ratios) > 650_000):
        raise EvidenceError("canonical warm-reopen threshold failed")
    document = {
        "schemaVersion": SET_SCHEMA, "status": "PASS", "suite": SUITE,
        "preset": PRESET, "profile": arguments.profile, "sourceCommit": source,
        "memberCount": expected, "serialMembers": True, "comparable": True,
        "published42Control": "PASS", "allTenCells": "PASS",
        "replacementHost": "PASS", "cleanup": "PASS",
        "medianRatioMicros": median, "maximumRatioMicros": max(ratios),
        "medianThresholdMicros": 500_000, "memberThresholdMicros": 650_000,
        "canonicalEligible": arguments.profile == "canonical", "members": members,
    }
    write_set(arguments.output, document); validate_set(arguments.output)
    print(f"v43CloudSet=PASS profile={arguments.profile} members={expected} "
          f"medianRatioMicros={median} eligible={document['canonicalEligible']}")
    return 0


def read_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schemaVersion": REGISTRY_SCHEMA, "baselines": []}
    try:
        document = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as failure:
        raise EvidenceError("invalid V4.3 registry") from failure
    if not isinstance(document, dict) \
            or set(document) != {"schemaVersion", "baselines"} \
            or document.get("schemaVersion") != REGISTRY_SCHEMA \
            or not isinstance(document.get("baselines"), list):
        raise EvidenceError("unsupported V4.3 registry")
    names: set[str] = set()
    for entry in document["baselines"]:
        if not isinstance(entry, dict) or set(entry) != {
                "name", "suite", "preset", "sourceCommit", "setDigest",
                "memberCount", "medianRatioMicros"} \
                or entry.get("name") != BASELINE \
                or entry.get("suite") != SUITE or entry.get("preset") != PRESET \
                or entry.get("memberCount") != 3 \
                or type(entry.get("medianRatioMicros")) is not int \
                or not 0 < entry["medianRatioMicros"] <= 500_000:
            raise EvidenceError("unsupported V4.3 baseline entry")
        validate_source(entry.get("sourceCommit"))
        digest = entry.get("setDigest", "")
        if len(digest) != 64 \
                or any(char not in "0123456789abcdef" for char in digest) \
                or entry["name"] in names:
            raise EvidenceError("invalid or duplicate V4.3 baseline entry")
        names.add(entry["name"])
    return document


def register(arguments: argparse.Namespace) -> int:
    if arguments.name != BASELINE:
        raise EvidenceError(f"baseline must be named {BASELINE}")
    evidence = validate_set(arguments.set_bundle)
    if evidence["canonicalEligible"] is not True:
        raise EvidenceError("only canonical evidence can be registered")
    registry = read_registry(arguments.registry)
    if any(entry.get("name") == BASELINE for entry in registry["baselines"]):
        raise EvidenceError("V4.3 baseline already exists")
    registry["baselines"].append({
        "name": BASELINE, "suite": SUITE, "preset": PRESET,
        "sourceCommit": evidence["sourceCommit"],
        "setDigest": sha256(arguments.set_bundle / "evidence.json"),
        "memberCount": 3, "medianRatioMicros": evidence["medianRatioMicros"]})
    arguments.registry.parent.mkdir(parents=True, exist_ok=True)
    arguments.registry.write_bytes(canonical_json(registry))
    print(f"v43CloudBaselineRegistration=PASS name={BASELINE} "
          f"source={evidence['sourceCommit']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(); commands = parser.add_subparsers(dest="command", required=True)
    assembly = commands.add_parser("assemble")
    assembly.add_argument("--members-root", type=Path, required=True)
    assembly.add_argument("--profile", choices=("experiment", "canonical", "failure-drill"), required=True)
    assembly.add_argument("--expected-members", type=int, required=True)
    assembly.add_argument("--output", type=Path, required=True)
    validation = commands.add_parser("validate"); validation.add_argument("bundle", type=Path)
    registration = commands.add_parser("register")
    registration.add_argument("--registry", type=Path, required=True)
    registration.add_argument("--set-bundle", type=Path, required=True)
    registration.add_argument("--name", required=True)
    listing = commands.add_parser("registry-list"); listing.add_argument("registry", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "assemble": return assemble(arguments)
    if arguments.command == "validate":
        value = validate_set(arguments.bundle)
        print(f"v43CloudSetValidation=PASS profile={value['profile']}"); return 0
    if arguments.command == "register": return register(arguments)
    for baseline in read_registry(arguments.registry)["baselines"]:
        print(f"{baseline['name']}\t{baseline['setDigest']}\t{baseline['sourceCommit']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError) as failure:
        print(f"v43CloudSet=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
