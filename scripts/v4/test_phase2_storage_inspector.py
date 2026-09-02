from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from scripts.v4.evidence import EvidenceError
from scripts.v4.storage_inspector import (
    FRAME_MAGIC,
    METADATA_MAGIC,
    WAL_MAGIC,
    crc32c,
    inspect_phase2_directory,
)


class Phase2StorageInspectorTest(unittest.TestCase):
    def test_complete_frame_and_incomplete_terminal_header(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_store(directory, complete_frame())
            inspection = inspect_phase2_directory(directory)
            self.assertEqual(
                1, inspection["wal"]["lastCompleteSequence"])
            self.assertEqual("NONE", inspection["wal"]["terminalTail"])

            wal = directory / "gse-wal-00000000000000000001.log"
            partial_header = struct.pack(">Ihh", FRAME_MAGIC, 1, 0)[:5]
            wal.write_bytes(wal.read_bytes() + partial_header)
            inspection = inspect_phase2_directory(directory)
            self.assertEqual(
                "INCOMPLETE_HEADER", inspection["wal"]["terminalTail"])
            self.assertEqual(1, inspection["wal"]["lastCompleteSequence"])

    def test_invalid_available_partial_header_bytes_are_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_store(directory, complete_frame() + b"NOPE")
            with self.assertRaisesRegex(EvidenceError, "identity"):
                inspect_phase2_directory(directory)

    def test_metadata_hard_limit_violation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_store(
                directory,
                complete_frame(),
                limits=(64 * 1024 * 1024 + 1, 4096, 100, 1000, 4096, 65536),
            )
            with self.assertRaisesRegex(EvidenceError, "limits"):
                inspect_phase2_directory(directory)

    def test_complete_checksum_failure_is_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            frame = bytearray(complete_frame())
            frame[-1] ^= 0x01
            write_store(directory, bytes(frame))
            with self.assertRaisesRegex(EvidenceError, "checksum"):
                inspect_phase2_directory(directory)


def text(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack(">i", len(encoded)) + encoded


def metadata_bytes(
        limits: tuple[int, int, int, int, int, int] =
        (1024, 4096, 100, 1000, 4096, 65536),
) -> bytes:
    history_most = 0x0102030405060708
    history_least = 0x1112131415161718
    content = b"".join((
        struct.pack(">QhhQQ", METADATA_MAGIC, 1, 0, history_most, history_least),
        text("gse-durable"),
        text("phase2-store-v1"),
        text("phase2-schema-v1"),
        text("phase2-codec-v1"),
        struct.pack(">i", 1),
        struct.pack(">iiiiqq", *limits),
        struct.pack(">i", 0),
    ))
    return content + struct.pack(">I", crc32c(content))


def wal_header() -> bytes:
    content = struct.pack(
        ">QhhQQQQ",
        WAL_MAGIC,
        1,
        0,
        0x0102030405060708,
        0x1112131415161718,
        1,
        1,
    )
    return content + struct.pack(">I", crc32c(content))


def complete_frame() -> bytes:
    key = struct.pack(">i", 7)
    document = b"document-seven"
    payload = b"".join((
        struct.pack(">b", 1),
        struct.pack(">i", len(key)),
        key,
        struct.pack(">i", len(document)),
        document,
    ))
    frame_length = 28 + len(payload) + 4
    header = struct.pack(
        ">IhhIqbbhi",
        FRAME_MAGIC,
        1,
        0,
        frame_length,
        1,
        1,
        0,
        0,
        len(payload),
    )
    checked = header + payload
    return checked + struct.pack(">I", crc32c(checked))


def write_store(
        directory: Path,
        frame: bytes,
        limits: tuple[int, int, int, int, int, int] =
        (1024, 4096, 100, 1000, 4096, 65536),
) -> None:
    (directory / "gse.lock").write_bytes(b"")
    (directory / "gse-metadata").write_bytes(metadata_bytes(limits))
    (directory / "gse-wal-00000000000000000001.log").write_bytes(
        wal_header() + frame)


if __name__ == "__main__":
    unittest.main()
