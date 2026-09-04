from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts.v42.evidence import EvidenceError, validate_bundle
from scripts.v42.fake_cloud_lane import PLAN, fake_run


class Phase1InfrastructureTest(unittest.TestCase):
    def test_fake_migration_is_serial_quota_safe_and_fully_cleaned(self) -> None:
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
            self.assertFalse(evidence["case"]["sourceAndTargetWritersConcurrent"])
            self.assertTrue(evidence["source"]["bytesUnchanged"])
            self.assertEqual("MODEL_PASS",
                             evidence["rollback"]["untouchedSourceReopened"])
            self.assertEqual([], evidence["cleanup"]["leftovers"])
            self.assertTrue(evidence["cleanup"]["verifiedBeforeNextMember"])

    def test_plan_freezes_quota_cost_oidc_and_retention(self) -> None:
        self.assertEqual("c3d-standard-30", PLAN["machineType"])
        self.assertEqual("pd-balanced", PLAN["diskType"])
        self.assertEqual(400, PLAN["peakRegionalSsdGiB"])
        self.assertEqual(30, PLAN["peakProjectVcpus"])
        self.assertEqual(1_800, PLAN["measurementSeconds"])
        self.assertEqual(5_400, PLAN["maximumMemberRuntimeSeconds"])
        self.assertEqual(25, PLAN["maximumCompleteRunCostUsd"])
        self.assertEqual("gcs", PLAN["retention"]["canonical"])
        self.assertIn("<source-sha>", PLAN["gcsLayout"])
        self.assertIn("member-<slot>", PLAN["gcsLayout"])
        self.assertTrue(PLAN["workflowRef"].endswith(
            "v42-storage-evolution-evidence.yml@refs/heads/master"))
        self.assertEqual("cloud-benchmark", PLAN["environment"])

    def test_lifecycle_stops_each_writer_before_other_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "experiment"
            fake_run(Namespace(output=output, source_sha="2" * 40,
                               source_state="dirty", profile="experiment"))
            lifecycle = validate_bundle(output)["lifecycle"]
            self.assertLess(lifecycle.index("source-writer-stopped"),
                            lifecycle.index("migration-plan-model-validated"))
            self.assertLess(lifecycle.index("target-writer-stopped-before-rollback"),
                            lifecycle.index(
                                "published-4.1-source-rollback-model-passed"))
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
