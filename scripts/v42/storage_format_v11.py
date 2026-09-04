#!/usr/bin/env python3
"""Independent gse-durable/gse-backup (1,1) encoder and structural inspector."""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
from dataclasses import dataclass
from pathlib import Path

METADATA_MAGIC = 0x4753454D45544131  # GSEMETA1
CHECKPOINT_MAGIC = 0x47534543484B3130  # GSECHK10
CHECKPOINT_MANIFEST_MAGIC = 0x4753454D414E3130  # GSEMAN10
WAL_MAGIC = 0x47534557414C3130  # GSEWAL10
BACKUP_MAGIC = 0x475345424B503130  # GSEBKP10
FORMAT_MAJOR = 1
FORMAT_MINOR = 1
PROFILE_DOMAIN = b"gse-durable-format-profile-v1\x00"
BACKUP_DOMAIN = b"gse-backup-content-v2\x00"
PROFILE_CAPABILITIES = (
    "canonical-documents-v1",
    "checkpoint-authority-v1",
    "crc32c-wal-v1",
    "logical-index-config-v1",
    "sha256-profile-binding-v1",
)
LIVE_FIXED_MEMBERS = ("gse-metadata", "gse-checkpoint-manifest")
BACKUP_MEMBERS = (
    "gse-backup-checkpoint",
    "gse-backup-manifest",
    "gse-backup-metadata",
)
BACKUP_PAYLOAD_ORDER = ("gse-backup-checkpoint", "gse-backup-metadata")
CHECKPOINT_NAME = (
    "gse-checkpoint-00000000000000000007-"
    "00112233445566778899aabbccddeeff.chk"
)
WAL_NAME = "gse-wal-00000000000000000002.log"
CAPABILITY = re.compile(r"[a-z0-9][a-z0-9-]{0,127}")


class StorageFormatError(ValueError):
    """Exact V4.2 format bytes violate the frozen Phase 2 contract."""


def crc32c(data: bytes) -> int:
    checksum = 0xFFFFFFFF
    for value in data:
        checksum ^= value
        for _ in range(8):
            checksum = ((checksum >> 1) ^ 0x82F63B78) \
                if checksum & 1 else checksum >> 1
    return checksum ^ 0xFFFFFFFF


def checked(content: bytes) -> bytes:
    return content + struct.pack(">I", crc32c(content))


def lp(value: str) -> bytes:
    encoded = value.encode("utf-8", errors="strict")
    return struct.pack(">I", len(encoded)) + encoded


def profile_bytes(
        required: tuple[str, ...] = PROFILE_CAPABILITIES,
        optional: tuple[str, ...] = (),
) -> bytes:
    return b"".join((
        struct.pack(">I", len(required)),
        *(lp(value) for value in required),
        struct.pack(">I", len(optional)),
        *(lp(value) for value in optional),
    ))


def profile_digest(profile: bytes | None = None) -> bytes:
    return hashlib.sha256(PROFILE_DOMAIN + (profile or profile_bytes())).digest()


class Cursor:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def take(self, size: int) -> bytes:
        if size < 0 or self.offset + size > len(self.data):
            raise StorageFormatError("bounded field is truncated")
        value = self.data[self.offset:self.offset + size]
        self.offset += size
        return value

    def unpack(self, shape: str) -> tuple[object, ...]:
        return struct.unpack(shape, self.take(struct.calcsize(shape)))

    def string(self, maximum: int, allow_empty: bool = False) -> str:
        (length,) = self.unpack(">I")
        if length > maximum or (length == 0 and not allow_empty):
            raise StorageFormatError("string length is outside its bound")
        try:
            return self.take(length).decode("utf-8", errors="strict")
        except UnicodeError as failure:
            raise StorageFormatError("string is not strict UTF-8") from failure

    def finish(self) -> None:
        if self.offset != len(self.data):
            raise StorageFormatError("member has trailing bytes")


@dataclass(frozen=True)
class Fixture:
    live: dict[str, bytes]
    backup: dict[str, bytes]
    profile_sha256: str
    backup_identity: str


