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
        for profile in ("docs", "full"):
            f = self.fixture(profile)
            outputs = f.root / "outputs"
            result = subprocess.run([sys.executable, "-m", "scripts.ci_plan", "--output", "retained"],
                                    cwd=f.root, env=dict(f.env, GITHUB_OUTPUT=str(outputs)), capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            actual = dict(line.split("=", 1) for line in outputs.read_text().splitlines())
            self.assertEqual(f.outputs, actual)
            self.assertEqual(f.plan, json.loads((f.root / "retained/execution-plan.json").read_text()))
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
        f = self.fixture()
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


if __name__ == "__main__":unittest.main()
