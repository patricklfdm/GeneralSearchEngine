#!/usr/bin/env python3
"""Run, assemble, and validate V4.1 operational source-loss evidence."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from scripts.v41.backup_format import BackupFormatError, inspect_bundle
from scripts.v41.evidence import EvidenceError, validate_bundle, validate_source, write_bundle
from scripts.v41.fake_cloud_lane import PLAN

JAVA_MAIN = (
    "io.github.patricklfdm.generalsearch.engine."
    "V41OperationalEvidenceProbe"
)
PROPERTIES_SCHEMA = "gse-v41-operational-properties-v1"
LOG_LIMIT = 16 * 1024
EXPECTED = {
    "smoke": {"documents": 1_000, "preBackupMutations": 100,
              "continuedMutations": 20},
    "production": {"documents": 100_000, "preBackupMutations": 10_000,
                   "continuedMutations": 1_000},
}


def parse_properties(path: Path) -> dict[str, str]:
    try:
        data = path.read_bytes()
    except OSError as failure:
        raise EvidenceError(f"cannot read properties: {path}") from failure
    if len(data) > 1024 * 1024:
        raise EvidenceError("operational properties exceed one MiB")
    try:
        lines = data.decode("utf-8", errors="strict").splitlines()
    except UnicodeError as failure:
        raise EvidenceError("operational properties are not UTF-8") from failure
    result: dict[str, str] = {}
    for number, line in enumerate(lines, start=1):
        if not line or "=" not in line:
            raise EvidenceError(f"invalid property line {number}")
        key, value = line.split("=", 1)
        if not key or not value or key in result:
            raise EvidenceError(f"duplicate or empty property line {number}")
        result[key] = value
    return result


def integer(properties: dict[str, str], key: str, *, positive: bool = False) -> int:
    try:
        value = int(properties[key])
    except (KeyError, ValueError) as failure:
        raise EvidenceError(f"missing or invalid integer property: {key}") from failure
    if positive and value <= 0:
        raise EvidenceError(f"property must be positive: {key}")
    return value


def validate_properties(
    source: dict[str, str],
    restore: dict[str, str],
    expected_profile: str,
    duration_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if expected_profile not in EXPECTED:
        raise EvidenceError("unsupported operational Java profile")
    expected = EXPECTED[expected_profile]
    common = {
        "schemaVersion": PROPERTIES_SCHEMA,
        "status": "PASS",
        "profile": expected_profile,
        "documents": str(expected["documents"]),
        "tokensPerDocument": "16",
        "preBackupMutations": str(expected["preBackupMutations"]),
        "continuedMutations": str(expected["continuedMutations"]),
        "measurementSeconds": str(duration_seconds),
        "codecId": "v41-operational-codec-v1",
        "codecVersion": "1",
        "storageIdentity": "v41-operational-store-v1",
        "schemaIdentity": "v41-operational-schema-v1",
    }
    for properties, stage in ((source, "source"), (restore, "restore")):
        for key, value in common.items():
            if properties.get(key) != value:
                raise EvidenceError(f"{stage} property differs: {key}")
        if properties.get("stage") != stage:
            raise EvidenceError(f"invalid operational stage: {stage}")
        for key in ("processCpuNanosAtStart", "processCpuNanosAtEnd"):
            integer(properties, key)

    for key in (
        "backup.elapsedNanos", "backup.totalBytes", "backup.peakObservedBytes",
        "backup.semanticDocuments", "source.loadNanos",
        "source.preBackupMutationNanos", "source.afterCutMutationNanos",
        "source.impactReads", "source.impactWrites", "source.impactReadNanos",
        "source.bytesBeforeBackup", "source.retainedBytes",
        "source.heapUsedBytes", "source.totalNanos",
    ):
        integer(source, key, positive=True)
    if source.get("backup.status") != "PASS" \
            or source.get("backup.structuralStatus") != "VALID" \
            or source.get("backup.semanticStatus") != "SEMANTICALLY_VALID":
        raise EvidenceError("source backup verification did not pass")
    if integer(source, "backup.semanticDocuments") != expected["documents"]:
        raise EvidenceError("source semantic document count differs")
    if integer(source, "backup.peakObservedBytes") \
            < integer(source, "source.bytesBeforeBackup"):
        raise EvidenceError("backup peak bytes precede the synchronous baseline")
    backup_sequence = integer(source, "backup.sequence", positive=True)
    if integer(source, "source.afterCutSequence") != backup_sequence + 1:
        raise EvidenceError("post-cut mutation sequence is not exact")
    identity = source.get("backup.contentIdentity", "")
    if not identity.startswith("gse-backup-v1-") or len(identity) != 78:
        raise EvidenceError("backup content identity is invalid")

    for key in (
        "verification.elapsedNanos", "verification.semanticDocuments",
        "restore.elapsedNanos", "restore.authoritativeBytes",
        "restore.firstOpenNanos", "restore.continuedMutationNanos",
        "restore.checkpointNanos", "restore.retainedBytes", "restore.heapUsedBytes",
        "restore.secondOpenNanos", "restore.finalDirectoryBytes",
        "measurement.reads", "measurement.durationNanos",
        "measurement.readsPerSecondMicros",
    ):
        integer(restore, key, positive=True)
    if restore.get("verification.structuralStatus") != "VALID" \
            or restore.get("verification.semanticStatus") != "SEMANTICALLY_VALID":
        raise EvidenceError("replacement-host verification did not pass")
    if integer(restore, "verification.semanticDocuments") != expected["documents"]:
        raise EvidenceError("restore semantic document count differs")
    if integer(restore, "restore.sequence") != backup_sequence:
        raise EvidenceError("restore sequence differs from backup cut")
    if integer(restore, "restore.finalSequence") != backup_sequence + 1:
        raise EvidenceError("continued mutation sequence is not exact")
    cut_checksum = source.get("oracle.cutChecksum", "")
    continued_checksum = restore.get("oracle.continuedChecksum", "")
    if len(cut_checksum) != 64 \
            or any(character not in "0123456789abcdef" for character in cut_checksum) \
            or len(continued_checksum) != 64 \
            or any(character not in "0123456789abcdef"
                   for character in continued_checksum) \
            or cut_checksum != restore.get("oracle.restoredChecksum"):
        raise EvidenceError("full restored-state oracle differs")
    if source.get("backup.sourceHistory") != restore.get("restore.sourceHistory"):
        raise EvidenceError("source-history provenance differs")
    if restore.get("restore.sourceHistory") == restore.get("restore.newHistory"):
        raise EvidenceError("restore did not create a new history")
    actual_duration = integer(restore, "measurement.durationNanos", positive=True)
    minimum_duration = duration_seconds * 1_000_000_000
    maximum_duration = (duration_seconds + 60) * 1_000_000_000
    if not minimum_duration <= actual_duration <= maximum_duration:
        raise EvidenceError("measurement duration differs")

    source_metrics: dict[str, Any] = {
        "loadNanos": integer(source, "source.loadNanos"),
        "preBackupMutationNanos": integer(source, "source.preBackupMutationNanos"),
        "afterCutMutationNanos": integer(source, "source.afterCutMutationNanos"),
        "impactReads": integer(source, "source.impactReads"),
        "impactWrites": integer(source, "source.impactWrites"),
        "impactReadNanos": integer(source, "source.impactReadNanos"),
        "bytesBeforeBackup": integer(source, "source.bytesBeforeBackup"),
        "retainedBytes": integer(source, "source.retainedBytes"),
        "heapUsedBytes": integer(source, "source.heapUsedBytes"),
        "totalNanos": integer(source, "source.totalNanos"),
    }
    restore_metrics: dict[str, Any] = {
        "semanticVerificationNanos": integer(restore, "verification.elapsedNanos"),
        "restoreNanos": integer(restore, "restore.elapsedNanos"),
        "firstOpenNanos": integer(restore, "restore.firstOpenNanos"),
        "continuedMutationNanos": integer(restore, "restore.continuedMutationNanos"),
        "checkpointNanos": integer(restore, "restore.checkpointNanos"),
        "secondOpenNanos": integer(restore, "restore.secondOpenNanos"),
        "retainedBytes": integer(restore, "restore.retainedBytes"),
        "heapUsedBytes": integer(restore, "restore.heapUsedBytes"),
        "finalDirectoryBytes": integer(restore, "restore.finalDirectoryBytes"),
        "measurementReads": integer(restore, "measurement.reads"),
        "measurementDurationNanos": integer(restore, "measurement.durationNanos"),
        "readsPerSecondMicros": integer(
            restore, "measurement.readsPerSecondMicros"),
    }
    return source_metrics, restore_metrics


def tail(value: str) -> str:
    encoded = value.encode("utf-8", errors="replace")
    return encoded[-LOG_LIMIT:].decode("utf-8", errors="replace")


def build_document(
    *,
    source_sha: str,
    source_state: str,
    evidence_profile: str,
    java_profile: str,
    duration_seconds: int,
    slot: int,
    source: dict[str, str],
    restore: dict[str, str],
    inspection: dict[str, object],
    provider: str,
    source_vm_deleted: bool,
    source_disk_deleted: bool,
    replacement_vm_deleted: bool,
    restore_disk_deleted: bool,
    staging_object_deleted: bool,
    stdout: str,
    stderr: str,
) -> dict[str, Any]:
    validate_source(source_sha)
    if evidence_profile not in {"local-scaffold", "experiment", "canonical",
                                "failure-drill"}:
        raise EvidenceError("invalid operational evidence profile")
    if slot <= 0:
        raise EvidenceError("slot must be positive")
    source_metrics, restore_metrics = validate_properties(
        source, restore, java_profile, duration_seconds)
    if inspection.get("status") != "VALID" \
            or inspection.get("contentIdentity") != source["backup.contentIdentity"] \
            or inspection.get("sequence") != int(source["backup.sequence"]):
        raise EvidenceError("independent backup inspection differs")
    if provider == "gcp":
        cleanup_values: dict[str, Any] = {
            "sourceVmDeleted": source_vm_deleted,
            "sourceDiskDeleted": source_disk_deleted,
            "replacementVmDeleted": replacement_vm_deleted,
            "restoreDiskDeleted": restore_disk_deleted,
            "stagingObjectDeleted": staging_object_deleted,
        }
        if not all(cleanup_values.values()):
            raise EvidenceError("cloud source-loss evidence requires complete cleanup")
    else:
        cleanup_values = {
            "sourceVmDeleted": "NOT_APPLICABLE",
            "sourceDiskDeleted": "NOT_APPLICABLE",
            "replacementVmDeleted": "NOT_APPLICABLE",
            "restoreDiskDeleted": "NOT_APPLICABLE",
            "stagingObjectDeleted": "NOT_APPLICABLE",
            "localSourceStoreDeleted": True,
            "localRestoreStoreDeleted": True,
            "localArtifactsRemoved": True,
        }
    configuration = dict(PLAN)
    configuration.update({
        "javaProfile": java_profile,
        "durationSeconds": duration_seconds,
        "measurementSeconds": duration_seconds,
        "slot": slot,
    })
    if provider == "gcp":
        lifecycle = [
            "exact-source-validated", "source-disk-created", "source-vm-created",
            "source-store-mutated", "backup-cut-selected",
            "backup-structurally-verified", "bundle-uploaded",
            "source-vm-deleted", "source-disk-deleted",
            "source-unavailable-proven", "restore-disk-created",
            "replacement-vm-created", "bundle-downloaded",
            "independent-byte-verification-passed", "new-history-restore-passed",
            "full-oracle-passed", "continued-mutation-passed",
            "checkpoint-passed", "second-reopen-passed", "evidence-retained",
            "replacement-vm-deleted", "restore-disk-deleted",
            "staging-object-deleted", "cleanup-verified",
        ]
    else:
        lifecycle = [
            "exact-source-validated", "local-source-store-created",
            "source-store-mutated", "backup-cut-selected",
            "backup-structurally-verified", "local-source-store-deleted",
            "local-source-unavailable-proven",
            "independent-byte-verification-passed", "local-restore-store-created",
            "new-history-restore-passed", "full-oracle-passed",
            "continued-mutation-passed", "checkpoint-passed",
            "second-reopen-passed", "local-artifacts-removed",
            "evidence-retained", "cleanup-verified",
        ]
    return {
        "schemaVersion": "gse-v41-operational-evidence-v1",
        "kind": "v41-source-loss-replacement-host",
        "status": "PASS",
        "sourceCommit": source_sha,
        "sourceState": source_state,
        "suite": "v4.1-operational-safety-suite-v1",
        "preset": "v4.1-operational-safety-v1",
        "profile": evidence_profile,
        "case": {
            "caseId": f"source-loss-member-{slot}",
            "slot": slot,
            "sourceLoss": True,
            "replacementHost": provider == "gcp",
        },
        "configuration": configuration,
        "backup": {
            "status": "PASS",
            "format": inspection["format"],
            "sequence": inspection["sequence"],
            "contentIdentity": inspection["contentIdentity"],
            "sourceHistory": inspection["sourceHistory"],
            "authoritativeBytes": inspection["authoritativeBytes"],
            "elapsedNanos": int(source["backup.elapsedNanos"]),
            "peakObservedBytes": int(source["backup.peakObservedBytes"]),
            "sourceMetrics": source_metrics,
            "transport": "GCS" if provider == "gcp" else "LOCAL_COPY",
        },
        "verification": {
            "status": "PASS",
            "parser": "independent-python-v1",
            "structural": source["backup.structuralStatus"],
            "semantic": restore["verification.semanticStatus"],
            "documentCount": int(restore["verification.semanticDocuments"]),
        },
        "restore": {
            "status": "PASS",
            "sourceHistory": restore["restore.sourceHistory"],
            "newHistory": restore["restore.newHistory"],
            "sequence": int(restore["restore.sequence"]),
            "finalSequence": int(restore["restore.finalSequence"]),
            "fullOracle": "PASS",
            "postCutExcluded": True,
            "continuedMutation": "PASS",
            "checkpoint": "PASS",
            "secondReopen": "PASS",
            "metrics": restore_metrics,
        },
        "process": {
            "provider": provider,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "pid": os.getpid(),
            "sourceVmDistinctFromReplacement": provider == "gcp",
        },
        "lifecycle": lifecycle,
        "cleanup": {
            "status": "PASS",
            "leftovers": [],
            **cleanup_values,
        },
        "logs": {
            "stdoutTail": tail(stdout),
            "stderrTail": tail(stderr),
            "limitBytesPerStream": LOG_LIMIT,
        },
        "result": {
            "sourceLossProven": True,
            "replacementHostProven": provider == "gcp",
            "fullOracle": "PASS",
            "cleanup": "PASS",
            "eligibleForCanonicalRegistration": (
                provider == "gcp" and evidence_profile == "canonical"
            ),
        },
    }


def run_java(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command, check=False, capture_output=True, text=True, timeout=timeout)
    if completed.returncode != 0:
        raise EvidenceError(
            f"operational Java stage exited with {completed.returncode}: "
            f"{tail(completed.stderr)}")
    return completed


def run_local(arguments: argparse.Namespace) -> int:
    validate_source(arguments.source_sha)
    workspace = arguments.workspace.resolve()
    if workspace.exists():
        raise EvidenceError("operational workspace already exists")
    workspace.mkdir(parents=True)
    source_store = workspace / "source-store"
    backup = workspace / "backup"
    source_properties = workspace / "source.properties"
    restore_store = workspace / "restore-store"
    restore_properties = workspace / "restore.properties"
    log_out = ""
    log_err = ""
    started = time.monotonic()
    source_run = run_java([
        arguments.java, "-cp", arguments.classpath, JAVA_MAIN, "source",
        arguments.java_profile, str(source_store), str(backup),
        str(source_properties), str(arguments.duration_seconds),
    ], arguments.timeout_seconds)
    log_out += source_run.stdout
    log_err += source_run.stderr
    inspection = inspect_bundle(backup)
    shutil.rmtree(source_store)
    if source_store.exists():
        raise EvidenceError("local source store remained available")
    restore_run = run_java([
        arguments.java, "-cp", arguments.classpath, JAVA_MAIN, "restore",
        arguments.java_profile, str(backup), str(restore_store),
        str(source_properties), str(restore_properties),
        str(arguments.duration_seconds),
    ], arguments.timeout_seconds)
    log_out += restore_run.stdout
    log_err += restore_run.stderr
    source = parse_properties(source_properties)
    restore = parse_properties(restore_properties)
    shutil.rmtree(backup)
    shutil.rmtree(restore_store)
    source_properties.unlink()
    restore_properties.unlink()
    document = build_document(
        source_sha=arguments.source_sha,
        source_state=arguments.source_state,
        evidence_profile="local-scaffold",
        java_profile=arguments.java_profile,
        duration_seconds=arguments.duration_seconds,
        slot=1,
        source=source,
        restore=restore,
        inspection=inspection,
        provider="local",
        source_vm_deleted=True,
        source_disk_deleted=True,
        replacement_vm_deleted=True,
        restore_disk_deleted=True,
        staging_object_deleted=True,
        stdout=log_out + f"elapsedSeconds={time.monotonic() - started:.3f}\n",
        stderr=log_err,
    )
    write_bundle(workspace / "evidence", document)
    validate_operational_bundle(workspace / "evidence")
    print("v41OperationalLocal=PASS sourceLoss=true secondReopen=true")
    return 0


def assemble(arguments: argparse.Namespace) -> int:
    source = parse_properties(arguments.source_properties)
    restore = parse_properties(arguments.restore_properties)
    try:
        inspection = inspect_bundle(arguments.backup)
    except BackupFormatError as failure:
        raise EvidenceError(f"independent backup inspection failed: {failure}") from failure
    document = build_document(
        source_sha=arguments.source_sha,
        source_state=arguments.source_state,
        evidence_profile=arguments.profile,
        java_profile=arguments.java_profile,
        duration_seconds=arguments.duration_seconds,
        slot=arguments.slot,
        source=source,
        restore=restore,
        inspection=inspection,
        provider=arguments.provider,
        source_vm_deleted=arguments.source_vm_deleted,
        source_disk_deleted=arguments.source_disk_deleted,
        replacement_vm_deleted=arguments.replacement_vm_deleted,
        restore_disk_deleted=arguments.restore_disk_deleted,
        staging_object_deleted=arguments.staging_object_deleted,
        stdout=arguments.stdout_log.read_text("utf-8")
        if arguments.stdout_log else "",
        stderr=arguments.stderr_log.read_text("utf-8")
        if arguments.stderr_log else "",
    )
    write_bundle(arguments.output, document)
    validate_operational_bundle(arguments.output)
    print(f"v41OperationalAssemble=PASS profile={arguments.profile} slot={arguments.slot}")
    return 0


def validate_operational_bundle(directory: Path) -> dict[str, Any]:
    document = validate_bundle(directory)
    if document["kind"] != "v41-source-loss-replacement-host" \
            or document["status"] != "PASS":
        raise EvidenceError("not passing V4.1 source-loss evidence")
    case = document["case"]
    result = document["result"]
    if case.get("sourceLoss") is not True \
            or result.get("sourceLossProven") is not True \
            or result.get("fullOracle") != "PASS":
        raise EvidenceError("source-loss result is incomplete")
    lifecycle = document["lifecycle"]
    if document["profile"] == "local-scaffold":
        required_order = [
            "local-source-store-created", "backup-cut-selected",
            "local-source-store-deleted", "local-source-unavailable-proven",
            "independent-byte-verification-passed", "local-restore-store-created",
            "new-history-restore-passed", "continued-mutation-passed",
            "second-reopen-passed", "local-artifacts-removed",
        ]
    else:
        required_order = [
            "bundle-uploaded", "source-vm-deleted", "source-disk-deleted",
            "source-unavailable-proven", "restore-disk-created",
            "replacement-vm-created", "bundle-downloaded",
            "independent-byte-verification-passed", "new-history-restore-passed",
            "continued-mutation-passed", "second-reopen-passed",
        ]
    positions = [lifecycle.index(item) for item in required_order]
    if positions != sorted(positions):
        raise EvidenceError("source-loss lifecycle order differs")
    configuration = document["configuration"]
    cleanup = document["cleanup"]
    if document["profile"] == "local-scaffold":
        if configuration.get("javaProfile") != "smoke" \
                or document["process"].get("provider") != "local" \
                or any(cleanup.get(key) != "NOT_APPLICABLE" for key in (
                    "sourceVmDeleted", "sourceDiskDeleted",
                    "replacementVmDeleted", "restoreDiskDeleted",
                    "stagingObjectDeleted")) \
                or not all(cleanup.get(key) is True for key in (
                    "localSourceStoreDeleted", "localRestoreStoreDeleted",
                    "localArtifactsRemoved")):
            raise EvidenceError("local operational evidence configuration differs")
    else:
        expected_durations = {1_800}
        if configuration.get("javaProfile") != "production" \
                or configuration.get("documents") != 100_000 \
                or configuration.get("tokensPerDocument") != 16 \
                or configuration.get("preBackupMutations") != 10_000 \
                or configuration.get("continuedMutations") != 1_000 \
                or configuration.get("measurementSeconds") not in expected_durations \
                or configuration.get("durationSeconds") \
                != configuration.get("measurementSeconds") \
                or configuration.get("machineType") != "c3d-standard-30" \
                or configuration.get("sourceDiskGiB") != 200 \
                or configuration.get("restoreDiskGiB") != 200 \
                or document["process"].get("provider") != "gcp" \
                or result.get("replacementHostProven") is not True \
                or not all(cleanup.get(key) is True for key in (
                    "sourceVmDeleted", "sourceDiskDeleted",
                    "replacementVmDeleted", "restoreDiskDeleted",
                    "stagingObjectDeleted")):
            raise EvidenceError("cloud operational evidence configuration differs")
    if document["profile"] == "canonical" and (
            document["backup"].get("transport") != "GCS"
            or result.get("replacementHostProven") is not True
            or result.get("eligibleForCanonicalRegistration") is not True):
        raise EvidenceError("canonical evidence is not registration eligible")
    return document


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-state", choices=("clean", "dirty"), required=True)
    parser.add_argument("--java-profile", choices=sorted(EXPECTED), required=True)
    parser.add_argument("--duration-seconds", type=int, required=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    local = commands.add_parser("run-local")
    add_common(local)
    local.add_argument("--workspace", type=Path, required=True)
    local.add_argument("--java", default="java")
    local.add_argument("--classpath", default="target/benchmarks.jar")
    local.add_argument("--timeout-seconds", type=int, default=600)
    assemble_parser = commands.add_parser("assemble")
    add_common(assemble_parser)
    assemble_parser.add_argument("--profile", choices=(
        "experiment", "canonical", "failure-drill"), required=True)
    assemble_parser.add_argument("--slot", type=int, required=True)
    assemble_parser.add_argument("--provider", choices=("local", "gcp"), required=True)
    assemble_parser.add_argument("--source-properties", type=Path, required=True)
    assemble_parser.add_argument("--restore-properties", type=Path, required=True)
    assemble_parser.add_argument("--backup", type=Path, required=True)
    assemble_parser.add_argument("--output", type=Path, required=True)
    assemble_parser.add_argument("--stdout-log", type=Path)
    assemble_parser.add_argument("--stderr-log", type=Path)
    for name in ("source-vm-deleted", "source-disk-deleted",
                 "replacement-vm-deleted", "restore-disk-deleted",
                 "staging-object-deleted"):
        assemble_parser.add_argument(f"--{name}", action="store_true")
    validate = commands.add_parser("validate")
    validate.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if hasattr(arguments, "duration_seconds") and arguments.duration_seconds <= 0:
        raise EvidenceError("duration must be positive")
    if arguments.command == "run-local":
        return run_local(arguments)
    if arguments.command == "assemble":
        return assemble(arguments)
    value = validate_operational_bundle(arguments.bundle)
    print(f"v41OperationalEvidenceValidation=PASS profile={value['profile']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, BackupFormatError, OSError, subprocess.SubprocessError) as failure:
        print(f"v41OperationalEvidence=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
