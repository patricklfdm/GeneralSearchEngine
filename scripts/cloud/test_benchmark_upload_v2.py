#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.cloud import benchmark_v2 as v2
from scripts.cloud.test_benchmark_v2 import COMMIT, Fixture


def canonical_controls():
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


def create_canonical_set(root: Path) -> Path:
    fixtures = []
    for slot in range(1, 4):
        fixture = Fixture(
            root,
            run_id=f"20260828T20000{slot}Z-0123456789ab-full",
            instance=f"gse-upload-set-{slot}",
        )
        fixtures.append(fixture)
    results = fixtures[0].results
    workspace = results / "sets" / "in-progress" / "upload-set"
    v2.initialize_set_workspace(
        workspace,
        "canonical",
        3,
        "full",
        "v3-production-full-v1",
        "https://github.com/patricklfdm/GeneralSearchEngine.git",
        COMMIT,
        canonical_controls(),
    )
    for slot, fixture in enumerate(fixtures, 1):
        intent = v2.begin_set_attempt(workspace, slot)
        intent["pointer"].write_text(
            str(fixture.orchestration_path.resolve()) + "\n", encoding="utf-8"
        )
        result = v2.record_set_attempt(workspace, slot, 0)
        if result != 0:
            raise AssertionError(f"Cannot create canonical upload fixture: slot {slot} -> {result}")
    return v2.finalize_benchmark_set(workspace)[0]


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, dict] = {}
        self.create_calls: list[tuple[Path, str, str]] = []
        self.describe_calls: list[str] = []
        self.fail_uri: str | None = None

    def describe(self, uri: str):
        self.describe_calls.append(uri)
        value = self.objects.get(uri)
        return None if value is None else dict(value)

    def create(self, source: Path, uri: str, sha256_hex: str) -> None:
        self.create_calls.append((source, uri, sha256_hex))
        if uri == self.fail_uri:
            raise v2.fail_upload("synthetic upload failure")
        if uri in self.objects:
            raise v2.fail_upload("synthetic create-only collision")
        integrity = v2.local_object_integrity(source)
        bucket, name = v2.split_gcs_uri(uri)
        self.objects[uri] = {
            "bucket": bucket,
            "crc32c_hash": integrity["crc32c"],
            "custom_fields": {"gse-sha256": sha256_hex},
            "generation": str(len(self.objects) + 100),
            "md5_hash": integrity["md5"],
            "name": name,
            "size": str(source.stat().st_size),
        }


