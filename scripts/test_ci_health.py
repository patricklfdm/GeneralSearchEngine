"""Full health is fresh, exact-base, complete and conservatively rechecked."""
import copy
import json
import subprocess
import sys
import time
import unittest

from scripts import ci_health as h, ci_plan, ci_suites as s
from scripts.ci_test_support import PlanFixture


class HealthTest(unittest.TestCase):
    def setUp(self):
        self.f = PlanFixture("integration");self.addCleanup(self.f.close)
        self.registry = s.load_registry()
        self.data = copy.deepcopy(self.f.health_api)
        self.list_key = next(key for key in self.data if "workflows/" in key)
        self.jobs_key = next(key for key in self.data if "/jobs?" in key)

    def collect(self, **kwargs):
        return h.collect(self.f.root, self.f.env, self.f.graph.base, self.registry, self.f.plan["bindings"],
                         get=lambda path: copy.deepcopy(self.data[path]), **kwargs)

    def test_push_manual_and_nightly_full_are_health_only_and_expire(self):
        for event in ("push", "workflow_dispatch", "schedule"):
            self.data[self.list_key]["workflow_runs"][0]["event"] = event
            self.data["actions/runs/120"]["event"] = event
            value = self.collect()
            self.assertEqual("HEALTHY", value["status"])
            self.assertEqual(self.f.graph.base, value["source"])
            self.assertNotIn("fullRemoteQualification", value)
            self.assertEqual("STALE", self.collect(now=time.time()+h.MAX_AGE_SECONDS)["status"])

    def test_failed_pending_docs_cancelled_and_unknown_health_select_full(self):
        original = copy.deepcopy(self.data)
        for state, outcome in (("completed", "failure"), ("completed", "cancelled"), ("in_progress", None)):
            self.data = copy.deepcopy(original)
            self.data["actions/runs/120"].update(status=state, conclusion=outcome)
            self.assertNotEqual("HEALTHY", self.collect()["status"])
        self.data = original
        for job in self.data[self.jobs_key]["jobs"]:
            if job["name"] not in ("Required", "Change scope"):job["conclusion"] = "skipped"
        self.assertEqual("UNAVAILABLE", self.collect()["status"])
        self.f.health_file.write_text(json.dumps(self.data))
        plan, _ = ci_plan.compute(self.f.root, self.f.env, self.f.graph.event)
        self.assertEqual(("integration", "full"), (plan["candidateProfile"], plan["profile"]))
        self.assertEqual("HEALTH_UNAVAILABLE", plan["reasons"][-1])

    def test_missing_matrix_wrong_source_attempt_and_skipped_qualification_are_not_healthy(self):
        original = copy.deepcopy(self.data)
        for mutation in ("missing", "duplicate", "wrong-source", "wrong-attempt", "skipped", "hidden-step", "future"):
            self.data = copy.deepcopy(original)
            page = self.data[self.jobs_key];jobs = page["jobs"]
            row = next(j for j in jobs if j["name"].startswith("V5.1 owned canonical (repetition "))
            if mutation == "missing":jobs.remove(row);page["total_count"] -= 1
            elif mutation == "duplicate":jobs[-1] = copy.deepcopy(row)
            elif mutation == "wrong-source":row["head_sha"] = "a"*40
            elif mutation == "wrong-attempt":row["run_attempt"] = 2
            elif mutation == "skipped":row["conclusion"] = "skipped"
            elif mutation == "hidden-step":row["steps"][0]["conclusion"] = "skipped"
            else:row["completed_at"] = "2099-01-01T00:00:00Z"
            with self.subTest(mutation=mutation):self.assertEqual("UNAVAILABLE", self.collect()["status"])

    def test_newest_failed_run_is_not_replaced_with_an_older_green_run(self):
        newer = {**self.data["actions/runs/120"], "id": 121, "conclusion": "failure"}
        self.data["actions/runs/121"] = newer
        self.data[self.list_key].update(total_count=2, workflow_runs=[newer, self.data["actions/runs/120"]])
        value = self.collect()
        self.assertEqual(("FAILED", 121), (value["status"], value["runId"]))

    def test_history_listing_is_paginated_and_changed_or_unavailable_inputs_fail_closed(self):
        first = self.data[self.list_key]
        rows = [dict(self.f.health_run, id=i) for i in range(20,120)]
        first.update(total_count=101, workflow_runs=rows)
        self.data[self.list_key.replace("&page=1", "&page=2")] = dict(total_count=101, workflow_runs=[self.f.health_run])
        # API order is newest first; keep latest on page 1 for the stable recheck.
        first["workflow_runs"][0] = self.f.health_run
        self.data[self.list_key.replace("&page=1", "&page=2")]["workflow_runs"] = [dict(self.f.health_run, id=20)]
        self.assertEqual("HEALTHY", self.collect()["status"])
        first["total_count"] = 301
        self.assertEqual("UNAVAILABLE", self.collect()["status"])
        for exception in (OSError(), subprocess.TimeoutExpired("gh", 10), ValueError("bad JSON")):
            def fail(path):raise exception
            value = h.collect(self.f.root, self.f.env, self.f.graph.base, self.registry, self.f.plan["bindings"], get=fail)
            self.assertEqual("UNAVAILABLE", value["status"])

    def test_failed_or_new_run_during_observation_cannot_leave_healthy_receipt(self):
        for mutation in ("attempt", "new-run"):
            calls = {}
            def changed(path):
                calls[path] = calls.get(path, 0) + 1
                value = copy.deepcopy(self.data[path])
                if mutation == "attempt" and path == "actions/runs/120" and calls[path] == 2:value["run_attempt"] = 2
                if mutation == "new-run" and path == self.list_key and calls[path] == 2:
                    value["workflow_runs"].insert(0, dict(self.f.health_run, id=121));value["total_count"] += 1
                return value
            value = h.collect(self.f.root, self.f.env, self.f.graph.base, self.registry, self.f.plan["bindings"], get=changed)
            self.assertEqual("UNAVAILABLE", value["status"])

    def test_required_rechecks_integration_but_does_not_downgrade_an_original_full_fallback(self):
        self.f.health_file.write_text("{}")
        full, _ = ci_plan.compute(self.f.root, self.f.env, self.f.graph.event)
        self.assertEqual("full", full["profile"])
        self.f.health_file.write_text(json.dumps(self.data))
        for plan in (full, self.f.plan):
            needs = {key: dict(result=value, outputs={}) for key, value in plan["recipe"]["expectedResults"].items()}
            needs["changes"] = dict(result="success", outputs=ci_plan.outputs(plan))
            result = subprocess.run([sys.executable, "-m", "scripts.ci_required"], cwd=self.f.root,
                                    env=dict(self.f.env, CI_NEEDS_JSON=json.dumps(needs)), capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout+result.stderr)
        self.f.health_file.write_text("{}")
        with self.assertRaises(ValueError):h.replay(self.f.plan, self.f.root, self.f.env, self.registry, self.f.plan["bindings"])

    def test_forged_health_fields_do_not_authorize_reduced_coverage(self):
        for key in self.f.plan["health"]:
            plan = copy.deepcopy(self.f.plan);plan["health"][key] = "forged"
            with self.subTest(key=key), self.assertRaises(ValueError):
                h.replay(plan, self.f.root, self.f.env, self.registry, self.f.plan["bindings"])


class RoutingTest(unittest.TestCase):
    def test_full_routes_and_concurrency_cannot_be_weakened(self):
        workflow = s.read(s.ROOT, s.WORKFLOW);registry = s.load_registry()
        related = {".github/workflows/release.yml": s.read(s.ROOT, ".github/workflows/release.yml")}
        for before, after in (("'17 10 * * *'", "'*/5 * * * *'"), ("  workflow_dispatch:\n", ""),
                              ("  actions: read", "  actions: write"),
                              ("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", "cancel-in-progress: true"),
                              ("&& github.ref || github.run_id", "&& github.ref || github.ref")):
            with self.subTest(before=before), self.assertRaises(ValueError):
                s.validate_workflow(registry, workflow.replace(before, after, 1), related)


if __name__ == "__main__":unittest.main()
