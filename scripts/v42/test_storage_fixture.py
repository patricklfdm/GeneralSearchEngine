from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.v42.storage_fixture import FixtureError, load_fixture


FIXTURE = Path("src/test/resources/compatibility/v42-migration-v1")


class StorageFixtureTest(unittest.TestCase):
    def test_immutable_dual_minor_logical_fixture_passes(self) -> None:
        documents = load_fixture(FIXTURE)
        self.assertEqual(17, documents["source-v1.0.json"]["sequence"])
        self.assertEqual(1, documents["target-v1.1.json"]["format"]["minor"])
        self.assertEqual("PHASE2_PENDING",
                         documents["backup-v1.1.json"]["physicalEncodingStatus"])

    def test_checksum_mutation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "fixture"
            shutil.copytree(FIXTURE, copied)
            with (copied / "source-v1.0.json").open("ab") as stream:
                stream.write(b" ")
            with self.assertRaisesRegex(FixtureError, "checksum"):
                load_fixture(copied)

    def test_projection_mutation_fails_after_rebinding_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "fixture"
            shutil.copytree(FIXTURE, copied)
            target = copied / "target-v1.1.json"
            value = json.loads(target.read_text(encoding="utf-8"))
            value["records"][0]["document"] = "changed"
            target.write_text(json.dumps(value, sort_keys=True,
                                         separators=(",", ":")) + "\n",
                              encoding="utf-8")
            from scripts.v42.storage_fixture import JSON_MEMBERS, sha256
            (copied / "fixture-checksums.sha256").write_text("".join(
                f"{sha256(copied / name)}  {name}\n" for name in JSON_MEMBERS),
                encoding="ascii")
            with self.assertRaisesRegex(FixtureError, "projection"):
                load_fixture(copied)


if __name__ == "__main__":
    unittest.main()
