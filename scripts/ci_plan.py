"""Source-bound CI execution receipts. Policy is data, never executable commands."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scripts import ci_shadow_plan as shadow, ci_suites as suites

SCHEMA = "gse-ci-execution-plan-v1"
OUTPUTS = ("run_full_ci", "profile", "run_canonical", "plan", "plan_sha256")
BINDINGS = (shadow.WORKFLOW, shadow.POLICY, shadow.REGISTRY, shadow.PLANNER,
            shadow.SUITE_VALIDATOR, "scripts/ci_changes.py", "scripts/ci_required.py", "scripts/ci_plan.py")
IDENTITIES = ("event", "testedSha", "repository", "ref", "runId", "runAttempt", "workflow",
              "baseSha", "headSha", "mergeBaseSha", "comparison")


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def compute(root, env, event):
    registry = suites.check(root)
    report = shadow.plan(root, dict(env, ACTUAL_RUN_FULL_CI="true"), event)
    # Invalid run/source context cannot create an execution receipt. Missing
    # historical policy is different: the source-bound fallback recipe is full.
    suites.need(report["registry"]["sha256"] is not None and report["workflow"]["sha256"] is not None,
                "execution context or registry unavailable")
    bindings = {}
    for path in BINDINGS:
        data = shadow.blob(root, report["testedSha"], path)
        suites.need(data == (root / path).read_bytes(), "dirty execution input: " + path)
        bindings[path] = shadow.digest(data)
    candidate = report["recommendedProfile"]
    profile = "full" if candidate == "integration" and report["forceFull"] else candidate
    plan = dict(schema=SCHEMA, identity={key: report[key] for key in IDENTITIES},
                bindings=bindings, policy=report["policy"], diffSha256=report["diffSha256"],
                changedPathsSha256=report["changedPathsSha256"], candidateProfile=candidate,
                profile=profile, reasons=report["reasons"], recipe=shadow.suite_plan(registry, profile))
    validate(plan, registry)
    return plan, report


def validate(value, registry):
    suites.keys(value, {"schema", "identity", "bindings", "policy", "diffSha256", "changedPathsSha256",
                        "candidateProfile", "profile", "reasons", "recipe"}, "execution plan")
    suites.need(value["schema"] == SCHEMA, "execution plan version")
    suites.keys(value["identity"], IDENTITIES, "execution identity")
    suites.keys(value["bindings"], BINDINGS, "execution bindings")
    suites.need(value["profile"] in ("docs", "integration", "full") and
                value["candidateProfile"] in ("docs", "integration", "full"), "execution profile")
    suites.need(value["recipe"] == shadow.suite_plan(registry, value["profile"]), "execution recipe differs")
    suites.need(type(value["reasons"]) is list and value["reasons"] and
                all(v in shadow.REASONS for v in value["reasons"]), "execution reasons")
    # All other identity/data fields are compared to an independently generated
    # receipt in Required. No untrusted plan field drives a Git/API command.
    return value


def outputs(plan):
    raw = encode(plan)
    return dict(run_full_ci="false" if plan["profile"] == "docs" else "true", profile=plan["profile"],
                run_canonical="true" if plan["profile"] == "full" else "false", plan=raw,
                plan_sha256=shadow.digest(raw.encode("utf-8")))


def checked_outputs(value, registry, expected=None):
    suites.keys(value, OUTPUTS, "classifier output")
    suites.need(all(type(v) is str for v in value.values()), "classifier output types")
    plan = validate(suites.strict_json(value["plan"]), registry)
    suites.need(outputs(plan) == value, "classifier outputs differ from execution plan")
    if expected is not None:
        suites.need(plan == expected, "execution plan differs from independent source-bound replay")
    return plan


def event(env):
    try:
        return shadow.strict_json(Path(env["GITHUB_EVENT_PATH"]).read_bytes())
    except (KeyError, OSError, ValueError, UnicodeError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan, observation = compute(Path.cwd(), os.environ, event(os.environ))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "execution-plan.json").write_text(encode(plan) + "\n", encoding="utf-8")
    (args.output / "change-records.json").write_text(encode(observation) + "\n", encoding="utf-8")
    # JSON is canonical one-line data. Never interpolate paths into a shell.
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        for key, value in outputs(plan).items():stream.write(key + "=" + value + "\n")
    print(encode(dict(profile=plan["profile"], reasons=plan["reasons"],
                      executedJobs=plan["recipe"]["executedJobCount"])))


if __name__ == "__main__":main()
