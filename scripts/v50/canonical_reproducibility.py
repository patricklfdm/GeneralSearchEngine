#!/usr/bin/env python3
"""Record and validate V5.0 canonical two-workspace artifact identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from scripts.v50.evidence import canonical_bytes as canonical_json
from scripts.v50.toolchain_manifest import validate as validate_toolchain

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "gse-v50-canonical-reproducibility-v1"
CHECKSUMS = "artifact-checksums.sha256"
VERSION = "5.0.0"
JARS = {
    f"general-search-engine-{VERSION}.jar",
    f"general-search-engine-{VERSION}-sources.jar",
    f"general-search-engine-{VERSION}-javadoc.jar",
    f"general-search-engine-processor-{VERSION}.jar",
    f"general-search-engine-processor-{VERSION}-sources.jar",
    f"general-search-engine-processor-{VERSION}-javadoc.jar",
    f"general-search-engine-replication-{VERSION}.jar",
    f"general-search-engine-replication-{VERSION}-sources.jar",
    f"general-search-engine-replication-{VERSION}-javadoc.jar",
}
POMS = {"general-search-engine.pom", "general-search-engine-processor.pom",
        "general-search-engine-replication.pom"}
ARTIFACTS = JARS | POMS


class ReproducibilityError(ValueError):
    """Canonical build evidence is absent, malformed, or not reproducible."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(directory: Path) -> dict[str, str]:
    if not directory.is_dir() or directory.is_symlink():
        raise ReproducibilityError("canonical capture is not a regular directory")
    members = {path.name for path in directory.iterdir()
               if path.is_file() and not path.is_symlink()}
    if members != ARTIFACTS or len(list(directory.iterdir())) != len(ARTIFACTS):
        raise ReproducibilityError("canonical artifact inventory differs")
    return {name: sha256(directory / name) for name in sorted(ARTIFACTS)}


def validate_source(source: object) -> dict:
    if not isinstance(source, dict) or set(source) != {
            "kind", "commit", "archiveSha256"} or source["kind"] not in {
                "git-commit", "working-tree"} or re.fullmatch(
                    r"[0-9a-f]{40}", str(source["commit"])) is None or re.fullmatch(
                    r"[0-9a-f]{64}", str(source["archiveSha256"])) is None:
        raise ReproducibilityError("source provenance differs")
    return source


def write_record(first: Path, second: Path, output: Path, source: dict) -> dict[str, Any]:
    source = validate_source(source)
    toolchain = validate_toolchain(ROOT / "docs/v5x/v5.0/release-toolchain.json")
    left = inventory(first)
    right = inventory(second)
    if left != right:
        differences = sorted(name for name in ARTIFACTS if left[name] != right[name])
        raise ReproducibilityError(
            "canonical workspace hashes differ: " + ",".join(differences))
    document = {
        "schemaVersion": SCHEMA,
        "status": "PASS",
        "source": source,
        "toolchainManifest": "docs/v5x/v5.0/release-toolchain.json",
        "containerIndexDigest": toolchain["container"]["indexDigest"],
        "containerPlatformDigest": toolchain["container"]["platformDigest"],
        "architecture": toolchain["architecture"],
        "javaFullVersion": toolchain["java"]["fullVersion"],
        "mavenVersion": toolchain["mavenWrapper"]["version"],
        "independentCleanWorkspaces": 2,
        "canonicalJarCount": 9,
        "canonicalPomCount": 3,
        "artifacts": left,
        "claim": "EXACT_UNSIGNED_BYTE_IDENTITY",
    }
    output.mkdir(parents=True, exist_ok=False)
    evidence = output / "evidence.json"
    evidence.write_bytes(canonical_json(document))
    (output / CHECKSUMS).write_text(
        f"{sha256(evidence)}  evidence.json\n", encoding="ascii")
    return validate_record(output)


def validate_record(output: Path) -> dict[str, Any]:
    if not output.is_dir() or output.is_symlink() \
            or {path.name for path in output.iterdir()} != {
                "evidence.json", CHECKSUMS}:
        raise ReproducibilityError("reproducibility evidence inventory differs")
    if any(not path.is_file() or path.is_symlink() for path in output.iterdir()):
        raise ReproducibilityError("reproducibility evidence member is not a regular file")
    evidence = output / "evidence.json"
    if (output / CHECKSUMS).read_text(encoding="ascii") != \
            f"{sha256(evidence)}  evidence.json\n":
        raise ReproducibilityError("reproducibility evidence checksum differs")
    try:
        document = json.loads(evidence.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as failure:
        raise ReproducibilityError("reproducibility evidence is invalid JSON") from failure
    expected = {
        "schemaVersion", "status", "source", "toolchainManifest",
        "containerIndexDigest", "containerPlatformDigest", "architecture",
        "javaFullVersion", "mavenVersion", "independentCleanWorkspaces",
        "canonicalJarCount", "canonicalPomCount", "artifacts", "claim",
    }
    if not isinstance(document, dict) or set(document) != expected \
            or document.get("schemaVersion") != SCHEMA \
            or document.get("status") != "PASS" \
            or document.get("toolchainManifest") \
            != "docs/v5x/v5.0/release-toolchain.json" \
            or document.get("independentCleanWorkspaces") != 2 \
            or document.get("canonicalJarCount") != 9 \
            or document.get("canonicalPomCount") != 3 \
            or document.get("claim") != "EXACT_UNSIGNED_BYTE_IDENTITY":
        raise ReproducibilityError("reproducibility evidence shape differs")
    validate_source(document.get("source"))
    toolchain = validate_toolchain(ROOT / "docs/v5x/v5.0/release-toolchain.json")
    if document.get("containerIndexDigest") != toolchain["container"]["indexDigest"] \
            or document.get("containerPlatformDigest") \
            != toolchain["container"]["platformDigest"] \
            or document.get("architecture") != toolchain["architecture"] \
            or document.get("javaFullVersion") != toolchain["java"]["fullVersion"] \
            or document.get("mavenVersion") != toolchain["mavenWrapper"]["version"]:
        raise ReproducibilityError("canonical toolchain binding differs")
    artifacts = document.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != ARTIFACTS \
            or any(not isinstance(digest, str) or len(digest) != 64
                   or any(character not in "0123456789abcdef" for character in digest)
                   for digest in artifacts.values()):
        raise ReproducibilityError("canonical artifact hashes differ")
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("record")
    record.add_argument("--first", type=Path, required=True)
    record.add_argument("--second", type=Path, required=True)
    record.add_argument("--output", type=Path, required=True)
    record.add_argument("--source", type=Path, required=True)
    verify = commands.add_parser("validate")
    verify.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "record":
        value = write_record(arguments.first, arguments.second,
                             arguments.output, json.loads(arguments.source.read_text()))
    else:
        value = validate_record(arguments.bundle)
    print("v50CanonicalReproducibility=PASS "
          f"source={value['source']['kind']} jars=9 poms=3 workspaces=2")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReproducibilityError, OSError) as failure:
        print(f"v50CanonicalReproducibility=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
