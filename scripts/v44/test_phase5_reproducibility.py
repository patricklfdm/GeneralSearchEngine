from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.v44.canonical_reproducibility import (
    ARTIFACTS,
    ReproducibilityError,
    validate_record,
    write_record,
)
from scripts.v44.toolchain_manifest import ROOT, validate as validate_toolchain


class Phase5ReproducibilityTest(unittest.TestCase):
    def _capture(self, root: Path, suffix: bytes = b"") -> Path:
        root.mkdir()
        for name in ARTIFACTS:
            (root / name).write_bytes(name.encode("ascii") + suffix)
        return root

    def test_two_identical_exact_inventories_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "evidence"
            value = write_record(self._capture(root / "one"),
                                 self._capture(root / "two"), output, "a" * 40)
            self.assertEqual(6, value["canonicalJarCount"])
            self.assertEqual(2, value["canonicalPomCount"])
            self.assertEqual("EXACT_UNSIGNED_BYTE_IDENTITY", value["claim"])

    def test_workspace_byte_difference_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ReproducibilityError, "hashes differ"):
                write_record(self._capture(root / "one"),
                             self._capture(root / "two", b"changed"),
                             root / "evidence", "b" * 40)

    def test_tampered_record_fails_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "evidence"
            write_record(self._capture(root / "one"),
                         self._capture(root / "two"), output, "c" * 40)
            document = json.loads((output / "evidence.json").read_text())
            document["canonicalJarCount"] = 5
            (output / "evidence.json").write_text(json.dumps(document))
            with self.assertRaisesRegex(ReproducibilityError, "checksum"):
                validate_record(output)

    def test_canonical_maven_bootstrap_is_cache_independent(self) -> None:
        toolchain = validate_toolchain(
            ROOT / "docs/v4x/v4.4/release-toolchain.json")
        wrapper = toolchain["mavenWrapper"]
        self.assertEqual("host-download-read-only-mount",
                         wrapper["canonicalAcquisition"])
        self.assertEqual("jdk-jar", wrapper["canonicalExtraction"])
        self.assertEqual("direct-maven-binary",
                         wrapper["canonicalInvocation"])


if __name__ == "__main__":
    unittest.main()
