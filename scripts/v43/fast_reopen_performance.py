#!/usr/bin/env python3
"""Run, assemble, and validate bounded V4.3 fast-reopen evidence."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.v43.derived_format_v12 import (
    DerivedFormatError, inspect_backup_directory,
)
from scripts.v43.evidence import (
    EvidenceError, base_document, validate_bundle, validate_source, write_bundle,
)
from scripts.v43.fake_cloud_lane import CELLS, PLAN

JAVA_MAIN = "io.github.patricklfdm.generalsearch.engine.V43FastReopenEvidenceProbe"
PUBLISHED_MAIN = "PublishedV42FastReopenControl"
PROPERTIES_SCHEMA = "gse-v43-fast-reopen-properties-v1"
PUBLISHED_SCHEMA = "gse-v43-published-v42-properties-v1"
LOG_LIMIT = 16 * 1024
EXPECTED = {
    "smoke": {"documents": 1_000, "mutations": 100, "samples": 3},
    "production": {"documents": 100_000, "mutations": 10_000, "samples": 5},
}


def parse_properties(path: Path) -> dict[str, str]:
    try:
        raw = path.read_bytes()
    except OSError as failure:
        raise EvidenceError(f"cannot read properties: {path}") from failure
    if len(raw) > 1024 * 1024:
        raise EvidenceError("properties exceed one MiB")
    try:
        lines = raw.decode("ascii", errors="strict").splitlines()
    except UnicodeError as failure:
        raise EvidenceError("properties are not ASCII") from failure
    values: dict[str, str] = {}
    for number, line in enumerate(lines, 1):
        if not line or "=" not in line:
            raise EvidenceError(f"invalid property line {number}")
        key, value = line.split("=", 1)
        if not key or not value or key in values:
            raise EvidenceError(f"duplicate or empty property line {number}")
        values[key] = value
    return values


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
    suffix = value[len(prefix):] if value.startswith(prefix) else ""
    if len(suffix) != 64 or any(char not in "0123456789abcdef" for char in suffix):
        raise EvidenceError(f"invalid digest property: {key}")
    return value


def samples(values: dict[str, str], key: str, count: int) -> list[int]:
    try:
        result = [int(value) for value in values[key].split(",")]
    except (KeyError, ValueError) as failure:
        raise EvidenceError(f"invalid samples property: {key}") from failure
    if len(result) != count or any(value <= 0 for value in result):
        raise EvidenceError(f"samples differ: {key}")
    return result


def validate_properties(
    published: dict[str, str], source: dict[str, str],
    replacement: dict[str, str], java_profile: str, duration_seconds: int,
) -> dict[str, Any]:
    if java_profile not in EXPECTED:
        raise EvidenceError("unsupported Java profile")
    expected = EXPECTED[java_profile]
    common = {
        "status": "PASS", "profile": java_profile,
        "documents": str(expected["documents"]), "tokensPerDocument": "16",
        "samples": str(expected["samples"]),
    }
    for values, stage in ((source, "source"), (replacement, "replacement")):
        required = {"schemaVersion": PROPERTIES_SCHEMA, "stage": stage,
                    "mutations": str(expected["mutations"]), **common}
        for key, value in required.items():
            if values.get(key) != value:
                raise EvidenceError(f"{stage} property differs: {key}")
        if values.get("pageCacheState") != "uncontrolled-os-cache":
            raise EvidenceError(f"{stage} page-cache state differs")
        for key in ("processCpuNanosAtStart", "processCpuNanosAtEnd"):
            integer(values, key)
    published_required = {
        "schemaVersion": PUBLISHED_SCHEMA, "publishedVersion": "4.2.0",
        "pageCacheState": "uncontrolled-os-cache", **common,
    }
    for key, value in published_required.items():
        if published.get(key) != value:
            raise EvidenceError(f"published control property differs: {key}")

    count = expected["samples"]
    published_samples = samples(published, "open.samplesNanos", count)
    forced_samples = samples(source, "forced.samplesNanos", count)
    warm_samples = samples(source, "warm.samplesNanos", count)
    for values, prefix, observed in (
        (published, "open", published_samples),
        (source, "forced", forced_samples), (source, "warm", warm_samples),
    ):
        median = integer(values, f"{prefix}.medianNanos", positive=True)
        if median != sorted(observed)[len(observed) // 2]:
            raise EvidenceError(f"{prefix} median differs from samples")
    for key in (
        "source.loadCheckpointNanos", "source.sequence", "backup.elapsedNanos",
        "backup.sequence", "backup.totalBytes", "forced.recoveryReadyMedianNanos",
        "forced.refreshMedianNanos", "warm.derivedReadMedianBytes",
        "restore.coldOpenNanos", "restore.warmOpenNanos", "migration.planNanos",
        "migration.applyNanos", "migration.coldOpenNanos", "source.canonicalBytes",
        "source.derivedBytes", "source.directoryBytes", "source.temporaryPeakBytes",
        "source.heapUsedBytes", "source.totalNanos",
    ):
        integer(source, key, positive=True)
    for key in ("source.gcCount", "source.gcTimeMillis"):
        integer(source, key)
    ratio = integer(source, "warm.ratioMicros", positive=True)
    calculated = round(integer(source, "warm.medianNanos", positive=True)
                       * 1_000_000 / integer(source, "forced.medianNanos", positive=True))
    if ratio != calculated:
        raise EvidenceError("warm ratio differs from recorded medians")
    if integer(source, "backup.sequence") != integer(source, "source.sequence"):
        raise EvidenceError("backup sequence differs from source")
    digest(source, "backup.contentIdentity", "gse-backup-v3-")
    digest(source, "migration.planDigest", "gse-migration-plan-v1-")
    if source.get("restore.coldOutcome") != "FULL_FALLBACK" \
            or source.get("restore.warmOutcome") != "COMPLETE_WARM" \
            or source.get("migration.coldOutcome") != "FULL_FALLBACK":
        raise EvidenceError("restore or migration reopen outcome differs")

    oracle = digest(source, "source.initialChecksum")
    if digest(published, "oracleChecksum") != oracle:
        raise EvidenceError("published 4.2 oracle differs from current source")
    for key in ("forced.checksum", "warm.checksum", "restore.checksum",
                "migration.checksum"):
        if digest(source, key) != oracle:
            raise EvidenceError(f"source checksum differs: {key}")

    for key in (
        "replacement.primaryWarmNanos", "replacement.migratedWarmNanos",
        "fallback.structuredOpenNanos", "fallback.textOpenNanos",
        "fallback.catalogOpenNanos", "wal.openNanos", "wal.recoveredSequence",
        "lifecycle.elapsedNanos", "lifecycle.reopenNanos", "lifecycle.sequence",
        "measurement.reads", "measurement.durationNanos",
        "measurement.readsPerSecondMicros", "replacement.heapUsedBytes",
        "replacement.canonicalBytes", "replacement.derivedBytes",
        "replacement.directoryBytes",
    ):
        integer(replacement, key, positive=True)
    for key in ("wal.replayCreatedIndexes", "measurement.processCpuNanos",
                "measurement.readBytes", "measurement.writeBytes",
                "measurement.gcCount", "measurement.gcTimeMillis"):
        integer(replacement, key)
    if integer(replacement, "measurementSeconds") != duration_seconds:
        raise EvidenceError("measurement duration declaration differs")
    elapsed = integer(replacement, "measurement.durationNanos", positive=True)
    if not duration_seconds * 1_000_000_000 <= elapsed \
            <= (duration_seconds + 60) * 1_000_000_000:
        raise EvidenceError("measurement duration differs")
    if (integer(replacement, "fallback.structuredLoaded"),
            integer(replacement, "fallback.structuredRebuilt"),
            integer(replacement, "fallback.textLoaded"),
            integer(replacement, "fallback.textRebuilt"),
            integer(replacement, "fallback.catalogRebuilt")) != (3, 1, 3, 1, 4):
        raise EvidenceError("selective fallback counts differ")
    for key in ("replacement.primaryChecksum", "replacement.migratedChecksum",
                "fallback.structuredChecksum", "fallback.textChecksum",
                "fallback.catalogChecksum"):
        if digest(replacement, key) != oracle:
            raise EvidenceError(f"replacement checksum differs: {key}")
    wal = digest(replacement, "wal.checksum")
    if digest(replacement, "lifecycle.checksum") != wal or wal == oracle:
        raise EvidenceError("continued-mutation oracle differs")
    return {"expected": expected, "oracle": oracle, "ratioMicros": ratio}


def tail(value: str) -> str:
    encoded = value.encode("utf-8", errors="replace")
    return encoded[-LOG_LIMIT:].decode("utf-8", errors="replace")


def build_document(
    *, source_sha: str, source_state: str, evidence_profile: str,
    java_profile: str, duration_seconds: int, slot: int,
    published: dict[str, str], source: dict[str, str],
    replacement: dict[str, str], inspection: dict[str, object], provider: str,
    cleanup: dict[str, Any], stdout: str, stderr: str,
) -> dict[str, Any]:
    validate_source(source_sha)
    checked = validate_properties(
        published, source, replacement, java_profile, duration_seconds)
    if inspection.get("status") != "VALID" \
            or inspection.get("contentIdentity") != source["backup.contentIdentity"] \
            or inspection.get("sequence") != int(source["backup.sequence"]):
        raise EvidenceError("independent backup inspection differs")
    configuration = dict(PLAN)
    configuration.update({"javaProfile": java_profile, "slot": slot,
                          "durationSeconds": duration_seconds,
                          "documents": checked["expected"]["documents"],
                          "mutations": checked["expected"]["mutations"]})
    document = base_document(source_sha, source_state, evidence_profile)
    document.update({
        "kind": "v43-fast-reopen-replacement-host", "status": "PASS",
        "case": {"caseId": f"fast-reopen-member-{slot}", "slot": slot,
                 "serial": True, "replacementHost": provider == "gcp",
                 "cells": list(CELLS)},
        "configuration": configuration,
        "canonical": {
            "authority": "VALID", "bytesUnchanged": True,
            "oracleChecksum": checked["oracle"],
            "sequence": int(source["source.sequence"]),
            "backupContentIdentity": source["backup.contentIdentity"],
            "backupInspection": "PASS",
            "backup": {
                "sequence": int(source["backup.sequence"]),
                "totalBytes": int(source["backup.totalBytes"]),
                "elapsedNanos": int(source["backup.elapsedNanos"]),
            },
            "checksums": {
                "published42": published["oracleChecksum"],
                "currentForced": source["forced.checksum"],
                "completeWarm": source["warm.checksum"],
                "restored": source["restore.checksum"],
                "migrated": source["migration.checksum"],
                "replacementPrimary": replacement["replacement.primaryChecksum"],
                "replacementMigrated": replacement["replacement.migratedChecksum"],
                "structuredFallback": replacement["fallback.structuredChecksum"],
                "textFallback": replacement["fallback.textChecksum"],
                "catalogFallback": replacement["fallback.catalogChecksum"],
                "checkpointPlusWal": replacement["wal.checksum"],
                "indexLifecycle": replacement["lifecycle.checksum"],
            },
        },
        "derived": {
            "classification": "COMPLETE_WARM", "productionBytes": True,
            "forcedRebuildControlIsBenchmarkOnly": True,
            "outcomes": ["COMPLETE_WARM", "PARTIAL_FALLBACK", "FULL_FALLBACK"],
            "structuredPartial": {"loaded": 3, "rebuilt": 1},
            "textPartial": {"loaded": 3, "rebuilt": 1},
            "catalogFallbackRebuilt": 4,
            "openNanos": {
                "published42Samples": samples(
                    published, "open.samplesNanos", checked["expected"]["samples"]),
                "currentForcedSamples": samples(
                    source, "forced.samplesNanos", checked["expected"]["samples"]),
                "completeWarmSamples": samples(
                    source, "warm.samplesNanos", checked["expected"]["samples"]),
                "forcedRecoveryReadyMedian": int(
                    source["forced.recoveryReadyMedianNanos"]),
                "forcedRefreshMedian": int(source["forced.refreshMedianNanos"]),
                "restoredCold": int(source["restore.coldOpenNanos"]),
                "restoredWarm": int(source["restore.warmOpenNanos"]),
                "migrationPlan": int(source["migration.planNanos"]),
                "migrationApply": int(source["migration.applyNanos"]),
                "migratedCold": int(source["migration.coldOpenNanos"]),
                "replacementPrimaryWarm": int(
                    replacement["replacement.primaryWarmNanos"]),
                "replacementMigratedWarm": int(
                    replacement["replacement.migratedWarmNanos"]),
                "structuredFallback": int(
                    replacement["fallback.structuredOpenNanos"]),
                "textFallback": int(replacement["fallback.textOpenNanos"]),
                "catalogFallback": int(replacement["fallback.catalogOpenNanos"]),
                "checkpointPlusWal": int(replacement["wal.openNanos"]),
                "indexLifecycle": int(replacement["lifecycle.reopenNanos"]),
            },
            "completeWarmDerivedReadMedianBytes": int(
                source["warm.derivedReadMedianBytes"]),
            "checkpointPlusWal": {
                "recoveredSequence": int(replacement["wal.recoveredSequence"]),
                "replayCreatedIndexes": int(
                    replacement["wal.replayCreatedIndexes"]),
            },
            "indexLifecycle": {
                "sequence": int(replacement["lifecycle.sequence"]),
                "elapsedNanos": int(replacement["lifecycle.elapsedNanos"]),
            },
        },
        "process": {
            "provider": provider, "javaProfile": java_profile,
            "replacementHost": provider == "gcp",
            "published42MedianNanos": int(published["open.medianNanos"]),
            "currentForcedMedianNanos": int(source["forced.medianNanos"]),
            "completeWarmMedianNanos": int(source["warm.medianNanos"]),
            "warmToForcedRatioMicros": checked["ratioMicros"],
            "pageCacheState": source["pageCacheState"],
            "sourceHeapUsedBytes": int(source["source.heapUsedBytes"]),
            "replacementHeapUsedBytes": int(replacement["replacement.heapUsedBytes"]),
            "sourceCpuNanos": int(source["processCpuNanosAtEnd"])
                - int(source["processCpuNanosAtStart"]),
            "replacementCpuNanos": int(replacement["processCpuNanosAtEnd"])
                - int(replacement["processCpuNanosAtStart"]),
            "sourceGcCount": int(source["source.gcCount"]),
            "sourceGcTimeMillis": int(source["source.gcTimeMillis"]),
            "measurementGcCount": int(replacement["measurement.gcCount"]),
            "measurementGcTimeMillis": int(
                replacement["measurement.gcTimeMillis"]),
            "sourceCanonicalBytes": int(source["source.canonicalBytes"]),
            "sourceDerivedBytes": int(source["source.derivedBytes"]),
            "sourceDirectoryBytes": int(source["source.directoryBytes"]),
            "sourceTemporaryPeakBytes": int(source["source.temporaryPeakBytes"]),
            "sourceTotalNanos": int(source["source.totalNanos"]),
            "replacementCanonicalBytes": int(
                replacement["replacement.canonicalBytes"]),
            "replacementDerivedBytes": int(
                replacement["replacement.derivedBytes"]),
            "replacementDirectoryBytes": int(
                replacement["replacement.directoryBytes"]),
            "measurementSeconds": int(replacement["measurementSeconds"]),
            "measurementDurationNanos": int(
                replacement["measurement.durationNanos"]),
            "measurementReads": int(replacement["measurement.reads"]),
            "measurementReadsPerSecondMicros": int(
                replacement["measurement.readsPerSecondMicros"]),
            "measurementCpuNanos": int(replacement["measurement.processCpuNanos"]),
            "measurementReadBytes": int(replacement["measurement.readBytes"]),
            "measurementWriteBytes": int(replacement["measurement.writeBytes"]),
        },
        "lifecycle": [
            "published-4.2-control-recorded", "canonical-source-created",
            "canonical-only-backup-independently-verified",
            "current-forced-and-warm-samples-paired",
            "restore-cold-then-warm-proved", "migration-cold-proved",
            "source-host-retired" if provider == "gcp" else "local-source-closed",
            "replacement-host-started" if provider == "gcp" else "local-replacement-opened",
            "structured-partial-fallback-proved", "text-partial-fallback-proved",
            "catalog-full-fallback-proved", "checkpoint-plus-wal-reopen-proved",
            "dynamic-index-lifecycle-proved", "measurement-window-completed",
            "all-owned-resources-cleaned",
        ],
        "cleanup": cleanup,
        "logs": {"stdoutTail": tail(stdout), "stderrTail": tail(stderr),
                 "limitBytesPerStream": LOG_LIMIT},
        "result": {
            "paidExecution": provider == "gcp", "productionDerivedState": True,
            "cells": list(CELLS), "cellCount": len(CELLS),
            "warmToForcedRatioMicros": checked["ratioMicros"],
            "memberThresholdRatioMicros": 650_000,
            "memberThresholdApplies": evidence_profile == "canonical",
            "replacementHostProven": provider == "gcp", "cleanup": "PASS",
        },
    })
    if evidence_profile == "canonical" and checked["ratioMicros"] > 650_000:
        raise EvidenceError("canonical member warm ratio exceeds 0.65")
    return document


def validate_fast_reopen_bundle(path: Path) -> dict[str, Any]:
    document = validate_bundle(path)
    if document.get("kind") != "v43-fast-reopen-replacement-host" \
            or document.get("status") != "PASS" \
            or document["case"].get("cells") != CELLS \
            or document["result"].get("cells") != CELLS \
            or document["result"].get("cellCount") != len(CELLS):
        raise EvidenceError("fast-reopen evidence shape differs")
    profile = document["profile"]
    provider = document["process"].get("provider")
    java_profile = document["process"].get("javaProfile")
    if provider == "local":
        expected_profile, expected_java, replacement_host = \
            "local-scaffold", "smoke", False
    elif provider == "gcp":
        expected_profile, expected_java, replacement_host = \
            profile, "production", True
        if profile not in {"experiment", "canonical", "failure-drill"}:
            raise EvidenceError("cloud member profile differs")
    else:
        raise EvidenceError("fast-reopen provider differs")
    if profile != expected_profile or java_profile != expected_java:
        raise EvidenceError("evidence and Java profiles differ")

    expected = EXPECTED[expected_java]
    configuration = dict(PLAN)
    configuration.update({
        "javaProfile": expected_java,
        "slot": document["case"].get("slot"),
        "durationSeconds": 1 if provider == "local" else 1_800,
        "documents": expected["documents"],
        "mutations": expected["mutations"],
    })
    if document["configuration"] != configuration:
        raise EvidenceError("fast-reopen configuration differs")
    slot = document["case"].get("slot")
    maximum_slot = 3 if profile == "canonical" else 1
    if type(slot) is not int or not 1 <= slot <= maximum_slot \
            or document["case"] != {
                "caseId": f"fast-reopen-member-{slot}", "slot": slot,
                "serial": True, "replacementHost": replacement_host,
                "cells": list(CELLS),
            }:
        raise EvidenceError("fast-reopen case differs")

    canonical = document["canonical"]
    identity = canonical.get("backupContentIdentity", "")
    oracle = canonical.get("oracleChecksum", "")
    if set(canonical) != {
            "authority", "bytesUnchanged", "oracleChecksum", "sequence",
            "backupContentIdentity", "backupInspection", "backup", "checksums"} \
            or canonical.get("authority") != "VALID" \
            or canonical.get("bytesUnchanged") is not True \
            or canonical.get("backupInspection") != "PASS" \
            or type(canonical.get("sequence")) is not int \
            or canonical["sequence"] <= 0 \
            or len(identity) != len("gse-backup-v3-") + 64 \
            or not identity.startswith("gse-backup-v3-") \
            or any(char not in "0123456789abcdef" for char in identity[-64:]) \
            or len(oracle) != 64 \
            or any(char not in "0123456789abcdef" for char in oracle):
        raise EvidenceError("canonical evidence differs")
    backup = canonical["backup"]
    if set(backup) != {"sequence", "totalBytes", "elapsedNanos"} \
            or backup.get("sequence") != canonical["sequence"]:
        raise EvidenceError("canonical backup evidence differs")
    for key in ("sequence", "totalBytes", "elapsedNanos"):
        if type(backup.get(key)) is not int or backup[key] <= 0:
            raise EvidenceError(f"canonical backup metric differs: {key}")
    checksums = canonical["checksums"]
    canonical_checksum_keys = {
        "published42", "currentForced", "completeWarm", "restored", "migrated",
        "replacementPrimary", "replacementMigrated", "structuredFallback",
        "textFallback", "catalogFallback",
    }
    if set(checksums) != canonical_checksum_keys | {
            "checkpointPlusWal", "indexLifecycle"} \
            or any(checksums.get(key) != oracle for key in canonical_checksum_keys) \
            or checksums.get("checkpointPlusWal") \
            != checksums.get("indexLifecycle") \
            or checksums.get("checkpointPlusWal") == oracle:
        raise EvidenceError("canonical checksum evidence differs")
    continued = checksums["checkpointPlusWal"]
    if len(continued) != 64 \
            or any(char not in "0123456789abcdef" for char in continued):
        raise EvidenceError("continued-mutation checksum differs")

    derived = document["derived"]
    if set(derived) != {
            "classification", "productionBytes",
            "forcedRebuildControlIsBenchmarkOnly", "outcomes",
            "structuredPartial", "textPartial", "catalogFallbackRebuilt",
            "openNanos", "completeWarmDerivedReadMedianBytes",
            "checkpointPlusWal", "indexLifecycle"} \
            or derived.get("classification") != "COMPLETE_WARM" \
            or derived.get("productionBytes") is not True \
            or derived.get("forcedRebuildControlIsBenchmarkOnly") is not True \
            or derived.get("outcomes") != [
                "COMPLETE_WARM", "PARTIAL_FALLBACK", "FULL_FALLBACK"] \
            or derived.get("structuredPartial") != {"loaded": 3, "rebuilt": 1} \
            or derived.get("textPartial") != {"loaded": 3, "rebuilt": 1} \
            or derived.get("catalogFallbackRebuilt") != 4:
        raise EvidenceError("derived-state evidence differs")
    timings = derived["openNanos"]
    expected_timing_keys = {
        "published42Samples", "currentForcedSamples", "completeWarmSamples",
        "forcedRecoveryReadyMedian", "forcedRefreshMedian", "restoredCold",
        "restoredWarm", "migrationPlan", "migrationApply", "migratedCold",
        "replacementPrimaryWarm", "replacementMigratedWarm",
        "structuredFallback", "textFallback", "catalogFallback",
        "checkpointPlusWal", "indexLifecycle",
    }
    if set(timings) != expected_timing_keys:
        raise EvidenceError("reopen timing evidence differs")
    sample_count = expected["samples"]
    for key in ("published42Samples", "currentForcedSamples",
                "completeWarmSamples"):
        values = timings.get(key)
        if not isinstance(values, list) or len(values) != sample_count \
                or any(type(value) is not int or value <= 0 for value in values):
            raise EvidenceError(f"reopen samples differ: {key}")
    for key in expected_timing_keys - {
            "published42Samples", "currentForcedSamples", "completeWarmSamples"}:
        if type(timings.get(key)) is not int or timings[key] <= 0:
            raise EvidenceError(f"reopen timing differs: {key}")
    if sorted(timings["published42Samples"])[sample_count // 2] \
            != document["process"].get("published42MedianNanos") \
            or sorted(timings["currentForcedSamples"])[sample_count // 2] \
            != document["process"].get("currentForcedMedianNanos") \
            or sorted(timings["completeWarmSamples"])[sample_count // 2] \
            != document["process"].get("completeWarmMedianNanos"):
        raise EvidenceError("reopen sample medians differ")
    if type(derived.get("completeWarmDerivedReadMedianBytes")) is not int \
            or derived["completeWarmDerivedReadMedianBytes"] <= 0:
        raise EvidenceError("derived read-byte evidence differs")
    wal = derived["checkpointPlusWal"]
    lifecycle_state = derived["indexLifecycle"]
    if set(wal) != {"recoveredSequence", "replayCreatedIndexes"} \
            or type(wal.get("recoveredSequence")) is not int \
            or wal["recoveredSequence"] <= canonical["sequence"] \
            or type(wal.get("replayCreatedIndexes")) is not int \
            or wal["replayCreatedIndexes"] < 0 \
            or set(lifecycle_state) != {"sequence", "elapsedNanos"} \
            or type(lifecycle_state.get("sequence")) is not int \
            or lifecycle_state["sequence"] <= wal["recoveredSequence"] \
            or type(lifecycle_state.get("elapsedNanos")) is not int \
            or lifecycle_state["elapsedNanos"] <= 0:
        raise EvidenceError("WAL or index-lifecycle evidence differs")

    process = document["process"]
    expected_process_keys = {
        "provider", "javaProfile", "replacementHost",
        "published42MedianNanos", "currentForcedMedianNanos",
        "completeWarmMedianNanos", "warmToForcedRatioMicros",
        "pageCacheState", "sourceHeapUsedBytes", "replacementHeapUsedBytes",
        "sourceCpuNanos", "replacementCpuNanos", "sourceGcCount",
        "sourceGcTimeMillis", "measurementGcCount", "measurementGcTimeMillis",
        "sourceCanonicalBytes", "sourceDerivedBytes", "sourceDirectoryBytes",
        "sourceTemporaryPeakBytes", "sourceTotalNanos",
        "replacementCanonicalBytes", "replacementDerivedBytes",
        "replacementDirectoryBytes", "measurementSeconds",
        "measurementDurationNanos", "measurementReads",
        "measurementReadsPerSecondMicros", "measurementCpuNanos",
        "measurementReadBytes", "measurementWriteBytes",
    }
    if set(process) != expected_process_keys \
            or process.get("replacementHost") is not replacement_host \
            or process.get("pageCacheState") != "uncontrolled-os-cache":
        raise EvidenceError("process evidence differs")
    for key in expected_process_keys - {
            "provider", "javaProfile", "replacementHost", "pageCacheState"}:
        if type(process.get(key)) is not int or process[key] < 0:
            raise EvidenceError(f"process metric differs: {key}")
    for key in ("published42MedianNanos", "currentForcedMedianNanos",
                "completeWarmMedianNanos", "warmToForcedRatioMicros",
                "sourceHeapUsedBytes", "replacementHeapUsedBytes",
                "sourceCanonicalBytes", "sourceDerivedBytes",
                "sourceDirectoryBytes", "sourceTemporaryPeakBytes",
                "sourceTotalNanos", "replacementCanonicalBytes",
                "replacementDerivedBytes", "replacementDirectoryBytes",
                "measurementSeconds", "measurementDurationNanos",
                "measurementReads", "measurementReadsPerSecondMicros"):
        if process[key] <= 0:
            raise EvidenceError(f"process metric must be positive: {key}")
    expected_seconds = 1 if provider == "local" else 1_800
    if process["measurementSeconds"] != expected_seconds \
            or not expected_seconds * 1_000_000_000 \
            <= process["measurementDurationNanos"] \
            <= (expected_seconds + 60) * 1_000_000_000 \
            or process["sourceDirectoryBytes"] \
            != process["sourceCanonicalBytes"] + process["sourceDerivedBytes"] \
            or process["replacementDirectoryBytes"] \
            != process["replacementCanonicalBytes"] \
            + process["replacementDerivedBytes"] \
            or process["sourceTemporaryPeakBytes"] \
            < process["sourceDirectoryBytes"]:
        raise EvidenceError("duration or byte-amplification evidence differs")
    ratio = document["process"].get("warmToForcedRatioMicros")
    if not isinstance(ratio, int) or ratio <= 0 \
            or ratio != document["result"].get("warmToForcedRatioMicros"):
        raise EvidenceError("fast-reopen ratio differs")
    calculated = round(process["completeWarmMedianNanos"] * 1_000_000
                       / process["currentForcedMedianNanos"])
    if ratio != calculated:
        raise EvidenceError("fast-reopen ratio is inconsistent")
    expected_lifecycle = [
        "published-4.2-control-recorded", "canonical-source-created",
        "canonical-only-backup-independently-verified",
        "current-forced-and-warm-samples-paired",
        "restore-cold-then-warm-proved", "migration-cold-proved",
        "source-host-retired" if provider == "gcp" else "local-source-closed",
        "replacement-host-started" if provider == "gcp"
        else "local-replacement-opened",
        "structured-partial-fallback-proved", "text-partial-fallback-proved",
        "catalog-full-fallback-proved", "checkpoint-plus-wal-reopen-proved",
        "dynamic-index-lifecycle-proved", "measurement-window-completed",
        "all-owned-resources-cleaned",
    ]
    if document["lifecycle"] != expected_lifecycle:
        raise EvidenceError("fast-reopen lifecycle differs")
    cleanup = document["cleanup"]
    expected_cleanup = ({"status": "PASS", "leftovers": [],
                         "localArtifactsDeleted": True}
                        if provider == "local" else {
                            "status": "PASS", "leftovers": [],
                            "sourceVmDeleted": True,
                            "replacementVmDeleted": True,
                            "primaryDiskDeleted": True,
                            "targetDiskDeleted": True,
                            "stagingObjectsDeleted": True,
                        })
    if cleanup != expected_cleanup:
        raise EvidenceError("fast-reopen cleanup evidence differs")
    expected_result = {
        "paidExecution": provider == "gcp", "productionDerivedState": True,
        "cells": list(CELLS), "cellCount": len(CELLS),
        "warmToForcedRatioMicros": ratio,
        "memberThresholdRatioMicros": 650_000,
        "memberThresholdApplies": profile == "canonical",
        "replacementHostProven": replacement_host, "cleanup": "PASS",
    }
    if document["result"] != expected_result:
        raise EvidenceError("fast-reopen result differs")
    if profile == "canonical" and ratio > 650_000:
        raise EvidenceError("canonical member warm ratio exceeds 0.65")
    return document


def run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, check=False, text=True,
                               capture_output=True, timeout=timeout)
    if completed.returncode != 0:
        raise EvidenceError(f"command failed ({command[0]}): {tail(completed.stderr)}")
    return completed


def run_local(arguments: argparse.Namespace) -> int:
    if arguments.workspace.exists():
        raise EvidenceError("workspace must be absent")
    arguments.workspace.mkdir(parents=True)
    primary, target = arguments.workspace / "primary", arguments.workspace / "target"
    primary.mkdir(); target.mkdir()
    published_path = arguments.workspace / "published.properties"
    source_path = arguments.workspace / "source.properties"
    replacement_path = arguments.workspace / "replacement.properties"
    published_store = arguments.workspace / "published-store"
    published_run = run(["java", "-cp", arguments.published_classpath,
                         PUBLISHED_MAIN, arguments.java_profile,
                         str(published_store), str(published_path)],
                        arguments.timeout_seconds)
    source_run = run(["java", "-cp", arguments.classpath, JAVA_MAIN, "source",
                      arguments.java_profile, str(primary), str(target),
                      str(source_path)], arguments.timeout_seconds)
    replacement_run = run([
        "java", "-cp", arguments.classpath, JAVA_MAIN, "replacement",
        arguments.java_profile, str(primary), str(target), str(source_path),
        str(replacement_path), str(arguments.duration_seconds),
    ], arguments.timeout_seconds)
    inspection = inspect_backup_directory(primary / "canonical-backup")
    cleanup = {"status": "PASS", "leftovers": [], "localArtifactsDeleted": True}
    document = build_document(
        source_sha=arguments.source_sha, source_state=arguments.source_state,
        evidence_profile="local-scaffold", java_profile=arguments.java_profile,
        duration_seconds=arguments.duration_seconds, slot=1,
        published=parse_properties(published_path), source=parse_properties(source_path),
        replacement=parse_properties(replacement_path), inspection=inspection,
        provider="local", cleanup=cleanup,
        stdout=published_run.stdout + source_run.stdout + replacement_run.stdout,
        stderr=published_run.stderr + source_run.stderr + replacement_run.stderr)
    shutil.rmtree(primary); shutil.rmtree(target); shutil.rmtree(published_store)
    write_bundle(arguments.workspace / "evidence", document)
    validate_fast_reopen_bundle(arguments.workspace / "evidence")
    print("v43FastReopenEvidence=PASS provider=local profile=local-scaffold")
    return 0


def assemble(arguments: argparse.Namespace) -> int:
    cleanup = {
        "status": "PASS", "leftovers": [],
        "sourceVmDeleted": arguments.source_vm_deleted,
        "replacementVmDeleted": arguments.replacement_vm_deleted,
        "primaryDiskDeleted": arguments.primary_disk_deleted,
        "targetDiskDeleted": arguments.target_disk_deleted,
        "stagingObjectsDeleted": arguments.staging_object_deleted,
    }
    if not all(value is True for key, value in cleanup.items()
               if key not in {"status", "leftovers"}):
        raise EvidenceError("cloud cleanup proof is incomplete")
    inspection = inspect_backup_directory(arguments.backup)
    stdout = arguments.stdout_log.read_text("utf-8", errors="replace") \
        if arguments.stdout_log else ""
    stderr = arguments.stderr_log.read_text("utf-8", errors="replace") \
        if arguments.stderr_log else ""
    document = build_document(
        source_sha=arguments.source_sha, source_state=arguments.source_state,
        evidence_profile=arguments.profile, java_profile=arguments.java_profile,
        duration_seconds=arguments.duration_seconds, slot=arguments.slot,
        published=parse_properties(arguments.published_properties),
        source=parse_properties(arguments.source_properties),
        replacement=parse_properties(arguments.replacement_properties),
        inspection=inspection, provider="gcp", cleanup=cleanup,
        stdout=stdout, stderr=stderr)
    write_bundle(arguments.output, document)
    validate_fast_reopen_bundle(arguments.output)
    print(f"v43FastReopenEvidence=PASS provider=gcp profile={arguments.profile} "
          f"slot={arguments.slot}")
    return 0


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
    local.add_argument("--timeout-seconds", type=int, required=True)
    local.add_argument("--classpath", required=True)
    local.add_argument("--published-classpath", required=True)
    assembly = commands.add_parser("assemble")
    add_common(assembly)
    assembly.add_argument("--profile", choices=("experiment", "canonical",
                                                  "failure-drill"), required=True)
    assembly.add_argument("--slot", type=int, required=True)
    assembly.add_argument("--published-properties", type=Path, required=True)
    assembly.add_argument("--source-properties", type=Path, required=True)
    assembly.add_argument("--replacement-properties", type=Path, required=True)
    assembly.add_argument("--backup", type=Path, required=True)
    assembly.add_argument("--output", type=Path, required=True)
    assembly.add_argument("--stdout-log", type=Path)
    assembly.add_argument("--stderr-log", type=Path)
    for flag in ("source-vm-deleted", "replacement-vm-deleted",
                 "primary-disk-deleted", "target-disk-deleted",
                 "staging-object-deleted"):
        assembly.add_argument(f"--{flag}", action="store_true")
    validation = commands.add_parser("validate")
    validation.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "run-local":
        return run_local(arguments)
    if arguments.command == "assemble":
        return assemble(arguments)
    value = validate_fast_reopen_bundle(arguments.bundle)
    print(f"v43FastReopenEvidenceValidation=PASS profile={value['profile']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, DerivedFormatError, OSError,
            subprocess.TimeoutExpired) as failure:
        print(f"v43FastReopenEvidence=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