def fixture() -> Fixture:
    most = 0x0011223344556677
    least = 0x8899AABBCCDDEEFF
    profile = profile_bytes()
    profile_sha = profile_digest(profile)
    metadata = checked(b"".join((
        struct.pack(">QhhQQ", METADATA_MAGIC, 1, 1, most, least),
        lp("gse-durable"),
        struct.pack(">I", len(profile)), profile, profile_sha,
        lp("v42-fixture-store"),
        lp("v42-fixture-schema"),
        lp("v42-fixture-codec"),
        struct.pack(">iiiiiqqi", 1, 1024, 4096, 1000, 10000,
                    1_048_576, 67_108_864, 0),
    )))
    key = b"doc-1"
    document = b"fixture-value"
    checkpoint = checked(b"".join((
        struct.pack(">QhhQQ", CHECKPOINT_MAGIC, 1, 1, most, least),
        profile_sha,
        struct.pack(">qiii", 7, 1, 1, 0),
        struct.pack(">iB", 1, 1),
        struct.pack(">i", len(key)), key,
        struct.pack(">i", len(document)), document,
    )))
    checkpoint_crc = struct.unpack(">I", checkpoint[-4:])[0]
    checkpoint_manifest = checked(b"".join((
        struct.pack(">QhhQQ", CHECKPOINT_MANIFEST_MAGIC, 1, 1, most, least),
        profile_sha,
        struct.pack(">qqI", 7, len(checkpoint), checkpoint_crc),
        lp(CHECKPOINT_NAME),
        struct.pack(">qq", 2, 8),
    )))
    wal_content = b"".join((
        struct.pack(">QhhQQ", WAL_MAGIC, 1, 1, most, least),
        profile_sha,
        struct.pack(">qq", 2, 8),
    ))
    wal = checked(wal_content)
    live = {
        "gse.lock": b"",
        "gse-metadata": metadata,
        CHECKPOINT_NAME: checkpoint,
        "gse-checkpoint-manifest": checkpoint_manifest,
        WAL_NAME: wal,
    }
    payloads = {
        "gse-backup-checkpoint": checkpoint,
        "gse-backup-metadata": metadata,
    }
    fields: dict[str, object] = {
        "historyMost": most,
        "historyLeast": least,
        "sequence": 7,
        "storageIdentity": "v42-fixture-store",
        "schemaIdentity": "v42-fixture-schema",
        "codecIdentity": "v42-fixture-codec",
        "codecVersion": 1,
    }
    content_digest = hashlib.sha256(
        backup_preimage(fields, payloads, profile_sha)
    ).digest()
    manifest = checked(b"".join((
        struct.pack(">Qhh", BACKUP_MAGIC, 1, 1),
        lp("gse-backup"), lp("gse-durable"), struct.pack(">hh", 1, 1),
        profile_sha,
        struct.pack(">QQq", most, least, 7),
        lp(str(fields["storageIdentity"])),
        lp(str(fields["schemaIdentity"])),
        lp(str(fields["codecIdentity"])),
        struct.pack(">iI", 1, len(BACKUP_PAYLOAD_ORDER)),
        *(
            lp(name) + struct.pack(">Q", len(payloads[name]))
            + hashlib.sha256(payloads[name]).digest()
            for name in BACKUP_PAYLOAD_ORDER
        ),
        content_digest,
        struct.pack(">q", 0),
        lp("phase2-fixture"),
    )))
    backup = dict(payloads)
    backup["gse-backup-manifest"] = manifest
    return Fixture(
        live, backup, profile_sha.hex(),
        "gse-backup-v2-" + content_digest.hex())


def backup_preimage(
        fields: dict[str, object],
        payloads: dict[str, bytes],
        profile_sha: bytes,
) -> bytes:
    return b"".join((
        BACKUP_DOMAIN,
        lp("gse-backup"), struct.pack(">hh", 1, 1),
        lp("gse-durable"), struct.pack(">hh", 1, 1), profile_sha,
        struct.pack(">QQq", int(fields["historyMost"]),
                    int(fields["historyLeast"]), int(fields["sequence"])),
        lp(str(fields["storageIdentity"])), lp(str(fields["schemaIdentity"])),
        lp(str(fields["codecIdentity"])),
        struct.pack(">iI", int(fields["codecVersion"]), len(payloads)),
        *(
            lp(name) + struct.pack(">Q", len(payloads[name]))
            + hashlib.sha256(payloads[name]).digest()
            for name in sorted(payloads, key=lambda item: item.encode("utf-8"))
        ),
    ))


