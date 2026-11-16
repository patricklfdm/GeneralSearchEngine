"""Original/accepted scope attempts and bounded read-only pagination."""
import copy
import contextlib
import io
import json
import subprocess
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
            run.return_value.stderr = b''
            self.assertEqual(dict(ok=True), o.github("owner/repo", "actions/runs/1"))
            args = run.call_args.args[0]
            self.assertEqual(["gh", "api", "--hostname", "github.com", "--method", "GET"], args[:6])
            self.assertEqual(30, run.call_args.kwargs["timeout"])
            run.return_value.returncode = 1
            run.return_value.stderr = b'gh: Forbidden (HTTP 403)'
            with self.assertRaises(ValueError):o.github("owner/repo", "actions/runs/1")


class GitHubReadTest(unittest.TestCase):
    def setUp(self):
        self.clock = 0.0
        self.delays = []
        def sleep(seconds):
            self.delays.append(seconds); self.clock += seconds
        self.enterContext(patch('time.monotonic', side_effect=lambda: self.clock))
        self.enterContext(patch('time.sleep', side_effect=sleep))
        self.diagnostics = self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    @staticmethod
    def reply(status=0, stdout=b'{"ok":true}', stderr=b''):
        return subprocess.CompletedProcess(['gh'], status, stdout, stderr)

    def test_timeout_then_success_repeats_only_the_same_get(self):
        with patch.object(o.subprocess, 'run', side_effect=[
                subprocess.TimeoutExpired('private-token', 10, stderr=b'private-token'), self.reply()]) as run:
            self.assertEqual({'ok': True}, o.github('owner/repo', 'actions/runs/1', env={'GH_TOKEN':'private-token'}))
        self.assertEqual(2, run.call_count)
        self.assertEqual(run.call_args_list[0], run.call_args_list[1])
        self.assertEqual(30, run.call_args.kwargs['timeout'])
        self.assertEqual([2], self.delays)
        self.assertNotIn('private-token', self.diagnostics.getvalue())

    def test_transient_http_and_transport_recover_but_attempts_are_bounded(self):
        errors = [self.reply(1, stderr=f'gh: Unavailable (HTTP {status})\n'.encode())
                  for status in (408, 429, 500, 502, 503, 504)]
        errors.append(self.reply(1, stderr=b'error connecting to api.github.com'))
        errors.append(subprocess.TimeoutExpired('gh', 30))
        for failure in errors:
            with self.subTest(failure=failure), patch.object(o.subprocess, 'run', side_effect=[failure, self.reply()]):
                self.assertEqual({'ok': True}, o.github('owner/repo', 'actions/runs/1'))
        self.delays.clear()
        with patch.object(o.subprocess, 'run', side_effect=[errors[0]]*4) as run:
            with self.assertRaisesRegex(ValueError, 'exhausted.*attempts=3'):
                o.github('owner/repo', 'actions/runs/1')
        self.assertEqual(3, run.call_count); self.assertEqual([2, 4], self.delays)

    def test_auth_not_found_unknown_and_ambiguous_fail_without_retry(self):
        errors = [f'gh: Rejected (HTTP {status})\nconnection reset by peer'.encode()
                  for status in (400, 401, 403, 404, 422)]
        errors += [b'unknown private-token failure', b'gh: Failed (HTTP 503)\ngh: Forbidden (HTTP 403)',
                   b'HTTP 403: connection reset by peer', b'gh: Failed (HTTP 503)\nother HTTP 403']
        for stderr in errors:
            with self.subTest(stderr=stderr), patch.object(o.subprocess, 'run', return_value=self.reply(1, stderr=stderr)) as run:
                with self.assertRaises(ValueError) as failure:o.github('owner/repo', 'actions/runs/1')
                self.assertNotIn('private-token', str(failure.exception)); self.assertEqual(1, run.call_count)
        self.assertEqual([], self.delays)

    def test_cli_cancellation_and_auth_exit_are_not_transient_http_failures(self):
        for code in (-15, 2, 4):
            with self.subTest(code=code), patch.object(o.subprocess, 'run',
                    return_value=self.reply(code, stderr=b'gh: Unavailable (HTTP 503)')) as run:
                with self.assertRaises(ValueError):o.github('owner/repo', 'actions/runs/1')
                self.assertEqual(1, run.call_count)
        self.assertEqual([], self.delays)

    def test_invalid_json_and_oversized_response_are_not_retried(self):
        for data in (b'{', b'{"ok":true,"ok":false}', b'{"value":NaN}', b'\xff', b'x'*(8*1024*1024+1)):
            with self.subTest(size=len(data)), patch.object(o.subprocess, 'run', return_value=self.reply(stdout=data)) as run:
                with self.assertRaises(ValueError):o.github('owner/repo', 'actions/runs/1')
                self.assertEqual(1, run.call_count)
        self.assertEqual([], self.delays)

    def test_shared_observation_deadline_bounds_all_requests_and_retry_sleep(self):
        get = o.reader('owner/repo')
        def response(*args, **kwargs):
            self.clock += 29
            return self.reply()
        with patch.object(o.subprocess, 'run', side_effect=response) as run:
            for _ in range(4):get('actions/runs/1')
            self.assertEqual(4, run.call_count)
        def timeout(*args, **kwargs):
            self.assertEqual(4, kwargs['timeout']); self.clock += 4
            raise subprocess.TimeoutExpired('gh', 4)
        with patch.object(o.subprocess, 'run', side_effect=timeout) as run:
            with self.assertRaisesRegex(ValueError, 'budget exhausted'):get('actions/runs/1')
            self.assertEqual(1, run.call_count)
        with patch.object(o.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'budget exhausted'):get('actions/runs/1')
            run.assert_not_called()
        self.assertEqual([], self.delays)

    def test_unavailable_cli_fails_without_retry_or_private_exception_text(self):
        with patch.object(o.subprocess, 'run', side_effect=FileNotFoundError('private-token')) as run:
            with self.assertRaisesRegex(ValueError, 'START_FAILED') as failure:o.github('owner/repo', 'actions/runs/1')
            self.assertEqual(1, run.call_count); self.assertNotIn('private-token', str(failure.exception))
        self.assertEqual([], self.delays)

    def test_carried_scope_uses_retried_observation_and_still_checks_identity(self):
        original = ObservationTest('test_same_attempt_needs_no_network_and_carried_job_binds_original_execution')
        original.setUp(); self.addCleanup(original.doCleanups)
        timeouts = set()
        def response(argv, **kwargs):
            path = argv[-1].split(original.f.env['GITHUB_REPOSITORY']+'/', 1)[1]
            if '/jobs?' in path and path not in timeouts:
                timeouts.add(path); raise subprocess.TimeoutExpired('gh', 30)
            return self.reply(stdout=json.dumps(original.get(path)).encode())
        with patch.object(o.subprocess, 'run', side_effect=response) as run:
            env = o.producer_environment(original.plan, original.f.env)
            self.assertEqual('1', env['GITHUB_RUN_ATTEMPT']); self.assertEqual(6, run.call_count)
            original.current['head_sha'] = 'a'*40
            with self.assertRaisesRegex(ValueError, 'scope producing job identity'):
                o.producer_environment(original.plan, original.f.env)


if __name__ == "__main__":unittest.main()
