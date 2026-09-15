import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.v50.replica_fixture import MAX_FILE_BYTES, generate, inspect


class ReplicaFixtureTest(unittest.TestCase):
    def test_generated_manifest_log_proof_and_snapshot_are_independently_inspected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "fixture"
            generate(fixture)
            result = inspect(fixture)
            self.assertEqual(3, len(result["log"]))
            self.assertEqual(2, result["commitProof"]["commitIndex"])
            self.assertEqual(2, result["snapshot"]["lastAppliedIndex"])

    def test_checksum_corruption_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "fixture"
            generate(fixture)
            with (fixture / "log.jsonl").open("ab") as output:
                output.write(b"corruption\n")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                inspect(fixture)

    def test_oversized_member_fails_even_with_a_matching_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "fixture"
            generate(fixture)
            oversized = b"x" * (MAX_FILE_BYTES + 1)
            (fixture / "snapshot.json").write_bytes(oversized)
            checksums = fixture / "artifact-checksums.sha256"
            lines = [line for line in checksums.read_text(encoding="utf-8").splitlines()
                     if not line.endswith("  snapshot.json")]
            lines.append(f"{hashlib.sha256(oversized).hexdigest()}  snapshot.json")
            checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "finite size bounds"):
                inspect(fixture)


if __name__ == "__main__":
    unittest.main()
