from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.v42.storage_fixture import load_fixture
from scripts.v42.storage_format_v11 import (
    fixture,
    inspect_backup,
    inspect_store,
    load_hex_fixture,
)


PROJECT = Path(__file__).resolve().parents[2]
STORAGE_FIXTURE = PROJECT / "src/test/resources/compatibility/v42-storage-v11"
MIGRATION_FIXTURE = PROJECT / "src/test/resources/compatibility/v42-migration-v1"
API_FIXTURE = PROJECT / (
    "src/test/resources/compatibility/V42StorageEvolutionPublicApi.java.fixture"
)
REGISTRY = PROJECT / "docs/v4x/v4.2/cloud-benchmark-baselines.json"


class Phase7ReleaseFixtureTest(unittest.TestCase):
    def test_frozen_fixture_file_hashes(self) -> None:
        expected = {
            API_FIXTURE: "19f71f0668c8f97ac3223c5da5a77d5e5555ab44ea3cb644461f18e71dc51cb1",
            STORAGE_FIXTURE / "README.md": "8f93e0dc87f014fd19d3f8a37fb52b45ed41a8b2f8a012a4a6c2597788158ee4",
            STORAGE_FIXTURE / "fixture-identities.properties": "0195e1fd297a25864a38490c7bddd231d48da5b2472fc99fa49f5335b30ad5c3",
            STORAGE_FIXTURE / "fixture-inventory.tsv": "761bb841af93bafe2ad1350a16f6f4cd9b5f036d8ebf70f0bae6e4fda65bb57f",
            STORAGE_FIXTURE / "gse-backup-manifest.hex": "8a811745a6da37725524982a6b86e40e03a0b061fb0e34311ec48f44e80ffcdf",
            STORAGE_FIXTURE / "gse-checkpoint-manifest.hex": "d5e32e44ffd24e844f56df2c6f3704e885edccaa8923abe3da703f1d984032f0",
            STORAGE_FIXTURE / "gse-checkpoint.hex": "a79afd4cb3c223b71befce90a90bc013b0df9bc9441930d107bc002ab7a8220a",
            STORAGE_FIXTURE / "gse-metadata.hex": "b208c000f5542482434111449832759a34f7b0bf050e51ed67a548f6e95c36a2",
            STORAGE_FIXTURE / "gse-wal.hex": "ea8e32d8643b0dc95252c16fb0c57a9902966f04d64df467ab800b760cf356e8",
            MIGRATION_FIXTURE / "README.md": "9b2deaed6f1d70d07dd3187bd6340ca752823a4c9bbad9804484b8796dd9536b",
            MIGRATION_FIXTURE / "backup-v1.1.json": "c17bef2cc62314e16dda406f9e82f8370520e867de86e7eeaf6dec06ef64d3f8",
            MIGRATION_FIXTURE / "fixture-checksums.sha256": "a19afa91748fae0ad8f3d9822408a9e9a19d37252a78d304a4ecb6c684202f5c",
            MIGRATION_FIXTURE / "migration-plan.json": "cafbea9bba88eb0eba0cb0df3174cbb7d3da452d6e90aadc2539268bbb0bde10",
            MIGRATION_FIXTURE / "source-v1.0.json": "2f4df29a19b3f7171edfa505f6cbac48de63ad5bcae8dc69d1b2fd58a06478ee",
            MIGRATION_FIXTURE / "target-v1.1.json": "d5bf3136b66284e38551bdc530b363f349edfcf8a1e4b5e3f6b14559ed6e7905",
        }
        for path, digest in expected.items():
            with self.subTest(path=path.name):
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_storage_fixture_matches_encoder_and_independent_inspector(self) -> None:
        expected = fixture()
        frozen = load_hex_fixture(STORAGE_FIXTURE)
        self.assertEqual(expected, frozen)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = root / "live"
            backup = root / "backup"
            live.mkdir()
            backup.mkdir()
            for name, value in frozen.live.items():
                (live / name).write_bytes(value)
            for name, value in frozen.backup.items():
                (backup / name).write_bytes(value)
            self.assertEqual("VALID", inspect_store(live)["status"])
            inspected = inspect_backup(backup)
            self.assertEqual("VALID", inspected["status"])
            self.assertEqual(frozen.backup_identity, inspected["contentIdentity"])

    def test_logical_migration_fixture_and_registration_are_exact(self) -> None:
        documents = load_fixture(MIGRATION_FIXTURE)
        self.assertEqual(0, documents["source-v1.0.json"]["format"]["minor"])
        self.assertEqual(1, documents["target-v1.1.json"]["format"]["minor"])
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "schemaVersion": "gse-v42-migration-baseline-registry-v1",
                "baselines": [
                    {
                        "memberCount": 3,
                        "name": "v4.2.0-migration-cloud",
                        "preset": "v4.2-storage-evolution-v1",
                        "setDigest": "57abb5394a537faaf551b9182ae5a1669de4703689dfe91e6e08dcd4580f2d75",
                        "sourceCommit": "d0afbb593ab5df468c0b7c4b2622ebc6daa69317",
                        "suite": "v4.2-storage-evolution-suite-v1",
                    }
                ],
            },
            registry,
        )


if __name__ == "__main__":
    unittest.main()
