#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.cloud import benchmark_v2 as v2


COMMIT = "0123456789abcdef0123456789abcdef01234567"


def metric(score, unit, *, percentiles=None, error=1.0):
    return {
        "score": score,
        "scoreError": error,
        "scoreConfidence": [score - 1, score + 1],
        "scorePercentiles": percentiles or {},
        "scoreUnit": unit,
        "rawData": [[score]],
    }


def jmh_entry(mode="avgt", *, benchmark="example.Search.search", params=None, threads=1):
    unit = "ops/s" if mode == "thrpt" else "us/op"
    percentiles = {
        "0.0": 1000.0,
        "50.0": 2000.0,
        "95.0": 3000.0,
        "99.0": 4000.0,
        "100.0": 5000.0,
    }
    primary = metric(2500.0 if mode != "thrpt" else 900.0, unit)
    if mode == "sample":
        primary["scorePercentiles"] = percentiles
    secondary = {
        "gc.alloc.rate": metric(128.0, "MB/sec"),
        "gc.alloc.rate.norm": metric(4096.0, "B/op"),
        "gc.count": metric(2.0, "counts", error="NaN"),
        "gc.time": metric(4.0, "ms"),
    }
    if mode == "sample":
        secondary.update(
            {
                "p0.99": metric(4000.0, unit),
                "read": metric(2200.0, unit, percentiles=percentiles),
                "read:p0.99": metric(4000.0, unit),
                "write": metric(1200.0, unit, percentiles=percentiles),
                "write:p0.99": metric(4000.0, unit),
            }
        )
    elif mode == "thrpt":
        secondary.update({"read": metric(800.0, unit), "write": metric(100.0, unit)})
    return {
        "jmhVersion": "1.37",
        "benchmark": benchmark,
        "mode": mode,
        "threads": threads,
        "forks": 2,
        "warmupIterations": 3,
        "warmupTime": "1 s",
        "warmupBatchSize": 1,
        "measurementIterations": 5,
        "measurementTime": "1 s",
        "measurementBatchSize": 1,
        "params": params or {"documentCount": "100000", "queryType": "TEXT", "topK": "10"},
        "primaryMetric": primary,
        "secondaryMetrics": secondary,
    }


