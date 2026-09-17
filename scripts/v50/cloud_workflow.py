"""Plan/summary command for the Phase 1 manual no-paid workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from scripts.v50.fake_cloud_lane import plan
from scripts.v50.cloud_summary import cell


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "summary"))
    parser.add_argument("--profile", choices=("experiment", "failure-drill", "canonical"), required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execution", choices=("plan", "fake"), default="plan")
    parser.add_argument("--job-status", default="unknown")
    args = parser.parse_args()
    document = plan(args.profile)
    document["sourceCommit"] = args.source_sha
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.command == "plan":
        args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"v50CloudPlan=PASS profile={args.profile} voters=3 concurrent=true")
    else:
        args.output.write_text(
            "# V5.0 replication no-paid plan\n\n"
            "| Field | Value |\n| --- | --- |\n"
            f"| Source commit | {cell(args.source_sha)} |\n"
            f"| Profile | `{args.profile}` |\n"
            f"| Requested execution / job status | {args.execution} / {cell(args.job_status)} |\n"
            "| Topology | `3 concurrent fixed voters` |\n"
            f"| Serial topology repeats | `{document['topologyRepeats']}` |\n"
            "| Peak quota | `24 vCPU / 450 GiB provisioned disk` |\n"
            f"| Catalog selection | `{document['selection']['machineType']} / {document['selection']['zone']}` |\n"
            f"| Image | `{document['selection']['image']}` |\n"
            "| Boot / data disk per voter | 50 GiB / 100 GiB |\n"
            "| Topology time ceiling | 5400 s |\n"
            "| Planned complete sequence budget | USD 40; no paid approval in Foundation |\n"
            "| Network | private replication only |\n"
            "| Artifacts | v50-foundation run/attempt/profile; 14-day retention |\n"
            "| Execution | `fake only; no GCP authentication or resources` |\n",
            encoding="utf-8")
        print("v50CloudSummary=PASS")


if __name__ == "__main__":
    main()
