from __future__ import annotations

import unittest

from scripts.v4.durable_cloud_workflow import (
    render_plan_summary,
    validate_inputs,
    validate_plan_document,
)
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

    def test_plan_summary_is_validated_readable_markdown(self) -> None:
        document = {
            "schemaVersion": "gse-v40-durable-cloud-plan-v1",
            "suite": "v4.0-durable-single-node-suite-v1",
            "preset": "v4.0-durable-single-node-v1",
            "sourceCommit": "a" * 40,
            "trustedRef": "origin/master",
            "runId": "12345",
            "request": validate_inputs(
                "experiment", 1, 120, "actions",
                "c3d-standard-30", "standard"
            ),
            "slots": [1],
            "resources": {
                "diskType": "pd-balanced",
                "diskSizeGiB": 200,
                "filesystem": "ext4",
                "mountOptions": "defaults",
                "maximumRuntimeSeconds": 3720,
            },
        }
        self.assertIs(document, validate_plan_document(document))
        summary = render_plan_summary(document)
        self.assertIn("# V4 durable cloud preflight", summary)
        self.assertIn("| Source commit | `" + "a" * 40 + "` |", summary)
        self.assertIn("| Persistent data disk | `pd-balanced / 200 GiB` |", summary)
        self.assertIn("created no VM or disk", summary)

        document["resources"]["diskSizeGiB"] = 201
        with self.assertRaisesRegex(EvidenceError, "resources differ"):
            render_plan_summary(document)


if __name__ == "__main__":
    unittest.main()
