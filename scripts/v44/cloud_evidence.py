#!/usr/bin/env python3
"""Assemble and validate V4.4 final-durable replacement-host evidence."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from scripts.v43.derived_format_v12 import inspect_backup_directory
from scripts.v43.fast_reopen_performance import parse_properties, validate_properties
from scripts.v44.cloud_workflow import RESOURCES
from scripts.v44.evidence import (
    EvidenceError,
    base_document,
    sha256,
    validate_bundle,
    validate_source,
    write_bundle,
)

KIND = "v44-final-durable-replacement-host"
PAIRED = re.compile(
    r"v44PairedControl=PASS label=([a-z0-9-]{1,32}) documents=([0-9]+) "
    r"indexes=4 writeNanos=([0-9]+) reopenMedianNanos=([0-9]+) "
    r"semanticDigest=([0-9a-f]{64})\n?"
)


def parse_paired(path: Path, expected_label: str) -> dict[str, Any]:
    try:
        value = path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as failure:
        raise EvidenceError("cannot read paired control") from failure
    match = PAIRED.fullmatch(value)
    if match is None or match.group(1) != expected_label:
        raise EvidenceError("paired control output differs")
    documents, write, reopen = (int(match.group(index)) for index in (2, 3, 4))
    if documents != 20_000 or write <= 0 or reopen <= 0:
        raise EvidenceError("paired control measurement differs")
    return {"label": expected_label, "documents": documents,
            "writeNanos": write, "reopenMedianNanos": reopen,
            "semanticDigest": match.group(5)}


def _ratio(current: int, published: int) -> int:
    return round(current * 1_000_000 / published)


def build_document(
    *, source_sha: str, source_state: str, profile: str, slot: int,
    duration_seconds: int, published42: dict[str, str],
    source: dict[str, str], replacement: dict[str, str],
    inspection: dict[str, object], published43: dict[str, Any],
    current: dict[str, Any], cleanup: dict[str, Any],
    stdout: str, stderr: str,
) -> dict[str, Any]:
    validate_source(source_sha)
    maximum_slot = 3 if profile == "canonical" else 1
    if profile not in {"experiment", "canonical", "failure-drill"} \
            or not 1 <= slot <= maximum_slot or duration_seconds != 3_600:
        raise EvidenceError("V4.4 member identity differs")
    inherited = validate_properties(
        published42, source, replacement, "production", duration_seconds)
    if inspection.get("status") != "VALID" \
            or inspection.get("sequence") != int(source["backup.sequence"]) \
            or inspection.get("contentIdentity") != source["backup.contentIdentity"]:
        raise EvidenceError("independent backup inspection differs")
    if published43.get("label") != "published-4-3" \
            or current.get("label") != "current-source" \
            or published43.get("documents") != 20_000 \
            or current.get("documents") != 20_000 \
            or published43.get("semanticDigest") != current.get("semanticDigest"):
        raise EvidenceError("paired published-4.3 semantic control differs")
    write_ratio = _ratio(current["writeNanos"], published43["writeNanos"])
    reopen_ratio = _ratio(
        current["reopenMedianNanos"], published43["reopenMedianNanos"])
    if profile == "canonical" and max(write_ratio, reopen_ratio) \
            > RESOURCES["lowerMemberMaximumRatioMicros"]:
        raise EvidenceError("canonical member exceeds paired 1.35 threshold")
    if cleanup != {
            "status": "PASS", "leftovers": [], "sourceVmDeleted": True,
            "replacementVmDeleted": True, "dataDiskDeleted": True,
            "targetDiskDeleted": True, "stagingObjectsDeleted": True}:
        raise EvidenceError("cloud cleanup proof differs")
    document = base_document(source_sha, source_state, profile)
    document.update({
        "kind": KIND,
        "case": {"caseId": f"final-durable-member-{slot}", "slot": slot,
                 "serial": True, "replacementHost": True,
                 "matrixFamilies": 10},
        "configuration": {
            "productionChange": False, "paidExecution": True,
            "documents": 100_000, "mutations": 10_000, "indexes": 4,
            "durationSeconds": 3_600, "machineType": "c3d-standard-30",
            "dataDiskGiB": 200, "targetDiskGiB": 200,
            "publishedControl": "4.3.0",
            "pageCacheTreatment": "warm-and-explicit-cold-control-reported-separately",
        },
        "authority": {
            "canonical": "VALID", "derived": "VALID_OR_FALLBACK",
            "backupInspection": "PASS", "canonicalBytesUnchanged": True,
            "oracleChecksum": inherited["oracle"],
            "continuedChecksum": replacement["wal.checksum"],
            "backupContentIdentity": source["backup.contentIdentity"],
            "published43SemanticDigest": published43["semanticDigest"],
        },
        "process": {
            "provider": "gcp", "sourceHostDeleted": True,
            "replacementHost": True, "javaProfile": "production",
            "published43WriteNanos": published43["writeNanos"],
            "currentWriteNanos": current["writeNanos"],
            "published43ReopenMedianNanos": published43["reopenMedianNanos"],
            "currentReopenMedianNanos": current["reopenMedianNanos"],
            "writeRatioMicros": write_ratio,
            "reopenRatioMicros": reopen_ratio,
            "inheritedWarmRatioMicros": inherited["ratioMicros"],
        },
        "lifecycle": [
            "exact-source-and-controls-validated", "source-host-created",
            "canonical-authority-and-backup-created",
            "published-4.3-paired-control-recorded", "source-host-deleted",
            "replacement-host-created", "pre-open-inspection-passed",
            "restore-migration-fallback-and-wal-continuation-proved",
            "3600-second-measurement-completed", "all-resources-cleaned",
        ],
        "measurements": {
            "measurementSeconds": int(replacement["measurementSeconds"]),
            "measurementReads": int(replacement["measurement.reads"]),
            "measurementReadsPerSecondMicros":
                int(replacement["measurement.readsPerSecondMicros"]),
            "sourceCanonicalBytes": int(source["source.canonicalBytes"]),
            "sourceDerivedBytes": int(source["source.derivedBytes"]),
            "sourceDirectoryBytes": int(source["source.directoryBytes"]),
            "sourceTemporaryPeakBytes": int(source["source.temporaryPeakBytes"]),
            "replacementCanonicalBytes":
                int(replacement["replacement.canonicalBytes"]),
            "replacementDerivedBytes": int(replacement["replacement.derivedBytes"]),
            "replacementDirectoryBytes":
                int(replacement["replacement.directoryBytes"]),
            "sourceHeapUsedBytes": int(source["source.heapUsedBytes"]),
            "replacementHeapUsedBytes":
                int(replacement["replacement.heapUsedBytes"]),
            "writeRatioMicros": write_ratio,
            "reopenRatioMicros": reopen_ratio,
        },
        "cleanup": cleanup,
        "logs": {"stdoutTail": stdout.encode("utf-8", errors="replace")[-16_384:]
                 .decode("utf-8", errors="replace"),
                 "stderrTail": stderr.encode("utf-8", errors="replace")[-16_384:]
                 .decode("utf-8", errors="replace"),
                 "limitBytesPerStream": 16_384},
        "result": {
            "productionChange": False, "paidExecution": True,
            "expectedBoundaryObserved": False,
            "replacementHostProven": True, "allTenFamilies": "PASS",
            "pairedPublished43": "PASS", "memberThresholdApplies":
                profile == "canonical",
            "lowerMemberMaximumRatioMicros": 1_350_000,
            "cleanup": "PASS",
        },
    })
    return document


def validate_evidence(path: Path) -> dict[str, Any]:
    document = validate_bundle(path)
    if document.get("kind") != KIND or document.get("status") != "PASS" \
            or document["case"].get("matrixFamilies") != 10 \
            or document["process"].get("provider") != "gcp" \
            or document["process"].get("sourceHostDeleted") is not True \
            or document["result"].get("replacementHostProven") is not True \
            or document["result"].get("pairedPublished43") != "PASS" \
            or document["result"].get("allTenFamilies") != "PASS" \
            or document["measurements"].get("measurementSeconds") != 3_600:
        raise EvidenceError("V4.4 cloud evidence shape differs")
    profile = document["profile"]
    slot = document["case"].get("slot")
    maximum_slot = 3 if profile == "canonical" else 1
    if type(slot) is not int or not 1 <= slot <= maximum_slot:
        raise EvidenceError("V4.4 cloud evidence slot differs")
    for key in ("writeRatioMicros", "reopenRatioMicros"):
        value = document["measurements"].get(key)
        if type(value) is not int or value <= 0 \
                or profile == "canonical" and value > 1_350_000:
            raise EvidenceError("V4.4 paired member ratio differs")
    identity = document["authority"].get("backupContentIdentity", "")
    if not identity.startswith("gse-backup-v3-") or len(identity) != 78:
        raise EvidenceError("V4.4 backup identity differs")
    return document


def assemble(arguments: argparse.Namespace) -> int:
    cleanup = {
        "status": "PASS", "leftovers": [],
        "sourceVmDeleted": arguments.source_vm_deleted,
        "replacementVmDeleted": arguments.replacement_vm_deleted,
        "dataDiskDeleted": arguments.data_disk_deleted,
        "targetDiskDeleted": arguments.target_disk_deleted,
        "stagingObjectsDeleted": arguments.staging_object_deleted,
    }
    inspection = inspect_backup_directory(arguments.backup)
    stdout = arguments.stdout_log.read_text("utf-8", errors="replace") \
        if arguments.stdout_log else ""
    stderr = arguments.stderr_log.read_text("utf-8", errors="replace") \
        if arguments.stderr_log else ""
    document = build_document(
        source_sha=arguments.source_sha, source_state=arguments.source_state,
        profile=arguments.profile, slot=arguments.slot,
        duration_seconds=arguments.duration_seconds,
        published42=parse_properties(arguments.published42_properties),
        source=parse_properties(arguments.source_properties),
        replacement=parse_properties(arguments.replacement_properties),
        inspection=inspection,
        published43=parse_paired(arguments.published43_output, "published-4-3"),
        current=parse_paired(arguments.current_output, "current-source"),
        cleanup=cleanup, stdout=stdout, stderr=stderr)
    write_bundle(arguments.output, document)
    validate_evidence(arguments.output)
    print(f"v44CloudEvidence=PASS profile={arguments.profile} slot={arguments.slot}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    assembly = commands.add_parser("assemble")
    assembly.add_argument("--source-sha", required=True)
    assembly.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    assembly.add_argument("--profile", choices=("experiment", "canonical", "failure-drill"), required=True)
    assembly.add_argument("--slot", type=int, required=True)
    assembly.add_argument("--duration-seconds", type=int, required=True)
    for name in ("published42-properties", "source-properties",
                 "replacement-properties", "published43-output",
                 "current-output", "backup", "output"):
        assembly.add_argument(f"--{name}", type=Path, required=True)
    assembly.add_argument("--stdout-log", type=Path)
    assembly.add_argument("--stderr-log", type=Path)
    for flag in ("source-vm-deleted", "replacement-vm-deleted",
                 "data-disk-deleted", "target-disk-deleted",
                 "staging-object-deleted"):
        assembly.add_argument(f"--{flag}", action="store_true")
    validation = commands.add_parser("validate")
    validation.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "assemble":
        return assemble(arguments)
    value = validate_evidence(arguments.bundle)
    print(f"v44CloudEvidenceValidation=PASS profile={value['profile']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, ValueError) as failure:
        print(f"v44CloudEvidence=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
