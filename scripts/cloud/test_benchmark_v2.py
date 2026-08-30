#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import hashlib
import io
from itertools import product
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
        self.orchestration_dir.mkdir(parents=True, exist_ok=True)
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
            groups = ((1, 1), (4, 1), (16, 1)) if raw_schema == 1 and mode == "full" else ((4, 1),)
            for readers, writers in groups:
                latency_name = (
                    f"concurrent-latency-{readers}-{writers}.json"
                    if raw_schema == 1
                    else f"concurrent-read-write-{readers}-{writers}.json"
                )
                (self.raw / latency_name).write_text(
                    json.dumps(
                        [
                            jmh_entry(
                                "sample",
                                benchmark="example.Concurrent.mixed",
                                threads=readers + writers,
                            )
                        ],
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                if raw_schema == 1:
                    (self.raw / f"concurrent-throughput-{readers}-{writers}.json").write_text(
                        json.dumps(
                            [
                                jmh_entry(
                                    "thrpt",
                                    benchmark="example.Concurrent.mixed",
                                    threads=readers + writers,
                                )
                            ],
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
        elif mode == "ranked-v31":
            self._write_v31_ranked()
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
            "concurrency_documents": (
                "1000000" if self.mode == "ranked-v31" else "100000"
            ),
            "concurrency_thread_groups": (
                "1,1 4,1 16,1"
                if self.raw_schema == 1 and self.mode == "full"
                else "16,1" if self.mode == "ranked-v31" else "4,1"
            ),
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
            if self.mode == "full":
                values["benchmark_preset_id"] = "v3-production-full-v1"
            elif self.mode == "ranked-v31":
                values["benchmark_suite"] = "v3.1-ranked-suite-v1"
                values["benchmark_preset_id"] = "v3.1-ranked-v1"
                values["jvm_options"] = "-Xms32g -Xmx64g"
                values["v31_document_counts"] = "100000,1000000"
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
            "boot_disk_type": "pd-balanced",
            "boot_disk_size": "100GB",
            "max_run_duration": (
                "3600s" if self.mode == "ranked-v31" else "43200s"
            ),
            "network": "default",
            "subnet": "",
            "ssh_transport": "external_ip",
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
                "update_mode": "revision",
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

    def _write_v31_ranked(self) -> None:
        package = "io.github.patricklfdm.generalsearch.benchmark.jmh."

        def write(name: str, entries: list[dict]) -> None:
            (self.raw / f"{name}.json").write_text(
                json.dumps(entries, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        write(
            "v31-phrase",
            [
                jmh_entry(
                    benchmark=package + "V31PhraseFeatureBenchmark.search",
                    params={"documentCount": documents, "scenario": scenario},
                )
                for documents, scenario in product(
                    ("100000", "1000000"),
                    (
                        "low-s0", "high-s0", "low-s1", "high-s1",
                        "low-s2", "high-s2", "low-s4", "high-s4",
                        "repeated", "analyzer-gap", "same-position",
                    ),
                )
            ],
        )
        write(
            "v31-bool",
            [
                jmh_entry(
                    benchmark=package + "V31MinimumShouldMatchBenchmark.search",
                    params={
                        "documentCount": documents,
                        "minimum": minimum,
                        "shouldWidth": width,
                        "withMust": with_must,
                    },
                )
                for documents, minimum, width, with_must in product(
                    ("100000", "1000000"),
                    ("one", "half", "all"),
                    ("4", "16", "64"),
                    ("false", "true"),
                )
            ],
        )
        write(
            "v31-fuzzy",
            [
                jmh_entry(
                    benchmark=package + "V31FuzzyDictionaryBenchmark.traverse",
                    params={"scenario": scenario, "vocabularySize": vocabulary},
                )
                for scenario, vocabulary in product(
                    ("short-exact", "long-near", "unicode-near", "sparse-miss", "dense-hit"),
                    ("100000", "1000000"),
                )
            ],
        )
        write(
            "v31-text-build",
            [
                jmh_entry(
                    benchmark=package + "V31TextDictionaryBenchmark.build",
                    params={
                        "mutationBatchSize": "1",
                        "transition": "unchanged",
                        "vocabularySize": vocabulary,
                    },
                )
                for vocabulary in ("100000", "1000000")
            ],
        )
        write(
            "v31-text-publication",
            [
                jmh_entry(
                    benchmark=package + "V31TextDictionaryBenchmark.publish",
                    params={
                        "mutationBatchSize": batch,
                        "transition": transition,
                        "vocabularySize": vocabulary,
                    },
                )
                for batch, transition, vocabulary in product(
                    ("1", "100"),
                    ("unchanged", "added", "removed"),
                    ("100000", "1000000"),
                )
            ],
        )
        concurrency_benchmark = (
            package + "V31ConcurrentMixedWorkloadBenchmark.mixed"
        )
        latency = jmh_entry(
            "sample",
            benchmark=concurrency_benchmark,
            params={"documentCount": "1000000"},
            threads=17,
        )
        latency["secondaryMetrics"].update(
            {
                "snapshotPublications": metric(50.0, "#"),
                "writerQueueMaximum": {
                    **metric(10.0, "#"),
                    "rawData": [[1.0] * 5, [1.0] * 5],
                },
                "writerQueueNonzeroSamples": metric(10.0, "#"),
            }
        )
        throughput = jmh_entry(
            "thrpt",
            benchmark=concurrency_benchmark,
            params={"documentCount": "1000000"},
            threads=17,
        )
        throughput["secondaryMetrics"].update(
            {
                "snapshotPublications": metric(50.0, "#"),
                "writerQueueMaximum": {
                    **metric(10.0, "#"),
                    "rawData": [[1.0] * 5, [1.0] * 5],
                },
                "writerQueueNonzeroSamples": metric(10.0, "#"),
            }
        )
        write("v31-concurrent-latency-16-1", [latency])
        write("v31-concurrent-throughput-16-1", [throughput])

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

    def canonical_set_controls(self):
        return {
            "bootDiskSize": "100GB",
            "bootDiskType": "pd-balanced",
            "externalIp": "true",
            "imageFamily": "ubuntu-2404-lts-amd64",
            "imageProject": "ubuntu-os-cloud",
            "jvmOptions": "-Xms8g -Xmx16g",
            "machineType": "c3d-standard-30",
            "maxRunDuration": "43200s",
            "network": "default",
            "project": "ignored-project",
            "provisioning": "standard",
            "resolvedImage": "ubuntu-2404-noble-amd64-v20260826",
            "resolvedImageCreatedAt": "2026-08-26T04:39:04Z",
            "resolvedImageId": "5563818848645508791",
            "resolvedImageSelfLink": "https://compute.example/images/5563818848645508791",
            "useIap": "false",
            "zone": "us-west4-a",
        }

    def complete_fixture_attempt(self, workspace, slot, fixture):
        intent = v2.begin_set_attempt(workspace, slot)
        intent["pointer"].write_text(str(fixture.orchestration_path.resolve()) + "\n", encoding="utf-8")
        self.assertEqual(0, v2.record_set_attempt(workspace, slot, 0))

    def test_profile_repeat_mode_provisioning_and_preset_matrix(self):
        repository = "https://github.com/patricklfdm/GeneralSearchEngine.git"
        for repeats in (1, 10):
            for mode in (
                "quick",
                "full",
                "concurrency",
                "soak",
                "investigation",
                "stabilized-investigation",
                "ranked-v31",
                "all",
            ):
                with self.subTest(profile="experiment", repeats=repeats, mode=mode):
                    plan = v2.validate_set_plan_inputs(
                        "experiment",
                        repeats,
                        mode,
                        None,
                        repository,
                        COMMIT,
                        {"provisioning": "spot"},
                    )
                    self.assertEqual("experiment", plan["evidenceProfile"])
                    self.assertIsNone(plan["presetId"])
        for repeats in (0, 11):
            self.assert_error(
                v2.EXIT_CONFIG,
                lambda repeats=repeats: v2.validate_set_plan_inputs(
                    "experiment",
                    repeats,
                    "quick",
                    None,
                    repository,
                    COMMIT,
                    {"provisioning": "spot"},
                ),
            )
        for repeats in (3, 10):
            for mode in ("full", "concurrency", "soak", "all"):
                with self.subTest(profile="canonical", repeats=repeats, mode=mode):
                    preset = f"v3-production-{mode}-v1"
                    plan = v2.validate_set_plan_inputs(
                        "canonical",
                        repeats,
                        mode,
                        preset,
                        repository,
                        COMMIT,
                        self.canonical_set_controls(),
                    )
                    self.assertEqual("canonical", plan["evidenceProfile"])
                    self.assertEqual(preset, plan["presetId"])
            ranked = v2.validate_set_plan_inputs(
                "canonical",
                repeats,
                "ranked-v31",
                "v3.1-ranked-v1",
                repository,
                COMMIT,
                self.canonical_set_controls(),
            )
            self.assertEqual("v3.1-ranked-v1", ranked["presetId"])
        for repeats in (1, 2, 11):
            self.assert_error(
                v2.EXIT_CONFIG,
                lambda repeats=repeats: v2.validate_set_plan_inputs(
                    "canonical",
                    repeats,
                    "full",
                    "v3-production-full-v1",
                    repository,
                    COMMIT,
                    self.canonical_set_controls(),
                ),
            )
        for mode in ("quick", "investigation", "stabilized-investigation"):
            self.assert_error(
                v2.EXIT_CONFIG,
                lambda mode=mode: v2.validate_set_plan_inputs(
                    "canonical",
                    3,
                    mode,
                    f"v3-production-{mode}-v1",
                    repository,
                    COMMIT,
                    self.canonical_set_controls(),
                ),
            )
        spot_controls = {**self.canonical_set_controls(), "provisioning": "spot"}
        self.assert_error(
            v2.EXIT_CONFIG,
            lambda: v2.validate_set_plan_inputs(
                "canonical",
                3,
                "full",
                "v3-production-full-v1",
                repository,
                COMMIT,
                spot_controls,
            ),
        )
        for preset in (None, "v3-production-soak-v1", "unknown-preset"):
            self.assert_error(
                v2.EXIT_CONFIG,
                lambda preset=preset: v2.validate_set_plan_inputs(
                    "canonical",
                    3,
                    "full",
                    preset,
                    repository,
                    COMMIT,
                    self.canonical_set_controls(),
                ),
            )

    def test_experiment_preset_must_match_selected_mode(self):
        repository = "https://github.com/patricklfdm/GeneralSearchEngine.git"
        matching = v2.validate_set_plan_inputs(
            "experiment",
            1,
            "full",
            "v3-production-full-v1",
            repository,
            COMMIT,
            {"provisioning": "spot"},
        )
        self.assertEqual("v3-production-full-v1", matching["presetId"])
        self.assert_error(
            v2.EXIT_CONFIG,
            lambda: v2.validate_set_plan_inputs(
                "experiment",
                1,
                "full",
                "v3-production-soak-v1",
                repository,
                COMMIT,
                {"provisioning": "spot"},
            ),
        )
        self.assert_error(
            v2.EXIT_CONFIG,
            lambda: v2.validate_set_plan_inputs(
                "experiment",
                1,
                "full",
                "unknown-preset",
                repository,
                COMMIT,
                {"provisioning": "spot"},
            ),
        )

    def test_existing_canonical_preset_definitions_remain_frozen(self):
        self.assertEqual(
            {
                "mode": "full",
                "threadGroups": "1,1 4,1 16,1",
                "jmh": True,
                "soak": False,
            },
            v2.CANONICAL_PRESETS["v3-production-full-v1"],
        )
        self.assertEqual(
            {
                "mode": "concurrency",
                "threadGroups": "1,1 4,1 8,1 16,1 24,1 30,1",
                "jmh": True,
                "soak": False,
            },
            v2.CANONICAL_PRESETS["v3-production-concurrency-v1"],
        )
        self.assertEqual(
            {
                "mode": "soak",
                "threadGroups": "1,1 4,1 16,1",
                "jmh": False,
                "soak": True,
            },
            v2.CANONICAL_PRESETS["v3-production-soak-v1"],
        )
        self.assertEqual(
            {
                "mode": "all",
                "threadGroups": "1,1 4,1 16,1",
                "jmh": True,
                "soak": True,
            },
            v2.CANONICAL_PRESETS["v3-production-all-v1"],
        )
    def test_profile_is_bound_into_plan_checkpoint_hash(self):
        repository = "https://github.com/patricklfdm/GeneralSearchEngine.git"
        experiment = v2.validate_set_plan_inputs(
            "experiment", 3, "full", "v3-production-full-v1", repository, COMMIT,
            self.canonical_set_controls(),
        )
        canonical = v2.validate_set_plan_inputs(
            "canonical", 3, "full", "v3-production-full-v1", repository, COMMIT,
            self.canonical_set_controls(),
        )
        self.assertNotEqual(
            v2.initial_checkpoint(experiment)["planSha256"],
            v2.initial_checkpoint(canonical)["planSha256"],
        )

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
        self.assertEqual(3, len(sample_p99))
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

    def test_ranked_v31_canonical_matrix_and_auxiliary_evidence(self):
        fixture = Fixture(
            self.root / "ranked",
            run_id="20260828T000000Z-0123456789ab-ranked-v31",
            mode="ranked-v31",
        )
        _, manifest, metrics = v2.derive_manifest(
            fixture.raw,
            evidence_profile="canonical",
        )
        self.assertEqual("VALID_CANONICAL_MEMBER", manifest["status"])
        self.assertTrue(manifest["canonicalEligibility"])
        self.assertEqual("v3.1-ranked-v1", manifest["benchmark"]["presetId"])
        self.assertEqual(
            "v3.1-ranked-suite-v1",
            manifest["suite"]["name"],
        )
        self.assertEqual(84, manifest["benchmark"]["configurationSummary"]["jmhEntryCount"])
        auxiliary_names = {
            item["identity"]["metricName"]
            for item in metrics["metrics"]
            if item["workload"].startswith("v31-concurrent-")
        }
        self.assertTrue(
            {
                "snapshotPublications",
                "writerQueueMaximum",
                "writerQueueNonzeroSamples",
            }.issubset(auxiliary_names)
        )
        queue_maxima = [
            item
            for item in metrics["metrics"]
            if item["identity"]["metricName"] == "writerQueueMaximum"
        ]
        self.assertEqual(2, len(queue_maxima))
        for maximum in queue_maxima:
            self.assertEqual("maximum", maximum["statistic"])
            self.assertEqual(1.0, maximum["canonicalValue"])
            self.assertEqual(
                "secondaryMetrics.writerQueueMaximum.rawData",
                maximum["source"]["field"],
            )
            self.assertNotIn("error", maximum)
            self.assertNotIn("confidence", maximum)
            self.assertEqual(
                {
                    "kind": "maximum-over-jmh-forks-and-iterations",
                    "reportedScoreField": "secondaryMetrics.writerQueueMaximum.score",
                    "sourceField": "secondaryMetrics.writerQueueMaximum.rawData",
                },
                maximum["normalization"],
            )

        incomplete = Fixture(
            self.root / "incomplete",
            run_id="20260828T000000Z-0123456789ab-ranked-v31",
            mode="ranked-v31",
        )
        phrase_path = incomplete.raw / "v31-phrase.json"
        phrase_entries = json.loads(phrase_path.read_text(encoding="utf-8"))
        phrase_path.write_text(
            json.dumps(phrase_entries[:-1], sort_keys=True) + "\n",
            encoding="utf-8",
        )
        incomplete.refresh_checksums()
        self.assert_error(
            v2.EXIT_INVALID_EVIDENCE,
            lambda: v2.derive_manifest(
                incomplete.raw,
                evidence_profile="canonical",
            ),
        )

        malformed = Fixture(
            self.root / "malformed-queue-maximum",
            run_id="20260828T000000Z-0123456789ab-ranked-v31",
            mode="ranked-v31",
        )
        concurrency_path = malformed.raw / "v31-concurrent-throughput-16-1.json"
        concurrency_entries = json.loads(
            concurrency_path.read_text(encoding="utf-8")
        )
        concurrency_entries[0]["secondaryMetrics"]["writerQueueMaximum"][
            "rawData"
        ][1].pop()
        concurrency_path.write_text(
            json.dumps(concurrency_entries, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        malformed.refresh_checksums()
        self.assert_error(
            v2.EXIT_INVALID_EVIDENCE,
            lambda: v2.derive_manifest(
                malformed.raw,
                evidence_profile="canonical",
            ),
        )

    def test_zero_gc_count_synthesizes_stable_zero_gc_time(self):
        missing = Fixture(self.root / "missing", instance="gse-missing-gc-time")
        missing_document = missing.raw / "document-scale.json"
        missing_entries = json.loads(missing_document.read_text(encoding="utf-8"))
        missing_entries[0]["secondaryMetrics"]["gc.count"]["score"] = 0.0
        missing_entries[0]["secondaryMetrics"].pop("gc.time")
        missing_document.write_text(json.dumps(missing_entries, sort_keys=True) + "\n", encoding="utf-8")
        missing.refresh_checksums()

        explicit = Fixture(
            self.root / "explicit",
            run_id="20260828T000001Z-0123456789ab-full",
            instance="gse-explicit-gc-time",
        )
        explicit_document = explicit.raw / "document-scale.json"
        explicit_entries = json.loads(explicit_document.read_text(encoding="utf-8"))
        explicit_entries[0]["secondaryMetrics"]["gc.count"]["score"] = 0.0
        explicit_entries[0]["secondaryMetrics"]["gc.time"]["score"] = 0.0
        explicit_document.write_text(
            json.dumps(explicit_entries, sort_keys=True) + "\n", encoding="utf-8"
        )
        explicit.refresh_checksums()

        _, missing_manifest, missing_metrics = v2.derive_manifest(missing.raw)
        _, explicit_manifest, explicit_metrics = v2.derive_manifest(explicit.raw)
        synthesized = next(
            metric
            for metric in missing_metrics["metrics"]
            if metric["workload"] == "document-scale"
            and metric["identity"]["metricName"] == "gc.time"
        )
        self.assertEqual(0.0, synthesized["sourceValue"])
        self.assertEqual("ms", synthesized["sourceUnit"])
        self.assertEqual(
            {
                "kind": "zero-gc-time-when-count-is-zero",
                "sourceField": "secondaryMetrics.gc.count.score",
            },
            synthesized["normalization"],
        )
        self.assertEqual(
            v2.member_compatibility_key(missing_manifest, missing_metrics),
            v2.member_compatibility_key(explicit_manifest, explicit_metrics),
        )

    def test_missing_gc_time_with_nonzero_count_is_invalid(self):
        fixture = Fixture(self.root, instance="gse-invalid-gc-time")
        document = fixture.raw / "document-scale.json"
        entries = json.loads(document.read_text(encoding="utf-8"))
        entries[0]["secondaryMetrics"].pop("gc.time")
        document.write_text(json.dumps(entries, sort_keys=True) + "\n", encoding="utf-8")
        fixture.refresh_checksums()
        self.assert_error(v2.EXIT_INVALID_EVIDENCE, lambda: v2.derive_manifest(fixture.raw))

    def test_derivation_is_byte_stable_and_idempotent(self):
        fixture = Fixture(self.root)
        output, manifest, _ = v2.derive_manifest(fixture.raw)
        first = {path.name: path.read_bytes() for path in output.iterdir()}
        output_again, manifest_again, _ = v2.derive_manifest(fixture.raw)
        second = {path.name: path.read_bytes() for path in output_again.iterdir()}
        self.assertEqual(first, second)
        self.assertEqual(manifest, manifest_again)

    def test_three_member_set_is_deterministic_and_retains_extremes(self):
        fixtures = []
        for ordinal, score in enumerate((2000.0, 2500.0, 4000.0), 1):
            fixture = Fixture(
                self.root,
                run_id=f"20260828T00000{ordinal}Z-0123456789ab-full",
                instance=f"gse-fixture-{ordinal}",
            )
            document = fixture.raw / "document-scale.json"
            entries = json.loads(document.read_text(encoding="utf-8"))
            entries[0]["primaryMetric"]["score"] = score
            entries[0]["primaryMetric"]["scoreConfidence"] = [score - 1, score + 1]
            entries[0]["primaryMetric"]["rawData"] = [[score]]
            document.write_text(json.dumps(entries, sort_keys=True) + "\n", encoding="utf-8")
            fixture.refresh_checksums()
            fixtures.append(fixture)
        workspace = fixtures[0].results / "sets" / "in-progress" / "fixture-set"
        v2.initialize_set_workspace(
            workspace,
            "canonical",
            3,
            "full",
            "v3-production-full-v1",
            "https://github.com/patricklfdm/GeneralSearchEngine.git",
            COMMIT,
            self.canonical_set_controls(),
        )
        for slot, fixture in enumerate(fixtures, 1):
            self.complete_fixture_attempt(workspace, slot, fixture)
        destination, manifest = v2.finalize_benchmark_set(workspace)
        self.assertEqual("VALID_CANONICAL_SET", manifest["status"])
        self.assertEqual(3, len(manifest["members"]))
        first_bytes = {path.name: path.read_bytes() for path in destination.iterdir()}
        again, again_manifest = v2.finalize_benchmark_set(workspace)
        self.assertEqual(destination, again)
        self.assertEqual(manifest, again_manifest)
        self.assertEqual(first_bytes, {path.name: path.read_bytes() for path in again.iterdir()})
        aggregate = v2.read_json(destination / "aggregate-metrics.json")
        document_primary = next(
            item
            for item in aggregate["metrics"]
            if item["identity"]["workload"] == "document-scale"
            and item["identity"]["metricRole"] == "primary"
        )
        self.assertEqual([2.0, 2.5, 4.0], [item["value"] for item in document_primary["values"]])
        self.assertEqual(2.0, document_primary["minimum"])
        self.assertEqual(2.5, document_primary["median"])
        self.assertEqual(4.0, document_primary["maximum"])
        self.assertEqual(2.0, document_primary["absoluteRange"])
        self.assertEqual(80.0, document_primary["relativeRangePct"])

    def test_aggregate_even_median_zero_and_consensus(self):
        def document(value, categorical):
            return {
                "metrics": [
                    {
                        "canonicalUnit": "count",
                        "canonicalValue": value,
                        "direction": "diagnostic",
                        "id": "m1-numeric",
                        "identity": {"metricName": "growth"},
                        "statistic": "diagnostic_bytes",
                    },
                    {
                        "canonicalUnit": "boolean",
                        "canonicalValue": categorical,
                        "direction": "categorical",
                        "id": "m1-consensus",
                        "identity": {"metricName": "valid"},
                        "statistic": "decision",
                    },
                ]
            }

        aggregate = v2.aggregate_member_metrics(
            "gse-set-v1-test",
            {"name": "v3-production", "schemaVersion": 1},
            [(1, "a", document(-1, True)), (2, "b", document(1, True))],
        )
        numeric = next(item for item in aggregate["metrics"] if item["metricId"] == "m1-numeric")
        consensus = next(item for item in aggregate["metrics"] if item["metricId"] == "m1-consensus")
        self.assertEqual(0.0, numeric["median"])
        self.assertIsNone(numeric["relativeRangePct"])
        self.assertEqual("median_zero", numeric["relativeRangeUnavailableReason"])
        self.assertTrue(consensus["allEqual"])
        self.assertIs(True, consensus["unanimousValue"])

    def test_infrastructure_replacement_is_explicit_and_audited(self):
        fixture = Fixture(self.root)
        workspace = fixture.results / "sets" / "in-progress" / "replacement-set"
        v2.initialize_set_workspace(
            workspace,
            "canonical",
            3,
            "full",
            "v3-production-full-v1",
            "https://github.com/patricklfdm/GeneralSearchEngine.git",
            COMMIT,
            self.canonical_set_controls(),
        )
        intent = v2.begin_set_attempt(workspace, 1)
        fixture.orchestration["primary_exit_code"] = "10"
        fixture.rewrite_orchestration()
        intent["pointer"].write_text(
            str(fixture.orchestration_path.resolve()) + "\n", encoding="utf-8"
        )
        self.assertEqual(10, v2.record_set_attempt(workspace, 1, 10))
        self.assert_error(v2.EXIT_CONFIG, lambda: v2.begin_set_attempt(workspace, 1))
        self.assert_error(
            v2.EXIT_CONFIG,
            lambda: v2.authorize_set_replacement(workspace, 1, "provision failed", False),
        )
        authorization = v2.authorize_set_replacement(
            workspace, 1, "provision failed before benchmark", True
        )
        self.assertTrue(authorization.is_file())
        replacement = v2.begin_set_attempt(workspace, 1)
        self.assertEqual(2, replacement["attempt"])

    def test_member_environment_mismatch_stops_before_later_slot(self):
        first = Fixture(self.root, instance="gse-compatible")
        second = Fixture(
            self.root,
            run_id="20260828T000002Z-0123456789ab-full",
            instance="gse-incompatible",
        )
        second.metadata["java_vm_version"] = "21.0.99+1-LTS"
        second.rewrite_metadata()
        second.refresh_checksums()
        workspace = first.results / "sets" / "in-progress" / "incompatible-set"
        v2.initialize_set_workspace(
            workspace,
            "canonical",
            3,
            "full",
            "v3-production-full-v1",
            "https://github.com/patricklfdm/GeneralSearchEngine.git",
            COMMIT,
            self.canonical_set_controls(),
        )
        self.complete_fixture_attempt(workspace, 1, first)
        intent = v2.begin_set_attempt(workspace, 2)
        intent["pointer"].write_text(str(second.orchestration_path.resolve()) + "\n", encoding="utf-8")
        diagnostics = io.StringIO()
        with contextlib.redirect_stderr(diagnostics):
            self.assertEqual(v2.EXIT_INCOMPATIBLE_SET, v2.record_set_attempt(workspace, 2, 0))
        output = diagnostics.getvalue()
        self.assertIn("reference slot=1, candidate slot=2", output)
        self.assertIn("environmentFingerprint", output)
        self.assertIn("environment.java.vmVersion", output)
        self.assertIn('reference="21.0.8+9-LTS"', output)
        self.assertIn('candidate="21.0.99+1-LTS"', output)
        _, _, checkpoint = v2.load_set_workspace(workspace)
        self.assertEqual("INCOMPATIBLE", checkpoint["state"])
        self.assertEqual("PENDING", checkpoint["slots"][2]["state"])
        self.assert_error(v2.EXIT_CONFIG, lambda: v2.begin_set_attempt(workspace, 3))

    def test_completed_set_detects_artifact_corruption(self):
        fixtures = [
            Fixture(
                self.root,
                run_id=f"20260828T10000{slot}Z-0123456789ab-full",
                instance=f"gse-corruption-{slot}",
            )
            for slot in range(1, 4)
        ]
        workspace = fixtures[0].results / "sets" / "in-progress" / "corruption-set"
        v2.initialize_set_workspace(
            workspace,
            "canonical",
            3,
            "full",
            "v3-production-full-v1",
            "https://github.com/patricklfdm/GeneralSearchEngine.git",
            COMMIT,
            self.canonical_set_controls(),
        )
        for slot, fixture in enumerate(fixtures, 1):
            self.complete_fixture_attempt(workspace, slot, fixture)
        destination, _ = v2.finalize_benchmark_set(workspace)
        (destination / "aggregate-metrics.json").write_text("{}\n", encoding="utf-8")
        self.assert_error(v2.EXIT_CONTRADICTION, lambda: v2.finalize_benchmark_set(workspace))

    def test_running_attempt_without_finalized_pointer_becomes_unresolved(self):
        fixture = Fixture(self.root)
        workspace = fixture.results / "sets" / "in-progress" / "unresolved-set"
        v2.initialize_set_workspace(
            workspace,
            "experiment",
            1,
            "quick",
            None,
            "https://github.com/patricklfdm/GeneralSearchEngine.git",
            COMMIT,
            {"provisioning": "spot"},
        )
        v2.begin_set_attempt(workspace, 1)
        self.assertEqual(v2.EXIT_INCOMPATIBLE_SET, v2.reconcile_running_attempt(workspace))
        _, _, checkpoint = v2.load_set_workspace(workspace)
        self.assertEqual("UNRESOLVED", checkpoint["state"])

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

    def test_environment_fingerprint_normalizes_sub_mib_memory_jitter(self):
        baseline = Fixture(self.root / "baseline", instance="gse-memory-baseline")
        jitter = Fixture(
            self.root / "jitter",
            run_id="20260829T010204Z-0123456789ab-full",
            instance="gse-memory-jitter",
        )
        jitter.metadata["memory_bytes"] = str(int(jitter.metadata["memory_bytes"]) + 8192)
        jitter.rewrite_metadata()
        jitter.refresh_checksums()
        different = Fixture(
            self.root / "different",
            run_id="20260829T010205Z-0123456789ab-full",
            instance="gse-memory-different",
        )
        different.metadata["memory_bytes"] = str(
            int(different.metadata["memory_bytes"]) + 2 * 1024 * 1024
        )
        different.rewrite_metadata()
        different.refresh_checksums()

        _, baseline_manifest, _ = v2.derive_manifest(baseline.raw)
        _, jitter_manifest, _ = v2.derive_manifest(jitter.raw)
        _, different_manifest, _ = v2.derive_manifest(different.raw)
        self.assertNotEqual(
            baseline_manifest["environment"]["memoryBytes"],
            jitter_manifest["environment"]["memoryBytes"],
        )
        self.assertEqual(
            baseline_manifest["environmentFingerprint"], jitter_manifest["environmentFingerprint"]
        )
        self.assertNotEqual(
            baseline_manifest["environmentFingerprint"],
            different_manifest["environmentFingerprint"],
        )

    def test_metric_signature_diagnostics_use_metric_id_sets(self):
        manifest = {
            "benchmark": {"mode": "quick", "presetId": None},
            "benchmarkConfigFingerprint": "sha256:" + "1" * 64,
            "environment": {},
            "environmentFingerprint": "sha256:" + "2" * 64,
            "evidenceProfile": "experiment",
            "source": {"commit": COMMIT, "repository": "repository"},
            "suite": {"name": "v3-production", "schemaVersion": 1},
        }
        shared = {"canonicalValue": 1.0, "id": "m1-shared", "identity": {"metricName": "shared"}}
        reference_only = {
            "canonicalValue": 2.0,
            "id": "m1-reference",
            "identity": {"metricName": "reference"},
        }
        candidate_only = {
            "canonicalValue": 3.0,
            "id": "m1-candidate",
            "identity": {"metricName": "candidate"},
        }
        differences = v2.member_compatibility_differences(
            manifest,
            {"metrics": [shared, reference_only]},
            manifest,
            {"metrics": [candidate_only, shared]},
        )
        self.assertEqual(
            [
                "metricSignatures.missingFromCandidate[m1-reference]",
                "metricSignatures.missingFromReference[m1-candidate]",
            ],
            [path for path, _, _ in differences],
        )

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
        self.assertEqual("v3-production-full-v1", manifest["benchmark"]["presetId"])
        quick = Fixture(self.root / "quick", mode="quick", instance="gse-quick")
        self.assert_error(
            v2.EXIT_CONFIG,
            lambda: v2.derive_manifest(quick.raw, evidence_profile="canonical"),
        )

    def test_canonical_member_requires_matching_versioned_preset(self):
        fixture = Fixture(self.root)
        fixture.metadata.pop("benchmark_preset_id")
        fixture.rewrite_metadata()
        fixture.refresh_checksums()
        self.assert_error(
            v2.EXIT_INVALID_EVIDENCE,
            lambda: v2.derive_manifest(fixture.raw, evidence_profile="canonical"),
        )
        fixture.metadata["benchmark_preset_id"] = "v3-production-concurrency-v1"
        fixture.rewrite_metadata()
        fixture.refresh_checksums()
        self.assert_error(v2.EXIT_INVALID_EVIDENCE, lambda: v2.derive_manifest(fixture.raw))

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
