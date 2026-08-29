#!/usr/bin/env python3
"""Test-only create-only gcloud storage double."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from scripts.cloud import benchmark_v2 as v2


def fail(message: str, code: int = 1) -> int:
    print(message, file=sys.stderr)
    return code


def main() -> int:
    state_text = os.environ.get("FAKE_GCS_STATE_DIR")
    if not state_text:
        return fail("FAKE_GCS_STATE_DIR is required", 2)
    state = Path(state_text)
    objects = state / "objects"
    metadata_dir = state / "metadata"
    state.mkdir(parents=True, exist_ok=True)
    objects.mkdir(exist_ok=True)
    metadata_dir.mkdir(exist_ok=True)
    with (state / "commands.log").open("a", encoding="utf-8") as target:
        target.write(json.dumps(sys.argv[1:], separators=(",", ":")) + "\n")
    arguments = sys.argv[1:]
    if len(arguments) < 2 or arguments[:1] != ["storage"]:
        return fail("fake gcloud supports storage only", 2)

    if arguments[1:3] == ["objects", "describe"] and len(arguments) >= 4:
        uri = arguments[3]
        key = v2.sha256_bytes(uri.encode("utf-8"))
        metadata_path = metadata_dir / f"{key}.json"
        if not metadata_path.is_file():
            return 1
        sys.stdout.write(metadata_path.read_text(encoding="utf-8"))
        return 0

    if arguments[1] == "cp" and len(arguments) >= 4:
        source = Path(arguments[2])
        uri = arguments[3]
        if "--if-generation-match=0" not in arguments:
            return fail("create-only generation precondition is required", 2)
        metadata_arg = next(
            (item for item in arguments if item.startswith("--custom-metadata=gse-sha256=")),
            None,
        )
        if metadata_arg is None:
            return fail("gse-sha256 metadata is required", 2)
        sha256_hex = metadata_arg.rsplit("=", 1)[1]
        key = v2.sha256_bytes(uri.encode("utf-8"))
        metadata_path = metadata_dir / f"{key}.json"
        if metadata_path.exists():
            return 1
        if os.environ.get("FAKE_GCS_FAIL_URI") == uri:
            return 1
        integrity = v2.local_object_integrity(source)
        bucket, name = v2.split_gcs_uri(uri)
        generation_file = state / "generation"
        generation = int(generation_file.read_text(encoding="utf-8")) + 1 \
            if generation_file.exists() else 1000
        generation_file.write_text(str(generation), encoding="utf-8")
        shutil.copyfile(source, objects / key)
        metadata = {
            "bucket": bucket,
            "crc32c_hash": integrity["crc32c"],
            "custom_fields": {"gse-sha256": sha256_hex},
            "generation": str(generation),
            "md5_hash": integrity["md5"],
            "name": name,
            "size": integrity["size"],
        }
        metadata_path.write_bytes(v2.canonical_json_bytes(metadata))
        return 0

    return fail("unsupported fake gcloud storage command", 2)


if __name__ == "__main__":
    raise SystemExit(main())
