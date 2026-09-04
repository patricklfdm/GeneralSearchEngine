#!/usr/bin/env python3
"""Validated manual workflow plan for V4.2 storage-evolution evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.v42.evidence import EvidenceError, canonical_json, validate_source

SUITE = "v4.2-storage-evolution-suite-v1"
PRESET = "v4.2-storage-evolution-v1"
SCHEMA = "gse-v42-storage-evolution-cloud-plan-v1"
REPEATS = {"experiment": 1, "canonical": 3, "failure-drill": 1}
RETENTION = {"experiment": "actions", "canonical": "gcs",
             "failure-drill": "actions"}


def validate_inputs(profile: str, repeats: int, duration_seconds: int,
                    retention: str, machine_type: str,
                    provisioning: str) -> dict[str, Any]:
    if profile not in REPEATS or repeats != REPEATS[profile]:
        raise EvidenceError("profile/member count differs from the frozen V4.2 plan")
    if duration_seconds != 1_800:
        raise EvidenceError("duration differs from the frozen V4.2 plan")
    if profile in RETENTION and retention != RETENTION[profile]:
        raise EvidenceError(f"{profile} requires {RETENTION[profile]} retention")
    if machine_type != "c3d-standard-30" or provisioning != "standard":
        raise EvidenceError("V4.2 requires Standard c3d-standard-30")
    return {"profile": profile, "repeats": repeats,
            "durationSeconds": duration_seconds, "retention": retention,
            "machineType": machine_type, "provisioning": provisioning}


def git_output(root: Path, *arguments: str) -> str:
    completed = subprocess.run(["git", *arguments], cwd=root, check=False,
                               capture_output=True, text=True)
    if completed.returncode != 0:
        raise EvidenceError(f"git {' '.join(arguments)} failed")
    return completed.stdout.strip()


def validate_plan(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schemaVersion") != SCHEMA \
            or document.get("suite") != SUITE or document.get("preset") != PRESET:
        raise EvidenceError("unsupported V4.2 cloud plan")
    request = document.get("request")
    resources = document.get("resources")
    slots = document.get("slots")
    if not isinstance(request, dict) or not isinstance(resources, dict) \
            or not isinstance(slots, list):
        raise EvidenceError("V4.2 cloud plan is incomplete")
    validated = validate_inputs(
        request.get("profile", ""), request.get("repeats", -1),
        request.get("durationSeconds", -1), request.get("retention", ""),
        request.get("machineType", ""), request.get("provisioning", ""))
    if request != validated or slots != list(range(1, validated["repeats"] + 1)):
        raise EvidenceError("V4.2 request or slots differ")
    if resources != {
        "sourceDiskType": "pd-balanced", "sourceDiskGiB": 200,
        "targetDiskType": "pd-balanced", "targetDiskGiB": 200,
        "peakRegionalSsdGiB": 400, "peakProjectVcpus": 30,
        "filesystem": "ext4", "mountOptions": "defaults",
        "maximumMemberRuntimeSeconds": 5_400,
        "maximumRunCostUsd": 25, "serialMembers": True,
        "publishedRollbackVersion": "4.1.0",
    }:
        raise EvidenceError("V4.2 resource plan differs")
    validate_source(document.get("sourceCommit"))
    if re.fullmatch(r"[0-9]+", str(document.get("runId", ""))) is None:
        raise EvidenceError("run ID must be numeric")
    return document


def markdown(value: object) -> str:
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
        ("Corpus", "100000 documents / 16 tokens per document"),
        ("Mutations", "10000 before migration / 1000 continued on target"),
        ("Measurement", f"{request['durationSeconds']} seconds"),
        ("Source disk",
         f"{resources['sourceDiskType']} / {resources['sourceDiskGiB']} GiB"),
        ("Target disk",
         f"{resources['targetDiskType']} / {resources['targetDiskGiB']} GiB"),
        ("Peak quota", f"{resources['peakProjectVcpus']} vCPU / "
                       f"{resources['peakRegionalSsdGiB']} GiB regional SSD"),
        ("Filesystem / mount",
         f"{resources['filesystem']} / {resources['mountOptions']}"),
        ("Replacement-host target", "required"),
        ("Published rollback", resources["publishedRollbackVersion"]),
        ("Final retention", request["retention"]),
        ("Maximum member runtime",
         f"{resources['maximumMemberRuntimeSeconds']} seconds"),
        ("Maximum complete-run cost", f"USD {resources['maximumRunCostUsd']}"),
        ("Suite / preset", f"{plan['suite']} / {plan['preset']}"),
    ]
    lines = ["# V4.2 storage-evolution evidence preflight", "",
             "| Field | Validated value |", "|---|---|"]
    lines.extend(f"| {markdown(label)} | `{markdown(value)}` |"
                 for label, value in rows)
    lines.extend(["", "> This preflight requested no OIDC token and created no paid "
                  "resource. Members execute serially and delete all owned VMs and "
                  "disks before the next slot.", ""])
    return "\n".join(lines)


def write_output(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            if re.fullmatch(r"[a-z_]+", key) is None or "\n" in value:
                raise EvidenceError("invalid GitHub output")
            stream.write(f"{key}={value}\n")


def plan_command(arguments: argparse.Namespace) -> int:
    request = validate_inputs(arguments.profile, arguments.repeats,
                              arguments.duration_seconds, arguments.retention,
                              arguments.machine_type, arguments.provisioning)
    root = arguments.repository_root.resolve()
    trusted = validate_source(git_output(
        root, "rev-parse", f"{arguments.trusted_ref}^{{commit}}"))
    requested = arguments.source_commit or arguments.dispatch_sha
    source = validate_source(git_output(root, "rev-parse", f"{requested}^{{commit}}"))
    if source != trusted:
        raise EvidenceError("source must equal the exact protected-master tip")
    document = {
        "schemaVersion": SCHEMA, "suite": SUITE, "preset": PRESET,
        "sourceCommit": source, "trustedRef": arguments.trusted_ref,
        "runId": arguments.run_id, "request": request,
        "slots": list(range(1, arguments.repeats + 1)),
        "resources": {
            "sourceDiskType": "pd-balanced", "sourceDiskGiB": 200,
            "targetDiskType": "pd-balanced", "targetDiskGiB": 200,
            "peakRegionalSsdGiB": 400, "peakProjectVcpus": 30,
            "filesystem": "ext4", "mountOptions": "defaults",
            "maximumMemberRuntimeSeconds": 5_400,
            "maximumRunCostUsd": 25, "serialMembers": True,
            "publishedRollbackVersion": "4.1.0",
        },
    }
    validate_plan(document)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(canonical_json(document))
    if arguments.github_output:
        write_output(arguments.github_output, {
            "source_commit": source,
            "slots": json.dumps(document["slots"], separators=(",", ":")),
            "duration_seconds": str(arguments.duration_seconds),
            "profile": arguments.profile, "retention": arguments.retention})
    print(f"v42CloudPlan=PASS profile={arguments.profile} "
          f"members={arguments.repeats} source={source}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--profile", required=True)
    plan.add_argument("--repeats", type=int, required=True)
    plan.add_argument("--duration-seconds", type=int, required=True)
    plan.add_argument("--retention", required=True)
    plan.add_argument("--machine-type", required=True)
    plan.add_argument("--provisioning", required=True)
    plan.add_argument("--source-commit", default="")
    plan.add_argument("--dispatch-sha", required=True)
    plan.add_argument("--repository-root", type=Path, required=True)
    plan.add_argument("--trusted-ref", required=True)
    plan.add_argument("--run-id", required=True)
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
        raise EvidenceError("cannot read V4.2 cloud plan") from failure
    with arguments.github_step_summary.open("a", encoding="utf-8") as stream:
        stream.write(render_summary(document))
    print("v42CloudPlanSummary=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as failure:
        print(f"v42CloudPlan=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
