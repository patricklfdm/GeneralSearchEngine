#!/usr/bin/env python3
"""Independent exact (1,2) live/backup/derived encoder and parser."""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
from dataclasses import dataclass
from pathlib import Path

METADATA_MAGIC = 0x4753454D45544131
CHECKPOINT_MAGIC = 0x47534543484B3130
CHECKPOINT_MANIFEST_MAGIC = 0x4753454D414E3130
WAL_MAGIC = 0x47534557414C3130
BACKUP_MAGIC = 0x475345424B503130
CATALOG_MAGIC = 0x4753454443415431
COMPONENT_MAGIC = 0x4753454449445831
FORMAT_MAJOR = 1
FORMAT_MINOR = 2
PROFILE_DOMAIN = b"gse-durable-format-profile-v1\x00"
BACKUP_DOMAIN = b"gse-backup-content-v3\x00"
CATALOG_DOMAIN = b"gse-derived-catalog-content-v1\x00"
COMPONENT_DOMAIN = b"gse-derived-component-content-v1\x00"
GENERATOR = "gse-derived-generator-v1"
GENERATOR_VERSION = 1
CAPABILITIES = (
    "canonical-documents-v1",
    "checkpoint-authority-v1",
    "crc32c-wal-v1",
    "logical-index-config-v1",
    "reconstructible-derived-index-images-v1",
    "sha256-profile-binding-v1",
)
DESCRIPTORS = (
    (1, "category", ""),
    (2, "price", ""),
    (3, "title", ""),
    (4, "body", "gse-simple-v1"),
)
CHECKPOINT_NAME = (
    "gse-checkpoint-00000000000000000007-"
    "00112233445566778899aabbccddeeff.chk"
)
WAL_NAME = "gse-wal-00000000000000000002.log"
GENERATION = "0123456789abcdeffedcba9876543210"
COMPONENT_RE = re.compile(
    r"gse-derived-index-([0-9]{20})-([0-9]{5})-([a-f0-9]{32})\.idx"
)
MAX_COMPONENTS = 100_000
MAX_STRING = 1024 * 1024


class DerivedFormatError(ValueError):
    """Exact V4.3 derived bytes violate the frozen Phase 2 contract."""


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


def profile_bytes() -> bytes:
    return b"".join((
        struct.pack(">I", len(CAPABILITIES)),
        *(lp(value) for value in CAPABILITIES),
        struct.pack(">I", 0),
    ))


def profile_digest() -> bytes:
    return hashlib.sha256(PROFILE_DOMAIN + profile_bytes()).digest()


class Cursor:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def take(self, size: int) -> bytes:
        if size < 0 or self.offset + size > len(self.data):
            raise DerivedFormatError("bounded field is truncated")
        value = self.data[self.offset:self.offset + size]
        self.offset += size
        return value

    def unpack(self, shape: str) -> tuple[object, ...]:
        return struct.unpack(shape, self.take(struct.calcsize(shape)))

    def string(self, maximum: int, allow_empty: bool = False) -> str:
        length, = self.unpack(">I")
        if length > maximum or (length == 0 and not allow_empty):
            raise DerivedFormatError("string length is outside its bound")
        try:
            return self.take(length).decode("utf-8", errors="strict")
        except UnicodeError as failure:
            raise DerivedFormatError("string is not strict UTF-8") from failure

    def finish(self) -> None:
        if self.offset != len(self.data):
            raise DerivedFormatError("member has trailing bytes")


def uncheck(data: bytes, minimum: int, member: str) -> Cursor:
    if len(data) < minimum:
        raise DerivedFormatError(f"{member} is truncated")
    stored, = struct.unpack(">I", data[-4:])
    if crc32c(data[:-4]) != stored:
        raise DerivedFormatError(f"{member} CRC32C mismatch")
    return Cursor(data[:-4])


@dataclass(frozen=True)
class Fixture:
    live: dict[str, bytes]
    backup: dict[str, bytes]
    profile_sha256: str
    catalog_identity: str
    backup_identity: str


def _component_payload(kind: int) -> bytes:
    if kind in (1, 2, 3):
        return struct.pack(">I", 0)
    return struct.pack(">IqII", 0, 0, 0, 0)


