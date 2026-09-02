from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts.v4.durable_cloud_lane import fake_run
from scripts.v4.durable_performance import validate_properties
from scripts.v4.evidence import EvidenceError, validate_bundle


class Phase6PerformanceTest(unittest.TestCase):
    def test_frozen_properties_accept_complete_smoke_result(self) -> None:
        properties = self.properties()
        validated = validate_properties(properties, "smoke")
        self.assertEqual("smoke", validated["profile"])

    def test_latency_distribution_must_be_ordered(self) -> None:
        properties = self.properties()
        properties["mutation.durable.single.p95Nanos"] = "2"
        properties["mutation.durable.single.p50Nanos"] = "3"
        with self.assertRaisesRegex(EvidenceError, "latency distribution"):
            validate_properties(properties, "smoke")

    def test_force_units_must_match_submitted_producer_work(self) -> None:
        properties = self.properties()
        properties["groupCommit.forcedUnits"] = "7"
        with self.assertRaisesRegex(EvidenceError, "force-group"):
            validate_properties(properties, "smoke")

    def test_load_batch_size_is_required_and_positive(self) -> None:
        properties = self.properties()
        properties.pop("loadBatchSize")
        with self.assertRaisesRegex(EvidenceError, "loadBatchSize"):
            validate_properties(properties, "smoke")

        properties["loadBatchSize"] = "0"
        with self.assertRaisesRegex(EvidenceError, "loadBatchSize"):
            validate_properties(properties, "smoke")

    def test_phase6_fake_cloud_keeps_independent_durable_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "phase6-cloud"
            self.assertEqual(0, fake_run(Namespace(
                output=output,
                source_sha="6" * 40,
                source_state="clean",
                profile="canonical",
                phase="phase6-performance",
            )))
            evidence = validate_bundle(output)
            self.assertEqual(
                "v4.0-durable-single-node-suite-v1",
                evidence["environment"]["suite"],
            )
            self.assertEqual(3, evidence["environment"]["slots"])
            self.assertEqual(
                "SIMULATED_PASS", evidence["result"]["durablePerformance"]
            )
            self.assertEqual("PASS", evidence["cleanup"]["status"])

    @staticmethod
    def properties() -> dict[str, str]:
        values = {
            "schemaVersion": "gse-v40-performance-properties-v1",
            "status": "PASS",
            "profile": "smoke",
            "codecId": "v40-performance-codec-v1",
            "codecVersion": "1",
            "storageIdentity": "v40-performance-store-v1",
            "schemaIdentity": "v40-performance-schema-v1",
            "documents": "1000",
            "singleOperations": "40",
            "bulkOperations": "10",
            "bulkSize": "20",
            "loadBatchSize": "500",
            "producers": "4",
            "producerOperations": "20",
            "longRunSeconds": "1",
            "compatibility.inMemoryChecksum": "123",
            "compatibility.durableChecksum": "123",
            "groupCommit.forceGroups": "20",
            "groupCommit.forcedUnits": "80",
            "groupCommit.maximumGroupSize": "4",
            "groupCommit.elapsedNanos": "100",
            "groupCommit.averageGroupSizeMicros": "4000000",
            "groupCommit.walAppendForceNanos": "80",
            "checkpoint.elapsedNanos": "100",
            "checkpoint.processCpuNanos": "90",
            "checkpoint.retainedBeforeBytes": "2000",
            "checkpoint.temporaryPeakBytes": "3000",
            "checkpoint.retainedAfterBytes": "1500",
            "checkpoint.encodedCorpusBytes": "1000",
            "checkpoint.retainedAmplificationMicros": "1500000",
            "checkpoint.temporaryAmplificationMicros": "3000000",
            "longRun.elapsedNanos": "1000",
            "longRun.reads": "20",
            "longRun.writes": "10",
            "longRun.checkpoints": "2",
            "longRun.maximumRetainedBytes": "3000",
            "longRun.finalRetainedBytes": "1500",
            "longRun.finalSequence": "11",
            "longRun.status": "OPEN",
        }
        for prefix, source in (
            ("recovery.walOnly", "WAL_ONLY"),
            ("recovery.checkpointOnly", "CHECKPOINT_ONLY"),
            ("recovery.checkpointAndWal", "CHECKPOINT_AND_WAL"),
        ):
            values[f"{prefix}.source"] = source
            for suffix in (
                "documents",
                "replayedRecords",
                "totalOpenNanos",
                "reportedRecoveryNanos",
                "storageOpenNanos",
                "checkpointLoadNanos",
                "replayAndRebuildNanos",
                "indexRebuildNanos",
                "retainedBytes",
                "walBytes",
            ):
                values[f"{prefix}.{suffix}"] = "1"
        for prefix in (
            "mutation.inMemory.single",
            "mutation.durable.single",
            "mutation.inMemory.bulk",
            "mutation.durable.bulk",
        ):
            values[f"{prefix}.count"] = "10"
            values[f"{prefix}.meanNanos"] = "2"
            values[f"{prefix}.p50Nanos"] = "1"
            values[f"{prefix}.p95Nanos"] = "2"
            values[f"{prefix}.p99Nanos"] = "3"
            values[f"{prefix}.maxNanos"] = "4"
        return values


if __name__ == "__main__":
    unittest.main()
