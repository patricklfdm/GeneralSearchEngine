"""PR2: compare actual local actions to the retained inline-step contract."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import ci_suites as s
from scripts.ci_changes import is_documentation


def effective_job(body, job, actions=None):
    """Render expanded step data for existing literal workflow tests, never execute it."""
    parsed = s.steps(s.fields(body, 4)["steps"])
    expanded = s.expand_steps(parsed, job, s.load_actions() if actions is None else actions)
    lines = []
    for name, values in expanded.items():
        lines.append("      - name: " + name)
        for key, (value, children) in values.items():
            lines.append("        " + key + ":" + (" " + value if value else ""))
            if children:
                lines.append(children)
    return body.split("    steps:\n", 1)[0] + "    steps:\n" + "\n".join(lines) + "\n"


class CompositeTest(unittest.TestCase):
    def setUp(self):
        self.actions = s.load_actions()
        self.registry = s.load_registry()
        self.workflow = s.read(s.ROOT, s.WORKFLOW)
        self.jobs = s.job_blocks(self.workflow)
        self.related = {".github/workflows/release.yml": s.read(s.ROOT, ".github/workflows/release.yml")}
        self.fixture = s.read(s.ROOT, "scripts/fixtures/ci-v51-build-steps-v1.yml")

    def check(self, actions=None, workflow=None):
        return s.validate_workflow(self.registry, workflow or self.workflow, self.related,
                                   self.actions if actions is None else actions)

    def reject_action(self, action, before, after):
        self.assertIn(before, self.actions[action])
        actions = {**self.actions, action: self.actions[action].replace(before, after, 1)}
        with self.assertRaises((ValueError, KeyError, TypeError)):
            self.check(actions)

    def test_actual_consumers_match_independent_inline_fixture(self):
        callers = {job for job, body in self.jobs.items() if s.RESTORE_ACTION in body or s.RETAIN_ACTION in body}
        self.assertEqual(s.BUILD_CONSUMERS, callers)
        self.assertEqual(15, len(callers))
        for job in callers:
            with self.subTest(job=job):
                expanded = s.steps(s.fields(effective_job(self.jobs[job], job), 4)["steps"])
                original = s.steps(s.fields(self.fixture.replace("v51-foundation-build-inputs-", job + "-build-inputs-"), 4)["steps"])
                self.assertEqual(original, {key: expanded[key] for key in original})
                order = list(expanded)
                start = order.index(s.DOWNLOAD_STEP)
                self.assertEqual(list(original), order[start:start+3])
        self.assertEqual(50, len(self.check()))

    def test_artifact_inventory_unchanged_after_expansion(self):
        uploads = downloads = 0
        for suite in self.registry["suites"]:
            job = suite["id"]
            steps = s.steps(s.fields(effective_job(self.jobs[job], job), 4)["steps"])
            actual_in, actual_out = s.artifacts(steps, "download"), s.artifacts(steps, "upload")
            self.assertEqual(suite["inputs"], actual_in)
            self.assertEqual(suite["evidence"], actual_out)
            downloads += len(actual_in); uploads += len(actual_out)
        self.assertEqual((28, 112), (downloads, uploads))

    def test_wrong_or_missing_producer_id_never_falls_back_to_a_name(self):
        original = "artifact-id: " + s.BUILD_ID
        for value in ("''", "123", "${{ github.run_attempt }}", "latest-successful", "${{ needs.v51-verification-build.outputs.artifact_id }}"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check(workflow=self.workflow.replace(original, "artifact-id: " + value, 1))
        self.reject_action(s.RESTORE_ACTION, "artifact-ids:", "name:")
        self.reject_action(s.RESTORE_ACTION, "inputs.artifact-id || 'missing-build-artifact'", "inputs.artifact-id")
        # Empty input is guarded inside the action too: required:true alone does not enforce it.
        self.assertIn("artifact-ids: ${{ inputs.artifact-id || 'missing-build-artifact' }}", self.actions[s.RESTORE_ACTION])

    def test_failure_receipts_require_both_outer_and_inner_always(self):
        before = "if: " + s.ALWAYS
        for after in ("if: false", "if: ${{ success() }}", "if: ${{ failure() }}"):
            self.reject_action(s.RETAIN_ACTION, before, after)
            start = self.workflow.index("\n  v51-foundation:\n")
            workflow = self.workflow[:start] + self.workflow[start:].replace(before, after, 1)
            with self.assertRaises(ValueError):self.check(workflow=workflow)
        self.reject_action(s.RETAIN_ACTION, "      " + before + "\n", "")

    def test_restore_cannot_be_skipped_retried_or_weakened(self):
        for before, after in (
            ("shell: bash", "shell: sh"),
            ("shell: bash", "shell: bash\n      continue-on-error: true"),
            ("shell: bash", "shell: bash\n      if: false"),
            ("scripts.ci_v51_bundle restore", "scripts.ci_v51_bundle create"),
            ('--source "$GITHUB_SHA"', '--source "old-source"'),
            ("--bundle target/ci-v51-build", "--bundle target/cache"),
            ('--receipt "$RUNNER_TEMP/v51-build/restore.json"', '|| true'),
            ("merge-multiple: true", "merge-multiple: false"),
            ("@d3f86a106a0bac45b974a628896c90dbdf5c8093", "@main")):
            with self.subTest(after=after):self.reject_action(s.RESTORE_ACTION, before, after)

    def test_evidence_retention_paths_and_name_remain_fixed(self):
        for before, after in (("retention-days: 14", "retention-days: 1"),
                              ("if-no-files-found: warn", "if-no-files-found: ignore"),
                              ("/v51-build/restore.json", "/other/restore.json"),
                              ("name: ${{ inputs.artifact-name }}", "name: generic"),
                              ("@ea165f8d65b6e75b540449e92b4886f43607fa02", "@main")):
            with self.subTest(after=after):self.reject_action(s.RETAIN_ACTION, before, after)
        with self.assertRaises(ValueError):
            self.check(workflow=self.workflow.replace("artifact-name: v51-foundation-build-inputs-", "artifact-name: shared-", 1))

    def test_unknown_nested_actions_and_unreviewed_inputs_rejected(self):
        self.reject_action(s.RESTORE_ACTION, "using: composite", "using: node24")
        self.reject_action(s.RESTORE_ACTION, "    required: true", "    required: true\n    default: latest")
        self.reject_action(s.RESTORE_ACTION, "    required: true", "    required: false")
        self.reject_action(s.RESTORE_ACTION, "      uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4", "      uses: ./nested")
        with self.assertRaises(ValueError):
            self.check(workflow=self.workflow.replace(s.RESTORE_ACTION, "./unregistered", 1))
        with self.assertRaises(ValueError):
            self.check(workflow=self.workflow.replace("uses: " + s.RESTORE_ACTION, "uses: " + s.RESTORE_ACTION + "\n        if: false", 1))
        with self.assertRaises((ValueError, KeyError)):
            self.check(actions={s.RESTORE_ACTION: self.actions[s.RESTORE_ACTION]})

    def test_original_producer_owned_and_matrix_lanes_stay_inline(self):
        for job in ("v51-verification-build", "v51-owned-experiment", "v51-owned-canonical",
                    "v51-owned-canonical-tapes", "v51-remote-rich", "v51-remote-rich-shards",
                    "v51-remote-rich-inputs", "v51-guest-services", "release-artifacts"):
            self.assertNotIn("uses: ./.github/actions/", self.jobs[job])
        parsed = s.steps(s.fields(self.jobs["v51-foundation"], 4)["steps"])
        with self.assertRaises(ValueError):s.expand_steps(parsed, "v51-owned-experiment", self.actions)

    def test_restore_and_provenance_must_remain_adjacent_and_after_setup(self):
        body = self.jobs["v51-foundation"]
        pairs = s.steps(s.fields(body, 4)["steps"])
        for removed in (s.RESTORE_STEP, s.RETAIN_STEP, "Check out source", "Set up Java 21"):
            broken = {key: value for key, value in pairs.items() if key != removed}
            with self.subTest(removed=removed), self.assertRaises(ValueError):
                s.expand_steps(broken, "v51-foundation", self.actions)
        bad = {s.RESTORE_STEP: pairs[s.RESTORE_STEP], **{k:v for k,v in pairs.items() if k!=s.RESTORE_STEP}}
        with self.assertRaises(ValueError):s.expand_steps(bad, "v51-foundation", self.actions)

    def test_local_action_files_require_full_ci_including_markdown(self):
        for path in (".github/actions/v51-restore-build/action.yml", ".github/actions/v51-retain-build/action.yml",
                     ".github/actions/README.md", ".github/actions/new/helper.md"):
            self.assertFalse(is_documentation(path))
        self.assertTrue(is_documentation("docs/CI_REFACTOR_PROGRESS.md"))

    def test_actual_restore_command_preserves_argv_and_failure_exit(self):
        step = s.composite_steps(self.actions[s.RESTORE_ACTION], "artifact-id")[s.RESTORE_STEP]
        command = " ".join(line.strip() for line in step["run"][1].splitlines())
        with tempfile.TemporaryDirectory(prefix="ci action spaces ") as tmp:
            root = Path(tmp); fake = root / "python3"; log = root / "argv.json"
            fake.write_text('#!' + sys.executable + '\nimport json,os,sys\n'
                            'open(os.environ["ARGV_LOG"],"w").write(json.dumps(sys.argv[1:]))\n'
                            'sys.exit(int(os.environ["TEST_EXIT"]))\n')
            fake.chmod(0o755)
            marker = root / "should-not-execute"
            source = '$(touch "' + str(marker) + '")'
            env = dict(os.environ, PATH=str(root)+os.pathsep+os.environ["PATH"], RUNNER_TEMP=str(root),
                       GITHUB_SHA=source, ARGV_LOG=str(log))
            for exit_code in (0, 2):
                result = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", command],
                                        env={**env,"TEST_EXIT":str(exit_code)}, capture_output=True)
                self.assertEqual(exit_code, result.returncode, result.stderr)
                self.assertEqual(["-m","scripts.ci_v51_bundle","restore","--source",source,"--bundle","target/ci-v51-build",
                                  "--receipt",str(root/"v51-build/restore.json")], json.loads(log.read_text()))
                self.assertFalse(marker.exists())


if __name__ == "__main__":unittest.main()
