from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.v41.backup_format import MEMBERS, inspect_bundle, load_hex_fixture


PROJECT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT / "src/test/resources/compatibility/v41-backup-v1"
API_FIXTURE = PROJECT / (
    "src/test/resources/compatibility/V41OperationalPublicApi.java.fixture"
)
REGISTRY = PROJECT / "docs/v4x/v4.1/cloud-benchmark-baselines.json"


class Phase7ReleaseFixtureTest(unittest.TestCase):
    def test_frozen_fixture_file_hashes(self) -> None:
        expected = {
            "V41OperationalPublicApi.java.fixture": (
                API_FIXTURE,
                "1f50af65a5894d08d25d70d490c86a9cb958119576750b507ac049e8b0a5432b",
            ),
            "gse-backup-metadata.hex": (
                FIXTURE_ROOT / "gse-backup-metadata.hex",
                "d733f6915dab8e1de93355118f5f02acb212acdb5e219397ef276e4d03253a81",
            ),
            "gse-backup-checkpoint.hex": (
                FIXTURE_ROOT / "gse-backup-checkpoint.hex",
                "8e7e1d01515ac136d19aeea96a2c6bad6f1b47e89e33c9677c40ae633968a01c",
            ),
            "gse-backup-manifest.hex": (
                FIXTURE_ROOT / "gse-backup-manifest.hex",
                "99f9219505b58711ade6cb208af2f64d5b85a2060b24d2e5ad049f8b11940993",
            ),
        }
        for name, (path, digest) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_frozen_backup_materializes_and_validates_independently(self) -> None:
        frozen = load_hex_fixture(FIXTURE_ROOT)
        self.assertEqual(
            "gse-backup-v1-d1a8b2c947d21af5d3cf2d0b50e80006c0369b9f4e5a0f5e5a427c6e57e18514",
            frozen.content_identity,
        )
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "bundle"
            bundle.mkdir()
            payloads = {
                "gse-backup-checkpoint": frozen.checkpoint,
                "gse-backup-manifest": frozen.manifest,
                "gse-backup-metadata": frozen.metadata,
            }
            self.assertEqual(set(MEMBERS), set(payloads))
            for name, payload in payloads.items():
                (bundle / name).write_bytes(payload)
            inspected = inspect_bundle(bundle)
            self.assertEqual("VALID", inspected["status"])
            self.assertEqual(7, inspected["sequence"])
            self.assertEqual(frozen.content_identity, inspected["contentIdentity"])

    def test_operational_baseline_registration_is_exact_and_unique(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(
            "gse-v41-operational-baseline-registry-v1",
            registry["schemaVersion"],
        )
        self.assertEqual(
            [
                {
                    "memberCount": 3,
                    "name": "v4.1.0-operational-cloud",
                    "preset": "v4.1-operational-safety-v1",
                    "setDigest": "bede37bfd7c37bd7da891461a5d91d8dc6bdc3a085d2b873c739cc723ca68f27",
                    "sourceCommit": "88205cf28f1aa80f8ea7ccf1bada723b3205215c",
                    "suite": "v4.1-operational-safety-suite-v1",
                }
            ],
            registry["baselines"],
        )


if __name__ == "__main__":
    unittest.main()
