#!/usr/bin/env python3
"""Assemble and register independent V4 durable cloud evidence sets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.v4.durable_cloud_lane import PRESET, SUITE
from scripts.v4.durable_performance import validate_performance_bundle
from scripts.v4.evidence import (
    EvidenceError,
    canonical_json,
    sha256,
    validate_bundle,
    write_bundle,
)

REGISTRY_SCHEMA = "gse-v4-durable-baseline-registry-v1"
SET_KIND = "v4-durable-cloud-set"
BASELINE_NAME = "v4.0.0-durable-cloud"


def discover_members(root: Path) -> list[Path]:
    members = sorted({path.parent for path in root.rglob("evidence.json")})
    if not members:
        raise EvidenceError("no durable performance evidence members found")
    return members


def validate_cleanup_receipt(member: Path, source: str, profile: str) -> None:
    receipt = member.parent / "cloud-member.properties"
    try:
        lines = receipt.read_text("utf-8").splitlines()
    except (OSError, UnicodeError) as failure:
        raise EvidenceError("cloud member cleanup receipt is missing") from failure
    properties: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            raise EvidenceError("cloud member cleanup receipt is invalid")
        key, value = line.split("=", 1)
        if not key or not value or key in properties:
            raise EvidenceError("cloud member cleanup receipt is invalid")
        properties[key] = value
    if properties.get("sourceCommit") != source \
            or properties.get("profile") != profile \
            or properties.get("runStatus") != "PASS" \
            or properties.get("cleanup") != "PASS":
        raise EvidenceError("cloud member cleanup receipt differs")


def assemble(arguments: argparse.Namespace) -> int:
    expected = 3 if arguments.profile == "canonical" else 1
    if arguments.expected_members != expected:
        raise EvidenceError(
            f"{arguments.profile} sets require exactly {expected} member(s)")
    member_paths = discover_members(arguments.members_root)
    if len(member_paths) != expected:
        raise EvidenceError(
            f"found {len(member_paths)} members, expected {expected}")
    documents = [validate_performance_bundle(path) for path in member_paths]
    sources = {document["sourceCommit"] for document in documents}
    if len(sources) != 1:
        raise EvidenceError("cloud set members use different sources")
    source = next(iter(sources))
    comparable = {
        (
            document["environment"].get("cloudProvider"),
            document["environment"].get("cloudMachineType"),
            document["environment"].get("cloudImage"),
            document["environment"].get("cloudZone"),
            document["environment"].get("filesystem"),
            document["configuration"].get("codecIdentity"),
            document["configuration"].get("schemaIdentity"),
            document["configuration"].get("storageIdentity"),
            document["configuration"].get("durationSeconds"),
        )
        for document in documents
    }
    if len(comparable) != 1:
        raise EvidenceError("cloud set members are not comparable")
    for document in documents:
        if document["environment"].get("evidenceProfile") != arguments.profile:
            raise EvidenceError("member evidence profile differs")
        if document["environment"].get("profile") != "production":
            raise EvidenceError("cloud member did not use the production workload")
        if document["environment"].get("cloudProvider") != "gcp" \
                or document["result"].get("paidExecution") is not True:
            raise EvidenceError("cloud member is not paid GCP evidence")
    for path, document in zip(member_paths, documents, strict=True):
        validate_cleanup_receipt(path, document["sourceCommit"], arguments.profile)
    members = [{
        "slot": index,
        "sourceCommit": document["sourceCommit"],
        "evidenceSha256": sha256(path / "evidence.json"),
        "device": document["environment"].get("device"),
        "result": "PASS",
    } for index, (path, document) in enumerate(
        zip(member_paths, documents, strict=True), start=1)]
    eligible = arguments.profile == "canonical" and len(members) == 3
    output = arguments.output
    evidence = {
        "kind": SET_KIND,
        "status": "PASS",
        "sourceCommit": source,
        "environment": {
            "sourceState": "clean",
            "provider": "gcp",
            "suite": SUITE,
            "preset": PRESET,
            "profile": arguments.profile,
            "members": len(members),
        },
        "configuration": {
            "comparisonIdentity": list(next(iter(comparable))),
            "expectedMembers": expected,
        },
        "case": {
            "caseId": f"phase6-cloud-set-{arguments.profile}",
            "seed": 40,
            "barrierId": "NONE_PERFORMANCE_ONLY",
            "acknowledgement": "ALL_MEMBERS_VALIDATED",
        },
        "submittedHistory": [],
        "futureOutcomes": [],
        "process": {
            "termination": "NORMAL",
            "exitCode": 0,
            "gracefulCloseRan": True,
            "members": members,
        },
        "inspection": {
            "memberEvidence": members,
            "comparable": True,
        },
        "recovery": {
            "status": "PASS",
            "sourcesMeasured": [
                "WAL_ONLY", "CHECKPOINT_ONLY", "CHECKPOINT_AND_WAL"
            ],
        },
        "logs": {
            "stdoutTail": "",
            "stderrTail": "",
            "limitBytesPerStream": 4096,
        },
        "cleanup": {
            "status": "PASS",
            "memberResourcesDeleted": True,
            "leftovers": [],
        },
        "lifecycle": [
            "members-discovered",
            "checksums-validated",
            "identities-compared",
            "eligibility-classified",
        ],
        "result": {
            "canonicalEligible": eligible,
            "memberCount": len(members),
            "baselineName": BASELINE_NAME if eligible else None,
            "paidExecution": True,
        },
    }
    write_bundle(output, evidence)
    validate_set(output)
    print(
        "v40CloudSet=PASS "
        f"profile={arguments.profile} members={len(members)} eligible={eligible}"
    )
    return 0


def validate_set(path: Path) -> dict[str, Any]:
    document = validate_bundle(path)
    if document.get("kind") != SET_KIND or document.get("status") != "PASS":
        raise EvidenceError("not a passing V4 durable cloud set")
    profile = document["environment"].get("profile")
    count = document["result"].get("memberCount")
    eligible = document["result"].get("canonicalEligible")
    if profile == "canonical":
        if count != 3 or eligible is not True:
            raise EvidenceError("canonical set is not three-member eligible evidence")
    elif profile == "experiment":
        if count != 1 or eligible is not False:
            raise EvidenceError("experiment set eligibility differs")
    else:
        raise EvidenceError("unsupported cloud set profile")
    return document


def read_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schemaVersion": REGISTRY_SCHEMA, "baselines": []}
    try:
        registry = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as failure:
        raise EvidenceError("invalid V4 durable baseline registry") from failure
    if registry.get("schemaVersion") != REGISTRY_SCHEMA \
            or not isinstance(registry.get("baselines"), list):
        raise EvidenceError("unsupported V4 durable baseline registry")
    return registry


def register(arguments: argparse.Namespace) -> int:
    if arguments.name != BASELINE_NAME:
        raise EvidenceError(f"durable baseline must be named {BASELINE_NAME}")
    evidence = validate_set(arguments.set_bundle)
    if evidence["result"].get("canonicalEligible") is not True:
        raise EvidenceError("only canonical-eligible sets may be registered")
    registry = read_registry(arguments.registry)
    if any(entry.get("name") == arguments.name
           for entry in registry["baselines"]):
        raise EvidenceError("durable baseline name is already registered")
    registry["baselines"].append({
        "name": arguments.name,
        "suite": SUITE,
        "preset": PRESET,
        "sourceCommit": evidence["sourceCommit"],
        "setDigest": sha256(arguments.set_bundle / "evidence.json"),
        "memberCount": 3,
    })
    arguments.registry.parent.mkdir(parents=True, exist_ok=True)
    arguments.registry.write_bytes(canonical_json(registry))
    print(
        f"v40CloudBaselineRegistration=PASS name={arguments.name} "
        f"source={evidence['sourceCommit']}"
    )
    return 0


def list_registry(path: Path) -> int:
    registry = read_registry(path)
    for baseline in registry["baselines"]:
        print(
            f"{baseline['name']}\t{baseline['setDigest']}\t"
            f"{baseline['sourceCommit']}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    assemble_parser = subparsers.add_parser("assemble")
    assemble_parser.add_argument("--members-root", type=Path, required=True)
    assemble_parser.add_argument(
        "--profile", choices=("experiment", "canonical"), required=True)
    assemble_parser.add_argument("--expected-members", type=int, required=True)
    assemble_parser.add_argument("--output", type=Path, required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("bundle", type=Path)
    register_parser = subparsers.add_parser("register")
    register_parser.add_argument("--registry", type=Path, required=True)
    register_parser.add_argument("--set-bundle", type=Path, required=True)
    register_parser.add_argument("--name", required=True)
    list_parser = subparsers.add_parser("registry-list")
    list_parser.add_argument("registry", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "assemble":
        return assemble(arguments)
    if arguments.command == "validate":
        validate_set(arguments.bundle)
        print(f"v40CloudSetValidation=PASS bundle={arguments.bundle}")
        return 0
    if arguments.command == "register":
        return register(arguments)
    return list_registry(arguments.registry)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as failure:
        print(f"v40CloudSet=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
