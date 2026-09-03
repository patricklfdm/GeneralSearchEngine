#!/usr/bin/env python3
"""Independent Phase 3 source/bundle classifier after abrupt backup death."""

from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

from scripts.v4.storage_inspector import inspect_phase4_directory
from scripts.v41.backup_format import (
    BackupFormatError,
    Cursor,
    MEMBERS,
    crc32c,
    inspect_bundle,
)

STAGING = re.compile(r"\.gse-v41-backup-[0-9a-f]{32}\.staging")
FINAL_BARRIERS = {
    "v41-backup-after-final-rename-v1",
    "v41-backup-after-parent-force-v1",
    "v41-backup-before-future-completion-v1",
}
OPERATION_MAGIC = 0x4753454F50313030


def parse_marker(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < 50 or crc32c(data[:-4]) != struct.unpack(">I", data[-4:])[0]:
        raise BackupFormatError("operation marker checksum or size is invalid")
    cursor = Cursor(data[:-4])
    magic, major, minor, kind, history_most, history_least = cursor.unpack(
        ">QhhBQQ"
    )
    staging_name = cursor.string(128)
    target_name = cursor.string(255)
    if cursor.offset != len(cursor.data):
        raise BackupFormatError("operation marker has trailing bytes")
    operation_id = f"{history_most:016x}{history_least:016x}"
    expected_staging = f".gse-v41-backup-{operation_id}.staging"
    if (magic, major, minor, kind) != (OPERATION_MAGIC, 1, 0, 1) \
            or staging_name != expected_staging \
            or path.name != staging_name + ".operation" \
            or target_name != "backup" \
            or "/" in target_name or "\\" in target_name:
        raise BackupFormatError("operation marker binding is invalid")
    return {"operationId": operation_id, "staging": staging_name,
            "target": target_name}


def inspect_crash(workspace: Path, barrier: str) -> dict[str, object]:
    if (workspace / "graceful-close.marker").exists():
        raise BackupFormatError("graceful shutdown ran during abrupt backup case")
    source = inspect_phase4_directory(workspace / "source")
    target = workspace / "backup"
    staging = sorted(
        path for path in workspace.iterdir() if STAGING.fullmatch(path.name)
    )
    markers = sorted(
        path for path in workspace.iterdir()
        if path.name.endswith(".staging.operation")
    )
    if len(staging) > 1 or len(markers) > 1:
        raise BackupFormatError("multiple operation remnants are ambiguous")
    marker = None if not markers else parse_marker(markers[0])
    if marker is not None and staging \
            and marker["staging"] != staging[0].name:
        raise BackupFormatError("operation marker does not bind the staging member")

    bundle: dict[str, object] | None = None
    if barrier in FINAL_BARRIERS:
        if not target.is_dir() or staging:
            raise BackupFormatError("published backup state is incomplete")
        bundle = inspect_bundle(target)
    else:
        if target.exists():
            raise BackupFormatError("backup was published before its authority barrier")
        if staging:
            names = tuple(sorted(path.name for path in staging[0].iterdir()))
            if names == MEMBERS:
                bundle = inspect_bundle(staging[0])
            elif "gse-backup-manifest" in names:
                raise BackupFormatError("completion manifest exists without exact bundle")

    if bundle is not None and bundle["sequence"] != 1:
        raise BackupFormatError("backup cut sequence is not exact")
    return {
        "schemaVersion": "gse-v41-backup-crash-inspection-v1",
        "status": "PASS",
        "barrier": barrier,
        "sourceSequence": source.get("durableSequence", 0),
        "finalBundle": target.is_dir(),
        "stagingCount": len(staging),
        "markerCount": len(markers),
        "markerBinding": marker,
        "bundleStatus": None if bundle is None else bundle["status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("barrier")
    arguments = parser.parse_args()
    result = inspect_crash(arguments.workspace.resolve(), arguments.barrier)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
