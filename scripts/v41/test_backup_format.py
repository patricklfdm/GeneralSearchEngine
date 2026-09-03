from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.v41.backup_format import (
    BackupFormatError,
    MEMBERS,
    fixture,
    inspect_bundle,
    load_hex_fixture,
)


class BackupFormatTest(unittest.TestCase):
    FIXTURE_ROOT = Path(
        "src/test/resources/compatibility/v41-backup-v1"
    )

    def test_immutable_hex_representations_match_the_independent_encoder(self) -> None:
        expected = fixture()
        frozen = load_hex_fixture(self.FIXTURE_ROOT)
        self.assertEqual(expected.metadata, frozen.metadata)
        self.assertEqual(expected.checkpoint, frozen.checkpoint)
        self.assertEqual(expected.manifest, frozen.manifest)
        self.assertEqual(expected.content_identity, frozen.content_identity)

    def test_materialized_exact_bundle_validates(self) -> None:
        frozen = load_hex_fixture(self.FIXTURE_ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "bundle"
            bundle.mkdir()
            values = {
                "gse-backup-metadata": frozen.metadata,
                "gse-backup-checkpoint": frozen.checkpoint,
                "gse-backup-manifest": frozen.manifest,
            }
            for name, value in values.items():
                (bundle / name).write_bytes(value)
            result = inspect_bundle(bundle)
            self.assertEqual("VALID", result["status"])
            self.assertEqual(7, result["sequence"])
            self.assertEqual(list(MEMBERS), result["members"])
            self.assertEqual(frozen.content_identity, result["contentIdentity"])

    def test_tampering_and_extra_members_fail_closed(self) -> None:
        frozen = load_hex_fixture(self.FIXTURE_ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "bundle"
            bundle.mkdir()
            (bundle / "gse-backup-metadata").write_bytes(frozen.metadata + b"x")
            (bundle / "gse-backup-checkpoint").write_bytes(frozen.checkpoint)
            (bundle / "gse-backup-manifest").write_bytes(frozen.manifest)
            with self.assertRaises(BackupFormatError):
                inspect_bundle(bundle)
            (bundle / "gse-backup-metadata").write_bytes(frozen.metadata)
            (bundle / "unexpected").write_text("x", encoding="ascii")
            with self.assertRaises(BackupFormatError):
                inspect_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
