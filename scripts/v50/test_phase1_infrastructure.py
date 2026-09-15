import tempfile
import unittest
import copy
import json
from pathlib import Path

from scripts.v50.evidence import validate, write_bundle
from scripts.v50.fake_cloud_lane import plan, run


class Phase1InfrastructureTest(unittest.TestCase):
    def test_availability_record_matches_the_selected_catalog_identities(self):
        root = Path(__file__).resolve().parents[2] / "docs/v5x/v5.0"
        record = json.loads((root / "cloud-availability.json").read_text())
        selection = plan("experiment")["selection"]
        self.assertEqual(selection["machineType"], record["machine"]["name"])
        self.assertEqual(selection["zone"], record["machine"]["zone"])
        self.assertEqual(8, record["machine"]["guestCpus"])
        self.assertEqual("UP", record["zone"]["status"])
        self.assertEqual(selection["imageId"], record["image"]["id"])
        self.assertEqual(selection["image"], record["image"]["name"])
        self.assertEqual("READY", record["image"]["status"])
        self.assertIsNone(record["image"]["deprecated"])
        self.assertFalse(record["resourcesCreated"])

    def test_plan_freezes_concurrent_quota_safe_topology(self):
        canonical = plan("canonical")
        self.assertEqual(3, canonical["votersPerTopology"])
        self.assertTrue(canonical["votersConcurrent"])
        self.assertTrue(canonical["repeatsAreSerial"])
        self.assertEqual(24, canonical["resources"]["peakVcpus"])
        self.assertEqual(450, canonical["resources"]["peakProvisionedDiskGiB"])
        self.assertEqual(3, canonical["topologyRepeats"])

    def test_failure_retains_evidence_and_proves_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evidence"
            run(output, "1" * 40, "experiment", "provision-node-2")
            document = validate(output)
            self.assertEqual("FAIL", document["runStatus"])
            self.assertEqual("PASS", document["cleanupStatus"])
            self.assertEqual(7, len(document["cleanup"]))
            self.assertTrue(all(receipt["deleted"] for receipt in document["cleanup"]))
            self.assertEqual(
                {"topology-1-private-replication-firewall", "topology-1-evidence-staging-prefix"},
                {receipt["resource"] for receipt in document["cleanup"]}
                & {"topology-1-private-replication-firewall", "topology-1-evidence-staging-prefix"},
            )

    def test_canonical_repetitions_have_overlapping_voters_and_serial_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evidence"
            run(output, "1" * 40, "canonical", None)
            document = validate(output)
            self.assertEqual(33, len(document["cleanup"]))
            self.assertEqual(3, sum(event["action"] == "measure" for event in document["events"]))
            self.assertEqual([], document["remainingResources"])

    def test_run_failure_cleans_all_resources_and_stops_later_topologies(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evidence"
            run(output, "1" * 40, "canonical", "run-node-1")
            document = validate(output)
            self.assertEqual(11, len(document["cleanup"]))
            self.assertEqual({1}, {event["topology"] for event in document["events"]})

    def test_cleanup_failure_retains_evidence_and_cannot_pass_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evidence"
            with self.assertRaisesRegex(ValueError, "cleanup incomplete"):
                run(output, "1" * 40, "canonical", "cleanup-node-2-data-disk")
            document = json.loads((output / "evidence.json").read_text())
            self.assertEqual(["topology-1-node-2-data-disk"], document["remainingResources"])
            with self.assertRaisesRegex(ValueError, "cleanup incomplete"):
                validate(output)

    def test_rechecks_semantics_even_when_tampered_evidence_has_valid_checksums(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evidence"
            run(output, "1" * 40, "canonical", None)
            original = validate(output)
            mutations = (
                lambda d: d.update(sourceCommit="x"),
                lambda d: d.update(cleanup=[]),
                lambda d: d.update(events=[]),
                lambda d: d.update(remainingResources=["forgotten-disk"]),
                lambda d: d["plan"].update(topologyRepeats=1),
                lambda d: d["plan"]["resources"].update(peakVcpus=25),
                lambda d: next(e for e in d["events"] if e["action"] == "measure").update(voters=["node-1"]),
                lambda d: next(e for e in d["events"] if e["action"] == "start").update(node="node-4"),
                lambda d: next(e for e in d["events"] if e["action"] == "delete").update(resource="unknown"),
                lambda d: d.update(authorityClaim="production-quorum"),
            )
            for index, mutate in enumerate(mutations):
                with self.subTest(mutation=index):
                    changed = copy.deepcopy(original)
                    mutate(changed)
                    write_bundle(output, changed)
                    with self.assertRaises(ValueError):
                        validate(output)

    def test_checksums_and_inventory_reject_untrusted_paths_and_missing_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evidence"
            run(output, "1" * 40, "experiment", None)
            checksums = output / "artifact-checksums.sha256"
            original = checksums.read_text()
            for raw in (original + original, original.replace("evidence.json", "../outside"), ""):
                checksums.write_text(raw)
                with self.assertRaises(ValueError):
                    validate(output)


if __name__ == "__main__":
    unittest.main()
