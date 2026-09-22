from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from scripts.ci_changes import comparison, decide, is_documentation, main


ROOT = Path(__file__).resolve().parents[1]
BASE, HEAD = "a" * 40, "b" * 40
PUSH = {"before": BASE, "after": HEAD}
PR = {"pull_request": {"base": {"sha": BASE}, "head": {"sha": HEAD}}}
FULL_GATES = {
    "reactor-core": "REACTOR_RESULT",
    "v51-regression": "V51_RESULT",
    "v50-regression": "V50_RESULT",
    "v4-regression": "V4_RESULT",
    "soak-examples": "SOAK_RESULT",
    "compatibility": "COMPATIBILITY_RESULT",
    "release-artifacts": "RELEASE_RESULT",
    "cloud-runner-tests": "CLOUD_RUNNER_RESULT",
}


class ChangeDetectionTest(unittest.TestCase):
    def test_documentation_allowlist(self):
        for path in ("README.md", "docs/v5x/v5.0/plan.md", "module/README.md",
                     "LICENSE", ".gitignore", ".github/ISSUE_TEMPLATE/bug.yml"):
            with self.subTest(path=path):
                self.assertTrue(is_documentation(path))

    def test_build_inputs_and_unknown_paths_require_full_ci(self):
        for path in ("src/main/java/Engine.java", "module/src/test/resources/input.md",
                     "pom.xml", "new-module/pom.xml", "reactor/pom.xml", "mvnw",
                     ".mvn/wrapper/maven-wrapper.properties", "scripts/check.py", "scripts/input.md",
                     ".github/workflows/ci.yml", ".github/workflows/README.md",
                     "docs/v5x/v5.0/phase1-plan.json", "docs/baseline.sha256",
                     "new-module/new-build-input", "src/test/resources/README.md"):
            with self.subTest(path=path):
                self.assertFalse(is_documentation(path))

    def test_event_boundaries_include_all_changes(self):
        self.assertEqual(BASE + "..." + HEAD, comparison("pull_request", PR))
        self.assertEqual(BASE + ".." + HEAD, comparison("push", PUSH))

    def test_unknown_or_incomplete_boundaries_force_full_ci(self):
        for event_name, event in (("workflow_dispatch", {}), ("unknown", PUSH),
                                  ("push", {}), ("push", {"before": "0" * 40, "after": HEAD}),
                                  ("push", {"before": "--help", "after": HEAD}),
                                  ("pull_request", {"pull_request": None})):
            with self.subTest(event_name=event_name, event=event), patch("scripts.ci_changes.subprocess.run") as git:
                self.assertTrue(decide(event_name, event, ROOT)[0])
                git.assert_not_called()

    def test_nul_delimited_docs_with_spaces_and_newlines(self):
        with patch("scripts.ci_changes.subprocess.run") as git:
            git.return_value.stdout = b"README.md\0docs/a b.md\0docs/a\nb.md\0"
            self.assertFalse(decide("push", PUSH, ROOT)[0])
            args = git.call_args.args[0]
            self.assertIn("--no-renames", args)
            self.assertIn("-z", args)

    def test_mixed_or_renamed_source_cannot_hide_behind_docs(self):
        with patch("scripts.ci_changes.subprocess.run") as git:
            # --no-renames retains the deleted original source path.
            git.return_value.stdout = b"docs/Engine.md\0src/main/java/Engine.java\0"
            self.assertTrue(decide("pull_request", PR, ROOT)[0])

    def test_no_changed_file_truncation(self):
        with patch("scripts.ci_changes.subprocess.run") as git:
            git.return_value.stdout = b"".join(f"docs/{i}.md\0".encode() for i in range(3500)) + b"pom.xml\0"
            self.assertTrue(decide("pull_request", PR, ROOT)[0])

    def test_missing_history_and_invalid_diff_force_full_ci(self):
        for error in (OSError(), subprocess.CalledProcessError(128, "git"),
                      subprocess.TimeoutExpired("git", 60)):
            with patch("scripts.ci_changes.subprocess.run", side_effect=error):
                self.assertTrue(decide("push", PUSH, ROOT)[0])
        for output in (b"", b"README.md"):
            with patch("scripts.ci_changes.subprocess.run") as git:
                git.return_value.stdout = output
                self.assertTrue(decide("push", PUSH, ROOT)[0])

    def test_bad_event_payload_emits_full_ci_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            with patch.dict(os.environ, {"GITHUB_EVENT_PATH": directory + "/missing",
                                         "GITHUB_OUTPUT": str(output)}):
                main()
            self.assertEqual("run_full_ci=true\n", output.read_text())