def _component(
        ordinal: int,
        descriptor: tuple[int, str, str],
        checkpoint_sha: bytes,
) -> bytes:
    kind, name, analyzer = descriptor
    content = b"".join((
        struct.pack(">Qhhhh", COMPONENT_MAGIC, 1, 0, 1, 2),
        profile_digest(),
        struct.pack(">QQq", 0x0011223344556677,
                    0x8899AABBCCDDEEFF, 7),
        checkpoint_sha,
        lp("v43-fixture-store"), lp("v43-fixture-schema"),
        lp("v43-fixture-codec"), struct.pack(">i", 1),
        lp(GENERATOR), struct.pack(">iiB", GENERATOR_VERSION, ordinal, kind),
        lp(name), lp(analyzer), struct.pack(">ii", 0, 0),
        _component_payload(kind),
    ))
    identity = hashlib.sha256(COMPONENT_DOMAIN + content).digest()
    return checked(content + identity)


def _backup_preimage(
        payloads: dict[str, bytes], profile_sha: bytes
) -> bytes:
    return b"".join((
        BACKUP_DOMAIN,
        lp("gse-backup"), struct.pack(">hh", 1, 2),
        lp("gse-durable"), struct.pack(">hh", 1, 2), profile_sha,
        struct.pack(">QQq", 0x0011223344556677,
                    0x8899AABBCCDDEEFF, 7),
        lp("v43-fixture-store"), lp("v43-fixture-schema"),
        lp("v43-fixture-codec"), struct.pack(">iI", 1, len(payloads)),
        *(
            lp(name) + struct.pack(">Q", len(payloads[name]))
            + hashlib.sha256(payloads[name]).digest()
            for name in sorted(payloads)
        ),
    ))


