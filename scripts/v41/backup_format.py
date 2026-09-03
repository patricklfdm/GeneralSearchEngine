#!/usr/bin/env python3
"""Independent gse-backup (1,0) fixture encoder and byte inspector."""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
from dataclasses import dataclass
from pathlib import Path

BACKUP_MAGIC = 0x475345424B503130  # GSEBKP10
METADATA_MAGIC = 0x4753454D45544131  # GSEMETA1
CHECKPOINT_MAGIC = 0x47534543484B3130  # GSECHK10
FORMAT_FAMILY = "gse-backup"
FORMAT_MAJOR = 1
FORMAT_MINOR = 0
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MEMBERS = (
    "gse-backup-checkpoint",
    "gse-backup-manifest",
    "gse-backup-metadata",
)
PAYLOAD_MEMBERS = (
    "gse-backup-checkpoint",
    "gse-backup-metadata",
)
DOMAIN = b"gse-backup-content-v1\x00"
IDENTITY_PATTERN = re.compile(r"gse-backup-v1-[0-9a-f]{64}")


class BackupFormatError(ValueError):
    """A bundle violates the frozen Phase 1 wire format."""


def crc32c(data: bytes) -> int:
    checksum = 0xFFFFFFFF
    for value in data:
        checksum ^= value
        for _ in range(8):
            checksum = ((checksum >> 1) ^ 0x82F63B78) \
                if checksum & 1 else checksum >> 1
    return checksum ^ 0xFFFFFFFF


def lp(value: str) -> bytes:
    encoded = value.encode("utf-8", errors="strict")
    return struct.pack(">I", len(encoded)) + encoded


def checked(data: bytes) -> bytes:
    return data + struct.pack(">I", crc32c(data))


class Cursor:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def take(self, size: int) -> bytes:
        if size < 0 or self.offset + size > len(self.data):
            raise BackupFormatError("bounded field is truncated")
        value = self.data[self.offset:self.offset + size]
        self.offset += size
        return value

    def unpack(self, shape: str) -> tuple[object, ...]:
        return struct.unpack(shape, self.take(struct.calcsize(shape)))

    def string(self, maximum: int = 1024) -> str:
        (length,) = self.unpack(">I")
        if length > maximum:
            raise BackupFormatError("string exceeds its format bound")
        try:
            return self.take(length).decode("utf-8", errors="strict")
        except UnicodeError as failure:
            raise BackupFormatError("string is not strict UTF-8") from failure


@dataclass(frozen=True)
class Fixture:
    metadata: bytes
    checkpoint: bytes
    manifest: bytes
    content_identity: str


def fixture() -> Fixture:
    history_most = 0x0011223344556677
    history_least = 0x8899AABBCCDDEEFF
    metadata_content = b"".join((
        struct.pack(">QhhQQ", METADATA_MAGIC, 1, 0, history_most, history_least),
        lp("gse-durable"),
        lp("v41-fixture-store"),
        lp("v41-fixture-schema"),
        lp("v41-fixture-codec"),
        struct.pack(">iiiiiqqi", 1, 1024, 4096, 1000, 10000,
                    1_048_576, 67_108_864, 0),
    ))
    metadata = checked(metadata_content)
    key = b"doc-1"
    document = b"fixture-value"
    checkpoint_content = b"".join((
        struct.pack(">QhhQQqiii", CHECKPOINT_MAGIC, 1, 0,
                    history_most, history_least, 7, 1, 1, 0),
        struct.pack(">iB", 1, 1),
        struct.pack(">i", len(key)), key,
        struct.pack(">i", len(document)), document,
    ))
    checkpoint = checked(checkpoint_content)
    fields = {
        "family": FORMAT_FAMILY,
        "sourceFamily": "gse-durable",
        "historyMost": history_most,
        "historyLeast": history_least,
        "sequence": 7,
        "storageIdentity": "v41-fixture-store",
        "schemaIdentity": "v41-fixture-schema",
        "codecIdentity": "v41-fixture-codec",
        "codecVersion": 1,
    }
    payloads = {
        "gse-backup-checkpoint": checkpoint,
        "gse-backup-metadata": metadata,
    }
    preimage = content_preimage(fields, payloads)
    content_digest = hashlib.sha256(preimage).digest()
    identity = "gse-backup-v1-" + content_digest.hex()
    manifest_content = b"".join((
        struct.pack(">Qhh", BACKUP_MAGIC, FORMAT_MAJOR, FORMAT_MINOR),
        lp(FORMAT_FAMILY),
        lp("gse-durable"),
        struct.pack(">hhQQq", 1, 0, history_most, history_least, 7),
        lp(fields["storageIdentity"]),
        lp(fields["schemaIdentity"]),
        lp(fields["codecIdentity"]),
        struct.pack(">iI", 1, len(PAYLOAD_MEMBERS)),
        *(
            lp(name)
            + struct.pack(">Q", len(payloads[name]))
            + hashlib.sha256(payloads[name]).digest()
            for name in PAYLOAD_MEMBERS
        ),
        content_digest,
        struct.pack(">q", 0),
        lp("phase1-fixture"),
    ))
    manifest = checked(manifest_content)
    return Fixture(metadata, checkpoint, manifest, identity)


