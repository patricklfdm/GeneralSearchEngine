"""Production three-JVM fault plans, deterministic wire replay, pressure and repeated recovery."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import time
import uuid

from scripts.v50 import recovery_harness as recovery, wire_fixture as wire, storage_format as storage
from scripts.v50.deterministic_transport import DeterministicTransport
from scripts.v50.hardening_trace import validate as validate_trace
from scripts.v50.leader_harness import Worker, settled
from scripts.v50.storage_harness import ROOT, save, check

WORKER = "io.github.patricklfdm.generalsearch.replication.V50HardeningWorker"
RECOVERY_CUTS = ("AFTER_PROMISE_QUORUM", "AFTER_RECOVERY_SELECTION", "AFTER_RECOVERY_INSTALL",
                 "AFTER_RECOVERY_APPLICATION_PUBLICATION", "AFTER_RECOVERY_READY_QUORUM")
PRESSURE_CATCHUP_ATTEMPTS = 100
PRESSURE_CATCHUP_SECONDS = 10
PRESSURE_CATCHUP_BACKOFF = 0.05


class Group(recovery.Group):
    def start(self, index, armed=True):
        self.generations[index] += 1
        self.workers[index] = Worker(self.case / f"node-{index + 1}", index + 1, self.ports,
                                    self.barrier if armed and index == self.target else "", self.generations[index], worker_class=WORKER)

    def fault(self, kind, mode="drop-first", targets=(1, 2)):
        for index in targets:
            result = self.workers[index].command("fault", type=kind, mode=mode, barrier="BEFORE_RESPONSE_WRITE")
            check(result["accepted"], "fault plan admission failed")

    def heal(self):
        for worker in self.workers:
            if worker is not None: check(worker.command("heal")["accepted"], "fault release failed")

    def restart(self, label, before, kill=None):
        if kill is not None: self.stop(kill, kill=True)
        self.close()
        before.update({label + ":" + node: report for node, report in self.capture(label).items()})
        for index in range(3): self.start(index, armed=False)
        self.command("activate")
        self.command("catchup", peer="node-2"); self.command("catchup", peer="node-3")
        self.command("checkpoint")


def events(case):
    result = []
    for index in range(1, 4):
        file = case / f"node-{index}/network.jsonl"
        check(file.stat().st_size <= 64 * 1024 * 1024, "network evidence exceeds bound")
        result.extend(json.loads(line) for line in file.read_text().splitlines())
    return result


def finish(group, before, artifact, required=()):
    observed = {f"node-{index + 1}": worker.command("status") for index, worker in enumerate(group.workers)}
    group.close()
    reports = group.capture("final")
    expected = recovery.control(group.case, group.history, artifact)
    save(group.case / "observed-application.json", observed)
    oracle = recovery.validate(before, reports, observed, expected, group.acknowledged)
    save(group.case / "model-comparison.json", oracle)
    transcript = events(group.case)
    owners = set()
    for index in range(1, 4):
        for path in (group.case / f"node-{index}").glob("process-*.json"):
            record = json.loads(path.read_text()); owners.add((f"node-{index}", record["pid"]))
    check(all((event["node"], event["pid"]) in owners for event in transcript), "network transcript is not bound to an owned JVM")
    network = validate_trace(transcript, required_actions=required)
    save(group.case / "network-validation.json", network)
    result = {"case": group.case.name, "status": "PASS", "threeConcurrentVoters": True, "oracle": oracle, "network": network}
    save(group.case / "result.json", result)
    print(json.dumps({"case": group.case.name, "status": "PASS", "oracle": oracle}, sort_keys=True), flush=True)
    return result


def dropped_response(workspace, artifact, kind, suffix=""):
    group = Group(workspace / ("lost-" + kind.lower() + suffix))
    try:
        group.prepare(); group.fault(kind)
        if kind.startswith("SNAPSHOT_"): group.command("checkpoint")
        else: group.apply("add", id=20, value="shared")
        # Quiesce both outgoing FIFO streams before clearing the fault plan.
        group.command("catchup", peer="node-2"); group.command("catchup", peer="node-3")
        group.heal(); before = {}
        group.restart("pre-reopen", before)
        return finish(group, before, artifact, [(kind, "disconnect")])
    finally: group.close()


def exhausted_response(workspace, artifact, kind):
    group = Group(workspace / ("exhausted-" + kind.lower()))
    try:
        group.prepare(); initial = group.command("status"); group.fault(kind, "drop-all")
        rejected = group.workers[0].command("add", id=20, value="uncertain")
        check(not rejected["accepted"] and rejected["reason"] == "QUORUM_UNAVAILABLE", "lost ACKs manufactured a successful write")
        check(rejected["appliedIndex"] == initial["appliedIndex"] and not rejected["writeQuorum"], "failed quorum published application state")
        check(not group.workers[0].command("add", id=21, value="rejected")["accepted"], "unavailable leader admitted a later write")
        group.heal(); before = {}
        if kind == "COMMIT_PROOF":
            group.history.append({"command": "add", "id": 20, "value": "uncertain"})
            save(group.case / "indeterminate.json", {"originalSuccess": False, "retained": "valid durable proof"})
        group.restart("pre-reopen", before)
        return finish(group, before, artifact, [(kind, "disconnect")])
    finally: group.close()


def catchup_after_pressure(group, peer):
    """Re-admit catch-up after releasing pressure; permanent failures still fail."""
    attempts = []
    started = time.monotonic()
    deadline = started + PRESSURE_CATCHUP_SECONDS
    try:
        for _ in range(PRESSURE_CATCHUP_ATTEMPTS):
            if attempts and time.monotonic() >= deadline:
                break
            result = group.workers[0].command("catchup", peer=peer)
            attempts.append({"elapsedSeconds": time.monotonic() - started, "result": result})
            if result["accepted"]:
                return result
            check(result["reason"] == "CAPACITY_EXCEEDED", f"catchup failed after pressure release: {result}")
            check(result["state"] == "READY" and result["writeQuorum"],
                  f"capacity rejection changed leader availability: {result}")
            remaining = deadline - time.monotonic()
            if remaining <= 0 or len(attempts) == PRESSURE_CATCHUP_ATTEMPTS:
                break
            time.sleep(min(PRESSURE_CATCHUP_BACKOFF, remaining))
        raise AssertionError(f"catchup capacity did not recover after {len(attempts)} attempts: {attempts[-1]['result']}")
    finally:
        save(group.case / f"catchup-after-pressure-{peer}.json", {
            "peer": peer, "maximumAttempts": PRESSURE_CATCHUP_ATTEMPTS,
            "admissionWindowSeconds": PRESSURE_CATCHUP_SECONDS,
            "backoffSeconds": PRESSURE_CATCHUP_BACKOFF, "attempts": attempts})


def slow_follower(workspace, artifact):
    group = Group(workspace / "slow-follower-pressure")
    try:
        group.prepare(); initial = group.command("status"); group.fault("APPEND", "hold-first", (2,))
        for identity in range(20, 30): group.apply("add", id=identity, value="shared")
        lagging = group.workers[2].command("status")
        check(lagging["appliedIndex"] == initial["appliedIndex"], "held slow follower unexpectedly applied later state")
        # heal releases the follower's held response, not the leader's queued
        # exchanges. The eight in-flight slots can still be full at this point.
        group.heal(); catchup_after_pressure(group, "node-3")
        group.command("catchup", peer="node-2")
        before = {}; group.restart("pre-reopen", before)
        return finish(group, before, artifact, [("APPEND", "hold")])
    finally: group.close()


def exact_read(connection, count):
    chunks = bytearray()
    while len(chunks) < count:
        part = connection.recv(count - len(chunks))
        check(part, "incomplete raw response"); chunks.extend(part)
    return bytes(chunks)


def exchange(port, envelope):
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        connection.sendall(wire.encode(envelope))
        header = exact_read(connection, 48); length = struct.unpack_from(">I", header, 12)[0]
        check(length <= 1024 * 1024 - 48, "raw response exceeds frame bound")
        response = wire.inspect(header + exact_read(connection, length))
    check(all(response[field] == envelope[field] for field in ("groupId", "configurationId", "epoch", "incarnationId", "traceId", "eventSequence")), "uncorrelated raw replay response")
    check(response["sender"] == envelope["recipient"] and response["recipient"] == envelope["sender"], "wrong raw response voter")
    return response


def replay_wire(workspace, artifact):
    group = Group(workspace / "deterministic-wire-replay")
    try:
        group.prepare(); before_state = group.workers[1].command("status")
        requests = [event["request"] for event in events(group.case) if event["barrier"] == "BEFORE_REQUEST_WRITE"
                    and event["request"]["recipient"] == "node-2"]
        append = next(copy.deepcopy(request) for request in reversed(requests) if request["type"] == "APPEND")
        proof = next(copy.deepcopy(request) for request in reversed(requests) if request["type"] == "COMMIT_PROOF")
        stale = dict(append, incarnationId="99999999-9999-9999-9999-999999999999")
        conflicting = copy.deepcopy(append)
        frame = base64.b64decode(conflicting["payload"]["entry"]); body = bytearray(frame[48:]); body[-1] ^= 1
        body[117:149] = hashlib.sha256(body[149:]).digest()
        conflicting["payload"]["entry"] = base64.b64encode(storage.frame(5, body)).decode()
        # A distinct trace keeps this deliberate conflicting request separate from exact retries.
        conflicting["traceId"] = "77777777-7777-7777-7777-777777777777"
        stale["traceId"] = "88888888-8888-8888-8888-888888888888"
        schedule = DeterministicTransport("phase5-reordered-duplicate-stale-conflict-v1")
        for request, action, tick in [(append, "drop", 0), (append, "duplicate", 2), (proof, "duplicate", 1), (stale, "deliver", 3), (conflicting, "deliver", 4)]:
            schedule.message("node-1", "node-2", request["type"], request, action=action, delay_ticks=tick)
        raw = schedule.to_json(); (group.case / "schedule.json").write_text(raw + "\n")
        transcripts = []
        for repeat in (1, 2):
            restored = DeterministicTransport.from_json(raw)
            responses = []
            def receive(event):
                request = restored.payload(event); response = exchange(group.ports[1], request)
                responses.append({"request": request, "response": response})
                if response["type"] == "REJECT": raise ValueError(response["payload"]["reason"])
                return response["type"]
            transcript = restored.replay(receive)
            save(group.case / f"wire-responses-{repeat}.json", responses)
            save(group.case / f"replay-{repeat}.json", transcript); transcripts.append(transcript)
            check(group.workers[1].command("status") == before_state, "wire replay changed committed authority/application")
        check(transcripts[0] == transcripts[1], "deterministic replay outcomes changed")
        check([event["reason"] for event in transcripts[0] if event["outcome"] == "rejected"] == ["STALE_EPOCH", "CONFLICTING_HISTORY"], "wrong replay rejection reasons")
        before = {}; group.restart("pre-reopen", before)
        return finish(group, before, artifact)
    finally: group.close()


def repeated_recovery(workspace, artifact):
    group = Group(workspace / "repeated-crash-checkpoint-recovery")
    try:
        group.prepare(); before = {}; epochs = []
        for cycle in range(3):
            group.apply("add", id=20 + cycle, value="shared"); settled(group.workers, group.acknowledged)
            group.restart(f"cycle-{cycle}", before, kill=0)
            epochs.append(group.command("status")["epoch"])
        check(epochs == sorted(set(epochs)), "recovery epoch failed to advance")
        return finish(group, before, artifact)
    finally: group.close()


def cancellation_close(workspace, artifact):
    group = Group(workspace / "cancel-pressure-close-recovery", "AFTER_ENTRY_QUORUM")
    try:
        group.prepare(); group.command("arm")
        group.command("submit", token=1, id=20, value="uncertain")
        marker = recovery.wait_barrier(group, 0); save(group.case / "held-client.json", marker)
        for token in range(2, 9): group.command("submit", token=token, id=20 + token, value="queued")
        check(group.command("status")["pendingClients"] == 8, "pending client bound did not retain admitted work")
        group.command("cancel", token=1)
        group.command("submit", token=9, id=40, value="capacity-rejected")
        refused = group.workers[0].command("await", token=9)
        check(not refused["accepted"] and refused["reason"] == "CAPACITY_EXCEEDED", "cancellation prematurely released admission")
        before = {}; group.restart("pre-reopen", before)
        return finish(group, before, artifact)
    finally: group.close()


def recovery_crash(workspace, artifact, barrier):
    group = Group(workspace / ("recovery-" + barrier.lower()), barrier)
    try:
        group.prepare(); group.fault("APPEND", "drop-all")
        rejected = group.workers[0].command("add", id=20, value="unproven recovery suffix")
        check(not rejected["accepted"] and rejected["reason"] == "QUORUM_UNAVAILABLE", "recovery fixture unexpectedly committed")
        group.heal(); group.close()
        for index in range(3): group.start(index)
        group.command("arm"); group.workers[0].send("activate")
        marker = recovery.wait_barrier(group, 0)
        save(group.case / "crash.json", {"signal": "SIGKILL", "marker": marker, "activationSuccess": False})
        before = {}; group.restart("pre-reopen", before, kill=0)
        return finish(group, before, artifact)
    finally: group.close()


def run(workspace, artifact):
    artifact = artifact.resolve()
    check(hashlib.sha256(artifact.read_bytes()).hexdigest() == recovery.CONTROL_SHA, "published V4.4 checksum mismatch")
    workspace.mkdir(parents=True, exist_ok=False)
    save(workspace / "source.json", {"sourceSha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
         "gitStatus": subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True), "controlSha256": recovery.CONTROL_SHA, "paidCloud": False})
    cases = [dropped_response(workspace, artifact, kind) for kind in ("APPEND", "COMMIT_PROOF", "SNAPSHOT_CHUNK", "SNAPSHOT_INSTALL")]
    repeated = dropped_response(workspace, artifact, "APPEND", "-repeated")
    check(cases[0]["network"]["faults"] == repeated["network"]["faults"], "repeated named ACK-loss plan changed fault outcomes")
    cases.append(repeated)
    cases += [exhausted_response(workspace, artifact, kind) for kind in ("APPEND", "COMMIT_PROOF")]
    cases += [slow_follower(workspace, artifact), replay_wire(workspace, artifact), repeated_recovery(workspace, artifact), cancellation_close(workspace, artifact)]
    cases += [recovery_crash(workspace, artifact, barrier) for barrier in RECOVERY_CUTS]
    save(workspace / "result.json", {"status": "PASS", "cases": cases, "paidCloud": False})
    print(json.dumps({"v50Phase5Hardening": "PASS", "cases": len(cases), "evidence": str(workspace)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--control-jar", type=Path, required=True)
    args = parser.parse_args(); run(args.workspace, args.control_jar)