def fixture() -> Fixture:
    most = 0x0011223344556677
    least = 0x8899AABBCCDDEEFF
    profile = profile_bytes()
    profile_sha = profile_digest()
    descriptors = b"".join(
        struct.pack(">B", kind) + lp(name) + lp(analyzer)
        for kind, name, analyzer in DESCRIPTORS
    )
    metadata = checked(b"".join((
        struct.pack(">QhhQQ", METADATA_MAGIC, 1, 2, most, least),
        lp("gse-durable"), struct.pack(">I", len(profile)), profile,
        profile_sha,
        lp("v43-fixture-store"), lp("v43-fixture-schema"),
        lp("v43-fixture-codec"),
        struct.pack(">iiiiiqqqi", 1, 1024, 4096, 1000, 10000,
                    1_048_576, 67_108_864, 33_554_432, len(DESCRIPTORS)),
        descriptors,
    )))
    checkpoint = checked(b"".join((
        struct.pack(">QhhQQ", CHECKPOINT_MAGIC, 1, 2, most, least),
        profile_sha, struct.pack(">qiii", 7, 0, 0, len(DESCRIPTORS)),
        descriptors, struct.pack(">i", 0),
    )))
    checkpoint_crc, = struct.unpack(">I", checkpoint[-4:])
    checkpoint_sha = hashlib.sha256(checkpoint).digest()
    manifest = checked(b"".join((
        struct.pack(">QhhQQ", CHECKPOINT_MANIFEST_MAGIC, 1, 2, most, least),
        profile_sha, struct.pack(">qqI", 7, len(checkpoint), checkpoint_crc),
        lp(CHECKPOINT_NAME), struct.pack(">qq", 2, 8),
    )))
    wal = checked(b"".join((
        struct.pack(">QhhQQ", WAL_MAGIC, 1, 2, most, least),
        profile_sha, struct.pack(">qq", 2, 8),
    )))

    components: dict[str, bytes] = {}
    entries: list[bytes] = []
    for ordinal, descriptor in enumerate(DESCRIPTORS):
        name = (f"gse-derived-index-{7:020d}-{ordinal:05d}-"
                f"{GENERATION}.idx")
        data = _component(ordinal, descriptor, checkpoint_sha)
        components[name] = data
        kind, field_name, analyzer = descriptor
        checksum, = struct.unpack(">I", data[-4:])
        entries.append(b"".join((
            struct.pack(">iB", ordinal, kind), lp(field_name), lp(analyzer),
            lp(name), struct.pack(">QI", len(data), checksum),
            hashlib.sha256(data).digest(),
        )))
    catalog_content = b"".join((
        struct.pack(">Qhhhh", CATALOG_MAGIC, 1, 0, 1, 2), profile_sha,
        struct.pack(">QQq", most, least, 7), lp(CHECKPOINT_NAME),
        struct.pack(">qI", len(checkpoint), checkpoint_crc), checkpoint_sha,
        lp("v43-fixture-store"), lp("v43-fixture-schema"),
        lp("v43-fixture-codec"), struct.pack(">i", 1),
        lp(GENERATOR), struct.pack(">iiii", GENERATOR_VERSION, 0, 0,
                                   len(DESCRIPTORS)),
        *entries,
    ))
    catalog_digest = hashlib.sha256(CATALOG_DOMAIN + catalog_content).digest()
    catalog = checked(catalog_content + catalog_digest)
    live = {
        "gse.lock": b"", "gse-metadata": metadata,
        CHECKPOINT_NAME: checkpoint, "gse-checkpoint-manifest": manifest,
        WAL_NAME: wal, **components, "gse-derived-manifest": catalog,
    }

    payloads = {
        "gse-backup-checkpoint": checkpoint,
        "gse-backup-metadata": metadata,
    }
    backup_digest = hashlib.sha256(
        _backup_preimage(payloads, profile_sha)).digest()
    backup_manifest = checked(b"".join((
        struct.pack(">Qhh", BACKUP_MAGIC, 1, 2),
        lp("gse-backup"), lp("gse-durable"), struct.pack(">hh", 1, 2),
        profile_sha, struct.pack(">QQq", most, least, 7),
        lp("v43-fixture-store"), lp("v43-fixture-schema"),
        lp("v43-fixture-codec"), struct.pack(">iI", 1, 2),
        *(
            lp(name) + struct.pack(">Q", len(payloads[name]))
            + hashlib.sha256(payloads[name]).digest()
            for name in ("gse-backup-checkpoint", "gse-backup-metadata")
        ),
        backup_digest, struct.pack(">q", 0), lp("phase2-fixture"),
    )))
    backup = dict(payloads)
    backup["gse-backup-manifest"] = backup_manifest
    return Fixture(live, backup, profile_sha.hex(),
                   "gse-derived-catalog-v1-" + catalog_digest.hex(),
                   "gse-backup-v3-" + backup_digest.hex())


def _read_descriptors(cursor: Cursor, count: int) \
        -> tuple[tuple[int, str, str], ...]:
    if count > MAX_COMPONENTS:
        raise DerivedFormatError("descriptor count exceeds its bound")
    return tuple((cursor.unpack(">B")[0], cursor.string(1024),
                  cursor.string(128, True)) for _ in range(count))


def parse_metadata(data: bytes) -> dict[str, object]:
    cursor = uncheck(data, 64, "metadata")
    magic, major, minor, most, least = cursor.unpack(">QhhQQ")
    family = cursor.string(128)
    length, = cursor.unpack(">I")
    profile = cursor.take(length)
    digest = cursor.take(32)
    if (magic, major, minor, family) != (METADATA_MAGIC, 1, 2, "gse-durable") \
            or profile != profile_bytes() or digest != profile_digest():
        raise DerivedFormatError("metadata format profile differs")
    storage = cursor.string(128)
    schema = cursor.string(128)
    codec = cursor.string(128)
    values = cursor.unpack(">iiiiiqqqi")
    codec_version, max_key, max_document, max_bulk, max_documents, \
        checkpoint_wal, retained, derived, count = values
    descriptors = _read_descriptors(cursor, count)
    cursor.finish()
    if min(codec_version + 1, max_key, max_document, max_bulk, max_documents,
           checkpoint_wal, retained, derived) <= 0 \
            or derived > retained or descriptors != DESCRIPTORS:
        raise DerivedFormatError("metadata bounds or descriptors differ")
    return {"history": (most, least), "profile": digest, "storage": storage,
            "schema": schema, "codec": codec, "codecVersion": codec_version,
            "descriptors": descriptors}