class Fixture:
    def __init__(
        self,
        root: Path,
        run_id: str = "20260828T000000Z-0123456789ab-full",
        *,
        raw_schema: int = 1,
        mode: str = "full",
        instance: str = "gse-fixture-a",
        branch: str = "",
    ) -> None:
        self.results = root / "benchmark-results" / "v3-production"
        self.raw = self.results / run_id
        self.orchestration_dir = self.results / "cloud-orchestration"
        self.raw.mkdir(parents=True)
        self.orchestration_dir.mkdir(parents=True)
        self.instance = instance
        self.raw_schema = raw_schema
        self.mode = mode
        self.metadata = self._metadata(branch)
        self.status = {
            "status": "PASS",
            "mode": mode,
            "started_utc": "20260828T000000Z",
            "finished_utc": "20260828T000100Z",
            "exit_code": "0",
        }
        self._write_properties(self.raw / "metadata.txt", self.metadata, metadata=True)
        self._write_properties(self.raw / "status.properties", self.status)
        (self.raw / "environment.txt").write_text("fixture environment\n", encoding="utf-8")
        if mode in {"full", "quick", "all"}:
            (self.raw / "document-scale.json").write_text(
                json.dumps([jmh_entry()], sort_keys=True) + "\n", encoding="utf-8"
            )
            latency_name = (
                "concurrent-latency-4-1.json"
                if raw_schema == 1
                else "concurrent-read-write-4-1.json"
            )
            (self.raw / latency_name).write_text(
                json.dumps(
                    [jmh_entry("sample", benchmark="example.Concurrent.mixed", threads=5)],
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            if raw_schema == 1:
                (self.raw / "concurrent-throughput-4-1.json").write_text(
                    json.dumps(
                        [jmh_entry("thrpt", benchmark="example.Concurrent.mixed", threads=5)],
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
        elif mode == "concurrency":
            (self.raw / "concurrent-latency-4-1.json").write_text(
                json.dumps(
                    [jmh_entry("sample", benchmark="example.Concurrent.mixed", threads=5)],
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        elif mode in {"soak", "investigation", "stabilized-investigation"}:
            self._write_soak()
        self.orchestration = self._orchestration()
        self.orchestration_path = self.orchestration_dir / f"{instance}.properties"
        self._write_properties(self.orchestration_path, self.orchestration)
        self.refresh_checksums()

    def _metadata(self, branch: str) -> dict[str, str]:
        values = {
            "started_utc": "20260828T000000Z",
            "mode": self.mode,
            "git_commit": COMMIT,
            "git_branch": branch,
            "logical_cpus": "30",
            "java_home": "/usr/lib/jvm/java-21",
            "java_runtime": 'openjdk version "21.0.8"',
            "jvm_options": "-Xms8g -Xmx16g",
            "jmh_forks": "2",
            "jmh_warmups": "3",
            "jmh_iterations": "5",
            "jmh_duration": "1s",
            "concurrency_documents": "100000",
            "concurrency_thread_groups": "4,1",
            "soak_index_cycles": "true",
            "cloud_provider": "gcp",
            "cloud_project": "ignored-project",
            "cloud_zone": "us-west4-a",
            "cloud_machine_type": "c3d-standard-30",
            "cloud_provisioning": "standard",
            "cloud_instance_name": self.instance,
            "cloud_image_project": "ubuntu-os-cloud",
            "cloud_image_family": "ubuntu-2404-lts-amd64",
            "cloud_image": "ubuntu-2404-noble-amd64-v20260826",
            "cloud_image_id": "5563818848645508791",
            "cloud_image_self_link": "https://compute.example/images/5563818848645508791",
            "cloud_image_created_at": "2026-08-26T04:39:04Z",
        }
        if self.raw_schema == 1:
            values.update(
                {
                    "evidence_schema_version": "1",
                    "benchmark_suite": "v3-production",
                    "benchmark_suite_schema_version": "1",
                    "source_repository": "https://github.com/patricklfdm/GeneralSearchEngine.git",
                    "kernel_release": "6.8.0-1030-gcp",
                    "memory_bytes": "128849018880",
                    "cpu_vendor": "AuthenticAMD",
                    "cpu_model": "AMD EPYC 9B14",
                    "cpu_sockets": "1",
                    "cpu_cores_per_socket": "15",
                    "cpu_threads_per_core": "2",
                    "java_vendor": "Eclipse Adoptium",
                    "java_runtime_version": "21.0.8+9-LTS",
                    "java_vm_name": "OpenJDK 64-Bit Server VM",
                    "java_vm_version": "21.0.8+9-LTS",
                }
            )
        return values

    def _orchestration(self) -> dict[str, str]:
        return {
            "provider": "gcp",
            "project": "ignored-project",
            "zone": "us-west4-a",
            "instance_name": self.instance,
            "machine_type": "c3d-standard-30",
            "provisioning": "STANDARD",
            "requested_image_family": "ubuntu-2404-lts-amd64",
            "resolved_image": "ubuntu-2404-noble-amd64-v20260826",
            "resolved_image_id": "5563818848645508791",
            "resolved_image_self_link": "https://compute.example/images/5563818848645508791",
            "resolved_image_created_at": "2026-08-26T04:39:04Z",
            "requested_commit": COMMIT,
            "benchmark_mode": self.mode,
            "remote_commit": COMMIT,
            "orchestrator_started_utc": "20260828T000000Z",
            "orchestrator_finished_utc": "20260828T000200Z",
            "stage": "FINISHED",
            "remote_state": "BENCHMARK_PASS",
            "remote_benchmark_exit_code": "0",
            "artifact_recovered": "true",
            "checksum_verified": "true",
            "preempted": "false",
            "run_complete": "true",
            "primary_exit_code": "0",
            "cleanup_attempted": "true",
            "cleanup_succeeded": "true",
            "local_result_path": str(self.raw),
        }

    def _write_soak(self) -> None:
        soak = self.raw / "soak"
        soak.mkdir()
        self._write_properties(
            soak / "soak-config.properties",
            {
                "corpus_profile": "zipf-en-medium-4",
                "documents": "100000",
                "index_cycles": "true",
                "readers": "16",
                "sample_seconds": "1",
                "seconds": "1800",
                "status": "CONFIGURED",
                "top_k": "10",
                "writers": "1",
            },
        )
        self._write_properties(
            soak / "soak-summary.properties",
            {
                "errors": "0",
                "final_document_count": "100000",
                "gc_count": "1122",
                "gc_time_ms": "2657",
                "read_latency_p99_us": "74692.782",
                "read_ops_per_second": "581.262",
                "status": "PASS",
                "write_latency_p99_us": "14304.000",
                "write_ops_per_second": "85.922",
            },
        )
        self._write_properties(
            soak / "soak-analysis.properties",
            {
                "analysis_version": "1",
                "analysis_status": "VALID",
                "review_required": "false",
                "writer_queue_nonzero_samples": "4",
                "writer_queue_maximum": "1",
                "read_rate_drift_pct": "-5.471923",
                "flag_read_rate_drift": "false",
            },
        )

    @staticmethod
    def _write_properties(path: Path, values: dict[str, str], *, metadata=False) -> None:
        content = "".join(f"{key}={value}\n" for key, value in values.items())
        if metadata:
            content += "working_tree_begin\nworking_tree_end\n"
        path.write_text(content, encoding="utf-8")

    def rewrite_metadata(self) -> None:
        self._write_properties(self.raw / "metadata.txt", self.metadata, metadata=True)

    def rewrite_orchestration(self) -> None:
        self._write_properties(self.orchestration_path, self.orchestration)

    def refresh_checksums(self) -> None:
        lines = []
        for path in sorted(self.raw.rglob("*")):
            if path.is_file() and path.name != "checksums.sha256":
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                lines.append(f"{digest}  ./{path.relative_to(self.raw).as_posix()}\n")
        (self.raw / "checksums.sha256").write_text("".join(lines), encoding="utf-8")


class BenchmarkV2Test(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def assert_error(self, code, callable_):
        with self.assertRaises(v2.BenchmarkV2Error) as caught:
            callable_()
        self.assertEqual(code, caught.exception.exit_code)

    def test_schema1_manifest_metrics_and_raw_immutability(self):
        fixture = Fixture(self.root)
        raw_before = v2.snapshot_raw(fixture.raw)
        output, manifest, metrics = v2.derive_manifest(fixture.raw)
        self.assertEqual("VALID_EXPERIMENT", manifest["status"])
        self.assertFalse(manifest["canonicalEligibility"])
        self.assertIsNotNone(manifest["environmentFingerprint"])
        self.assertIsNone(manifest["source"]["branch"])
        self.assertEqual(raw_before, v2.snapshot_raw(fixture.raw))
        self.assertEqual(output, fixture.results / "derived" / "runs" / fixture.raw.name / "v1")
        self.assertTrue((output / "derived-checksums.sha256").is_file())
        sample_p99 = [
            item
            for item in metrics["metrics"]
            if item["statistic"] == "sample_percentile_99.0"
            and item["identity"]["metricRole"] == "read"
        ]
        self.assertEqual(1, len(sample_p99))
        self.assertEqual("ms/op", sample_p99[0]["canonicalUnit"])
        self.assertEqual(4.0, sample_p99[0]["canonicalValue"])
        avgt_percentiles = [
            item
            for item in metrics["metrics"]
            if item["workload"] == "document-scale"
            and item["statistic"].startswith("sample_percentile")
        ]
        self.assertEqual([], avgt_percentiles)
        nan_errors = [
            item["error"]
            for item in metrics["metrics"]
            if item["identity"]["metricName"] == "gc.count"
        ]
        self.assertTrue(any(item["unavailableReason"] == "source_nan" for item in nan_errors))

    def test_derivation_is_byte_stable_and_idempotent(self):
        fixture = Fixture(self.root)
        output, manifest, _ = v2.derive_manifest(fixture.raw)
        first = {path.name: path.read_bytes() for path in output.iterdir()}
        output_again, manifest_again, _ = v2.derive_manifest(fixture.raw)
        second = {path.name: path.read_bytes() for path in output_again.iterdir()}
        self.assertEqual(first, second)
        self.assertEqual(manifest, manifest_again)

    def test_instance_timestamp_project_and_branch_do_not_change_fingerprints(self):
        first = Fixture(self.root / "a", instance="gse-a", branch="feature-a")
        second = Fixture(
            self.root / "b",
            run_id="20260829T010203Z-0123456789ab-full",
            instance="gse-b",
            branch="feature-b",
        )
        second.metadata["cloud_project"] = "another-project"
        second.rewrite_metadata()
        second.orchestration["project"] = "another-project"
        second.rewrite_orchestration()
        second.refresh_checksums()
        _, left, _ = v2.derive_manifest(first.raw)
        _, right, _ = v2.derive_manifest(second.raw)
        self.assertEqual(left["environmentFingerprint"], right["environmentFingerprint"])
        self.assertEqual(left["benchmarkConfigFingerprint"], right["benchmarkConfigFingerprint"])

    def test_environment_and_configuration_inputs_change_separate_fingerprints(self):
        baseline = Fixture(self.root / "base", instance="gse-base")
        environment = Fixture(self.root / "env", instance="gse-env")
        environment.metadata["java_vm_version"] = "21.0.9+1-LTS"
        environment.rewrite_metadata()
        environment.refresh_checksums()
        configuration = Fixture(self.root / "config", instance="gse-config")
        document = configuration.raw / "document-scale.json"
        entries = json.loads(document.read_text(encoding="utf-8"))
        entries[0]["params"]["topK"] = "100"
        document.write_text(json.dumps(entries, sort_keys=True) + "\n", encoding="utf-8")
        configuration.refresh_checksums()
        _, base_manifest, _ = v2.derive_manifest(baseline.raw)
        _, env_manifest, _ = v2.derive_manifest(environment.raw)
        _, config_manifest, _ = v2.derive_manifest(configuration.raw)
        self.assertNotEqual(
            base_manifest["environmentFingerprint"], env_manifest["environmentFingerprint"]
        )
        self.assertEqual(
            base_manifest["benchmarkConfigFingerprint"], env_manifest["benchmarkConfigFingerprint"]
        )
        self.assertEqual(
            base_manifest["environmentFingerprint"], config_manifest["environmentFingerprint"]
        )
        self.assertNotEqual(
            base_manifest["benchmarkConfigFingerprint"], config_manifest["benchmarkConfigFingerprint"]
        )

    def test_canonical_member_requires_supported_mode(self):
        fixture = Fixture(self.root)
        _, manifest, _ = v2.derive_manifest(fixture.raw, evidence_profile="canonical")
        self.assertEqual("VALID_CANONICAL_MEMBER", manifest["status"])
        self.assertTrue(manifest["canonicalEligibility"])
        quick = Fixture(self.root / "quick", mode="quick", instance="gse-quick")
        self.assert_error(
            v2.EXIT_CONFIG,
            lambda: v2.derive_manifest(quick.raw, evidence_profile="canonical"),
        )

    def test_schema0_explicit_adapter_is_experimental(self):
        fixture = Fixture(self.root, raw_schema=0)
        _, manifest, metrics = v2.derive_manifest(fixture.raw)
        self.assertEqual(0, manifest["suite"]["rawEvidenceSchemaVersion"])
        self.assertIsNone(manifest["environmentFingerprint"])
        self.assertTrue(any("legacy raw schema 0" in warning for warning in manifest["warnings"]))
        self.assertTrue(
            any(item["workload"].startswith("concurrent-read-write") for item in metrics["metrics"])
        )
        self.assert_error(
            v2.EXIT_INVALID_EVIDENCE,
            lambda: v2.derive_manifest(fixture.raw, evidence_profile="canonical"),
        )

    def test_unsupported_schema0_shape_has_stable_error(self):
        fixture = Fixture(self.root, raw_schema=0)
        old = fixture.raw / "document-scale.json"
        old.rename(fixture.raw / "mystery-benchmark.json")
        fixture.refresh_checksums()
        self.assert_error(v2.EXIT_UNSUPPORTED, lambda: v2.derive_manifest(fixture.raw))

    def test_fail_checksum_or_orchestration_contradiction_is_invalid(self):
        fixture = Fixture(self.root)
        fixture.status["status"] = "FAIL"
        fixture.status["exit_code"] = "1"
        fixture._write_properties(fixture.raw / "status.properties", fixture.status)
        fixture.refresh_checksums()
        self.assert_error(v2.EXIT_INVALID_EVIDENCE, lambda: v2.derive_manifest(fixture.raw))
        fixture.status["status"] = "PASS"
        fixture.status["exit_code"] = "0"
        fixture._write_properties(fixture.raw / "status.properties", fixture.status)
        fixture.refresh_checksums()
        with (fixture.raw / "environment.txt").open("a", encoding="utf-8") as target:
            target.write("tampered\n")
        self.assert_error(v2.EXIT_INVALID_EVIDENCE, lambda: v2.derive_manifest(fixture.raw))
        fixture.refresh_checksums()
        fixture.orchestration["remote_commit"] = "f" * 40
        fixture.rewrite_orchestration()
        self.assert_error(v2.EXIT_INVALID_EVIDENCE, lambda: v2.derive_manifest(fixture.raw))

    def test_duplicate_metric_identity_is_rejected(self):
        fixture = Fixture(self.root)
        document = fixture.raw / "document-scale.json"
        entries = json.loads(document.read_text(encoding="utf-8"))
        document.write_text(
            json.dumps([entries[0], entries[0]], sort_keys=True) + "\n", encoding="utf-8"
        )
        fixture.refresh_checksums()
        self.assert_error(v2.EXIT_CONTRADICTION, lambda: v2.derive_manifest(fixture.raw))

    def test_soak_properties_are_normalized_without_log_scraping(self):
        fixture = Fixture(self.root, mode="soak", instance="gse-soak")
        _, manifest, metrics = v2.derive_manifest(fixture.raw)
        by_name = {item["identity"]["metricName"]: item for item in metrics["metrics"]}
        self.assertAlmostEqual(74.692782, by_name["read_latency_p99_us"]["canonicalValue"])
        self.assertEqual("ms/op", by_name["read_latency_p99_us"]["canonicalUnit"])
        self.assertEqual("higher", by_name["read_ops_per_second"]["direction"])
        self.assertEqual("categorical", by_name["errors"]["direction"])
        self.assertEqual("diagnostic", by_name["read_rate_drift_pct"]["direction"])
        self.assertTrue(manifest["benchmark"]["configurationSummary"]["soakConfigured"])

    def test_output_boundary_and_conflicting_derived_file(self):
        fixture = Fixture(self.root)
        self.assert_error(
            v2.EXIT_CONFIG,
            lambda: v2.derive_manifest(fixture.raw, output_directory=fixture.raw / "derived"),
        )
        output = self.root / "custom-output"
        output.mkdir()
        (output / "benchmark-manifest.json").write_text("conflict\n", encoding="utf-8")
        self.assert_error(
            v2.EXIT_CONTRADICTION,
            lambda: v2.derive_manifest(fixture.raw, output_directory=output),
        )


if __name__ == "__main__":
    unittest.main()
