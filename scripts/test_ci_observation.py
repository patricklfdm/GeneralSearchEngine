"""Original/accepted scope attempts and bounded read-only pagination."""
import copy
import unittest
from unittest.mock import patch

from scripts import ci_observation as o, ci_plan
from scripts.ci_test_support import PlanFixture


class ObservationTest(unittest.TestCase):
    def setUp(self):
        self.f = PlanFixture("full");self.addCleanup(self.f.close)
        self.run = int(self.f.env["GITHUB_RUN_ID"])
        self.plan = copy.deepcopy(self.f.plan);self.plan["identity"]["runAttempt"] = "1"
        self.metadata = dict(id=self.run, run_attempt=2, head_sha=self.f.graph.head, path=o.s.WORKFLOW, event="pull_request",
                             repository=dict(full_name=self.f.env["GITHUB_REPOSITORY"]))
        self.original = dict(id=101, name="Change scope", run_id=self.run, run_attempt=1, head_sha=self.f.graph.head,
                             status="completed", conclusion="success", created_at="2026-10-14T00:00:00Z",
                             started_at="2026-10-14T00:00:01Z", completed_at="2026-10-14T00:01:00Z",
                             runner_id=1, runner_name="runner", steps=[dict(name="Classify the complete change set",
                             number=4, status="completed", conclusion="success", started_at="2026-10-14T00:00:10Z",
                             completed_at="2026-10-14T00:00:20Z")])
        self.current = {**copy.deepcopy(self.original), "id": 102, "run_attempt": 2, "created_at": "2026-10-14T01:00:00Z"}

    def get(self, path):
        if path == f"actions/runs/{self.run}":return copy.deepcopy(self.metadata)
        if path == f"actions/runs/{self.run}/attempts/1/jobs?per_page=100&page=1":job = self.original
        elif path == f"actions/runs/{self.run}/attempts/2/jobs?per_page=100&page=1":job = self.current
        else:raise AssertionError(path)
        return dict(total_count=1, jobs=[copy.deepcopy(job)])

    def test_same_attempt_needs_no_network_and_carried_job_binds_original_execution(self):
        self.assertEqual(self.f.env, o.producer_environment(self.f.plan, self.f.env, lambda _: self.fail("unexpected API")))
        env = o.producer_environment(self.plan, self.f.env, self.get)
        self.assertEqual("1", env["GITHUB_RUN_ATTEMPT"])
        expected, _ = ci_plan.compute(self.f.root, env, self.f.graph.event)
        self.assertEqual(self.plan, expected)

    def test_replaced_stale_or_unproven_scope_never_reuses_the_plan(self):
        valid = copy.deepcopy(self.current)
        for key, value in (("runner_id", 2), ("head_sha", "a" * 40), ("run_attempt", 1),
                           ("conclusion", "failure"), ("started_at", "2026-10-14T00:00:02Z"),
                           ("completed_at", "2026-10-14T00:02:00Z"), ("steps", []),
                           ("created_at", "2026-10-13T00:00:00Z")):
            self.current = {**valid, key: value}
            with self.subTest(key=key), self.assertRaises((ValueError, KeyError)):
                o.producer_environment(self.plan, self.f.env, self.get)
        self.current = valid
        for key, value in (("runId", "999"), ("testedSha", "a" * 40), ("repository", "other/repo"), ("runAttempt", "3")):
            plan = copy.deepcopy(self.plan);plan["identity"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):o.producer_environment(plan, self.f.env, self.get)

    def test_changed_run_and_missing_or_duplicate_producer_fail_closed(self):
        calls = []
        def changed(path):
            value = self.get(path)
            if path == f"actions/runs/{self.run}":
                calls.append(path)
                if len(calls) == 2:value["run_attempt"] = 3
            return value
        with self.assertRaises(ValueError):o.producer_environment(self.plan, self.f.env, changed)
        for mode in ("empty", "duplicate"):
            def bad(path):
                value = self.get(path)
                if "jobs?" in path:
                    value["jobs"] = [] if mode == "empty" else value["jobs"] * 2
                    value["total_count"] = len(value["jobs"])
                return value
            with self.subTest(mode=mode), self.assertRaises(ValueError):o.producer_environment(self.plan, self.f.env, bad)

    def test_job_pages_are_complete_and_never_silently_truncated(self):
        calls = []
        def pages(path):
            calls.append(path);page = int(path.rsplit("=", 1)[1])
            return dict(total_count=101, jobs=[dict(id=n) for n in (range(1,101) if page == 1 else [101])])
        self.assertEqual(101, len(o.jobs(pages, 1, 1)));self.assertEqual(2, len(calls))
        for mode in ("truncated", "drift", "duplicate", "too-many"):
            def bad(path):
                value = pages(path)
                if mode == "too-many":value["total_count"] = 301
                if "page=2" in path:
                    if mode == "truncated":value["jobs"] = []
                    elif mode == "drift":value["total_count"] = 102
                    elif mode == "duplicate":value["jobs"] = [dict(id=1)]
                return value
            with self.subTest(mode=mode), self.assertRaises(ValueError):o.jobs(bad, 1, 1)

    def test_network_is_get_only_bounded_and_does_not_print_credentials(self):
        with patch.object(o.subprocess, "run") as run:
            run.return_value.returncode = 0;run.return_value.stdout = b'{"ok":true}'
            self.assertEqual(dict(ok=True), o.github("owner/repo", "actions/runs/1"))
            args = run.call_args.args[0]
            self.assertEqual(["gh", "api", "--hostname", "github.com", "--method", "GET"], args[:6])
            self.assertEqual(10, run.call_args.kwargs["timeout"])
            run.return_value.returncode = 1
            with self.assertRaises(ValueError):o.github("owner/repo", "actions/runs/1")


if __name__ == "__main__":unittest.main()
