"""Production-JVM storage crash gate, with independent pre-reopen evidence.

All processes are our own Popen children. Only fresh caller-selected workspaces
are written; failed cases and raw bytes are retained for diagnosis. No network.
"""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import time

from scripts.v50 import storage_format as storage


ROOT = Path(__file__).resolve().parents[2]
CLASSPATH = os.pathsep.join(str(ROOT / directory) for directory in (
    "target/classes", "general-search-engine-replication/target/classes",
    "general-search-engine-replication/target/test-classes"))
WORKER = "io.github.patricklfdm.generalsearch.replication.V50ReplicaStorageWorker"
STATE_FIELDS = ("promisedEpoch", "lastLogIndex", "commitIndex")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def hashes(directory):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.iterdir())}


def java(*args):
    return ["java", "-cp", CLASSPATH, WORKER, *map(str, args)]


def invoke(case, label, *args):
    result = subprocess.run(java(*args), text=True, capture_output=True, timeout=20)
    (case / f"{label}.stdout").write_text(result.stdout)
    (case / f"{label}.stderr").write_text(result.stderr)
    check(result.returncode in (0, 3), f"unexpected JVM result: {result.returncode}: {result.stderr}")
    return json.loads(result.stdout)


def independent(directory):
    try:
        return {"accepted": True, **storage.inspect(directory)}
    except ValueError as error:
        return {"accepted": False, "reason": str(error)}


@contextmanager
def stopped_process(case, *args):
    marker = case / "barrier.json"
    with (case / "worker.stdout").open("w") as stdout, (case / "worker.stderr").open("w") as stderr:
        process = subprocess.Popen(java(*args, marker), stdout=stdout, stderr=stderr)
        try:
            deadline = time.monotonic() + 20
            while not marker.exists():
                check(process.poll() is None, "worker exited before requested barrier")
                check(time.monotonic() < deadline, "worker did not reach barrier in 20 seconds")
                time.sleep(0.02)
            # The marker is written once by this exact child; parse after its write completes.
            while True:
                try:
                    ready = json.loads(marker.read_text())
                    break
                except json.JSONDecodeError:
                    check(time.monotonic() < deadline, "incomplete barrier marker")
                    time.sleep(0.01)
            check(ready["pid"] == process.pid and ready["ackReturned"] is False, "invalid barrier identity/ACK")
            yield process, ready
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            save(case / "process.json", {"pid": process.pid, "returnCode": process.returncode,
                                         "signal": "SIGKILL" if process.returncode == -signal.SIGKILL else None})


def crash_case(workspace, barrier):
    case = workspace / barrier.lower()
    case.mkdir()
    directory = case / "node-2"
    with stopped_process(case, "crash", directory, barrier) as (process, ready):
        process.kill()
        check(process.wait(timeout=10) == -signal.SIGKILL, "worker did not die from SIGKILL")
    check(ready["barrier"] == barrier, "wrong crash barrier")
    before = hashes(directory)
    shutil.copytree(directory, case / "pre-reopen")
    python_report = independent(directory)
    save(case / "independent-before-reopen.json", python_report)
    java_report = invoke(case, "reopen", "inspect", directory)
    save(case / "java-reopen.json", java_report)
    check(python_report["accepted"] == java_report["accepted"], f"parser disagreement at {barrier}")
    check(before == hashes(directory), "reopen modified authoritative bytes")
    save(case / "pre-reopen-sha256.json", before)
    partial = barrier.endswith("WRITE_CHUNK")
    initializing = "INIT_" in barrier
    valid = not partial and (not initializing or "storage-ready.gsr_FORCE" in barrier)
    check(python_report["accepted"] == valid, f"unexpected valid prefix at {barrier}")
    if valid:
        if initializing:
            expected = (1, 0, 0)
        else:
            operation = next(op for op in ("PROMISE", "ENTRY", "PROOF") if op in barrier)
            before_write = barrier.startswith("BEFORE_") and barrier.endswith("_WRITE")
            expected = {"PROMISE": (1 if before_write else 2, 0, 0),
                        "ENTRY": (2, 0 if before_write else 1, 0),
                        "PROOF": (2, 1, 0 if before_write else 1)}[operation]
        for report in (python_report, java_report):
            check(tuple(report[field] for field in STATE_FIELDS) == expected, f"lost/added history at {barrier}")
    return {"barrier": barrier, "ackReturned": False, "acceptedOnReopen": valid,
            "rawBytesUnchanged": True, "processKilled": True}


