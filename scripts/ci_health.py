"""A recent exact-base full run is required before reducing PR coverage.

This is an operational health guard, never a cloud/release qualification receipt.
The newest matching master run is observed even when failed/pending/docs-only;
there is no search for an older green result. Missing/ambiguous data selects full.
"""
import subprocess
import time
import json

from scripts import ci_observation as api, ci_shadow_plan as shadow, ci_suites as s

MAX_AGE_SECONDS = 36 * 60 * 60
FIELDS = {"schema", "status", "reason", "source", "runId", "attempt", "completedAt", "workflowSha256", "jobsSha256"}


def empty(source, reason="HEALTH_UNAVAILABLE"):
    return dict(schema="gse-ci-full-health-v1", status="UNAVAILABLE", reason=reason, source=source,
                runId=None, attempt=None, completedAt=None, workflowSha256=None, jobsSha256=None)


def validate(value, source):
    s.keys(value, FIELDS, "full health")
    s.need(value["schema"] == "gse-ci-full-health-v1" and value["source"] == source, "full health source/version")
    s.need((value["status"], value["reason"]) in (("HEALTHY", "HEALTHY"), ("UNAVAILABLE", "HEALTH_UNAVAILABLE"),
           ("STALE", "HEALTH_STALE"), ("FAILED", "HEALTH_FAILED")), "full health verdict")
    return value


def collect(root, env, source, registry, bindings, get=None, now=None):
    result = empty(source)
    get = get or (lambda path: api.github(env["GITHUB_REPOSITORY"], path, env=env))
    now = time.time() if now is None else now
    try:
        s.need(shadow.sha(source), "full health source")
        # Eligible changes cannot replace the policy/validator that defines health.
        s.need(all(shadow.digest(shadow.blob(root, source, path)) == value for path, value in bindings.items()),
               "full health policy/workflow drift")
        rows = []; total = None
        for page in range(1, 4):
            value = get(f"actions/workflows/ci.yml/runs?branch=master&head_sha={source}&per_page=100&page={page}")
            count = value["total_count"]
            s.need(type(count) is int and 0 <= count <= 300 and total in (None, count), "full health pagination")
            page_rows = value["workflow_runs"]
            s.need(type(page_rows) is list and len(page_rows) <= 100 and (page_rows or count == 0), "full health page truncated")
            total = count;rows.extend(page_rows)
            if len(rows) >= total:break
        s.need(len(rows) == total and len({row["id"] for row in rows}) == total, "full health pages incomplete")
        candidates = [row for row in rows if row["head_sha"] == source and row["head_branch"] == "master"
                      and row["path"] == s.WORKFLOW and row["event"] in ("push", "workflow_dispatch", "schedule")]
        s.need(candidates, "no full health candidate")
        latest = max(candidates, key=lambda row: row["id"])
        run = get(f"actions/runs/{latest['id']}")
        s.need(all(run[key] == latest[key] for key in ("id", "run_attempt", "head_sha", "head_branch", "path", "event"))
               and run["repository"]["full_name"] == env["GITHUB_REPOSITORY"], "full health run identity")
        s.need(type(run["id"]) is int and run["id"] > 0 and type(run["run_attempt"]) is int and run["run_attempt"] > 0,
               "full health run/attempt")
        result.update(runId=run["id"], attempt=run["run_attempt"], workflowSha256=bindings[s.WORKFLOW])
        if run["status"] != "completed":return result
        if run["conclusion"] != "success":return {**result, "status": "FAILED", "reason": "HEALTH_FAILED"}
        jobs = api.jobs(get, run["id"], run["run_attempt"])
        s.need(sorted(row["name"] for row in jobs) == sorted(s.expanded_names(registry)), "full health full inventory")
        for job in jobs:
            s.need(job["run_id"] == run["id"] and job["run_attempt"] == run["run_attempt"]
                   and job["head_sha"] == source and job["status"] == "completed" and job["conclusion"] == "success",
                   "full health job failed/skipped/wrong attempt")
            s.need(0 < api.stamp(job["started_at"]) <= api.stamp(job["completed_at"]) <= now, "full health job time")
            step_name = None
            if job["name"].startswith("V5.1 owned canonical (repetition "):
                step_name = "Qualify fifteen owned canonical cells without GCP"
            elif job["name"] == "V5.1 owned experiment (no GCP)":
                step_name = "Qualify V5.1 owned complete experiment history and backup restore without GCP"
            if step_name:
                steps = [step for step in job["steps"] if step["name"] == step_name]
                s.need(len(steps) == 1 and steps[0]["status"] == "completed" and steps[0]["conclusion"] == "success",
                       "full health qualification step missing/skipped")
        after = get(f"actions/runs/{run['id']}")
        keys = ("id", "run_attempt", "head_sha", "head_branch", "event", "path", "status", "conclusion")
        s.need(all(run[key] == after[key] for key in keys), "full health run changed")
        # Recheck the newest page so a failed/new run cannot be hidden by a green read.
        page = get(f"actions/workflows/ci.yml/runs?branch=master&head_sha={source}&per_page=100&page=1")
        s.need(page["total_count"] == total and any(v["id"] == run["id"] for v in page["workflow_runs"])
               and not any(v["id"] > run["id"] and v["head_sha"] == source and v["head_branch"] == "master"
                           and v["path"] == s.WORKFLOW and v["event"] in ("push", "workflow_dispatch", "schedule")
                           for v in page["workflow_runs"]), "new full health run appeared")
        result["completedAt"] = max(api.stamp(job["completed_at"]) for job in jobs)
        fields = ("id", "name", "run_id", "run_attempt", "head_sha", "status", "conclusion", "started_at", "completed_at", "steps")
        result["jobsSha256"] = shadow.digest(json.dumps([{k: job[k] for k in fields} for job in sorted(jobs, key=lambda v: v["id"])],
                                            sort_keys=True, separators=(",", ":")).encode())
        if now - result["completedAt"] > MAX_AGE_SECONDS:
            return {**result, "status": "STALE", "reason": "HEALTH_STALE"}
        return {**result, "status": "HEALTHY", "reason": "HEALTHY"}
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, UnicodeError):
        return result


def replay(claimed, root, env, registry, bindings):
    health = claimed["health"]
    if health is None:return None
    validate(health, claimed["identity"]["baseSha"])
    # A conservative full receipt needs all suites; improving external health
    # must not turn it into integration during Required's independent replay.
    if claimed["profile"] != "integration":
        s.need(health["status"] != "HEALTHY", "unexpected full health receipt")
        return health
    current = collect(root, env, health["source"], registry, bindings)
    s.need(current == health and current["status"] == "HEALTHY", "integration full health changed/stale/unavailable")
    return health