def content_preimage(fields: dict[str, object], payloads: dict[str, bytes]) -> bytes:
    return b"".join((
        DOMAIN,
        lp(str(fields["family"])),
        struct.pack(">hh", FORMAT_MAJOR, FORMAT_MINOR),
        lp(str(fields["sourceFamily"])),
        struct.pack(">hhQQq", 1, 0,
                    int(fields["historyMost"]), int(fields["historyLeast"]),
                    int(fields["sequence"])),
        lp(str(fields["storageIdentity"])),
        lp(str(fields["schemaIdentity"])),
        lp(str(fields["codecIdentity"])),
        struct.pack(">iI", int(fields["codecVersion"]), len(payloads)),
        *(
            lp(name)
            + struct.pack(">Q", len(payloads[name]))
            + hashlib.sha256(payloads[name]).digest()
            for name in sorted(payloads, key=lambda item: item.encode("utf-8"))
        ),
    ))


def parse_manifest(data: bytes) -> dict[str, object]:
    if len(data) < 128 or len(data) > MAX_MANIFEST_BYTES:
        raise BackupFormatError("manifest size is outside the frozen bound")
    if crc32c(data[:-4]) != struct.unpack(">I", data[-4:])[0]:
        raise BackupFormatError("manifest CRC32C mismatch")
    cursor = Cursor(data[:-4])
    magic, major, minor = cursor.unpack(">Qhh")
    family = cursor.string(128)
    source_family = cursor.string(128)
    source_major, source_minor, history_most, history_least, sequence = \
        cursor.unpack(">hhQQq")
    storage_identity = cursor.string(128)
    schema_identity = cursor.string(128)
    codec_identity = cursor.string(128)
    codec_version, count = cursor.unpack(">iI")
    if (magic, major, minor, family) != (
            BACKUP_MAGIC, FORMAT_MAJOR, FORMAT_MINOR, FORMAT_FAMILY):
        raise BackupFormatError("unsupported backup header")
    if (source_family, source_major, source_minor) != ("gse-durable", 1, 0):
        raise BackupFormatError("unsupported source storage format")
    if sequence < 0 or codec_version < 0 or count != 2:
        raise BackupFormatError("manifest identity fields are invalid")
    members: dict[str, dict[str, object]] = {}
    ordered_names: list[str] = []
    for _ in range(count):
        name = cursor.string(128)
        size, = cursor.unpack(">Q")
        digest = cursor.take(32).hex()
        if name in members:
            raise BackupFormatError("duplicate manifest member")
        ordered_names.append(name)
        members[name] = {"size": size, "sha256": digest}
    content_digest = cursor.take(32).hex()
    created_epoch_millis, = cursor.unpack(">q")
    request_id = cursor.string(256)
    if cursor.offset != len(cursor.data):
        raise BackupFormatError("manifest has trailing bytes")
    if tuple(ordered_names) != PAYLOAD_MEMBERS:
        raise BackupFormatError("manifest payload inventory is not canonical")
    return {
        "family": family,
        "major": major,
        "minor": minor,
        "sourceFamily": source_family,
        "sourceMajor": source_major,
        "sourceMinor": source_minor,
        "historyMost": history_most,
        "historyLeast": history_least,
        "sequence": sequence,
        "storageIdentity": storage_identity,
        "schemaIdentity": schema_identity,
        "codecIdentity": codec_identity,
        "codecVersion": codec_version,
        "members": members,
        "contentDigest": content_digest,
        "contentIdentity": "gse-backup-v1-" + content_digest,
        "createdEpochMillis": created_epoch_millis,
        "requestId": request_id,
        "bytes": len(data),
    }