def parse_checkpoint(data: bytes, metadata: dict[str, object]) -> dict[str, object]:
    cursor = uncheck(data, 88, "checkpoint")
    magic, major, minor, most, least = cursor.unpack(">QhhQQ")
    binding = cursor.take(32)
    sequence, next_doc, live, count = cursor.unpack(">qiii")
    descriptors = _read_descriptors(cursor, count)
    slots, = cursor.unpack(">i")
    cursor.finish()
    if (magic, major, minor) != (CHECKPOINT_MAGIC, 1, 2) \
            or (most, least) != metadata["history"] \
            or binding != metadata["profile"] or sequence != 7 \
            or (next_doc, live, slots) != (0, 0, 0) \
            or descriptors != metadata["descriptors"]:
        raise DerivedFormatError("checkpoint authority differs")
    return {"sequence": sequence, "nextDocId": next_doc,
            "liveDocuments": live, "sha256": hashlib.sha256(data).digest(),
            "bytes": len(data), "crc": struct.unpack(">I", data[-4:])[0]}


def parse_component(
        data: bytes, metadata: dict[str, object], checkpoint: dict[str, object],
        ordinal: int,
) -> dict[str, object]:
    cursor = uncheck(data, 192, "component")
    content = data[:-36]
    magic, encoding_major, encoding_minor, live_major, live_minor = \
        cursor.unpack(">Qhhhh")
    binding = cursor.take(32)
    most, least, sequence = cursor.unpack(">QQq")
    checkpoint_sha = cursor.take(32)
    storage, schema, codec = cursor.string(128), cursor.string(128), \
        cursor.string(128)
    codec_version, = cursor.unpack(">i")
    generator = cursor.string(128)
    generator_version, observed_ordinal, kind = cursor.unpack(">iiB")
    name, analyzer = cursor.string(MAX_STRING), cursor.string(128, True)
    next_doc, live = cursor.unpack(">ii")
    if kind in (1, 2, 3):
        count, = cursor.unpack(">I")
        if count != 0:
            raise DerivedFormatError("fixture component is not empty")
    elif kind == 4:
        if cursor.unpack(">IqII") != (0, 0, 0, 0):
            raise DerivedFormatError("fixture text component is not empty")
    else:
        raise DerivedFormatError("component kind is unsupported")
    identity = cursor.take(32)
    cursor.finish()
    expected = metadata["descriptors"][ordinal]
    if (magic, encoding_major, encoding_minor, live_major, live_minor) \
            != (COMPONENT_MAGIC, 1, 0, 1, 2) \
            or binding != metadata["profile"] \
            or (most, least) != metadata["history"] or sequence != 7 \
            or checkpoint_sha != checkpoint["sha256"] \
            or (storage, schema, codec, codec_version) != (
                metadata["storage"], metadata["schema"], metadata["codec"],
                metadata["codecVersion"]) \
            or (generator, generator_version) != (GENERATOR, 1) \
            or observed_ordinal != ordinal or (kind, name, analyzer) != expected \
            or (next_doc, live) != (0, 0) \
            or identity != hashlib.sha256(COMPONENT_DOMAIN + content).digest():
        raise DerivedFormatError("component binding differs")
    return {"ordinal": ordinal, "kind": kind, "name": name,
            "analyzer": analyzer, "bytes": len(data),
            "crc": struct.unpack(">I", data[-4:])[0],
            "sha256": hashlib.sha256(data).digest()}


