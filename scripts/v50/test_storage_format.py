"""Independent, codec-free storage checks, usable in the no-Java/no-cloud CI job."""

import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

from scripts.v50 import storage_format as storage


GOLDEN = Path(__file__).resolve().parents[2] / "general-search-engine-replication/src/test/resources/replication/v50-storage-v1"


class StorageFormatTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "node-2"
        storage.generate(self.directory)

    def hashes(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.directory.iterdir()}

    def reject_unchanged(self):
        before = self.hashes()
        with self.assertRaises(ValueError):
            storage.inspect(self.directory)
        self.assertEqual(before, self.hashes())

    def test_golden_inventory_and_regeneration(self):
        actual = self.hashes()
        expected = {line.split()[1]: line.split()[0] for line in (GOLDEN / "SHA256SUMS").read_text().splitlines()}
        self.assertEqual(expected, actual)
        for filename in storage.FILES:
            self.assertEqual((self.directory / filename).read_bytes(), (GOLDEN / "node-2" / filename).read_bytes())
        report = storage.inspect(self.directory)
        self.assertEqual((2, 3, 2, 0, 0), tuple(report[k] for k in (
            "promisedEpoch", "lastLogIndex", "commitIndex", "appliedIndex", "applicationSequence")))

    def test_every_authoritative_file_torn_or_corrupt(self):
        for filename in sorted(storage.FILES - {"replica.lock"}):
            path = self.directory / filename
            original = path.read_bytes()
            for length in (0, 7, 47, len(original) - 1):
                with self.subTest(filename=filename, length=length):
                    path.write_bytes(original[:length])
                    self.reject_unchanged()
            path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
            self.reject_unchanged()
            path.write_bytes(original)

    def test_oversize_length_is_rejected_before_reading_body(self):
        path = self.directory / "entries.gsr"
        original = bytearray(path.read_bytes())
        start = 48 + struct.unpack_from(">i", original, 12)[0]
        struct.pack_into(">i", original, start + 12, 2 ** 31 - 1)
        path.write_bytes(original)
        self.reject_unchanged()

    def test_invalid_proof_receipt_with_valid_outer_checksum(self):
        path = self.directory / "proofs.gsr"
        original = path.read_bytes()
        start = 48 + struct.unpack_from(">i", original, 12)[0]
        body = bytearray(original[start + 48:])
        body[-1] ^= 1
        path.write_bytes(original[:start] + storage.frame(6, body))
        self.reject_unchanged()

    def test_missing_ready_and_unknown_member(self):
        (self.directory / "storage-ready.gsr").unlink()
        self.reject_unchanged()
        (self.directory / "surprise").write_bytes(b"keep")
        self.reject_unchanged()

    def test_unknown_operation_cannot_be_hidden_by_valid_frame_checksum(self):
        path = self.directory / "entries.gsr"
        original = path.read_bytes()
        start = 48 + struct.unpack_from(">i", original, 12)[0]
        size = 48 + struct.unpack_from(">i", original, start + 12)[0]
        body = bytearray(original[start + 48:start + size])
        body[64] = 11  # CONFIGURATION is reserved, not a V5.0 operation.
        path.write_bytes(original[:start] + storage.frame(5, body) + original[start + size:])
        self.reject_unchanged()

    def test_exact_retry_as_duplicate_on_disk_is_not_a_valid_history(self):
        for filename in ("promises.gsr", "entries.gsr", "proofs.gsr"):
            path = self.directory / filename
            original = path.read_bytes()
            start = 48 + struct.unpack_from(">i", original, 12)[0]
            path.write_bytes(original + original[start:])
            self.reject_unchanged()
            path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
