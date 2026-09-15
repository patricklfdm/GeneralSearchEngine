import tempfile
import unittest
from pathlib import Path

from scripts.v50.evidence import validate
from scripts.v50.fake_cloud_lane import plan, run


class Phase1InfrastructureTest(unittest.TestCase):
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
            self.assertEqual(8, len(document["cleanup"]))
            self.assertTrue(all(receipt["deleted"] for receipt in document["cleanup"]))
            self.assertEqual(
                {"private-replication-firewall", "evidence-staging-prefix"},
                {receipt["resource"] for receipt in document["cleanup"]}
                & {"private-replication-firewall", "evidence-staging-prefix"},
            )


if __name__ == "__main__":
    unittest.main()
