#!/usr/bin/env python3
"""Independent pre-reopen inspection for V4.1 live cleanup crashes."""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

from scripts.v41.backup_crash_inspector import parse_marker


OBSOLETE_CHECKPOINT = re.compile(
    r"gse-checkpoint-00000000000000000000-2{32}\.chk"
)
SAFE_REMNANTS = {"gse-metadata.staging"}
OPERATION_STAGING = ".gse-v41-backup-33333333333333333333333333333333.staging"
OPERATION_MEMBERS = {"gse-backup-metadata", "gse-backup-manifest.staging"}


def digest(path: pathlib.Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(64 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def inspect(workspace: pathlib.Path, scope: str = "live") -> dict[str, object]:
    if scope not in {"live", "operation"}:
        raise ValueError("unsupported cleanup scope")
    store = workspace / ("store" if scope == "live" else "source")
    manifest = workspace / "protected.sha256"
    if not store.is_dir() or store.is_symlink() or not manifest.is_file():
        raise ValueError("workspace or protected manifest is absent")
    protected: dict[str, str] = {}
    for line in manifest.read_text(encoding="ascii").splitlines():
        expected, name = line.split("  ", 1)
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or name in protected:
            raise ValueError("invalid protected manifest")
        protected[name] = expected
    observed = {member.name: member for member in store.iterdir()}
    for name, expected in protected.items():
        member = observed.get(name)
        if member is None or member.is_symlink() or not member.is_file():
            raise ValueError(f"protected member is absent or unsafe: {name}")
        if digest(member) != expected:
            raise ValueError(f"protected member changed: {name}")
    extras: list[str]
    if scope == "live":
        extras = sorted(set(observed) - set(protected))
        for name in extras:
            member = observed[name]
            if member.is_symlink() or not member.is_file():
                raise ValueError(f"non-regular remnant: {name}")
            if name not in SAFE_REMNANTS \
                    and not OBSOLETE_CHECKPOINT.fullmatch(name):
                raise ValueError(f"unexpected member: {name}")
    else:
        extras = inspect_operation_remnants(workspace)
    return {
        "schemaVersion": "gse-v41-cleanup-crash-inspection-v1",
        "status": "PASS",
        "scope": scope,
        "protectedMembers": len(protected),
        "safeRemnants": extras,
    }


def inspect_operation_remnants(workspace: pathlib.Path) -> list[str]:
    staging = workspace / OPERATION_STAGING
    marker = workspace / f"{OPERATION_STAGING}.operation"
    target = workspace / "backup"
    if target.exists() or target.is_symlink():
        raise ValueError("operation cleanup created or retained the final target")
    remnants: list[str] = []
    if staging.exists() or staging.is_symlink():
        if staging.is_symlink() or not staging.is_dir():
            raise ValueError("operation staging is not a plain directory")
        names = {member.name for member in staging.iterdir()}
        if not names.issubset(OPERATION_MEMBERS):
            raise ValueError("operation staging contains an unexpected member")
        for member in staging.iterdir():
            if member.is_symlink() or not member.is_file():
                raise ValueError("operation staging member is not regular")
        remnants.append(OPERATION_STAGING)
    if marker.exists() or marker.is_symlink():
        if marker.is_symlink() or not marker.is_file():
            raise ValueError("operation marker is not a plain file")
        binding = parse_marker(marker)
        if binding["staging"] != OPERATION_STAGING:
            raise ValueError("operation marker has the wrong staging binding")
        remnants.append(marker.name)
    return sorted(remnants)


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("usage: cleanup_crash_inspector.py WORKSPACE [SCOPE]")
    try:
        scope = sys.argv[2] if len(sys.argv) == 3 else "live"
        report = inspect(pathlib.Path(sys.argv[1]).resolve(), scope)
    except (OSError, ValueError) as failure:
        print(f"v41CleanupInspection=FAIL reason={failure}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
