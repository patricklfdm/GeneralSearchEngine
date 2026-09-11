"""Tests for the V4.4 Phase 3 finding-admission decision."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.v44.admission import AdmissionError, DECISION_PATH, validate


class Phase3AdmissionTest(unittest.TestCase):
    def test_zero_change_decision_matches_phase2_boundaries(self) -> None:
        document = validate()
        self.assertFalse(document["productionChange"])
        self.assertEqual([], document["acceptedContractViolations"])
        self.assertEqual([], document["acceptedMeasuredRegressions"])
        self.assertEqual(9, len(document["expectedBoundaryCaseIds"]))

    def test_production_change_without_admitted_finding_is_rejected(self) -> None:
        document = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
        document["productionChange"] = True
        with tempfile.TemporaryDirectory(prefix="gse-v44-admission-") as root:
            path = Path(root) / "decision.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(AdmissionError,
                                        "unexpectedly authorizes"):
                validate(path)

    def test_expected_boundary_drift_is_rejected(self) -> None:
        document = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
        document["expectedBoundaryCaseIds"].pop()
        with tempfile.TemporaryDirectory(prefix="gse-v44-admission-") as root:
            path = Path(root) / "decision.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(AdmissionError,
                                        "boundary inventory differs"):
                validate(path)


if __name__ == "__main__":
    unittest.main()
