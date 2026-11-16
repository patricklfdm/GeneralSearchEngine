"""Bounded read-only GitHub observations for local CI control-plane decisions."""
from datetime import datetime
import json
import re
import subprocess
import sys
import time

from scripts import ci_shadow_plan as shadow, ci_suites as s


REQUEST_SECONDS = 30
REQUEST_ATTEMPTS = 3
OBSERVATION_SECONDS = 120
RETRY_DELAYS = (2, 4)
TRANSIENT_HTTP = frozenset((408, 429, 500, 502, 503, 504))


def _command_failure(result):
    # Only gh's HTTP diagnostic or a known transport failure permits retry.
    # Never expose stderr, response bodies, credentials or exception text.
    if result.returncode != 1: return 'PROCESS_FAILED', False
    statuses = re.findall(rb'^gh: (?:[^\r\n]* \()?HTTP ([1-5][0-9]{2})\)?\r?$', result.stderr, re.M)
    if len(statuses) == 1 and len(re.findall(rb'\bHTTP [1-5][0-9]{2}\b', result.stderr)) == 1:
        status = int(statuses[0])
        return 'HTTP_' + str(status), status in TRANSIENT_HTTP
    transport = (b'connection reset by peer', b'TLS handshake timeout', b'i/o timeout',
                 b'context deadline exceeded', b'unexpected EOF', b'no such host',
                 b'error connecting to api.github.com')
    if b'HTTP ' not in result.stderr and any(word in result.stderr for word in transport):
        return 'TRANSPORT', True
    return 'PROCESS_FAILED', False


def reader(repository, env=None):
    """One shared deadline for all pages and final identity rechecks."""
    deadline = time.monotonic() + OBSERVATION_SECONDS
    return lambda path: github(repository, path, env=env, deadline=deadline)


def github(repository, path, env=None, *, deadline=None):
    s.need(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is not None, "GitHub repository")
    s.need(type(path) is str and path.startswith("actions/") and ".." not in path and "\n" not in path,
           "GitHub read path")
    if deadline is None: deadline = time.monotonic() + OBSERVATION_SECONDS
    command = ["gh", "api", "--hostname", "github.com", "--method", "GET", "repos/" + repository + "/" + path]
    for attempt in range(1, REQUEST_ATTEMPTS + 1):
        remaining = deadline - time.monotonic()
        s.need(remaining > 0, 'GitHub observation budget exhausted')
        try:
            result = subprocess.run(command, capture_output=True, timeout=min(REQUEST_SECONDS, remaining), env=env)
        except subprocess.TimeoutExpired:
            reason, retryable = 'TIMEOUT', True
        except OSError:
            raise ValueError('GitHub read failed (START_FAILED)') from None
        else:
            s.need(len(result.stdout) <= 8 << 20 and len(result.stderr) <= 16384, 'GitHub read oversized')
            if result.returncode == 0:
                s.need(time.monotonic() <= deadline, 'GitHub observation budget exhausted')
                try:
                    return shadow.strict_json(result.stdout)
                except (ValueError, UnicodeError, RecursionError):
                    raise ValueError('GitHub read invalid JSON') from None
            reason, retryable = _command_failure(result)
        if not retryable:
            raise ValueError(f'GitHub read failed ({reason}; attempts={attempt})')
        if attempt == REQUEST_ATTEMPTS:
            raise ValueError(f'GitHub read exhausted ({reason}; attempts={attempt})')
        delay = RETRY_DELAYS[attempt - 1]
        s.need(deadline - time.monotonic() > delay, 'GitHub observation budget exhausted')
        print(json.dumps(dict(githubRead='retry', attempt=attempt, limit=REQUEST_ATTEMPTS,
                              reason=reason, delaySeconds=delay)), file=sys.stderr, flush=True)
        time.sleep(delay)


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
    s.need(type(value) is str, "timestamp must be a string")
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
    get = get or reader(env["GITHUB_REPOSITORY"], env=env)
    run_id = int(env["GITHUB_RUN_ID"])
    before = get(f"actions/runs/{run_id}")
    expected_head = identity["headSha"] if env["GITHUB_EVENT_NAME"] == "pull_request" else env["GITHUB_SHA"]
    s.need(before["id"] == run_id and before["run_attempt"] == accepted and before["head_sha"] == expected_head
           and before["event"] == env["GITHUB_EVENT_NAME"] and before["path"] == s.WORKFLOW
           and before["repository"]["full_name"] == env["GITHUB_REPOSITORY"],
           "accepted run changed")
    selected = []
    for attempt in (producer, accepted):
        found = [row for row in jobs(get, run_id, attempt) if row["name"] == "Change scope"]
        s.need(len(found) == 1, "scope producer missing/duplicate")
        job = found[0]
        s.need(job["run_id"] == run_id and job["run_attempt"] == attempt and job["head_sha"] == expected_head
               and type(job["id"]) is int and job["id"] > 0 and job["status"] == "completed"
               and job["conclusion"] == "success" and 0 < stamp(job["started_at"]) <= stamp(job["completed_at"]),
               "scope producing job identity")
        steps = [row for row in job["steps"] if row["name"] == "Classify the complete change set"]
        s.need(len(steps) == 1 and steps[0]["conclusion"] == "success" and steps[0]["status"] == "completed",
               "scope producing step failed")
        s.need(stamp(job["started_at"]) <= stamp(steps[0]["started_at"]) <= stamp(steps[0]["completed_at"])
               <= stamp(job["completed_at"]), "scope step time outside job")
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
    s.need(all(before[key] == after[key] for key in ("id", "run_attempt", "head_sha", "path", "event", "repository")),
           "run changed during scope observation")
    return dict(env, GITHUB_RUN_ATTEMPT=str(producer))
