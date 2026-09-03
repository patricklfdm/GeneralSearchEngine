from __future__ import annotations

import unittest

from scripts.v41.restore_crash_inspector import FINAL_BARRIERS, STAGING


class RestoreCrashInspectorContractTest(unittest.TestCase):
    def test_staging_and_final_barrier_contracts_are_frozen(self) -> None:
        self.assertIsNotNone(STAGING.fullmatch(
            ".gse-v41-restore-0123456789abcdef0123456789abcdef.staging"))
        self.assertEqual({
            "v41-restore-after-final-rename-v1",
            "v41-restore-after-parent-force-v1",
            "v41-restore-before-return-v1",
        }, FINAL_BARRIERS)


if __name__ == "__main__":
    unittest.main()
