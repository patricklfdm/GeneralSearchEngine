"""Temporary real Git contexts for CI gate tests; never imported by production gates."""
import json
import os
from datetime import datetime, timezone
import sys
import time

from scripts import ci_plan
from scripts import test_ci_shadow_plan as shadow_tests


class PlanFixture:
    def __init__(self, profile):
        self.graph = shadow_tests.ShadowPlanTest()
        self.graph.setUp()
        path = {"docs": "README.md", "integration": ci_plan.shadow.INTEGRATION_PATH, "full": "unclassified.txt"}[profile]
        self.graph.pr({path: b"change\n"})
        self.root = self.graph.root
        payload = self.root / ".git/ci-test-event.json"
        payload.write_text(json.dumps(self.graph.event))
        self.env = dict(os.environ, **self.graph.env, GITHUB_EVENT_PATH=str(payload), PYTHONDONTWRITEBYTECODE="1")
        self.install_health(self.graph.base)
        self.plan, self.observation = ci_plan.compute(self.root, self.env, self.graph.event)
        assert self.plan["profile"] == profile
        self.outputs = ci_plan.outputs(self.plan)

    def close(self):
        self.graph.doCleanups()

    def install_health(self, source):
        """Actual gh subprocess seam with deterministic local API data, never network."""
        from scripts import ci_suites
        now = int(time.time())
        stamp = lambda n: datetime.fromtimestamp(n, timezone.utc).isoformat().replace("+00:00", "Z")
        self.health_run = dict(id=120, run_attempt=1, head_sha=source, head_branch="master", path=ci_suites.WORKFLOW,
                               event="push", status="completed", conclusion="success",
                               repository=dict(full_name=self.env["GITHUB_REPOSITORY"]))
        jobs = []
        for index, name in enumerate(ci_suites.expanded_names(ci_suites.load_registry())):
            step = "Tests"
            if name.startswith("V5.1 owned canonical (repetition "):step = "Qualify fifteen owned canonical cells without GCP"
            elif name == "V5.1 owned experiment (no GCP)":step = "Qualify V5.1 owned complete experiment history and backup restore without GCP"
            jobs.append(dict(id=500+index, name=name, run_id=120, run_attempt=1, head_sha=source,
                             status="completed", conclusion="success", started_at=stamp(now-120), completed_at=stamp(now-60),
                             steps=[dict(name=step, status="completed", conclusion="success", started_at=stamp(now-110), completed_at=stamp(now-70))]))
        self.health_api = {
            f"actions/workflows/ci.yml/runs?branch=master&head_sha={source}&per_page=100&page=1": dict(total_count=1, workflow_runs=[self.health_run]),
            "actions/runs/120": self.health_run,
            "actions/runs/120/attempts/1/jobs?per_page=100&page=1": dict(total_count=len(jobs), jobs=jobs)}
        self.health_file = self.root / ".git/health-api.json"
        self.health_file.write_text(json.dumps(self.health_api))
        folder = self.root / ".git/test-bin";folder.mkdir(exist_ok=True)
        gh = folder / "gh"
        gh.write_text(f"#!{sys.executable}\nimport json,sys,pathlib\n"
                      "assert sys.argv[1:6] == ['api','--hostname','github.com','--method','GET']\n"
                      f"prefix = {'repos/'+self.env['GITHUB_REPOSITORY']+'/'!r}\n"
                      "assert sys.argv[6].startswith(prefix)\n"
                      f"value=json.loads(pathlib.Path({str(self.health_file)!r}).read_text())\n"
                      "print(json.dumps(value[sys.argv[6][len(prefix):]]))\n")
        gh.chmod(0o755)
        self.env["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
