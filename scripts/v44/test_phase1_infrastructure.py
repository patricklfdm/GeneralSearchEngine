from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts.v44.evidence import EvidenceError, validate_bundle
from scripts.v44.fake_cloud_lane import PLAN_PATH, fake_run, load_plan
from scripts.v44.final_matrix import validate as validate_matrix
from scripts.v44.toolchain_manifest import validate as validate_toolchain

ROOT = Path(__file__).resolve().parents[2]


class Phase1InfrastructureTest(unittest.TestCase):
    def test_plan_freezes_closed_surface_workloads_thresholds_and_cloud(self) -> None:
        plan = load_plan()
        self.assertEqual("4.4.0-SNAPSHOT", plan["productVersion"])
        self.assertEqual("4.3.0", plan["publishedControl"]["version"])
        self.assertFalse(plan["publicApiExpansion"])
        self.assertFalse(plan["productionChange"])
        self.assertFalse(plan["paidExecution"])
        self.assertEqual(["1.0", "1.1", "1.2"], plan["formats"])
        self.assertEqual(20_000, plan["denseWorkload"]["documents"])
        self.assertEqual(100_000, plan["persistentWorkload"]["documents"])
        self.assertEqual(3_600, plan["persistentWorkload"]["measurementSeconds"])
        thresholds = plan["pairedThresholds"]
        self.assertEqual(1.20, thresholds["lowerMedianMaximumRatio"])
        self.assertEqual(1.35, thresholds["lowerMemberMaximumRatio"])
        self.assertEqual(0.80, thresholds["higherMedianMinimumRatio"])
        self.assertEqual(0.65, thresholds["higherMemberMinimumRatio"])
        cloud = plan["cloud"]
        self.assertEqual("c3d-standard-30", cloud["machineType"])
        self.assertEqual(30, cloud["peakProjectVcpus"])
        self.assertEqual(400, cloud["peakDataDiskGiB"])
        self.assertEqual(500, cloud["peakProvisionedDiskGiB"])
        self.assertEqual(3, cloud["canonicalMembers"])
        self.assertTrue(cloud["serialMembers"])
        self.assertEqual(40, cloud["maximumCompleteRunCostUsd"])
        self.assertEqual("v4.4-final-durable/",
                         plan["identities"]["gcsPrefix"])

    def test_fake_profiles_are_serial_quota_safe_and_exactly_clean(self) -> None:
        for profile, members in (("experiment", 1), ("canonical", 3),
                                 ("failure-drill", 1)):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / profile
                fake_run(Namespace(output=output, source_sha="4" * 40,
                                   source_state="clean", profile=profile))
                evidence = validate_bundle(output)
                self.assertEqual(members, evidence["case"]["memberCount"])
                self.assertTrue(evidence["case"]["serialMembers"])
                self.assertTrue(evidence["process"]["sourceHostDeleted"])
                self.assertTrue(evidence["cleanup"]["verifiedBeforeNextMember"])
                self.assertEqual([], evidence["cleanup"]["leftovers"])

    def test_tampered_evidence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "evidence"
            fake_run(Namespace(output=output, source_sha="5" * 40,
                               source_state="dirty", profile="failure-drill"))
            document = json.loads((output / "evidence.json").read_text())
            document["cleanup"]["leftovers"] = ["disk"]
            (output / "evidence.json").write_text(json.dumps(document))
            with self.assertRaisesRegex(EvidenceError, "checksum"):
                validate_bundle(output)

    def test_independent_matrix_and_toolchain_are_frozen(self) -> None:
        matrix = validate_matrix(ROOT /
            "src/test/resources/compatibility/v44-final-matrix-v1")
        self.assertEqual(10, len(matrix["families"]))
        self.assertGreaterEqual(len(matrix["cases"]), 18)
        toolchain = validate_toolchain(ROOT /
            "docs/v4x/v4.4/release-toolchain.json")
        self.assertEqual(6, toolchain["canonicalJarCount"])
        self.assertEqual("21.0.12+8", toolchain["java"]["fullVersion"])

    def test_plan_path_is_under_accepted_v44_docs(self) -> None:
        self.assertEqual(ROOT / "docs/v4x/v4.4/phase1-plan.json", PLAN_PATH)


if __name__ == "__main__":
    unittest.main()