def uncheck(data: bytes, minimum: int, name: str) -> Cursor:
    if len(data) < minimum:
        raise StorageFormatError(f"{name} is shorter than its fixed header")
    stored, = struct.unpack(">I", data[-4:])
    if crc32c(data[:-4]) != stored:
        raise StorageFormatError(f"{name} CRC32C mismatch")
    return Cursor(data[:-4])


def read_profile(cursor: Cursor) -> bytes:
    length, = cursor.unpack(">I")
    if length < 12 or length > 4096:
        raise StorageFormatError("profile length is outside its bound")
    encoded = cursor.take(length)
    observed = cursor.take(32)
    if observed != profile_digest(encoded):
        raise StorageFormatError("profile digest mismatch")
    profile_cursor = Cursor(encoded)
    required = read_capabilities(profile_cursor)
    optional = read_capabilities(profile_cursor)
    profile_cursor.finish()
    if required != PROFILE_CAPABILITIES or optional:
        raise StorageFormatError("profile capabilities are incompatible")
    return observed


def read_capabilities(cursor: Cursor) -> tuple[str, ...]:
    count, = cursor.unpack(">I")
    if count > 64:
        raise StorageFormatError("profile capability count exceeds its bound")
    result = tuple(cursor.string(128) for _ in range(count))
    if any(not CAPABILITY.fullmatch(value) for value in result) \
            or tuple(sorted(set(result))) != result:
        raise StorageFormatError("profile capabilities are not canonical")
    return result


def parse_metadata(data: bytes) -> dict[str, object]:
    cursor = uncheck(data, 64, "metadata")
    magic, major, minor, most, least = cursor.unpack(">QhhQQ")
    family = cursor.string(128)
    if (magic, major, minor, family) != (METADATA_MAGIC, 1, 1, "gse-durable"):
        raise StorageFormatError("metadata format is unsupported")
    profile_sha = read_profile(cursor)
    storage = cursor.string(128)
    schema = cursor.string(128)
    codec = cursor.string(128)
    codec_version, max_key, max_document, max_bulk, max_documents, \
        checkpoint_wal, max_retained, index_count = cursor.unpack(">iiiiiqqi")
    if codec_version < 0 or min(max_key, max_document, max_bulk, max_documents,
                                checkpoint_wal, max_retained) <= 0 \
            or max_retained <= checkpoint_wal or index_count > 100_000:
        raise StorageFormatError("metadata bounds are invalid")
    indexes = []
    for _ in range(index_count):
        kind, = cursor.unpack(">B")
        indexes.append((kind, cursor.string(1024), cursor.string(128, True)))
    cursor.finish()
    return {
        "history": (most, least), "profileDigest": profile_sha,
        "storageIdentity": storage, "schemaIdentity": schema,
        "codecIdentity": codec, "codecVersion": codec_version,
        "maxKey": max_key, "maxDocument": max_document,
        "maxBulk": max_bulk, "maxDocuments": max_documents,
        "maxRetained": max_retained, "indexes": indexes,
    }


def parse_checkpoint(data: bytes, metadata: dict[str, object]) -> dict[str, object]:
    cursor = uncheck(data, 88, "checkpoint")
    magic, major, minor, most, least = cursor.unpack(">QhhQQ")
    binding = cursor.take(32)
    sequence, next_doc_id, live_documents, index_count = cursor.unpack(">qiii")
    if (magic, major, minor) != (CHECKPOINT_MAGIC, 1, 1) \
            or (most, least) != metadata["history"] \
            or binding != metadata["profileDigest"]:
        raise StorageFormatError("checkpoint authority is invalid")
    indexes = []
    for _ in range(index_count):
        kind, = cursor.unpack(">B")
        indexes.append((kind, cursor.string(1024), cursor.string(128, True)))
    slots, = cursor.unpack(">i")
    decoded = 0
    for _ in range(slots):
        state, = cursor.unpack(">B")
        if state == 0:
            continue
        if state != 1:
            raise StorageFormatError("checkpoint slot state is invalid")
        key_length, = cursor.unpack(">i")
        cursor.take(key_length)
        document_length, = cursor.unpack(">i")
        cursor.take(document_length)
        decoded += 1
    cursor.finish()
    if sequence < 0 or next_doc_id != slots or decoded != live_documents \
            or indexes != metadata["indexes"]:
        raise StorageFormatError("checkpoint counts or indexes are invalid")
    return {"sequence": sequence, "bytes": len(data),
            "checksum": struct.unpack(">I", data[-4:])[0]}


