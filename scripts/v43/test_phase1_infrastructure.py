from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts.v43.evidence import EvidenceError, validate_bundle
from scripts.v43.fake_cloud_lane import CELLS, PLAN, fake_run


class Phase1InfrastructureTest(unittest.TestCase):
    def test_fake_canonical_is_serial_quota_safe_and_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "canonical"
            self.assertEqual(0, fake_run(Namespace(
                output=output, source_sha="1" * 40,
                source_state="clean", profile="canonical")))
            evidence = validate_bundle(output)
            self.assertEqual(3, evidence["case"]["memberCount"])
            self.assertTrue(evidence["case"]["serialMembers"])
            self.assertEqual(CELLS, evidence["case"]["cells"])
            self.assertEqual([], evidence["cleanup"]["leftovers"])
            self.assertTrue(evidence["cleanup"]["verifiedBeforeNextMember"])

    def test_plan_freezes_resource_cost_identity_and_thresholds(self) -> None:
        self.assertEqual("c3d-standard-30", PLAN["machineType"])
        self.assertEqual(30, PLAN["peakProjectVcpus"])
        self.assertEqual(400, PLAN["peakRegionalSsdGiB"])
        self.assertEqual(1_800, PLAN["measurementSeconds"])
        self.assertEqual(5_400, PLAN["maximumMemberRuntimeSeconds"])
        self.assertEqual(25, PLAN["maximumCompleteRunCostUsd"])
        self.assertEqual("4.2.0", PLAN["publishedControlVersion"])
        self.assertEqual(0.50, PLAN["warmMedianMaximumRatio"])
        self.assertEqual(0.65, PLAN["warmMemberMaximumRatio"])
        self.assertEqual("gcs", PLAN["retention"]["canonical"])
        self.assertIn("<source-sha>", PLAN["gcsLayout"])
        self.assertTrue(PLAN["workflowRef"].endswith(
            "v43-fast-reopen-evidence.yml@refs/heads/master"))
        self.assertEqual("cloud-benchmark", PLAN["environment"])

    def test_replacement_host_precedes_transient_target_cells(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "experiment"
            fake_run(Namespace(output=output, source_sha="2" * 40,
                               source_state="dirty", profile="experiment"))
            lifecycle = validate_bundle(output)["lifecycle"]
            self.assertLess(lifecycle.index("source-host-deleted"),
                            lifecycle.index("replacement-host-created"))
            self.assertLess(lifecycle.index("replacement-host-deleted"),
                            lifecycle.index(
                                "transient-restore-migration-disks-run-serially"))
            self.assertEqual("cleanup-verified-before-next-member", lifecycle[-1])

    def test_tampered_evidence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "failure"
            fake_run(Namespace(output=output, source_sha="3" * 40,
                               source_state="clean", profile="failure-drill"))
            (output / "evidence.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceError, "checksum"):
                validate_bundle(output)


if __name__ == "__main__":
    unittest.main()
