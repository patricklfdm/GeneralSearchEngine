#!/usr/bin/env python3
"""Separate-process V4.4 crash/fault protocol scaffold."""

from __future__ import annotations

import argparse
import hashlib
import json
import selectors
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.v44.evidence import (
    EvidenceError, base_document, validate_bundle, validate_source, write_bundle,
)

PROCESS_CLASS = (
    "io.github.patricklfdm.generalsearch.durability.harness."
    "V44FinalHardeningHarnessProcess"
)
BARRIER = "v44-phase1-model-publication-v1"
SEED = 440001
CASES = (
    "graceful-close", "runtime-halt", "external-kill", "startup-failure",
    "injected-io-failure", "malformed-bytes", "corrupt-bytes",
)


def _run(java: str, classpath: str, *arguments: str,
         timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run([java, "-cp", classpath, PROCESS_CLASS, *arguments],
                          check=False, capture_output=True, text=True,
                          timeout=timeout)


def _line(process: subprocess.Popen[str], timeout: float) -> str:
    assert process.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    ready = selector.select(timeout)
    selector.close()
    if not ready:
        process.kill()
        process.wait(timeout=5)
        raise EvidenceError("barrier acknowledgement timed out")
    value = process.stdout.readline().rstrip("\n")
    if not value:
        raise EvidenceError("writer exited before stable barrier")
    return value


def _inspect_model(path: Path, expected_sequence: int) -> str:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        pairs = dict(line.split("=", 1) for line in text.splitlines())
    except (OSError, UnicodeError, ValueError) as failure:
        raise EvidenceError("independent model inspection rejected bytes") from failure
    required = {"schema", "barrierId", "seed", "sequence",
                "canonicalAuthority", "productionStorage", "crc32c"}
    if set(pairs) != required:
        raise EvidenceError("independent model member inventory differs")
    body = "".join(f"{name}={pairs[name]}\n" for name in (
        "schema", "barrierId", "seed", "sequence",
        "canonicalAuthority", "productionStorage"))
    observed = 0xffffffff
    for byte in body.encode("utf-8"):
        observed ^= byte
        for _ in range(8):
            observed = (observed >> 1) ^ (0x82F63B78 if observed & 1 else 0)
    observed = (~observed) & 0xffffffff
    if pairs["schema"] != "gse-v44-phase1-model-v1" \
            or pairs["barrierId"] != BARRIER \
            or pairs["seed"] != str(SEED) \
            or pairs["sequence"] != str(expected_sequence) \
            or pairs["canonicalAuthority"] != "VALID" \
            or pairs["productionStorage"] != "false" \
            or not pairs["crc32c"].isdigit() \
            or observed != int(pairs["crc32c"]):
        raise EvidenceError("independent model semantics differ")
    return hashlib.sha256(raw).hexdigest()


def _valid_case(arguments: argparse.Namespace, store: Path) -> tuple[int, str, str]:
    mode = {"graceful-close": "writer-graceful",
            "runtime-halt": "writer-halt",
            "external-kill": "writer-wait"}[arguments.case]
    writer = subprocess.Popen(
        [arguments.java, "-cp", arguments.classpath, PROCESS_CLASS, mode,
         str(store), BARRIER, str(SEED)], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True)
    line = _line(writer, arguments.timeout)
    prefix = "GSE_V44_BARRIER_READY="
    if not line.startswith(prefix):
        writer.kill()
        raise EvidenceError("invalid barrier acknowledgement")
    acknowledgement = json.loads(line[len(prefix):])
    if acknowledgement != {"barrierId": BARRIER, "pid": writer.pid,
                            "seed": SEED, "sequence": 1}:
        writer.kill()
        raise EvidenceError("barrier identity differs")
    before = _inspect_model(store / "canonical.properties", 1)
    if arguments.case == "external-kill":
        interrupter = _run(arguments.java, arguments.classpath, "interrupt",
                           str(store), str(writer.pid), timeout=arguments.timeout)
        if interrupter.returncode != 0 or "GSE_V44_INTERRUPTER=PASS" \
                not in interrupter.stdout:
            writer.kill()
            raise EvidenceError("separate interrupter JVM failed")
    stdout, stderr = writer.communicate(timeout=arguments.timeout)
    expected_exit = {"graceful-close": 0, "runtime-halt": 89,
                     "external-kill": -9}[arguments.case]
    if writer.returncode != expected_exit:
        raise EvidenceError(f"unexpected writer exit: {writer.returncode}")
    marker = (store / "graceful-close.marker").exists()
    if marker != (arguments.case == "graceful-close"):
        raise EvidenceError("graceful-close distinction failed")
    inspect = _run(arguments.java, arguments.classpath, "inspect", str(store),
                   BARRIER, "1", timeout=arguments.timeout)
    recover = _run(arguments.java, arguments.classpath, "recover", str(store),
                   BARRIER, timeout=arguments.timeout)
    continuation = _run(arguments.java, arguments.classpath, "continue", str(store),
                        BARRIER, timeout=arguments.timeout)
    final_inspect = _run(arguments.java, arguments.classpath, "inspect", str(store),
                         BARRIER, "2", timeout=arguments.timeout)
    if any(item.returncode != 0 for item in
           (inspect, recover, continuation, final_inspect)):
        raise EvidenceError("inspector/recovery/continuation JVM failed")
    after = _inspect_model(store / "canonical.properties", 2)
    return writer.returncode, before + ":" + after, stderr + stdout


def run_case(arguments: argparse.Namespace) -> int:
    validate_source(arguments.source_sha)
    workspace = arguments.workspace.resolve()
    if workspace.exists():
        raise EvidenceError("workspace already exists")
    workspace.mkdir(parents=True)
    store = workspace / "store"
    lifecycle = ["writer-jvm-started"]
    exit_code = 0
    byte_identity = "NOT_APPLICABLE"
    logs = ""
    authority = "VALID"
    canonical_state = "VALID"
    continuation = False
    if arguments.case in {"graceful-close", "runtime-halt", "external-kill"}:
        exit_code, byte_identity, logs = _valid_case(arguments, store)
        lifecycle.extend(["stable-barrier-observed", "termination-observed",
                          "python-pre-open-inspection-passed",
                          "inspector-jvm-passed", "recovery-jvm-passed",
                          "continuation-jvm-passed", "second-inspection-passed"])
        continuation = True
    elif arguments.case == "startup-failure":
        result = _run(arguments.java, arguments.classpath, "startup-failure",
                      str(store), timeout=arguments.timeout)
        exit_code, logs = result.returncode, result.stderr
        if exit_code != 78 or store.exists():
            raise EvidenceError("startup failure did not fail before mutation")
        canonical_state = "ABSENT_EXPECTED"
        lifecycle.append("startup-failed-before-store-creation")
    elif arguments.case == "injected-io-failure":
        result = _run(arguments.java, arguments.classpath, "injected-io-failure",
                      str(store), timeout=arguments.timeout)
        exit_code, logs = result.returncode, result.stderr
        if exit_code != 74 or (store / "canonical.properties").exists() \
                or not (store / "canonical.properties.staging").is_file():
            raise EvidenceError("injected I/O failure publication boundary differs")
        canonical_state = "ABSENT_EXPECTED"
        lifecycle.append("injected-io-left-only-staging")
    else:
        result = _run(arguments.java, arguments.classpath, "writer-malformed",
                      str(store), BARRIER, timeout=arguments.timeout)
        exit_code, logs = result.returncode, result.stderr + result.stdout
        if exit_code != 89:
            raise EvidenceError("malformed writer did not halt")
        if arguments.case == "corrupt-bytes":
            path = store / "canonical.properties"
            path.write_bytes(path.read_bytes() + b"corrupt")
        try:
            _inspect_model(store / "canonical.properties", 1)
        except EvidenceError:
            authority = "INVALID"
            canonical_state = "INVALID_EXPECTED"
        else:
            raise EvidenceError("malformed/corrupt bytes were accepted")
        lifecycle.append("independent-inspector-failed-closed")
    shutil.rmtree(store, ignore_errors=True)
    evidence = base_document(arguments.source_sha, arguments.source_state,
                             "local-scaffold")
    evidence.update({
        "kind": "local-final-hardening-protocol",
        "case": {"caseId": arguments.case, "barrierId": BARRIER,
                 "seed": SEED},
        "configuration": {"productionChange": False, "paidExecution": False,
                          "productionStorage": False, "deadlineSeconds":
                              arguments.timeout},
        "authority": {"canonical": canonical_state,
                      "observedBeforeRecovery": authority,
                      "continued": continuation, "byteIdentity": byte_identity},
        "process": {"writerExitCode": exit_code, "separateJvmRoles":
                    ["writer", "interrupter", "inspector", "recovery",
                     "continuation"], "case": arguments.case},
        "lifecycle": lifecycle + ["workspace-cleaned"],
        "measurements": {"seed": SEED, "processDeadlineSeconds":
                         arguments.timeout},
        "cleanup": {"status": "PASS", "leftovers": []},
        "logs": {"stdoutTail": logs[-4096:], "stderrTail": "",
                 "limitBytesPerStream": 4096},
        "result": {"productionChange": False, "paidExecution": False,
                   "expectedBoundaryObserved": True},
    })
    write_bundle(workspace / "evidence", evidence)
    validate_bundle(workspace / "evidence")
    print(f"v44CrashHarness=PASS case={arguments.case}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--workspace", type=Path, required=True)
    run.add_argument("--source-sha", required=True)
    run.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    run.add_argument("--case", choices=CASES, required=True)
    run.add_argument("--java", default="java")
    run.add_argument("--classpath", default="target/test-classes:target/classes")
    run.add_argument("--timeout", type=float, default=15.0)
    validate = commands.add_parser("validate")
    validate.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "validate":
        value = validate_bundle(arguments.bundle)
        print(f"v44CrashEvidenceValidation=PASS case={value['case']['caseId']}")
        return 0
    return run_case(arguments)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, subprocess.SubprocessError,
            json.JSONDecodeError) as failure:
        print(f"v44CrashHarness=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
