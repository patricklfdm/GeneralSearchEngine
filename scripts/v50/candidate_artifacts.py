#!/usr/bin/env python3
"""Validate the exact nine-JAR V5.0 release-candidate byte inventory."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from scripts.v50.canonical_reproducibility import JARS, validate_record


MANIFEST = Path("docs/v5x/v5.0/candidate-artifacts.sha256")
LINE = re.compile(r"([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)")


class CandidateArtifactError(ValueError):
    """The candidate manifest or compared artifact inventory is invalid."""


def read_manifest(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        raise CandidateArtifactError("candidate manifest is not a regular file")
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as failure:
        raise CandidateArtifactError("candidate manifest is unreadable") from failure
    if len(lines) != len(JARS):
        raise CandidateArtifactError("candidate manifest must contain exactly nine lines")
    parsed: dict[str, str] = {}
    for line in lines:
        match = LINE.fullmatch(line)
        if match is None:
            raise CandidateArtifactError("candidate manifest line is malformed")
        digest, name = match.groups()
        if name in parsed:
            raise CandidateArtifactError("candidate manifest contains a duplicate artifact")
        parsed[name] = digest
    if set(parsed) != JARS:
        raise CandidateArtifactError("candidate manifest artifact inventory differs")
    if list(parsed) != sorted(JARS):
        raise CandidateArtifactError("candidate manifest artifact order differs")
    return parsed


def write_from_evidence(bundle: Path, output: Path) -> dict[str, str]:
    if output.exists() or output.is_symlink():
        raise CandidateArtifactError("candidate manifest output already exists")
    record = validate_record(bundle)
    artifacts = record["artifacts"]
    selected = {name: artifacts[name] for name in sorted(JARS)}
    output.write_text("".join(
        f"{digest}  {name}\n" for name, digest in selected.items()),
        encoding="ascii")
    return read_manifest(output)


def validate_hashes(expected: dict[str, str], actual: dict[str, str]) -> None:
    if set(actual) != JARS:
        raise CandidateArtifactError("observed candidate artifact inventory differs")
    differences = sorted(name for name in JARS if actual[name] != expected[name])
    if differences:
        raise CandidateArtifactError(
            "candidate artifact hashes differ: " + "; ".join(
                f"{name} (expected={expected[name]}, actual={actual[name]})"
                for name in differences))


def validate_evidence(manifest: Path, bundle: Path) -> dict[str, str]:
    expected = read_manifest(manifest)
    record = validate_record(bundle)
    validate_hashes(expected, {
        name: record["artifacts"][name] for name in sorted(JARS)
    })
    return expected


def file_hash(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(directory: Path) -> dict[str, str]:
    if not directory.is_dir() or directory.is_symlink():
        raise CandidateArtifactError("candidate artifact directory is invalid")
    members = list(directory.iterdir())
    if {path.name for path in members} != JARS or len(members) != len(JARS) \
            or any(not path.is_file() or path.is_symlink() for path in members):
        raise CandidateArtifactError("candidate artifact directory inventory differs")
    return {path.name: file_hash(path) for path in members}


def validate_directory(manifest: Path, directory: Path) -> dict[str, str]:
    expected = read_manifest(manifest)
    validate_hashes(expected, inventory(directory))
    return expected


def validate_build(manifest: Path, core: Path, processor: Path,
                   replication: Path) -> dict[str, str]:
    expected = read_manifest(manifest)
    actual: dict[str, str] = {}
    for name in sorted(JARS):
        directory = processor if name.startswith("general-search-engine-processor-") \
            else core
        if name.startswith("general-search-engine-replication-"):
            directory = replication
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise CandidateArtifactError(f"candidate artifact is absent: {name}")
        actual[name] = file_hash(path)
    validate_hashes(expected, actual)
    return expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-manifest")
    from_evidence = commands.add_parser("from-evidence")
    from_evidence.add_argument("bundle", type=Path)
    from_evidence.add_argument("output", type=Path)
    evidence = commands.add_parser("validate-evidence")
    evidence.add_argument("bundle", type=Path)
    directory = commands.add_parser("validate-directory")
    directory.add_argument("directory", type=Path)
    build = commands.add_parser("validate-build")
    build.add_argument("--core", type=Path, default=Path("target"))
    build.add_argument("--processor", type=Path,
                       default=Path("general-search-engine-processor/target"))
    build.add_argument("--replication", type=Path,
                       default=Path("general-search-engine-replication/target"))
    arguments = parser.parse_args()

    if arguments.command == "validate-manifest":
        value = read_manifest(arguments.manifest)
    elif arguments.command == "from-evidence":
        value = write_from_evidence(arguments.bundle, arguments.output)
    elif arguments.command == "validate-evidence":
        value = validate_evidence(arguments.manifest, arguments.bundle)
    elif arguments.command == "validate-directory":
        value = validate_directory(arguments.manifest, arguments.directory)
    else:
        value = validate_build(arguments.manifest, arguments.core,
                               arguments.processor, arguments.replication)
    print(f"v50CandidateArtifacts=PASS jars={len(value)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CandidateArtifactError, OSError) as failure:
        print(f"v50CandidateArtifacts=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
