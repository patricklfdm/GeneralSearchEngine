#!/usr/bin/env python3
"""Record and validate V4.4 canonical two-workspace artifact identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from scripts.v44.evidence import canonical_json, validate_source
from scripts.v44.toolchain_manifest import validate as validate_toolchain

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "gse-v44-canonical-reproducibility-v1"
CHECKSUMS = "artifact-checksums.sha256"
VERSION = "4.4.0-SNAPSHOT"
JARS = {
    f"general-search-engine-{VERSION}.jar",
    f"general-search-engine-{VERSION}-sources.jar",
    f"general-search-engine-{VERSION}-javadoc.jar",
    f"general-search-engine-processor-{VERSION}.jar",
    f"general-search-engine-processor-{VERSION}-sources.jar",
    f"general-search-engine-processor-{VERSION}-javadoc.jar",
}
POMS = {"general-search-engine.pom", "general-search-engine-processor.pom"}
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


def write_record(first: Path, second: Path, output: Path, source: str) -> dict[str, Any]:
    source = validate_source(source)
    toolchain = validate_toolchain(ROOT / "docs/v4x/v4.4/release-toolchain.json")
    left = inventory(first)
    right = inventory(second)
    if left != right:
        differences = sorted(name for name in ARTIFACTS if left[name] != right[name])
        raise ReproducibilityError(
            "canonical workspace hashes differ: " + ",".join(differences))
    document = {
        "schemaVersion": SCHEMA,
        "status": "PASS",
        "sourceCommit": source,
        "toolchainManifest": "docs/v4x/v4.4/release-toolchain.json",
        "containerIndexDigest": toolchain["container"]["indexDigest"],
        "containerPlatformDigest": toolchain["container"]["platformDigest"],
        "architecture": toolchain["architecture"],
        "javaFullVersion": toolchain["java"]["fullVersion"],
        "mavenVersion": toolchain["mavenWrapper"]["version"],
        "independentCleanWorkspaces": 2,
        "canonicalJarCount": 6,
        "canonicalPomCount": 2,
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
    evidence = output / "evidence.json"
    if (output / CHECKSUMS).read_text(encoding="ascii") != \
            f"{sha256(evidence)}  evidence.json\n":
        raise ReproducibilityError("reproducibility evidence checksum differs")
    try:
        document = json.loads(evidence.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as failure:
        raise ReproducibilityError("reproducibility evidence is invalid JSON") from failure
    expected = {
        "schemaVersion", "status", "sourceCommit", "toolchainManifest",
        "containerIndexDigest", "containerPlatformDigest", "architecture",
        "javaFullVersion", "mavenVersion", "independentCleanWorkspaces",
        "canonicalJarCount", "canonicalPomCount", "artifacts", "claim",
    }
    if not isinstance(document, dict) or set(document) != expected \
            or document.get("schemaVersion") != SCHEMA \
            or document.get("status") != "PASS" \
            or document.get("toolchainManifest") \
            != "docs/v4x/v4.4/release-toolchain.json" \
            or document.get("independentCleanWorkspaces") != 2 \
            or document.get("canonicalJarCount") != 6 \
            or document.get("canonicalPomCount") != 2 \
            or document.get("claim") != "EXACT_UNSIGNED_BYTE_IDENTITY":
        raise ReproducibilityError("reproducibility evidence shape differs")
    validate_source(document.get("sourceCommit"))
    toolchain = validate_toolchain(ROOT / "docs/v4x/v4.4/release-toolchain.json")
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
    record.add_argument("--source-sha", required=True)
    verify = commands.add_parser("validate")
    verify.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "record":
        value = write_record(arguments.first, arguments.second,
                             arguments.output, arguments.source_sha)
    else:
        value = validate_record(arguments.bundle)
    print("v44CanonicalReproducibility=PASS "
          f"source={value['sourceCommit']} jars=6 poms=2 workspaces=2")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReproducibilityError, OSError) as failure:
        print(f"v44CanonicalReproducibility=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
