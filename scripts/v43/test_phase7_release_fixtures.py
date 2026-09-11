from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from scripts.v43.derived_fixture import validate as validate_logical_fixture
from scripts.v43.derived_format_v12 import (
    fixture,
    inspect_backup,
    inspect_live,
    load_hex_fixture,
)


PROJECT = Path(__file__).resolve().parents[2]
API_FIXTURE = PROJECT / (
    "src/test/resources/compatibility/V43FastReopenPublicApi.java.fixture"
)
LOGICAL_FIXTURE = PROJECT / "src/test/resources/compatibility/v43-derived-model-v1"
PHYSICAL_FIXTURE = PROJECT / "src/test/resources/compatibility/v43-derived-v12"
REGISTRY = PROJECT / "docs/v4x/v4.3/cloud-benchmark-baselines.json"


class Phase7ReleaseFixtureTest(unittest.TestCase):
    def test_frozen_fixture_file_hashes(self) -> None:
        expected = {
            API_FIXTURE: "4bf3503d77d01834915377002ceea92e5704274a2f131f15c71baaf7c2ed233a",
            LOGICAL_FIXTURE / "README.md": "9160d2fa57919185939de3cc352ca65966069d053e41956abfe6bc6eb59a8337",
            LOGICAL_FIXTURE / "fixture-checksums.sha256": "a250a380108465df5f23ba1f668dd6eff9a034d7eb9dd1cd7cee36691567a3a2",
            LOGICAL_FIXTURE / "logical-fixtures.json": "15cf132657c3efd5678983e718bfd55e3fdc4bb7aecef0af9c8c298bb5ae1f67",
            PHYSICAL_FIXTURE / "README.md": "e66f6e86264157bcd75af8149486b5b925c2348edf2ed6e2df84962c184b45d1",
            PHYSICAL_FIXTURE / "fixture-identities.properties": "46eeac1efa9b0ed2a942cfdef68a5829e97c312cc265e2746bcfbad7aac92f9e",
            PHYSICAL_FIXTURE / "fixture-inventory.tsv": "199936016748f12c09210e905f8fedaf40b3e9e669bacdff71ac7d5554402a54",
            PHYSICAL_FIXTURE / "backup-gse-backup-checkpoint.hex": "1b412803ec3f9294e413157a409a98ec5ce9da68c0b5b70872eb3e9a878c000c",
            PHYSICAL_FIXTURE / "backup-gse-backup-manifest.hex": "9e41ab6b2ccb59b69656939a6a8d5db0545b8fd8bad698800b9c22829e2ffefc",
            PHYSICAL_FIXTURE / "backup-gse-backup-metadata.hex": "e3fe575ad980799f5c29cd6faecbaf6e2b354fd644f8634c2bf4f2655d1cb60f",
            PHYSICAL_FIXTURE / "live-gse-checkpoint-00000000000000000007-00112233445566778899aabbccddeeff.chk.hex": "1b412803ec3f9294e413157a409a98ec5ce9da68c0b5b70872eb3e9a878c000c",
            PHYSICAL_FIXTURE / "live-gse-checkpoint-manifest.hex": "381f6133f4b6adb6197488b8cd25fcef132705e4108d49dcb7fe13aadbf3862b",
            PHYSICAL_FIXTURE / "live-gse-derived-index-00000000000000000007-00000-0123456789abcdeffedcba9876543210.idx.hex": "493f3b099bbaa76c84493c852173892459fb9481dafaeecff9eebfa871394a5a",
            PHYSICAL_FIXTURE / "live-gse-derived-index-00000000000000000007-00001-0123456789abcdeffedcba9876543210.idx.hex": "b5b7a8495e3de25eba9da8f72db44a7dac8e70174f91e04b8aaa7457c3383c99",
            PHYSICAL_FIXTURE / "live-gse-derived-index-00000000000000000007-00002-0123456789abcdeffedcba9876543210.idx.hex": "73d6a2b0b6b257ae5ecaa8ca190c45f9a818f11ed07ffd490cee9aefd4577c56",
            PHYSICAL_FIXTURE / "live-gse-derived-index-00000000000000000007-00003-0123456789abcdeffedcba9876543210.idx.hex": "60cc5efb9462708a0fba527d1e21226a3832b288e9155e5f379efc155b078661",
            PHYSICAL_FIXTURE / "live-gse-derived-manifest.hex": "5ba1df3015dedb557e059ab2715fecaee16c31dfd58a3348371f8147772b5eae",
            PHYSICAL_FIXTURE / "live-gse-metadata.hex": "e3fe575ad980799f5c29cd6faecbaf6e2b354fd644f8634c2bf4f2655d1cb60f",
            PHYSICAL_FIXTURE / "live-gse-wal-00000000000000000002.log.hex": "70202b3dc815ff962bb4301f6a5757de1be501374aedf771a2f4910b8d57ddd2",
        }
        for path, digest in expected.items():
            with self.subTest(path=path.name):
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_physical_and_logical_fixtures_remain_independently_valid(self) -> None:
        validate_logical_fixture(LOGICAL_FIXTURE)
        expected = fixture()
        frozen = load_hex_fixture(PHYSICAL_FIXTURE)
        self.assertEqual(expected, frozen)
        live = inspect_live(frozen.live)
        backup = inspect_backup(frozen.backup)
        self.assertEqual("VALID", live["status"])
        self.assertEqual(4, len(live["components"]))
        self.assertEqual(frozen.catalog_identity, live["identity"])
        self.assertEqual("VALID", backup["status"])
        self.assertEqual(frozen.backup_identity, backup["contentIdentity"])

    def test_fast_reopen_registration_is_exact(self) -> None:
        self.assertEqual(
            {
                "schemaVersion": "gse-v43-fast-reopen-baseline-registry-v1",
                "baselines": [
                    {
                        "medianRatioMicros": 256803,
                        "memberCount": 3,
                        "name": "v4.3.0-fast-reopen-cloud",
                        "preset": "v4.3-fast-reopen-v1",
                        "setDigest": "b91f780d8f630d626f8aec3bc090073a5c4bbd9273819bc437d07c10ff7200c4",
                        "sourceCommit": "1d59ba9c354f5ea5ca4ebc8d8b5b30519479aac6",
                        "suite": "v4.3-fast-reopen-suite-v1",
                    }
                ],
            },
            json.loads(REGISTRY.read_text(encoding="utf-8")),
        )


if __name__ == "__main__":
    unittest.main()
