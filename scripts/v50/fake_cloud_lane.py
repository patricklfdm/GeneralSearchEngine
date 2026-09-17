"""No-GCP control plane for the frozen three-voter topology."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from scripts.v50.evidence import write_bundle


PROFILE_REPEATS = {"experiment": 1, "failure-drill": 1, "canonical": 3}
FAILURES = ("provision-node-2", "run-node-1", "cleanup-node-2-data-disk")


def plan(profile: str) -> dict:
    if profile not in PROFILE_REPEATS:
        raise ValueError("unsupported profile")
    foundation = json.loads((Path(__file__).resolve().parents[2]
                             / "docs/v5x/v5.0/phase1-plan.json").read_text())
    return {
        "schemaVersion": "gse-v50-cloud-plan-v1",
        "suite": "v5.0-replicated-single-shard-suite-v1",
        "preset": "v5.0-replicated-single-shard-v1",
        "profile": profile,
        "topologyRepeats": PROFILE_REPEATS[profile],
        "repeatsAreSerial": True,
        "votersPerTopology": 3,
        "votersConcurrent": True,
        "selection": foundation["cloudSelection"],
        "resources": {
            "vcpusPerVoter": 8,
            "peakVcpus": 24,
            "dataDiskGiBPerVoter": 100,
            "bootDiskGiBPerVoter": 50,
            "peakProvisionedDiskGiB": 450,
            "privateReplicationOnly": True,
        },
        "limits": {"maximumTopologyRuntimeSeconds": 5400,
                   "maximumCompleteRunCostUsd": foundation["resourceBounds"]["maximumCompleteRunCostUsd"]},
    }


def run(output: Path, source_sha: str, profile: str, failure: str | None) -> None:
    if failure is not None and failure not in FAILURES:
        raise ValueError("unsupported injected failure")
    topology = plan(profile)
    live, running, events, cleanup = {}, set(), [], []
    run_status, cleanup_status = "PASS", "PASS"

    def event(repetition, action, **details):
        events.append(dict(sequence=len(events), topology=repetition, action=action, **details))

    def create(repetition, suffix, kind):
        name = f"topology-{repetition}-{suffix}"
        if name in live:
            raise ValueError("duplicate simulated resource")
        live[name] = kind
        event(repetition, "create", resource=name, kind=kind)

    for repetition in range(1, topology["topologyRepeats"] + 1):
        if live or running:
            raise ValueError("preceding topology cleanup is incomplete")
        event(repetition, "begin")
        try:
            create(repetition, "private-replication-firewall", "firewall")
            create(repetition, "evidence-staging-prefix", "staging")
            for index in range(1, 4):
                create(repetition, f"node-{index}-boot-disk", "boot-disk")
                create(repetition, f"node-{index}-data-disk", "data-disk")
                if failure == "provision-node-2" and index == 2:
                    event(repetition, "fault", point=failure)
                    raise RuntimeError(failure)
                create(repetition, f"node-{index}-vm", "vm")
            # Running sets represent overlapping lifetimes in the fake control
            # plane. These are simulated voters, not Java workers or real VMs.
            for index in range(1, 4):
                node = f"node-{index}"
                running.add(node)
                event(repetition, "start", node=node)
            event(repetition, "measure", voters=sorted(running))
            if failure == "run-node-1":
                event(repetition, "fault", point=failure)
                raise RuntimeError(failure)
        except RuntimeError:
            run_status = "FAIL"
        finally:
            for node in sorted(running):
                event(repetition, "stop", node=node)
            running.clear()
            for name in reversed(tuple(live)):
                if failure == "cleanup-node-2-data-disk" and name.endswith("node-2-data-disk"):
                    event(repetition, "fault", point=failure)
                    event(repetition, "delete-failed", resource=name, kind=live[name])
                    cleanup_status, run_status = "FAIL", "FAIL"
                    continue
                kind = live.pop(name)
                event(repetition, "delete", resource=name, kind=kind)
                cleanup.append({"resource": name, "deleted": name not in live})
            event(repetition, "end", status=run_status)
        if run_status == "FAIL":
            break
    write_bundle(output, {
        "profile": profile,
        "sourceCommit": source_sha,
        "authorityClaim": "fake-control-plane-only",
        "plan": topology,
        "injectedFailure": failure,
        "runStatus": run_status,
        "events": events,
        "cleanup": cleanup,
        "remainingResources": sorted(live),
        "cleanupStatus": cleanup_status,
    })
    if live:
        raise ValueError("fake cleanup incomplete; failure evidence retained")
    print(f"v50FakeCloud=PASS profile={profile} cleanup={cleanup_status}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--profile", choices=tuple(PROFILE_REPEATS), required=True)
    parser.add_argument("--inject-failure", choices=FAILURES)
    args = parser.parse_args()
    run(args.output, args.source_sha, args.profile, args.inject_failure)


if __name__ == "__main__":
    main()
