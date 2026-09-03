from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts.v41.evidence import EvidenceError, validate_bundle
from scripts.v41.fake_cloud_lane import PLAN, fake_run


class Phase1InfrastructureTest(unittest.TestCase):
    def test_fake_source_loss_is_serial_bounded_and_fully_cleaned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "canonical"
            self.assertEqual(0, fake_run(Namespace(
                output=output,
                source_sha="1" * 40,
                source_state="clean",
                profile="canonical",
            )))
            evidence = validate_bundle(output)
            self.assertEqual(3, evidence["case"]["memberCount"])
            self.assertTrue(evidence["case"]["serialMembers"])
            self.assertFalse(evidence["restore"]["sourceVmAvailable"])
            self.assertFalse(evidence["restore"]["sourceDiskAvailable"])
            self.assertEqual([], evidence["cleanup"]["leftovers"])
            self.assertEqual(200, evidence["configuration"]["sourceDiskGiB"])
            self.assertEqual(200, evidence["configuration"]["restoreDiskGiB"])
            self.assertEqual(25, evidence["configuration"]["maximumRunCostUsd"])

    def test_plan_matches_the_frozen_quota_envelope(self) -> None:
        self.assertEqual("c3d-standard-30", PLAN["machineType"])
        self.assertEqual("pd-balanced", PLAN["diskType"])
        self.assertEqual(1_800, PLAN["durationSeconds"])
        self.assertEqual(5_400, PLAN["maximumMemberRuntimeSeconds"])
        self.assertIn("<source-sha>", PLAN["gcsLayout"])
        self.assertIn("member-<slot>", PLAN["gcsLayout"])

    def test_tampered_evidence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "experiment"
            fake_run(Namespace(output=output, source_sha="2" * 40,
                               source_state="dirty", profile="experiment"))
            (output / "evidence.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceError, "checksum"):
                validate_bundle(output)


if __name__ == "__main__":
    unittest.main()
