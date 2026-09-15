"""Concurrent three-JVM loopback TCP and real leader-crash evidence gate."""

import argparse
import json
import os
from pathlib import Path
import select
import shutil
import signal
import socket
import subprocess
import time

from scripts.v50.storage_harness import ROOT, CLASSPATH, hashes, save, check
from scripts.v50 import storage_format
from scripts.v50.leader_oracle import validate


WORKER = "io.github.patricklfdm.generalsearch.replication.V50LeaderWorker"
BARRIERS = ("AFTER_LOCAL_ENTRY_FORCE", "AFTER_ENTRY_QUORUM", "AFTER_LOCAL_PROOF_FORCE",
            "AFTER_PROOF_QUORUM", "BEFORE_APPLICATION_PUBLICATION", "AFTER_APPLICATION_PUBLICATION", "BEFORE_CLIENT_SUCCESS")


class Worker:
    def __init__(self, root, ordinal, ports, barrier="", generation=1):
        self.root, self.ordinal = root, ordinal
        root.mkdir(parents=True, exist_ok=True)
        self.stderr = (root / f"stderr-{generation}.log").open("w")
        self.receipts = (root / f"control-{generation}.jsonl").open("w")
        self.process = subprocess.Popen(["java", "-cp", CLASSPATH, WORKER, str(root), str(ordinal),
                                         ",".join(map(str, ports)), barrier], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.stderr, text=True, bufsize=1)
        self.started = time.monotonic_ns()
        self.generation = generation
        try:
            ready = self.receive()
            check(ready["ready"] and ready["pid"] == self.process.pid and ready["node"] == f"node-{ordinal}", "wrong worker identity")
        except BaseException:
            self.finish(kill=True)
            raise

    def send(self, command, **values):
        message = {"command": command, **values}
        self.receipts.write(json.dumps({"direction": "request", "message": message, "pid": self.process.pid}) + "\n")
        self.receipts.flush()
        self.process.stdin.write(json.dumps(message, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        self.process.stdin.flush()

    def receive(self):
        readable, _, _ = select.select([self.process.stdout], [], [], 25)
        check(readable, "worker response timed out")
        line = self.process.stdout.readline()
        check(line, "worker exited before response")
        message = json.loads(line)
        self.receipts.write(json.dumps({"direction": "response", "message": message, "pid": self.process.pid}) + "\n")
        self.receipts.flush()
        return message

    def command(self, name, **values):
        self.send(name, **values)
        response = self.receive()
        check(response["command"] == name, "uncorrelated worker control response")
        return response

    def finish(self, kill=False):
        try:
            if self.process.poll() is None:
                if kill:
                    self.process.kill()
                else:
                    check(self.command("close")["accepted"], "worker close failed")
            code = self.process.wait(timeout=10)
            check(code == (-signal.SIGKILL if kill else 0), "unexpected worker exit status")
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=10)
            save(self.root / f"process-{self.generation}.json", {"pid": self.process.pid, "returnCode": self.process.returncode,
                 "startedNanos": self.started, "finishedNanos": time.monotonic_ns(), "generation": self.generation})
            self.stderr.close()
            self.receipts.close()
            self.process.stdin.close()
            self.process.stdout.close()


def ports():
    sockets = []
    try:
        for _ in range(3):
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
        return [sock.getsockname()[1] for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


def settled(workers, index):
    deadline = time.monotonic() + 15
    while True:
        reports = [worker.command("status") for worker in workers]
        if all(report["appliedIndex"] == index for report in reports):
            return reports
        check(time.monotonic() < deadline, "healthy followers did not reach committed boundary")
        time.sleep(0.02)


def collect(case, states, successes):
    reports = {}
    for ordinal in range(1, 4):
        node = f"node-{ordinal}"
        directory = case / node / "replica"
        shutil.copytree(directory, case / f"pre-reopen-{node}")
        before = hashes(directory)
        reports[node] = storage_format.inspect(directory)
        check(before == hashes(directory), "independent inspection changed bytes")
        save(case / f"{node}-sha256.json", before)
        save(case / f"{node}-independent.json", reports[node])
    oracle = validate(reports, states, successes)
    save(case / "model-comparison.json", oracle)
    save(case / "observed-application.json", states)
    return oracle


def run_case(workspace, barrier=None):
    name = barrier.lower() if barrier else "availability-and-restart"
    case = workspace / name
    case.mkdir()
    selected_ports = ports()
    workers, finished = [], set()
    states, successes = {}, []
    try:
        for ordinal in range(1, 4):
            workers.append(Worker(case / f"node-{ordinal}", ordinal, selected_ports, barrier or ""))
        check(all(worker.process.poll() is None for worker in workers), "voters were not concurrent")
        check(workers[0].command("activate")["accepted"], "leader activation failed")
        initial = settled(workers, 1)
        check(all(report["applicationSequence"] == 0 for report in initial), "activation NO_OP changed application sequence")
        successes.append(1)
        if barrier:
            workers[0].send("add", id=1, value="committed-document")
            marker = case / "node-1/barrier.json"
            deadline = time.monotonic() + 15
            while not marker.exists():
                check(workers[0].process.poll() is None and time.monotonic() < deadline, "leader did not reach crash barrier")
                time.sleep(0.01)
            while True:
                try:
                    observed = json.loads(marker.read_text())
                    break
                except json.JSONDecodeError:
                    check(time.monotonic() < deadline, "incomplete crash marker")
                    time.sleep(0.01)
            check(observed["pid"] == workers[0].process.pid and observed["barrier"] == barrier and observed["index"] == 2,
                  "wrong crash identity/index")
            ready_output, _, _ = select.select([workers[0].process.stdout], [], [], 0)
            check(not ready_output, "client response returned before the held success barrier")
            workers[0].finish(kill=True); finished.add(0)
            # The leader has not returned success; its last publication barrier defines the visible cut.
            published = barrier in {"AFTER_APPLICATION_PUBLICATION", "BEFORE_CLIENT_SUCCESS"}
            states["node-1"] = {"appliedIndex": 2 if published else 1, "applicationSequence": int(published)}
            for i in (1, 2):
                states[f"node-{i + 1}"] = workers[i].command("status")
            save(case / "crash.json", {"barrier": barrier, "pid": observed["pid"], "signal": "SIGKILL", "clientSuccessReturned": False})
        else:
            check(workers[0].command("add", id=1, value="committed-document")["accepted"], "healthy mutation failed")
            successes.append(2)
            settled(workers, 2)
            check(not workers[1].command("read", id=1)["accepted"], "follower accepted public read")
            workers[0].finish(kill=True); finished.add(0)
            workers[0] = Worker(case / "node-1", 1, selected_ports, generation=2)
            finished.remove(0)
            activated = workers[0].command("activate")
            check(activated["accepted"] and activated["epoch"] == 3 and activated["applicationSequence"] == 1,
                  "restart did not preserve state and advance epoch")
            successes.append(3)
            settled(workers, 3)
            states["node-3"] = workers[2].command("status")
            workers[2].finish(kill=True); finished.add(2)
            response = workers[0].command("add", id=2, value="one-follower-down")
            check(response["accepted"] and response["applicationSequence"] == 2, "one READY follower was not sufficient")
            successes.append(4)
            states["node-2"] = workers[1].command("status")
            workers[1].finish(kill=True); finished.add(1)
            response = workers[0].command("add", id=3, value="must-stay-invisible")
            check(not response["accepted"] and response["reason"] == "QUORUM_UNAVAILABLE", "no-quorum write succeeded")
            check(response["applicationSequence"] == 2 and response["documents"] == [
                {"id": 1, "value": "committed-document"}, {"id": 2, "value": "one-follower-down"}], "uncommitted state became visible")
            states["node-1"] = response
        for i, worker in enumerate(workers):
            if i not in finished:
                worker.finish(); finished.add(i)
        oracle = collect(case, states, successes)
        result = {"case": name, "status": "PASS", "threeConcurrentVoters": True, "oracle": oracle}
        save(case / "result.json", result)
        print(json.dumps(result, sort_keys=True), flush=True)
        return result
    finally:
        cleanup_errors = []
        for i, worker in enumerate(workers):
            if i not in finished:
                try:
                    worker.finish(kill=True)
                except Exception as error:
                    cleanup_errors.append(str(error))
        if cleanup_errors:
            save(case / "cleanup-errors.json", cleanup_errors)
            raise RuntimeError("worker cleanup failed: " + "; ".join(cleanup_errors))


def run(workspace):
    workspace.mkdir(parents=True, exist_ok=False)
    save(workspace / "source.json", {"sourceSha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
         "workingTreeDirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)), "paidCloud": False})
    results = [run_case(workspace)] + [run_case(workspace, barrier) for barrier in BARRIERS]
    save(workspace / "result.json", {"status": "PASS", "cases": results, "paidCloud": False})
    print(json.dumps({"v50Phase3LeaderPath": "PASS", "cases": len(results), "evidence": str(workspace)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    run(parser.parse_args().workspace)
