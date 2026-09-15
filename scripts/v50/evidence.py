"""Checksummed Phase 1 process and fake-cloud evidence bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


SCHEMA = "gse-v50-replication-evidence-v1"
MAX_MEMBER_BYTES = 1024 * 1024
MAX_BUNDLE_BYTES = 8 * MAX_MEMBER_BYTES
NODES = ("node-1", "node-2", "node-3")


def canonical_bytes(document: dict) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_bundle(directory: Path, document: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    document = dict(document)
    document["schemaVersion"] = SCHEMA
    data = canonical_bytes(document)
    (directory / "evidence.json").write_bytes(data)
    lines = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("unsafe evidence member")
        if path.is_file() and path.name != "artifact-checksums.sha256":
            lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(directory).as_posix()}\n")
    (directory / "artifact-checksums.sha256").write_text("".join(lines), encoding="utf-8")


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _validate_cloud(document: dict) -> None:
    """Independent replay of lifecycle evidence; never imports the fake runner."""
    profile = document["profile"]
    repeats = {"experiment": 1, "failure-drill": 1, "canonical": 3}[profile]
    expected_plan = json.loads((Path(__file__).resolve().parents[2]
                               / "docs/v5x/v5.0/phase1-plan.json").read_text())
    plan = document["plan"]
    _require(plan["schemaVersion"] == "gse-v50-cloud-plan-v1"
             and plan["suite"] == expected_plan["suite"]
             and plan["preset"] == expected_plan["preset"]
             and plan["profile"] == profile and plan["topologyRepeats"] == repeats
             and plan["votersPerTopology"] == 3 and plan["votersConcurrent"] is True
             and plan["repeatsAreSerial"] is True, "invalid topology plan")
    _require(plan["selection"] == expected_plan["cloudSelection"], "cloud selection changed")
    for field, value in expected_plan["resourceBounds"].items():
        section = plan["limits"] if field.startswith("maximum") else plan["resources"]
        _require(section.get(field) == value, f"invalid resource plan: {field}")
    _require(plan["resources"]["privateReplicationOnly"] is True, "public replication plan")
    failure = document.get("injectedFailure")
    _require(failure in (None, "provision-node-2", "run-node-1", "cleanup-node-2-data-disk"),
             "unknown failure injection")
    live, running, created, deleted = {}, set(), set(), []
    active, completed, measured, faults = None, 0, False, []
    expected_members = {}
    events = document["events"]
    _require(isinstance(events, list) and 1 <= len(events) <= 1000, "invalid lifecycle event count")
    for sequence, event in enumerate(events):
        _require(event["sequence"] == sequence and type(event["sequence"]) is int,
                 "noncontiguous lifecycle sequence")
        repetition, action = event["topology"], event["action"]
        if action == "begin":
            _require(active is None and not live and not running and not faults
                     and repetition == completed + 1 and repetition <= repeats,
                     "topology began before preceding cleanup or after failure")
            active, measured = repetition, False
            expected_members = {
                f"topology-{repetition}-{node}-{suffix}": kind
                for node in NODES for suffix, kind in (
                    ("vm", "vm"), ("boot-disk", "boot-disk"), ("data-disk", "data-disk"))}
            expected_members.update({
                f"topology-{repetition}-private-replication-firewall": "firewall",
                f"topology-{repetition}-evidence-staging-prefix": "staging"})
            continue
        _require(active == repetition, "event outside its topology")
        if action == "create":
            name, kind = event["resource"], event["kind"]
            _require(expected_members.get(name) == kind and name not in created and not faults,
                     "unknown/duplicate resource or creation after failure")
            live[name] = kind
            created.add(name)
            _require(sum(v == "vm" for v in live.values()) * 8 <= 24, "CPU cap exceeded")
            _require(sum(50 if v == "boot-disk" else 100 if v == "data-disk" else 0
                         for v in live.values()) <= 450, "disk cap exceeded")
        elif action == "start":
            node = event["node"]
            _require(node in NODES and node not in running and live == expected_members and not faults,
                     "voter start without the complete topology")
            running.add(node)
        elif action == "measure":
            _require(not measured and running == set(NODES) and event["voters"] == list(NODES),
                     "measurement did not have three concurrent voters")
            measured = True
        elif action == "stop":
            _require(event["node"] in running, "stopped an absent voter")
            running.remove(event["node"])
        elif action == "fault":
            point = event["point"]
            _require(point == failure and not faults, "unexpected or repeated failure")
            if point == "provision-node-2":
                _require(not measured and not running
                         and f"topology-{repetition}-node-2-data-disk" in live
                         and f"topology-{repetition}-node-2-vm" not in live,
                         "provision failure at the wrong boundary")
            else:
                _require(measured, "run/cleanup failure before concurrent measurement")
            faults.append(point)
        elif action in {"delete", "delete-failed"}:
            name = event["resource"]
            _require(not running and name in live and live[name] == event["kind"],
                     "deletion of unknown resource or before voter stop")
            if action == "delete":
                del live[name]
                deleted.append(name)
            else:
                _require(faults == ["cleanup-node-2-data-disk"]
                         and name.endswith("node-2-data-disk"), "unclassified cleanup failure")
        elif action == "end":
            _require(not running and (measured or faults == ["provision-node-2"]),
                     "topology did not complete its measurement/failure boundary")
            _require(event["status"] == ("FAIL" if faults else "PASS"), "incorrect topology result")
            active, completed = None, completed + 1
        else:
            raise ValueError("unknown lifecycle action")
    _require(active is None and completed == (1 if failure else repeats), "incomplete topology set")
    _require(faults == ([] if failure is None else [failure]), "failure injection not exercised")
    _require(document["runStatus"] == ("FAIL" if failure else "PASS"), "incorrect run result")
    _require(document["cleanup"] == [{"resource": name, "deleted": True} for name in deleted],
             "cleanup receipts disagree with deletion events")
    _require(document["remainingResources"] == sorted(live), "remaining-resource inventory mismatch")
    _require(not live and document["cleanupStatus"] == "PASS" and created == set(deleted),
             "cleanup incomplete")


def _properties(path: Path) -> dict:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


def _validate_process(directory: Path, document: dict) -> None:
    _require(document["voters"] == 3 and document["processesConcurrent"] is True,
             "invalid process topology")
    events = [json.loads(line) for line in
              (directory / "members/process-events.jsonl").read_text().splitlines()]
    live, generations, exits, windows = {}, {}, [], 0
    observed_pids = set()
    for sequence, event in enumerate(events):
        _require(event["sequence"] == sequence, "noncontiguous process sequence")
        action = event["action"]
        if action == "concurrent":
            _require(set(live) == set(NODES) and event["pids"] == live,
                     "three live JVMs were not observed concurrently")
            _require(generations == ({node: 1 for node in NODES} if windows == 0
                                     else {"node-1": 2, "node-2": 1, "node-3": 2}),
                     "concurrent window at the wrong restart boundary")
            windows += 1
            continue
        node, pid, generation = event["node"], event["pid"], event["generation"]
        _require(node in NODES and type(pid) is int and pid > 0, "invalid process identity")
        if action == "ready":
            _require(node not in live and pid not in observed_pids
                     and generation == generations.get(node, 0) + 1,
                     "invalid process restart")
            live[node], generations[node] = pid, generation
            observed_pids.add(pid)
            worker_lines = (directory / f"members/{node}/events.log").read_text().splitlines()
            _require(f"READY node={node} generation={generation} pid={pid}" in worker_lines,
                     "worker and parent readiness records disagree")
        elif action in {"crash", "storage-fault", "cleanup"}:
            _require(windows >= 1 and live.get(node) == pid and generations[node] == generation,
                     "exit without exact captured live PID")
            _require(action != "cleanup" or windows == 2, "cleanup before restarted concurrency check")
            _require(event["exitCode"] == (20 if action == "storage-fault" else 137),
                     "unexpected worker exit code")
            if action != "cleanup":
                exits.append((action, node, generation))
            del live[node]
        else:
            raise ValueError("unknown process action")
    _require(not live and windows == 2 and generations == {"node-1": 2, "node-2": 1, "node-3": 2},
             "incomplete process lifecycle")
    _require(exits == [("crash", "node-1", 1), ("storage-fault", "node-3", 1)],
             "missing classified process faults")
    for node, generation in generations.items():
        ready = _properties(directory / f"members/{node}/ready.properties")
        last_ready = [e for e in events if e["action"] == "ready" and e["node"] == node][-1]
        _require(ready == {"nodeId": node, "generation": str(generation), "pid": str(last_ready["pid"])},
                 "final readiness receipt mismatch")
    fault = _properties(directory / "members/node-3/storage-fault.properties")
    storage_exit = next(e for e in events if e["action"] == "storage-fault")
    _require(fault == {"nodeId": "node-3", "generation": "1", "exitCode": "20",
                       "pid": str(storage_exit["pid"])}, "storage-fault receipt mismatch")
    _require(f"STORAGE_FAULT node=node-3 generation=1 pid={storage_exit['pid']}" in
             (directory / "members/node-3/events.log").read_text().splitlines(),
             "worker storage-fault event is absent")


def validate(directory: Path) -> dict:
    _require(not directory.is_symlink(), "unsafe evidence directory")
    members = {}
    total = 0
    for path in directory.rglob("*"):
        _require(not path.is_symlink(), "unsafe evidence member")
        if path.is_file():
            size = path.stat().st_size
            _require(size <= MAX_MEMBER_BYTES, "evidence member capacity exceeded")
            total += size
            _require(total <= MAX_BUNDLE_BYTES and len(members) < 64,
                     "evidence bundle capacity exceeded")
            if path.name != "artifact-checksums.sha256":
                members[path.relative_to(directory).as_posix()] = path
    _require(total <= MAX_BUNDLE_BYTES, "evidence bundle capacity exceeded")
    checksums = (directory / "artifact-checksums.sha256").read_text().splitlines()
    expected = {}
    for line in checksums:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        _require(match is not None, "invalid checksum record")
        digest, name = match.groups()
        _require(name in members and name not in expected, "unsafe or duplicate checksum member")
        expected[name] = digest
    _require(set(expected) == set(members) and "evidence.json" in members, "incomplete checksum inventory")
    for name, path in members.items():
        _require(hashlib.sha256(path.read_bytes()).hexdigest() == expected[name], "evidence checksum mismatch")
    raw = (directory / "evidence.json").read_bytes()
    document = json.loads(raw)
    if document.get("schemaVersion") != SCHEMA:
        raise ValueError("unsupported evidence schema")
    _require(isinstance(document.get("sourceCommit"), str)
             and re.fullmatch(r"[0-9a-f]{40}", document["sourceCommit"]) is not None,
             "invalid evidence source identity")
    try:
        if document.get("profile") == "local-crash":
            _require(document["authorityClaim"] == "fixture-only", "invalid authority claim")
            process_members = {f"members/{node}/{name}" for node in NODES
                               for name in ("events.log", "ready.properties", "stdout.log", "stderr.log")}
            process_members.update({"evidence.json", "members/process-events.jsonl",
                                    "members/node-3/storage-fault.properties"})
            _require(set(members) == process_members, "incomplete process artifact inventory")
            _validate_process(directory, document)
        elif document.get("profile") in {"experiment", "failure-drill", "canonical"}:
            _require(document["authorityClaim"] == "fake-control-plane-only", "invalid authority claim")
            _require(set(members) == {"evidence.json"}, "unexpected fake evidence member")
            _validate_cloud(document)
        else:
            raise ValueError("unsupported evidence profile")
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("incomplete or malformed evidence") from error
    return document


def write_harness(directory: Path, source_sha: str, workspace: Path) -> None:
    members = directory / "members"
    members.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(workspace / "process-events.jsonl", members / "process-events.jsonl")
    for node in NODES:
        target = members / node
        target.mkdir()
        for name in ("events.log", "ready.properties", "stdout.log", "stderr.log", "storage-fault.properties"):
            source = workspace / node / name
            if source.exists():
                _require(source.is_file() and not source.is_symlink(), "unsafe worker artifact")
                shutil.copyfile(source, target / name)
    write_bundle(directory, {"profile": "local-crash", "sourceCommit": source_sha,
                            "authorityClaim": "fixture-only", "workspace": str(workspace),
                            "voters": 3, "processesConcurrent": True})


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    write = sub.add_parser("write-harness")
    write.add_argument("directory", type=Path)
    write.add_argument("--source-sha", required=True)
    write.add_argument("--workspace", required=True)
    check = sub.add_parser("validate")
    check.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "write-harness":
        write_harness(args.directory, args.source_sha, Path(args.workspace))
        print("v50ProcessEvidence=PASS")
    else:
        document = validate(args.directory)
        print(f"v50EvidenceValidation=PASS profile={document['profile']}")


if __name__ == "__main__":
    main()