def parse_catalog(
        data: bytes, metadata: dict[str, object], checkpoint: dict[str, object],
        components: dict[str, bytes],
) -> dict[str, object]:
    cursor = uncheck(data, 256, "catalog")
    content = data[:-36]
    magic, encoding_major, encoding_minor, live_major, live_minor = \
        cursor.unpack(">Qhhhh")
    binding = cursor.take(32)
    most, least, sequence = cursor.unpack(">QQq")
    checkpoint_name = cursor.string(256)
    checkpoint_bytes, checkpoint_crc = cursor.unpack(">qI")
    checkpoint_sha = cursor.take(32)
    storage, schema, codec = cursor.string(128), cursor.string(128), \
        cursor.string(128)
    codec_version, = cursor.unpack(">i")
    generator = cursor.string(128)
    generator_version, next_doc, live, count = cursor.unpack(">iiii")
    if count != len(DESCRIPTORS):
        raise DerivedFormatError("catalog component count differs")
    entries = []
    for expected_ordinal in range(count):
        ordinal, kind = cursor.unpack(">iB")
        name, analyzer, filename = cursor.string(MAX_STRING), \
            cursor.string(128, True), cursor.string(256)
        size, checksum = cursor.unpack(">QI")
        sha = cursor.take(32)
        if ordinal != expected_ordinal or not COMPONENT_RE.fullmatch(filename):
            raise DerivedFormatError("catalog entry order or filename differs")
        component = parse_component(components[filename], metadata, checkpoint,
                                    ordinal)
        if (kind, name, analyzer) != metadata["descriptors"][ordinal] \
                or (size, checksum, sha) != (
                    component["bytes"], component["crc"], component["sha256"]):
            raise DerivedFormatError("catalog component binding differs")
        entries.append(component)
    identity = cursor.take(32)
    cursor.finish()
    if (magic, encoding_major, encoding_minor, live_major, live_minor) \
            != (CATALOG_MAGIC, 1, 0, 1, 2) \
            or binding != metadata["profile"] \
            or (most, least) != metadata["history"] or sequence != 7 \
            or checkpoint_name != CHECKPOINT_NAME \
            or (checkpoint_bytes, checkpoint_crc, checkpoint_sha) != (
                checkpoint["bytes"], checkpoint["crc"], checkpoint["sha256"]) \
            or (storage, schema, codec, codec_version) != (
                metadata["storage"], metadata["schema"], metadata["codec"],
                metadata["codecVersion"]) \
            or (generator, generator_version, next_doc, live) \
            != (GENERATOR, 1, 0, 0) \
            or identity != hashlib.sha256(CATALOG_DOMAIN + content).digest():
        raise DerivedFormatError("catalog authority differs")
    return {"identity": "gse-derived-catalog-v1-" + identity.hex(),
            "components": entries}


def inspect_live(members: dict[str, bytes]) -> dict[str, object]:
    metadata = parse_metadata(members["gse-metadata"])
    checkpoint = parse_checkpoint(members[CHECKPOINT_NAME], metadata)
    derived = {name: value for name, value in members.items()
               if COMPONENT_RE.fullmatch(name)}
    catalog = parse_catalog(members["gse-derived-manifest"], metadata,
                            checkpoint, derived)
    if len(derived) != len(DESCRIPTORS):
        raise DerivedFormatError("derived inventory differs")
    return {"status": "VALID", "format": "gse-durable/1.2",
            "profileDigest": bytes(metadata["profile"]).hex(), **catalog}


def inspect_backup(members: dict[str, bytes]) -> dict[str, object]:
    if set(members) != {"gse-backup-checkpoint", "gse-backup-metadata",
                       "gse-backup-manifest"}:
        raise DerivedFormatError("backup inventory differs")
    metadata = parse_metadata(members["gse-backup-metadata"])
    checkpoint = parse_checkpoint(members["gse-backup-checkpoint"], metadata)
    cursor = uncheck(members["gse-backup-manifest"], 160, "backup manifest")
    magic, major, minor = cursor.unpack(">Qhh")
    family, source_family = cursor.string(128), cursor.string(128)
    source_major, source_minor = cursor.unpack(">hh")
    binding = cursor.take(32)
    most, least, sequence = cursor.unpack(">QQq")
    storage, schema, codec = cursor.string(128), cursor.string(128), \
        cursor.string(128)
    codec_version, count = cursor.unpack(">iI")
    names = []
    for _ in range(count):
        name = cursor.string(128)
        size, = cursor.unpack(">Q")
        sha = cursor.take(32)
        if name not in members or len(members[name]) != size \
                or hashlib.sha256(members[name]).digest() != sha:
            raise DerivedFormatError("backup payload binding differs")
        names.append(name)
    identity = cursor.take(32)
    created, = cursor.unpack(">q")
    cursor.string(256, True)
    cursor.finish()
    payloads = {name: members[name] for name in names}
    if (magic, major, minor, family, source_family, source_major, source_minor) \
            != (BACKUP_MAGIC, 1, 2, "gse-backup", "gse-durable", 1, 2) \
            or binding != metadata["profile"] \
            or (most, least) != metadata["history"] or sequence != 7 \
            or (storage, schema, codec, codec_version) != (
                metadata["storage"], metadata["schema"], metadata["codec"],
                metadata["codecVersion"]) \
            or names != ["gse-backup-checkpoint", "gse-backup-metadata"] \
            or created < 0 or checkpoint["sequence"] != sequence \
            or identity != hashlib.sha256(
                _backup_preimage(payloads, bytes(binding))).digest():
        raise DerivedFormatError("backup authority differs")
    return {"status": "VALID", "format": "gse-backup/1.2",
            "contentIdentity": "gse-backup-v3-" + identity.hex()}


