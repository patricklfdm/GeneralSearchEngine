"""Required's result policy, legacy shell parity, and real entry-point failures."""
import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest

from scripts import ci_required as gate, ci_suites as suites
from scripts.ci_changes import decide
from scripts.ci_test_support import PlanFixture
from unittest.mock import patch


class RequiredTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = {full: PlanFixture("full" if full else "docs") for full in (True, False)}
        for fixture in cls.fixtures.values():cls.addClassCleanup(fixture.close)
        cls.registry = suites.load_registry()
        cls.ids = [s["id"] for s in cls.registry["suites"]]
        legacy = (suites.ROOT / "scripts/fixtures/ci-required-v1.txt").read_text()
        cls.bindings = re.findall(r"^          (\w+): \$\{\{ needs\.([\w-]+)\.result \}\}$", legacy, re.M)
        cls.legacy = textwrap.dedent(legacy.split("        run: |\n", 1)[1])

    def needs(self, full=True):
        value = {key: dict(result="success" if full else "skipped", outputs={}) for key in self.ids}
        value["changes"] = dict(result="success", outputs=dict(self.fixtures[full].outputs))
        return value

    def result(self, value):
        return gate.evaluate(value, self.registry)

    def legacy_result(self, value):
        env = dict(os.environ, RUN_FULL_CI=value.get("changes", {}).get("outputs", {}).get("run_full_ci", ""))
        env.update({key: value.get(job, {}).get("result", "") for key, job in self.bindings})
        return subprocess.run(["bash", "-e", "-c", self.legacy], env=env, capture_output=True).returncode == 0

    def assert_rejected(self, value, job):
        result = self.result(value)
        self.assertEqual("FAIL", result["status"])
        self.assertIn(job, {e["job"] for e in result["errors"]})
        return result

    def test_full_and_docs_match_legacy_success(self):
        self.assertEqual((set(self.ids) - {job for job in self.ids if job.startswith(("v52-", "python-v52-"))}) | {"changes"}, {job for _, job in self.bindings})
        for full in (True, False):
            value = self.needs(full)
            self.assertTrue(self.legacy_result(value))
            self.assertEqual("PASS", self.result(value)["status"])

    def test_every_lane_result_and_missing_match_legacy(self):
        for full in (True, False):
            expected = "success" if full else "skipped"
            for job in self.ids:
                for actual in ("success", "skipped", "failure", "cancelled", "unknown", "", None):
                    with self.subTest(full=full, job=job, actual=actual):
                        value = self.needs(full)
                        if actual is None:
                            del value[job]
                        else:
                            value[job]["result"] = actual
                        if not job.startswith(("v52-", "python-v52-")):
                            self.assertEqual(actual == expected, self.legacy_result(value))
                        self.assertEqual(actual == expected, self.result(value)["status"] == "PASS")
                        if actual != expected:
                            self.assert_rejected(value, job)

    def test_classifier_failure_or_absence_never_passes(self):
        for actual in ("failure", "cancelled", "skipped", "unknown", "", None):
            value = self.needs()
            if actual is None:
                del value["changes"]
            else:
                value["changes"]["result"] = actual
            self.assert_rejected(value, "changes")
            self.assertFalse(self.legacy_result(value))

    def test_invalid_scope_and_outputs_rejected(self):
        for output in ({}, {"run_full_ci": "core"}, {"run_full_ci": True}, {"run_full_ci": None},
                       {"run_full_ci": "True"}, {"run_full_ci": "false", "profile": "docs"}, None):
            value = self.needs(False); value["changes"]["outputs"] = output
            self.assert_rejected(value, "changes")

    def test_missing_unknown_and_invalid_dependency_fields(self):
        for replacement in (None, [], {}, {"result": "success"}, {"outputs": {}},
                            {"result": "success", "outputs": {}, "extra": "field"},
                            {"result": "success", "outputs": []}, {"result": "success", "outputs": {"id": 1}},
                            {"result": True, "outputs": {}}, {"result": None, "outputs": {}}):
            value = self.needs(); value[self.ids[0]] = replacement
            self.assert_rejected(value, self.ids[0])
        value = self.needs(); value["orphan"] = dict(result="success", outputs={})
        self.assert_rejected(value, "orphan")
        for value in (None, [], "success", True):
            self.assert_rejected(value, "needs")

    def test_all_failures_are_reported_together(self):
        value = self.needs()
        for key in self.ids[:3]:value[key]["result"] = "failure"
        result = self.result(value)
        self.assertEqual(set(self.ids[:3]), {e["job"] for e in result["errors"]})
        for error in result["errors"]:
            self.assertEqual("failure", error["actual"])
            self.assertEqual("success", error["expected"])
            self.assertTrue(error["reason"])

    def test_valid_producer_outputs_do_not_require_new_child_receipts(self):
        value = self.needs()
        value["v51-verification-build"]["outputs"] = {"artifact_id": "1234"}
        value["v51-remote-rich-shards"]["outputs"] = {"published_controls": "1", "automatic_healthy": "2", "automatic_concurrent": "3"}
        self.assertEqual("PASS", self.result(value)["status"])
        self.assertEqual("PASS", self.result(self.needs(False))["status"])

    def invoke(self, raw, root=suites.ROOT):
        output = io.StringIO()
        try:
            full = json.loads(raw)["changes"]["outputs"].get("profile") != "docs"
        except (ValueError, TypeError, KeyError, AttributeError):full = True
        fixture = self.fixtures[full]
        env = dict(fixture.env)
        if raw is not None:env["CI_NEEDS_JSON"] = raw
        with contextlib.redirect_stdout(output):
            code = gate.main(env, fixture.root if root == suites.ROOT else root)
        return code, json.loads(output.getvalue())

    def test_entry_point_uses_real_inventory_and_fails_closed(self):
        for full in (True, False):
            code, result = self.invoke(json.dumps(self.needs(full)))
            self.assertEqual(0, code);self.assertEqual("PASS", result["status"])
        with tempfile.TemporaryDirectory() as root:
            code, result = self.invoke(json.dumps(self.needs()), Path(root))
            self.assertNotEqual(0, code);self.assertEqual("FAIL", result["status"])

    def test_invalid_duplicate_nonfinite_or_oversized_json(self):
        for raw in (None, "", "{", "null", "[]", '{"changes":{},"changes":{}}',
                    '{"changes":{"result":"success","result":"failure","outputs":{}}}',
                    '{"changes":NaN}', '"' + 'x' * suites.LIMIT + '"'):
            with self.subTest(raw=repr(raw)[:80]):
                code, result = self.invoke(raw)
                self.assertNotEqual(0, code);self.assertEqual("FAIL", result["status"])

    def test_untrusted_values_are_json_data_not_shell(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "executed"
            value = self.needs(); value[self.ids[0]]["result"] = f'$(touch {marker})\n::error::fake'
            code, result = self.invoke(json.dumps(value))
            self.assertNotEqual(0, code);self.assertFalse(marker.exists())
            self.assertEqual(value[self.ids[0]]["result"], result["errors"][0]["actual"])

    def test_docs_disguise_cannot_pass_through_classifier_and_required(self):
        event = {"pull_request": {"base": {"sha": "a" * 40}, "head": {"sha": "b" * 40}}}
        for diff in (b"README.md\0pom.xml\0", b"docs/Moved.md\0src/main/java/Old.java\0",
                     b"docs/plan.md\0scripts/ci_suite_registry.json\0"):
            with patch("scripts.ci_changes.subprocess.run") as git:
                git.return_value.stdout = diff
                full, _ = decide("pull_request", event, suites.ROOT)
            self.assertTrue(full)
            value = self.needs(False);value["changes"]["outputs"]["run_full_ci"] = str(full).lower()
            self.assertEqual("FAIL", self.result(value)["status"])


if __name__ == "__main__":unittest.main()
