#!/usr/bin/env python3
"""Validate and render the exact V4.3 paid evidence plan."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.v43.evidence import EvidenceError, canonical_json, validate_source

SCHEMA = "gse-v43-fast-reopen-cloud-plan-v1"
SUITE = "v4.3-fast-reopen-suite-v1"
PRESET = "v4.3-fast-reopen-v1"
REPEATS = {"experiment": 1, "canonical": 3, "failure-drill": 1}
RETENTION = {"experiment": "actions", "canonical": "gcs",
             "failure-drill": "actions"}
RESOURCES = {
    "primaryDiskType": "pd-balanced", "primaryDiskGiB": 200,
    "targetDiskType": "pd-balanced", "targetDiskGiB": 200,
    "bootDiskType": "pd-balanced", "bootDiskGiB": 100,
    "peakDataDiskGiB": 400, "peakProvisionedDiskGiB": 500,
    "peakProjectVcpus": 30,
    "filesystem": "ext4", "mountOptions": "defaults",
    "maximumMemberRuntimeSeconds": 5_400, "maximumRunCostUsd": 25,
    "serialMembers": True, "publishedControlVersion": "4.2.0",
    "warmMedianMaximumRatio": 0.50, "warmMemberMaximumRatio": 0.65,
}


def validate_inputs(profile: str, repeats: int, duration: int, retention: str,
                    machine: str, provisioning: str) -> dict[str, Any]:
    if profile not in REPEATS or repeats != REPEATS[profile]:
        raise EvidenceError("profile/member count differs from frozen V4.3 plan")
    if duration != 1_800 or retention != RETENTION[profile]:
        raise EvidenceError("duration or retention differs from frozen V4.3 plan")
    if machine != "c3d-standard-30" or provisioning != "standard":
        raise EvidenceError("V4.3 requires Standard c3d-standard-30")
    return {"profile": profile, "repeats": repeats,
            "durationSeconds": duration, "retention": retention,
            "machineType": machine, "provisioning": provisioning}


def git(root: Path, *arguments: str) -> str:
    result = subprocess.run(["git", *arguments], cwd=root, check=False,
                            capture_output=True, text=True)
    if result.returncode:
        raise EvidenceError("git source validation failed")
    return result.stdout.strip()


def validate_plan(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schemaVersion") != SCHEMA \
            or document.get("suite") != SUITE or document.get("preset") != PRESET:
        raise EvidenceError("unsupported V4.3 cloud plan")
    request = document.get("request")
    if not isinstance(request, dict) or document.get("resources") != RESOURCES:
        raise EvidenceError("V4.3 plan resources differ")
    validated = validate_inputs(
        request.get("profile", ""), request.get("repeats", -1),
        request.get("durationSeconds", -1), request.get("retention", ""),
        request.get("machineType", ""), request.get("provisioning", ""))
    if request != validated \
            or document.get("slots") != list(range(1, validated["repeats"] + 1)):
        raise EvidenceError("V4.3 request or slots differ")
    validate_source(document.get("sourceCommit"))
    if re.fullmatch(r"[0-9]+", str(document.get("runId", ""))) is None:
        raise EvidenceError("run ID must be numeric")
    return document


def markdown(value: object) -> str:
    return (str(value).replace("\\", "\\\\").replace("|", "\\|")
            .replace("<", "&lt;").replace(">", "&gt;")
            .replace("\r", " ").replace("\n", " "))


def render_summary(document: dict[str, Any]) -> str:
    plan = validate_plan(document); request = plan["request"]; resources = plan["resources"]
    rows = [
        ("Run", plan["runId"]), ("Source commit", plan["sourceCommit"]),
        ("Evidence profile", request["profile"]),
        ("Independent serial members", request["repeats"]),
        ("Provisioning / machine", f"{request['provisioning']} / {request['machineType']}"),
        ("Corpus", "100000 documents / 16 tokens per document"),
        ("Mutations", "10000 plus checkpoint/WAL and dynamic-index lifecycle"),
        ("Measurement", f"{request['durationSeconds']} seconds"),
        ("Primary / target disks", f"{resources['primaryDiskType']} / "
         f"{resources['primaryDiskGiB']} GiB each"),
        ("Peak quota", f"{resources['peakProjectVcpus']} vCPU / "
         f"{resources['peakDataDiskGiB']} GiB data + "
         f"{resources['bootDiskGiB']} GiB boot = "
         f"{resources['peakProvisionedDiskGiB']} GiB provisioned disk"),
        ("Published control", resources["publishedControlVersion"]),
        ("Warm thresholds", "set median <= 0.50 / every member <= 0.65"),
        ("Final retention", request["retention"]),
        ("Maximum member runtime", f"{resources['maximumMemberRuntimeSeconds']} seconds"),
        ("Maximum complete-run cost", f"USD {resources['maximumRunCostUsd']}"),
        ("Suite / preset", f"{plan['suite']} / {plan['preset']}"),
    ]
    lines = ["# V4.3 fast-reopen evidence preflight", "",
             "| Field | Validated value |", "|---|---|"]
    lines.extend(f"| {markdown(label)} | `{markdown(value)}` |" for label, value in rows)
    lines.extend(["", "> Preflight requests no OIDC token and creates no paid "
                  "resource. Every member runs after prior cleanup.", ""])
    return "\n".join(lines)


def write_outputs(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            if re.fullmatch(r"[a-z_]+", key) is None or "\n" in value:
                raise EvidenceError("invalid GitHub output")
            stream.write(f"{key}={value}\n")


def plan_command(arguments: argparse.Namespace) -> int:
    request = validate_inputs(arguments.profile, arguments.repeats,
                              arguments.duration_seconds, arguments.retention,
                              arguments.machine_type, arguments.provisioning)
    trusted = validate_source(git(arguments.repository_root,
                                  "rev-parse", f"{arguments.trusted_ref}^{{commit}}"))
    requested = arguments.source_commit or arguments.dispatch_sha
    source = validate_source(git(arguments.repository_root,
                                 "rev-parse", f"{requested}^{{commit}}"))
    if source != trusted:
        raise EvidenceError("source must equal exact protected-master tip")
    document = {"schemaVersion": SCHEMA, "suite": SUITE, "preset": PRESET,
                "sourceCommit": source, "trustedRef": arguments.trusted_ref,
                "runId": arguments.run_id, "request": request,
                "slots": list(range(1, arguments.repeats + 1)),
                "resources": dict(RESOURCES)}
    validate_plan(document)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(canonical_json(document))
    if arguments.github_output:
        write_outputs(arguments.github_output, {
            "source_commit": source,
            "slots": json.dumps(document["slots"], separators=(",", ":")),
            "duration_seconds": str(arguments.duration_seconds),
            "profile": arguments.profile, "retention": arguments.retention})
    print(f"v43CloudPlan=PASS profile={arguments.profile} "
          f"members={arguments.repeats} source={source}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(); commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    for name in ("profile", "retention", "machine-type", "provisioning",
                 "dispatch-sha", "trusted-ref", "run-id"):
        plan.add_argument(f"--{name}", required=True)
    plan.add_argument("--repeats", type=int, required=True)
    plan.add_argument("--duration-seconds", type=int, required=True)
    plan.add_argument("--source-commit", default="")
    plan.add_argument("--repository-root", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--github-output", type=Path)
    summary = commands.add_parser("plan-summary")
    summary.add_argument("--plan", type=Path, required=True)
    summary.add_argument("--github-step-summary", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "plan":
        return plan_command(arguments)
    try:
        document = json.loads(arguments.plan.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as failure:
        raise EvidenceError("cannot read V4.3 cloud plan") from failure
    with arguments.github_step_summary.open("a", encoding="utf-8") as stream:
        stream.write(render_summary(document))
    print("v43CloudPlanSummary=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as failure:
        print(f"v43CloudPlan=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
