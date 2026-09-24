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
    "v51-verification-build": "V51_BUILD_RESULT",
    "v51-foundation": "V51_FOUNDATION_RESULT",
    "v51-remote-rich": "V51_REMOTE_RICH_RESULT",
    "v51-remote-rich-inputs": "V51_RICH_INPUTS_RESULT",
    "v51-remote-rich-shards": "V51_RICH_SHARDS_RESULT",
    "v51-remote-faults": "V51_REMOTE_FAULTS_RESULT",
    "v51-admission-resources": "V51_ADMISSION_RESOURCES_RESULT",
    "v51-promise-crashes": "V51_PROMISE_CRASHES_RESULT",
    "v51-public-reads-faults": "V51_PUBLIC_READS_FAULTS_RESULT",
    "v51-public-recovery-pressure": "V51_PUBLIC_RECOVERY_PRESSURE_RESULT",
    "v51-public-hardening": "V51_PUBLIC_HARDENING_RESULT",
    "v51-protocol-selection": "V51_PROTOCOL_SELECTION_RESULT",
    "v51-candidate-crashes": "V51_CANDIDATE_CRASHES_RESULT",
    "v51-reclamation": "V51_RECLAMATION_RESULT",
    "v50-authority": "V50_AUTHORITY_RESULT",
    "v50-recovery-workload": "V50_RECOVERY_RESULT",
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

    def test_failed_shared_build_and_skipped_dependents_cannot_pass(self):
        outcomes = {name: "success" for name in FULL_GATES}
        for name in outcomes:
            if name.startswith("v51-"):
                outcomes[name] = "failure" if name == "v51-verification-build" else "skipped"
        self.assertNotEqual(0, self.result(results=list(outcomes.values())))

    def test_rich_matrix_failure_and_skipped_aggregate_fail_required(self):
        outcomes = {name: "success" for name in FULL_GATES}
        outcomes["v51-remote-rich-shards"] = "failure"
        outcomes["v51-remote-rich"] = "skipped"
        self.assertNotEqual(0, self.result(results=list(outcomes.values())))
        outcomes["v51-remote-rich-shards"] = "cancelled"
        self.assertNotEqual(0, self.result(results=list(outcomes.values())))

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

    def test_build_domains_and_lanes_skip_for_docs(self):
        self.assertEqual(set(FULL_GATES) | {"changes", "required"}, set(self.jobs))
        for name in FULL_GATES:
            with self.subTest(job=name):
                body = self.jobs[name]
                needs = "[changes, v51-verification-build]" if name.startswith("v51-") and name != "v51-verification-build" else "changes"
                if name == "v51-remote-rich-shards":
                    needs = "[changes, v51-verification-build, v51-remote-rich-inputs]"
                elif name == "v51-remote-rich":
                    needs = "[changes, v51-verification-build, v51-remote-rich-inputs, v51-remote-rich-shards]"
                self.assertEqual([needs], re.findall(r"^    needs: (.+)$", body, re.MULTILINE))
                self.assertIn("    if: ${{ needs.changes.outputs.run_full_ci == 'true' }}\n", body)
                self.assertNotIn("continue-on-error:", body)

    def test_required_waits_for_and_reads_every_lane(self):
        body = self.jobs["required"]
        self.assertIn("    if: ${{ always() }}\n", body)
        self.assertIn("    name: Required\n", body)
        self.assertCountEqual(["changes", *FULL_GATES], re.findall(r"^      - ([\w-]+)$", body, re.MULTILINE))
        result_bindings = re.findall(r"^          (\w+): \$\{\{ needs\.([\w-]+)\.result \}\}$", body, re.MULTILINE)
        self.assertCountEqual([("CHANGES_RESULT", "changes"), *[(env, job) for job, env in FULL_GATES.items()]], result_bindings)

    def test_v51_split_keeps_every_gate_once_with_its_own_evidence(self):
        expected = {
            "phase1-foundation", "phase2-storage", "phase3-protocol", "phase3-runtime", "phase3-rejoin",
            "phase4-public-bounds", "phase4-bootstrap", "phase4-resources", "phase4-public-promises",
            "phase4-public-runtime", "phase4-public-qualification", "phase4-public-faults",
            "phase4-public-recovery", "phase4-public-pressure", "phase4-backpressure", "phase4-final-coverage",
            "phase4-lifecycle-hardening", "phase5-hardening", "phase5-combined-lifecycle", "phase4-public-protocol",
            "phase4-public-selection", "phase4-public-candidates", "phase4-public-reclamation", "phase6-performance", "phase6-remote-faults", "phase6-full-size",
        }
        found = []
        for name in FULL_GATES:
            if not name.startswith("v51-") or name in ("v51-verification-build", "v51-remote-rich", "v51-remote-rich-inputs", "v51-remote-rich-shards"):
                continue
            body = self.jobs[name]
            gates = re.findall(r"^        run: scripts/verify-v51-([\w-]+)\.sh --skip-build$", body, re.MULTILINE)
            self.assertTrue(gates, name)
            found.extend(gates)
            uploads = [step for step in re.split(r"^      - ", body, flags=re.MULTILINE)
                       if "uses: actions/upload-artifact@" in step]
            for gate in gates:
                artifact = "target/v51-" + gate.split("-", 1)[1]
                own = [step for step in uploads if "          path: " + artifact + "\n" in step]
                self.assertEqual(1, len(own), (name, artifact))
                self.assertRegex(own[0], r"if: (?:\$\{\{ )?always\(\)")
                self.assertIn("          retention-days: 14\n", own[0])
        self.assertCountEqual(expected, found)

    def test_v51_build_executes_tests_and_consumers_restore_exact_inputs(self):
        build = self.jobs["v51-verification-build"]
        command = "run: scripts/run-maven-with-infra-retry.sh ./mvnw -f reactor/pom.xml clean package"
        self.assertEqual(1, build.count(command))
        self.assertLess(build.index("scripts.ci_v51_bundle prepare"), build.index(command))
        self.assertLess(build.index(command), build.index("scripts.ci_v51_bundle create"))
        self.assertIn("path: '**/target/surefire-reports/**'", build)
        self.assertIn("name: v51-verification-build-${{ github.sha }}", build)
        for step in re.split(r"^      - ", build, flags=re.MULTILINE):
            if "path: '**/target/surefire-reports/**'" in step or "path: ${{ runner.temp }}/" in step:
                self.assertIn("if: ${{ always() }}", step)
        for name in FULL_GATES:
            if not name.startswith("v51-") or name == "v51-verification-build":
                continue
            with self.subTest(job=name):
                body = self.jobs[name]
                self.assertNotIn("./mvnw", body)
                self.assertNotIn("cache: maven", body)
                self.assertIn("uses: actions/download-artifact@", body)
                self.assertIn("name: v51-verification-build-${{ github.sha }}", body)
                self.assertIn('scripts.ci_v51_bundle restore --source "$GITHUB_SHA"', body)
                verifier = "scripts.v51.remote_rich_shards" if name in ("v51-remote-rich", "v51-remote-rich-inputs") else "run: scripts/verify-v51-"
                self.assertLess(body.index("scripts.ci_v51_bundle restore"), body.index(verifier))
                if name in ("v51-remote-rich-inputs", "v51-remote-rich-shards"):
                    self.assertIn("${{ runner.temp }}/v51-build/restore.json", body)
                    continue
                receipts = [step for step in re.split(r"^      - ", body, flags=re.MULTILINE)
                            if "name: " + name + "-build-inputs-${{ github.sha }}" in step]
                self.assertEqual(1, len(receipts))
                self.assertIn("if: ${{ always() }}", receipts[0])
                self.assertIn("retention-days: 14", receipts[0])
        self.assertIn(command, self.jobs["reactor-core"])
        self.assertIn("scripts.test_ci_v51_bundle", self.jobs["changes"])

    def test_rich_matrix_and_complete_aggregate_are_required(self):
        shard = self.jobs["v51-remote-rich-shards"]
        self.assertIn("fail-fast: false", shard)
        self.assertIn("shard: [published-controls, automatic-healthy, automatic-concurrent]", shard)
        self.assertNotIn("continue-on-error", shard)
        self.assertIn('run: scripts/verify-v51-phase6-remote-rich-shard.sh "$RICH_SHARD"', shard)
        self.assertIn("name: v51-remote-rich-shard-${{ matrix.shard }}-${{ github.sha }}", shard)
        aggregate = self.jobs["v51-remote-rich"]
        for name in ("published-controls", "automatic-healthy", "automatic-concurrent"):
            self.assertIn("name: v51-remote-rich-shard-" + name + "-${{ github.sha }}", aggregate)
            self.assertIn("path: target/v51-remote-rich/inputs/" + name, aggregate)
        self.assertIn("scripts.v51.remote_rich_shards aggregate", aggregate)
        self.assertIn("name: v51-remote-rich-${{ github.sha }}", aggregate)
        self.assertIn("path: target/v51-remote-rich", aggregate)
        self.assertIn("scripts.v51.remote_rich_shards prepare", self.jobs["v51-remote-rich-inputs"])
        # The full serial entry point remains available for local diagnosis.
        script = (ROOT / "scripts/verify-v51-phase6-remote-rich.sh").read_text()
        self.assertIn("scripts.v51.remote_rich_qualification", script)
        self.assertIn("2400s", script)

    def test_infra_retry_only_wraps_reviewed_builds_and_retains_all_attempts(self):
        from scripts.maven_infra_retry import COMMANDS
        expected = {"v51-verification-build", "v50-authority", "v50-recovery-workload"}
        expected.update(("reactor-core", "v4-regression"))
        found = set()
        count = 0
        for name, body in self.jobs.items():
            commands = re.findall(r"^        run: scripts/run-maven-with-infra-retry.sh (.+)$", body, re.MULTILINE)
            if commands:
                found.add(name); count += len(commands)
                for command in commands:
                    self.assertIn(tuple(command.split()), COMMANDS)
                self.assertEqual(2 if name == "v4-regression" else 1, len(commands))
                uploads = [step for step in re.split(r"^      - ", body, flags=re.MULTILINE)
                           if "path: ${{ runner.temp }}/gse-maven-infra-retry" in step]
                self.assertEqual(1, len(uploads), name)
                self.assertIn("if: ${{ always() }}", uploads[0])
                self.assertIn("name: maven-infra-" + name + "-${{ github.sha }}", uploads[0])
                self.assertIn("retention-days: 14", uploads[0])
            self.assertNotRegex(body, r"run-maven-with-infra-retry.sh .*scripts/verify-")
        self.assertEqual(expected, found)
        self.assertEqual(6, count)
        self.assertIn("scripts.test_maven_infra_retry", self.jobs["changes"])
        for name in ("soak-examples", "compatibility", "release-artifacts", "cloud-runner-tests"):
            self.assertNotIn("run-maven-with-infra-retry.sh", self.jobs[name])

    def test_cloud_preflight_keeps_its_existing_ci_identifiers(self):
        self.assertIn("    name: Reactor tests\n", self.jobs["reactor-core"])
        self.assertIn("      - name: Verify V5.0 Phase 6B runner failures and offline volume-layout probe\n",
                      self.jobs["v50-recovery-workload"])


if __name__ == "__main__":
    unittest.main()
