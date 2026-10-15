"""Shadow-only decisions over real temporary Git graphs and historical paths."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import ci_changes, ci_shadow_plan as p, ci_suites as s

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "patricklfdm/GeneralSearchEngine"


class ShadowPlanTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ci shadow graph ")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.git_env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                            GIT_AUTHOR_NAME="Fixture", GIT_COMMITTER_NAME="Fixture",
                            GIT_AUTHOR_EMAIL="fixture@example.invalid", GIT_COMMITTER_EMAIL="fixture@example.invalid")
        self.git("init", "-q", "-b", "master")
        for path in (p.WORKFLOW, p.PLANNER, p.REGISTRY, p.SUITE_VALIDATOR,
                     "scripts/ci_plan.py", "scripts/ci_required.py", "scripts/ci_changes.py", "scripts/ci_observation.py", "scripts/ci_health.py",
                     ".github/workflows/release.yml", ".github/actions/v51-restore-build/action.yml",
                     ".github/actions/v51-retain-build/action.yml"):
            self.write(path, (ROOT / path).read_bytes())
        # Scenario fixtures start with integration enabled regardless of the deployed
        # rollback switch. ExecutionPlanTest also exercises the actual policy via CLI.
        self.write(p.POLICY, (json.dumps(p.POLICY_V2, indent=2) + "\n").encode())
        self.write("src/main/java/Engine.java", b"// original source\n")
        self.write(p.INTEGRATION_PATH, b"// original example\n")
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                                       cwd=self.root, env=self.git_env, stderr=subprocess.PIPE).decode().strip()

    def write(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def pr(self, changes=None):
        self.git("checkout", "-qb", "topic")
        for name, data in (changes or {"docs/guide.md": b"Guide\n"}).items():
            self.write(name, data)
        self.head = self.commit()
        self.git("checkout", "-q", "master")
        self.git("merge", "--no-ff", "-qm", "synthetic PR test merge", "topic")
        self.source = self.git("rev-parse", "HEAD")
        ref = "refs/pull/325/merge"
        self.env = dict(GITHUB_SHA=self.source, GITHUB_REPOSITORY=REPOSITORY,
                        GITHUB_EVENT_NAME="pull_request", GITHUB_REF=ref, GITHUB_WORKFLOW_SHA=self.source,
                        GITHUB_WORKFLOW_REF=REPOSITORY + "/" + p.WORKFLOW + "@" + ref,
                        GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="2", ACTUAL_RUN_FULL_CI="false")
        self.event = dict(repository=dict(full_name=REPOSITORY), number=325, pull_request=dict(
            base=dict(sha=self.base, ref="master", repo=dict(full_name=REPOSITORY)),
            head=dict(sha=self.head, repo=dict(full_name="fork-owner/GeneralSearchEngine"))))

    def result(self, expected="full", code=None):
        report = p.plan(self.root, self.env, self.event)
        self.assertEqual(expected, report["recommendedProfile"], report)
        self.assertFalse(report["coreEligible"])
        if code:
            self.assertEqual([code], report["reasons"])
        return report

    def test_docs_fork_pr_binds_test_merge_head_policy_workflow_and_attempt(self):
        self.pr()
        report = self.result("docs", "DOCS_ONLY")
        self.assertEqual("docs", report["actualProfile"])
        self.assertEqual(self.source, report["testedSha"])
        self.assertNotEqual(report["testedSha"], report["headSha"])
        self.assertEqual(self.head, report["headSha"])
        self.assertEqual(self.base, report["mergeBaseSha"])
        self.assertEqual(self.base, report["policy"]["source"])
        self.assertEqual("2", report["runAttempt"])
        self.assertEqual(p.digest((self.root / p.WORKFLOW).read_bytes()), report["workflow"]["sha256"])
        self.assertEqual(p.digest((self.root / p.POLICY).read_bytes()), report["policy"]["sha256"])
        self.assertEqual(["docs/guide.md"], report["changedPaths"])
        self.assertEqual(p.digest((self.root / p.REGISTRY).read_bytes()), report["registry"]["sha256"])
        self.assertEqual("gse-ci-shadow-plan-v2", report["schema"])
        self.assertEqual(2, report["suitePlan"]["candidate"]["executedJobCount"])
        self.assertEqual({"skipped"}, set(report["suitePlan"]["candidate"]["expectedResults"].values()))

    def test_exact_raw_status_mode_type_and_blobs_are_bound(self):
        self.git("checkout", "-qb", "topic")
        self.write("src/main/java/Engine.java", b"// changed\n")
        self.git("update-index", "--chmod=+x", "src/main/java/Engine.java")
        (self.root / "src/main/java/Engine.java").chmod(0o755)
        self.write("new.java", b"new\n")
        self.write("old.java", b"old\n")
        # Record a real type change and deletion on the same complete PR diff.
        self.git("checkout", "-q", "master")
        self.git("add", "--all"); self.git("commit", "-qm", "base files")
        self.base = self.git("rev-parse", "HEAD")
        self.git("branch", "-D", "topic")
        (self.root / "old.java").unlink()
        (self.root / "new.java").unlink(); (self.root / "new.java").symlink_to("old.java")
        self.pr({"src/main/java/Engine.java": b"// content only\n"})
        report = self.result(code="BUILD_OR_UNKNOWN_PATH")
        rows = {v["path"]: v for v in report["changes"]}
        self.assertEqual(("D", "absent"), (rows["old.java"]["status"], rows["old.java"]["newType"]))
        self.assertEqual(("T", "symlink"), (rows["new.java"]["status"], rows["new.java"]["newType"]))
        row = rows["src/main/java/Engine.java"]
        self.assertEqual(("M", "100755", "100755"), (row["status"], row["oldMode"], row["newMode"]))
        self.assertNotEqual(row["oldBlob"], row["newBlob"])
        self.assertEqual(47, report["suitePlan"]["candidate"]["executedJobCount"])

    def test_registry_missing_dirty_or_invalid_cannot_produce_selection(self):
        self.pr()
        for path in (p.REGISTRY, p.SUITE_VALIDATOR):
            original = (self.root / path).read_bytes()
            for data in (b"{}", b"bad registry"):
                self.write(path, data)
                report = self.result(code="REGISTRY_UNAVAILABLE")
                self.assertIsNone(report["suitePlan"])
            self.write(path, original)

    def test_raw_parser_rejects_duplicate_and_inconsistent_records(self):
        row = b":100644 100644 " + b"a" * 40 + b" " + b"b" * 40 + b" M\0file.java\0"
        self.assertEqual(1, len(p.change_records(row)))
        for raw in (row + row, row.replace(b" M\0", b" R100\0"), row.replace(b"100644", b"999999", 1),
                    row.replace(b"a" * 40, b"0" * 40), row.replace(b"file.java", b"../file.java")):
            with self.subTest(raw=raw), self.assertRaises(p.Unavailable):p.change_records(raw)

    def test_closed_suite_recipes_keep_matrix_group_and_dependency_closure(self):
        registry = s.load_registry()
        for profile, count in (("docs", 2), ("integration", 44), ("full", 47)):
            result = p.suite_plan(registry, profile)
            self.assertEqual(count, result["executedJobCount"])
            self.assertEqual(len(registry["suites"]), len(result["expectedResults"]))
        result = p.suite_plan(registry, "integration")
        self.assertEqual(["v51-owned-canonical"], [key for key, value in result["expectedResults"].items() if value == "skipped"])
        bad = copy.deepcopy(registry)
        next(v for v in bad["suites"] if v["id"] == "v51-remote-faults")["needs"].append("v51-owned-canonical")
        with self.assertRaises(p.Unavailable):p.suite_plan(bad, "integration")
        with self.assertRaises(p.Unavailable):p.suite_plan(registry, "custom")

    def test_multiple_commit_diff_and_base_only_changes(self):
        # A PR branches before an unrelated master change; only head-side changes
        # enter the three-dot diff, but an early code commit remains included.
        self.git("checkout", "-qb", "topic")
        self.write("src/main/java/Engine.java", b"// changed\n"); self.commit()
        self.write("docs/final.md", b"last PR commit\n"); head = self.commit()
        self.git("checkout", "-q", "master")
        self.write("master-only.json", b"{}\n"); base = self.commit()
        self.git("merge", "--no-ff", "-qm", "test merge", "topic")
        source = self.git("rev-parse", "HEAD")
        self.env = dict(GITHUB_SHA=source, GITHUB_REPOSITORY=REPOSITORY, GITHUB_EVENT_NAME="pull_request",
                        GITHUB_REF="refs/pull/325/merge", GITHUB_WORKFLOW_SHA=source,
                        GITHUB_WORKFLOW_REF=REPOSITORY + "/" + p.WORKFLOW + "@refs/pull/325/merge",
                        GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1", ACTUAL_RUN_FULL_CI="true")
        self.event = dict(repository=dict(full_name=REPOSITORY), number=325,
                          pull_request=dict(base=dict(sha=base, ref="master", repo=dict(full_name=REPOSITORY)), head=dict(sha=head)))
        report = self.result(code="BUILD_OR_UNKNOWN_PATH")
        self.assertEqual(self.base, report["mergeBaseSha"])
        self.assertCountEqual(["docs/final.md", "src/main/java/Engine.java"], report["changedPaths"])

    def test_rename_from_source_to_docs_retains_both_paths(self):
        self.git("checkout", "-qb", "rename")
        self.git("mv", "src/main/java/Engine.java", "Engine.md"); self.commit()
        self.git("checkout", "-q", "master")
        self.git("merge", "--ff-only", "-q", "rename")
        self.pr()
        # Rebuild just the tested merge with the original base and renamed head.
        tree = self.git("rev-parse", "HEAD^{tree}")
        self.source = self.git("commit-tree", tree, "-p", self.base, "-p", self.head, "-m", "test merge")
        self.git("checkout", "--detach", "-q", self.source)
        self.env.update(GITHUB_SHA=self.source, GITHUB_WORKFLOW_SHA=self.source)
        report = self.result(code="BUILD_OR_UNKNOWN_PATH")
        self.assertIn("src/main/java/Engine.java", report["changedPaths"])
        self.assertIn("Engine.md", report["changedPaths"])

    def test_no_path_count_truncation_and_no_shell_interpolation(self):
        changes = {f"docs/{i}.md": b"x" for i in range(3510)}
        changes.update({"docs/$(touch SHOULD_NOT_EXIST)\n`echo hi`.md": b"x", "new-build-input": b"x"})
        self.pr(changes)
        report = self.result(code="BUILD_OR_UNKNOWN_PATH")
        self.assertEqual(3512, len(report["changedPaths"]))
        self.assertFalse((self.root / "SHOULD_NOT_EXIST").exists())

    def test_push_and_manual_profiles_preserve_actual_decision(self):
        self.pr()
        self.env.update(GITHUB_EVENT_NAME="push", GITHUB_REF="refs/heads/master",
                        GITHUB_WORKFLOW_REF=REPOSITORY + "/" + p.WORKFLOW + "@refs/heads/master")
        self.event = dict(repository=dict(full_name=REPOSITORY), before=self.base, after=self.source, ref="refs/heads/master")
        self.result("docs", "DOCS_ONLY")
        self.event["after"] = self.head
        self.result(code="CONTEXT_UNAVAILABLE")
        self.event["after"] = self.source
        for event in ("workflow_dispatch", "pull_request_target", "unknown"):
            self.env["GITHUB_EVENT_NAME"] = event
            report = self.result(code="MANUAL_OR_UNKNOWN")
            self.assertEqual("docs", report["actualProfile"])

    def test_invalid_source_context_or_merge_identity_never_recommends_docs(self):
        self.pr()
        good = dict(self.env)
        for key, value in (("GITHUB_SHA", self.head), ("GITHUB_SHA", "$(touch bad)"),
                           ("GITHUB_WORKFLOW_SHA", self.base), ("GITHUB_WORKFLOW_REF", "other/workflow"),
                           ("GITHUB_REPOSITORY", "other/repository"), ("GITHUB_REF", "refs/heads/master"),
                           ("GITHUB_RUN_ID", ""), ("GITHUB_RUN_ATTEMPT", "0")):
            with self.subTest(key=key):
                self.env = {**good, key: value}; self.result(code="CONTEXT_UNAVAILABLE")
        self.env = good
        event = copy.deepcopy(self.event)
        for key, value in (("sha", self.head), ("ref", "not-master"), ("repo", {"full_name": "fork/repo"})):
            with self.subTest(base=key):
                self.event = copy.deepcopy(event); self.event["pull_request"]["base"][key] = value
                self.result(code="CONTEXT_UNAVAILABLE")

    def test_missing_history_empty_or_malformed_diff_are_full(self):
        self.pr()
        original = p.git
        for changed in (b"", b"no-nul.md", b"\0", b"../README.md\0", b"/README.md\0"):
            def git(root, *args):
                return changed if args[0] == "diff" else original(root, *args)
            with self.subTest(changed=changed), patch.object(p, "git", side_effect=git):
                self.result(code="EMPTY_OR_INVALID_DIFF")
        for error in (OSError(), subprocess.CalledProcessError(128, "git"), subprocess.TimeoutExpired("git", 15)):
            with patch.object(p, "git", side_effect=error):
                self.result(code="HISTORY_UNAVAILABLE")

    def test_changed_policy_cannot_authorize_its_own_core_paths(self):
        value = copy.deepcopy(p.POLICY_V2); value["integrationRules"] = ["src/main/java/Engine.java"]
        self.pr({p.POLICY: json.dumps(value).encode(), "src/main/java/Engine.java": b"// changed\n"})
        report = self.result(code="POLICY_CHANGED")
        self.assertNotEqual(report["policy"]["sha256"], report["policy"]["testedSha256"])
        self.assertEqual(self.base, report["policy"]["source"])

    def test_unapproved_baseline_policy_and_first_rollout_recommend_full(self):
        self.pr()
        original = p.blob
        bad = [b"{}", b'{"schema":1,"schema":2}', b"not JSON"]
        for key, value in (("mode", "shadow"), ("integrationRules", ["README.md"]),
                           ("forceFull", 1), ("documentationRule", "all-docs-directory")):
            policy = copy.deepcopy(p.POLICY_V2); policy[key] = value; bad.append(json.dumps(policy).encode())
        for data in bad:
            def blob(root, source, path):
                return data if source == self.base and path == p.POLICY else original(root, source, path)
            with self.subTest(data=data), patch.object(p, "blob", side_effect=blob):
                self.result(code="POLICY_INVALID")
        def unavailable(root, source, path):
            if source == self.base and path == p.POLICY:
                raise subprocess.CalledProcessError(128, "git")
            return original(root, source, path)
        with patch.object(p, "blob", side_effect=unavailable):
            report = self.result(code="POLICY_UNAVAILABLE")
            self.assertEqual(["docs/guide.md"], report["changedPaths"])

    def test_dirty_source_or_deleted_policy_is_full(self):
        self.pr()
        for path in (p.POLICY, p.PLANNER, p.WORKFLOW):
            before = (self.root / path).read_bytes()
            (self.root / path).unlink()
            self.result()
            self.write(path, before)

    def test_missing_actual_result_and_bad_event_recorded_without_outputs(self):
        self.pr(); self.env["ACTUAL_RUN_FULL_CI"] = "core"
        report = self.result(code="ACTUAL_UNKNOWN")
        self.assertEqual("unknown", report["actualProfile"])
        for event in (None, [], {}, {"pull_request": None}):
            self.event = event; self.result(code="CONTEXT_UNAVAILABLE")

    def test_cli_retains_plan_summary_without_modifying_actual_github_output(self):
        self.pr()
        payload = self.root / "event.json"; payload.write_text(json.dumps(self.event))
        output = self.root / "outputs"; output.write_text("run_full_ci=false\n")
        summary = self.root / "summary.md"
        env = dict(os.environ, **self.env, GITHUB_EVENT_PATH=str(payload), GITHUB_OUTPUT=str(output),
                   GITHUB_STEP_SUMMARY=str(summary), PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, str(self.root / p.PLANNER), "--output", str(self.root / "evidence")],
                                cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads((self.root / "evidence/plan.json").read_text())
        self.assertEqual("docs", report["recommendedProfile"])
        self.assertIn("Actual execution profile", summary.read_text())
        self.assertIn("Shadow recommendation", summary.read_text())
        self.assertEqual("run_full_ci=false\n", output.read_text())
        payload.write_text("{bad event")
        result = subprocess.run([sys.executable, str(self.root / p.PLANNER), "--output", str(self.root / "bad-event")],
                                cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads((self.root / "bad-event/plan.json").read_text())
        self.assertEqual(["CONTEXT_UNAVAILABLE"], report["reasons"])
        self.assertEqual("full", report["recommendedProfile"])
        self.assertEqual("run_full_ci=false\n", output.read_text())

    def test_summary_does_not_render_untrusted_event_text_as_markup(self):
        self.pr(); self.env["GITHUB_EVENT_NAME"] = "<script>bad</script>|\n`code`"
        report = self.result(code="MANUAL_OR_UNKNOWN")
        rendered = p.summary(report)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("&#124;", rendered)


class ShadowPolicyContractTest(unittest.TestCase):
    def test_historical_pr_paths_match_conservative_rule(self):
        fixture = json.loads((ROOT / "scripts/fixtures/ci-shadow-history-v1.json").read_text())
        self.assertEqual([322, 323, 324], [row["pullRequest"] for row in fixture["pullRequests"]])
        for row in fixture["pullRequests"]:
            self.assertNotEqual(row["headSha"], row["mergeSha"])
            paths = row["changedPaths"]
            self.assertTrue(paths)
            profile = "docs" if all(p.documentation(path) for path in paths) else "full"
            self.assertEqual(row["expectedPathProfile"], profile)
            for path in paths:
                self.assertEqual(ci_changes.is_documentation(path), p.documentation(path))

    def test_release_runtime_oracle_permissions_and_unknown_inputs_remain_full(self):
        paths = ["src/main/java/Engine.java", "module/src/test/resources/fixture.md",
                 "scripts/v51/cloud_permissions.py", "scripts/v51/cloud_cleanup.py", "scripts/v51/cloud_lease.py",
                 "scripts/v51/public_protocol_evidence.py", "scripts/v51/artifact_version.py",
                 "scripts/v51/test_phase7_release_fixtures.py", "scripts/verify-published-release.sh",
                 "scripts/ci_suite_registry.json", "scripts/ci_v51_bundle.py", p.POLICY,
                 "docs/v5x/v5.1/candidate-artifacts.sha256", "docs/v5x/v5.1/release-toolchain.json",
                 "docs/plan.json", "new-module/pom.xml", ".mvn/new-input", ".github/actions/helper.md",
                 ".github/workflows/release.yml", "future/input.unknown", "scripts/README.md"]
        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(p.documentation(path))
                self.assertEqual(ci_changes.is_documentation(path), p.documentation(path))
        policy = p.strict_json((ROOT / p.POLICY).read_bytes())
        self.assertIs(type(policy["forceFull"]), bool)
        self.assertEqual({**p.POLICY_V2, "forceFull": policy["forceFull"]}, policy)
        self.assertEqual([p.INTEGRATION_RULE], p.POLICY_V2["integrationRules"])

    def test_shadow_cannot_replace_classifier_or_gate_and_retention_is_attempt_specific(self):
        workflow = (ROOT / p.WORKFLOW).read_text()
        related = {".github/workflows/release.yml": (ROOT / ".github/workflows/release.yml").read_text()}
        replacements = [
            ("run_full_ci: ${{ steps.scope.outputs.run_full_ci }}", "run_full_ci: ${{ steps.shadow.outputs.profile }}"),
            (s.FULL_IF, "${{ needs.changes.outputs.shadow == 'full' }}"),
            ("ACTUAL_RUN_FULL_CI: ${{ steps.scope.outputs.run_full_ci }}", "ACTUAL_RUN_FULL_CI: 'false'"),
            ("name: Observe the CI shadow plan", "name: Observe the CI shadow plan\n        id: shadow"),
            ("name: Retain the CI shadow plan", "name: Retain something else"),
            ("ci-shadow-plan-${{ github.run_id }}-${{ github.run_attempt }}", "ci-shadow-plan-${{ github.run_id }}"),
            ("run: python3 -m scripts.ci_shadow_plan --output target/ci-shadow-plan", "run: echo ignored"),
        ]
        for before, after in replacements:
            self.assertIn(before, workflow)
            with self.subTest(after=after), self.assertRaises((ValueError, KeyError)):
                s.validate_workflow(s.load_registry(), workflow.replace(before, after, 1), related)


if __name__ == "__main__":
    unittest.main()
