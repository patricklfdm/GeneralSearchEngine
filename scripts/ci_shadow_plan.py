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
import sys

# Keep the historic direct-script entry point as well as python -m support.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import ci_suites as suites

WORKFLOW = ".github/workflows/ci.yml"
POLICY = "scripts/ci_shadow_policy.json"
PLANNER = "scripts/ci_shadow_plan.py"
REGISTRY = suites.REGISTRY
SUITE_VALIDATOR = "scripts/ci_suites.py"
POLICY_V1 = {"schema": "gse-ci-shadow-policy-v1", "mode": "shadow",
             "profiles": ["docs", "core", "full"],
             "documentationRule": "ci-documentation-v1", "corePaths": []}
INTEGRATION_RULE = "travel-demo-content-v1"
INTEGRATION_PATH = "examples/travel-search/src/main/java/example/travel/TravelSearchDemo.java"
POLICY_V2 = {"schema": "gse-ci-policy-v2", "mode": "execution",
             "profiles": ["docs", "integration", "full"],
             "documentationRule": "ci-documentation-v1", "forceFull": False, "integrationRules": [INTEGRATION_RULE]}
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
    "REGISTRY_UNAVAILABLE": "The source-bound suite registry or its validator is unavailable/invalid.",
    "REVIEWED_INTEGRATION": "Only reviewed existing-file content and permitted documentation changed.",
    "FORCE_FULL": "The trusted policy requires full execution while retaining the candidate recommendation.",
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
    def constant(value):
        raise ValueError("invalid JSON constant: " + value)
    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def documentation(path):
    # Keep this frozen rule independent of candidate ci_changes.py. Its parity
    # with the actual classifier is tested; policy cannot redefine it from JSON.
    return ("src" not in path.split("/")[:-1]
            and not path.startswith((".github/workflows/", ".github/actions/", "scripts/", ".mvn/"))
            and (path.endswith(".md") or path in ("LICENSE", ".gitignore")
                 or path.startswith(".github/ISSUE_TEMPLATE/")))


def valid_path(path):
    return bool(path) and not path.startswith("/") and all(part not in ("", ".", "..") for part in path.split("/"))


def valid_policy(value):
    return (type(value) is dict and type(value.get("forceFull")) is bool
            and value.get("integrationRules") in ([], [INTEGRATION_RULE])
            and value == {**POLICY_V2, "forceFull": value["forceFull"], "integrationRules": value["integrationRules"]})


def integration_change(change, rules):
    return (rules == [INTEGRATION_RULE] and change["path"] == INTEGRATION_PATH
            and change["status"] == "M" and change["oldMode"] == change["newMode"]
            and change["oldType"] == change["newType"] == "regular"
            and change["oldBlob"] != change["newBlob"])


def change_records(raw):
    """Parse complete raw NUL records; --no-renames exposes both rename endpoints."""
    require(raw and raw.endswith(b"\0"), "EMPTY_OR_INVALID_DIFF")
    pieces = raw[:-1].split(b"\0")
    require(len(pieces) % 2 == 0, "EMPTY_OR_INVALID_DIFF")
    records = []
    kinds = {"000000": "absent", "100644": "regular", "100755": "regular",
             "120000": "symlink", "160000": "gitlink"}
    for header, path_bytes in zip(pieces[::2], pieces[1::2]):
        match = re.fullmatch(rb":([0-7]{6}) ([0-7]{6}) ([0-9a-f]{40}) ([0-9a-f]{40}) ([AMDT])", header)
        require(match is not None, "EMPTY_OR_INVALID_DIFF")
        old_mode, new_mode, old_blob, new_blob, status = (v.decode("ascii") for v in match.groups())
        try:
            path = path_bytes.decode("utf-8")
        except UnicodeError:
            raise Unavailable("EMPTY_OR_INVALID_DIFF") from None
        require(valid_path(path) and old_mode in kinds and new_mode in kinds, "EMPTY_OR_INVALID_DIFF")
        require((old_mode == "000000") == (old_blob == "0" * 40)
                and (new_mode == "000000") == (new_blob == "0" * 40), "EMPTY_OR_INVALID_DIFF")
        require((status == "A" and old_mode == "000000" and new_mode != "000000")
                or (status == "D" and old_mode != "000000" and new_mode == "000000")
                or (status in ("M", "T") and "000000" not in (old_mode, new_mode)), "EMPTY_OR_INVALID_DIFF")
        records.append(dict(path=path, status=status, oldMode=old_mode, newMode=new_mode,
                            oldType=kinds[old_mode], newType=kinds[new_mode], oldBlob=old_blob, newBlob=new_blob))
    require(len({v["path"] for v in records}) == len(records), "EMPTY_OR_INVALID_DIFF")
    return records


def suite_plan(registry, profile):
    """Closed recipes; a policy cannot supply suites, shell or expressions."""
    suites.validate_registry(registry)
    require(profile in ("docs", "integration", "full"), "CONTEXT_UNAVAILABLE")
    expected = {row["id"]: row[profile + "Result"] for row in registry["suites"]}
    selected = [row["id"] for row in registry["suites"] if expected[row["id"]] == "success"]
    for row in registry["suites"]:
        if row["id"] in selected:
            require(all(dep == "changes" or dep in selected for dep in row["needs"]), "REGISTRY_UNAVAILABLE")
    expanded = suites.expanded_names(dict(metaJobs=registry["metaJobs"],
                                         suites=[row for row in registry["suites"] if row["id"] in selected]))
    return dict(profile=profile, selectedSuites=selected, expectedResults=expected, executedJobCount=len(expanded))