def ownership_case(workspace, source):
    case = workspace / "ownership"
    case.mkdir()
    directory = case / "node-2"
    shutil.copytree(source, directory)
    before = hashes(directory)
    with stopped_process(case, "hold", directory) as (process, _):
        python_report = independent(directory)
        java_report = invoke(case, "while-owned", "inspect", directory)
        check(not python_report["accepted"] and "owner" in python_report["reason"], "Python bypassed owner lock")
        check(not java_report["accepted"] and java_report["reason"] == "STORAGE_FAILURE", "Java bypassed owner lock")
        check(process.poll() is None, "owner exited during rejection")
    check(invoke(case, "after-owner-exit", "inspect", directory)["accepted"], "owner lock was not released")
    check(before == hashes(directory), "ownership checks changed bytes")
    return {"independentLockRejection": True, "javaLockRejection": True, "releasedAfterKill": True}


def corruption_cases(workspace, source):
    results = []
    for kind in ("major", "length", "operation", "payload", "predecessor", "promise", "receipt", "missing-ready", "v4-magic"):
        case = workspace / ("invalid-" + kind)
        case.mkdir()
        directory = case / "node-2"
        shutil.copytree(source, directory)
        path = directory / ("proofs.gsr" if kind == "receipt" else "entries.gsr")
        original = path.read_bytes()
        start = 48 + struct.unpack_from(">i", original, 12)[0]
        size = 48 + struct.unpack_from(">i", original, start + 12)[0]
        body = bytearray(original[start + 48:start + size])
        if kind == "missing-ready":
            (directory / "storage-ready.gsr").unlink()
        else:
            if kind == "operation": body[64] = 11
            if kind == "payload": body[117] ^= 1
            if kind == "predecessor": body[81] ^= 1
            if kind == "promise": struct.pack_into(">q", body, 32, 3)
            if kind == "receipt": body[-1] ^= 1
            edited = bytearray(storage.frame(6 if kind == "receipt" else 5, body))
            if kind == "major": edited[5] = 2
            if kind == "length": struct.pack_into(">i", edited, 12, 2 ** 31 - 1)
            if kind == "v4-magic": edited[:4] = b"GSEW"
            path.write_bytes(original[:start] + edited + original[start + size:])
        before = hashes(directory)
        report = independent(directory)
        save(case / "independent.json", report)
        check(not report["accepted"], "independent parser accepted " + kind)
        check(not invoke(case, "java", "inspect", directory)["accepted"], "Java accepted " + kind)
        check(before == hashes(directory), "corruption rejection changed bytes")
        results.append(kind)
    return results


def run(workspace):
    workspace.mkdir(parents=True, exist_ok=False)
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    save(workspace / "source.json", {"schemaVersion": 1, "sourceSha": source, "workingTreeDirty": bool(dirty),
                                      "gitStatus": dirty, "productionRuntimeEnabled": False, "paidCloud": False})
    golden = workspace / "python-produced"
    python_report = storage.generate(golden)
    java_report = invoke(workspace, "python-in-java", "inspect", golden)
    check(java_report["accepted"], "Java rejected independent golden bytes")
    produced = workspace / "java-produced"
    check(invoke(workspace, "java-create", "create", produced)["accepted"], "Java create failed")
    check(hashes(golden) == hashes(produced), "Python and Java writers disagree on bytes")
    check(storage.inspect(produced) == python_report, "independent Java-byte inspection differs")
    save(workspace / "independent-java-bytes.json", storage.inspect(produced))
    barriers = [f"{prefix}_{operation}_{suffix}" for operation in ("PROMISE", "ENTRY", "PROOF")
                for prefix, suffix in (("BEFORE", "WRITE"), ("AFTER", "WRITE_CHUNK"),
                                       ("BEFORE", "FORCE"), ("AFTER", "FORCE"), ("BEFORE", "ACK"))]
    barriers += ["AFTER_INIT_manifest.gsr_WRITE_CHUNK", "BEFORE_INIT_entries.gsr_FORCE",
                 "AFTER_INIT_storage-ready.gsr_WRITE_CHUNK", "AFTER_INIT_storage-ready.gsr_FORCE"]
    crashes = [crash_case(workspace, barrier) for barrier in barriers]
    ownership = ownership_case(workspace, produced)
    corruption = corruption_cases(workspace, produced)
    result = {"schemaVersion": 1, "status": "PASS", "crossLanguageBytes": True,
              "crashCases": crashes, "ownership": ownership, "corruptionCases": corruption,
              "applicationApplyEnabled": False, "paidCloud": False}
    save(workspace / "result.json", result)
    print(json.dumps({"v50Phase2Storage": "PASS", "crashCases": len(crashes), "corruptionCases": len(corruption),
                      "evidence": str(workspace)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    run(parser.parse_args().workspace)
