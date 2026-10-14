"""Bounded read-only GitHub observations for local CI control-plane decisions."""
from datetime import datetime
import re
import subprocess

from scripts import ci_shadow_plan as shadow, ci_suites as s


def github(repository, path):
    s.need(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is not None, "GitHub repository")
    s.need(type(path) is str and path.startswith("actions/") and ".." not in path and "\n" not in path,
           "GitHub read path")
    result = subprocess.run(["gh", "api", "--hostname", "github.com", "--method", "GET",
                             "repos/" + repository + "/" + path], capture_output=True, timeout=10)
    s.need(result.returncode == 0 and len(result.stdout) <= 8 << 20, "GitHub read unavailable/oversized")
    return shadow.strict_json(result.stdout)


def jobs(get, run_id, attempt):
    s.need(type(run_id) is int and run_id > 0 and type(attempt) is int and attempt > 0, "run/attempt identity")
    rows = []; total = None
    for page in range(1, 4):
        value = get(f"actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100&page={page}")
        count = value["total_count"]
        s.need(type(count) is int and 0 < count <= 300 and total in (None, count), "job page count changed")
        s.need(type(value["jobs"]) is list and 0 < len(value["jobs"]) <= 100, "job page truncated")
        total = count;rows.extend(value["jobs"])
        if len(rows) >= total:break
    s.need(len(rows) == total and len({row["id"] for row in rows}) == total, "job pages incomplete/duplicate")
    return rows


def stamp(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    s.need(stamp.tzinfo is not None, "timestamp timezone missing")
    return stamp.timestamp()


def producer_environment(plan, env, get=None):
    """Accept a carried scope job only after binding its original execution.

    GitHub can allocate a new ID/attempt to a carried successful check run. Its
    execution times, step records and original runner must remain unchanged.
    This mirrors the existing build-artifact consumer's provenance requirement.
    """
    identity = plan["identity"]
    for key, variable in (("runId", "GITHUB_RUN_ID"), ("testedSha", "GITHUB_SHA"), ("repository", "GITHUB_REPOSITORY")):
        s.need(identity[key] == env[variable], "plan run/source/repository mismatch")
    for value in (identity["runAttempt"], env["GITHUB_RUN_ATTEMPT"]):
        s.need(type(value) is str and re.fullmatch(r"[1-9][0-9]{0,5}", value), "plan attempt")
    producer, accepted = int(identity["runAttempt"]), int(env["GITHUB_RUN_ATTEMPT"])
    s.need(producer <= accepted, "future plan producing attempt")
    if producer == accepted:return env
    get = get or (lambda path: github(env["GITHUB_REPOSITORY"], path))
    run_id = int(env["GITHUB_RUN_ID"])
    before = get(f"actions/runs/{run_id}")
    expected_head = identity["headSha"] if env["GITHUB_EVENT_NAME"] == "pull_request" else env["GITHUB_SHA"]
    s.need(before["id"] == run_id and before["run_attempt"] == accepted and before["head_sha"] == expected_head
           and before["path"] == s.WORKFLOW and before["repository"]["full_name"] == env["GITHUB_REPOSITORY"],
           "accepted run changed")
    selected = []
    for attempt in (producer, accepted):
        found = [row for row in jobs(get, run_id, attempt) if row["name"] == "Change scope"]
        s.need(len(found) == 1, "scope producer missing/duplicate")
        job = found[0]
        s.need(job["run_id"] == run_id and job["run_attempt"] == attempt and job["head_sha"] == expected_head
               and job["status"] == "completed" and job["conclusion"] == "success", "scope producing job identity")
        steps = [row for row in job["steps"] if row["name"] == "Classify the complete change set"]
        s.need(len(steps) == 1 and steps[0]["conclusion"] == "success" and steps[0]["status"] == "completed",
               "scope producing step failed")
        selected.append(job)
    original, current = selected
    fields = ("name", "run_id", "head_sha", "started_at", "completed_at", "status", "conclusion", "steps")
    s.need(all(original[key] == current[key] for key in fields), "scope execution was replaced")
    if original["id"] != current["id"]:
        s.need(type(original.get("runner_id")) is int and original["runner_id"] > 0
               and original["runner_id"] == current.get("runner_id") and original.get("runner_name")
               and original["runner_name"] == current.get("runner_name")
               and stamp(original["created_at"]) <= stamp(original["started_at"])
               and stamp(current["created_at"]) >= stamp(original["completed_at"]), "scope carried runner changed")
    after = get(f"actions/runs/{run_id}")
    s.need(all(before[key] == after[key] for key in ("id", "run_attempt", "head_sha", "path")), "run changed during scope observation")
    return dict(env, GITHUB_RUN_ATTEMPT=str(producer))
