#!/usr/bin/env python3
"""Independent Phase 1 storage inventory; production format parsing starts in Phase 2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.v4.evidence import EvidenceError

RESERVED_PRODUCTION_PREFIXES = ("manifest", "checkpoint-", "wal-")


def inspect_phase1_directory(workspace: Path, barrier: str) -> dict[str, object]:
    if not workspace.is_dir() or workspace.is_symlink():
        raise EvidenceError("engine directory must be a regular directory")
    entries = sorted(workspace.iterdir(), key=lambda entry: entry.name)
    for entry in entries:
        if not entry.is_file() or entry.is_symlink():
            raise EvidenceError(f"unexpected engine-directory member: {entry.name}")
        if entry.name.startswith(RESERVED_PRODUCTION_PREFIXES):
            raise EvidenceError("Phase 1 contains a production storage artifact")
    state = workspace / "phase1-scaffold.properties"
    if not state.is_file():
        raise EvidenceError("phase1 scaffold state is missing")
    text = state.read_text(encoding="utf-8")
    if f"barrierId={barrier}\n" not in text:
        raise EvidenceError("phase1 scaffold barrier mismatch")
    if "productionStorage=false\n" not in text:
        raise EvidenceError("Phase 1 must not claim production storage")
    if (workspace / "graceful-close.marker").exists():
        raise EvidenceError("graceful shutdown path ran")
    return {
        "schemaVersion": "gse-v4-storage-inspection-v1",
        "classification": "NO_PRODUCTION_STORAGE_EXPECTED",
        "barrierId": barrier,
        "files": [entry.name for entry in entries],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--barrier", required=True)
    arguments = parser.parse_args()
    print(json.dumps(
        inspect_phase1_directory(arguments.directory, arguments.barrier),
        sort_keys=True,
        separators=(",", ":"),
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
