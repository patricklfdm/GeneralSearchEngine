#!/usr/bin/env python3
"""Run and validate bounded V4.4 Phase 4 local hardening evidence."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.v44.evidence import (
    EvidenceError,
    base_document,
    validate_bundle,
    validate_source,
    write_bundle,
)

PROPERTY_SCHEMA = "gse-v44-local-hardening-properties-v1"
RESULT_KIND = "local-scale-hardening"
JAVA_MAIN = (
    "io.github.patricklfdm.generalsearch.engine."
    "V44FinalDurableLocalProbe"
)
STATIC = {
    "schemaVersion": PROPERTY_SCHEMA,
    "status": "PASS",
    "profile": "dense",
    "seed": "440001",
    "documents": "20000",
    "tokensPerDocument": "16",
    "keyBytes": "8",
    "valueBytes": "256",
    "indexes": "4",
    "mutations": "2000",
    "readers": "4",
    "writers": "1",
    "checkpointEveryMutations": "500",
    "backupEveryCheckpoints": "2",
    "migrationCount": "4",
    "pageCacheTreatment": "uncontrolled-local-page-cache",
    "gc": "G1",
}
INTEGER_KEYS = {
    "durationSeconds", "measurement.backups", "measurement.checkpoints",
    "measurement.concurrentNanos", "measurement.reads",
    "measurement.retainedBytes", "measurement.searches",
    "measurement.sequence", "measurement.totalNanos", "measurement.walBytes",
    "measurement.writes", "reopen.maximumNanos", "reopen.medianNanos",
    "resource.finalDirectoryBytes", "resource.gcCount",
    "resource.gcTimeMillis", "resource.heapMaximumBytes",
    "resource.heapUsedBytes", "resource.peakDirectoryBytes",
    "resource.processCpuNanos",
}
OTHER_KEYS = {
    "filesystem", "oracle.afterContinuation", "oracle.beforeClose",
    "reopen.samplesNanos",
}
ALL_KEYS = set(STATIC) | INTEGER_KEYS | OTHER_KEYS


def parse_properties(path: Path) -> dict[str, str]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as failure:
        raise EvidenceError("cannot read local hardening properties") from failure
    if len(content.encode("utf-8")) > 64 * 1024:
        raise EvidenceError("local hardening properties exceed 64 KiB")
    result: dict[str, str] = {}
    for number, line in enumerate(content.splitlines(), start=1):
        if not line or "=" not in line:
            raise EvidenceError(f"invalid property line: {number}")
        key, value = line.split("=", 1)
        if not key or not value or key in result:
            raise EvidenceError(f"duplicate or empty property: {number}")
        result[key] = value
    return result


def _integer(values: dict[str, str], key: str, *, positive: bool = False) -> int:
    try:
        value = int(values[key])
    except (KeyError, ValueError) as failure:
        raise EvidenceError(f"invalid integer property: {key}") from failure
    if value < 0 or positive and value == 0:
        raise EvidenceError(f"invalid numeric bound: {key}")
    return value


def _digest(values: dict[str, str], key: str) -> str:
    value = values.get(key, "")
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise EvidenceError(f"invalid semantic digest: {key}")
    return value


def validate_properties(values: dict[str, str]) -> dict[str, Any]:
    if set(values) != ALL_KEYS:
        raise EvidenceError("local hardening property inventory differs")
    for key, expected in STATIC.items():
        if values.get(key) != expected:
            raise EvidenceError(f"local hardening identity differs: {key}")
    if not values["filesystem"].endswith("-local-filesystem"):
        raise EvidenceError("filesystem declaration differs")
    numeric = {key: _integer(values, key) for key in INTEGER_KEYS}
    for key in (
        "durationSeconds", "measurement.concurrentNanos", "measurement.reads",
        "measurement.searches", "measurement.totalNanos",
        "measurement.retainedBytes", "measurement.writes",
        "reopen.maximumNanos", "reopen.medianNanos",
        "resource.finalDirectoryBytes", "resource.heapMaximumBytes",
        "resource.heapUsedBytes", "resource.peakDirectoryBytes",
        "resource.processCpuNanos",
    ):
        if numeric[key] == 0:
            raise EvidenceError(f"required measurement made no progress: {key}")
    if not 1 <= numeric["durationSeconds"] <= 180:
        raise EvidenceError("duration is outside frozen local bounds")
    if numeric["measurement.concurrentNanos"] \
            < numeric["durationSeconds"] * 1_000_000_000:
        raise EvidenceError("concurrent measurement ended too early")
    if (numeric["measurement.writes"], numeric["measurement.checkpoints"],
            numeric["measurement.backups"], numeric["measurement.sequence"]) \
            != (2_000, 4, 2, 2_020):
        raise EvidenceError("dense operation cadence differs")
    if numeric["resource.heapMaximumBytes"] > 1024 * 1024 * 1024:
        raise EvidenceError("heap exceeds the frozen one-GiB bound")
    if numeric["resource.heapUsedBytes"] > numeric["resource.heapMaximumBytes"]:
        raise EvidenceError("used heap exceeds maximum heap")
    if numeric["resource.peakDirectoryBytes"] \
            < numeric["resource.finalDirectoryBytes"]:
        raise EvidenceError("directory peak precedes final inventory")
    samples = [int(item) for item in values["reopen.samplesNanos"].split(",")]
    if len(samples) != 3 or any(sample <= 0 for sample in samples) \
            or samples != sorted(samples) \
            or numeric["reopen.medianNanos"] != samples[1] \
            or numeric["reopen.maximumNanos"] != samples[2]:
        raise EvidenceError("reopen distribution differs")
    before = _digest(values, "oracle.beforeClose")
    after = _digest(values, "oracle.afterContinuation")
    if before == after:
        raise EvidenceError("continued mutation did not change the oracle")
    return {"numeric": numeric, "before": before, "after": after,
            "samples": samples}


def run(arguments: argparse.Namespace) -> int:
    source = validate_source(arguments.source_sha)
    workspace = arguments.workspace.resolve()
    if workspace.exists():
        raise EvidenceError("local hardening workspace already exists")
    workspace.mkdir(parents=True)
    probe = workspace / "probe"
    command = [
        arguments.java, "-Xms1g", "-Xmx1g", "-XX:+UseG1GC",
        "-cp", arguments.classpath, JAVA_MAIN, str(probe),
        str(arguments.duration_seconds),
    ]
    completed = subprocess.run(
        command, check=False, capture_output=True, text=True,
        timeout=arguments.timeout_seconds,
    )
    if completed.returncode != 0:
        raise EvidenceError(
            f"local hardening probe exited with {completed.returncode}: "
            f"{completed.stderr[-4096:]}")
    values = parse_properties(probe / "performance.properties")
    checked = validate_properties(values)
    shutil.rmtree(probe)
    if probe.exists():
        raise EvidenceError("local probe cleanup failed")

    evidence = base_document(source, arguments.source_state, "local-scaffold")
    numeric = checked["numeric"]
    evidence.update({
        "kind": RESULT_KIND,
        "case": {"caseId": "phase4-dense-local-hardening", "seed": 440001,
                 "validAuthority": True, "continuationRequired": True},
        "configuration": {
            "productionChange": False, "paidExecution": False,
            "documents": 20_000, "tokensPerDocument": 16,
            "keyBytes": 8, "valueBytes": 256, "indexes": 4,
            "mutations": 2_000, "readers": 4, "writers": 1,
            "checkpointEveryMutations": 500,
            "backupEveryCheckpoints": 2, "migrationCount": 4,
            "durationSeconds": arguments.duration_seconds,
            "heapMiB": 1024, "gc": "G1",
            "pageCacheTreatment": values["pageCacheTreatment"],
        },
        "authority": {"canonical": "VALID", "derived": "VALID_OR_FALLBACK",
                      "semanticDigestBefore": checked["before"],
                      "semanticDigestAfterContinuation": checked["after"]},
        "process": {
            "provider": "local-process", "python": platform.python_version(),
            "platform": platform.platform(), "filesystem": values["filesystem"],
            "externalDeadlineSeconds": arguments.timeout_seconds,
            "reopenSamplesNanos": checked["samples"],
        },
        "lifecycle": [
            "dense-corpus-created", "concurrent-readers-started",
            "mutations-checkpoints-backups-completed", "semantic-oracle-verified",
            "three-reopens-verified", "continued-mutation-checkpointed",
            "second-reopen-verified", "probe-cleaned", "evidence-written",
        ],
        "measurements": numeric,
        "cleanup": {"status": "PASS", "leftovers": []},
        "logs": {"stdoutTail": completed.stdout[-4096:],
                 "stderrTail": completed.stderr[-4096:],
                 "limitBytesPerStream": 4096},
        "result": {
            "productionChange": False, "paidExecution": False,
            "expectedBoundaryObserved": False,
            "phase4Status": "PASS_NO_MEASURED_REGRESSION",
            "admittedOptimization": False,
            "classification": None,
        },
    })
    write_bundle(workspace / "evidence", evidence)
    validate_evidence(workspace / "evidence")
    print("v44LocalHardeningEvidence=PASS documents=20000 mutations=2000 "
          "readers=4 checkpoints=4 backups=2 optimization=false")
    return 0


def validate_evidence(directory: Path) -> dict[str, Any]:
    document = validate_bundle(directory)
    if document["kind"] != RESULT_KIND \
            or document["result"].get("phase4Status") \
            != "PASS_NO_MEASURED_REGRESSION" \
            or document["result"].get("admittedOptimization") is not False \
            or document["result"].get("classification") is not None \
            or document["configuration"].get("productionChange") is not False \
            or document["configuration"].get("paidExecution") is not False:
        raise EvidenceError("Phase 4 evidence decision differs")
    if document["measurements"].get("measurement.writes") != 2_000 \
            or document["measurements"].get("measurement.sequence") != 2_020:
        raise EvidenceError("Phase 4 evidence cadence differs")
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--workspace", type=Path, required=True)
    execute.add_argument("--source-sha", required=True)
    execute.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    execute.add_argument("--duration-seconds", type=int, default=2)
    execute.add_argument("--timeout-seconds", type=int, default=240)
    execute.add_argument("--java", default="java")
    execute.add_argument("--classpath", default="target/benchmarks.jar")
    verify = commands.add_parser("validate")
    verify.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "run":
        return run(arguments)
    document = validate_evidence(arguments.bundle.resolve())
    print("v44LocalHardeningValidation=PASS "
          f"writes={document['measurements']['measurement.writes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, ValueError,
            subprocess.SubprocessError) as failure:
        print(f"v44LocalHardening=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