def load_hex_fixture(root: Path) -> Fixture:
    live: dict[str, bytes] = {"gse.lock": b""}
    backup: dict[str, bytes] = {}
    for line in (root / "fixture-inventory.tsv").read_text(
            encoding="ascii").splitlines():
        if not line or line.startswith("#"):
            continue
        kind, name, digest, filename = line.split("\t")
        data = bytes.fromhex((root / filename).read_text(encoding="ascii"))
        if hashlib.sha256(data).hexdigest() != digest:
            raise DerivedFormatError(f"fixture checksum mismatch: {name}")
        (live if kind == "live" else backup)[name] = data
    properties = dict(line.split("=", 1) for line in (
        root / "fixture-identities.properties").read_text(
            encoding="ascii").splitlines() if line)
    return Fixture(live, backup, properties["profileDigest"],
                   properties["catalogIdentity"], properties["backupIdentity"])


def emit() -> None:
    value = fixture()
    for kind, members in (("live", value.live), ("backup", value.backup)):
        for name, data in members.items():
            if name == "gse.lock":
                continue
            print(f"{kind}\t{name}\t{hashlib.sha256(data).hexdigest()}\t"
                  f"{kind}-{name}.hex")
            print(f"HEX\t{kind}-{name}.hex\t{data.hex()}")
    print(f"PROP\tprofileDigest\t{value.profile_sha256}")
    print(f"PROP\tcatalogIdentity\t{value.catalog_identity}")
    print(f"PROP\tbackupIdentity\t{value.backup_identity}")


def write_fixture(root: Path) -> None:
    value = fixture()
    root.mkdir(parents=True, exist_ok=True)
    inventory = []
    for kind, members in (("live", value.live), ("backup", value.backup)):
        for name, data in members.items():
            if name == "gse.lock":
                continue
            filename = f"{kind}-{name}.hex"
            (root / filename).write_text(data.hex() + "\n", encoding="ascii")
            inventory.append(
                f"{kind}\t{name}\t{hashlib.sha256(data).hexdigest()}\t{filename}")
    (root / "fixture-inventory.tsv").write_text(
        "# kind\tmember\tsha256\thex-file\n" + "\n".join(inventory) + "\n",
        encoding="ascii")
    (root / "fixture-identities.properties").write_text(
        f"profileDigest={value.profile_sha256}\n"
        f"catalogIdentity={value.catalog_identity}\n"
        f"backupIdentity={value.backup_identity}\n",
        encoding="ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("emit")
    write = sub.add_parser("write")
    write.add_argument("root", type=Path)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("root", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "emit":
        emit()
    elif arguments.command == "write":
        write_fixture(arguments.root)
    else:
        value = load_hex_fixture(arguments.root)
        live = inspect_live(value.live)
        backup = inspect_backup(value.backup)
        if live["profileDigest"] != value.profile_sha256 \
                or live["identity"] != value.catalog_identity \
                or backup["contentIdentity"] != value.backup_identity:
            raise DerivedFormatError("frozen identities differ")
        print("v43DerivedFormatV12=PASS components=4 backupMembers=3")


if __name__ == "__main__":
    main()
