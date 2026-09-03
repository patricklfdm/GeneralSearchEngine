from __future__ import annotations

import base64
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.v4.evidence import EvidenceError
from scripts.v4.storage_inspector import (
    inspect_phase3_directory,
    inspect_phase4_directory,
)

PROJECT = Path(__file__).resolve().parents[2]
FIXTURES = PROJECT / (
    "src/main/resources/io/github/patricklfdm/generalsearch/durability/"
    "v4-format-1.0-fixtures.tsv"
)


def load_fixtures() -> dict[str, list[tuple[str, str, str]]]:
    fixtures: dict[str, list[tuple[str, str, str]]] = {}
    for line in FIXTURES.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        case, name, digest, encoded = line.split("\t")
        fixtures.setdefault(case, []).append((name, digest, encoded))
    return fixtures


def materialize(case: str, directory: Path) -> None:
    for name, digest, encoded in load_fixtures()[case]:
        if name == "-":
            continue
        payload = base64.b64decode(encoded, validate=True)
        if hashlib.sha256(payload).hexdigest() != digest:
            raise AssertionError(f"fixture checksum mismatch: {case}/{name}")
        (directory / name).write_bytes(payload)


class Phase7ReleaseFixtureTest(unittest.TestCase):
    def test_fixture_inventory_and_hashes_are_frozen(self) -> None:
        fixtures = load_fixtures()
        self.assertEqual(
            {
                "fresh",
                "wal-only",
                "checkpoint-only",
                "checkpoint-wal",
                "incomplete-tail",
                "corruption",
            },
            set(fixtures),
        )
        for case in fixtures:
            with tempfile.TemporaryDirectory() as temporary:
                materialize(case, Path(temporary))

    def test_independent_inspector_accepts_wal_fixtures(self) -> None:
        for case in ("wal-only", "incomplete-tail"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                materialize(case, directory)
                inspected = inspect_phase3_directory(directory)
                self.assertEqual(1, inspected["wal"]["lastCompleteSequence"])
                self.assertEqual(
                    "INCOMPLETE_HEADER" if case == "incomplete-tail" else "NONE",
                    inspected["wal"]["terminalTail"],
                )

    def test_independent_inspector_accepts_checkpoint_fixtures(self) -> None:
        expectations = {"checkpoint-only": 1, "checkpoint-wal": 2}
        for case, sequence in expectations.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                materialize(case, directory)
                inspected = inspect_phase4_directory(directory)
                self.assertEqual(sequence, inspected["durableSequence"])
                self.assertEqual(1, inspected["checkpoint"]["liveDocuments"])

    def test_independent_inspector_rejects_corruption_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            materialize("corruption", directory)
            with self.assertRaisesRegex(EvidenceError, "checksum"):
                inspect_phase3_directory(directory)


if __name__ == "__main__":
    unittest.main()
