from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.v43.derived_fixture import FixtureError, classify, validate


FIXTURE = Path("src/test/resources/compatibility/v43-derived-model-v1")


class DerivedFixtureTest(unittest.TestCase):
    def test_frozen_fixture_passes(self) -> None:
        document = validate(FIXTURE)
        self.assertEqual(10, len(document["cases"]))

    def test_classification_does_not_hide_canonical_failure(self) -> None:
        with self.assertRaisesRegex(FixtureError, "canonical"):
            classify({"canonicalAuthority": "CORRUPT", "formatMinor": 2,
                      "catalog": "VALID", "components": []})

    def test_checksum_tampering_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for source in FIXTURE.iterdir():
                (root / source.name).write_bytes(source.read_bytes())
            document = json.loads((root / "logical-fixtures.json").read_text())
            document["cases"][0]["expected"] = "VALID"
            (root / "logical-fixtures.json").write_text(
                json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(FixtureError, "checksum"):
                validate(root)


if __name__ == "__main__":
    unittest.main()
