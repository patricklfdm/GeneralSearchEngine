"""Temporary real Git contexts for CI gate tests; never imported by production gates."""
import json
import os

from scripts import ci_plan
from scripts import test_ci_shadow_plan as shadow_tests


class PlanFixture:
    def __init__(self, profile):
        self.graph = shadow_tests.ShadowPlanTest()
        self.graph.setUp()
        self.graph.pr({"README.md" if profile == "docs" else "unclassified.txt": b"change\n"})
        self.root = self.graph.root
        payload = self.root / "event.json"
        payload.write_text(json.dumps(self.graph.event))
        self.env = dict(os.environ, **self.graph.env, GITHUB_EVENT_PATH=str(payload), PYTHONDONTWRITEBYTECODE="1")
        self.plan, self.observation = ci_plan.compute(self.root, self.env, self.graph.event)
        assert self.plan["profile"] == profile
        self.outputs = ci_plan.outputs(self.plan)

    def close(self):
        self.graph.doCleanups()