class RequiredGateTest(unittest.TestCase):
    """Execute the actual workflow shell, so unexpected skips cannot pass Required."""

    @classmethod
    def setUpClass(cls):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        required = workflow.split("\n  required:\n", 1)[1]
        cls.script = textwrap.dedent(required.split("        run: |\n", 1)[1])

    def result(self, full="true", changes="success", results=None):
        if results is None:
            results = ["success" if full == "true" else "skipped"] * len(FULL_GATES)
        self.assertEqual(len(FULL_GATES), len(results))
        env = dict(os.environ, CHANGES_RESULT=changes, RUN_FULL_CI=full,
                   **dict(zip(FULL_GATES.values(), results)))
        return subprocess.run(["bash", "-e", "-c", self.script], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode

    def test_all_full_gates_success(self):
        self.assertEqual(0, self.result())

    def test_verified_docs_only_skips_success(self):
        self.assertEqual(0, self.result(full="false"))

    def test_full_ci_rejects_failed_cancelled_or_skipped_gate(self):
        for index in range(len(FULL_GATES)):
            for outcome in ("failure", "cancelled", "skipped", ""):
                results = ["success"] * len(FULL_GATES)
                results[index] = outcome
                with self.subTest(index=index, outcome=outcome):
                    self.assertNotEqual(0, self.result(results=results))

    def test_docs_lane_requires_exact_skips(self):
        for index in range(len(FULL_GATES)):
            for outcome in ("success", "failure", "cancelled", ""):
                results = ["skipped"] * len(FULL_GATES)
                results[index] = outcome
                with self.subTest(index=index, outcome=outcome):
                    self.assertNotEqual(0, self.result(full="false", results=results))

    def test_detection_failure_or_invalid_output_cannot_pass(self):
        for full in ("true", "false"):
            for changes in ("failure", "cancelled", "skipped", ""):
                with self.subTest(full=full, changes=changes):
                    self.assertNotEqual(0, self.result(full=full, changes=changes))
        for full in ("", "unknown"):
            self.assertNotEqual(0, self.result(full=full))


class WorkflowTopologyTest(unittest.TestCase):
    """Check scheduling and gate wiring without adding a docs-lane dependency."""

    @classmethod
    def setUpClass(cls):
        # Read the workflow's explicit job blocks; this is not a general YAML parser.
        workflow = (ROOT / ".github/workflows/ci.yml").read_text().split("\njobs:\n", 1)[1]
        parts = re.split(r"^  ([\w-]+):\n", workflow, flags=re.MULTILINE)
        cls.jobs = dict(zip(parts[1::2], parts[2::2]))

    def test_full_lanes_start_independently_and_skip_for_docs(self):
        self.assertEqual(set(FULL_GATES) | {"changes", "required"}, set(self.jobs))
        for name in FULL_GATES:
            with self.subTest(job=name):
                body = self.jobs[name]
                self.assertEqual(["changes"], re.findall(r"^    needs: (.+)$", body, re.MULTILINE))
                self.assertIn("    if: ${{ needs.changes.outputs.run_full_ci == 'true' }}\n", body)
                self.assertNotIn("continue-on-error:", body)

    def test_required_waits_for_and_reads_every_lane(self):
        body = self.jobs["required"]
        self.assertIn("    if: ${{ always() }}\n", body)
        self.assertIn("    name: Required\n", body)
        self.assertCountEqual(["changes", *FULL_GATES], re.findall(r"^      - ([\w-]+)$", body, re.MULTILINE))
        result_bindings = re.findall(r"^          (\w+): \$\{\{ needs\.([\w-]+)\.result \}\}$", body, re.MULTILINE)
        self.assertCountEqual([("CHANGES_RESULT", "changes"), *[(env, job) for job, env in FULL_GATES.items()]], result_bindings)

    def test_cloud_preflight_keeps_its_existing_ci_identifiers(self):
        self.assertIn("    name: Reactor tests\n", self.jobs["reactor-core"])
        self.assertIn("      - name: Verify V5.0 Phase 6B runner failures and offline volume-layout probe\n",
                      self.jobs["v50-regression"])


if __name__ == "__main__":
    unittest.main()
