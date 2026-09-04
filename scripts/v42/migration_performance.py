#!/usr/bin/env python3
"""Assemble and validate V4.2 migration performance evidence."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.v41.backup_format import BackupFormatError, inspect_bundle
from scripts.v42.evidence import EvidenceError, validate_bundle, validate_source, write_bundle
from scripts.v42.fake_cloud_lane import PLAN

JAVA_MAIN = "io.github.patricklfdm.generalsearch.engine.V42MigrationEvidenceProbe"
PROPERTIES_SCHEMA = "gse-v42-migration-properties-v1"
LOG_LIMIT = 16 * 1024
EXPECTED = {
    "smoke": {"documents": 1_000, "preMigrationMutations": 100,
              "continuedTargetMutations": 20, "batchSize": 100},
    "production": {"documents": 100_000, "preMigrationMutations": 10_000,
                   "continuedTargetMutations": 1_000, "batchSize": 1_000},
}


def parse_properties(path: Path) -> dict[str, str]:
    try:
        raw = path.read_bytes()
    except OSError as failure:
        raise EvidenceError(f"cannot read properties: {path}") from failure
    if len(raw) > 1024 * 1024:
        raise EvidenceError("migration properties exceed one MiB")
    try:
        lines = raw.decode("utf-8", errors="strict").splitlines()
    except UnicodeError as failure:
        raise EvidenceError("migration properties are not UTF-8") from failure
    result: dict[str, str] = {}
    for number, line in enumerate(lines, start=1):
        if not line or "=" not in line:
            raise EvidenceError(f"invalid property line {number}")
        key, value = line.split("=", 1)
        if not key or not value or key in result:
            raise EvidenceError(f"duplicate or empty property line {number}")
        result[key] = value
    return result


def integer(values: dict[str, str], key: str, *, positive: bool = False) -> int:
    try:
        value = int(values[key])
    except (KeyError, ValueError) as failure:
        raise EvidenceError(f"missing or invalid integer property: {key}") from failure
    if positive and value <= 0:
        raise EvidenceError(f"property must be positive: {key}")
    return value


def digest(values: dict[str, str], key: str, prefix: str = "") -> str:
    value = values.get(key, "")
    candidate = value[len(prefix):] if value.startswith(prefix) else ""
    if len(candidate) != 64 or any(char not in "0123456789abcdef" for char in candidate):
        raise EvidenceError(f"invalid digest property: {key}")
    return value


def validate_properties(
    source: dict[str, str],
    migration: dict[str, str],
    target: dict[str, str],
    rollback: dict[str, str],
    java_profile: str,
    duration_seconds: int,
) -> dict[str, Any]:
    if java_profile not in EXPECTED:
        raise EvidenceError("unsupported migration Java profile")
    expected = EXPECTED[java_profile]
    for values, stage in ((source, "source"), (migration, "migration"),
                          (target, "target")):
        common = {
            "schemaVersion": PROPERTIES_SCHEMA,
            "status": "PASS",
            "stage": stage,
            "profile": java_profile,
            "documents": str(expected["documents"]),
            "tokensPerDocument": "16",
            "preMigrationMutations": str(expected["preMigrationMutations"]),
            "continuedTargetMutations": str(expected["continuedTargetMutations"]),
        }
        for key, value in common.items():
            if values.get(key) != value:
                raise EvidenceError(f"{stage} property differs: {key}")
        for key in ("processCpuNanosAtStart", "processCpuNanosAtEnd"):
            integer(values, key)

    for key in ("source.loadNanos", "source.mutationNanos",
                "source.checkpointNanos", "source.sequence",
                "backup.elapsedNanos", "backup.sequence", "backup.totalBytes",
                "source.retainedBytes", "source.heapUsedBytes",
                "source.directoryBytes", "source.totalNanos"):
        integer(source, key, positive=True)
    if integer(source, "backup.sequence") != integer(source, "source.sequence"):
        raise EvidenceError("backup sequence differs from source")
    digest(source, "source.oracleChecksum")
    digest(source, "source.directorySha256")
    digest(source, "backup.contentIdentity", "gse-backup-v1-")

    for key in ("migration.planNanos", "migration.applyNanos",
                "migration.predictedTargetBytes", "migration.peakTargetBytes",
                "migration.sourceSequence", "migration.authoritativeBytes",
                "migration.heapUsedBytes", "target.initialSequence",
                "target.directoryBytes"):
        integer(migration, key, positive=True)
    for key, prefix in (
        ("migration.planDigest", "gse-migration-plan-v1-"),
        ("migration.projectionDigest", "gse-migration-projection-v1-"),
        ("migration.sourceAuthorityIdentity", "gse-migration-source-v1-"),
        ("migration.sourceDirectorySha256After", ""),
        ("target.initialChecksum", ""),
        ("target.directorySha256", ""),
    ):
        digest(migration, key, prefix)
    if migration["migration.sourceDirectorySha256After"] \
            != source["source.directorySha256"]:
        raise EvidenceError("source bytes changed during migration")
    if integer(migration, "migration.sourceSequence") \
            != integer(source, "source.sequence") \
            or integer(migration, "target.initialSequence") \
            != integer(source, "source.sequence"):
        raise EvidenceError("migration sequence differs")
    if migration.get("migration.sourceHistory") \
            == migration.get("migration.targetHistory"):
        raise EvidenceError("migration did not create a new history")

    for key in ("target.firstOpenNanos", "target.continuedMutationNanos",
                "target.checkpointNanos", "target.secondOpenNanos",
                "target.finalSequence", "target.finalDirectoryBytes",
                "target.retainedBytes", "target.heapUsedBytes",
                "measurement.reads", "measurement.durationNanos",
                "measurement.readsPerSecondMicros", "measurementSeconds"):
        integer(target, key, positive=True)
    digest(target, "target.finalChecksum")
    digest(target, "target.finalDirectorySha256")
    expected_steps = (expected["continuedTargetMutations"]
                      + expected["batchSize"] - 1) // expected["batchSize"]
    if integer(target, "target.finalSequence") \
            != integer(migration, "target.initialSequence") + expected_steps:
        raise EvidenceError("continued target sequence differs")
    if integer(target, "measurementSeconds") != duration_seconds:
        raise EvidenceError("measurement duration declaration differs")
    elapsed = integer(target, "measurement.durationNanos", positive=True)
    if not duration_seconds * 1_000_000_000 <= elapsed \
            <= (duration_seconds + 60) * 1_000_000_000:
        raise EvidenceError("measurement duration differs")

    if rollback != {
        "schemaVersion": "gse-v42-published-rollback-properties-v1",
        "status": "PASS",
        "profile": java_profile,
        "publishedVersion": "4.1.0",
        "sourceDirectorySha256": source["source.directorySha256"],
        "sourceSequence": source["source.sequence"],
        "sourceOracleChecksum": source["source.oracleChecksum"],
    }:
        raise EvidenceError("published-4.1 rollback properties differ")
    return expected


def tail(value: str) -> str:
    encoded = value.encode("utf-8", errors="replace")
    return encoded[-LOG_LIMIT:].decode("utf-8", errors="replace")


def build_document(
    *, source_sha: str, source_state: str, evidence_profile: str,
    java_profile: str, duration_seconds: int, slot: int,
    source: dict[str, str], migration: dict[str, str],
    target: dict[str, str], rollback: dict[str, str],
    inspection: dict[str, object], provider: str,
    cleanup: dict[str, Any], stdout: str, stderr: str,
) -> dict[str, Any]:
    validate_source(source_sha)
    expected = validate_properties(
        source, migration, target, rollback, java_profile, duration_seconds)
    if inspection.get("status") != "VALID" \
            or inspection.get("contentIdentity") != source["backup.contentIdentity"] \
            or inspection.get("sequence") != int(source["backup.sequence"]):
        raise EvidenceError("independent backup inspection differs")
    configuration = dict(PLAN)
    configuration.update({"javaProfile": java_profile,
                          "durationSeconds": duration_seconds,
                          "measurementSeconds": duration_seconds, "slot": slot})
    lifecycle = [
        "exact-source-validated", "source-disk-created", "target-disk-created",
        "source-vm-created", "published-compatible-source-materialized",
        "source-checkpointed-and-closed", "source-backup-verified",
        "source-before-identity-recorded", "migration-planned",
        "migration-applied-to-absent-target", "source-after-identity-matched",
        "source-vm-deleted", "target-disk-detached",
        "replacement-target-vm-created", "target-independently-verified",
        "target-continued-and-checkpointed", "target-second-reopen-passed",
        "replacement-target-vm-deleted", "target-writer-stopped-before-rollback",
        "rollback-vm-created", "published-4.1-source-reopen-passed",
        "rollback-vm-deleted", "source-disk-deleted", "target-disk-deleted",
        "staging-object-deleted", "cleanup-verified-before-next-member",
    ] if provider == "gcp" else [
        "exact-source-validated", "local-source-created-and-closed",
        "source-backup-verified", "source-before-identity-recorded",
        "migration-planned", "migration-applied-to-absent-target",
        "source-after-identity-matched", "local-target-reopened",
        "target-continued-and-checkpointed", "target-second-reopen-passed",
        "published-4.1-source-reopen-passed", "local-artifacts-deleted",
        "cleanup-verified-before-next-member",
    ]
    return {
        "schemaVersion": "gse-v42-migration-evidence-v1",
        "kind": "v42-storage-evolution-replacement-host",
        "status": "PASS", "sourceCommit": source_sha,
        "sourceState": source_state,
        "suite": "v4.2-storage-evolution-suite-v1",
        "preset": "v4.2-storage-evolution-v1",
        "profile": evidence_profile,
        "case": {"caseId": f"migration-member-{slot}", "slot": slot,
                 "serial": True, "replacementHost": provider == "gcp"},
        "configuration": configuration,
        "source": {
            "format": "gse-durable (1,0)", "bytesUnchanged": True,
            "directorySha256": source["source.directorySha256"],
            "oracleChecksum": source["source.oracleChecksum"],
            "sequence": int(source["source.sequence"]),
            "directoryBytes": int(source["source.directoryBytes"]),
            "backupContentIdentity": source["backup.contentIdentity"],
            "backupInspection": "PASS", "metrics": {
                "loadNanos": int(source["source.loadNanos"]),
                "mutationNanos": int(source["source.mutationNanos"]),
                "checkpointNanos": int(source["source.checkpointNanos"]),
                "backupNanos": int(source["backup.elapsedNanos"]),
                "heapUsedBytes": int(source["source.heapUsedBytes"]),
            },
        },
        "target": {
            "format": "gse-durable (1,1)",
            "initialChecksum": migration["target.initialChecksum"],
            "finalChecksum": target["target.finalChecksum"],
            "initialSequence": int(migration["target.initialSequence"]),
            "finalSequence": int(target["target.finalSequence"]),
            "replacementHost": provider == "gcp", "secondReopen": "PASS",
            "metrics": {
                "firstOpenNanos": int(target["target.firstOpenNanos"]),
                "continuedMutationNanos": int(target["target.continuedMutationNanos"]),
                "checkpointNanos": int(target["target.checkpointNanos"]),
                "secondOpenNanos": int(target["target.secondOpenNanos"]),
                "reads": int(target["measurement.reads"]),
                "durationNanos": int(target["measurement.durationNanos"]),
                "readsPerSecondMicros": int(target["measurement.readsPerSecondMicros"]),
                "heapUsedBytes": int(target["target.heapUsedBytes"]),
            },
        },
        "migration": {
            "plan": "PASS", "apply": "PASS", "sourcePreserved": True,
            "planDigest": migration["migration.planDigest"],
            "projectionDigest": migration["migration.projectionDigest"],
            "sourceAuthorityIdentity": migration["migration.sourceAuthorityIdentity"],
            "sourceHistory": migration["migration.sourceHistory"],
            "targetHistory": migration["migration.targetHistory"],
            "transformIdentity": "catalog-schema-key-v1", "metrics": {
                "planNanos": int(migration["migration.planNanos"]),
                "applyNanos": int(migration["migration.applyNanos"]),
                "predictedTargetBytes": int(migration["migration.predictedTargetBytes"]),
                "peakTargetBytes": int(migration["migration.peakTargetBytes"]),
                "authoritativeBytes": int(migration["migration.authoritativeBytes"]),
                "heapUsedBytes": int(migration["migration.heapUsedBytes"]),
            },
        },
        "rollback": {"publishedVersion": "4.1.0", "status": "PASS",
                     "untouchedSourceReopened": True,
                     "targetWriterStopped": True,
                     "targetOnlyWritesMerged": False},
        "process": {"provider": provider, "python": platform.python_version(),
                    "platform": platform.platform(), "pid": os.getpid(),
                    "serialMembers": True},
        "lifecycle": lifecycle,
        "cleanup": cleanup,
        "logs": {"stdoutTail": tail(stdout), "stderrTail": tail(stderr),
                 "limitBytesPerStream": LOG_LIMIT},
        "result": {"documents": expected["documents"],
                   "replacementHostProven": provider == "gcp",
                   "published41Rollback": "PASS", "fullOracle": "PASS",
                   "cleanup": "PASS",
                   "eligibleForCanonicalRegistration": (
                       provider == "gcp" and evidence_profile == "canonical")},
    }


def run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, check=False, capture_output=True,
                               text=True, timeout=timeout)
    if completed.returncode != 0:
        raise EvidenceError(
            f"migration stage exited with {completed.returncode}: {tail(completed.stderr)}")
    return completed


def run_local(arguments: argparse.Namespace) -> int:
    validate_source(arguments.source_sha)
    workspace = arguments.workspace.resolve()
    if workspace.exists():
        raise EvidenceError("migration workspace already exists")
    workspace.mkdir(parents=True)
    source = workspace / "source"
    target = workspace / "target"
    backup = workspace / "backup"
    source_properties = workspace / "source.properties"
    migration_properties = workspace / "migration.properties"
    target_properties = workspace / "target.properties"
    rollback_properties = workspace / "rollback.properties"
    outputs = []
    for command in (
        [arguments.java, "-cp", arguments.classpath, JAVA_MAIN, "source",
         arguments.java_profile, str(source), str(backup),
         str(source_properties), str(arguments.duration_seconds)],
        [arguments.java, "-cp", arguments.classpath, JAVA_MAIN, "migrate",
         arguments.java_profile, str(source), str(target),
         str(source_properties), str(migration_properties)],
        [arguments.java, "-cp", arguments.classpath, JAVA_MAIN, "target",
         arguments.java_profile, str(target), str(migration_properties),
         str(target_properties), str(arguments.duration_seconds)],
        [arguments.java, "-cp", arguments.published_classpath,
         "PublishedV41MigrationCloudProbe", arguments.java_profile,
         str(source), str(source_properties)],
    ):
        outputs.append(run(command, arguments.timeout_seconds).stdout)
    source_values = parse_properties(source_properties)
    rollback_properties.write_text(
        "schemaVersion=gse-v42-published-rollback-properties-v1\n"
        "status=PASS\n"
        f"profile={arguments.java_profile}\n"
        "publishedVersion=4.1.0\n"
        f"sourceDirectorySha256={source_values['source.directorySha256']}\n"
        f"sourceSequence={source_values['source.sequence']}\n"
        f"sourceOracleChecksum={source_values['source.oracleChecksum']}\n",
        encoding="ascii")
    inspection = inspect_bundle(backup)
    document = build_document(
        source_sha=arguments.source_sha, source_state=arguments.source_state,
        evidence_profile="local-scaffold", java_profile=arguments.java_profile,
        duration_seconds=arguments.duration_seconds, slot=1,
        source=source_values, migration=parse_properties(migration_properties),
        target=parse_properties(target_properties),
        rollback=parse_properties(rollback_properties), inspection=inspection,
        provider="local", cleanup={
            "status": "PASS", "leftovers": [],
            "sourceVmDeleted": "NOT_APPLICABLE",
            "replacementTargetVmDeleted": "NOT_APPLICABLE",
            "rollbackVmDeleted": "NOT_APPLICABLE",
            "sourceDiskDeleted": "NOT_APPLICABLE",
            "targetDiskDeleted": "NOT_APPLICABLE",
            "stagingObjectDeleted": "NOT_APPLICABLE",
            "localArtifactsDeleted": True,
        }, stdout="".join(outputs), stderr="")
    for path in (source, target, backup):
        shutil.rmtree(path)
    for path in (source_properties, migration_properties,
                 target_properties, rollback_properties):
        path.unlink()
    write_bundle(workspace / "evidence", document)
    validate_migration_bundle(workspace / "evidence")
    print("v42MigrationPerformanceLocal=PASS rollback=published-4.1")
    return 0


def assemble(arguments: argparse.Namespace) -> int:
    try:
        inspection = inspect_bundle(arguments.backup)
    except BackupFormatError as failure:
        raise EvidenceError(f"independent backup inspection failed: {failure}") from failure
    cleanup = {"status": "PASS", "leftovers": [],
               "sourceVmDeleted": arguments.source_vm_deleted,
               "replacementTargetVmDeleted": arguments.replacement_target_vm_deleted,
               "rollbackVmDeleted": arguments.rollback_vm_deleted,
               "sourceDiskDeleted": arguments.source_disk_deleted,
               "targetDiskDeleted": arguments.target_disk_deleted,
               "stagingObjectDeleted": arguments.staging_object_deleted}
    document = build_document(
        source_sha=arguments.source_sha, source_state=arguments.source_state,
        evidence_profile=arguments.profile, java_profile=arguments.java_profile,
        duration_seconds=arguments.duration_seconds, slot=arguments.slot,
        source=parse_properties(arguments.source_properties),
        migration=parse_properties(arguments.migration_properties),
        target=parse_properties(arguments.target_properties),
        rollback=parse_properties(arguments.rollback_properties),
        inspection=inspection, provider="gcp", cleanup=cleanup,
        stdout=arguments.stdout_log.read_text("utf-8") if arguments.stdout_log else "",
        stderr=arguments.stderr_log.read_text("utf-8") if arguments.stderr_log else "")
    write_bundle(arguments.output, document)
    validate_migration_bundle(arguments.output)
    print(f"v42MigrationPerformanceAssemble=PASS profile={arguments.profile} "
          f"slot={arguments.slot}")
    return 0


def validate_migration_bundle(directory: Path) -> dict[str, Any]:
    document = validate_bundle(directory)
    if document["kind"] != "v42-storage-evolution-replacement-host" \
            or document["status"] != "PASS" \
            or document["source"].get("bytesUnchanged") is not True \
            or document["migration"].get("sourcePreserved") is not True \
            or document["rollback"].get("publishedVersion") != "4.1.0" \
            or document["rollback"].get("untouchedSourceReopened") is not True:
        raise EvidenceError("not passing V4.2 migration evidence")
    lifecycle = document["lifecycle"]
    required = ["source-before-identity-recorded", "migration-planned",
                "migration-applied-to-absent-target", "source-after-identity-matched",
                "target-continued-and-checkpointed", "target-second-reopen-passed",
                "published-4.1-source-reopen-passed",
                "cleanup-verified-before-next-member"]
    positions = [lifecycle.index(value) for value in required]
    if positions != sorted(positions):
        raise EvidenceError("migration lifecycle order differs")
    if document["profile"] == "local-scaffold":
        if document["process"].get("provider") != "local" \
                or document["configuration"].get("javaProfile") != "smoke" \
                or document["cleanup"].get("localArtifactsDeleted") is not True:
            raise EvidenceError("local migration evidence differs")
    else:
        cleanup = document["cleanup"]
        if document["process"].get("provider") != "gcp" \
                or document["configuration"].get("javaProfile") != "production" \
                or document["configuration"].get("documents") != 100_000 \
                or document["configuration"].get("durationSeconds") != 1_800 \
                or not all(cleanup.get(key) is True for key in (
                    "sourceVmDeleted", "replacementTargetVmDeleted",
                    "rollbackVmDeleted", "sourceDiskDeleted",
                    "targetDiskDeleted", "stagingObjectDeleted")) \
                or document["result"].get("replacementHostProven") is not True:
            raise EvidenceError("cloud migration evidence differs")
    if document["profile"] == "canonical" \
            and document["result"].get("eligibleForCanonicalRegistration") is not True:
        raise EvidenceError("canonical migration evidence is ineligible")
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
    local.add_argument("--published-classpath", required=True)
    local.add_argument("--timeout-seconds", type=int, default=600)
    assembly = commands.add_parser("assemble")
    add_common(assembly)
    assembly.add_argument("--profile", choices=("experiment", "canonical",
                                                 "failure-drill"), required=True)
    assembly.add_argument("--slot", type=int, required=True)
    assembly.add_argument("--source-properties", type=Path, required=True)
    assembly.add_argument("--migration-properties", type=Path, required=True)
    assembly.add_argument("--target-properties", type=Path, required=True)
    assembly.add_argument("--rollback-properties", type=Path, required=True)
    assembly.add_argument("--backup", type=Path, required=True)
    assembly.add_argument("--output", type=Path, required=True)
    assembly.add_argument("--stdout-log", type=Path)
    assembly.add_argument("--stderr-log", type=Path)
    for name in ("source-vm-deleted", "replacement-target-vm-deleted",
                 "rollback-vm-deleted", "source-disk-deleted",
                 "target-disk-deleted", "staging-object-deleted"):
        assembly.add_argument(f"--{name}", action="store_true")
    validate = commands.add_parser("validate")
    validate.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if hasattr(arguments, "duration_seconds") and arguments.duration_seconds <= 0:
        raise EvidenceError("duration must be positive")
    if arguments.command == "run-local":
        return run_local(arguments)
    if arguments.command == "assemble":
        return assemble(arguments)
    result = validate_migration_bundle(arguments.bundle)
    print(f"v42MigrationPerformanceValidation=PASS profile={result['profile']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, BackupFormatError, OSError,
            subprocess.SubprocessError) as failure:
        print(f"v42MigrationPerformance=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
