from __future__ import annotations

import unittest

from scripts.v4.durable_cloud_workflow import validate_inputs
from scripts.v4.evidence import EvidenceError


class DurableCloudWorkflowTest(unittest.TestCase):
    def test_experiment_is_one_standard_member(self) -> None:
        plan = validate_inputs(
            "experiment", 1, 120, "actions", "c3d-standard-30", "standard"
        )
        self.assertEqual(1, plan["repeats"])

    def test_canonical_requires_three_members_and_gcs(self) -> None:
        plan = validate_inputs(
            "canonical", 3, 1800, "gcs", "c3d-standard-30", "standard"
        )
        self.assertEqual(3, plan["repeats"])
        with self.assertRaisesRegex(EvidenceError, "exactly 3"):
            validate_inputs(
                "canonical", 1, 1800, "gcs", "c3d-standard-30", "standard"
            )
        with self.assertRaisesRegex(EvidenceError, "GCS"):
            validate_inputs(
                "canonical", 3, 1800, "actions", "c3d-standard-30", "standard"
            )

    def test_failure_drill_is_separate_and_gcs_retained(self) -> None:
        plan = validate_inputs(
            "failure-drill", 1, 120, "gcs", "c3d-standard-30", "standard"
        )
        self.assertEqual("failure-drill", plan["profile"])

    def test_spot_and_machine_substitution_are_rejected(self) -> None:
        with self.assertRaisesRegex(EvidenceError, "Standard"):
            validate_inputs(
                "experiment", 1, 120, "actions", "c3d-standard-30", "spot"
            )
        with self.assertRaisesRegex(EvidenceError, "c3d-standard-30"):
            validate_inputs(
                "experiment", 1, 120, "actions", "c3d-standard-60", "standard"
            )


if __name__ == "__main__":
    unittest.main()