def parse_checkpoint_manifest(
        data: bytes, metadata: dict[str, object]
) -> dict[str, object]:
    cursor = uncheck(data, 104, "checkpoint manifest")
    magic, major, minor, most, least = cursor.unpack(">QhhQQ")
    binding = cursor.take(32)
    sequence, checkpoint_bytes, checkpoint_crc = cursor.unpack(">qqI")
    checkpoint_name = cursor.string(256)
    generation, first_sequence = cursor.unpack(">qq")
    cursor.finish()
    if (magic, major, minor) != (CHECKPOINT_MANIFEST_MAGIC, 1, 1) \
            or (most, least) != metadata["history"] \
            or binding != metadata["profileDigest"] \
            or first_sequence != sequence + 1:
        raise StorageFormatError("checkpoint manifest authority is invalid")
    return {"sequence": sequence, "checkpointBytes": checkpoint_bytes,
            "checkpointChecksum": checkpoint_crc,
            "checkpointName": checkpoint_name, "generation": generation,
            "firstSequence": first_sequence}


def parse_wal(data: bytes, metadata: dict[str, object]) -> dict[str, object]:
    cursor = uncheck(data, 80, "WAL")
    magic, major, minor, most, least = cursor.unpack(">QhhQQ")
    binding = cursor.take(32)
    generation, first_sequence = cursor.unpack(">qq")
    cursor.finish()
    if (magic, major, minor) != (WAL_MAGIC, 1, 1) \
            or (most, least) != metadata["history"] \
            or binding != metadata["profileDigest"] \
            or generation <= 0 or first_sequence <= 0:
        raise StorageFormatError("WAL generation authority is invalid")
    return {"generation": generation, "firstSequence": first_sequence}


def inspect_store(directory: Path) -> dict[str, object]:
    names = {path.name for path in directory.iterdir()}
    expected = {"gse.lock", "gse-metadata", "gse-checkpoint-manifest",
                CHECKPOINT_NAME, WAL_NAME}
    if names != expected or (directory / "gse.lock").read_bytes():
        raise StorageFormatError("live inventory is not the exact fixture inventory")
    metadata_bytes = (directory / "gse-metadata").read_bytes()
    metadata = parse_metadata(metadata_bytes)
    checkpoint_bytes = (directory / CHECKPOINT_NAME).read_bytes()
    checkpoint = parse_checkpoint(checkpoint_bytes, metadata)
    manifest = parse_checkpoint_manifest(
        (directory / "gse-checkpoint-manifest").read_bytes(), metadata)
    wal = parse_wal((directory / WAL_NAME).read_bytes(), metadata)
    if manifest["checkpointName"] != CHECKPOINT_NAME \
            or manifest["checkpointBytes"] != len(checkpoint_bytes) \
            or manifest["checkpointChecksum"] != checkpoint["checksum"] \
            or manifest["sequence"] != checkpoint["sequence"] \
            or manifest["generation"] != wal["generation"] \
            or manifest["firstSequence"] != wal["firstSequence"]:
        raise StorageFormatError("live authority members disagree")
    return {"status": "VALID", "format": "gse-durable/1.1",
            "sequence": checkpoint["sequence"],
            "profileDigest": bytes(metadata["profileDigest"]).hex()}


def parse_backup_manifest(data: bytes) -> dict[str, object]:
    cursor = uncheck(data, 160, "backup manifest")
    magic, major, minor = cursor.unpack(">Qhh")
    family = cursor.string(128)
    source_family = cursor.string(128)
    source_major, source_minor = cursor.unpack(">hh")
    binding = cursor.take(32)
    most, least, sequence = cursor.unpack(">QQq")
    storage = cursor.string(128)
    schema = cursor.string(128)
    codec = cursor.string(128)
    codec_version, count = cursor.unpack(">iI")
    if (magic, major, minor, family) != (BACKUP_MAGIC, 1, 1, "gse-backup") \
            or (source_family, source_major, source_minor) \
            != ("gse-durable", 1, 1) \
            or binding != profile_digest() or count != 2:
        raise StorageFormatError("backup format authority is invalid")
    payloads: dict[str, dict[str, object]] = {}
    order = []
    for _ in range(count):
        name = cursor.string(128)
        size, = cursor.unpack(">Q")
        digest = cursor.take(32)
        if name in payloads:
            raise StorageFormatError("duplicate backup payload")
        order.append(name)
        payloads[name] = {"size": size, "sha256": digest}
    content_digest = cursor.take(32)
    created, = cursor.unpack(">q")
    request = cursor.string(256, True)
    cursor.finish()
    if tuple(order) != BACKUP_PAYLOAD_ORDER or sequence < 0 \
            or codec_version < 0 or created < 0:
        raise StorageFormatError("backup canonical fields are invalid")
    return {"history": (most, least), "sequence": sequence,
            "profileDigest": binding, "storageIdentity": storage,
            "schemaIdentity": schema, "codecIdentity": codec,
            "codecVersion": codec_version, "payloads": payloads,
            "contentDigest": content_digest, "requestId": request}


