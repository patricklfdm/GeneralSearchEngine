"""Checksummed Phase 1 process and fake-cloud evidence bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "gse-v50-replication-evidence-v1"


def canonical_bytes(document: dict) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_bundle(directory: Path, document: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    document = dict(document)
    document["schemaVersion"] = SCHEMA
    data = canonical_bytes(document)
    (directory / "evidence.json").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (directory / "artifact-checksums.sha256").write_text(
        f"{digest}  evidence.json\n", encoding="utf-8")


def validate(directory: Path) -> dict:
    raw = (directory / "evidence.json").read_bytes()
    document = json.loads(raw)
    if document.get("schemaVersion") != SCHEMA:
        raise ValueError("unsupported evidence schema")
    expected = (directory / "artifact-checksums.sha256").read_text().split()[0]
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("evidence checksum mismatch")
    if document.get("sourceCommit") is None or document.get("profile") is None:
        raise ValueError("evidence identity is incomplete")
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    write = sub.add_parser("write-harness")
    write.add_argument("directory", type=Path)
    write.add_argument("--source-sha", required=True)
    write.add_argument("--workspace", required=True)
    check = sub.add_parser("validate")
    check.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "write-harness":
        write_bundle(args.directory, {
            "profile": "local-crash",
            "sourceCommit": args.source_sha,
            "authorityClaim": "fixture-only",
            "workspace": args.workspace,
            "voters": 3,
            "processesConcurrent": True,
            "crash": {"node": "node-1", "method": "SIGKILL", "restartGeneration": 2},
            "storageFault": {"node": "node-3", "exitCode": 20, "restartGeneration": 2},
        })
        print("v50ProcessEvidence=PASS")
    else:
        document = validate(args.directory)
        print(f"v50EvidenceValidation=PASS profile={document['profile']}")


if __name__ == "__main__":
    main()
