#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.cloud import benchmark_v2 as v2
from scripts.cloud.test_benchmark_v2 import COMMIT, Fixture


class BenchmarkComparisonV2Test(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results = self.root / "benchmark-results" / "v3-production"
        self.registry = self.root / "baselines.json"
        self.registry.write_bytes(
            v2.canonical_json_bytes(
                {
                    "baselines": {},
                    "kind": "cloud-benchmark-baseline-registry",
                    "schemaVersion": 1,
                }
            )
        )

    def tearDown(self):
        self.temporary.cleanup()

    def assert_error(self, code, callable_):
        with self.assertRaises(v2.BenchmarkV2Error) as caught:
            callable_()
        self.assertEqual(code, caught.exception.exit_code)

    @staticmethod
    def controls(provisioning="standard"):
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
            "provisioning": provisioning,
            "resolvedImage": "ubuntu-2404-noble-amd64-v20260826",
            "resolvedImageCreatedAt": "2026-08-26T04:39:04Z",
            "resolvedImageId": "5563818848645508791",
            "resolvedImageSelfLink": "https://compute.example/images/5563818848645508791",
            "useIap": "false",
            "zone": "us-west4-a",
        }

    def build_set(
        self,
        label,
        score,
        *,
        commit=COMMIT,
        profile="canonical",
        provisioning="standard",
    ):
        repeats = 3 if profile == "canonical" else 1
        fixtures = []
        for slot in range(1, repeats + 1):
            fixture = Fixture(
                self.root,
                run_id=f"20260828T{label}{slot:02d}00Z-{commit[:12]}-full",
                instance=f"gse-{label}-{slot}",
            )
            fixture.metadata["git_commit"] = commit
            fixture.metadata["cloud_provisioning"] = provisioning
            fixture.rewrite_metadata()
            fixture.orchestration["requested_commit"] = commit
            fixture.orchestration["remote_commit"] = commit
            fixture.orchestration["provisioning"] = provisioning.upper()
            fixture.rewrite_orchestration()
            document = fixture.raw / "document-scale.json"
            entries = json.loads(document.read_text(encoding="utf-8"))
            primary = entries[0]["primaryMetric"]
            primary["score"] = score
            primary["scoreConfidence"] = [score - 1, score + 1]
            primary["rawData"] = [[score]]
            document.write_text(json.dumps(entries, sort_keys=True) + "\n", encoding="utf-8")
            fixture.refresh_checksums()
            fixtures.append(fixture)
        workspace = self.results / "sets" / "in-progress" / f"set-{label}"
        v2.initialize_set_workspace(
            workspace,
            profile,
            repeats,
            "full",
            "v3-production-full-v1",
            "https://github.com/patricklfdm/GeneralSearchEngine.git",
            commit,
            self.controls(provisioning),
        )
        for slot, fixture in enumerate(fixtures, 1):
            intent = v2.begin_set_attempt(workspace, slot)
            intent["pointer"].write_text(
                str(fixture.orchestration_path.resolve()) + "\n", encoding="utf-8"
            )
            self.assertEqual(0, v2.record_set_attempt(workspace, slot, 0))
        destination, _ = v2.finalize_benchmark_set(workspace)
        return destination, fixtures

    def test_direct_comparison_is_deterministic_ordered_and_reports_regression(self):
        baseline, _ = self.build_set("0101", 2500.0)
        candidate_commit = "f" * 40
        candidate, _ = self.build_set("0202", 3000.0, commit=candidate_commit)
        output, document, exit_code = v2.compare_benchmarks(
            baseline,
            candidate,
            results_root=self.results,
            registry_path=self.registry,
        )
        self.assertEqual(0, exit_code)
        self.assertEqual("DIRECTLY_COMPARABLE", document["compatibility"]["status"])
        regressions = [
            item for item in document["metrics"] if item["classification"] == "POSSIBLE_REGRESSION"
        ]
        self.assertEqual(1, len(regressions))
        self.assertEqual(20.0, regressions[0]["deltaPct"])
        first = {path.name: path.read_bytes() for path in output.iterdir()}
        self.assertNotIn(str(self.root).encode("utf-8"), first["comparison.json"])
        self.assertNotIn(str(self.root).encode("utf-8"), first["comparison.md"])
        self.assertEqual("a\\|b c\\\\d ", v2.markdown_escape("a|b\nc\\d\x01"))
        output_again, document_again, exit_again = v2.compare_benchmarks(
            baseline,
            candidate,
            results_root=self.results,
            registry_path=self.registry,
        )
        self.assertEqual((document, exit_code), (document_again, exit_again))
        self.assertEqual(first, {path.name: path.read_bytes() for path in output_again.iterdir()})
        reverse, reversed_document, _ = v2.compare_benchmarks(
            candidate,
            baseline,
            results_root=self.results,
            registry_path=self.registry,
        )
        self.assertNotEqual(output, reverse)
        self.assertNotEqual(document["comparisonId"], reversed_document["comparisonId"])

    def test_direct_run_is_incomparable_but_exploratory_is_reported(self):
        baseline, fixtures = self.build_set("0303", 2500.0)
        run = v2.derive_manifest(fixtures[0].raw, evidence_profile="canonical")[0]
        output, document, exit_code = v2.compare_benchmarks(
            run,
            baseline,
            results_root=self.results,
            registry_path=self.registry,
        )
        self.assertEqual(v2.EXIT_INCOMPARABLE, exit_code)
        self.assertEqual("INCOMPARABLE", document["compatibility"]["status"])
        self.assertEqual([], document["metrics"])
        self.assertTrue(output.is_dir())
        _, exploratory, exploratory_exit = v2.compare_benchmarks(
            run,
            baseline,
            results_root=self.results,
            registry_path=self.registry,
            allow_exploratory=True,
        )
        self.assertEqual(0, exploratory_exit)
        self.assertEqual("COMPARABLE_WITH_WARNINGS", exploratory["compatibility"]["status"])
        continuous = [
            item for item in exploratory["metrics"] if item["policyId"] == "continuous-relative-v1"
        ]
        self.assertTrue(continuous)
        self.assertTrue(all(item["classification"] is None for item in continuous))
        self.assertTrue(
            all(item["reason"] == "independent_variation_unavailable" for item in continuous)
        )

    def test_ranked_v31_suite_is_explicitly_incomparable_with_v3_production(self):
        production = Fixture(
            self.root,
            run_id="20260828T070700Z-0123456789ab-full",
            instance="gse-production-suite",
        )
        ranked = Fixture(
            self.root,
            run_id="20260828T080800Z-0123456789ab-ranked-v31",
            mode="ranked-v31",
            instance="gse-ranked-suite",
        )
        production_run = v2.derive_manifest(
            production.raw,
            evidence_profile="canonical",
        )[0]
        ranked_run = v2.derive_manifest(
            ranked.raw,
            evidence_profile="canonical",
        )[0]
        _, document, exit_code = v2.compare_benchmarks(
            production_run,
            ranked_run,
            results_root=self.results,
            registry_path=self.registry,
        )
        self.assertEqual(v2.EXIT_INCOMPARABLE, exit_code)
        self.assertEqual("INCOMPARABLE", document["compatibility"]["status"])
        self.assertIn("suite_mismatch", document["compatibility"]["reasons"])

    def test_legacy_schema_zero_run_remains_explicitly_exploratory(self):
        fixture = Fixture(self.root, raw_schema=0, instance="gse-legacy")
        run = v2.derive_manifest(fixture.raw)[0]
        view = v2.load_comparison_evidence(run, self.results)
        self.assertEqual(0, view["suite"]["schemaVersion"])
        self.assertIsNone(view["environmentFingerprint"])
        _, document, exit_code = v2.compare_benchmarks(
            run,
            run,
            results_root=self.results,
            registry_path=self.registry,
            allow_exploratory=True,
        )
        self.assertEqual(0, exit_code)
        self.assertEqual("COMPARABLE_WITH_WARNINGS", document["compatibility"]["status"])

    def test_exploratory_provisioning_only_is_allowed_but_machine_change_is_not(self):
        canonical, _ = self.build_set("0404", 2500.0)
        spot, _ = self.build_set(
            "0505", 2500.0, profile="experiment", provisioning="spot", commit="e" * 40
        )
        _, document, exit_code = v2.compare_benchmarks(
            canonical,
            spot,
            results_root=self.results,
            registry_path=self.registry,
            allow_exploratory=True,
        )
        self.assertEqual(0, exit_code)
        self.assertEqual("COMPARABLE_WITH_WARNINGS", document["compatibility"]["status"])
        self.assertIn(
            "provisioning_models_differ_comparison_is_exploratory",
            document["compatibility"]["warnings"],
        )
        member_manifest = self.results / v2.read_json(spot / "benchmark-set-manifest.json")["members"][0]["manifestReference"]
        member = v2.read_json(member_manifest)
        member["environment"]["machineType"] = "c3d-standard-60"
        member_manifest.write_bytes(v2.canonical_json_bytes(member))
        self.assert_error(
            v2.EXIT_CONTRADICTION,
            lambda: v2.compare_benchmarks(
                canonical,
                spot,
                results_root=self.results,
                registry_path=self.registry,
                allow_exploratory=True,
            ),
        )

    def test_registry_validation_listing_and_local_binding(self):
        baseline, _ = self.build_set("0606", 2500.0)
        view = v2.validate_set_evidence(baseline, self.results)
        name = "v3.0.0-cloud"
        registry = {
            "baselines": {
                name: {
                    "benchmarkConfigFingerprint": view["benchmarkConfigFingerprint"],
                    "environmentFingerprint": view["environmentFingerprint"],
                    "evidenceProfile": "canonical",
                    "manifestGeneration": "12345678901234567890",
                    "manifestUri": f"gs://gse-benchmark/general-search-engine/sets/{view['id']}/v1/benchmark-set-manifest.json",
                    "releaseLabel": "v3.0.0 reviewed cloud baseline",
                    "setId": view["id"],
                    "setManifestSha256": view["manifestDigest"],
                    "sourceCommit": view["source"]["commit"],
                    "uploadReceiptId": "gse-upload-receipt-v1-" + "a" * 64,
                    "uploadReceiptSha256": "sha256:" + "b" * 64,
                }
            },
            "kind": "cloud-benchmark-baseline-registry",
            "schemaVersion": 1,
        }
        self.registry.write_bytes(v2.canonical_json_bytes(registry))
        self.assertEqual(registry, v2.validate_baseline_registry(self.registry))
        self.assertTrue(
            v2.validate_immutable_baseline_name(
                registry, name, registry["baselines"][name]
            )
        )
        self.assert_error(
            v2.EXIT_REGISTRY,
            lambda: v2.validate_immutable_baseline_name(
                registry, name, {**registry["baselines"][name], "sourceCommit": "f" * 40}
            ),
        )
        self.assertEqual(
            baseline,
            v2.resolve_registry_baseline(name, self.registry, self.results),
        )
        _, document, exit_code = v2.compare_benchmarks(
            name,
            baseline,
            results_root=self.results,
            registry_path=self.registry,
        )
        self.assertEqual(0, exit_code)
        self.assertEqual("DIRECTLY_COMPARABLE", document["compatibility"]["status"])
        registry["baselines"][name]["sourceCommit"] = "f" * 40
        self.registry.write_bytes(v2.canonical_json_bytes(registry))
        self.assert_error(
            v2.EXIT_REGISTRY,
            lambda: v2.resolve_registry_baseline(name, self.registry, self.results),
        )

    def test_policy_thresholds_health_and_diagnostics(self):
        def metric(value, variation, *, direction="lower", statistic="mean_time", name="latency"):
            return {
                "aggregationKind": "median_of_independent_run_values",
                "direction": direction,
                "identity": {"metricName": name},
                "percentile": None,
                "statistic": statistic,
                "unit": "ms/op",
                "value": value,
                "variationPct": variation,
                "variationUnavailableReason": None,
            }

        neutral = v2.classify_metric("m", metric(100, 5), metric(105, 5))
        material = v2.classify_metric("m", metric(100, 5), metric(110, 5))
        higher = v2.classify_metric(
            "m", metric(100, 2, direction="higher", statistic="throughput"), metric(120, 2, direction="higher", statistic="throughput")
        )
        zero = v2.classify_metric("m", metric(0, None), metric(1, 0))
        self.assertEqual("NEUTRAL", neutral["classification"])
        self.assertEqual("POSSIBLE_REGRESSION", material["classification"])
        self.assertEqual("MATERIAL_IMPROVEMENT", higher["classification"])
        self.assertEqual("baseline_median_zero", zero["reason"])
        diagnostic = v2.classify_metric(
            "m", metric(1, 0, direction="diagnostic", statistic="gc_time"), metric(2, 0, direction="diagnostic", statistic="gc_time")
        )
        self.assertIsNone(diagnostic["classification"])
        self.assertEqual("diagnostic-only-v1", diagnostic["policyId"])
        consensus = {
            "aggregationKind": "consensus",
            "direction": "categorical",
            "identity": {"metricName": "review_required"},
            "percentile": None,
            "statistic": "decision",
            "unit": "boolean",
            "variationPct": None,
            "variationUnavailableReason": "categorical_metric",
        }
        healthy = {**consensus, "value": {"allEqual": True, "distinctValues": [False], "unanimousValue": False}}
        review = {**consensus, "value": {"allEqual": True, "distinctValues": [True], "unanimousValue": True}}
        self.assertEqual("WARNING", v2.classify_metric("review", healthy, review)["classification"])
        dominated = v2.classify_metric("m", metric(100, 12), metric(110, 1))
        material_by_variation = v2.classify_metric("m", metric(100, 12), metric(124, 1))
        self.assertEqual("NEUTRAL", dominated["classification"])
        self.assertEqual("POSSIBLE_REGRESSION", material_by_variation["classification"])

    def test_public_wrapper_and_option_order(self):
        baseline, _ = self.build_set("0909", 2500.0)
        candidate, _ = self.build_set("1010", 2500.0, commit="c" * 40)
        repository = Path(__file__).resolve().parents[2]
        environment = dict(os.environ)
        environment["GSE_BENCHMARK_RESULTS_ROOT"] = str(self.results)
        completed = subprocess.run(
            [str(repository / "compare-cloud-benchmark.sh"), str(baseline), str(candidate)],
            cwd=repository,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("Compatibility: DIRECTLY_COMPARABLE", completed.stdout)
        rejected = subprocess.run(
            [
                str(repository / "compare-cloud-benchmark.sh"),
                str(baseline),
                "--allow-exploratory",
                str(candidate),
            ],
            cwd=repository,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(v2.EXIT_CONFIG, rejected.returncode)

    def test_checksum_corruption_and_output_collision_are_rejected(self):
        baseline, _ = self.build_set("0707", 2500.0)
        candidate, _ = self.build_set("0808", 2500.0, commit="d" * 40)
        output, _, _ = v2.compare_benchmarks(
            baseline,
            candidate,
            results_root=self.results,
            registry_path=self.registry,
        )
        (output / "comparison.md").write_text("collision\n", encoding="utf-8")
        self.assert_error(
            v2.EXIT_CONTRADICTION,
            lambda: v2.compare_benchmarks(
                baseline,
                candidate,
                results_root=self.results,
                registry_path=self.registry,
            ),
        )
        aggregate = candidate / "aggregate-metrics.json"
        aggregate.write_text("{}\n", encoding="utf-8")
        self.assert_error(
            v2.EXIT_INVALID_EVIDENCE,
            lambda: v2.load_comparison_evidence(candidate, self.results),
        )


if __name__ == "__main__":
    unittest.main()
