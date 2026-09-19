from __future__ import annotations

import tempfile
import unittest
import json
import hashlib
import io
import tarfile
from pathlib import Path

from scripts.v50.candidate_artifacts import (
    CandidateArtifactError,
    read_manifest,
    validate_build,
    validate_directory,
    validate_evidence,
    write_from_evidence,
)
from scripts.v50.canonical_reproducibility import (
    ARTIFACTS, JARS, ReproducibilityError, git_source_mode, validate_record, write_record,
)


class CandidateArtifactsTest(unittest.TestCase):
    def test_local_read_write_modes_do_not_change_source_archive_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "Source.java"
            source.write_text("class Source {}\n")
            archives = []
            for mode in (0o600, 0o640, 0o644, 0o664):
                source.chmod(mode)
                buffer = io.BytesIO()
                with tarfile.open(fileobj=buffer, mode="w") as archive:
                    archive.add(source, arcname=source.name, filter=git_source_mode)
                archives.append(buffer.getvalue())
            self.assertEqual(1, len(set(archives)))
            with tarfile.open(fileobj=io.BytesIO(archives[0])) as archive:
                member = archive.getmember(source.name)
                self.assertEqual(0o644, member.mode)
                self.assertEqual(source.read_bytes(), archive.extractfile(member).read())

    def test_source_archive_preserves_git_executable_bit(self) -> None:
        for mode in (0o700, 0o750, 0o755, 0o775):
            member = tarfile.TarInfo("mvnw")
            member.mode = mode
            self.assertEqual(0o755, git_source_mode(member).mode)

    def _capture(self, root: Path) -> Path:
        root.mkdir()
        for name in ARTIFACTS:
            (root / name).write_bytes(name.encode("ascii"))
        return root

    def _manifest(self, root: Path) -> tuple[Path, Path]:
        evidence = root / "evidence"
        write_record(self._capture(root / "one"), self._capture(root / "two"),
                     evidence, {"kind": "git-commit", "commit": "d" * 40,
                                "archiveSha256": "e" * 64})
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
            replication = root / "replication"
            core.mkdir()
            processor.mkdir()
            replication.mkdir()
            for name in JARS:
                payload = name.encode("ascii")
                (flat / name).write_bytes(payload)
                target = processor if name.startswith(
                    "general-search-engine-processor-") else core
                if name.startswith("general-search-engine-replication-"):
                    target = replication
                (target / name).write_bytes(payload)
            validate_directory(manifest, flat)
            validate_build(manifest, core, processor, replication)

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

    def test_replication_bytes_and_missing_member_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, manifest = self._manifest(root)
            flat = root / "flat"
            flat.mkdir()
            for name in JARS:
                (flat / name).write_bytes(name.encode("ascii"))
            member = flat / "general-search-engine-replication-5.0.0.jar"
            member.write_bytes(b"different replication runtime")
            with self.assertRaisesRegex(CandidateArtifactError, "hashes differ"):
                validate_directory(manifest, flat)
            member.unlink()
            with self.assertRaisesRegex(CandidateArtifactError, "inventory"):
                validate_directory(manifest, flat)
            member.symlink_to(root / "one" / member.name)
            with self.assertRaisesRegex(CandidateArtifactError, "inventory"):
                validate_directory(manifest, flat)

    def test_two_workspaces_must_match_including_replication_pom(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            one, two = self._capture(root / "one"), self._capture(root / "two")
            (two / "general-search-engine-replication.pom").write_bytes(b"different dependency")
            with self.assertRaisesRegex(ReproducibilityError, "workspace hashes differ"):
                write_record(one, two, root / "evidence", {
                    "kind": "git-commit", "commit": "d" * 40, "archiveSha256": "e" * 64})

    def test_resealed_invalid_provenance_or_toolchain_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence, _ = self._manifest(root)
            original = json.loads((evidence / "evidence.json").read_text())
            for field, value in (("source", {"commit": "d" * 40}),
                                 ("containerPlatformDigest", "sha256:" + "0" * 64),
                                 ("independentCleanWorkspaces", 1)):
                document = dict(original)
                document[field] = value
                payload = json.dumps(document).encode()
                (evidence / "evidence.json").write_bytes(payload)
                (evidence / "artifact-checksums.sha256").write_text(
                    hashlib.sha256(payload).hexdigest() + "  evidence.json\n")
                with self.subTest(field=field), self.assertRaises(ReproducibilityError):
                    validate_record(evidence)

    def test_local_uncommitted_source_is_explicit_in_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = {"kind": "working-tree", "commit": "d" * 40, "archiveSha256": "e" * 64}
            record = write_record(self._capture(root / "one"), self._capture(root / "two"),
                                  root / "evidence", source)
            self.assertEqual(source, record["source"])
            self.assertNotIn("sourceCommit", record)


if __name__ == "__main__":
    unittest.main()
