from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts.cloud import cloud_workflow_v2 as workflow


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CloudWorkflowV2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()
        subprocess.run(["git", "-C", str(self.repository), "init", "-b", "master", "--quiet"], check=True)
        subprocess.run(["git", "-C", str(self.repository), "config", "user.name", "Workflow Test"], check=True)
        subprocess.run(["git", "-C", str(self.repository), "config", "user.email", "workflow@example.test"], check=True)
        (self.repository / "tracked.txt").write_text("trusted\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repository), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repository), "commit", "--quiet", "-m", "trusted"], check=True)
        self.commit = self.git("rev-parse", "HEAD")
        subprocess.run(["git", "-C", str(self.repository), "remote", "add", "origin", workflow.REPOSITORY], check=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.repository), *arguments],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()

    def options(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "evidence_profile": "experiment",
            "mode": "quick",
            "repeats": "1",
            "provisioning": "spot",
            "machine_type": "c3d-standard-30",
            "soak_duration": "30m",
            "retention": "actions",
            "source_commit": "",
            "dispatch_sha": self.commit,
            "repository_root": str(self.repository),
            "trusted_ref": "master",
            "run_id": "1234",
            "run_attempt": "2",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def plan(self, **overrides: object) -> dict:
        return workflow.make_plan(self.options(**overrides))

    def test_experiment_and_canonical_matrix_edges(self) -> None:
        with mock.patch.object(workflow, "validate_source"):
            for mode in ("quick", "full", "concurrency", "soak", "all"):
                for repeats in ("1", "3", "5"):
                    for provisioning in ("spot", "standard"):
                        for retention in ("actions", "gcs"):
                            plan = self.plan(
                                mode=mode,
                                repeats=repeats,
                                provisioning=provisioning,
                                retention=retention,
                            )
                            self.assertEqual("experiment", plan["request"]["evidenceProfile"])
            for mode in ("full", "concurrency", "soak", "all"):
                for repeats in ("3", "5"):
                    plan = self.plan(
                        evidence_profile="canonical",
                        mode=mode,
                        repeats=repeats,
                        provisioning="standard",
                        retention="gcs",
                    )
                    self.assertEqual(f"v3-production-{mode}-v1", plan["derived"]["presetId"])

    def test_invalid_matrix_is_rejected(self) -> None:
        invalid = (
            {"evidence_profile": "canonical", "mode": "quick", "repeats": "3", "provisioning": "standard", "retention": "gcs"},
            {"evidence_profile": "canonical", "mode": "full", "repeats": "1", "provisioning": "standard", "retention": "gcs"},
            {"evidence_profile": "canonical", "mode": "full", "repeats": "3", "provisioning": "spot", "retention": "gcs"},
            {"evidence_profile": "canonical", "mode": "full", "repeats": "3", "provisioning": "standard", "retention": "actions"},
            {"mode": "quick", "soak_duration": "2h"},
            {"mode": "soak", "repeats": "3", "soak_duration": "2h"},
            {"mode": "invalid"},
            {"machine_type": "n2-standard-30"},
            {"retention": "shell"},
        )
        with mock.patch.object(workflow, "validate_source"):
            for values in invalid:
                with self.subTest(values=values), self.assertRaises(workflow.WorkflowError):
                    self.plan(**values)

    def test_two_hour_single_experiment_soak_and_all_are_accepted(self) -> None:
        with mock.patch.object(workflow, "validate_source"):
            for mode in ("soak", "all"):
                plan = self.plan(mode=mode, soak_duration="2h")
                self.assertEqual(7200, plan["derived"]["soakSeconds"])

    def test_source_must_be_exact_protected_master_ancestor(self) -> None:
        trusted = self.plan()
        self.assertEqual(self.commit, trusted["source"]["commit"])
        self.git("switch", "-c", "unprotected")
        (self.repository / "branch.txt").write_text("branch\n", encoding="utf-8")
        self.git("add", "branch.txt")
        self.git("commit", "--quiet", "-m", "unprotected")
        untrusted = self.git("rev-parse", "HEAD")
        with self.assertRaisesRegex(workflow.WorkflowError, "protected master"):
            self.plan(source_commit=untrusted)
        with self.assertRaisesRegex(workflow.WorkflowError, "40-character"):
            self.plan(source_commit="master")

    def test_wrong_origin_is_rejected(self) -> None:
        self.git("remote", "set-url", "origin", "https://github.com/example/other.git")
        with self.assertRaisesRegex(workflow.WorkflowError, "reviewed GeneralSearchEngine"):
            self.plan()

    def test_environment_validation_and_gcs_requirement(self) -> None:
        environment = {
            "GSE_CLOUD_WIF_PROVIDER": "projects/123456/locations/global/workloadIdentityPools/gse-pool/providers/github-provider",
            "GSE_CLOUD_SERVICE_ACCOUNT": "gse-benchmark@gse-benchmark.iam.gserviceaccount.com",
            "GSE_GCP_PROJECT": "gse-benchmark",
            "GSE_GCP_ZONE": "us-west4-a",
            "GSE_CLOUD_IMAGE": "ubuntu-2404-noble-amd64-v20260826",
            "GSE_BENCHMARK_GCS_BUCKET": "gs://gse-benchmark-evidence",
        }
        workflow.validate_config(self.plan(), environment)
        workflow.validate_config(self.plan(retention="gcs"), environment)
        for name in (
            "GSE_CLOUD_WIF_PROVIDER",
            "GSE_CLOUD_SERVICE_ACCOUNT",
            "GSE_GCP_PROJECT",
            "GSE_GCP_ZONE",
            "GSE_CLOUD_IMAGE",
        ):
            invalid = dict(environment)
            invalid[name] = "bad\nvalue"
            with self.subTest(name=name), self.assertRaises(workflow.WorkflowError):
                workflow.validate_config(self.plan(), invalid)
        missing_bucket = dict(environment)
        missing_bucket["GSE_BENCHMARK_GCS_BUCKET"] = ""
        with self.assertRaisesRegex(workflow.WorkflowError, "gs://bucket"):
            workflow.validate_config(self.plan(retention="gcs"), missing_bucket)

    def create_set(self, plan: dict, *, unexpected: bool = False) -> tuple[Path, dict]:
        results = self.root / "results"
        set_id = "gse-set-v1-" + "a" * 64
        set_root = results / "sets" / set_id / "v1"
        set_root.mkdir(parents=True)
        members = []
        for slot in range(1, plan["request"]["repeats"] + 1):
            run_id = f"run-{slot}"
            derived = results / "derived" / "runs" / run_id / "v1"
            derived.mkdir(parents=True)
            for name in workflow.DERIVED_FILES:
                (derived / name).write_text(f"{name}-{slot}\n", encoding="utf-8")
            orchestration = results / "cloud-orchestration" / f"instance-{slot}.properties"
            orchestration.parent.mkdir(exist_ok=True)
            orchestration.write_text("status=PASS\n", encoding="utf-8")
            orchestration.with_suffix(".log").write_text("bounded log\n", encoding="utf-8")
            members.append(
                {
                    "manifestReference": (derived / "benchmark-manifest.json").relative_to(results).as_posix(),
                    "metricsReference": (derived / "normalized-metrics.json").relative_to(results).as_posix(),
                    "orchestrationReference": orchestration.relative_to(results).as_posix(),
                    "rawRunId": run_id,
                    "slot": slot,
                }
            )
        manifest = {
            "evidenceProfile": plan["request"]["evidenceProfile"],
            "kind": "benchmark-set",
            "members": members,
            "mode": plan["request"]["mode"],
            "setId": set_id,
            "source": {"commit": plan["source"]["commit"], "repository": workflow.REPOSITORY},
            "status": "VALID_CANONICAL_SET" if plan["request"]["evidenceProfile"] == "canonical" else "VALID_EXPERIMENT_SET",
        }
        write_json(set_root / "benchmark-set-manifest.json", manifest)
        write_json(set_root / "aggregate-metrics.json", {"metrics": []})
        write_json(set_root / "set-attempt-audit.json", {"slots": []})
        lines = [
            f"{checksum(set_root / name)}  {name}"
            for name in workflow.SET_FILES[:3]
        ]
        (set_root / "set-checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
        if unexpected:
            (set_root / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
        return results, manifest

    def create_result(self, plan: dict, results: Path) -> tuple[Path, dict]:
        options = argparse.Namespace(
            plan=str(self.root / "workflow-plan.json"),
            results_root=str(results),
            dry_run_exit="0",
            benchmark_exit="0",
        )
        write_json(Path(options.plan), plan)
        result = workflow.benchmark_result(options)
        path = self.root / "workflow-result.json"
        write_json(path, result)
        return path, result

    def test_completed_set_discovery_and_checksum_gate(self) -> None:
        plan = self.plan()
        results, manifest = self.create_set(plan)
        root, located = workflow.locate_set(results, plan)
        self.assertEqual(manifest["setId"], located["setId"])
        self.assertEqual("v1", root.name)
        (root / "aggregate-metrics.json").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(workflow.WorkflowError, "Checksum"):
            workflow.locate_set(results, plan)

    def test_completed_set_rejects_unexpected_files_and_ambiguity(self) -> None:
        plan = self.plan()
        results, _ = self.create_set(plan, unexpected=True)
        with self.assertRaisesRegex(workflow.WorkflowError, "found 0"):
            workflow.locate_set(results, plan)

        options = argparse.Namespace(
            plan=str(self.root / "unexpected-plan.json"),
            results_root=str(results),
            dry_run_exit="0",
            benchmark_exit="0",
        )
        write_json(Path(options.plan), plan)
        result = workflow.benchmark_result(options)
        self.assertEqual(82, result["primary"]["exit"])
        self.assertEqual("set-discovery", result["primary"]["stage"])

    def create_receipt(self, results: Path, result: dict) -> dict:
        receipt_id = "gse-upload-receipt-v1-" + "b" * 64
        root = results / "upload-receipts" / receipt_id / "v1"
        receipt = {
            "bucket": "gs://gse-benchmark-evidence",
            "kind": "cloud-benchmark-upload-receipt",
            "objects": [
                {"uri": f"gs://gse-benchmark-evidence/general-search-engine/sets/{result['set']['id']}/v1/benchmark-set-manifest.json"}
            ],
            "receiptId": receipt_id,
            "schemaVersion": 1,
            "source": {"id": result["set"]["id"], "kind": "benchmark-set"},
        }
        write_json(root / "upload-receipt.json", receipt)
        (root / "upload-receipt.sha256").write_text(
            f"{checksum(root / 'upload-receipt.json')}  upload-receipt.json\n", encoding="utf-8"
        )
        return receipt

    def test_receipt_binding_and_upload_result(self) -> None:
        plan = self.plan(retention="gcs")
        results, _ = self.create_set(plan)
        result_path, result = self.create_result(plan, results)
        receipt = self.create_receipt(results, result)
        options = argparse.Namespace(
            plan=str(self.root / "workflow-plan.json"),
            result=str(result_path),
            results_root=str(results),
            upload_exit="0",
        )
        updated = workflow.update_upload(options)
        self.assertEqual(receipt["receiptId"], updated["upload"]["receipt"]["id"])
        options.upload_exit = "86"
        failed = workflow.update_upload(options)
        self.assertEqual("failed", failed["upload"]["status"])

    def test_artifact_staging_is_allowlisted_and_checksummed(self) -> None:
        plan = self.plan()
        results, _ = self.create_set(plan)
        result_path, result = self.create_result(plan, results)
        summary = self.root / "workflow-summary.md"
        summary.write_text(workflow.render_summary(plan, result), encoding="utf-8")
        staging = self.root / "staging"
        options = argparse.Namespace(
            plan=str(self.root / "workflow-plan.json"),
            result=str(result_path),
            summary=str(summary),
            results_root=str(results),
            staging=str(staging),
        )
        staged = workflow.stage_artifact(options)
        self.assertGreater(staged["fileCount"], 4)
        self.assertTrue((staging / "artifact-checksums.sha256").is_file())
        self.assertFalse(any(path.name == "environment.txt" for path in staging.rglob("*")))
        self.assertFalse(any("raw" in path.parts for path in staging.rglob("*")))

    def test_artifact_staging_rejects_symlink_and_size_limit(self) -> None:
        plan = self.plan()
        results, manifest = self.create_set(plan)
        result_path, result = self.create_result(plan, results)
        summary = self.root / "workflow-summary.md"
        summary.write_text(workflow.render_summary(plan, result), encoding="utf-8")
        manifest_ref = results / manifest["members"][0]["manifestReference"]
        manifest_ref.unlink()
        manifest_ref.symlink_to(summary)
        options = argparse.Namespace(
            plan=str(self.root / "workflow-plan.json"),
            result=str(result_path),
            summary=str(summary),
            results_root=str(results),
            staging=str(self.root / "symlink-staging"),
        )
        with self.assertRaisesRegex(workflow.WorkflowError, "results root|regular file"):
            workflow.stage_artifact(options)

        manifest_ref.unlink()
        manifest_ref.write_text("manifest\n", encoding="utf-8")
        options.staging = str(self.root / "large-staging")
        with mock.patch.object(workflow, "MAX_ARTIFACT_BYTES", 8):
            with self.assertRaisesRegex(workflow.WorkflowError, "100 MiB"):
                workflow.stage_artifact(options)

    def test_summary_is_bounded_and_final_exit_preserves_primary(self) -> None:
        plan = self.plan()
        results, _ = self.create_set(plan)
        _, result = self.create_result(plan, results)
        result["primary"] = {"category": "benchmark|failure", "exit": 30, "stage": "benchmark"}
        summary = workflow.render_summary(plan, result)
        self.assertIn("benchmark\\|failure", summary)
        self.assertIn("No baseline comparison", summary)
        self.assertNotIn(str(self.root), summary)
        self.assertEqual(30, workflow.final_exit(result, ("failure", "failure")))
        result["primary"]["exit"] = 0
        result["upload"] = {"exit": 86, "receipt": None, "status": "failed"}
        self.assertEqual(86, workflow.final_exit(result, ("success",)))
        result["upload"] = {"exit": None, "receipt": None, "status": "not-requested"}
        self.assertEqual(2, workflow.final_exit(result, ("failure",)))
        self.assertEqual(0, workflow.final_exit(result, ("success", "success")))

    def test_github_outputs_are_single_line(self) -> None:
        output = self.root / "github-output"
        workflow.write_github_output(str(output), {"source_commit": self.commit})
        self.assertEqual(f"source_commit={self.commit}\n", output.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(workflow.WorkflowError, "Unsafe"):
            workflow.write_github_output(str(output), {"bad": "line\nbreak"})

    def test_preflight_summary_and_fresh_workspace_gate(self) -> None:
        plan = self.plan()
        summary = workflow.render_plan_summary(plan)
        self.assertIn("requested no OIDC token", summary)
        self.assertIn(self.commit, summary)
        results = self.root / "fresh-results"
        workflow.assert_fresh(results)
        receipt = results / "upload-receipts" / ("gse-upload-receipt-v1-" + "c" * 64) / "v1"
        receipt.mkdir(parents=True)
        (receipt / "upload-receipt.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(workflow.WorkflowError, "completed evidence"):
            workflow.assert_fresh(results)


if __name__ == "__main__":
    unittest.main()
