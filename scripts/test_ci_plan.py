"""Exercise real execution receipts and independently replayed Required gates."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from scripts import ci_plan as p, ci_required, ci_suites as s
from scripts.ci_test_support import PlanFixture


class ExecutionPlanTest(unittest.TestCase):
    def fixture(self, profile="full"):
        fixture = PlanFixture(profile)
        self.addCleanup(fixture.close)
        return fixture

    def needs(self, plan):
        needs = {k: dict(result=v, outputs={}) for k, v in plan["recipe"]["expectedResults"].items()}
        needs["changes"] = dict(result="success", outputs=p.outputs(plan))
        return needs

    def test_real_classification_and_required_cli_replay_docs_and_full(self):
        for profile in ("docs", "full", "integration"):
            f = self.fixture(profile)
            outputs = f.root / "outputs"
            result = subprocess.run([sys.executable, "-m", "scripts.ci_plan", "--output", "retained"],
                                    cwd=f.root, env=dict(f.env, GITHUB_OUTPUT=str(outputs)), capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            actual = dict(line.split("=", 1) for line in outputs.read_text().splitlines())
            self.assertEqual(f.outputs, actual)
            self.assertEqual(f.plan, json.loads((f.root / "retained/execution-plan.json").read_text()))
            if profile == "integration":
                self.assertEqual("true", actual["run_full_ci"])
                self.assertEqual("false", actual["run_canonical"])
                self.assertEqual(43, f.plan["recipe"]["executedJobCount"])
            needs = self.needs(f.plan)
            for modified, success in ((needs, True), ({**needs, "orphan": dict(result="success", outputs={})}, False)):
                result = subprocess.run([sys.executable, "-m", "scripts.ci_required"], cwd=f.root,
                                        env=dict(f.env, CI_NEEDS_JSON=json.dumps(modified)), capture_output=True, text=True)
                self.assertEqual(success, result.returncode == 0, result.stdout + result.stderr)

    def test_every_output_and_plan_binding_is_checked_against_independent_replay(self):
        f = self.fixture()
        registry = s.load_registry()
        for key in p.OUTPUTS:
            for change in ("missing", "corrupt", "extra"):
                outputs = dict(f.outputs)
                if change == "missing":del outputs[key]
                elif change == "extra":outputs["unknown"] = "x"
                else:outputs[key] = "tampered"
                with self.subTest(key=key, change=change), self.assertRaises(ValueError):
                    p.checked_outputs(outputs, registry, f.plan)
        for key in f.plan["identity"]:
            plan = copy.deepcopy(f.plan);plan["identity"][key] = "stale-or-forged"
            with self.subTest(identity=key), self.assertRaises(ValueError):
                p.checked_outputs(p.outputs(plan), registry, f.plan)
        for key in f.plan["bindings"]:
            plan = copy.deepcopy(f.plan);plan["bindings"][key] = "0" * 64
            with self.subTest(binding=key), self.assertRaises(ValueError):
                p.checked_outputs(p.outputs(plan), registry, f.plan)
        plan = copy.deepcopy(f.plan);plan["profile"] = "integration"
        with self.assertRaises(ValueError):p.checked_outputs(p.outputs(plan), registry, f.plan)

    def test_old_baseline_policy_is_valid_conservative_full_but_missing_plan_is_not(self):
        f = self.fixture("docs")
        original = p.shadow.blob
        from unittest.mock import patch
        def old(root, source, path):
            if source == f.graph.base and path == p.shadow.POLICY:
                return json.dumps(p.shadow.POLICY_V1).encode()
            return original(root, source, path)
        with patch.object(p.shadow, "blob", side_effect=old):
            plan, _ = p.compute(f.root, f.env, f.graph.event)
        self.assertEqual("full", plan["profile"])
        self.assertEqual(["POLICY_INVALID"], plan["reasons"])
        needs = self.needs(plan);del needs["changes"]["outputs"]["plan"]
        self.assertEqual("FAIL", ci_required.evaluate(needs, s.load_registry(), plan)["status"])

    def test_dirty_execution_input_fails_generation_and_cannot_emit_successful_fallback(self):
        f = self.fixture()
        for path in p.BINDINGS:
            file = f.root / path; data = file.read_bytes();file.write_bytes(data + b"\n")
            with self.subTest(path=path), self.assertRaises(ValueError):
                p.compute(f.root, f.env, f.graph.event)
            file.write_bytes(data)

    def test_selected_and_unselected_integration_results_require_the_complete_inventory(self):
        f = self.fixture("integration")
        registry = s.load_registry();plan = copy.deepcopy(f.plan)
        plan.update(profile="integration", candidateProfile="integration", recipe=p.shadow.suite_plan(registry, "integration"))
        self.assertEqual("PASS", ci_required.evaluate(self.needs(plan), registry, plan)["status"])
        for job, expected in plan["recipe"]["expectedResults"].items():
            for result in ("success", "skipped", "failure", "cancelled", "timed_out", "missing"):
                needs = self.needs(plan)
                if result == "missing":del needs[job]
                else:needs[job]["result"] = result
                with self.subTest(job=job, result=result):
                    self.assertEqual(result == expected, ci_required.evaluate(needs, registry, plan)["status"] == "PASS")

    def test_integration_rule_rejects_new_delete_rename_mode_type_mixed_and_unknown_changes(self):
        for mutation in ("new", "delete", "rename", "mode", "type", "mixed", "new-version"):
            f = self.fixture("integration");g = f.graph
            g.git("checkout", "-q", "master")
            # Start a new reviewed-base branch, never alter the receipt's graph.
            g.base = g.git("rev-parse", "HEAD")
            g.git("branch", "-D", "topic")
            path = p.shadow.INTEGRATION_PATH
            if mutation == "new":
                (g.root / path).unlink();g.base = g.commit()
            g.git("checkout", "-qb", "topic")
            g.write(path, b"// next example content\n")
            if mutation == "delete":(g.root / path).unlink()
            elif mutation == "rename":g.git("mv", path, "TravelDemo.md")
            elif mutation == "mode":(g.root / path).chmod(0o755)
            elif mutation == "type":
                (g.root / path).unlink();(g.root / path).symlink_to("other.java")
            elif mutation == "mixed":g.write("pom.xml", b"build input\n")
            elif mutation == "new-version":g.write("scripts/v52/helper.py", b"# new\n")
            head = g.commit();g.git("checkout", "-q", "master");g.git("merge", "--no-ff", "-qm", "merge", "topic")
            source = g.git("rev-parse", "HEAD")
            env = {**f.env, "GITHUB_SHA": source, "GITHUB_WORKFLOW_SHA": source}
            event = copy.deepcopy(g.event);event["pull_request"]["base"]["sha"] = g.base;event["pull_request"]["head"]["sha"] = head
            with self.subTest(mutation=mutation):
                plan, _ = p.compute(g.root, env, event)
                self.assertEqual("full", plan["profile"], plan)

    def test_trusted_force_full_rollback_and_policy_edit_cannot_downgrade_itself(self):
        from unittest.mock import patch
        f = self.fixture("integration")
        original = p.shadow.blob
        policy = {**p.shadow.POLICY_V2, "forceFull": True}
        data = (json.dumps(policy) + "\n").encode()
        (f.root / p.shadow.POLICY).write_bytes(data)
        def forced(root, source, path):
            return data if path == p.shadow.POLICY else original(root, source, path)
        with patch.object(p.shadow, "blob", side_effect=forced):
            plan, _ = p.compute(f.root, f.env, f.graph.event)
        self.assertEqual(("integration", "full"), (plan["candidateProfile"], plan["profile"]))
        self.assertIn("FORCE_FULL", plan["reasons"])
        # Different old/new policies are a full rollout even for the candidate.
        def rollout(root, source, path):
            if path == p.shadow.POLICY:
                return json.dumps(p.shadow.POLICY_V2).encode() if source == f.graph.base else data
            return original(root, source, path)
        with patch.object(p.shadow, "blob", side_effect=rollout):
            plan, _ = p.compute(f.root, f.env, f.graph.event)
        self.assertEqual("full", plan["profile"])
        self.assertEqual(["POLICY_CHANGED"], plan["reasons"])

    def test_master_and_manual_never_use_integration_for_the_candidate(self):
        f = self.fixture("integration")
        env = {**f.env, "GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/master",
               "GITHUB_WORKFLOW_REF": f.graph.env["GITHUB_REPOSITORY"] + "/" + p.shadow.WORKFLOW + "@refs/heads/master"}
        event = dict(repository=f.graph.event["repository"], before=f.graph.base, after=f.graph.source, ref="refs/heads/master")
        plan, _ = p.compute(f.root, env, event)
        self.assertEqual("full", plan["profile"])
        for name in ("workflow_dispatch", "schedule", "unknown"):
            plan, _ = p.compute(f.root, {**env, "GITHUB_EVENT_NAME": name}, event)
            self.assertEqual("full", plan["profile"])

    def test_documentation_can_mix_with_the_exact_candidate_but_ci_self_changes_are_full(self):
        for path, expected in (("docs/guide.md", "integration"), (p.shadow.PLANNER, "full"),
                               ("scripts/ci_plan.py", "full"), (p.shadow.REGISTRY, "full")):
            f = self.fixture("integration");g = f.graph
            g.base = g.git("rev-parse", "HEAD");g.git("branch", "-D", "topic")
            before = (g.root / path).read_bytes() if (g.root / path).exists() else b""
            g.pr({p.shadow.INTEGRATION_PATH: b"next example\n", path: before + b"\n"})
            f.install_health(g.base)
            plan, _ = p.compute(g.root, {**f.env, **g.env}, g.event)
            self.assertEqual(expected, plan["profile"], path)

    def test_optional_tiers_remain_explicitly_disabled(self):
        registry = s.load_registry()
        for profile in ("consumer", "python-isolated", "core"):
            with self.subTest(profile=profile), self.assertRaises(ValueError):p.shadow.suite_plan(registry, profile)
        for rules in (["consumer"], ["python-isolated"], ["scripts/*.py"], ["examples/**"],
                      [p.shadow.INTEGRATION_RULE, p.shadow.INTEGRATION_RULE]):
            self.assertFalse(p.shadow.valid_policy({**p.shadow.POLICY_V2, "integrationRules": rules}))


if __name__ == "__main__":unittest.main()
