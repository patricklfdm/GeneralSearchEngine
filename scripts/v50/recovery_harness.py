"""Real three-JVM recovery, SIGKILL and checksum-pinned V4.4 semantic-control gate."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import time

from scripts.v50 import storage_format as storage
from scripts.v50.leader_harness import Worker, ports, settled
from scripts.v50.storage_harness import ROOT, CLASSPATH, save, check
from scripts.v50.recovery_oracle import validate

WORKER = "io.github.patricklfdm.generalsearch.replication.V50RecoveryWorker"
CONTROL = "io.github.patricklfdm.generalsearch.replication.V50RecoveryControl"
CONTROL_SHA = "0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5"
BARRIERS = ("AFTER_RECOVERY_STAGE_CREATE", "AFTER_RECOVERY_SNAPSHOT_FILE_FORCE", "AFTER_RECOVERY_ENTRIES_FORCE",
            "AFTER_RECOVERY_PROOFS_FORCE", "AFTER_RECOVERY_STAGE_FORCE", "BEFORE_RECOVERY_POINTER_PUBLISH",
            "AFTER_RECOVERY_POINTER_RENAME", "AFTER_RECOVERY_POINTER_FORCE", "AFTER_RECOVERY_FLOOR_RENAME",
            "AFTER_RECOVERY_CLEANUP_MEMBER", "AFTER_RECOVERY_LEGACY_COMPACTION", "AFTER_RECOVERY_CLEANUP_FORCE")


def hashes(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.rglob("*")) if path.is_file() and not path.is_symlink()}


class Group:
    def __init__(self, case, barrier="", target=0):
        self.case, self.ports, self.barrier, self.target = case, ports(), barrier, target
        self.workers, self.generations = [None] * 3, [0] * 3
        self.history, self.acknowledged = [], 0
        case.mkdir()
        try:
            for index in range(3): self.start(index)
            check(all(worker.process.poll() is None for worker in self.workers), "voters were not concurrent")
        except BaseException:
            self.close()
            raise

    def start(self, index, armed=True):
        self.generations[index] += 1
        self.workers[index] = Worker(self.case / f"node-{index + 1}", index + 1, self.ports,
                self.barrier if armed and index == self.target else "", self.generations[index], worker_class=WORKER)

    def stop(self, index, kill=False):
        worker = self.workers[index]
        if worker is not None:
            try: worker.finish(kill=kill)
            finally: self.workers[index] = None

    def close(self):
        errors = []
        for index in range(3):
            try: self.stop(index)
            except Exception as error: errors.append(str(error))
        if errors:
            save(self.case / "cleanup-errors.json", errors)
            raise RuntimeError("recovery harness cleanup failed: " + "; ".join(errors))

    def command(self, name, **values):
        result = self.workers[0].command(name, **values)
        check(result["accepted"], f"{name} failed: {result}")
        return result

    def apply(self, name, **values):
        result = self.command(name, **values)
        self.history.append({"command": name, **values})
        self.acknowledged = max(self.acknowledged, result["appliedIndex"])
        return result

    def prepare(self):
        self.command("activate")
        self.apply("add", id=1, value="shared")
        self.apply("add", id=2, value="second")
        settled(self.workers, 3)
        self.command("checkpoint")
        self.apply("update", id=2, value="changed")
        self.apply("add", id=3, value="shared")
        self.apply("remove", id=1)
        self.apply("add", id=1, value="shared")
        self.apply("drop")
        result = self.apply("index")
        settled(self.workers, result["appliedIndex"])

    def replace(self, index):
        self.stop(index, kill=True)
        root = self.case / f"node-{index + 1}"
        backup = root / f"lost-replica-{self.generations[index]}"
        (root / "replica").rename(backup)
        (root / "replacement.request").write_text("explicit test-only replacement\n")
        self.start(index, armed=False)
        return storage.inspect(backup)

    def capture(self, label):
        check(all(worker is None for worker in self.workers), "inspection requires closed owners")
        reports = {}
        for index in range(3):
            node = f"node-{index + 1}"
            directory = self.case / node / "replica"
            before = hashes(directory)
            shutil.copytree(directory, self.case / f"{label}-{node}")
            reports[node] = storage.inspect(directory)
            save(self.case / f"{label}-{node}-independent.json", reports[node])
            save(self.case / f"{label}-{node}-sha256.json", before)
            check(before == hashes(directory), "independent inspection changed bytes")
        return reports


def control(case, history, artifact):
    request = case / "control-operations.jsonl"
    request.write_text("".join(json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n" for item in history))
    classpath = os.pathsep.join([str(artifact), str(ROOT / "general-search-engine-replication/target/classes"),
                                str(ROOT / "general-search-engine-replication/target/test-classes")])
    result = subprocess.run(["java", "-cp", classpath, CONTROL, str(request)], text=True, capture_output=True, timeout=30)
    (case / "v44-control.stdout").write_text(result.stdout)
    (case / "v44-control.stderr").write_text(result.stderr)
    check(result.returncode == 0, "published V4.4 control failed")
    origins = [line.removeprefix("controlSource=") for line in result.stderr.splitlines() if line.startswith("controlSource=")]
    check(origins == [str(artifact)], "semantic control did not load the pinned V4.4 core")
    return json.loads(result.stdout)


def finish(group, before, artifact):
    observed = {f"node-{index + 1}": worker.command("status") for index, worker in enumerate(group.workers)}
    group.close()
    reports = group.capture("final")
    expected = control(group.case, group.history, artifact)
    oracle = validate(before, reports, observed, expected, group.acknowledged)
    save(group.case / "observed-application.json", observed)
    save(group.case / "model-comparison.json", oracle)
    save(group.case / "result.json", {"status": "PASS", "threeConcurrentVoters": True, "oracle": oracle})
    print(json.dumps({"case": group.case.name, "status": "PASS", "oracle": oracle}, sort_keys=True), flush=True)
    return {"case": group.case.name, "status": "PASS"}


def wait_barrier(group, target):
    worker = group.workers[target]
    path = group.case / f"node-{target + 1}/barrier.json"
    deadline = time.monotonic() + 20
    while True:
        check(worker.process.poll() is None and time.monotonic() < deadline, "process missed recovery barrier")
        if path.exists():
            try: marker = json.loads(path.read_text())
            except json.JSONDecodeError: pass
            else: break
        time.sleep(0.01)
    check(marker["pid"] == worker.process.pid and marker["node"] == f"node-{target + 1}" and marker["barrier"] == group.barrier, "wrong recovery crash identity")
    return marker


def crash_case(workspace, artifact, barrier, kind="checkpoint"):
    target = 2 if kind == "transfer" else 0
    case = workspace / (kind + "-" + barrier.lower())
    group = Group(case, barrier, target)
    try:
        group.prepare()
        if kind == "transfer":
            group.stop(2, kill=True)
            group.apply("add", id=4, value="shared")
            group.command("checkpoint")
            group.start(2)
        group.workers[target].command("arm")
        if kind == "mutation": group.workers[0].send("update", id=2, value="uncertain")
        elif kind == "transfer": group.workers[0].send("catchup", peer="node-3")
        else: group.workers[0].send("checkpoint")
        marker = wait_barrier(group, target)
        if target == 0:
            ready, _, _ = select.select([group.workers[0].process.stdout], [], [], 0)
            check(not ready, "control response preceded held recovery barrier")
        group.stop(target, kill=True)
        if target != 0: check(not group.workers[0].receive()["accepted"], "interrupted transfer returned success")
        group.close()
        before = group.capture("pre-reopen")
        save(case / "crash.json", {"signal": "SIGKILL", "marker": marker, "clientSuccessReturned": False})
        if kind == "mutation" and barrier == "AFTER_LOCAL_PROOF_FORCE":
            group.history.append({"command": "update", "id": 2, "value": "uncertain"})
            save(case / "indeterminate-response.json", {"reason": "surviving valid proof is protected during recovery", "originalSuccessReturned": False})
        for index in range(3): group.start(index, armed=False)
        group.command("activate")
        group.command("catchup", peer="node-2")
        group.command("catchup", peer="node-3")
        group.command("checkpoint")  # Also proves that interrupted cleanup can be retried.
        return finish(group, before, artifact)
    finally:
        group.close()


def lifecycle_case(workspace, artifact):
    group = Group(workspace / "incremental-snapshot-and-replacement")
    try:
        group.prepare(); group.stop(2, kill=True)
        group.apply("update", id=2, value="shared"); group.apply("add", id=4, value="late")
        group.start(2); group.command("catchup", peer="node-3")
        group.stop(2, kill=True)
        group.apply("add", id=5, value="snapshot fallback"); group.command("checkpoint")
        group.apply("add", id=6, value="tail after floor")
        group.start(2); group.command("catchup", peer="node-3")
        before = {"replaced-follower": group.replace(2)}
        group.command("catchup", peer="node-3")
        before["replaced-leader"] = group.replace(0)
        group.stop(2, kill=True)
        check(not group.workers[0].command("activate")["accepted"], "replacement leader voted before reconstruction")
        response = group.workers[0].command("reconstruct")
        check(not response["accepted"] and response["reason"] == "QUORUM_UNAVAILABLE" and response["lastLogIndex"] == 0,
              "replacement leader counted its erased vote")
        group.start(2, armed=False); group.command("reconstruct")
        group.apply("update", id=6, value="after two-survivor reconstruction")
        group.command("catchup", peer="node-2"); group.command("catchup", peer="node-3"); group.command("checkpoint")
        return finish(group, before, artifact)
    finally:
        group.close()


def corruptions(workspace, source):
    baseline = subprocess.run(["java", "-cp", CLASSPATH, WORKER, "inspect", str(source)], text=True, capture_output=True, timeout=20)
    check(baseline.returncode == 0 and json.loads(baseline.stdout)["accepted"], "Java rejected valid recovery source")
    results = []
    for kind in ("pointer-checksum", "snapshot-checksum", "missing-selector", "floor-ancestry", "truncated-snapshot", "unknown-generation-member"):
        case = workspace / ("corrupt-" + kind); case.mkdir(); directory = case / "replica"; shutil.copytree(source, directory)
        pointer = directory / "current.gsr"
        # Read the selected slot from the independently framed pointer.
        reader = storage.Reader(storage.single(pointer, 10)[0]); reader.take(32); reader.identity(64); slot = reader.string(32)
        if kind == "missing-selector": pointer.unlink()
        elif kind == "unknown-generation-member": (directory / slot / "unknown.bin").write_bytes(b"unexpected")
        else:
            path = directory / slot / "snapshot.gsr" if "snapshot" in kind else directory / "recovery-floor.gsr" if kind == "floor-ancestry" else pointer
            raw = bytearray(path.read_bytes())
            if kind == "truncated-snapshot": raw = raw[:-1]
            elif kind == "floor-ancestry":
                body = bytearray(raw[48:]); reader = storage.Reader(body); reader.take(32); reader.identity(64); reader.number("q"); body[reader.offset] ^= 1; raw = storage.frame(12, body)
            else: raw[-1] ^= 1
            path.write_bytes(raw)
        before = hashes(directory)
        try: storage.inspect(directory)
        except (ValueError, OSError): pass
        else: raise AssertionError("independent parser accepted " + kind)
        result = subprocess.run(["java", "-cp", CLASSPATH, WORKER, "inspect", str(directory)], text=True, capture_output=True, timeout=20)
        (case / "java.stdout").write_text(result.stdout); (case / "java.stderr").write_text(result.stderr)
        check(result.returncode == 3 and not json.loads(result.stdout)["accepted"], "Java accepted " + kind)
        check(before == hashes(directory), "corruption rejection changed authority bytes")
        results.append(kind)
    return results


def run(workspace, artifact):
    artifact = artifact.resolve()
    check(hashlib.sha256(artifact.read_bytes()).hexdigest() == CONTROL_SHA, "V4.4 control checksum mismatch")
    workspace.mkdir(parents=True, exist_ok=False)
    save(workspace / "source.json", {"sourceSha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
         "gitStatus": subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True), "controlSha256": CONTROL_SHA, "paidCloud": False})
    from scripts.v50.recovery_format import generate
    generated = workspace / "python-produced"
    generate(generated)
    golden = ROOT / "general-search-engine-replication/src/test/resources/replication/v50-recovery-v1/node-2"
    check(hashes(generated) == hashes(golden), "independent recovery fixture bytes changed")
    inspected = subprocess.run(["java", "-cp", CLASSPATH, WORKER, "inspect", str(generated)], text=True, capture_output=True, timeout=20)
    (workspace / "python-in-java.stdout").write_text(inspected.stdout)
    (workspace / "python-in-java.stderr").write_text(inspected.stderr)
    check(inspected.returncode == 0 and json.loads(inspected.stdout)["accepted"], "Java rejected independently generated recovery bytes")
    results = [lifecycle_case(workspace, artifact)]
    results += [crash_case(workspace, artifact, barrier) for barrier in BARRIERS]
    results += [crash_case(workspace, artifact, barrier, "mutation") for barrier in ("AFTER_LOCAL_ENTRY_FORCE", "AFTER_LOCAL_PROOF_FORCE")]
    results += [crash_case(workspace, artifact, barrier, "transfer") for barrier in ("AFTER_SNAPSHOT_CHUNK_FORCE", "BEFORE_SNAPSHOT_INSTALL_ACK")]
    malformed = corruptions(workspace, workspace / "incremental-snapshot-and-replacement/final-node-1")
    save(workspace / "result.json", {"status": "PASS", "cases": results, "corruptionCases": malformed, "paidCloud": False})
    print(json.dumps({"v50Phase4Recovery": "PASS", "cases": len(results), "corruptionCases": len(malformed), "evidence": str(workspace)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--control-jar", type=Path, required=True)
    args = parser.parse_args(); run(args.workspace, args.control_jar)