def parse_metadata(data: bytes) -> dict[str, object]:
    if len(data) < 64 or crc32c(data[:-4]) != struct.unpack(">I", data[-4:])[0]:
        raise BackupFormatError("source metadata checksum or size is invalid")
    cursor = Cursor(data[:-4])
    magic, major, minor, history_most, history_least = cursor.unpack(">QhhQQ")
    family = cursor.string(128)
    storage_identity = cursor.string(128)
    schema_identity = cursor.string(128)
    codec_identity = cursor.string(128)
    codec_version, max_key, max_document, max_bulk, max_documents, \
        checkpoint_wal, max_retained, index_count = cursor.unpack(">iiiiiqqi")
    if (magic, major, minor, family) != (METADATA_MAGIC, 1, 0, "gse-durable"):
        raise BackupFormatError("source metadata format is unsupported")
    limits = (max_key, max_document, max_bulk, max_documents,
              checkpoint_wal, max_retained)
    if codec_version < 0 or any(value <= 0 for value in limits) \
            or max_retained <= checkpoint_wal \
            or index_count < 0 or index_count > 100_000:
        raise BackupFormatError("source metadata bounds are invalid")
    indexes: list[tuple[int, str, str]] = []
    for _ in range(index_count):
        kind, = cursor.unpack(">B")
        field = cursor.string(1024)
        analyzer = cursor.string(128)
        if kind not in {1, 2, 3, 4} or (kind == 4) != (analyzer == "gse-simple-v1"):
            raise BackupFormatError("source metadata index is invalid")
        indexes.append((kind, field, analyzer))
    if cursor.offset != len(cursor.data) or len(indexes) != len(set(indexes)):
        raise BackupFormatError("source metadata is not canonical")
    return {
        "family": family, "major": major, "minor": minor,
        "historyMost": history_most, "historyLeast": history_least,
        "storageIdentity": storage_identity, "schemaIdentity": schema_identity,
        "codecIdentity": codec_identity, "codecVersion": codec_version,
        "maxKey": max_key, "maxDocument": max_document,
        "maxDocuments": max_documents, "indexes": indexes,
    }


def parse_checkpoint(data: bytes, metadata: dict[str, object]) -> dict[str, object]:
    if len(data) < 56 or crc32c(data[:-4]) != struct.unpack(">I", data[-4:])[0]:
        raise BackupFormatError("source checkpoint checksum or size is invalid")
    cursor = Cursor(data[:-4])
    magic, major, minor, history_most, history_least, sequence, next_doc_id, \
        live_documents, index_count = cursor.unpack(">QhhQQqiii")
    if (magic, major, minor) != (CHECKPOINT_MAGIC, 1, 0) \
            or history_most != metadata["historyMost"] \
            or history_least != metadata["historyLeast"] \
            or sequence < 0 or next_doc_id < 0 \
            or live_documents < 0 or live_documents > next_doc_id \
            or live_documents > metadata["maxDocuments"] \
            or index_count < 0 or index_count > 100_000:
        raise BackupFormatError("source checkpoint identity or bounds are invalid")
    indexes: list[tuple[int, str, str]] = []
    for _ in range(index_count):
        kind, = cursor.unpack(">B")
        field = cursor.string(1024)
        analyzer = cursor.string(128)
        if kind not in {1, 2, 3, 4} or (kind == 4) != (analyzer == "gse-simple-v1"):
            raise BackupFormatError("source checkpoint index is invalid")
        indexes.append((kind, field, analyzer))
    slot_count, = cursor.unpack(">i")
    if slot_count != next_doc_id or indexes != metadata["indexes"]:
        raise BackupFormatError("source checkpoint is not canonical")
    decoded_live = 0
    for _ in range(slot_count):
        state, = cursor.unpack(">B")
        if state == 0:
            continue
        if state != 1:
            raise BackupFormatError("source checkpoint slot state is invalid")
        key_size, = cursor.unpack(">i")
        if key_size < 0 or key_size > metadata["maxKey"]:
            raise BackupFormatError("source checkpoint key exceeds its bound")
        cursor.take(key_size)
        document_size, = cursor.unpack(">i")
        if document_size < 0 or document_size > metadata["maxDocument"]:
            raise BackupFormatError("source checkpoint document exceeds its bound")
        cursor.take(document_size)
        decoded_live += 1
    if decoded_live != live_documents or cursor.offset != len(cursor.data):
        raise BackupFormatError("source checkpoint payload is not canonical")
    return {"sequence": sequence, "nextDocId": next_doc_id,
            "liveDocuments": live_documents, "indexes": indexes}


