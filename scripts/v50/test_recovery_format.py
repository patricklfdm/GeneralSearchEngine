import tempfile
import unittest
from pathlib import Path
from scripts.v50 import recovery_format as recovery, storage_format as storage


class RecoveryFormatTest(unittest.TestCase):
    def test_independent_snapshot_generation_preserves_ancestry_and_control_sequence(self):
        with tempfile.TemporaryDirectory() as root:
            report = recovery.generate(Path(root) / "replica")
            self.assertEqual((2, 3, 2, 1, True), (report["snapshotIndex"], report["lastLogIndex"], report["commitIndex"], report["snapshotApplicationSequence"], report["voter"]))
            self.assertEqual([3], [entry["index"] for entry in report["retainedApplicationEntries"]])
            self.assertEqual(0, report["appliedIndex"])

    def test_checksum_and_structural_corruptions_reject(self):
        for kind in ("pointer", "snapshot", "floor", "missing-selector", "unknown-member", "tail-incarnation"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as root:
                path = Path(root) / "replica"
                recovery.generate(path)
                if kind == "missing-selector": (path / "current.gsr").unlink()
                elif kind == "unknown-member": (path / "generation-a/foreign").write_bytes(b"unexpected")
                elif kind == "tail-incarnation":
                    promises = path / "promises.gsr"
                    import io
                    source = io.BytesIO(promises.read_bytes())
                    storage.read_frame(source, 3, storage.MAX_METADATA); offset = source.tell()
                    body = bytearray(storage.read_frame(source, 4, storage.MAX_METADATA)[0])
                    body[-24:-16] = (3).to_bytes(8, "big")
                    promises.write_bytes(promises.read_bytes()[:offset] + storage.frame(4, body))
                    tail = path / "generation-a/entries.gsr"
                    source = io.BytesIO(tail.read_bytes())
                    storage.read_frame(source, 3, storage.MAX_METADATA); offset = source.tell()
                    body = bytearray(storage.read_frame(source, 5, storage.MAX_FRAME)[0]); body[40] ^= 1
                    tail.write_bytes(tail.read_bytes()[:offset] + storage.frame(5, body))
                else:
                    file = path / {"pointer": "current.gsr", "snapshot": "generation-a/snapshot.gsr", "floor": "recovery-floor.gsr"}[kind]
                    raw = bytearray(file.read_bytes()); raw[-1] ^= 1; file.write_bytes(raw)
                with self.assertRaises(ValueError): storage.inspect(path)

    def test_snapshot_proof_must_bind_terminal_ancestry_even_after_rechecksumming(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "replica"; recovery.generate(path)
            snapshot = path / "generation-a/snapshot.gsr"
            raw = bytearray(snapshot.read_bytes()); body = bytearray(raw[48:]); body[36 + 25] ^= 1
            # Parse snapshot directly so the seal mismatch does not mask proof/ancestry validation.
            snapshot.write_bytes(storage.frame(8, body))
            manifest = storage.single(path / "manifest.gsr", 1)[1]
            with self.assertRaises(ValueError): recovery.snapshot(snapshot, manifest, storage.VOTERS)

    def test_unselected_partial_stage_preserves_selected_authority(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "replica"; before = recovery.generate(path)
            (path / "generation-b").mkdir(); (path / "generation-b/snapshot.gsr").write_bytes(b"partial")
            self.assertEqual(before, storage.inspect(path))


if __name__ == "__main__": unittest.main()
