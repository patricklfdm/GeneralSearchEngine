"""Unit tests for the V4.4 Phase 2 execution map and evidence recorder."""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from scripts.v44.evidence import EvidenceError
from scripts.v44.local_matrix import (
    MAP_PATH,
    load_execution_map,
    record_matrix,
    validate_matrix_evidence,
)


class Phase2MatrixTest(unittest.TestCase):
    SOURCE = "a" * 40

    def test_map_binds_every_frozen_case_to_executed_gates(self) -> None:
        document = load_execution_map()
        self.assertEqual(13, len(document["gates"]))
        self.assertEqual(20, len(document["cases"]))
        self.assertEqual(
            {gate["id"] for gate in document["gates"]},
            {gate_id for case in document["cases"]
             for gate_id in case["gateIds"]},
        )

    def test_exact_receipts_record_and_validate_complete_matrix(self) -> None:
        execution = load_execution_map()
        with tempfile.TemporaryDirectory(prefix="gse-v44-phase2-test-") as root:
            workspace = Path(root)
            receipts = workspace / "receipts"
            receipts.mkdir()
            self._write_receipts(receipts, execution)
            output = workspace / "evidence"

            self.assertEqual(0, record_matrix(argparse.Namespace(
                execution_map=MAP_PATH,
                receipts=receipts,
                output=output,
                source_sha=self.SOURCE,
                source_state="clean",
            )))
            document = validate_matrix_evidence(output)
            self.assertEqual(20, document["measurements"]["caseCount"])
            self.assertEqual(0,
                             document["measurements"]["unexpectedFindingCount"])
            self.assertEqual("PASS_NO_ADMITTED_FINDINGS",
                             document["result"]["phase2Status"])

    def test_missing_receipt_fails_closed(self) -> None:
        execution = load_execution_map()
        with tempfile.TemporaryDirectory(prefix="gse-v44-phase2-test-") as root:
            workspace = Path(root)
            receipts = workspace / "receipts"
            receipts.mkdir()
            self._write_receipts(receipts, execution)
            (receipts / "v44-targeted-junit.receipt").unlink()

            with self.assertRaisesRegex(EvidenceError,
                                        "receipt inventory differs"):
                record_matrix(argparse.Namespace(
                    execution_map=MAP_PATH,
                    receipts=receipts,
                    output=workspace / "evidence",
                    source_sha=self.SOURCE,
                    source_state="clean",
                ))

    def test_tampered_result_fails_checksum_validation(self) -> None:
        execution = load_execution_map()
        with tempfile.TemporaryDirectory(prefix="gse-v44-phase2-test-") as root:
            workspace = Path(root)
            receipts = workspace / "receipts"
            receipts.mkdir()
            self._write_receipts(receipts, execution)
            output = workspace / "evidence"
            record_matrix(argparse.Namespace(
                execution_map=MAP_PATH,
                receipts=receipts,
                output=output,
                source_sha=self.SOURCE,
                source_state="clean",
            ))
            evidence = output / "evidence.json"
            document = json.loads(evidence.read_text(encoding="utf-8"))
            document["case"]["results"][0]["observed"] = "FAIL_CLOSED"
            evidence.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(EvidenceError,
                                        "checksum mismatch"):
                validate_matrix_evidence(output)

    @staticmethod
    def _write_receipts(directory: Path, execution: dict[str, object]) -> None:
        gates = execution["gates"]
        assert isinstance(gates, list)
        for gate in gates:
            assert isinstance(gate, dict)
            gate_id = gate["id"]
            assert isinstance(gate_id, str)
            (directory / f"{gate_id}.receipt").write_text(
                f"gateId={gate_id}\nstatus=PASS\n", encoding="ascii")


if __name__ == "__main__":
    unittest.main()