def load_hex_fixture(directory: Path) -> Fixture:
    def read(name: str) -> bytes:
        path = directory / f"{name}.hex"
        try:
            text = path.read_text(encoding="ascii")
            return bytes.fromhex(text)
        except (OSError, UnicodeError, ValueError) as failure:
            raise BackupFormatError(f"invalid fixture representation: {path}") from failure

    metadata = read("gse-backup-metadata")
    checkpoint = read("gse-backup-checkpoint")
    manifest = read("gse-backup-manifest")
    parsed = parse_manifest(manifest)
    return Fixture(metadata, checkpoint, manifest, str(parsed["contentIdentity"]))


def inspect_bundle(directory: Path) -> dict[str, object]:
    if not directory.is_dir() or directory.is_symlink():
        raise BackupFormatError("backup path must be a non-symbolic directory")
    entries = list(directory.iterdir())
    names = tuple(sorted(entry.name for entry in entries))
    if names != MEMBERS:
        raise BackupFormatError(f"backup inventory mismatch: {names}")
    for entry in entries:
        if entry.is_symlink() or not entry.is_file():
            raise BackupFormatError(f"non-regular backup member: {entry.name}")
    before = {entry.name: entry.stat() for entry in entries}
    payloads = {
        name: (directory / name).read_bytes()
        for name in PAYLOAD_MEMBERS
    }
    manifest_data = (directory / "gse-backup-manifest").read_bytes()
    after = {entry.name: entry.stat() for entry in entries}
    for name in MEMBERS:
        if (before[name].st_size, before[name].st_mtime_ns) != \
                (after[name].st_size, after[name].st_mtime_ns):
            raise BackupFormatError(f"member changed while read: {name}")
    manifest = parse_manifest(manifest_data)
    metadata = parse_metadata(payloads["gse-backup-metadata"])
    checkpoint = parse_checkpoint(payloads["gse-backup-checkpoint"], metadata)
    for name, payload in payloads.items():
        descriptor = manifest["members"][name]  # type: ignore[index]
        if descriptor["size"] != len(payload) or \
                descriptor["sha256"] != hashlib.sha256(payload).hexdigest():
            raise BackupFormatError(f"payload integrity mismatch: {name}")
    fields = {
        key: manifest[key]
        for key in ("family", "sourceFamily", "historyMost", "historyLeast",
                    "sequence", "storageIdentity", "schemaIdentity",
                    "codecIdentity", "codecVersion")
    }
    recomputed = hashlib.sha256(content_preimage(fields, payloads)).hexdigest()
    if recomputed != manifest["contentDigest"]:
        raise BackupFormatError("content identity mismatch")
    for field in ("historyMost", "historyLeast", "storageIdentity",
                  "schemaIdentity", "codecIdentity", "codecVersion"):
        if manifest[field] != metadata[field]:
            raise BackupFormatError(f"manifest/source metadata mismatch: {field}")
    if manifest["sequence"] != checkpoint["sequence"]:
        raise BackupFormatError("manifest/source checkpoint sequence mismatch")
    return {
        "schemaVersion": "gse-v41-backup-inspection-v1",
        "status": "VALID",
        "format": "gse-backup (1,0)",
        "contentIdentity": manifest["contentIdentity"],
        "sourceHistory": f"{manifest['historyMost']:016x}{manifest['historyLeast']:016x}",
        "sequence": manifest["sequence"],
        "members": list(MEMBERS),
        "authoritativeBytes": sum(entry.stat().st_size for entry in entries),
    }


def _main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("fixture-hex")
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("directory", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "fixture-hex":
        value = fixture()
        print("gse-backup-metadata=" + value.metadata.hex())
        print("gse-backup-checkpoint=" + value.checkpoint.hex())
        print("gse-backup-manifest=" + value.manifest.hex())
        print("contentIdentity=" + value.content_identity)
        return 0
    result = inspect_bundle(arguments.directory)
    print("v41BackupInspection=PASS "
          f"identity={result['contentIdentity']} sequence={result['sequence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
