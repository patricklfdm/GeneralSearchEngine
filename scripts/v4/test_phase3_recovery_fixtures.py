from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from scripts.v4.evidence import EvidenceError
from scripts.v4.storage_inspector import (
    FRAME_MAGIC,
    crc32c,
    inspect_phase3_directory,
)
from scripts.v4.test_phase2_storage_inspector import (
    complete_frame,
    write_store,
)


class Phase3RecoveryFixtureTest(unittest.TestCase):
    def test_every_structural_incomplete_tail_retains_only_valid_prefix(self) -> None:
        payload = mutation_payload()
        header = frame_header(2, len(payload))
        cases = {
            "header": header[:17],
            "payload": header + payload[:3],
            "trailer": header + payload + struct.pack(">I", crc32c(
                header + payload))[:2],
        }
        for name, tail in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                write_store(directory, complete_frame() + tail)
                inspection = inspect_phase3_directory(directory)
                self.assertEqual(
                    "PHASE3_WAL_ONLY_RECOVERY_INPUT",
                    inspection["classification"],
                )
                self.assertEqual(1, inspection["wal"]["lastCompleteSequence"])
                self.assertNotEqual("NONE", inspection["wal"]["terminalTail"])

    def test_complete_invalid_payload_is_corruption_not_a_tail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            payload = bytearray(mutation_payload())
            payload[0] = 9
            frame = complete(1, bytes(payload))
            write_store(directory, frame)
            with self.assertRaisesRegex(EvidenceError, "operation"):
                inspect_phase3_directory(directory)

    def test_checksum_valid_sequence_gap_is_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_store(directory, complete(2, mutation_payload()))
            with self.assertRaisesRegex(EvidenceError, "sequence"):
                inspect_phase3_directory(directory)


def mutation_payload() -> bytes:
    key = struct.pack(">i", 7)
    document = b"document-seven"
    return b"".join((
        struct.pack(">b", 1),
        struct.pack(">i", len(key)),
        key,
        struct.pack(">i", len(document)),
        document,
    ))


def frame_header(sequence: int, payload_length: int) -> bytes:
    return struct.pack(
        ">IhhIqbbhi",
        FRAME_MAGIC,
        1,
        0,
        28 + payload_length + 4,
        sequence,
        1,
        0,
        0,
        payload_length,
    )


def complete(sequence: int, payload: bytes) -> bytes:
    checked = frame_header(sequence, len(payload)) + payload
    return checked + struct.pack(">I", crc32c(checked))


if __name__ == "__main__":
    unittest.main()