def inspect_backup(directory: Path) -> dict[str, object]:
    if {path.name for path in directory.iterdir()} != set(BACKUP_MEMBERS):
        raise StorageFormatError("backup inventory is not canonical")
    values = {name: (directory / name).read_bytes() for name in BACKUP_MEMBERS}
    manifest = parse_backup_manifest(values["gse-backup-manifest"])
    metadata = parse_metadata(values["gse-backup-metadata"])
    checkpoint = parse_checkpoint(values["gse-backup-checkpoint"], metadata)
    for name in BACKUP_PAYLOAD_ORDER:
        descriptor = manifest["payloads"][name]
        if descriptor["size"] != len(values[name]) \
                or descriptor["sha256"] != hashlib.sha256(values[name]).digest():
            raise StorageFormatError("backup payload integrity mismatch")
    fields = {
        "historyMost": manifest["history"][0],
        "historyLeast": manifest["history"][1],
        "sequence": manifest["sequence"],
        "storageIdentity": manifest["storageIdentity"],
        "schemaIdentity": manifest["schemaIdentity"],
        "codecIdentity": manifest["codecIdentity"],
        "codecVersion": manifest["codecVersion"],
    }
    expected = hashlib.sha256(backup_preimage(
        fields,
        {name: values[name] for name in BACKUP_PAYLOAD_ORDER},
        bytes(manifest["profileDigest"]),
    )).digest()
    if manifest["history"] != metadata["history"] \
            or manifest["profileDigest"] != metadata["profileDigest"] \
            or manifest["sequence"] != checkpoint["sequence"] \
            or manifest["contentDigest"] != expected:
        raise StorageFormatError("backup members or content identity disagree")
    return {"status": "VALID", "format": "gse-backup/1.1",
            "sourceFormat": "gse-durable/1.1",
            "sequence": manifest["sequence"],
            "profileDigest": bytes(manifest["profileDigest"]).hex(),
            "contentIdentity": "gse-backup-v2-" + expected.hex()}


def load_hex_fixture(root: Path) -> Fixture:
    live: dict[str, bytes] = {"gse.lock": b""}
    backup: dict[str, bytes] = {}
    for line in (root / "fixture-inventory.tsv").read_text(
            encoding="ascii").splitlines():
        if not line or line.startswith("#"):
            continue
        kind, name, sha256, hex_name = line.split("\t")
        value = bytes.fromhex((root / hex_name).read_text(encoding="ascii"))
        if hashlib.sha256(value).hexdigest() != sha256:
            raise StorageFormatError(f"fixture checksum mismatch: {name}")
        (live if kind == "live" else backup)[name] = value
    identities = (root / "fixture-identities.properties").read_text(
        encoding="ascii").splitlines()
    properties = dict(line.split("=", 1) for line in identities if line)
    return Fixture(live, backup, properties["profileDigest"],
                   properties["backupIdentity"])


def emit() -> None:
    value = fixture()
    for kind, members in (("live", value.live), ("backup", value.backup)):
        for name, data in members.items():
            if name == "gse.lock":
                continue
            print(f"{kind}\t{name}\t{hashlib.sha256(data).hexdigest()}\t"
                  f"{kind}-{name}.hex")
            print(f"HEX {kind}-{name}.hex {data.hex()}")
    print(f"profileDigest={value.profile_sha256}")
    print(f"backupIdentity={value.backup_identity}")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("emit")
    store = subparsers.add_parser("inspect-store")
    store.add_argument("directory", type=Path)
    backup = subparsers.add_parser("inspect-backup")
    backup.add_argument("directory", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "emit":
        emit()
    elif arguments.command == "inspect-store":
        print(inspect_store(arguments.directory))
    else:
        print(inspect_backup(arguments.directory))


if __name__ == "__main__":
    main()
