from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from scripts.v44.cloud_set import (
    BASELINE,
    PRESET,
    REGISTRY_SCHEMA,
    SCHEMA,
    SUITE,
    read_registry,
    register,
    validate_set,
)
from scripts.v44.evidence import EvidenceError, canonical_json, sha256


SOURCE = "6301d855a92a3b2de8d9c338232a520fb9dd2b36"
SET_DIGEST = "f1435bdf528138363986542ecafac563dbee0cf9dbed60f781ada27ff53c6465"
ROOT = Path(__file__).resolve().parents[2]
TRACKED_REGISTRY = ROOT / "docs/v4x/v4.4/cloud-benchmark-baselines.json"


def set_document(profile: str = "canonical") -> dict[str, object]:
    if profile == "canonical":
        writes = [1_025_553, 985_501, 1_022_115]
        reopens = [1_027_857, 1_002_019, 1_018_469]
    else:
        writes = [990_807]
        reopens = [1_035_882]
    members = [{
        "slot": slot,
        "sourceCommit": SOURCE,
        "evidenceSha256": str(slot) * 64,
        "backupContentIdentity": "gse-backup-v3-" + str(slot + 3) * 64,
        "writeRatioMicros": writes[slot - 1],
        "reopenRatioMicros": reopens[slot - 1],
        "result": "PASS",
    } for slot in range(1, len(writes) + 1)]
    return {
        "schemaVersion": SCHEMA, "status": "PASS", "suite": SUITE,
        "preset": PRESET, "profile": profile, "sourceCommit": SOURCE,
        "memberCount": len(members), "serialMembers": True,
        "comparable": True, "allTenFamilies": "PASS",
        "published43Control": "PASS", "replacementHost": "PASS",
        "cleanup": "PASS", "medianWriteRatioMicros": sorted(writes)[len(writes) // 2],
        "maximumWriteRatioMicros": max(writes),
        "medianReopenRatioMicros": sorted(reopens)[len(reopens) // 2],
        "maximumReopenRatioMicros": max(reopens),
        "medianThresholdMicros": 1_200_000,
        "memberThresholdMicros": 1_350_000,
        "canonicalEligible": profile == "canonical", "members": members,
    }


def write_set(path: Path, profile: str = "canonical") -> None:
    path.mkdir()
    evidence = path / "evidence.json"
    evidence.write_bytes(canonical_json(set_document(profile)))
    (path / "artifact-checksums.sha256").write_text(
        f"{sha256(evidence)}  evidence.json\n", encoding="ascii")


class Phase6RegistrationTest(unittest.TestCase):
    def test_registers_one_exact_canonical_entry_and_rejects_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "set"
            registry = root / "registry.json"
            write_set(bundle)
            arguments = argparse.Namespace(
                registry=registry, set_bundle=bundle, name=BASELINE)
            self.assertEqual(0, register(arguments))
            value = read_registry(registry)
            self.assertEqual(REGISTRY_SCHEMA, value["schemaVersion"])
            self.assertEqual(1, len(value["baselines"]))
            entry = value["baselines"][0]
            self.assertEqual(SOURCE, entry["sourceCommit"])
            self.assertEqual(3, entry["memberCount"])
            self.assertEqual(1_022_115, entry["medianWriteRatioMicros"])
            self.assertEqual(1_018_469, entry["medianReopenRatioMicros"])
            with self.assertRaisesRegex(EvidenceError, "already registered"):
                register(arguments)

    def test_rejects_wrong_name_and_noncanonical_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            experiment = root / "experiment"
            write_set(canonical)
            write_set(experiment, "experiment")
            with self.assertRaisesRegex(EvidenceError, "must be named"):
                register(argparse.Namespace(
                    registry=root / "wrong.json", set_bundle=canonical,
                    name="renamed-baseline"))
            with self.assertRaisesRegex(EvidenceError, "only canonical"):
                register(argparse.Namespace(
                    registry=root / "experiment.json", set_bundle=experiment,
                    name=BASELINE))

    def test_registry_shape_and_values_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "registry.json"
            for value in (
                    {"schemaVersion": REGISTRY_SCHEMA, "baselines": {},},
                    {"schemaVersion": REGISTRY_SCHEMA, "baselines": [{
                        "name": BASELINE, "suite": SUITE, "preset": PRESET,
                        "sourceCommit": SOURCE, "setDigest": "x" * 64,
                        "memberCount": 3, "medianWriteRatioMicros": 1,
                        "medianReopenRatioMicros": 1,
                    }]},):
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(EvidenceError):
                    read_registry(path)

    def test_tracked_registration_is_exact(self) -> None:
        value = read_registry(TRACKED_REGISTRY)
        self.assertEqual({
            "schemaVersion": REGISTRY_SCHEMA,
            "baselines": [{
                "name": BASELINE,
                "suite": SUITE,
                "preset": PRESET,
                "sourceCommit": SOURCE,
                "setDigest": SET_DIGEST,
                "memberCount": 3,
                "medianWriteRatioMicros": 1_022_115,
                "medianReopenRatioMicros": 1_018_469,
            }],
        }, value)

    def test_reviewed_set_digest_is_reproducible_when_available(self) -> None:
        bundle = ROOT / (
            "benchmark-results/v44-final-durable/"
            "34824651199-1-canonical/set")
        if bundle.exists():
            self.assertEqual(SET_DIGEST, sha256(bundle / "evidence.json"))
            self.assertEqual("canonical", validate_set(bundle)["profile"])


if __name__ == "__main__":
    unittest.main()
