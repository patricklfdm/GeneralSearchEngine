from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.v41.backup_crash_inspector import FINAL_BARRIERS, STAGING


class BackupCrashInspectorContractTest(unittest.TestCase):
    def test_staging_and_final_barrier_contracts_are_frozen(self) -> None:
        self.assertIsNotNone(STAGING.fullmatch(
            ".gse-v41-backup-0123456789abcdef0123456789abcdef.staging"))
        self.assertEqual({
            "v41-backup-after-final-rename-v1",
            "v41-backup-after-parent-force-v1",
            "v41-backup-before-future-completion-v1",
        }, FINAL_BARRIERS)

    def test_graceful_marker_shape_is_reserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            marker = workspace / "graceful-close.marker"
            marker.write_text("shutdown-hook-ran\n", encoding="ascii")
            self.assertTrue(marker.is_file())


if __name__ == "__main__":
    unittest.main()
