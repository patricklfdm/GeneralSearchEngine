from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from scripts.v4.evidence import EvidenceError
from scripts.v4.storage_inspector import (
    CHECKPOINT_MAGIC,
    MANIFEST_MAGIC,
    WAL_MAGIC,
    crc32c,
    inspect_phase4_directory,
)
from scripts.v4.test_phase2_storage_inspector import (
    complete_frame,
    metadata_bytes,
    text,
)

HISTORY_MOST = 0x0102030405060708
HISTORY_LEAST = 0x1112131415161718
CHECKPOINT_FILE = (
    "gse-checkpoint-00000000000000000001-"
    "0123456789abcdef0123456789abcdef.chk"
)


class Phase4CheckpointFixtureTest(unittest.TestCase):
    def test_authoritative_checkpoint_and_post_cut_wal_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_store(directory)
            inspection = inspect_phase4_directory(directory)
            self.assertEqual("PHASE4_CHECKPOINT_HISTORY",
                             inspection["classification"])
            self.assertEqual(1, inspection["durableSequence"])
            self.assertEqual(1, inspection["checkpoint"]["liveDocuments"])
            self.assertEqual(2, inspection["wals"][0]["generation"])
            self.assertEqual(2, inspection["wals"][0]["firstSequence"])

    def test_staging_is_inventory_only_and_never_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_store(directory)
            staging = directory / (
                "gse-checkpoint-00000000000000000002-"
                "fedcba9876543210fedcba9876543210.chk.staging")
            staging.write_bytes(b"partial")
            inspection = inspect_phase4_directory(directory)
            self.assertEqual([staging.name], inspection["stagingFiles"])
            self.assertEqual(CHECKPOINT_FILE,
                             inspection["manifest"]["checkpointFile"])

    def test_checkpoint_and_manifest_corruption_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_store(directory)
            checkpoint = directory / CHECKPOINT_FILE
            damaged = bytearray(checkpoint.read_bytes())
            damaged[-1] ^= 1
            checkpoint.write_bytes(damaged)
            with self.assertRaisesRegex(EvidenceError, "checkpoint checksum"):
                inspect_phase4_directory(directory)

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_store(directory)
            manifest = directory / "gse-checkpoint-manifest"
            damaged = bytearray(manifest.read_bytes())
            damaged[-1] ^= 1
            manifest.write_bytes(damaged)
            with self.assertRaisesRegex(EvidenceError, "manifest checksum"):
                inspect_phase4_directory(directory)

    def test_pre_manifest_wal_retained_after_cleanup_failure_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_store(directory)
            (directory / "gse-wal-00000000000000000001.log").write_bytes(
                wal_header_for(1, 1) + complete_frame())
            inspection = inspect_phase4_directory(directory)
            self.assertEqual(1, inspection["durableSequence"])
            self.assertEqual([1, 2], [wal["generation"]
                                     for wal in inspection["wals"]])
            self.assertEqual([1, 2], [wal["firstSequence"]
                                     for wal in inspection["wals"]])


def checked(content: bytes) -> bytes:
    return content + struct.pack(">I", crc32c(content))


def checkpoint_bytes() -> bytes:
    key = struct.pack(">i", 7)
    document = b"doc-seven"
    content = b"".join((
        struct.pack(">QhhQQqiii", CHECKPOINT_MAGIC, 1, 0,
                    HISTORY_MOST, HISTORY_LEAST, 1, 1, 1, 0),
        struct.pack(">iB", 1, 1),
        struct.pack(">i", len(key)), key,
        struct.pack(">i", len(document)), document,
    ))
    return checked(content)


def manifest_bytes(checkpoint: bytes) -> bytes:
    checkpoint_checksum = struct.unpack(">I", checkpoint[-4:])[0]
    content = b"".join((
        struct.pack(">QhhQQqqI", MANIFEST_MAGIC, 1, 0,
                    HISTORY_MOST, HISTORY_LEAST, 1, len(checkpoint),
                    checkpoint_checksum),
        text(CHECKPOINT_FILE),
        struct.pack(">qq", 2, 2),
    ))
    return checked(content)


def wal_header() -> bytes:
    return wal_header_for(2, 2)


def wal_header_for(generation: int, first_sequence: int) -> bytes:
    content = struct.pack(
        ">QhhQQQQ",
        WAL_MAGIC,
        1,
        0,
        HISTORY_MOST,
        HISTORY_LEAST,
        generation,
        first_sequence,
    )
    return checked(content)


def write_store(directory: Path) -> None:
    checkpoint = checkpoint_bytes()
    (directory / "gse.lock").write_bytes(b"")
    (directory / "gse-metadata").write_bytes(metadata_bytes())
    (directory / CHECKPOINT_FILE).write_bytes(checkpoint)
    (directory / "gse-checkpoint-manifest").write_bytes(
        manifest_bytes(checkpoint))
    (directory / "gse-wal-00000000000000000002.log").write_bytes(wal_header())


if __name__ == "__main__":
    unittest.main()
