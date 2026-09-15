"""Generate and independently inspect bounded Phase 1 replica-format fixtures.

This module deliberately does not import production Java or implement a writable
replica store.  It freezes small manifest/log/proof/snapshot examples that later
storage code must remain compatible with.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FILES = ("manifest.json", "log.jsonl", "commit-proof.json", "snapshot.json")
MAX_FILE_BYTES = 1024 * 1024
MAX_BUNDLE_BYTES = 4 * MAX_FILE_BYTES


def _canonical(document: dict) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _entry(index: int, epoch: int, payload: str) -> dict:
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return {"epoch": epoch, "index": index, "payload": payload, "payloadSha256": digest}


def generate(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    documents = {
        "manifest.json": {
            "schemaVersion": "gse-replica-manifest-v1",
            "protocol": "gse-replication/1.0",
            "groupId": "11111111-1111-1111-1111-111111111111",
            "configurationId": "config-v1",
            "localNodeId": "node-2",
            "configuredLeaderId": "node-1",
            "voters": ["node-1", "node-2", "node-3"],
            "promisedEpoch": 3,
            "recoveryFloor": 2,
        },
        "commit-proof.json": {
            "schemaVersion": "gse-replica-commit-proof-v1",
            "epoch": 3,
            "commitIndex": 2,
            "voters": ["node-1", "node-2"],
        },
        "snapshot.json": {
            "schemaVersion": "gse-replica-snapshot-v1",
            "lastAppliedIndex": 2,
            "documentCount": 2,
            "materializationSha256": hashlib.sha256(b"fixture-materialization-v1").hexdigest(),
        },
    }
    log = [
        _entry(1, 2, "PUT:1:alpha"),
        _entry(2, 3, "PUT:2:beta"),
        _entry(3, 3, "PUT:3:uncommitted"),
    ]
    documents["commit-proof.json"]["entrySha256"] = log[1]["payloadSha256"]

    for name, document in documents.items():
        (directory / name).write_bytes(_canonical(document))
    (directory / "log.jsonl").write_bytes(b"".join(_canonical(entry) for entry in log))
    checksums = "".join(
        f"{hashlib.sha256((directory / name).read_bytes()).hexdigest()}  {name}\n"
        for name in FILES
    )
    (directory / "artifact-checksums.sha256").write_text(checksums, encoding="utf-8")


def inspect(directory: Path) -> dict:
    if not directory.is_dir():
        raise ValueError("fixture directory is absent")
    for name in (*FILES, "artifact-checksums.sha256"):
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"fixture member is absent or unsafe: {name}")
    sizes = {name: (directory / name).stat().st_size for name in FILES}
    if any(size <= 0 or size > MAX_FILE_BYTES for size in sizes.values()):
        raise ValueError("fixture member exceeds finite size bounds")
    if sum(sizes.values()) > MAX_BUNDLE_BYTES:
        raise ValueError("fixture bundle exceeds finite size bounds")

    expected = {}
    for line in (directory / "artifact-checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        expected[name.strip()] = digest
    if set(expected) != set(FILES):
        raise ValueError("fixture checksum inventory is not exact")
    for name in FILES:
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if actual != expected[name]:
            raise ValueError(f"fixture checksum mismatch: {name}")

    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    proof = json.loads((directory / "commit-proof.json").read_text(encoding="utf-8"))
    snapshot = json.loads((directory / "snapshot.json").read_text(encoding="utf-8"))
    log = [json.loads(line) for line in
           (directory / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    if manifest.get("schemaVersion") != "gse-replica-manifest-v1":
        raise ValueError("unsupported manifest schema")
    if manifest.get("protocol") != "gse-replication/1.0":
        raise ValueError("unsupported logical protocol")
    if manifest.get("voters") != ["node-1", "node-2", "node-3"]:
        raise ValueError("fixture must contain the exact three voters")
    if [entry.get("index") for entry in log] != list(range(1, len(log) + 1)):
        raise ValueError("log indexes are not contiguous")
    for entry in log:
        digest = hashlib.sha256(entry["payload"].encode()).hexdigest()
        if digest != entry.get("payloadSha256"):
            raise ValueError("log payload checksum mismatch")
    commit_index = proof.get("commitIndex")
    if proof.get("schemaVersion") != "gse-replica-commit-proof-v1":
        raise ValueError("unsupported commit-proof schema")
    if not isinstance(commit_index, int) or commit_index <= 0 or commit_index > len(log):
        raise ValueError("commit proof index is outside the log")
    if proof.get("voters") != ["node-1", "node-2"]:
        raise ValueError("commit proof does not contain the frozen quorum")
    if proof.get("entrySha256") != log[commit_index - 1]["payloadSha256"]:
        raise ValueError("commit proof does not identify the committed entry")
    if snapshot.get("schemaVersion") != "gse-replica-snapshot-v1":
        raise ValueError("unsupported snapshot schema")
    if snapshot.get("lastAppliedIndex") != commit_index:
        raise ValueError("snapshot apply point differs from commit proof")
    if manifest.get("recoveryFloor") != commit_index:
        raise ValueError("manifest recovery floor differs from commit proof")
    return {"manifest": manifest, "log": log, "commitProof": proof, "snapshot": snapshot}


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("directory", type=Path)
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.directory)
        print(f"v50ReplicaFixtureGeneration=PASS directory={args.directory}")
    else:
        fixture = inspect(args.directory)
        print("v50ReplicaFixtureInspection=PASS "
              f"entries={len(fixture['log'])} commitIndex={fixture['commitProof']['commitIndex']}")


if __name__ == "__main__":
    main()
