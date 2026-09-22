from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from scripts.v44.canonical_reproducibility import ARTIFACTS, VERSION
from scripts.v44.cloud_set import BASELINE, read_registry
from scripts.v44.final_matrix import validate as validate_matrix
from scripts.v44.toolchain_manifest import validate as validate_toolchain


PROJECT = Path(__file__).resolve().parents[2]
API_INVENTORY = PROJECT / (
    "src/test/resources/compatibility/v44-public-api-inventory-v1.json"
)
MATRIX = PROJECT / "src/test/resources/compatibility/v44-final-matrix-v1"
TOOLCHAIN = PROJECT / "docs/v4x/v4.4/release-toolchain.json"
REGISTRY = PROJECT / "docs/v4x/v4.4/cloud-benchmark-baselines.json"
CANDIDATE_ARTIFACTS = PROJECT / "docs/v4x/v4.4/candidate-artifacts.sha256"
CI_WORKFLOW = PROJECT / ".github/workflows/ci.yml"
RELEASE_WORKFLOW = PROJECT / ".github/workflows/release.yml"


class Phase7ReleaseFixtureTest(unittest.TestCase):
    def test_frozen_v44_fixture_file_hashes(self) -> None:
        expected = {
            API_INVENTORY:
                "67e8c3435a6ccdfb572a0a00d3aa8b3b969815462a6fdebba08e64b412eaf04f",
            MATRIX / "README.md":
                "f52c17290dcfdc4875cbf95a234627f1f6bfd23d21e67c329e9cd30149d13a09",
            MATRIX / "fixture-checksums.sha256":
                "330a4659bc4d5a63a4dd0129376f166de5ca90f7a84e7c9858e5fe4fdf7dc3db",
            MATRIX / "logical-cases.json":
                "924dd54f51581bc178b5425f3905999cdfc8f3aa5601633760f459b760df2429",
            TOOLCHAIN:
                "7452aad8d3c885aaa7ede678faad9a8b8ffae00a6782a2960b9d5aa6050ea93c",
            REGISTRY:
                "5d7dd59e953bd91b7d5e7691a421b2aa6206c7e36c7dd7069065bbe221bd4c47",
            CANDIDATE_ARTIFACTS:
                "8420b47f91b80c54f19b125fcdf3f169a8f04355e06dbe64d122cfb60d720013",
        }
        for path, digest in expected.items():
            with self.subTest(path=path.name):
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_public_api_inventory_remains_the_published_43_inventory(self) -> None:
        self.assertEqual({
            "declarationLineCount": 2939,
            "inventorySha256":
                "d67f7f18795222d77c36d4e11ffdc913d1c9c8b6330ea9797b41f6f77d83650b",
            "publicTypeCount": 177,
            "schemaVersion": "gse-v44-public-api-inventory-v1",
        }, json.loads(API_INVENTORY.read_text(encoding="utf-8")))

    def test_independent_matrix_and_toolchain_remain_valid(self) -> None:
        matrix = validate_matrix(MATRIX)
        self.assertEqual(10, len(matrix["families"]))
        self.assertGreaterEqual(len(matrix["cases"]), 18)
        toolchain = validate_toolchain(TOOLCHAIN)
        self.assertEqual("21.0.12+8", toolchain["java"]["fullVersion"])
        self.assertEqual(6, toolchain["canonicalJarCount"])

    def test_final_artifact_inventory_uses_release_coordinates(self) -> None:
        self.assertEqual("4.4.0", VERSION)
        self.assertEqual(8, len(ARTIFACTS))
        self.assertTrue(all("SNAPSHOT" not in name for name in ARTIFACTS))

    def test_final_durable_registration_is_exact(self) -> None:
        registry = read_registry(REGISTRY)
        self.assertEqual("gse-v44-final-durable-baseline-registry-v1",
                         registry["schemaVersion"])
        self.assertEqual(1, len(registry["baselines"]))
        entry = registry["baselines"][0]
        self.assertEqual(BASELINE, entry["name"])
        self.assertEqual(
            "6301d855a92a3b2de8d9c338232a520fb9dd2b36",
            entry["sourceCommit"])
        self.assertEqual(
            "f1435bdf528138363986542ecafac563dbee0cf9dbed60f781ada27ff53c6465",
            entry["setDigest"])

    def check_workflow_java_selectors(self, workflow: str, release: bool = False) -> None:
        # Inspect explicit job/step blocks without adding a YAML dependency to CI.
        parts = re.split(r"^  ([\w-]+):\n", workflow.split("\njobs:\n", 1)[1], flags=re.MULTILINE)
        jobs = dict(zip(parts[1::2], parts[2::2]))
        expected_jobs = ({"validate", "publish"} if release else
                         set(jobs) - {"changes", "required", "cloud-runner-tests"})
        java_jobs = {name for name, body in jobs.items() if "uses: actions/setup-java@" in body}
        self.assertEqual(expected_jobs, java_jobs)
        selector = "21.0.12+8.0.LTS"
        for name in sorted(java_jobs):
            steps = re.split(r"^      - ", jobs[name], flags=re.MULTILINE)[1:]
            setups = [step for step in steps if "uses: actions/setup-java@" in step]
            self.assertEqual(1, len(setups), name)
            self.assertEqual(["temurin"], re.findall(r"^          distribution: (.+)$", setups[0], re.MULTILINE), name)
            expected = "'21'" if name == "compatibility" else "'" + selector + "'"
            if release:
                expected = "${{ (env.RELEASE_TAG == 'v4.4.0' || env.RELEASE_TAG == 'v5.0.0') && '" + selector + "' || '21' }}"
            self.assertEqual([expected], re.findall(r"^          java-version: (.+)$", setups[0], re.MULTILINE), name)

    def test_workflows_select_the_available_temurin_lts_catalog_version(self) -> None:
        self.check_workflow_java_selectors(CI_WORKFLOW.read_text(encoding="utf-8"))
        self.check_workflow_java_selectors(RELEASE_WORKFLOW.read_text(encoding="utf-8"), release=True)

    def test_java_selector_check_allows_an_additional_ci_lane(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        lane = re.search(r"^  reactor-core:\n.*?(?=^  [\w-]+:\n)", workflow, re.MULTILINE | re.DOTALL).group()
        self.check_workflow_java_selectors(workflow + lane.replace("  reactor-core:\n", "  extra-regression:\n", 1))

    def test_java_selector_check_rejects_drift_or_missing_setup(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        for old, new in (("21.0.12+8.0.LTS", "21.0.12+8"),
                         ("distribution: temurin", "distribution: zulu"),
                         ("java-version: '21.0.12+8.0.LTS'", "java-version: '21'"),
                         ("java-version: '21.0.12+8.0.LTS'", "# missing version"),
                         ("uses: actions/setup-java@", "uses: actions/missing-java@")):
            with self.subTest(drift=new), self.assertRaises(AssertionError):
                self.check_workflow_java_selectors(workflow.replace(old, new, 1))


if __name__ == "__main__":
    unittest.main()
