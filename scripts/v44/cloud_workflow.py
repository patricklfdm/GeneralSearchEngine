#!/usr/bin/env python3
"""Validate and render the exact V4.4 paid-evidence plan without using GCP."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.v44.evidence import EvidenceError, canonical_json, validate_source

SCHEMA = "gse-v44-final-durable-cloud-plan-v1"
SUITE = "v4.4-final-durable-suite-v1"
PRESET = "v4.4-final-durable-v1"
REPEATS = {"experiment": 1, "canonical": 3, "failure-drill": 1}
RETENTION = {"experiment": "actions", "canonical": "gcs",
             "failure-drill": "actions"}
RESOURCES = {
    "dataDiskType": "pd-balanced", "dataDiskGiB": 200,
    "targetDiskType": "pd-balanced", "targetDiskGiB": 200,
    "bootDiskType": "pd-balanced", "bootDiskGiB": 100,
    "peakDataDiskGiB": 400, "peakProvisionedDiskGiB": 500,
    "peakProjectVcpus": 30, "filesystem": "ext4",
    "mountOptions": "defaults", "maximumMemberRuntimeSeconds": 10_800,
    "maximumRunCostUsd": 40, "serialMembers": True,
    "publishedControlVersion": "4.3.0",
    "lowerMedianMaximumRatioMicros": 1_200_000,
    "lowerMemberMaximumRatioMicros": 1_350_000,
}


def validate_inputs(profile: str, repeats: int, duration: int, retention: str,
                    machine: str, provisioning: str) -> dict[str, Any]:
    if profile not in REPEATS or repeats != REPEATS[profile]:
        raise EvidenceError("profile/member count differs from frozen V4.4 plan")
    if duration != 3_600 or retention != RETENTION[profile]:
        raise EvidenceError("duration or retention differs from frozen V4.4 plan")
    if machine != "c3d-standard-30" or provisioning != "standard":
        raise EvidenceError("V4.4 requires Standard c3d-standard-30")
    return {"profile": profile, "repeats": repeats,
            "durationSeconds": duration, "retention": retention,
            "machineType": machine, "provisioning": provisioning}


def validate_plan(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schemaVersion") != SCHEMA \
            or document.get("suite") != SUITE or document.get("preset") != PRESET:
        raise EvidenceError("unsupported V4.4 cloud plan")
    request = document.get("request")
    if not isinstance(request, dict) or document.get("resources") != RESOURCES:
        raise EvidenceError("V4.4 cloud resources differ")
    validated = validate_inputs(
        request.get("profile", ""), request.get("repeats", -1),
        request.get("durationSeconds", -1), request.get("retention", ""),
        request.get("machineType", ""), request.get("provisioning", ""))
    if request != validated \
            or document.get("slots") != list(range(1, validated["repeats"] + 1)):
        raise EvidenceError("V4.4 request or slots differ")
    validate_source(document.get("sourceCommit"))
    if document.get("trustedRef") != "origin/master" \
            or re.fullmatch(r"[0-9]+", str(document.get("runId", ""))) is None:
        raise EvidenceError("trusted ref or run ID differs")
    return document


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(["git", *arguments], cwd=root, check=False,
                               capture_output=True, text=True)
    if completed.returncode:
        raise EvidenceError("git source validation failed")
    return completed.stdout.strip()


def _markdown(value: object) -> str:
    return (str(value).replace("\\", "\\\\").replace("|", "\\|")
            .replace("<", "&lt;").replace(">", "&gt;")
            .replace("\r", " ").replace("\n", " "))


def render_summary(document: dict[str, Any]) -> str:
    plan = validate_plan(document)
    request = plan["request"]
    resources = plan["resources"]
    rows = [
        ("Run", plan["runId"]), ("Source commit", plan["sourceCommit"]),
        ("Evidence profile", request["profile"]),
        ("Independent serial members", request["repeats"]),
        ("Provisioning / machine",
         f"{request['provisioning']} / {request['machineType']}"),
        ("Persistent workload", "100000 documents / 10000 mutations / 4 indexes"),
        ("Measurement", f"{request['durationSeconds']} seconds"),
        ("Data / target disks",
         f"{resources['dataDiskType']} / {resources['dataDiskGiB']} GiB each"),
        ("Peak quota", f"{resources['peakProjectVcpus']} vCPU / "
         f"{resources['peakDataDiskGiB']} GiB data + "
         f"{resources['bootDiskGiB']} GiB boot = "
         f"{resources['peakProvisionedDiskGiB']} GiB provisioned disk"),
        ("Published control", resources["publishedControlVersion"]),
        ("Lower-is-better thresholds", "median <= 1.20 / every member <= 1.35"),
        ("Final retention", request["retention"]),
        ("Maximum member runtime",
         f"{resources['maximumMemberRuntimeSeconds']} seconds"),
        ("Maximum complete-run cost", f"USD {resources['maximumRunCostUsd']}"),
        ("Suite / preset", f"{plan['suite']} / {plan['preset']}"),
    ]
    lines = ["# V4.4 final durable evidence preflight", "",
             "| Field | Validated value |", "|---|---|"]
    lines.extend(f"| {_markdown(label)} | `{_markdown(value)}` |"
                 for label, value in rows)
    lines.extend(["", "> Preflight requests no OIDC token and creates no paid "
                  "resource. Members execute serially after exact cleanup.", ""])
    return "\n".join(lines)


def _outputs(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            if re.fullmatch(r"[a-z_]+", key) is None or "\n" in value:
                raise EvidenceError("invalid GitHub output")
            stream.write(f"{key}={value}\n")


def plan_command(arguments: argparse.Namespace) -> int:
    request = validate_inputs(arguments.profile, arguments.repeats,
                              arguments.duration_seconds, arguments.retention,
                              arguments.machine_type, arguments.provisioning)
    trusted = validate_source(_git(arguments.repository_root, "rev-parse",
                                   f"{arguments.trusted_ref}^{{commit}}"))
    requested = arguments.source_commit or arguments.dispatch_sha
    source = validate_source(_git(arguments.repository_root, "rev-parse",
                                  f"{requested}^{{commit}}"))
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
        _outputs(arguments.github_output, {
            "source_commit": source,
            "slots": json.dumps(document["slots"], separators=(",", ":")),
            "duration_seconds": str(arguments.duration_seconds),
            "profile": arguments.profile, "retention": arguments.retention})
    print(f"v44CloudPlan=PASS profile={arguments.profile} "
          f"members={arguments.repeats} source={source}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
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
        document = json.loads(arguments.plan.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as failure:
        raise EvidenceError("cannot read V4.4 cloud plan") from failure
    with arguments.github_step_summary.open("a", encoding="utf-8") as stream:
        stream.write(render_summary(document))
    print("v44CloudPlanSummary=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as failure:
        print(f"v44CloudPlan=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
