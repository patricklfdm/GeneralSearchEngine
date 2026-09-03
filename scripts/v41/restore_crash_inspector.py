#!/usr/bin/env python3
"""Independent Phase 4 classifier for abrupt restore publication death."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from scripts.v4.storage_inspector import inspect_phase4_directory
from scripts.v41.backup_format import (
    BackupFormatError,
    Cursor,
    crc32c,
    inspect_bundle,
)

STAGING = re.compile(r"\.gse-v41-restore-[0-9a-f]{32}\.staging")
FINAL_BARRIERS = {
    "v41-restore-after-final-rename-v1",
    "v41-restore-after-parent-force-v1",
    "v41-restore-before-return-v1",
}


def inspect_restore_crash(workspace: Path, barrier: str) -> dict[str, object]:
    if (workspace / "graceful-close.marker").exists():
        raise BackupFormatError("graceful shutdown ran during abrupt restore case")
    backup = inspect_bundle(workspace / "backup")
    target = workspace / "restored"
    staging = sorted(
        path for path in workspace.iterdir() if STAGING.fullmatch(path.name)
    )
    markers = sorted(
        path for path in workspace.iterdir()
        if path.name.endswith(".staging.operation")
    )
    if len(staging) > 1 or len(markers) > 1:
        raise BackupFormatError("multiple restore remnants are ambiguous")
    marker = None
    if markers:
        marker = parse_restore_marker(markers[0])
        if staging and marker["staging"] != staging[0].name:
            raise BackupFormatError("restore marker does not bind staging")

    target_state = None
    if barrier in FINAL_BARRIERS:
        if not target.is_dir() or staging:
            raise BackupFormatError("post-publication restore target is absent")
        target_state = inspect_phase4_directory(target)
        if target_state.get("durableSequence") != backup["sequence"]:
            raise BackupFormatError("restored sequence differs from backup")
    elif target.exists():
        raise BackupFormatError("restore target was published before final rename")

    return {
        "schemaVersion": "gse-v41-restore-crash-inspection-v1",
        "status": "PASS",
        "barrier": barrier,
        "backupSequence": backup["sequence"],
        "finalTarget": target.is_dir(),
        "stagingCount": len(staging),
        "markerCount": len(markers),
        "markerBinding": marker,
        "targetStatus": None if target_state is None else "VALID",
    }


def parse_restore_marker(path: Path) -> dict[str, object]:
    import struct

    data = path.read_bytes()
    if len(data) < 50 or crc32c(data[:-4]) != struct.unpack(">I", data[-4:])[0]:
        raise BackupFormatError("restore marker checksum or size is invalid")
    cursor = Cursor(data[:-4])
    magic, major, minor, kind, history_most, history_least = cursor.unpack(
        ">QhhBQQ"
    )
    staging_name = cursor.string(128)
    target_name = cursor.string(255)
    operation_id = f"{history_most:016x}{history_least:016x}"
    expected = f".gse-v41-restore-{operation_id}.staging"
    if cursor.offset != len(cursor.data) \
            or (magic, major, minor, kind) != (0x4753454F50313030, 1, 0, 2) \
            or staging_name != expected \
            or path.name != staging_name + ".operation" \
            or target_name != "restored" or "/" in target_name \
            or "\\" in target_name:
        raise BackupFormatError("restore marker binding is invalid")
    return {"operationId": operation_id, "staging": staging_name,
            "target": target_name}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("barrier")
    arguments = parser.parse_args()
    result = inspect_restore_crash(arguments.workspace.resolve(), arguments.barrier)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
