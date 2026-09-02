#!/usr/bin/env python3
"""Independent Phase 1 storage inventory; production format parsing starts in Phase 2."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from scripts.v4.evidence import EvidenceError

RESERVED_PRODUCTION_PREFIXES = ("manifest", "checkpoint-", "wal-")
PHASE2_FILES = {
    "gse.lock",
    "gse-metadata",
    "gse-wal-00000000000000000001.log",
}
METADATA_MAGIC = 0x4753454D45544131
WAL_MAGIC = 0x47534557414C3130
FRAME_MAGIC = 0x47534546
WAL_HEADER_BYTES = 48
FRAME_HEADER_BYTES = 28
FRAME_TRAILER_BYTES = 4
MAX_FRAME_BYTES = 256 * 1024 * 1024
HARD_LIMITS = (
    64 * 1024 * 1024,
    256 * 1024 * 1024,
    1_000_000,
    100_000_000,
    1024 * 1024 * 1024 * 1024,
    16 * 1024 * 1024 * 1024 * 1024,
)


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


def crc32c(data: bytes) -> int:
    checksum = 0xFFFFFFFF
    for value in data:
        checksum ^= value
        for _ in range(8):
            checksum = ((checksum >> 1) ^ 0x82F63B78) \
                if checksum & 1 else checksum >> 1
    return checksum ^ 0xFFFFFFFF


class Cursor:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def read(self, size: int) -> bytes:
        if size < 0 or self.offset + size > len(self.data):
            raise EvidenceError("bounded storage field is truncated")
        result = self.data[self.offset:self.offset + size]
        self.offset += size
        return result

    def unpack(self, shape: str) -> tuple[object, ...]:
        size = struct.calcsize(shape)
        return struct.unpack(shape, self.read(size))

    def string(self, allow_empty: bool = False) -> str:
        (length,) = self.unpack(">i")
        if length < 0 or length > 1024 or (length == 0 and not allow_empty):
            raise EvidenceError("persisted string length is invalid")
        try:
            return self.read(length).decode("utf-8", errors="strict")
        except UnicodeError as failure:
            raise EvidenceError("persisted string is not UTF-8") from failure


def inspect_phase2_directory(workspace: Path) -> dict[str, object]:
    if not workspace.is_dir() or workspace.is_symlink():
        raise EvidenceError("engine directory must be a regular directory")
    entries = sorted(workspace.iterdir(), key=lambda entry: entry.name)
    names = {entry.name for entry in entries}
    if names != PHASE2_FILES:
        raise EvidenceError(f"unexpected Phase 2 storage members: {sorted(names)}")
    for entry in entries:
        if not entry.is_file() or entry.is_symlink():
            raise EvidenceError(f"non-regular Phase 2 storage member: {entry.name}")
    metadata = inspect_metadata(workspace / "gse-metadata")
    wal = inspect_wal(
        workspace / "gse-wal-00000000000000000001.log",
        metadata,
    )
    return {
        "schemaVersion": "gse-v4-storage-inspection-v1",
        "classification": "PHASE2_WAL_ONLY",
        "files": [entry.name for entry in entries],
        "metadata": metadata,
        "wal": wal,
    }


def inspect_metadata(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < 4 or crc32c(data[:-4]) != struct.unpack(">I", data[-4:])[0]:
        raise EvidenceError("metadata checksum mismatch")
    cursor = Cursor(data[:-4])
    magic, major, minor, history_most, history_least = cursor.unpack(">QhhQQ")
    if (magic, major, minor) != (METADATA_MAGIC, 1, 0):
        raise EvidenceError("metadata format identity mismatch")
    family = cursor.string()
    if family != "gse-durable":
        raise EvidenceError("metadata family mismatch")
    storage_identity = cursor.string()
    schema_identity = cursor.string()
    codec_id = cursor.string()
    (codec_version,) = cursor.unpack(">i")
    limits = cursor.unpack(">iiiiqq")
    if (codec_version < 0
            or any(value <= 0 for value in limits)
            or any(value > maximum
                   for value, maximum in zip(limits, HARD_LIMITS, strict=True))
            or limits[5] <= limits[4]):
        raise EvidenceError("metadata codec or limits are invalid")
    (index_count,) = cursor.unpack(">i")
    if index_count < 0 or index_count > 1_000_000:
        raise EvidenceError("metadata index count is invalid")
    indexes: list[dict[str, object]] = []
    for _ in range(index_count):
        (kind,) = cursor.unpack(">b")
        field = cursor.string()
        analyzer = cursor.string(allow_empty=True)
        if kind not in {1, 2, 3, 4}:
            raise EvidenceError("metadata index kind is invalid")
        if (kind == 4) != (analyzer == "gse-simple-v1"):
            raise EvidenceError("metadata analyzer identity is invalid")
        indexes.append({"kind": kind, "field": field, "analyzer": analyzer})
    if cursor.offset != len(cursor.data):
        raise EvidenceError("metadata has trailing bytes")
    return {
        "formatFamily": family,
        "formatMajor": major,
        "formatMinor": minor,
        "historyMost": f"{history_most:016x}",
        "historyLeast": f"{history_least:016x}",
        "storageIdentity": storage_identity,
        "schemaIdentity": schema_identity,
        "codecId": codec_id,
        "codecVersion": codec_version,
        "maxEncodedKeyBytes": limits[0],
        "maxEncodedDocumentBytes": limits[1],
        "maxBulkElements": limits[2],
        "maxDocuments": limits[3],
        "checkpointWalBytes": limits[4],
        "maxRetainedBytes": limits[5],
        "indexes": indexes,
        "bytes": len(data),
    }


def inspect_wal(path: Path, metadata: dict[str, object]) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < WAL_HEADER_BYTES:
        raise EvidenceError("WAL generation header is truncated")
    header = data[:WAL_HEADER_BYTES]
    unpacked = struct.unpack(">QhhQQQQI", header)
    magic, major, minor, history_most, history_least, generation, first, checksum = \
        unpacked
    if (magic, major, minor, generation, first) != (WAL_MAGIC, 1, 0, 1, 1):
        raise EvidenceError("WAL generation identity is invalid")
    if crc32c(header[:-4]) != checksum:
        raise EvidenceError("WAL generation checksum mismatch")
    if (f"{history_most:016x}" != metadata["historyMost"]
            or f"{history_least:016x}" != metadata["historyLeast"]):
        raise EvidenceError("WAL history identity mismatch")

    frames: list[dict[str, object]] = []
    offset = WAL_HEADER_BYTES
    expected_sequence = 1
    tail = "NONE"
    while offset < len(data):
        remaining = len(data) - offset
        if remaining < FRAME_HEADER_BYTES:
            validate_incomplete_header(data[offset:], expected_sequence)
            tail = "INCOMPLETE_HEADER"
            break
        header_values = struct.unpack(">IhhIqbbhi", data[offset:offset + 28])
        (frame_magic, frame_major, frame_minor, frame_length, sequence,
         unit_type, flags, reserved, payload_length) = header_values
        if (frame_magic, frame_major, frame_minor) != (FRAME_MAGIC, 1, 0):
            raise EvidenceError("WAL frame identity is invalid")
        if (unit_type not in {1, 2, 3, 4} or flags != 0 or reserved != 0):
            raise EvidenceError("WAL frame type or flags are invalid")
        if (payload_length < 0
                or frame_length != FRAME_HEADER_BYTES + payload_length
                + FRAME_TRAILER_BYTES
                or frame_length > MAX_FRAME_BYTES):
            raise EvidenceError("WAL frame length relation is invalid")
        if frame_length > remaining:
            tail = "INCOMPLETE_FRAME"
            break
        frame = data[offset:offset + frame_length]
        expected_crc = struct.unpack(">I", frame[-4:])[0]
        if crc32c(frame[:-4]) != expected_crc:
            raise EvidenceError("complete WAL frame checksum mismatch")
        if sequence != expected_sequence:
            raise EvidenceError("WAL sequence is not contiguous")
        payload = frame[FRAME_HEADER_BYTES:-4]
        inspect_payload(unit_type, payload, metadata)
        frames.append({
            "sequence": sequence,
            "type": unit_type,
            "payloadBytes": payload_length,
            "offset": offset,
            "frameBytes": frame_length,
        })
        expected_sequence += 1
        offset += frame_length
    return {
        "generation": generation,
        "firstSequence": first,
        "completeFrames": frames,
        "lastCompleteSequence": expected_sequence - 1,
        "lastValidOffset": offset,
        "terminalTail": tail,
        "bytes": len(data),
    }


def validate_incomplete_header(data: bytes, expected_sequence: int) -> None:
    fixed_identity = struct.pack(">Ihh", FRAME_MAGIC, 1, 0)
    identity_bytes = min(len(data), len(fixed_identity))
    if data[:identity_bytes] != fixed_identity[:identity_bytes]:
        raise EvidenceError("incomplete WAL frame identity is invalid")
    if len(data) >= 12:
        (frame_length,) = struct.unpack(">i", data[8:12])
        if frame_length < FRAME_HEADER_BYTES + FRAME_TRAILER_BYTES \
                or frame_length > MAX_FRAME_BYTES:
            raise EvidenceError("incomplete WAL frame length is invalid")
    if len(data) >= 20:
        (sequence,) = struct.unpack(">q", data[12:20])
        if sequence != expected_sequence:
            raise EvidenceError("incomplete WAL sequence is not contiguous")
    if len(data) >= 21 and data[20] not in {1, 2, 3, 4}:
        raise EvidenceError("incomplete WAL frame type is invalid")
    if len(data) >= 22 and data[21] != 0:
        raise EvidenceError("incomplete WAL frame flags are invalid")
    if len(data) >= 24 and data[22:24] != b"\x00\x00":
        raise EvidenceError("incomplete WAL frame reserved bytes are invalid")


def inspect_payload(
        unit_type: int,
        payload: bytes,
        metadata: dict[str, object],
) -> None:
    cursor = Cursor(payload)
    if unit_type == 1:
        inspect_mutation(cursor, metadata)
    elif unit_type == 2:
        (count,) = cursor.unpack(">i")
        if count <= 0 or count > metadata["maxBulkElements"]:
            raise EvidenceError("WAL bulk element count is invalid")
        for _ in range(count):
            inspect_mutation(cursor, metadata)
    elif unit_type == 3:
        (kind,) = cursor.unpack(">b")
        field = cursor.string()
        analyzer = cursor.string(allow_empty=True)
        if kind not in {1, 2, 3, 4} or not field:
            raise EvidenceError("WAL index descriptor is invalid")
        if (kind == 4) != (analyzer == "gse-simple-v1"):
            raise EvidenceError("WAL index analyzer is invalid")
    else:
        cursor.string()
    if cursor.offset != len(payload):
        raise EvidenceError("WAL payload has trailing bytes")


def inspect_mutation(cursor: Cursor, metadata: dict[str, object]) -> None:
    (operation,) = cursor.unpack(">b")
    if operation not in {1, 2, 3}:
        raise EvidenceError("WAL mutation operation is invalid")
    (key_length,) = cursor.unpack(">i")
    if key_length < 0 or key_length > metadata["maxEncodedKeyBytes"]:
        raise EvidenceError("WAL key length is invalid")
    cursor.read(key_length)
    (document_length,) = cursor.unpack(">i")
    if operation == 3:
        if document_length != -1:
            raise EvidenceError("remove WAL entry contains a document")
    else:
        if (document_length < 0
                or document_length > metadata["maxEncodedDocumentBytes"]):
            raise EvidenceError("WAL document length is invalid")
        cursor.read(document_length)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--phase", choices=("phase1", "phase2"), default="phase1")
    parser.add_argument("--barrier")
    arguments = parser.parse_args()
    if arguments.phase == "phase1" and not arguments.barrier:
        raise EvidenceError("Phase 1 inspection requires --barrier")
    result = inspect_phase1_directory(arguments.directory, arguments.barrier) \
        if arguments.phase == "phase1" else inspect_phase2_directory(
            arguments.directory)
    print(json.dumps(
        result,
        sort_keys=True,
        separators=(",", ":"),
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
