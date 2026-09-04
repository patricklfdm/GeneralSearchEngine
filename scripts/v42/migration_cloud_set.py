#!/usr/bin/env python3
"""Assemble and append-only register V4.2 migration evidence sets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.v42.evidence import EvidenceError, canonical_json, sha256
from scripts.v42.migration_performance import validate_migration_bundle

SET_SCHEMA = "gse-v42-migration-evidence-set-v1"
REGISTRY_SCHEMA = "gse-v42-migration-baseline-registry-v1"
BASELINE = "v4.2.0-migration-cloud"
SUITE = "v4.2-storage-evolution-suite-v1"
PRESET = "v4.2-storage-evolution-v1"


def discover(root: Path) -> list[Path]:
    paths = sorted({path.parent for path in root.rglob("evidence.json")
                    if path.parent.name == "evidence"})
    if not paths:
        raise EvidenceError("no V4.2 migration members found")
    return paths


def receipt(path: Path, source: str, profile: str, slot: int) -> None:
    receipt_path = path.parent / "cloud-member.properties"
    try:
        lines = receipt_path.read_text("utf-8").splitlines()
    except (OSError, UnicodeError) as failure:
        raise EvidenceError("member cleanup receipt is missing") from failure
    values: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            raise EvidenceError("member cleanup receipt is invalid")
        key, value = line.split("=", 1)
        if not key or not value or key in values:
            raise EvidenceError("member cleanup receipt is invalid")
        values[key] = value
    expected = {
        "sourceCommit": source, "profile": profile, "slot": str(slot),
        "runStatus": "PASS", "sourceVmDeleted": "PASS",
        "replacementTargetVmDeleted": "PASS", "rollbackVmDeleted": "PASS",
        "sourceDiskDeleted": "PASS", "targetDiskDeleted": "PASS",
        "stagingObjectDeleted": "PASS", "cleanup": "PASS",
    }
    if values != expected:
        raise EvidenceError("member cleanup receipt differs")


def write_set(path: Path, document: dict[str, Any]) -> None:
    path.mkdir(parents=True, exist_ok=False)
    evidence = path / "evidence.json"
    evidence.write_bytes(canonical_json(document))
    (path / "artifact-checksums.sha256").write_text(
        f"{sha256(evidence)}  evidence.json\n", encoding="ascii")


def validate_set(path: Path) -> dict[str, Any]:
    if not path.is_dir() or path.is_symlink() or {
            member.name for member in path.iterdir()} != {
            "evidence.json", "artifact-checksums.sha256"}:
        raise EvidenceError("set bundle inventory differs")
    evidence = path / "evidence.json"
    if (path / "artifact-checksums.sha256").read_text("ascii") \
            != f"{sha256(evidence)}  evidence.json\n":
        raise EvidenceError("set checksum differs")
    try:
        document = json.loads(evidence.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as failure:
        raise EvidenceError("set evidence is invalid JSON") from failure
    if document.get("schemaVersion") != SET_SCHEMA \
            or document.get("status") != "PASS" \
            or document.get("suite") != SUITE \
            or document.get("preset") != PRESET:
        raise EvidenceError("unsupported V4.2 migration set")
    profile = document.get("profile")
    expected = 3 if profile == "canonical" else 1
    if profile not in {"experiment", "canonical", "failure-drill"} \
            or document.get("memberCount") != expected \
            or len(document.get("members", [])) != expected \
            or document.get("canonicalEligible") is not (profile == "canonical") \
            or [member.get("slot") for member in document["members"]] \
            != list(range(1, expected + 1)):
        raise EvidenceError("migration set shape differs")
    return document


def assemble(arguments: argparse.Namespace) -> int:
    expected = 3 if arguments.profile == "canonical" else 1
    if arguments.expected_members != expected:
        raise EvidenceError("expected member count differs from profile")
    paths = discover(arguments.members_root)
    if len(paths) != expected:
        raise EvidenceError(f"found {len(paths)} members, expected {expected}")
    documents = [validate_migration_bundle(path) for path in paths]
    sources = {document["sourceCommit"] for document in documents}
    slots = {document["case"].get("slot") for document in documents}
    if len(sources) != 1 or slots != set(range(1, expected + 1)):
        raise EvidenceError("member sources or slots differ")
    comparable = {(document["profile"],
                   document["configuration"].get("javaProfile"),
                   document["configuration"].get("documents"),
                   document["configuration"].get("durationSeconds"),
                   document["configuration"].get("machineType"),
                   document["configuration"].get("sourceDiskGiB"),
                   document["configuration"].get("targetDiskGiB"))
                  for document in documents}
    if len(comparable) != 1 or next(iter(comparable))[0] != arguments.profile:
        raise EvidenceError("migration members are not comparable")
    source = next(iter(sources))
    members = []
    plan_digests: set[str] = set()
    histories: set[str] = set()
    for path, document in sorted(zip(paths, documents, strict=True),
                                 key=lambda item: item[1]["case"]["slot"]):
        slot = document["case"]["slot"]
        if document["process"].get("provider") != "gcp" \
                or document["result"].get("replacementHostProven") is not True:
            raise EvidenceError("member is not real replacement-host evidence")
        receipt(path, source, arguments.profile, slot)
        plan_digest = document["migration"]["planDigest"]
        target_history = document["migration"]["targetHistory"]
        plan_digests.add(plan_digest)
        histories.add(target_history)
        members.append({"slot": slot, "sourceCommit": source,
                        "evidenceSha256": sha256(path / "evidence.json"),
                        "planDigest": plan_digest,
                        "targetHistory": target_history, "result": "PASS"})
    if len(plan_digests) != expected or len(histories) != expected:
        raise EvidenceError("independent migration identities are not distinct")
    document = {
        "schemaVersion": SET_SCHEMA, "status": "PASS", "suite": SUITE,
        "preset": PRESET, "profile": arguments.profile,
        "sourceCommit": source, "memberCount": expected,
        "serialMembers": True, "comparable": True,
        "sourcePreservation": "PASS", "replacementHost": "PASS",
        "published41Rollback": "PASS", "cleanup": "PASS",
        "canonicalEligible": arguments.profile == "canonical",
        "members": members,
    }
    write_set(arguments.output, document)
    validate_set(arguments.output)
    print(f"v42CloudSet=PASS profile={arguments.profile} members={expected} "
          f"eligible={document['canonicalEligible']}")
    return 0


def read_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schemaVersion": REGISTRY_SCHEMA, "baselines": []}
    try:
        document = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as failure:
        raise EvidenceError("invalid V4.2 migration registry") from failure
    if document.get("schemaVersion") != REGISTRY_SCHEMA \
            or not isinstance(document.get("baselines"), list):
        raise EvidenceError("unsupported V4.2 migration registry")
    return document


def register(arguments: argparse.Namespace) -> int:
    if arguments.name != BASELINE:
        raise EvidenceError(f"baseline must be named {BASELINE}")
    evidence = validate_set(arguments.set_bundle)
    if evidence["canonicalEligible"] is not True:
        raise EvidenceError("only canonical evidence can be registered")
    registry = read_registry(arguments.registry)
    if any(entry.get("name") == BASELINE for entry in registry["baselines"]):
        raise EvidenceError("V4.2 migration baseline is already registered")
    registry["baselines"].append({
        "name": BASELINE, "suite": SUITE, "preset": PRESET,
        "sourceCommit": evidence["sourceCommit"],
        "setDigest": sha256(arguments.set_bundle / "evidence.json"),
        "memberCount": 3})
    arguments.registry.parent.mkdir(parents=True, exist_ok=True)
    arguments.registry.write_bytes(canonical_json(registry))
    print(f"v42CloudBaselineRegistration=PASS name={BASELINE} "
          f"source={evidence['sourceCommit']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    assembly = commands.add_parser("assemble")
    assembly.add_argument("--members-root", type=Path, required=True)
    assembly.add_argument("--profile", choices=("experiment", "canonical",
                                                 "failure-drill"), required=True)
    assembly.add_argument("--expected-members", type=int, required=True)
    assembly.add_argument("--output", type=Path, required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("bundle", type=Path)
    registration = commands.add_parser("register")
    registration.add_argument("--registry", type=Path, required=True)
    registration.add_argument("--set-bundle", type=Path, required=True)
    registration.add_argument("--name", required=True)
    listing = commands.add_parser("registry-list")
    listing.add_argument("registry", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "assemble":
        return assemble(arguments)
    if arguments.command == "validate":
        value = validate_set(arguments.bundle)
        print(f"v42CloudSetValidation=PASS profile={value['profile']}")
        return 0
    if arguments.command == "register":
        return register(arguments)
    for baseline in read_registry(arguments.registry)["baselines"]:
        print(f"{baseline['name']}\t{baseline['setDigest']}\t"
              f"{baseline['sourceCommit']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError) as failure:
        print(f"v42CloudSet=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
