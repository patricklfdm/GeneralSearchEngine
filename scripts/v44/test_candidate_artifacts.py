from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.v44.candidate_artifacts import (
    CandidateArtifactError,
    read_manifest,
    validate_build,
    validate_directory,
    validate_evidence,
    write_from_evidence,
)
from scripts.v44.canonical_reproducibility import ARTIFACTS, JARS, write_record


class CandidateArtifactsTest(unittest.TestCase):
    def _capture(self, root: Path) -> Path:
        root.mkdir()
        for name in ARTIFACTS:
            (root / name).write_bytes(name.encode("ascii"))
        return root

    def _manifest(self, root: Path) -> tuple[Path, Path]:
        evidence = root / "evidence"
        write_record(self._capture(root / "one"), self._capture(root / "two"),
                     evidence, "d" * 40)
        manifest = root / "candidate-artifacts.sha256"
        write_from_evidence(evidence, manifest)
        return evidence, manifest

    def test_exact_manifest_evidence_directory_and_build_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence, manifest = self._manifest(root)
            values = read_manifest(manifest)
            self.assertEqual(JARS, set(values))
            validate_evidence(manifest, evidence)

            flat = root / "flat"
            flat.mkdir()
            core = root / "core"
            processor = root / "processor"
            core.mkdir()
            processor.mkdir()
            for name in JARS:
                payload = name.encode("ascii")
                (flat / name).write_bytes(payload)
                target = processor if name.startswith(
                    "general-search-engine-processor-") else core
                (target / name).write_bytes(payload)
            validate_directory(manifest, flat)
            validate_build(manifest, core, processor)

    def test_extra_missing_duplicate_malformed_and_wrong_hash_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, manifest = self._manifest(root)
            original = manifest.read_text(encoding="ascii")
            cases = {
                "extra": original + "0" * 64 + "  extra.jar\n",
                "missing": "\n".join(original.splitlines()[:-1]) + "\n",
                "duplicate": "\n".join(
                    original.splitlines()[:-1] + [original.splitlines()[0]]) + "\n",
                "malformed": original.replace("  ", " ", 1),
                "uppercase": original.replace("a", "A", 1),
                "wrong": ("0" if original[0] != "0" else "1") + original[1:],
            }
            for name, contents in cases.items():
                with self.subTest(name=name):
                    manifest.write_text(contents, encoding="ascii")
                    with self.assertRaises(CandidateArtifactError):
                        if name == "wrong":
                            validate_evidence(manifest, root / "evidence")
                        else:
                            read_manifest(manifest)
            manifest.write_text(original, encoding="ascii")

    def test_directory_rejects_noncanonical_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, manifest = self._manifest(root)
            flat = root / "flat"
            flat.mkdir()
            for name in JARS:
                (flat / name).write_bytes(name.encode("ascii"))
            (flat / "unexpected.txt").write_text("unexpected", encoding="ascii")
            with self.assertRaisesRegex(CandidateArtifactError, "inventory"):
                validate_directory(manifest, flat)


if __name__ == "__main__":
    unittest.main()