def plan(root, env, event):
    actual = {"true": "full", "false": "docs"}.get(env.get("ACTUAL_RUN_FULL_CI"), "unknown")
    if "CI_PROFILE" in env:
        actual = env["CI_PROFILE"] if env["CI_PROFILE"] in ("docs", "integration", "full") else "unknown"
    report = dict(schema="gse-ci-shadow-plan-v2", mode="shadow", actualProfile=actual,
                  recommendedProfile="full", reasons=[], coreEligible=False, integrationEligible=False,
                  event=env.get("GITHUB_EVENT_NAME", ""), testedSha=env.get("GITHUB_SHA", ""),
                  repository=env.get("GITHUB_REPOSITORY", ""), ref=env.get("GITHUB_REF", ""),
                  runId=env.get("GITHUB_RUN_ID", ""), runAttempt=env.get("GITHUB_RUN_ATTEMPT", ""),
                  workflow=dict(path=WORKFLOW, ref=env.get("GITHUB_WORKFLOW_REF", ""),
                                source=env.get("GITHUB_WORKFLOW_SHA", ""), sha256=None),
                  plannerSha256=None, policy=dict(path=POLICY, source=None, sha256=None, testedSha256=None),
                  baseSha=None, headSha=None, mergeBaseSha=None, comparison=None,
                  changedPaths=[], changedPathsSha256=None, nonDocumentationPaths=[],
                  changes=[], diffSha256=None, forceFull=True, registry=dict(path=REGISTRY, sha256=None, validatorSha256=None),
                  suitePlan=None)
    registry = None
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
        try:
            registry_bytes = blob(root, source, REGISTRY)
            validator = blob(root, source, SUITE_VALIDATOR)
            require(registry_bytes == (root / REGISTRY).read_bytes()
                    and validator == (root / SUITE_VALIDATOR).read_bytes(), "REGISTRY_UNAVAILABLE")
            registry = suites.validate_registry(strict_json(registry_bytes))
            report["registry"].update(sha256=digest(registry_bytes), validatorSha256=digest(validator))
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
            raise Unavailable("REGISTRY_UNAVAILABLE") from None
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
        changed = git(root, "diff", "--raw", "--no-abbrev", "--no-renames", "-z", comparison, "--")
        report["diffSha256"] = digest(changed)
        report["changes"] = change_records(changed)
        paths = [v["path"] for v in report["changes"]]
        report["changedPathsSha256"] = digest(b"".join(v.encode("utf-8") + b"\0" for v in paths))
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
        require(valid_policy(value), "POLICY_INVALID")
        report["forceFull"] = value["forceFull"]
        try:
            tested_policy = blob(root, source, POLICY)
            report["policy"]["testedSha256"] = digest(tested_policy)
            require(tested_policy == policy == (root / POLICY).read_bytes(), "POLICY_CHANGED")
        except (OSError, subprocess.SubprocessError):
            raise Unavailable("POLICY_CHANGED") from None
        require(actual != "unknown", "ACTUAL_UNKNOWN")
        if report["nonDocumentationPaths"]:
            if report["event"] == "pull_request" and all(documentation(row["path"]) or
                    integration_change(row, value["integrationRules"]) for row in report["changes"]):
                report.update(recommendedProfile="integration", integrationEligible=True, reasons=["REVIEWED_INTEGRATION"])
            else:
                report["reasons"] = ["BUILD_OR_UNKNOWN_PATH"]
        else:
            report.update(recommendedProfile="docs", reasons=["DOCS_ONLY"])
    except Unavailable as error:
        report["reasons"] = [str(error)]
    except (OSError, subprocess.SubprocessError):
        report["reasons"] = ["HISTORY_UNAVAILABLE"]
    except (KeyError, TypeError, ValueError, UnicodeError):
        report["reasons"] = ["CONTEXT_UNAVAILABLE"]
    if registry is not None:
        report["suitePlan"] = dict(schema="gse-ci-suite-plan-v1",
                                   candidate=suite_plan(registry, report["recommendedProfile"]),
                                   actual=suite_plan(registry, actual) if actual != "unknown" else None)
    return report


def summary(report):
    def safe(value):
        return html.escape(str(value)).replace("|", "&#124;").replace("\n", " ").replace("\r", " ").replace("`", "&#96;")
    values = [("Actual execution profile", report["actualProfile"]),
              ("Shadow recommendation", report["recommendedProfile"]),
              ("Integration candidate", report["integrationEligible"]),
              ("Force full", report["forceFull"]),
              ("Event", report["event"]), ("Tested SHA", report["testedSha"]),
              ("PR head / push after", report["headSha"]), ("Policy baseline", report["policy"]["source"]),
              ("Workflow SHA-256", report["workflow"]["sha256"]),
              ("Policy SHA-256", report["policy"]["sha256"]),
              ("Registry SHA-256", report["registry"]["sha256"]),
              ("Changed paths", len(report["changedPaths"]))]
    lines = ["## CI shadow plan", "", "Observation only. The independently checked execution receipt decides coverage; this report is not qualification evidence.",
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
