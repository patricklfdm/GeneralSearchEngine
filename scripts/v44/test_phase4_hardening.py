#!/usr/bin/env python3
"""Negative and positive contracts for V4.4 Phase 4 local evidence."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from scripts.v44.evidence import EvidenceError, base_document, write_bundle
from scripts.v44.local_hardening import (
    RESULT_KIND,
    STATIC,
    validate_evidence,
    validate_properties,
)


def valid_properties() -> dict[str, str]:
    values = dict(STATIC)
    values.update({
        "durationSeconds": "2",
        "filesystem": "Linux-local-filesystem",
        "measurement.backups": "2",
        "measurement.checkpoints": "4",
        "measurement.concurrentNanos": "2000000000",
        "measurement.reads": "10000",
        "measurement.retainedBytes": "1000000",
        "measurement.searches": "10",
        "measurement.sequence": "2020",
        "measurement.totalNanos": "3000000000",
        "measurement.walBytes": "80",
        "measurement.writes": "2000",
        "oracle.afterContinuation": "b" * 64,
        "oracle.beforeClose": "a" * 64,
        "reopen.maximumNanos": "300",
        "reopen.medianNanos": "200",
        "reopen.samplesNanos": "100,200,300",
        "resource.finalDirectoryBytes": "2000000",
        "resource.gcCount": "2",
        "resource.gcTimeMillis": "3",
        "resource.heapMaximumBytes": str(1024 * 1024 * 1024),
        "resource.heapUsedBytes": "500000000",
        "resource.peakDirectoryBytes": "3000000",
        "resource.processCpuNanos": "1000000000",
    })
    return values


class Phase4HardeningTest(unittest.TestCase):
    def test_exact_local_property_contract_passes(self) -> None:
        checked = validate_properties(valid_properties())
        self.assertEqual([100, 200, 300], checked["samples"])

    def test_operation_cadence_drift_is_rejected(self) -> None:
        values = valid_properties()
        values["measurement.checkpoints"] = "3"
        with self.assertRaisesRegex(EvidenceError, "cadence"):
            validate_properties(values)

    def test_resource_peak_below_final_is_rejected(self) -> None:
        values = valid_properties()
        values["resource.peakDirectoryBytes"] = "1"
        with self.assertRaisesRegex(EvidenceError, "directory peak"):
            validate_properties(values)

    def test_missing_or_bad_semantic_oracle_is_rejected(self) -> None:
        values = valid_properties()
        values["oracle.beforeClose"] = "not-a-digest"
        with self.assertRaisesRegex(EvidenceError, "semantic digest"):
            validate_properties(values)

    def test_phase4_decision_cannot_admit_hidden_optimization(self) -> None:
        document = base_document("1" * 40, "clean", "local-scaffold")
        document.update({
            "kind": RESULT_KIND,
            "measurements": {
                "measurement.writes": 2_000,
                "measurement.sequence": 2_020,
            },
            "result": {
                "productionChange": False,
                "paidExecution": False,
                "phase4Status": "PASS_NO_MEASURED_REGRESSION",
                "admittedOptimization": False,
                "classification": None,
            },
        })
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "evidence"
            write_bundle(bundle, document)
            self.assertEqual(RESULT_KIND, validate_evidence(bundle)["kind"])
            changed = copy.deepcopy(document)
            changed["result"]["admittedOptimization"] = True
            second = Path(temporary) / "hidden-optimization"
            write_bundle(second, changed)
            with self.assertRaisesRegex(EvidenceError, "decision differs"):
                validate_evidence(second)


if __name__ == "__main__":
    unittest.main()
