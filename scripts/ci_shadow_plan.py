"""Observe a source-bound CI recommendation; never emit Actions gate outputs.

Policy is read as JSON data from the PR base (or push before) commit, not the
proposed working tree. V1 intentionally approves no core paths. Missing or
ambiguous inputs recommend full without overriding the actual classifier.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess

WORKFLOW = ".github/workflows/ci.yml"
POLICY = "scripts/ci_shadow_policy.json"
PLANNER = "scripts/ci_shadow_plan.py"
POLICY_V1 = {"schema": "gse-ci-shadow-policy-v1", "mode": "shadow",
             "profiles": ["docs", "core", "full"],
             "documentationRule": "ci-documentation-v1", "corePaths": []}
REASONS = {
    "CONTEXT_UNAVAILABLE": "Event or source identity is missing or inconsistent.",
    "HISTORY_UNAVAILABLE": "Complete comparison history is unavailable.",
    "POLICY_UNAVAILABLE": "The baseline has no usable shadow policy (including first rollout).",
    "POLICY_INVALID": "Baseline policy is unknown or attempts an unapproved rule/core allowlist.",
    "POLICY_CHANGED": "The tested source changes the baseline policy; it cannot downgrade itself.",
    "ACTUAL_UNKNOWN": "The actual classifier output is missing or invalid.",
    "MANUAL_OR_UNKNOWN": "Manual and unsupported events recommend full.",
    "EMPTY_OR_INVALID_DIFF": "The complete diff is empty or contains invalid paths.",
    "BUILD_OR_UNKNOWN_PATH": "A build, qualification, CI, release or unclassified path requires full.",
    "DOCS_ONLY": "Every changed path satisfies the existing conservative documentation rule.",
}


class Unavailable(ValueError):
    """A conservative observation gap, never an excuse to select core."""


def require(value, code):
    if not value:
        raise Unavailable(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) and value != "0" * 40


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=15).stdout


def blob(root, source, path):
    require(sha(source), "CONTEXT_UNAVAILABLE")
    return git(root, "show", source + ":" + path)


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs)


def documentation(path):
    # Keep this frozen rule independent of candidate ci_changes.py. Its parity
    # with the actual classifier is tested; policy cannot redefine it from JSON.
    return ("src" not in path.split("/")[:-1]
            and not path.startswith((".github/workflows/", ".github/actions/", "scripts/", ".mvn/"))
            and (path.endswith(".md") or path in ("LICENSE", ".gitignore")
                 or path.startswith(".github/ISSUE_TEMPLATE/")))


def valid_path(path):
    return bool(path) and not path.startswith("/") and all(part not in ("", ".", "..") for part in path.split("/"))


def plan(root, env, event):
    actual = {"true": "full", "false": "docs"}.get(env.get("ACTUAL_RUN_FULL_CI"), "unknown")
    report = dict(schema="gse-ci-shadow-plan-v1", mode="shadow", actualProfile=actual,
                  recommendedProfile="full", reasons=[], coreEligible=False,
                  event=env.get("GITHUB_EVENT_NAME", ""), testedSha=env.get("GITHUB_SHA", ""),
                  repository=env.get("GITHUB_REPOSITORY", ""), ref=env.get("GITHUB_REF", ""),
                  runId=env.get("GITHUB_RUN_ID", ""), runAttempt=env.get("GITHUB_RUN_ATTEMPT", ""),
                  workflow=dict(path=WORKFLOW, ref=env.get("GITHUB_WORKFLOW_REF", ""),
                                source=env.get("GITHUB_WORKFLOW_SHA", ""), sha256=None),
                  plannerSha256=None, policy=dict(path=POLICY, source=None, sha256=None, testedSha256=None),
                  baseSha=None, headSha=None, mergeBaseSha=None, comparison=None,
                  changedPaths=[], changedPathsSha256=None, nonDocumentationPaths=[])
    try:
        source, repository, ref = report["testedSha"], report["repository"], report["ref"]
        require(isinstance(event, dict) and sha(source), "CONTEXT_UNAVAILABLE")
        require(all(re.fullmatch(r"[1-9][0-9]*", report[key]) for key in ("runId", "runAttempt")),
                "CONTEXT_UNAVAILABLE")
        require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
                and event["repository"]["full_name"] == repository, "CONTEXT_UNAVAILABLE")
        require(git(root, "rev-parse", "HEAD").decode().strip() == source, "CONTEXT_UNAVAILABLE")
        require(report["workflow"]["ref"] == repository + "/" + WORKFLOW + "@" + ref
                and report["workflow"]["source"] == source, "CONTEXT_UNAVAILABLE")
        workflow = blob(root, source, WORKFLOW)
        report["workflow"]["sha256"] = digest(workflow)
        implementation = blob(root, source, PLANNER)
        report["plannerSha256"] = digest(implementation)
        require(workflow == (root / WORKFLOW).read_bytes()
                and implementation == (root / PLANNER).read_bytes(), "CONTEXT_UNAVAILABLE")
        if report["event"] == "pull_request":
            pr = event["pull_request"]
            base, head = pr["base"]["sha"], pr["head"]["sha"]
            number = event["number"]
            require(type(number) is int and number > 0 and ref == f"refs/pull/{number}/merge"
                    and pr["base"]["ref"] == "master"
                    and pr["base"]["repo"]["full_name"] == repository, "CONTEXT_UNAVAILABLE")
            require(sha(base) and sha(head), "CONTEXT_UNAVAILABLE")
            parents = git(root, "rev-list", "--parents", "-n", "1", source).decode().split()
            require(parents == [source, base, head], "CONTEXT_UNAVAILABLE")
            report["mergeBaseSha"] = git(root, "merge-base", base, head).decode().strip()
            comparison = base + "..." + head
        elif report["event"] == "push":
            base, head = event["before"], event["after"]
            require(sha(base) and sha(head) and head == source and ref == event["ref"] == "refs/heads/master",
                    "CONTEXT_UNAVAILABLE")
            comparison = base + ".." + head
        else:
            raise Unavailable("MANUAL_OR_UNKNOWN")
        report.update(baseSha=base, headSha=head, comparison=comparison)
        report["policy"]["source"] = base
        changed = git(root, "diff", "--name-only", "--no-renames", "-z", comparison, "--")
        report["changedPathsSha256"] = digest(changed)
        require(changed and changed.endswith(b"\0"), "EMPTY_OR_INVALID_DIFF")
        paths = changed[:-1].decode("utf-8").split("\0")
        require(all(valid_path(path) for path in paths), "EMPTY_OR_INVALID_DIFF")
        report["changedPaths"] = paths
        report["nonDocumentationPaths"] = [path for path in paths if not documentation(path)]
        try:
            policy = blob(root, base, POLICY)
            report["policy"]["sha256"] = digest(policy)
        except (OSError, subprocess.SubprocessError):
            raise Unavailable("POLICY_UNAVAILABLE") from None
        try:
            value = strict_json(policy)
        except (ValueError, UnicodeError):
            raise Unavailable("POLICY_INVALID") from None
        require(value == POLICY_V1, "POLICY_INVALID")
        try:
            tested_policy = blob(root, source, POLICY)
            report["policy"]["testedSha256"] = digest(tested_policy)
            require(tested_policy == policy == (root / POLICY).read_bytes(), "POLICY_CHANGED")
        except (OSError, subprocess.SubprocessError):
            raise Unavailable("POLICY_CHANGED") from None
        require(actual != "unknown", "ACTUAL_UNKNOWN")
        if report["nonDocumentationPaths"]:
            report["reasons"] = ["BUILD_OR_UNKNOWN_PATH"]
        else:
            report.update(recommendedProfile="docs", reasons=["DOCS_ONLY"])
    except Unavailable as error:
        report["reasons"] = [str(error)]
    except (OSError, subprocess.SubprocessError):
        report["reasons"] = ["HISTORY_UNAVAILABLE"]
    except (KeyError, TypeError, ValueError, UnicodeError):
        report["reasons"] = ["CONTEXT_UNAVAILABLE"]
    return report


def summary(report):
    def safe(value):
        return html.escape(str(value)).replace("|", "&#124;").replace("\n", " ").replace("\r", " ").replace("`", "&#96;")
    values = [("Actual execution profile", report["actualProfile"]),
              ("Shadow recommendation", report["recommendedProfile"]),
              ("Core eligible", "No; the approved allowlist is empty"),
              ("Event", report["event"]), ("Tested SHA", report["testedSha"]),
              ("PR head / push after", report["headSha"]), ("Policy baseline", report["policy"]["source"]),
              ("Workflow SHA-256", report["workflow"]["sha256"]),
              ("Policy SHA-256", report["policy"]["sha256"]),
              ("Changed paths", len(report["changedPaths"]))]
    lines = ["## CI shadow plan", "", "Observation only. Existing full/docs gates decide execution; this plan is not qualification evidence.",
             "", "| Field | Value |", "| --- | --- |"]
    lines += [f"| {name} | {safe(value)} |" for name, value in values]
    lines += ["", *[f"- **{code}**: {REASONS[code]}" for code in report["reasons"]], "",
              "Complete paths and source identities: the attempt-specific `ci-shadow-plan` artifact.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        event = strict_json(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())
    except (KeyError, OSError, ValueError, UnicodeError):
        event = None
    report = plan(Path.cwd(), os.environ, event)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "plan.json").write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    rendered = summary(report)
    (args.output / "summary.md").write_text(rendered, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
            output.write(rendered)
    print(json.dumps({key: report[key] for key in ("mode", "actualProfile", "recommendedProfile", "reasons")}))


if __name__ == "__main__":
    main()
