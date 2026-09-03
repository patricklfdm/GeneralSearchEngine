import hashlib
import pathlib
import tempfile
import unittest

from scripts.v41.cleanup_crash_inspector import inspect


class CleanupCrashInspectorTest(unittest.TestCase):
    def test_accepts_only_unchanged_authority_and_known_remnants(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = pathlib.Path(temporary)
            store = workspace / "store"
            store.mkdir()
            protected = store / "gse.lock"
            protected.write_bytes(b"")
            checksum = hashlib.sha256(b"").hexdigest()
            (workspace / "protected.sha256").write_text(
                f"{checksum}  gse.lock\n", encoding="ascii"
            )
            (store / "gse-metadata.staging").write_bytes(b"partial")
            self.assertEqual("PASS", inspect(workspace)["status"])
            protected.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "changed"):
                inspect(workspace)

    def test_operation_scope_preserves_source_and_rejects_final_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = pathlib.Path(temporary)
            source = workspace / "source"
            source.mkdir()
            protected = source / "gse.lock"
            protected.write_bytes(b"")
            checksum = hashlib.sha256(b"").hexdigest()
            (workspace / "protected.sha256").write_text(
                f"{checksum}  gse.lock\n", encoding="ascii"
            )
            report = inspect(workspace, "operation")
            self.assertEqual([], report["safeRemnants"])
            (workspace / "backup").mkdir()
            with self.assertRaisesRegex(ValueError, "final target"):
                inspect(workspace, "operation")


if __name__ == "__main__":
    unittest.main()