class UploadV2Test(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results = self.root / "benchmark-results" / "v3-production"
        self.bucket = "gs://gse-fixture-bucket"

    def tearDown(self):
        self.temporary.cleanup()

    def assert_error(self, code, callable_):
        with self.assertRaises(v2.BenchmarkV2Error) as caught:
            callable_()
        self.assertEqual(code, caught.exception.exit_code)

    def make_run(self, *, canonical=False, root=None, ordinal=1):
        fixture = Fixture(
            root or self.root,
            run_id=f"20260828T10000{ordinal}Z-0123456789ab-full",
            instance=f"gse-upload-{ordinal}",
        )
        output, _, _ = v2.derive_manifest(
            fixture.raw, evidence_profile="canonical" if canonical else "experiment"
        )
        return fixture, output

    def make_canonical_set(self):
        return create_canonical_set(self.root)

    def test_run_and_set_inventory_use_fixed_immutable_paths(self):
        _, run = self.make_run()
        run_plan = v2.plan_evidence_upload(run, self.results, self.bucket)
        self.assertEqual("derived-run", run_plan["source"]["kind"])
        uris = [item["uri"] for item in run_plan["objects"]]
        self.assertTrue(any("/raw/" + COMMIT + "/" in uri for uri in uris))
        self.assertTrue(any("/orchestration/" + COMMIT + "/" in uri for uri in uris))
        self.assertTrue(any("/derived/runs/" in uri for uri in uris))
        self.assertEqual(uris, sorted(uris))

        set_root = self.make_canonical_set()
        set_plan = v2.plan_evidence_upload(set_root, self.results, self.bucket)
        self.assertEqual("benchmark-set", set_plan["source"]["kind"])
        self.assertTrue(
            any(uri.endswith("/v1/benchmark-set-manifest.json") for uri in
                (item["uri"] for item in set_plan["objects"]))
        )
        self.assertEqual(len(set_plan["objects"]), len({item["uri"] for item in set_plan["objects"]}))

    def test_local_integrity_uses_crc32c_not_crc32(self):
        source = self.root / "known-vector.txt"
        source.write_bytes(b"123456789")
        integrity = v2.local_object_integrity(source)
        self.assertEqual("4waSgw==", integrity["crc32c"])
        self.assertEqual("JfnnlDI7RTiF9RgfG2JNCw==", integrity["md5"])
        self.assertEqual("9", integrity["size"])

    def test_upload_receipt_is_deterministic_and_retry_is_idempotent(self):
        fixture, run = self.make_run()
        raw_before = v2.snapshot_raw(fixture.raw)
        source_before = {
            item["sourcePath"]: v2.sha256_file(item["sourcePath"])
            for item in v2.plan_evidence_upload(run, self.results, self.bucket)["objects"]
        }
        storage = FakeStorage()
        receipt_root, receipt = v2.upload_evidence(
            run, self.results, self.bucket, storage=storage, confirmed=True
        )
        self.assertTrue((receipt_root / "upload-receipt.json").is_file())
        self.assertTrue((receipt_root / "upload-receipt.sha256").is_file())
        self.assertRegex(receipt["receiptId"], v2.RECEIPT_ID_RE)
        self.assertEqual(raw_before, v2.snapshot_raw(fixture.raw))
        self.assertEqual(
            source_before,
            {path: v2.sha256_file(path) for path in source_before},
        )
        first_count = len(storage.create_calls)
        again_root, again = v2.upload_evidence(
            run, self.results, self.bucket, storage=storage, confirmed=True
        )
        self.assertEqual(receipt_root, again_root)
        self.assertEqual(receipt, again)
        self.assertEqual(first_count, len(storage.create_calls))

    def test_dry_run_and_confirmation_do_not_mutate(self):
        _, run = self.make_run()
        storage = FakeStorage()
        receipt_root, plan = v2.upload_evidence(
            run, self.results, self.bucket, storage=storage, dry_run=True
        )
        self.assertIsNone(receipt_root)
        self.assertEqual("derived-run", plan["source"]["kind"])
        self.assertEqual([], storage.create_calls)
        self.assertFalse((self.results / "upload-receipts").exists())
        self.assert_error(
            v2.EXIT_CONFIG,
            lambda: v2.upload_evidence(run, self.results, self.bucket, storage=storage),
        )

    def test_conflicting_remote_object_fails_without_overwrite(self):
        _, run = self.make_run()
        plan = v2.plan_evidence_upload(run, self.results, self.bucket)
        target = plan["objects"][0]
        storage = FakeStorage()
        bucket, name = v2.split_gcs_uri(target["uri"])
        storage.objects[target["uri"]] = {
            "bucket": bucket,
            "crc32c_hash": "AAAAAA==",
            "custom_fields": {"gse-sha256": "f" * 64},
            "generation": "99",
            "md5_hash": "AAAAAAAAAAAAAAAAAAAAAA==",
            "name": name,
            "size": "1",
        }
        self.assert_error(
            v2.EXIT_UPLOAD,
            lambda: v2.upload_evidence(
                run, self.results, self.bucket, storage=storage, confirmed=True
            ),
        )
        self.assertEqual("f" * 64, storage.objects[target["uri"]]["custom_fields"]["gse-sha256"])

    def test_bucket_and_receipt_identity_are_strict(self):
        _, run = self.make_run()
        for bucket in ("", "gse-bucket", "gs://bucket/prefix", "gs://bucket/"):
            with self.subTest(bucket=bucket):
                self.assert_error(
                    v2.EXIT_CONFIG,
                    lambda bucket=bucket: v2.plan_evidence_upload(run, self.results, bucket),
                )
        storage = FakeStorage()
        receipt_root, _ = v2.upload_evidence(
            run, self.results, self.bucket, storage=storage, confirmed=True
        )
        receipt_path = receipt_root / "upload-receipt.json"
        receipt = v2.read_json(receipt_path)
        receipt["source"]["sourceCommit"] = "f" * 40
        receipt_path.write_bytes(v2.canonical_json_bytes(receipt))
        checksum = v2.sha256_file(receipt_path)
        (receipt_root / "upload-receipt.sha256").write_text(
            f"{checksum}  upload-receipt.json\n", encoding="utf-8"
        )
        self.assert_error(
            v2.EXIT_REGISTRY,
            lambda: v2.validate_upload_receipt(receipt_root, self.results),
        )

    def test_partial_failure_resumes_and_only_then_finalizes_receipt(self):
        _, run = self.make_run()
        plan = v2.plan_evidence_upload(run, self.results, self.bucket)
        storage = FakeStorage()
        storage.fail_uri = plan["objects"][1]["uri"]
        self.assert_error(
            v2.EXIT_UPLOAD,
            lambda: v2.upload_evidence(
                run, self.results, self.bucket, storage=storage, confirmed=True
            ),
        )
        self.assertFalse((self.results / "upload-receipts").exists())
        storage.fail_uri = None
        receipt_root, _ = v2.upload_evidence(
            run, self.results, self.bucket, storage=storage, confirmed=True
        )
        self.assertTrue(receipt_root.is_dir())

    def test_only_verified_canonical_set_can_register(self):
        set_root = self.make_canonical_set()
        storage = FakeStorage()
        receipt_root, receipt = v2.upload_evidence(
            set_root, self.results, self.bucket, storage=storage, confirmed=True
        )
        registry = self.root / "registry.json"
        registry.write_bytes(v2.canonical_json_bytes({
            "baselines": {},
            "kind": "cloud-benchmark-baseline-registry",
            "schemaVersion": 1,
        }))
        entry = v2.register_cloud_baseline(
            "v3.0.0-cloud",
            set_root,
            self.results,
            registry,
            receipt_path=receipt_root,
            release_label="v3.0.0 reviewed",
            storage=storage,
        )
        self.assertEqual(receipt["receiptId"], entry["uploadReceiptId"])
        self.assertIn("v3.0.0-cloud", v2.validate_baseline_registry(registry)["baselines"])
        before = registry.read_bytes()
        self.assert_error(
            v2.EXIT_REGISTRY,
            lambda: v2.register_cloud_baseline(
                "v3.0.0-cloud", set_root, self.results, registry,
                receipt_path=receipt_root, storage=storage,
            ),
        )
        self.assertEqual(before, registry.read_bytes())

        _, experiment = self.make_run(root=self.root / "experiment", ordinal=9)
        self.assert_error(
            v2.EXIT_REGISTRY,
            lambda: v2.register_cloud_baseline(
                "experiment", experiment, self.results, registry,
                receipt_path=receipt_root, storage=storage,
            ),
        )

    def test_registration_reverifies_remote_generation_and_receipt_selection(self):
        set_root = self.make_canonical_set()
        storage = FakeStorage()
        first_root, first = v2.upload_evidence(
            set_root, self.results, self.bucket, storage=storage, confirmed=True
        )
        second_root, _ = v2.upload_evidence(
            set_root,
            self.results,
            "gs://gse-second-bucket",
            storage=storage,
            confirmed=True,
        )
        self.assertNotEqual(first_root, second_root)
        registry = self.root / "registry.json"
        registry.write_bytes(v2.canonical_json_bytes({
            "baselines": {},
            "kind": "cloud-benchmark-baseline-registry",
            "schemaVersion": 1,
        }))
        self.assert_error(
            v2.EXIT_REGISTRY,
            lambda: v2.register_cloud_baseline(
                "ambiguous", set_root, self.results, registry, dry_run=True
            ),
        )
        manifest_uri = next(
            item["uri"] for item in first["objects"]
            if item["uri"].endswith("/benchmark-set-manifest.json")
        )
        storage.objects[manifest_uri]["generation"] = "999999"
        before = registry.read_bytes()
        self.assert_error(
            v2.EXIT_UPLOAD,
            lambda: v2.register_cloud_baseline(
                "generation-mismatch",
                set_root,
                self.results,
                registry,
                receipt_path=first_root,
                storage=storage,
            ),
        )
        self.assertEqual(before, registry.read_bytes())


if __name__ == "__main__":
    unittest.main()
