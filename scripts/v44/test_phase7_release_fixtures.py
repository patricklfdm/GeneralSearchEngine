from __future__ import annotations

import hashlib
import json
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


if __name__ == "__main__":
    unittest.main()
