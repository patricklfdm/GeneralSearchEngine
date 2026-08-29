#!/usr/bin/env python3
"""Deterministic Cloud Benchmark V2 evidence derivation.

The remote workload remains Bash/Java.  This dependency-free Python 3.11+ utility
validates recovered V1 evidence and writes only to the sibling derived tree.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Iterable


EXIT_CONFIG = 2
EXIT_INVALID_EVIDENCE = 80
EXIT_UNSUPPORTED = 81
EXIT_CONTRADICTION = 82
EXIT_INCOMPATIBLE_SET = 83
EXIT_INCOMPARABLE = 84
EXIT_REGISTRY = 85
EXIT_UPLOAD = 86

MANIFEST_SCHEMA_VERSION = 1
METRICS_SCHEMA_VERSION = 1
FINGERPRINT_SCHEMA_VERSION = 1
SUPPORTED_RAW_SCHEMAS = {0, 1}
CANONICAL_MODES = {"full", "concurrency", "soak", "all"}
CANONICAL_PRESETS: dict[str, dict[str, Any]] = {
    "v3-production-full-v1": {
        "mode": "full",
        "threadGroups": "1,1 4,1 16,1",
        "jmh": True,
        "soak": False,
    },
    "v3-production-concurrency-v1": {
        "mode": "concurrency",
        "threadGroups": "1,1 4,1 8,1 16,1 24,1 30,1",
        "jmh": True,
        "soak": False,
    },
    "v3-production-soak-v1": {
        "mode": "soak",
        "threadGroups": "1,1 4,1 16,1",
        "jmh": False,
        "soak": True,
    },
    "v3-production-all-v1": {
        "mode": "all",
        "threadGroups": "1,1 4,1 16,1",
        "jmh": True,
        "soak": True,
    },
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
CURRENT_CONCURRENCY_RE = re.compile(
    r"^concurrent-(?:latency|throughput)-([1-9][0-9]*)-([1-9][0-9]*)$"
)
LEGACY_CONCURRENCY_RE = re.compile(
    r"^concurrent-read-write-([1-9][0-9]*)-([1-9][0-9]*)$"
)
SYNTHETIC_PERCENTILE_RE = re.compile(r"^(?:read:|write:)?p[0-9.]+$")
SET_ID_RE = re.compile(r"^gse-set-v1-[0-9a-f]{64}$")
RECEIPT_ID_RE = re.compile(r"^gse-upload-receipt-v1-[0-9a-f]{64}$")
PREFIXED_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
BASELINE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
COMPARISON_POLICY_ID = "gse-comparison-policy-v1"
COMPARISON_SCHEMA_VERSION = 1


class BenchmarkV2Error(Exception):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def fail_config(message: str) -> BenchmarkV2Error:
    return BenchmarkV2Error(message, EXIT_CONFIG)


def fail_invalid(message: str) -> BenchmarkV2Error:
    return BenchmarkV2Error(message, EXIT_INVALID_EVIDENCE)


def fail_unsupported(message: str) -> BenchmarkV2Error:
    return BenchmarkV2Error(message, EXIT_UNSUPPORTED)


def fail_contradiction(message: str) -> BenchmarkV2Error:
    return BenchmarkV2Error(message, EXIT_CONTRADICTION)


def fail_registry(message: str) -> BenchmarkV2Error:
    return BenchmarkV2Error(message, EXIT_REGISTRY)


def fail_upload(message: str) -> BenchmarkV2Error:
    return BenchmarkV2Error(message, EXIT_UPLOAD)


def canonical_json_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise fail_contradiction(f"Value is not canonical JSON: {error}") from error
    return (encoded + "\n").encode("utf-8")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise fail_contradiction(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as source:
            return json.load(source, object_pairs_hook=strict_object)
    except BenchmarkV2Error:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise fail_invalid(f"Cannot parse JSON {path}: {error}") from error


def read_properties(path: Path, *, metadata: bool = False) -> tuple[dict[str, str], list[str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise fail_invalid(f"Cannot read properties {path}: {error}") from error
    values: dict[str, str] = {}
    working_tree: list[str] = []
    inside_working_tree = False
    for number, line in enumerate(lines, 1):
        if not line or line.startswith(('#', '!')):
            continue
        if metadata and line == "working_tree_begin":
            if inside_working_tree:
                raise fail_invalid(f"Nested working-tree marker in {path}:{number}")
            inside_working_tree = True
            continue
        if metadata and line == "working_tree_end":
            if not inside_working_tree:
                raise fail_invalid(f"Unmatched working-tree marker in {path}:{number}")
            inside_working_tree = False
            continue
        if inside_working_tree:
            working_tree.append(line)
            continue
        if "=" not in line:
            raise fail_invalid(f"Invalid properties line {path}:{number}")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise fail_invalid(f"Missing or duplicate property {key!r} in {path}:{number}")
        if "\r" in value or "\n" in value:
            raise fail_invalid(f"Multiline property {key!r} in {path}:{number}")
        values[key] = value
    if inside_working_tree:
        raise fail_invalid(f"Unclosed working-tree marker in {path}")
    return values, working_tree


def require_property(values: dict[str, str], key: str, source: Path) -> str:
    value = values.get(key)
    if value is None or value == "":
        raise fail_invalid(f"Missing required property {key} in {source}")
    return value


def positive_integer(value: str, name: str) -> int:
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise fail_invalid(f"{name} must be a positive integer")
    return int(value)


def nonnegative_integer(value: str, name: str) -> int:
    if not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise fail_invalid(f"{name} must be a non-negative integer")
    return int(value)


def boolean_property(values: dict[str, str], key: str, source: Path) -> bool:
    value = require_property(values, key, source).lower()
    if value not in {"true", "false"}:
        raise fail_invalid(f"{key} must be true or false in {source}")
    return value == "true"


def verify_raw_checksums(raw_dir: Path) -> tuple[str, dict[str, str]]:
    checksum_path = raw_dir / "checksums.sha256"
    if not checksum_path.is_file():
        raise fail_invalid(f"Missing raw checksum manifest: {checksum_path}")
    try:
        checksum_bytes = checksum_path.read_bytes()
        checksum_text = checksum_bytes.decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise fail_invalid(f"Cannot read {checksum_path}: {error}") from error
    entries: dict[str, str] = {}
    for number, line in enumerate(checksum_text.splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (\./.+)", line)
        if match is None:
            raise fail_invalid(f"Invalid checksum line {checksum_path}:{number}")
        expected, relative_text = match.groups()
        relative = Path(relative_text[2:])
        if relative.is_absolute() or ".." in relative.parts or relative.name == "checksums.sha256":
            raise fail_invalid(f"Unsafe checksum path {relative_text}")
        normalized = relative.as_posix()
        if normalized in entries:
            raise fail_invalid(f"Duplicate checksum path {normalized}")
        target = raw_dir / relative
        if not target.is_file() or target.is_symlink():
            raise fail_invalid(f"Checksummed file is missing or not regular: {normalized}")
        actual = sha256_file(target)
        if actual != expected:
            raise fail_invalid(f"Raw checksum mismatch: {normalized}")
        entries[normalized] = expected
    actual_files = {
        path.relative_to(raw_dir).as_posix()
        for path in raw_dir.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    }
    if set(entries) != actual_files:
        missing = sorted(actual_files - set(entries))
        stale = sorted(set(entries) - actual_files)
        raise fail_invalid(f"Raw checksum coverage mismatch; unlisted={missing}, missing={stale}")
    for required in ("status.properties", "metadata.txt", "environment.txt"):
        if required not in entries:
            raise fail_invalid(f"Raw checksum manifest does not cover {required}")
    return sha256_bytes(checksum_bytes), entries


def snapshot_raw(raw_dir: Path) -> dict[str, str]:
    return {
        path.relative_to(raw_dir).as_posix(): sha256_file(path)
        for path in raw_dir.rglob("*")
        if path.is_file()
    }


def orchestration_path_for(raw_dir: Path, metadata: dict[str, str], supplied: Path | None) -> Path:
    if supplied is not None:
        return supplied.resolve()
    instance = metadata.get("cloud_instance_name")
    if not instance:
        raise fail_unsupported("Cloud raw evidence has no instance identity for orchestration binding")
    return raw_dir.parent / "cloud-orchestration" / f"{instance}.properties"


def validate_orchestration(
    raw_dir: Path,
    metadata: dict[str, str],
    status: dict[str, str],
    record_path: Path,
) -> tuple[dict[str, str], str, list[str]]:
    if not record_path.is_file():
        raise fail_invalid(f"Missing matching orchestration record: {record_path}")
    record, extra = read_properties(record_path)
    if extra:
        raise fail_invalid(f"Unexpected orchestration working-tree data in {record_path}")
    expected_pairs = {
        "instance_name": require_property(metadata, "cloud_instance_name", raw_dir / "metadata.txt"),
        "requested_commit": require_property(metadata, "git_commit", raw_dir / "metadata.txt"),
        "remote_commit": require_property(metadata, "git_commit", raw_dir / "metadata.txt"),
        "benchmark_mode": require_property(metadata, "mode", raw_dir / "metadata.txt"),
        "provider": require_property(metadata, "cloud_provider", raw_dir / "metadata.txt"),
        "zone": require_property(metadata, "cloud_zone", raw_dir / "metadata.txt"),
        "machine_type": require_property(metadata, "cloud_machine_type", raw_dir / "metadata.txt"),
        "resolved_image": require_property(metadata, "cloud_image", raw_dir / "metadata.txt"),
        "resolved_image_id": require_property(metadata, "cloud_image_id", raw_dir / "metadata.txt"),
        "resolved_image_self_link": require_property(metadata, "cloud_image_self_link", raw_dir / "metadata.txt"),
        "resolved_image_created_at": require_property(metadata, "cloud_image_created_at", raw_dir / "metadata.txt"),
    }
    for key, expected in expected_pairs.items():
        actual = require_property(record, key, record_path)
        if actual != expected:
            raise fail_invalid(f"Orchestration contradiction for {key}: raw={expected!r}, record={actual!r}")
    raw_provisioning = require_property(metadata, "cloud_provisioning", raw_dir / "metadata.txt").lower()
    if require_property(record, "provisioning", record_path).lower() != raw_provisioning:
        raise fail_invalid("Orchestration provisioning contradicts raw metadata")
    if metadata.get("cloud_image_family") != record.get("requested_image_family"):
        raise fail_invalid("Orchestration image family contradicts raw metadata")
    record_result_path = Path(require_property(record, "local_result_path", record_path))
    if record_result_path.name != raw_dir.name:
        raise fail_invalid("Orchestration local_result_path does not bind this raw run")
    success_values = {
        "stage": "FINISHED",
        "remote_state": "BENCHMARK_PASS",
        "remote_benchmark_exit_code": "0",
        "artifact_recovered": "true",
        "checksum_verified": "true",
        "preempted": "false",
        "run_complete": "true",
        "primary_exit_code": "0",
        "cleanup_succeeded": "true",
    }
    for key, expected in success_values.items():
        if require_property(record, key, record_path).lower() != expected.lower():
            raise fail_invalid(f"Orchestration record is not a successful finalized run: {key}")
    if status.get("status") != "PASS" or status.get("exit_code") != "0":
        raise fail_invalid("Raw status is not PASS with exit_code=0")
    warnings: list[str] = []
    if not boolean_property(record, "cleanup_attempted", record_path):
        warnings.append("orchestration cleanup was not attempted; retained VM evidence is experimental only")
    return record, sha256_file(record_path), warnings


def unavailable_number(value: Any, field: str) -> dict[str, Any]:
    if isinstance(value, bool):
        raise fail_invalid(f"Boolean is not numeric at {field}")
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            return {"sourceValue": None, "unavailableReason": "source_non_finite"}
        return {"sourceValue": value, "unavailableReason": None}
    if isinstance(value, str) and value.lower() in {"nan", "+nan", "-nan"}:
        return {"sourceValue": None, "unavailableReason": "source_nan"}
    raise fail_invalid(f"Unsupported numeric value at {field}: {value!r}")


def finite_number(value: Any, field: str) -> int | float:
    parsed = unavailable_number(value, field)
    if parsed["sourceValue"] is None:
        raise fail_invalid(f"Required score is unavailable at {field}")
    return parsed["sourceValue"]


def convert_number(value: int | float, unit: str) -> tuple[int | float, str]:
    conversions = {
        "ns/op": (1_000_000.0, "ms/op"),
        "us/op": (1_000.0, "ms/op"),
        "ms/op": (1.0, "ms/op"),
    }
    if unit in conversions:
        divisor, canonical_unit = conversions[unit]
        return value / divisor, canonical_unit
    return value, unit


def convert_optional_number(value: Any, unit: str, field: str) -> dict[str, Any]:
    parsed = unavailable_number(value, field)
    source_value = parsed["sourceValue"]
    if source_value is None:
        return {
            "sourceValue": None,
            "sourceUnit": unit,
            "canonicalValue": None,
            "canonicalUnit": convert_number(0, unit)[1],
            "unavailableReason": parsed["unavailableReason"],
        }
    canonical_value, canonical_unit = convert_number(source_value, unit)
    return {
        "sourceValue": source_value,
        "sourceUnit": unit,
        "canonicalValue": canonical_value,
        "canonicalUnit": canonical_unit,
        "unavailableReason": None,
    }


def thread_group_for(workload: str) -> dict[str, int] | None:
    match = CURRENT_CONCURRENCY_RE.fullmatch(workload) or LEGACY_CONCURRENCY_RE.fullmatch(workload)
    if match is None:
        return None
    return {"readers": int(match.group(1)), "writers": int(match.group(2))}


def supported_workload(stem: str, raw_schema: int) -> None:
    if stem in {"document-scale", "top-k-scale", "corpus-shape"}:
        return
    if CURRENT_CONCURRENCY_RE.fullmatch(stem):
        return
    if raw_schema == 0 and LEGACY_CONCURRENCY_RE.fullmatch(stem):
        return
    raise fail_unsupported(f"Unsupported JMH evidence shape: {stem}.json")


def metric_direction(mode: str, role: str, name: str) -> str:
    if name == "gc.alloc.rate.norm":
        return "lower"
    if name.startswith("gc."):
        return "diagnostic"
    if role in {"primary", "read", "write"}:
        return "higher" if mode == "thrpt" else "lower"
    return "diagnostic"


def score_statistic(mode: str, name: str) -> str:
    if name == "gc.alloc.rate.norm":
        return "allocation_per_operation"
    if name == "gc.alloc.rate":
        return "allocation_rate"
    if name == "gc.count":
        return "gc_count"
    if name == "gc.time":
        return "gc_time"
    return {"avgt": "mean_time", "sample": "sample_mean", "thrpt": "throughput"}.get(
        mode, "score"
    )


def make_metric(
    *,
    suite_schema: int,
    workload: str,
    benchmark: str,
    mode: str,
    params: dict[str, str],
    threads: int,
    group: dict[str, int] | None,
    role: str,
    name: str,
    statistic: str,
    source_file: str,
    source_field: str,
    source_value: int | float | bool | str,
    source_unit: str,
    direction: str,
    error: dict[str, Any] | None = None,
    confidence: list[dict[str, Any]] | None = None,
    percentile: float | None = None,
) -> dict[str, Any]:
    if isinstance(source_value, bool) or isinstance(source_value, str):
        canonical_value: Any = source_value
        canonical_unit = source_unit
    else:
        canonical_value, canonical_unit = convert_number(source_value, source_unit)
    identity = {
        "benchmark": benchmark,
        "metricName": name,
        "metricRole": role,
        "mode": mode,
        "parameters": dict(sorted(params.items())),
        "statistic": statistic,
        "suiteSchemaVersion": suite_schema,
        "threadGroup": group,
        "threads": threads,
        "unit": canonical_unit,
        "workload": workload,
    }
    metric: dict[str, Any] = {
        "benchmark": benchmark,
        "canonicalUnit": canonical_unit,
        "canonicalValue": canonical_value,
        "comparisonPolicyId": None,
        "direction": direction,
        "id": "m1-" + sha256_bytes(canonical_json_bytes(identity)),
        "identity": identity,
        "mode": mode,
        "parameters": dict(sorted(params.items())),
        "source": {"field": source_field, "file": source_file},
        "sourceUnit": source_unit,
        "sourceValue": source_value,
        "statistic": statistic,
        "threadGroup": group,
        "threads": threads,
        "workload": workload,
    }
    if error is not None:
        metric["error"] = error
    if confidence is not None:
        metric["confidence"] = confidence
    if percentile is not None:
        metric["percentile"] = percentile
        metric["percentileSemantics"] = "sampled_operation_latency"
    return metric


def jmh_configuration(entry: dict[str, Any], workload: str) -> dict[str, Any]:
    required = (
        "jmhVersion",
        "benchmark",
        "mode",
        "threads",
        "forks",
        "warmupIterations",
        "warmupTime",
        "warmupBatchSize",
        "measurementIterations",
        "measurementTime",
        "measurementBatchSize",
        "params",
    )
    for key in required:
        if key not in entry:
            raise fail_invalid(f"JMH entry in {workload}.json is missing {key}")
    if not isinstance(entry["params"], dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in entry["params"].items()
    ):
        raise fail_invalid(f"JMH params in {workload}.json must be string properties")
    for key in (
        "threads",
        "forks",
        "warmupIterations",
        "warmupBatchSize",
        "measurementIterations",
        "measurementBatchSize",
    ):
        if not isinstance(entry[key], int) or isinstance(entry[key], bool) or entry[key] < 0:
            raise fail_invalid(f"JMH {key} in {workload}.json must be a non-negative integer")
    return {
        "benchmark": entry["benchmark"],
        "forks": entry["forks"],
        "jmhVersion": entry["jmhVersion"],
        "measurementBatchSize": entry["measurementBatchSize"],
        "measurementIterations": entry["measurementIterations"],
        "measurementTime": entry["measurementTime"],
        "mode": entry["mode"],
        "parameters": dict(sorted(entry["params"].items())),
        "threadGroup": thread_group_for(workload),
        "threads": entry["threads"],
        "warmupBatchSize": entry["warmupBatchSize"],
        "warmupIterations": entry["warmupIterations"],
        "warmupTime": entry["warmupTime"],
        "workload": workload,
    }


def validate_jmh_metadata(config: dict[str, Any], metadata: dict[str, str], raw_schema: int) -> None:
    if raw_schema != 1:
        return
    expected_integers = {
        "forks": "jmh_forks",
        "warmupIterations": "jmh_warmups",
        "measurementIterations": "jmh_iterations",
    }
    for config_key, metadata_key in expected_integers.items():
        expected = positive_integer(require_property(metadata, metadata_key, Path("metadata.txt")), metadata_key)
        if config[config_key] != expected:
            raise fail_invalid(f"JMH {config_key} contradicts raw metadata")
    expected_duration = require_property(metadata, "jmh_duration", Path("metadata.txt")).replace(" ", "")
    if str(config["warmupTime"]).replace(" ", "") != expected_duration:
        raise fail_invalid("JMH warmup time contradicts raw metadata")
    if str(config["measurementTime"]).replace(" ", "") != expected_duration:
        raise fail_invalid("JMH measurement time contradicts raw metadata")


def extract_jmh(
    raw_dir: Path, raw_schema: int, suite_schema: int, metadata: dict[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metrics: list[dict[str, Any]] = []
    configurations: list[dict[str, Any]] = []
    ignored_json_names = {"benchmark-manifest.json", "normalized-metrics.json", "report.json"}
    for path in sorted(raw_dir.glob("*.json")):
        if path.name in ignored_json_names:
            raise fail_invalid(f"Derived JSON must not exist inside raw evidence: {path.name}")
        workload = path.stem
        supported_workload(workload, raw_schema)
        entries = read_json(path)
        if not isinstance(entries, list) or not entries:
            raise fail_invalid(f"JMH file must contain a non-empty array: {path}")
        for entry_index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise fail_invalid(f"JMH entry {entry_index} in {path} is not an object")
            config = jmh_configuration(entry, workload)
            validate_jmh_metadata(config, metadata, raw_schema)
            configurations.append(config)
            benchmark = config["benchmark"]
            mode = config["mode"]
            if mode not in {"avgt", "sample", "thrpt"}:
                raise fail_unsupported(f"Unsupported JMH mode {mode!r} in {path.name}")
            params = config["parameters"]
            threads = config["threads"]
            group = config["threadGroup"]
            primary = entry.get("primaryMetric")
            secondary = entry.get("secondaryMetrics", {})
            if not isinstance(primary, dict) or not isinstance(secondary, dict):
                raise fail_invalid(f"Invalid JMH metric objects in {path.name}")
            metric_objects: list[tuple[str, str, dict[str, Any], str]] = [
                ("primary", "primary", primary, "primaryMetric")
            ]
            for name, metric_object in sorted(secondary.items()):
                if SYNTHETIC_PERCENTILE_RE.fullmatch(name):
                    continue
                if name not in {"read", "write", "gc.alloc.rate", "gc.alloc.rate.norm", "gc.count", "gc.time"}:
                    raise fail_unsupported(f"Unsupported JMH secondary metric {name!r} in {path.name}")
                if not isinstance(metric_object, dict):
                    raise fail_invalid(f"JMH secondary metric {name!r} is not an object")
                role = name if name in {"read", "write"} else "profiler"
                metric_objects.append((role, name, metric_object, f"secondaryMetrics.{name}"))
            for role, name, metric_object, field_prefix in metric_objects:
                unit = metric_object.get("scoreUnit")
                if not isinstance(unit, str) or not unit:
                    raise fail_invalid(f"Missing score unit at {path.name}:{field_prefix}")
                score = finite_number(metric_object.get("score"), f"{path.name}:{field_prefix}.score")
                error = convert_optional_number(
                    metric_object.get("scoreError"), unit, f"{path.name}:{field_prefix}.scoreError"
                )
                confidence_value = metric_object.get("scoreConfidence")
                if not isinstance(confidence_value, list) or len(confidence_value) != 2:
                    raise fail_invalid(f"Invalid scoreConfidence at {path.name}:{field_prefix}")
                confidence = [
                    convert_optional_number(value, unit, f"{path.name}:{field_prefix}.scoreConfidence")
                    for value in confidence_value
                ]
                metrics.append(
                    make_metric(
                        suite_schema=suite_schema,
                        workload=workload,
                        benchmark=benchmark,
                        mode=mode,
                        params=params,
                        threads=threads,
                        group=group,
                        role=role,
                        name=name,
                        statistic=score_statistic(mode, name),
                        source_file=path.name,
                        source_field=f"{field_prefix}.score",
                        source_value=score,
                        source_unit=unit,
                        direction=metric_direction(mode, role, name),
                        error=error,
                        confidence=confidence,
                    )
                )
                if mode == "sample" and role in {"primary", "read", "write"}:
                    percentiles = metric_object.get("scorePercentiles")
                    if not isinstance(percentiles, dict) or not percentiles:
                        raise fail_invalid(f"Sample metric lacks scorePercentiles at {path.name}:{field_prefix}")
                    parsed_percentiles: list[tuple[float, str, Any]] = []
                    for percentile_text, percentile_value in percentiles.items():
                        try:
                            percentile = float(percentile_text)
                        except ValueError as error_value:
                            raise fail_invalid(f"Invalid JMH percentile {percentile_text!r}") from error_value
                        if not math.isfinite(percentile) or percentile < 0 or percentile > 100:
                            raise fail_invalid(f"JMH percentile is outside 0..100: {percentile_text!r}")
                        parsed_percentiles.append((percentile, percentile_text, percentile_value))
                    for percentile, percentile_text, percentile_value in sorted(parsed_percentiles):
                        value = finite_number(
                            percentile_value,
                            f"{path.name}:{field_prefix}.scorePercentiles.{percentile_text}",
                        )
                        metrics.append(
                            make_metric(
                                suite_schema=suite_schema,
                                workload=workload,
                                benchmark=benchmark,
                                mode=mode,
                                params=params,
                                threads=threads,
                                group=group,
                                role=role,
                                name=name,
                                statistic=f"sample_percentile_{percentile_text}",
                                source_file=path.name,
                                source_field=f"{field_prefix}.scorePercentiles.{percentile_text}",
                                source_value=value,
                                source_unit=unit,
                                direction="lower",
                                percentile=percentile,
                            )
                        )
    return metrics, configurations


def parse_property_scalar(value: str, field: str) -> int | float | bool | str:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value):
        return int(value)
    try:
        number = float(value)
    except ValueError:
        return value
    if not math.isfinite(number):
        raise fail_invalid(f"Non-finite property value at {field}")
    return number


def soak_metric_semantics(key: str) -> tuple[str, str, str] | None:
    if key.endswith("_ops_per_second"):
        return "throughput", "ops/s", "higher"
    latency = re.search(r"_latency_(p50|p95|p99|max)_us$", key)
    if latency:
        statistic = "maximum" if latency.group(1) == "max" else f"sample_percentile_{latency.group(1)[1:]}"
        return statistic, "us/op", "lower"
    if key.endswith("_mean_latency_us"):
        return "sample_mean", "us/op", "lower"
    if key.endswith("_mean_latency_ns"):
        return "sample_mean", "ns/op", "lower"
    if key.endswith("_drift_pct"):
        return "diagnostic_drift", "percent", "diagnostic"
    if key.endswith("_bytes"):
        return "diagnostic_bytes", "bytes", "diagnostic"
    if key.endswith("_time_ms"):
        return "diagnostic_time", "ms", "diagnostic"
    if key.endswith("_seconds") or key.endswith("_elapsed_s"):
        return "diagnostic_time", "s", "diagnostic"
    if key in {"errors", "writer_queue_maximum", "writer_queue_nonzero_samples"}:
        return "count", "count", "categorical" if key == "errors" else "lower"
    if key.endswith(("_operations", "_samples", "_count", "_cycles", "_depth", "_version")):
        return "counter", "count", "diagnostic"
    if key.startswith("flag_") or key.startswith("readiness_") or key in {
        "review_required",
        "measurement_started",
        "handoff_within_30_seconds",
        "corpus_changed",
    }:
        return "decision", "boolean", "categorical"
    if key in {"analysis_status", "stabilization_status", "final_phase_state", "status"}:
        return "decision", "text", "categorical"
    return None


def include_soak_property(filename: str, key: str) -> bool:
    if key.startswith(("configured_", "bucket_", "window_")) or key in {
        "analysis_version",
        "jfr_output",
        "loaded_corpus_sha256",
        "initial_corpus_sha256",
        "final_corpus_sha256",
        "post_corpus_sha256",
        "investigation_cell",
        "stabilization_purpose",
    }:
        return False
    if filename != "soak-summary.properties" and key.startswith("summary_"):
        return False
    return soak_metric_semantics(key) is not None


def extract_soak(
    raw_dir: Path, suite_schema: int
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    soak_dir = raw_dir / "soak"
    if not soak_dir.is_dir():
        return [], None
    config_path = soak_dir / "soak-config.properties"
    summary_path = soak_dir / "soak-summary.properties"
    if not config_path.is_file() or not summary_path.is_file():
        raise fail_invalid("Soak evidence requires soak-config.properties and soak-summary.properties")
    config, _ = read_properties(config_path)
    if config.get("status") != "CONFIGURED":
        raise fail_invalid("Soak configuration is not CONFIGURED")
    fingerprint_config = {
        key: parse_property_scalar(value, f"{config_path.name}:{key}")
        for key, value in sorted(config.items())
        if key not in {"status", "jfr_output"}
    }
    params = {key: config[key] for key in sorted(fingerprint_config)}
    readers = nonnegative_integer(config.get("readers", ""), "soak readers")
    writers = nonnegative_integer(config.get("writers", ""), "soak writers")
    metrics: list[dict[str, Any]] = []
    property_paths = sorted(soak_dir.glob("soak-*.properties"))
    for path in property_paths:
        if path.name == "soak-config.properties":
            continue
        values, _ = read_properties(path)
        for key, raw_value in sorted(values.items()):
            if not include_soak_property(path.name, key):
                continue
            semantics = soak_metric_semantics(key)
            assert semantics is not None
            statistic, unit, direction = semantics
            value = parse_property_scalar(raw_value, f"{path.name}:{key}")
            metrics.append(
                make_metric(
                    suite_schema=suite_schema,
                    workload=path.stem,
                    benchmark="io.github.patricklfdm.generalsearch.benchmark.jmh.V3ProductionSoak",
                    mode="soak",
                    params=params,
                    threads=readers + writers,
                    group={
                        "readers": readers,
                        "writers": writers,
                    },
                    role=path.stem,
                    name=key,
                    statistic=statistic,
                    source_file=f"soak/{path.name}",
                    source_field=key,
                    source_value=value,
                    source_unit=unit,
                    direction=direction,
                )
            )
    summary, _ = read_properties(summary_path)
    if summary.get("status") != "PASS" or summary.get("errors") != "0":
        raise fail_invalid("Soak summary is not PASS with zero errors")
    return metrics, fingerprint_config


def reject_duplicate_metrics(metrics: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for metric in metrics:
        metric_id = metric["id"]
        if metric_id in by_id:
            raise fail_contradiction(f"Duplicate normalized metric identity: {metric_id}")
        by_id[metric_id] = metric
    return [by_id[key] for key in sorted(by_id)]


def fingerprint(payload: dict[str, Any]) -> str:
    envelope = {"fingerprintSchemaVersion": FINGERPRINT_SCHEMA_VERSION, "payload": payload}
    return "sha256:" + sha256_bytes(canonical_json_bytes(envelope))


def validate_benchmark_preset(
    preset_id: str | None,
    mode: str,
    metadata: dict[str, str],
    jmh_configs: list[dict[str, Any]],
    soak_config: dict[str, Any] | None,
) -> None:
    if preset_id is None:
        return
    preset = CANONICAL_PRESETS.get(preset_id)
    if preset is None:
        raise fail_unsupported(f"Unsupported benchmark preset: {preset_id}")
    if mode != preset["mode"]:
        raise fail_invalid(f"Benchmark preset {preset_id} contradicts mode {mode}")
    expected_metadata = {
        "concurrency_documents": "100000",
        "concurrency_thread_groups": preset["threadGroups"],
    }
    if preset["jmh"]:
        expected_metadata.update(
            {
                "jmh_forks": "2",
                "jmh_warmups": "3",
                "jmh_iterations": "5",
                "jmh_duration": "1s",
            }
        )
        if not jmh_configs:
            raise fail_invalid(f"Benchmark preset {preset_id} requires JMH evidence")
    elif jmh_configs:
        raise fail_invalid(f"Benchmark preset {preset_id} forbids JMH evidence")
    for key, expected in expected_metadata.items():
        if metadata.get(key) != expected:
            raise fail_invalid(
                f"Benchmark preset {preset_id} requires {key}={expected}"
            )
    if preset["soak"]:
        if soak_config is None:
            raise fail_invalid(f"Benchmark preset {preset_id} requires soak evidence")
        expected_soak: dict[str, Any] = {
            "corpus_profile": "zipf-en-medium-4",
            "documents": 100000,
            "index_cycles": True,
            "readers": 16,
            "sample_seconds": 1,
            "seconds": 1800,
            "top_k": 10,
            "update_mode": "revision",
            "writers": 1,
        }
        for key, expected in expected_soak.items():
            if soak_config.get(key) != expected:
                raise fail_invalid(
                    f"Benchmark preset {preset_id} requires soak {key}={expected}"
                )
    elif soak_config is not None:
        raise fail_invalid(f"Benchmark preset {preset_id} forbids soak evidence")


def environment_from_metadata(
    metadata: dict[str, str], raw_schema: int, warnings: list[str]
) -> tuple[dict[str, Any], str | None, bool]:
    try:
        jvm_options = shlex.split(metadata.get("jvm_options", ""))
    except ValueError as error:
        raise fail_invalid(f"Cannot parse ordered jvm_options: {error}") from error
    common = {
        "provider": metadata.get("cloud_provider"),
        "zone": metadata.get("cloud_zone"),
        "machineType": metadata.get("cloud_machine_type"),
        "provisioning": metadata.get("cloud_provisioning", "").lower() or None,
        "image": {
            "project": metadata.get("cloud_image_project"),
            "family": metadata.get("cloud_image_family"),
            "resolvedName": metadata.get("cloud_image"),
            "id": metadata.get("cloud_image_id"),
            "selfLink": metadata.get("cloud_image_self_link"),
            "createdAt": metadata.get("cloud_image_created_at"),
        },
        "jvmOptions": jvm_options,
    }
    if raw_schema == 0:
        common.update(
            {
                "cpu": {
                    "vendor": None,
                    "model": None,
                    "logicalCpus": int(metadata["logical_cpus"]) if metadata.get("logical_cpus", "").isdigit() else None,
                    "sockets": None,
                    "coresPerSocket": None,
                    "threadsPerCore": None,
                },
                "memoryBytes": None,
                "kernelRelease": None,
                "java": {
                    "vendor": None,
                    "runtimeVersion": None,
                    "vmName": None,
                    "vmVersion": None,
                },
            }
        )
        warnings.append("legacy raw schema 0 lacks strict environment facts; no environment fingerprint was created")
        return common, None, False
    required_strings = (
        "cloud_provider",
        "cloud_zone",
        "cloud_machine_type",
        "cloud_provisioning",
        "cloud_image_project",
        "cloud_image",
        "cloud_image_id",
        "kernel_release",
        "cpu_vendor",
        "cpu_model",
        "java_vendor",
        "java_runtime_version",
        "java_vm_name",
        "java_vm_version",
        "jvm_options",
    )
    for key in required_strings:
        require_property(metadata, key, Path("metadata.txt"))
    numeric = {
        "logicalCpus": positive_integer(require_property(metadata, "logical_cpus", Path("metadata.txt")), "logical_cpus"),
        "sockets": positive_integer(require_property(metadata, "cpu_sockets", Path("metadata.txt")), "cpu_sockets"),
        "coresPerSocket": positive_integer(
            require_property(metadata, "cpu_cores_per_socket", Path("metadata.txt")), "cpu_cores_per_socket"
        ),
        "threadsPerCore": positive_integer(
            require_property(metadata, "cpu_threads_per_core", Path("metadata.txt")), "cpu_threads_per_core"
        ),
    }
    memory_bytes = positive_integer(require_property(metadata, "memory_bytes", Path("metadata.txt")), "memory_bytes")
    common.update(
        {
            "cpu": {
                "vendor": metadata["cpu_vendor"],
                "model": metadata["cpu_model"],
                **numeric,
            },
            "memoryBytes": memory_bytes,
            "kernelRelease": metadata["kernel_release"],
            "java": {
                "vendor": metadata["java_vendor"],
                "runtimeVersion": metadata["java_runtime_version"],
                "vmName": metadata["java_vm_name"],
                "vmVersion": metadata["java_vm_version"],
            },
        }
    )
    return common, fingerprint(environment_fingerprint_payload(common)), True


def environment_fingerprint_payload(environment: dict[str, Any]) -> dict[str, Any]:
    """Return exactly the stable fields bound by an environment fingerprint."""
    image = environment.get("image", {})
    return {
        "provider": environment.get("provider"),
        "zone": environment.get("zone"),
        "machineType": environment.get("machineType"),
        "provisioning": environment.get("provisioning"),
        "cpu": environment.get("cpu"),
        "memoryBytes": environment.get("memoryBytes"),
        "image": {
            "project": image.get("project"),
            "resolvedName": image.get("resolvedName"),
            "id": image.get("id"),
        },
        "kernelRelease": environment.get("kernelRelease"),
        "java": environment.get("java"),
        "jvmOptions": environment.get("jvmOptions"),
    }


def write_stable_files(output_dir: Path, files: dict[str, bytes]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        destination = output_dir / name
        if destination.exists() and destination.read_bytes() != content:
            raise fail_contradiction(f"Existing derived artifact differs: {destination}")
    for name, content in files.items():
        destination = output_dir / name
        if destination.exists():
            continue
        handle, temporary_name = tempfile.mkstemp(prefix=f".{name}.", dir=output_dir)
        try:
            with os.fdopen(handle, "wb") as target:
                target.write(content)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary_name, destination)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)


def derive_manifest(
    raw_directory: Path,
    *,
    orchestration_record: Path | None = None,
    output_directory: Path | None = None,
    evidence_profile: str = "experiment",
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    raw_dir = raw_directory.resolve()
    if not raw_dir.is_dir():
        raise fail_config(f"Raw run directory does not exist: {raw_dir}")
    if evidence_profile not in {"experiment", "canonical"}:
        raise fail_config("Evidence profile must be experiment or canonical")
    raw_before = snapshot_raw(raw_dir)
    raw_checksum_digest, _ = verify_raw_checksums(raw_dir)
    metadata_path = raw_dir / "metadata.txt"
    status_path = raw_dir / "status.properties"
    metadata, working_tree = read_properties(metadata_path, metadata=True)
    status, _ = read_properties(status_path)
    raw_schema_text = metadata.get("evidence_schema_version", "0")
    if not raw_schema_text.isdigit():
        raise fail_invalid("evidence_schema_version must be a non-negative integer")
    raw_schema = int(raw_schema_text)
    if raw_schema not in SUPPORTED_RAW_SCHEMAS:
        raise fail_unsupported(f"Unsupported raw evidence schema: {raw_schema}")
    if raw_schema == 1:
        if metadata.get("benchmark_suite") != "v3-production":
            raise fail_invalid("Raw benchmark_suite must be v3-production")
        require_property(metadata, "source_repository", metadata_path)
        suite_schema = positive_integer(
            require_property(metadata, "benchmark_suite_schema_version", metadata_path),
            "benchmark_suite_schema_version",
        )
    else:
        suite_schema = 0
    commit = require_property(metadata, "git_commit", metadata_path)
    if not COMMIT_RE.fullmatch(commit):
        raise fail_invalid("git_commit must be an exact 40-character lowercase SHA")
    mode = require_property(metadata, "mode", metadata_path)
    if mode not in {"quick", "full", "concurrency", "soak", "investigation", "stabilized-investigation", "all"}:
        raise fail_unsupported(f"Unsupported benchmark mode: {mode}")
    if status.get("mode") != mode:
        raise fail_invalid("Status mode contradicts metadata mode")
    if evidence_profile == "canonical" and mode not in CANONICAL_MODES:
        raise fail_config(f"Mode {mode} is never canonical eligible")
    record_path = orchestration_path_for(raw_dir, metadata, orchestration_record)
    record, record_digest, warnings = validate_orchestration(raw_dir, metadata, status, record_path)
    if working_tree:
        warnings.append("raw source working tree was dirty")
    environment, environment_fingerprint, strict_environment = environment_from_metadata(
        metadata, raw_schema, warnings
    )
    jmh_metrics, jmh_configs = extract_jmh(raw_dir, raw_schema, suite_schema, metadata)
    soak_metrics, soak_config = extract_soak(raw_dir, suite_schema)
    preset_id = metadata.get("benchmark_preset_id") or None
    validate_benchmark_preset(preset_id, mode, metadata, jmh_configs, soak_config)
    metrics = reject_duplicate_metrics([*jmh_metrics, *soak_metrics])
    if not metrics:
        raise fail_unsupported("Raw run contains no supported benchmark metrics")
    observed_thread_groups = {
        (config["threadGroup"]["readers"], config["threadGroup"]["writers"])
        for config in jmh_configs
        if config["threadGroup"] is not None
    }
    metadata_thread_groups: list[dict[str, int]] = []
    for group_text in metadata.get("concurrency_thread_groups", "").split():
        match = re.fullmatch(r"([1-9][0-9]*),([1-9][0-9]*)", group_text)
        if match is None:
            raise fail_invalid(f"Invalid metadata concurrency thread group: {group_text!r}")
        metadata_thread_groups.append(
            {"readers": int(match.group(1)), "writers": int(match.group(2))}
        )
    if observed_thread_groups:
        if not metadata_thread_groups:
            raise fail_invalid("Concurrency JMH evidence lacks metadata thread groups")
        expected_thread_groups = {
            (group["readers"], group["writers"]) for group in metadata_thread_groups
        }
        if observed_thread_groups != expected_thread_groups:
            raise fail_invalid("JMH concurrency thread groups contradict raw metadata")
    logical_workloads = {config["workload"] for config in jmh_configs}
    if soak_config is not None:
        logical_workloads.add("soak")
    benchmark_config_payload = {
        "jmhEntries": sorted(jmh_configs, key=lambda value: canonical_json_bytes(value)),
        "mode": mode,
        "orderedThreadGroups": metadata_thread_groups,
        "soak": soak_config,
        "soakProfile": metadata.get("soak_profile"),
        "suite": "v3-production",
        "suiteSchemaVersion": suite_schema,
        "workloads": sorted(logical_workloads),
    }
    if preset_id is not None:
        benchmark_config_payload["presetId"] = preset_id
    benchmark_config_fingerprint = fingerprint(benchmark_config_payload)
    cleanup_attempted = boolean_property(record, "cleanup_attempted", record_path)
    canonical_reasons: list[str] = []
    if raw_schema != 1:
        canonical_reasons.append("raw schema 1 is required")
    if not strict_environment or environment_fingerprint is None:
        canonical_reasons.append("strict environment fingerprint is required")
    if environment.get("provisioning") != "standard":
        canonical_reasons.append("Standard provisioning is required")
    if working_tree:
        canonical_reasons.append("clean source is required")
    if not cleanup_attempted:
        canonical_reasons.append("ordinary cleanup proof is required")
    if mode not in CANONICAL_MODES:
        canonical_reasons.append(f"mode {mode} is experiment-only")
    if preset_id is None:
        canonical_reasons.append("versioned benchmark preset is required")
    evidence_reasons = list(canonical_reasons)
    if evidence_profile == "experiment":
        evidence_reasons.append("evidence profile is experiment")
    canonical_eligible = not canonical_reasons and evidence_profile == "canonical"
    if evidence_profile == "canonical" and canonical_reasons:
        raise fail_invalid("Canonical evidence requirements failed: " + "; ".join(canonical_reasons))
    metrics_document = {
        "kind": "normalized-benchmark-metrics",
        "metrics": metrics,
        "runId": raw_dir.name,
        "schemaVersion": METRICS_SCHEMA_VERSION,
        "suite": {"name": "v3-production", "schemaVersion": suite_schema},
    }
    metrics_bytes = canonical_json_bytes(metrics_document)
    metrics_digest = sha256_bytes(metrics_bytes)
    manifest = {
        "benchmark": {
            "configurationSummary": {
                "jmhEntryCount": len(jmh_configs),
                "soakConfigured": soak_config is not None,
                "workloads": benchmark_config_payload["workloads"],
            },
            "mode": mode,
            "presetId": preset_id,
        },
        "benchmarkConfigFingerprint": benchmark_config_fingerprint,
        "canonicalEligibility": canonical_eligible,
        "canonicalIneligibilityReasons": sorted(evidence_reasons),
        "environment": environment,
        "environmentFingerprint": environment_fingerprint,
        "evidence": {
            "artifactRecovered": True,
            "checksumVerified": True,
            "cleanupAttempted": cleanup_attempted,
            "cleanupSucceeded": True,
            "interrupted": False,
            "orchestrationRecordSha256": record_digest,
            "rawChecksumManifestSha256": raw_checksum_digest,
            "rawRunId": raw_dir.name,
        },
        "evidenceProfile": evidence_profile,
        "kind": "benchmark-run",
        "metrics": {
            "count": len(metrics),
            "path": "normalized-metrics.json",
            "schemaVersion": METRICS_SCHEMA_VERSION,
            "sha256": metrics_digest,
        },
        "project": "GeneralSearchEngine",
        "runId": raw_dir.name,
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "source": {
            "branch": metadata.get("git_branch") or None,
            "commit": commit,
            "repository": metadata.get("source_repository"),
        },
        "status": "VALID_CANONICAL_MEMBER" if canonical_eligible else "VALID_EXPERIMENT",
        "suite": {
            "name": metadata.get("benchmark_suite", "v3-production"),
            "rawEvidenceSchemaVersion": raw_schema,
            "schemaVersion": suite_schema,
        },
        "warnings": sorted(set(warnings)),
    }
    manifest_bytes = canonical_json_bytes(manifest)
    derived_checksums = (
        f"{sha256_bytes(manifest_bytes)}  benchmark-manifest.json\n"
        f"{metrics_digest}  normalized-metrics.json\n"
    ).encode("utf-8")
    if output_directory is None:
        output_dir = raw_dir.parent / "derived" / "runs" / raw_dir.name / "v1"
    else:
        output_dir = output_directory.resolve()
    try:
        output_dir.relative_to(raw_dir)
    except ValueError:
        pass
    else:
        raise fail_config("Derived output must not be inside the immutable raw run directory")
    write_stable_files(
        output_dir,
        {
            "benchmark-manifest.json": manifest_bytes,
            "normalized-metrics.json": metrics_bytes,
            "derived-checksums.sha256": derived_checksums,
        },
    )
    if snapshot_raw(raw_dir) != raw_before:
        raise fail_contradiction("Raw evidence changed during derivation")
    return output_dir, manifest, metrics_document


SET_PLAN_SCHEMA_VERSION = 1
SET_CHECKPOINT_SCHEMA_VERSION = 1
SET_MANIFEST_SCHEMA_VERSION = 1
SET_METRICS_SCHEMA_VERSION = 1
SET_AUDIT_SCHEMA_VERSION = 1
INFRASTRUCTURE_EXITS = {10, 20, 40, 50, 60, 70}
EVIDENCE_EXITS = {80, 81, 82}
SLOT_STATES = {
    "PENDING",
    "RUNNING",
    "VALID_MEMBER",
    "INFRASTRUCTURE_INVALID",
    "BENCHMARK_FAILURE",
    "CONFIGURATION_FAILURE",
    "EVIDENCE_INVALID",
    "UNRESOLVED",
}


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary_name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def atomic_write_json(path: Path, value: Any, *, immutable: bool = False) -> None:
    content = canonical_json_bytes(value)
    if path.exists():
        if immutable and path.read_bytes() == content:
            return
        if immutable:
            raise fail_contradiction(f"Immutable state already differs: {path}")
    atomic_write_bytes(path, content)


def parse_controls(items: list[str]) -> dict[str, str]:
    controls: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise fail_config(f"Set control must be KEY=VALUE: {item!r}")
        key, value = item.split("=", 1)
        if not re.fullmatch(r"[a-z][A-Za-z0-9]*", key) or key in controls:
            raise fail_config(f"Invalid or duplicate set control: {key!r}")
        if "\n" in value or "\r" in value:
            raise fail_config(f"Set control {key} must be a single line")
        controls[key] = value
    return dict(sorted(controls.items()))


def validate_set_plan_inputs(
    profile: str,
    repeats: int,
    mode: str,
    preset_id: str | None,
    repository: str,
    commit: str,
    controls: dict[str, str],
) -> dict[str, Any]:
    if profile not in {"canonical", "experiment"}:
        raise fail_config("Set evidence profile must be canonical or experiment")
    minimum = 3 if profile == "canonical" else 1
    if repeats < minimum or repeats > 10:
        raise fail_config(f"{profile} set repeats must be between {minimum} and 10")
    if mode not in {"quick", "full", "concurrency", "soak", "investigation", "stabilized-investigation", "all"}:
        raise fail_config(f"Unsupported V1 benchmark mode: {mode}")
    if not repository or "\n" in repository or "\r" in repository:
        raise fail_config("Source repository must be a non-empty single line")
    if not COMMIT_RE.fullmatch(commit):
        raise fail_config("Set source commit must be an exact lowercase 40-character SHA")
    if profile == "canonical":
        expected = f"v3-production-{mode}-v1"
        if mode not in CANONICAL_MODES:
            raise fail_config(f"Mode {mode} is not canonical set eligible")
        if preset_id != expected or preset_id not in CANONICAL_PRESETS:
            raise fail_config(f"Canonical mode {mode} requires preset {expected}")
        if controls.get("provisioning", "").lower() != "standard":
            raise fail_config("Canonical sets require Standard provisioning")
        for key in (
            "project",
            "zone",
            "machineType",
            "imageProject",
            "imageFamily",
            "resolvedImage",
            "resolvedImageId",
            "resolvedImageSelfLink",
            "resolvedImageCreatedAt",
            "jvmOptions",
            "bootDiskSize",
            "bootDiskType",
            "useIap",
            "externalIp",
            "maxRunDuration",
        ):
            if not controls.get(key):
                raise fail_config(f"Canonical set control {key} is required")
        if not controls.get("network") and not controls.get("subnet"):
            raise fail_config("Canonical set requires a frozen network or subnet")
    elif preset_id is not None:
        if preset_id not in CANONICAL_PRESETS:
            raise fail_config(f"Unknown set preset: {preset_id}")
        if CANONICAL_PRESETS[preset_id]["mode"] != mode:
            raise fail_config(f"Set mode {mode} is incompatible with preset {preset_id}")
    return {
        "controls": controls,
        "evidenceProfile": profile,
        "kind": "benchmark-set-plan",
        "mode": mode,
        "presetId": preset_id,
        "repeats": repeats,
        "schemaVersion": SET_PLAN_SCHEMA_VERSION,
        "slots": list(range(1, repeats + 1)),
        "source": {"commit": commit, "repository": repository},
        "stateSchemas": {
            "attemptAudit": SET_AUDIT_SCHEMA_VERSION,
            "checkpoint": SET_CHECKPOINT_SCHEMA_VERSION,
            "manifest": SET_MANIFEST_SCHEMA_VERSION,
            "metrics": SET_METRICS_SCHEMA_VERSION,
        },
    }


def initial_checkpoint(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "currentAttempt": None,
        "finalSetId": None,
        "kind": "benchmark-set-checkpoint",
        "nextPendingSlot": 1,
        "planSha256": sha256_bytes(canonical_json_bytes(plan)),
        "revision": 0,
        "schemaVersion": SET_CHECKPOINT_SCHEMA_VERSION,
        "slots": [
            {"attemptCount": 0, "selectedAttempt": None, "slot": slot, "state": "PENDING"}
            for slot in plan["slots"]
        ],
        "state": "READY",
    }


def load_set_workspace(workspace: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    root = workspace.resolve()
    plan = read_json(root / "set-plan.json")
    checkpoint = read_json(root / "checkpoint.json")
    if not isinstance(plan, dict) or plan.get("kind") != "benchmark-set-plan" or plan.get("schemaVersion") != 1:
        raise fail_invalid("Unsupported or invalid set plan")
    if not isinstance(checkpoint, dict) or checkpoint.get("kind") != "benchmark-set-checkpoint" or checkpoint.get("schemaVersion") != 1:
        raise fail_invalid("Unsupported or invalid set checkpoint")
    expected = sha256_bytes(canonical_json_bytes(plan))
    if checkpoint.get("planSha256") != expected:
        raise fail_contradiction("Checkpoint does not bind the immutable set plan")
    return root, plan, checkpoint


def checkpoint_slot(checkpoint: dict[str, Any], number: int) -> dict[str, Any]:
    slots = checkpoint.get("slots")
    if not isinstance(slots, list) or number < 1 or number > len(slots):
        raise fail_config(f"Slot {number} is outside the declared set")
    slot = slots[number - 1]
    if slot.get("slot") != number or slot.get("state") not in SLOT_STATES:
        raise fail_contradiction("Checkpoint slot structure is invalid")
    return slot


def save_checkpoint(root: Path, checkpoint: dict[str, Any]) -> None:
    checkpoint["revision"] = int(checkpoint["revision"]) + 1
    atomic_write_json(root / "checkpoint.json", checkpoint)


def initialize_set_workspace(
    workspace: Path,
    profile: str,
    repeats: int,
    mode: str,
    preset_id: str | None,
    repository: str,
    commit: str,
    controls: dict[str, str],
) -> tuple[Path, dict[str, Any]]:
    plan = validate_set_plan_inputs(profile, repeats, mode, preset_id, repository, commit, controls)
    root = workspace.resolve()
    if root.exists():
        raise fail_config(f"Set workspace already exists: {root}")
    root.mkdir(parents=True)
    atomic_write_json(root / "set-plan.json", plan, immutable=True)
    atomic_write_json(root / "checkpoint.json", initial_checkpoint(plan))
    return root, plan


def begin_set_attempt(workspace: Path, slot_number: int) -> dict[str, Any]:
    root, _, checkpoint = load_set_workspace(workspace)
    if checkpoint["state"] in {"COMPLETE", "INCOMPATIBLE", "UNRESOLVED", "BLOCKED_FAILURE"}:
        raise fail_config(f"Cannot begin an attempt while set state is {checkpoint['state']}")
    if checkpoint.get("currentAttempt") is not None:
        raise fail_config("A set attempt is already RUNNING")
    slot = checkpoint_slot(checkpoint, slot_number)
    if any(item["state"] == "VALID_MEMBER" for item in checkpoint["slots"][slot_number:]):
        raise fail_contradiction("A later slot has already completed")
    replacement = slot["state"] == "INFRASTRUCTURE_INVALID"
    if slot["state"] not in {"PENDING", "INFRASTRUCTURE_INVALID"}:
        raise fail_config(f"Slot {slot_number} is not runnable from {slot['state']}")
    attempt = int(slot["attemptCount"]) + 1
    if replacement:
        replacement_path = root / "replacements" / f"slot-{slot_number:03d}" / f"replacement-{attempt - 1:03d}.json"
        if not replacement_path.is_file():
            raise fail_config("Infrastructure replacement has not been explicitly authorized")
    pointer_relative = f"control/slot-{slot_number:03d}-attempt-{attempt:03d}.orchestration-pointer"
    log_relative = f"logs/slot-{slot_number:03d}-attempt-{attempt:03d}.log"
    pointer = root / pointer_relative
    log = root / log_relative
    pointer.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    if pointer.exists() or pointer.is_symlink() or log.exists():
        raise fail_contradiction("Attempt control or log target already exists")
    intent = {
        "attempt": attempt,
        "log": log_relative,
        "orchestrationPointer": pointer_relative,
        "slot": slot_number,
    }
    slot["attemptCount"] = attempt
    slot["state"] = "RUNNING"
    checkpoint["currentAttempt"] = intent
    checkpoint["nextPendingSlot"] = slot_number
    checkpoint["state"] = "RUNNING"
    save_checkpoint(root, checkpoint)
    return {"attempt": attempt, "log": log, "pointer": pointer, "slot": slot_number}


def portable_reference(path: Path, results_root: Path) -> str:
    try:
        return path.resolve().relative_to(results_root.resolve()).as_posix()
    except ValueError as error:
        raise fail_contradiction(f"Evidence path is outside the results root: {path}") from error


def classify_attempt_exit(exit_code: int) -> str:
    if exit_code == 0:
        return "VALID_MEMBER"
    if exit_code in INFRASTRUCTURE_EXITS:
        return "INFRASTRUCTURE_INVALID"
    if exit_code == 30:
        return "BENCHMARK_FAILURE"
    if exit_code == 2:
        return "CONFIGURATION_FAILURE"
    if exit_code in EVIDENCE_EXITS:
        return "EVIDENCE_INVALID"
    return "UNRESOLVED"


def read_attempt_pointer(pointer: Path) -> Path:
    if not pointer.is_file() or pointer.is_symlink():
        raise fail_contradiction("Attempt orchestration pointer is missing or not a regular file")
    try:
        lines = pointer.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise fail_contradiction(f"Cannot read attempt orchestration pointer: {error}") from error
    if len(lines) != 1 or not lines[0] or not Path(lines[0]).is_absolute():
        raise fail_contradiction("Attempt orchestration pointer must contain one absolute path")
    return Path(lines[0]).resolve()


def metric_signature(metric: dict[str, Any]) -> dict[str, Any]:
    excluded = {"canonicalValue", "sourceValue", "error", "confidence"}
    return {key: value for key, value in metric.items() if key not in excluded}


def member_compatibility_key(manifest: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "benchmarkConfigFingerprint": manifest.get("benchmarkConfigFingerprint"),
        "environmentFingerprint": manifest.get("environmentFingerprint"),
        "evidenceProfile": manifest.get("evidenceProfile"),
        "metricSignatures": [metric_signature(metric) for metric in metrics.get("metrics", [])],
        "mode": manifest.get("benchmark", {}).get("mode"),
        "presetId": manifest.get("benchmark", {}).get("presetId"),
        "source": {
            "commit": manifest.get("source", {}).get("commit"),
            "repository": manifest.get("source", {}).get("repository"),
        },
        "suite": manifest.get("suite"),
    }


_DIAGNOSTIC_MISSING = object()
_MAX_COMPATIBILITY_DIFFERENCES = 50
_MAX_DIAGNOSTIC_VALUE_CHARS = 240


def diagnostic_value(value: Any) -> str:
    if value is _DIAGNOSTIC_MISSING:
        return "<missing>"
    rendered = canonical_json_bytes(value).decode("utf-8").rstrip("\n")
    if len(rendered) > _MAX_DIAGNOSTIC_VALUE_CHARS:
        return rendered[: _MAX_DIAGNOSTIC_VALUE_CHARS - 3] + "..."
    return rendered


def structured_differences(
    reference: Any, candidate: Any, path: str
) -> list[tuple[str, Any, Any]]:
    if reference == candidate:
        return []
    if isinstance(reference, dict) and isinstance(candidate, dict):
        differences: list[tuple[str, Any, Any]] = []
        for key in sorted(set(reference) | set(candidate)):
            left = reference.get(key, _DIAGNOSTIC_MISSING)
            right = candidate.get(key, _DIAGNOSTIC_MISSING)
            child = f"{path}.{key}" if path else key
            differences.extend(structured_differences(left, right, child))
        return differences
    if isinstance(reference, list) and isinstance(candidate, list):
        differences = []
        for index in range(max(len(reference), len(candidate))):
            left = reference[index] if index < len(reference) else _DIAGNOSTIC_MISSING
            right = candidate[index] if index < len(candidate) else _DIAGNOSTIC_MISSING
            differences.extend(structured_differences(left, right, f"{path}[{index}]"))
        return differences
    return [(path, reference, candidate)]


def member_compatibility_differences(
    reference_manifest: dict[str, Any],
    reference_metrics: dict[str, Any],
    candidate_manifest: dict[str, Any],
    candidate_metrics: dict[str, Any],
) -> list[tuple[str, Any, Any]]:
    reference = member_compatibility_key(reference_manifest, reference_metrics)
    candidate = member_compatibility_key(candidate_manifest, candidate_metrics)
    differences: list[tuple[str, Any, Any]] = []
    for key in sorted(reference):
        if reference[key] == candidate[key]:
            continue
        differences.extend(structured_differences(reference[key], candidate[key], key))
        if key == "environmentFingerprint":
            differences.extend(
                structured_differences(
                    environment_fingerprint_payload(reference_manifest.get("environment", {})),
                    environment_fingerprint_payload(candidate_manifest.get("environment", {})),
                    "environment",
                )
            )
    return differences


def emit_member_compatibility_diagnostics(
    selected: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]
) -> None:
    if not selected:
        return
    reference_attempt, reference_manifest, reference_metrics = selected[0]
    reference_slot = reference_attempt.get("slot")
    for candidate_attempt, candidate_manifest, candidate_metrics in selected[1:]:
        differences = member_compatibility_differences(
            reference_manifest,
            reference_metrics,
            candidate_manifest,
            candidate_metrics,
        )
        if not differences:
            continue
        candidate_slot = candidate_attempt.get("slot")
        print(
            "ERROR: Set member compatibility mismatch: "
            f"reference slot={reference_slot}, candidate slot={candidate_slot}",
            file=sys.stderr,
        )
        for path, reference_value, candidate_value in differences[:_MAX_COMPATIBILITY_DIFFERENCES]:
            print(
                f"  {path}: reference={diagnostic_value(reference_value)}; "
                f"candidate={diagnostic_value(candidate_value)}",
                file=sys.stderr,
            )
        remaining = len(differences) - _MAX_COMPATIBILITY_DIFFERENCES
        if remaining > 0:
            print(f"  ... {remaining} additional differences omitted", file=sys.stderr)


def validate_member_against_plan(
    plan: dict[str, Any], manifest: dict[str, Any], record: dict[str, str]
) -> None:
    expected_status = (
        "VALID_CANONICAL_MEMBER"
        if plan["evidenceProfile"] == "canonical"
        else "VALID_EXPERIMENT"
    )
    checks = {
        "member status": (manifest.get("status"), expected_status),
        "evidence profile": (manifest.get("evidenceProfile"), plan["evidenceProfile"]),
        "source repository": (manifest.get("source", {}).get("repository"), plan["source"]["repository"]),
        "source commit": (manifest.get("source", {}).get("commit"), plan["source"]["commit"]),
        "benchmark mode": (manifest.get("benchmark", {}).get("mode"), plan["mode"]),
        "benchmark preset": (manifest.get("benchmark", {}).get("presetId"), plan["presetId"]),
        "project": (record.get("project"), plan["controls"].get("project")),
    }
    environment = manifest.get("environment", {})
    image = environment.get("image", {})
    try:
        planned_jvm_options = shlex.split(plan["controls"].get("jvmOptions", ""))
    except ValueError as error:
        raise fail_contradiction(f"Invalid JVM options in set plan: {error}") from error
    checks.update(
        {
            "zone": (environment.get("zone"), plan["controls"].get("zone")),
            "machine type": (environment.get("machineType"), plan["controls"].get("machineType")),
            "provisioning": (environment.get("provisioning"), plan["controls"].get("provisioning", "").lower()),
            "resolved image": (image.get("resolvedName"), plan["controls"].get("resolvedImage")),
            "resolved image ID": (image.get("id"), plan["controls"].get("resolvedImageId")),
            "resolved image self-link": (image.get("selfLink"), plan["controls"].get("resolvedImageSelfLink")),
            "resolved image creation": (image.get("createdAt"), plan["controls"].get("resolvedImageCreatedAt")),
            "ordered JVM options": (environment.get("jvmOptions"), planned_jvm_options),
            "boot disk size": (record.get("boot_disk_size"), plan["controls"].get("bootDiskSize")),
            "boot disk type": (record.get("boot_disk_type"), plan["controls"].get("bootDiskType")),
            "maximum runtime": (record.get("max_run_duration"), plan["controls"].get("maxRunDuration")),
            "network": (record.get("network", ""), plan["controls"].get("network", "")),
            "subnet": (record.get("subnet", ""), plan["controls"].get("subnet", "")),
            "SSH transport": (
                record.get("ssh_transport"),
                "iap" if plan["controls"].get("useIap") == "true" else "external_ip",
            ),
        }
    )
    for label, (actual, expected) in checks.items():
        if actual != expected:
            raise fail_invalid(f"Set plan {label} mismatch: expected {expected!r}, got {actual!r}")


def selected_member_documents(root: Path, checkpoint: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    results_root = root.parents[2]
    selected = []
    for slot in checkpoint["slots"]:
        if slot["state"] != "VALID_MEMBER":
            continue
        attempt_path = root / "attempts" / f"slot-{slot['slot']:03d}" / f"attempt-{slot['selectedAttempt']:03d}.json"
        attempt = read_json(attempt_path)
        manifest = read_json(results_root / attempt["member"]["manifestReference"])
        metrics_path = results_root / attempt["member"]["metricsReference"]
        metrics = read_json(metrics_path)
        if manifest.get("metrics", {}).get("sha256") != sha256_file(metrics_path):
            raise fail_contradiction("Member manifest does not bind its normalized metrics")
        selected.append((attempt, manifest, metrics))
    return selected


def record_set_attempt(workspace: Path, slot_number: int, v1_exit: int) -> int:
    root, plan, checkpoint = load_set_workspace(workspace)
    intent = checkpoint.get("currentAttempt")
    if not isinstance(intent, dict) or intent.get("slot") != slot_number:
        raise fail_config("No matching RUNNING attempt exists")
    slot = checkpoint_slot(checkpoint, slot_number)
    attempt_number = int(intent["attempt"])
    results_root = root.parents[2]
    outcome = classify_attempt_exit(v1_exit)
    attempt_record: dict[str, Any] = {
        "attempt": attempt_number,
        "classification": outcome,
        "member": None,
        "orchestration": None,
        "phase1Exit": None,
        "schemaVersion": 1,
        "slot": slot_number,
        "v1Exit": v1_exit,
    }
    pointer = root / intent["orchestrationPointer"]
    record_path: Path | None = None
    if pointer.exists() or pointer.is_symlink():
        try:
            record_path = read_attempt_pointer(pointer)
            record, _ = read_properties(record_path)
            if record.get("stage") != "FINISHED" or record.get("primary_exit_code") != str(v1_exit):
                raise fail_contradiction("Orchestration record does not match the finalized V1 exit")
            attempt_record["orchestration"] = {
                "digest": "sha256:" + sha256_file(record_path),
                "instance": record.get("instance_name"),
                "reference": portable_reference(record_path, results_root),
            }
        except BenchmarkV2Error:
            record_path = None
            outcome = "UNRESOLVED"
            attempt_record["classification"] = outcome
    elif v1_exit != 2:
        outcome = "UNRESOLVED"
        attempt_record["classification"] = outcome
    if v1_exit == 0:
        if record_path is None:
            outcome = "UNRESOLVED"
            attempt_record["classification"] = outcome
        else:
            record, _ = read_properties(record_path)
            raw_text = record.get("local_result_path", "")
            try:
                if not raw_text:
                    raise fail_invalid("Successful V1 record has no local_result_path")
                output, manifest, _ = derive_manifest(
                    Path(raw_text),
                    orchestration_record=record_path,
                    evidence_profile=plan["evidenceProfile"],
                )
                validate_member_against_plan(plan, manifest, record)
                manifest_path = output / "benchmark-manifest.json"
                metrics_path = output / "normalized-metrics.json"
                attempt_record["member"] = {
                    "instance": manifest["environment"].get("machineType") and record.get("instance_name"),
                    "manifestDigest": "sha256:" + sha256_file(manifest_path),
                    "manifestReference": portable_reference(manifest_path, results_root),
                    "metricsDigest": "sha256:" + sha256_file(metrics_path),
                    "metricsReference": portable_reference(metrics_path, results_root),
                    "rawRunId": manifest["runId"],
                }
            except BenchmarkV2Error as error:
                outcome = "EVIDENCE_INVALID"
                attempt_record["classification"] = outcome
                attempt_record["phase1Exit"] = error.exit_code
    attempt_path = root / "attempts" / f"slot-{slot_number:03d}" / f"attempt-{attempt_number:03d}.json"
    atomic_write_json(attempt_path, attempt_record, immutable=True)
    slot["state"] = outcome
    checkpoint["currentAttempt"] = None
    checkpoint["nextPendingSlot"] = None
    if outcome == "VALID_MEMBER":
        slot["selectedAttempt"] = attempt_number
        selected = selected_member_documents(root, checkpoint)
        compatibility = [member_compatibility_key(manifest, metrics) for _, manifest, metrics in selected]
        if compatibility and any(item != compatibility[0] for item in compatibility[1:]):
            emit_member_compatibility_diagnostics(selected)
            checkpoint["state"] = "INCOMPATIBLE"
            save_checkpoint(root, checkpoint)
            return EXIT_INCOMPATIBLE_SET
        identity_columns = {
            "rawRunId": [item[0]["member"]["rawRunId"] for item in selected],
            "orchestration.instance": [item[0]["orchestration"]["instance"] for item in selected],
            "orchestration.digest": [item[0]["orchestration"]["digest"] for item in selected],
            "member.manifestDigest": [item[0]["member"]["manifestDigest"] for item in selected],
        }
        duplicate_identity = {
            label: values for label, values in identity_columns.items() if len(values) != len(set(values))
        }
        if duplicate_identity:
            print("ERROR: Set member identity is not unique", file=sys.stderr)
            for label, values in duplicate_identity.items():
                print(f"  {label}: values={diagnostic_value(values)}", file=sys.stderr)
            checkpoint["state"] = "INCOMPATIBLE"
            save_checkpoint(root, checkpoint)
            return EXIT_INCOMPATIBLE_SET
        pending = next((item["slot"] for item in checkpoint["slots"] if item["state"] == "PENDING"), None)
        checkpoint["nextPendingSlot"] = pending
        checkpoint["state"] = "READY"
    elif outcome == "INFRASTRUCTURE_INVALID":
        checkpoint["state"] = "BLOCKED_INFRASTRUCTURE"
    elif outcome == "UNRESOLVED":
        checkpoint["state"] = "UNRESOLVED"
    else:
        checkpoint["state"] = "BLOCKED_FAILURE"
    save_checkpoint(root, checkpoint)
    if outcome == "EVIDENCE_INVALID":
        return int(attempt_record["phase1Exit"] or EXIT_INVALID_EVIDENCE)
    if outcome == "UNRESOLVED" and v1_exit == 0:
        return EXIT_INCOMPATIBLE_SET
    return v1_exit


def reconcile_running_attempt(workspace: Path) -> int:
    root, _, checkpoint = load_set_workspace(workspace)
    intent = checkpoint.get("currentAttempt")
    if not isinstance(intent, dict):
        return 0
    pointer = root / intent["orchestrationPointer"]
    try:
        record_path = read_attempt_pointer(pointer)
        record, _ = read_properties(record_path)
        if record.get("stage") != "FINISHED" or not record.get("primary_exit_code", "").isdigit():
            raise fail_contradiction("RUNNING attempt has no finalized orchestration outcome")
        return record_set_attempt(root, int(intent["slot"]), int(record["primary_exit_code"]))
    except BenchmarkV2Error:
        slot = checkpoint_slot(checkpoint, int(intent["slot"]))
        attempt_number = int(intent["attempt"])
        attempt_record = {
            "attempt": attempt_number,
            "classification": "UNRESOLVED",
            "member": None,
            "orchestration": None,
            "phase1Exit": None,
            "schemaVersion": 1,
            "slot": int(intent["slot"]),
            "v1Exit": None,
        }
        attempt_path = root / "attempts" / f"slot-{intent['slot']:03d}" / f"attempt-{attempt_number:03d}.json"
        atomic_write_json(attempt_path, attempt_record, immutable=True)
        slot["state"] = "UNRESOLVED"
        checkpoint["currentAttempt"] = None
        checkpoint["state"] = "UNRESOLVED"
        checkpoint["nextPendingSlot"] = None
        save_checkpoint(root, checkpoint)
        return EXIT_INCOMPATIBLE_SET


def authorize_set_replacement(workspace: Path, slot_number: int, reason: str, confirmed: bool) -> Path:
    root, _, checkpoint = load_set_workspace(workspace)
    if not confirmed:
        raise fail_config("Replacement requires --confirm-no-score-selection")
    if not reason or len(reason) > 500 or "\n" in reason or "\r" in reason:
        raise fail_config("Replacement reason must be 1..500 single-line UTF-8 characters")
    slot = checkpoint_slot(checkpoint, slot_number)
    if slot["state"] != "INFRASTRUCTURE_INVALID" or checkpoint["state"] != "BLOCKED_INFRASTRUCTURE":
        raise fail_config("Only an infrastructure-invalid blocked slot is replaceable")
    if any(item["state"] != "PENDING" for item in checkpoint["slots"][slot_number:]):
        raise fail_config("Replacement is forbidden after a later slot has started")
    prior_attempt = int(slot["attemptCount"])
    attempt_path = root / "attempts" / f"slot-{slot_number:03d}" / f"attempt-{prior_attempt:03d}.json"
    attempt = read_json(attempt_path)
    authorization = {
        "confirmedWithoutScoreSelection": True,
        "infrastructureClassification": attempt["classification"],
        "nextAttempt": prior_attempt + 1,
        "priorAttempt": prior_attempt,
        "priorOrchestration": attempt.get("orchestration"),
        "priorV1Exit": attempt["v1Exit"],
        "reason": reason,
        "schemaVersion": 1,
        "slot": slot_number,
    }
    path = root / "replacements" / f"slot-{slot_number:03d}" / f"replacement-{prior_attempt:03d}.json"
    atomic_write_json(path, authorization, immutable=True)
    checkpoint["nextPendingSlot"] = slot_number
    checkpoint["state"] = "READY"
    save_checkpoint(root, checkpoint)
    return path


def median(values: list[int | float]) -> int | float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def aggregate_member_metrics(
    set_id: str,
    suite: dict[str, Any],
    members: list[tuple[int, str, dict[str, Any]]],
) -> dict[str, Any]:
    by_member = [{item["id"]: item for item in document["metrics"]} for _, _, document in members]
    metric_ids = [item["id"] for item in members[0][2]["metrics"]]
    if any(set(values) != set(metric_ids) for values in by_member):
        raise fail_contradiction("Member metric ID sets differ")
    aggregates = []
    for metric_id in sorted(metric_ids):
        source = by_member[0][metric_id]
        values = [
            {"runId": run_id, "slot": slot, "value": metrics[metric_id].get("canonicalValue")}
            for (slot, run_id, _), metrics in zip(members, by_member)
        ]
        raw_values = [item["value"] for item in values]
        base = {
            "direction": source["direction"],
            "identity": source["identity"],
            "metricId": metric_id,
            "statistic": source["statistic"],
            "unit": source["canonicalUnit"],
            "values": values,
        }
        if "percentile" in source:
            base["percentile"] = source["percentile"]
        categorical = source["direction"] == "categorical" or any(
            isinstance(value, (bool, str)) or value is None for value in raw_values
        )
        if categorical:
            distinct = []
            for value in raw_values:
                if value not in distinct:
                    distinct.append(value)
            base.update(
                {
                    "aggregationKind": "consensus",
                    "allEqual": len(distinct) == 1,
                    "distinctValues": distinct,
                    "unanimousValue": distinct[0] if len(distinct) == 1 else None,
                }
            )
        else:
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in raw_values):
                raise fail_contradiction(f"Metric {metric_id} has a non-finite numeric value")
            minimum = min(raw_values)
            maximum = max(raw_values)
            middle = median(raw_values)
            absolute_range = maximum - minimum
            base.update(
                {
                    "absoluteRange": absolute_range,
                    "aggregationKind": (
                        "median_of_run_percentile"
                        if source["statistic"].startswith("sample_percentile_")
                        else "median_of_independent_run_values"
                    ),
                    "count": len(raw_values),
                    "maximum": maximum,
                    "median": middle,
                    "minimum": minimum,
                    "relativeRangePct": None if middle == 0 else absolute_range / abs(middle) * 100,
                }
            )
            if middle == 0:
                base["relativeRangeUnavailableReason"] = "median_zero"
        aggregates.append(base)
    return {
        "aggregationMethod": "median-and-range-of-independent-runs",
        "kind": "aggregate-benchmark-metrics",
        "memberCount": len(members),
        "metrics": aggregates,
        "schemaVersion": SET_METRICS_SCHEMA_VERSION,
        "setId": set_id,
        "suite": suite,
    }


def verify_final_set_directory(destination: Path) -> None:
    expected_names = {
        "aggregate-metrics.json",
        "benchmark-set-manifest.json",
        "set-attempt-audit.json",
        "set-checksums.sha256",
    }
    actual_names = {path.name for path in destination.iterdir() if path.is_file()}
    if actual_names != expected_names:
        raise fail_contradiction("Completed set artifact file set differs")
    checksum_path = destination / "set-checksums.sha256"
    entries = checksum_path.read_text(encoding="utf-8").splitlines()
    expected_lines = []
    for name in (
        "benchmark-set-manifest.json",
        "aggregate-metrics.json",
        "set-attempt-audit.json",
    ):
        expected_lines.append(f"{sha256_file(destination / name)}  {name}")
    if entries != expected_lines:
        raise fail_contradiction("Completed set checksum verification failed")


def finalize_benchmark_set(workspace: Path) -> tuple[Path, dict[str, Any]]:
    root, plan, checkpoint = load_set_workspace(workspace)
    if checkpoint["state"] == "COMPLETE":
        set_id = checkpoint["finalSetId"]
        destination = root.parents[2] / "sets" / set_id / "v1"
        verify_final_set_directory(destination)
        return destination, read_json(destination / "benchmark-set-manifest.json")
    if checkpoint.get("currentAttempt") is not None or any(slot["state"] != "VALID_MEMBER" for slot in checkpoint["slots"]):
        raise BenchmarkV2Error("Set is not complete", EXIT_INCOMPATIBLE_SET)
    selected = selected_member_documents(root, checkpoint)
    minimum = 3 if plan["evidenceProfile"] == "canonical" else 1
    if len(selected) < minimum:
        raise BenchmarkV2Error("Set has too few valid members", EXIT_INCOMPATIBLE_SET)
    compatibility = [member_compatibility_key(manifest, metrics) for _, manifest, metrics in selected]
    if any(item != compatibility[0] for item in compatibility[1:]):
        raise BenchmarkV2Error("Set members are incompatible", EXIT_INCOMPATIBLE_SET)
    audit_slots = []
    slot_identities = []
    final_members = []
    metric_members = []
    results_root = root.parents[2]
    for slot, (selected_attempt, manifest, metrics) in zip(checkpoint["slots"], selected):
        attempt_dir = root / "attempts" / f"slot-{slot['slot']:03d}"
        attempts = [read_json(path) for path in sorted(attempt_dir.glob("attempt-*.json"))]
        replacement_dir = root / "replacements" / f"slot-{slot['slot']:03d}"
        replacements = [read_json(path) for path in sorted(replacement_dir.glob("replacement-*.json"))] if replacement_dir.is_dir() else []
        slot_audit = {
            "attempts": attempts,
            "replacements": replacements,
            "selectedAttempt": slot["selectedAttempt"],
            "slot": slot["slot"],
        }
        slot_audit_digest = "sha256:" + sha256_bytes(canonical_json_bytes(slot_audit))
        audit_slots.append(slot_audit)
        member = selected_attempt["member"]
        orchestration = selected_attempt["orchestration"]
        slot_identities.append(
            {
                "instance": orchestration["instance"],
                "memberManifestSha256": member["manifestDigest"],
                "rawRunId": member["rawRunId"],
                "slot": slot["slot"],
                "slotAttemptAuditSha256": slot_audit_digest,
            }
        )
        final_members.append(
            {
                "instance": orchestration["instance"],
                "manifestReference": member["manifestReference"],
                "manifestSha256": member["manifestDigest"],
                "metricsReference": member["metricsReference"],
                "metricsSha256": member["metricsDigest"],
                "orchestrationReference": orchestration["reference"],
                "orchestrationSha256": orchestration["digest"],
                "rawRunId": member["rawRunId"],
                "slot": slot["slot"],
                "slotAttemptAuditSha256": slot_audit_digest,
            }
        )
        metric_members.append((slot["slot"], member["rawRunId"], metrics))
    base_manifest = selected[0][1]
    identity = {
        "benchmarkConfigFingerprint": base_manifest["benchmarkConfigFingerprint"],
        "environmentFingerprint": base_manifest["environmentFingerprint"],
        "evidenceProfile": plan["evidenceProfile"],
        "mode": plan["mode"],
        "schemaVersion": 1,
        "slots": slot_identities,
        "sourceCommit": plan["source"]["commit"],
        "suite": {
            "name": base_manifest["suite"]["name"],
            "schemaVersion": base_manifest["suite"]["schemaVersion"],
        },
    }
    set_id = "gse-set-v1-" + sha256_bytes(canonical_json_bytes(identity))
    audit = {
        "kind": "benchmark-set-attempt-audit",
        "schemaVersion": SET_AUDIT_SCHEMA_VERSION,
        "setId": set_id,
        "slots": audit_slots,
    }
    aggregate = aggregate_member_metrics(set_id, identity["suite"], metric_members)
    aggregate_bytes = canonical_json_bytes(aggregate)
    audit_bytes = canonical_json_bytes(audit)
    manifest = {
        "aggregateMetrics": {
            "count": len(aggregate["metrics"]),
            "path": "aggregate-metrics.json",
            "sha256": "sha256:" + sha256_bytes(aggregate_bytes),
        },
        "aggregationMethod": aggregate["aggregationMethod"],
        "attemptAudit": {
            "path": "set-attempt-audit.json",
            "sha256": "sha256:" + sha256_bytes(audit_bytes),
        },
        "benchmarkConfigFingerprint": base_manifest["benchmarkConfigFingerprint"],
        "environmentFingerprint": base_manifest["environmentFingerprint"],
        "evidenceProfile": plan["evidenceProfile"],
        "kind": "benchmark-set",
        "members": final_members,
        "mode": plan["mode"],
        "presetId": plan["presetId"],
        "schemaVersion": SET_MANIFEST_SCHEMA_VERSION,
        "setId": set_id,
        "source": plan["source"],
        "status": "VALID_CANONICAL_SET" if plan["evidenceProfile"] == "canonical" else "VALID_EXPERIMENT_SET",
        "suite": identity["suite"],
        "warnings": sorted({warning for _, member_manifest, _ in selected for warning in member_manifest["warnings"]}),
    }
    manifest_bytes = canonical_json_bytes(manifest)
    checksum_bytes = (
        f"{sha256_bytes(manifest_bytes)}  benchmark-set-manifest.json\n"
        f"{sha256_bytes(aggregate_bytes)}  aggregate-metrics.json\n"
        f"{sha256_bytes(audit_bytes)}  set-attempt-audit.json\n"
    ).encode("utf-8")
    destination = results_root / "sets" / set_id / "v1"
    expected_files = {
        "aggregate-metrics.json": aggregate_bytes,
        "benchmark-set-manifest.json": manifest_bytes,
        "set-attempt-audit.json": audit_bytes,
        "set-checksums.sha256": checksum_bytes,
    }
    if destination.exists():
        actual = {path.name: path.read_bytes() for path in destination.iterdir() if path.is_file()}
        if actual != expected_files:
            raise fail_contradiction(f"Existing final set artifact collision: {destination}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = destination.parent / f".v1.{uuid.uuid4().hex}"
        staging.mkdir()
        try:
            for name, content in expected_files.items():
                atomic_write_bytes(staging / name, content)
            os.replace(staging, destination)
        finally:
            if staging.exists():
                for child in staging.iterdir():
                    child.unlink()
                staging.rmdir()
    checkpoint["finalSetId"] = set_id
    checkpoint["nextPendingSlot"] = None
    checkpoint["state"] = "COMPLETE"
    save_checkpoint(root, checkpoint)
    return destination, manifest


def require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise fail_invalid(f"{field} must be an object")
    return value


def require_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise fail_invalid(f"{field} must be an array")
    return value


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise fail_invalid(f"{field} must be a non-empty string")
    return value


def require_integer_value(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise fail_invalid(f"{field} must be an integer >= {minimum}")
    return value


def canonical_document(path: Path) -> tuple[dict[str, Any], bytes]:
    value = require_object(read_json(path), str(path))
    encoded = canonical_json_bytes(value)
    try:
        source = path.read_bytes()
    except OSError as error:
        raise fail_invalid(f"Cannot read {path}: {error}") from error
    if source != encoded:
        raise fail_invalid(f"JSON evidence is not canonical: {path}")
    return value, source


def verify_exact_checksum_file(
    root: Path, checksum_name: str, data_names: tuple[str, ...]
) -> None:
    expected_names = {*data_names, checksum_name}
    try:
        entries = list(root.iterdir())
    except OSError as error:
        raise fail_invalid(f"Cannot inspect evidence directory {root}: {error}") from error
    if {entry.name for entry in entries} != expected_names:
        raise fail_invalid(f"Evidence file set differs in {root}")
    if any(not entry.is_file() or entry.is_symlink() for entry in entries):
        raise fail_invalid(f"Evidence contains a non-regular or symlinked file in {root}")
    checksum_path = root / checksum_name
    try:
        lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise fail_invalid(f"Cannot read checksum file {checksum_path}: {error}") from error
    expected_lines = [f"{sha256_file(root / name)}  {name}" for name in data_names]
    if lines != expected_lines:
        raise fail_invalid(f"Checksum verification failed in {root}")


def evidence_directory(operand: Path) -> tuple[Path, str]:
    path = operand.resolve()
    if path.is_dir():
        root = path
    elif path.is_file() and path.name in {
        "benchmark-set-manifest.json",
        "benchmark-manifest.json",
    }:
        root = path.parent
    elif path.exists():
        raise fail_config(f"Unsupported evidence operand: {operand}")
    else:
        raise fail_config(f"Evidence operand does not exist: {operand}")
    if (root / "benchmark-set-manifest.json").is_file():
        return root, "set"
    if (root / "benchmark-manifest.json").is_file():
        return root, "run"
    raise fail_invalid(f"Evidence directory has no supported manifest: {root}")


def safe_results_reference(results_root: Path, reference: Any) -> Path:
    text = require_string(reference, "portable evidence reference")
    relative = Path(text)
    if relative.is_absolute() or ".." in relative.parts:
        raise fail_contradiction(f"Unsafe portable evidence reference: {text}")
    root = results_root.resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise fail_contradiction(f"Evidence reference escapes the results root: {text}") from error
    return target


def comparison_metric_signature(metric: dict[str, Any]) -> dict[str, Any]:
    return {
        "aggregationKind": metric["aggregationKind"],
        "direction": metric["direction"],
        "identity": metric["identity"],
        "percentile": metric.get("percentile"),
        "statistic": metric["statistic"],
        "unit": metric["unit"],
    }


def validate_metric_common(metric: dict[str, Any], field: str) -> None:
    require_string(metric.get("direction"), f"{field}.direction")
    require_object(metric.get("identity"), f"{field}.identity")
    require_string(metric.get("statistic"), f"{field}.statistic")
    require_string(metric.get("unit"), f"{field}.unit")
    if metric.get("percentile") is not None:
        finite_number(metric["percentile"], f"{field}.percentile")


def source_and_suite(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    source = require_object(manifest.get("source"), "manifest.source")
    repository = source.get("repository")
    if repository is not None and (not isinstance(repository, str) or not repository):
        raise fail_contradiction("Manifest source repository must be null or a non-empty string")
    commit = require_string(source.get("commit"), "manifest.source.commit")
    if not COMMIT_RE.fullmatch(commit):
        raise fail_contradiction("Manifest source commit is not an exact lowercase Git ID")
    suite = require_object(manifest.get("suite"), "manifest.suite")
    require_string(suite.get("name"), "manifest.suite.name")
    require_integer_value(suite.get("schemaVersion"), "manifest.suite.schemaVersion", minimum=0)
    return {"commit": commit, "repository": repository}, {
        "name": suite["name"],
        "schemaVersion": suite["schemaVersion"],
    }


def representative_environment(
    manifest: dict[str, Any], results_root: Path
) -> dict[str, Any] | None:
    members = require_list(manifest.get("members"), "set manifest members")
    if not members:
        return None
    member = require_object(members[0], "set manifest member 0")
    target = safe_results_reference(results_root, member.get("manifestReference"))
    if not target.is_file() or target.is_symlink():
        return None
    expected = require_string(member.get("manifestSha256"), "member manifest digest")
    if not PREFIXED_SHA256_RE.fullmatch(expected):
        raise fail_contradiction("Member manifest digest has an invalid form")
    if "sha256:" + sha256_file(target) != expected:
        raise fail_contradiction("Representative member manifest digest contradicts the set")
    document, _ = canonical_document(target)
    if document.get("kind") != "benchmark-run" or document.get("schemaVersion") != 1:
        raise fail_unsupported("Representative member manifest schema is unsupported")
    if document.get("environmentFingerprint") != manifest.get("environmentFingerprint"):
        raise fail_contradiction("Representative member environment fingerprint contradicts the set")
    return require_object(document.get("environment"), "representative member environment")


def validate_set_evidence(root: Path, results_root: Path) -> dict[str, Any]:
    verify_exact_checksum_file(
        root,
        "set-checksums.sha256",
        ("benchmark-set-manifest.json", "aggregate-metrics.json", "set-attempt-audit.json"),
    )
    manifest, manifest_bytes = canonical_document(root / "benchmark-set-manifest.json")
    aggregate, aggregate_bytes = canonical_document(root / "aggregate-metrics.json")
    audit, audit_bytes = canonical_document(root / "set-attempt-audit.json")
    if manifest.get("kind") != "benchmark-set":
        raise fail_unsupported("Set manifest kind is unsupported")
    if manifest.get("schemaVersion") != SET_MANIFEST_SCHEMA_VERSION:
        raise fail_unsupported("Set manifest schema is unsupported")
    status = manifest.get("status")
    if status not in {"VALID_CANONICAL_SET", "VALID_EXPERIMENT_SET"}:
        raise fail_unsupported(f"Set status is unsupported: {status!r}")
    set_id = require_string(manifest.get("setId"), "set manifest setId")
    if not SET_ID_RE.fullmatch(set_id):
        raise fail_contradiction("Set ID has an invalid form")
    if root.name != "v1" or root.parent.name != set_id:
        raise fail_contradiction("Set directory and manifest set ID disagree")
    source, suite = source_and_suite(manifest)
    if suite["schemaVersion"] != 1:
        raise fail_unsupported("Set suite schema is unsupported")
    if source["repository"] is None:
        raise fail_contradiction("Set source repository is unavailable")
    profile = require_string(manifest.get("evidenceProfile"), "set evidence profile")
    expected_profile = "canonical" if status == "VALID_CANONICAL_SET" else "experiment"
    if profile != expected_profile:
        raise fail_contradiction("Set status and evidence profile disagree")
    for key in ("benchmarkConfigFingerprint", "environmentFingerprint"):
        fingerprint_value = manifest.get(key)
        if not isinstance(fingerprint_value, str) or not PREFIXED_SHA256_RE.fullmatch(fingerprint_value):
            raise fail_contradiction(f"Set {key} has an invalid form")
    preset_id = manifest.get("presetId")
    if preset_id is not None and (not isinstance(preset_id, str) or not preset_id):
        raise fail_contradiction("Set preset ID must be null or a non-empty string")
    members = require_list(manifest.get("members"), "set members")
    minimum = 3 if profile == "canonical" else 1
    if len(members) < minimum:
        raise fail_contradiction("Set has too few members for its evidence profile")
    slots: list[int] = []
    for index, value in enumerate(members):
        member = require_object(value, f"set member {index}")
        slot = require_integer_value(member.get("slot"), f"set member {index}.slot", minimum=1)
        slots.append(slot)
        require_string(member.get("rawRunId"), f"set member {index}.rawRunId")
        for key in ("manifestSha256", "metricsSha256", "orchestrationSha256", "slotAttemptAuditSha256"):
            digest = require_string(member.get(key), f"set member {index}.{key}")
            if not PREFIXED_SHA256_RE.fullmatch(digest):
                raise fail_contradiction(f"Set member {index}.{key} has an invalid digest")
        for key in ("manifestReference", "metricsReference", "orchestrationReference"):
            safe_results_reference(results_root, member.get(key))
    if slots != list(range(1, len(members) + 1)):
        raise fail_contradiction("Set member slots are not ordered and contiguous")
    aggregate_binding = require_object(manifest.get("aggregateMetrics"), "set aggregate binding")
    audit_binding = require_object(manifest.get("attemptAudit"), "set audit binding")
    if aggregate_binding.get("path") != "aggregate-metrics.json":
        raise fail_contradiction("Set aggregate path is contradictory")
    if audit_binding.get("path") != "set-attempt-audit.json":
        raise fail_contradiction("Set audit path is contradictory")
    if aggregate_binding.get("sha256") != "sha256:" + sha256_bytes(aggregate_bytes):
        raise fail_contradiction("Set aggregate digest is contradictory")
    if audit_binding.get("sha256") != "sha256:" + sha256_bytes(audit_bytes):
        raise fail_contradiction("Set audit digest is contradictory")
    if audit.get("kind") != "benchmark-set-attempt-audit" or audit.get("schemaVersion") != 1:
        raise fail_unsupported("Set attempt-audit schema is unsupported")
    if audit.get("setId") != set_id:
        raise fail_contradiction("Set attempt audit belongs to another set")
    if aggregate.get("kind") != "aggregate-benchmark-metrics":
        raise fail_unsupported("Aggregate metrics kind is unsupported")
    if aggregate.get("schemaVersion") != SET_METRICS_SCHEMA_VERSION:
        raise fail_unsupported("Aggregate metrics schema is unsupported")
    if aggregate.get("setId") != set_id or aggregate.get("suite") != suite:
        raise fail_contradiction("Aggregate metrics identity contradicts the set manifest")
    if aggregate.get("memberCount") != len(members):
        raise fail_contradiction("Aggregate member count contradicts the set manifest")
    metric_values = require_list(aggregate.get("metrics"), "aggregate metrics")
    if aggregate_binding.get("count") != len(metric_values):
        raise fail_contradiction("Aggregate metric count contradicts the set manifest")
    metrics: dict[str, dict[str, Any]] = {}
    observed_ids: list[str] = []
    for index, value in enumerate(metric_values):
        metric = require_object(value, f"aggregate metric {index}")
        metric_id = require_string(metric.get("metricId"), f"aggregate metric {index}.metricId")
        if metric_id in metrics:
            raise fail_contradiction(f"Duplicate aggregate metric ID: {metric_id}")
        observed_ids.append(metric_id)
        validate_metric_common(metric, f"aggregate metric {metric_id}")
        values = require_list(metric.get("values"), f"aggregate metric {metric_id}.values")
        if len(values) != len(members):
            raise fail_contradiction(f"Aggregate metric {metric_id} member count differs")
        raw_values = []
        for member_index, member_value in enumerate(values):
            entry = require_object(member_value, f"aggregate metric {metric_id} value {member_index}")
            if entry.get("slot") != member_index + 1:
                raise fail_contradiction(f"Aggregate metric {metric_id} slots are not ordered")
            if entry.get("runId") != members[member_index]["rawRunId"]:
                raise fail_contradiction(f"Aggregate metric {metric_id} run identity differs")
            raw_values.append(entry.get("value"))
        aggregation_kind = metric.get("aggregationKind")
        if aggregation_kind == "consensus":
            distinct: list[Any] = []
            for raw in raw_values:
                if raw not in distinct:
                    distinct.append(raw)
            if metric.get("distinctValues") != distinct:
                raise fail_contradiction(f"Aggregate metric {metric_id} consensus differs")
            all_equal = len(distinct) == 1
            if metric.get("allEqual") is not all_equal:
                raise fail_contradiction(f"Aggregate metric {metric_id} unanimity differs")
            expected_unanimous = distinct[0] if all_equal else None
            if metric.get("unanimousValue") != expected_unanimous:
                raise fail_contradiction(f"Aggregate metric {metric_id} unanimous value differs")
            comparison_value: Any = {
                "allEqual": all_equal,
                "distinctValues": distinct,
                "unanimousValue": expected_unanimous,
            }
            variation = None
            variation_reason = "categorical_metric"
        elif aggregation_kind in {
            "median_of_independent_run_values",
            "median_of_run_percentile",
        }:
            numeric = [finite_number(raw, f"aggregate metric {metric_id} value") for raw in raw_values]
            middle = median(numeric)
            minimum = min(numeric)
            maximum = max(numeric)
            absolute_range = maximum - minimum
            expected = {
                "absoluteRange": absolute_range,
                "count": len(numeric),
                "maximum": maximum,
                "median": middle,
                "minimum": minimum,
                "relativeRangePct": None if middle == 0 else absolute_range / abs(middle) * 100,
            }
            if any(metric.get(key) != expected_value for key, expected_value in expected.items()):
                raise fail_contradiction(f"Aggregate metric {metric_id} statistics differ")
            if middle == 0 and metric.get("relativeRangeUnavailableReason") != "median_zero":
                raise fail_contradiction(f"Aggregate metric {metric_id} lacks zero-median reason")
            comparison_value = middle
            variation = metric.get("relativeRangePct")
            variation_reason = "median_zero" if variation is None else None
        else:
            raise fail_unsupported(f"Aggregate metric {metric_id} aggregation kind is unsupported")
        metrics[metric_id] = {
            "aggregationKind": aggregation_kind,
            "direction": metric["direction"],
            "identity": metric["identity"],
            "percentile": metric.get("percentile"),
            "statistic": metric["statistic"],
            "unit": metric["unit"],
            "value": comparison_value,
            "variationPct": variation,
            "variationUnavailableReason": variation_reason,
        }
    if observed_ids != sorted(observed_ids):
        raise fail_contradiction("Aggregate metric IDs are not sorted")
    environment = representative_environment(manifest, results_root)
    return {
        "benchmarkConfigFingerprint": require_string(
            manifest.get("benchmarkConfigFingerprint"), "set benchmark configuration fingerprint"
        ),
        "environment": environment,
        "environmentFingerprint": require_string(
            manifest.get("environmentFingerprint"), "set environment fingerprint"
        ),
        "id": set_id,
        "kind": "set",
        "manifestDigest": "sha256:" + sha256_bytes(manifest_bytes),
        "memberCount": len(members),
        "metrics": metrics,
        "metricsDigest": "sha256:" + sha256_bytes(aggregate_bytes),
        "mode": require_string(manifest.get("mode"), "set mode"),
        "presetId": preset_id,
        "profile": profile,
        "source": source,
        "status": status,
        "suite": suite,
    }


def validate_run_evidence(root: Path) -> dict[str, Any]:
    verify_exact_checksum_file(
        root,
        "derived-checksums.sha256",
        ("benchmark-manifest.json", "normalized-metrics.json"),
    )
    manifest, manifest_bytes = canonical_document(root / "benchmark-manifest.json")
    metrics_document, metrics_bytes = canonical_document(root / "normalized-metrics.json")
    if manifest.get("kind") != "benchmark-run":
        raise fail_unsupported("Run manifest kind is unsupported")
    if manifest.get("schemaVersion") != MANIFEST_SCHEMA_VERSION:
        raise fail_unsupported("Run manifest schema is unsupported")
    status = manifest.get("status")
    if status not in {"VALID_CANONICAL_MEMBER", "VALID_EXPERIMENT"}:
        raise fail_unsupported(f"Run status is unsupported: {status!r}")
    run_id = require_string(manifest.get("runId"), "run ID")
    if root.name != "v1" or root.parent.name != run_id:
        raise fail_contradiction("Run directory and manifest run ID disagree")
    source, suite = source_and_suite(manifest)
    if suite["schemaVersion"] not in {0, 1}:
        raise fail_unsupported("Run suite schema is unsupported")
    if suite["schemaVersion"] == 1 and source["repository"] is None:
        raise fail_contradiction("Schema-1 run source repository is unavailable")
    if metrics_document.get("kind") != "normalized-benchmark-metrics":
        raise fail_unsupported("Normalized metrics kind is unsupported")
    if metrics_document.get("schemaVersion") != METRICS_SCHEMA_VERSION:
        raise fail_unsupported("Normalized metrics schema is unsupported")
    if metrics_document.get("runId") != run_id or metrics_document.get("suite") != {
        "name": suite["name"],
        "schemaVersion": suite["schemaVersion"],
    }:
        raise fail_contradiction("Normalized metrics identity contradicts the run manifest")
    binding = require_object(manifest.get("metrics"), "run metrics binding")
    if binding.get("path") != "normalized-metrics.json" or binding.get("schemaVersion") != 1:
        raise fail_contradiction("Run metrics binding is contradictory")
    metrics_digest = sha256_bytes(metrics_bytes)
    if binding.get("sha256") != metrics_digest:
        raise fail_contradiction("Run metrics digest is contradictory")
    metric_values = require_list(metrics_document.get("metrics"), "normalized metrics")
    if binding.get("count") != len(metric_values):
        raise fail_contradiction("Run metric count is contradictory")
    metrics: dict[str, dict[str, Any]] = {}
    observed_ids: list[str] = []
    for index, value in enumerate(metric_values):
        metric = require_object(value, f"run metric {index}")
        metric_id = require_string(metric.get("id"), f"run metric {index}.id")
        if metric_id in metrics:
            raise fail_contradiction(f"Duplicate run metric ID: {metric_id}")
        observed_ids.append(metric_id)
        normalized = {
            "direction": metric.get("direction"),
            "identity": metric.get("identity"),
            "percentile": metric.get("percentile"),
            "statistic": metric.get("statistic"),
            "unit": metric.get("canonicalUnit"),
        }
        validate_metric_common(normalized, f"run metric {metric_id}")
        value = metric.get("canonicalValue")
        if isinstance(value, bool) or isinstance(value, str) or value is None or metric.get("direction") == "categorical":
            comparison_value: Any = {
                "allEqual": True,
                "distinctValues": [value],
                "unanimousValue": value,
            }
            aggregation_kind = "consensus"
            variation_reason = "categorical_metric"
        else:
            comparison_value = finite_number(value, f"run metric {metric_id}.canonicalValue")
            aggregation_kind = (
                "median_of_run_percentile"
                if str(metric.get("statistic", "")).startswith("sample_percentile_")
                else "median_of_independent_run_values"
            )
            variation_reason = "single_run_has_no_independent_variation"
        metrics[metric_id] = {
            "aggregationKind": aggregation_kind,
            **normalized,
            "value": comparison_value,
            "variationPct": None,
            "variationUnavailableReason": variation_reason,
        }
    if observed_ids != sorted(observed_ids):
        raise fail_contradiction("Run metric IDs are not sorted")
    benchmark = require_object(manifest.get("benchmark"), "run benchmark")
    profile = require_string(manifest.get("evidenceProfile"), "run evidence profile")
    expected_profile = "canonical" if status == "VALID_CANONICAL_MEMBER" else "experiment"
    if profile != expected_profile:
        raise fail_contradiction("Run status and evidence profile disagree")
    config_fingerprint = manifest.get("benchmarkConfigFingerprint")
    if not isinstance(config_fingerprint, str) or not PREFIXED_SHA256_RE.fullmatch(config_fingerprint):
        raise fail_contradiction("Run benchmark configuration fingerprint has an invalid form")
    environment_fingerprint = manifest.get("environmentFingerprint")
    if environment_fingerprint is not None and (
        not isinstance(environment_fingerprint, str)
        or not PREFIXED_SHA256_RE.fullmatch(environment_fingerprint)
    ):
        raise fail_contradiction("Run environment fingerprint has an invalid form")
    preset_id = benchmark.get("presetId")
    if preset_id is not None and (not isinstance(preset_id, str) or not preset_id):
        raise fail_contradiction("Run preset ID must be null or a non-empty string")
    return {
        "benchmarkConfigFingerprint": config_fingerprint,
        "environment": require_object(manifest.get("environment"), "run environment"),
        "environmentFingerprint": environment_fingerprint,
        "id": run_id,
        "kind": "run",
        "manifestDigest": "sha256:" + sha256_bytes(manifest_bytes),
        "memberCount": 1,
        "metrics": metrics,
        "metricsDigest": "sha256:" + metrics_digest,
        "mode": require_string(benchmark.get("mode"), "run mode"),
        "presetId": preset_id,
        "profile": profile,
        "source": source,
        "status": status,
        "suite": suite,
    }


def load_comparison_evidence(operand: Path, results_root: Path) -> dict[str, Any]:
    root, kind = evidence_directory(operand)
    if kind == "set":
        return validate_set_evidence(root, results_root)
    return validate_run_evidence(root)


def scientific_environment(environment: dict[str, Any] | None) -> dict[str, Any] | None:
    if environment is None:
        return None
    return {key: value for key, value in environment.items() if key != "provisioning"}


def compatibility_decision(
    baseline: dict[str, Any], candidate: dict[str, Any], allow_exploratory: bool
) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    comparable_fields = {
        "benchmark_configuration_fingerprint_mismatch": "benchmarkConfigFingerprint",
        "benchmark_mode_mismatch": "mode",
        "benchmark_preset_mismatch": "presetId",
        "source_repository_mismatch": None,
        "suite_mismatch": "suite",
    }
    for code, key in comparable_fields.items():
        if key is None:
            differs = baseline["source"]["repository"] != candidate["source"]["repository"]
        else:
            differs = baseline.get(key) != candidate.get(key)
        if differs:
            reasons.append(code)
    baseline_ids = set(baseline["metrics"])
    candidate_ids = set(candidate["metrics"])
    if baseline_ids != candidate_ids:
        reasons.append("metric_id_set_mismatch")
    else:
        for metric_id in sorted(baseline_ids):
            if comparison_metric_signature(baseline["metrics"][metric_id]) != comparison_metric_signature(
                candidate["metrics"][metric_id]
            ):
                reasons.append(f"metric_signature_mismatch:{metric_id}")
    environment_equal = baseline.get("environmentFingerprint") == candidate.get("environmentFingerprint")
    provisioning_only = False
    if not environment_equal:
        left_environment = baseline.get("environment")
        right_environment = candidate.get("environment")
        if (
            left_environment is not None
            and right_environment is not None
            and scientific_environment(left_environment) == scientific_environment(right_environment)
            and {left_environment.get("provisioning"), right_environment.get("provisioning")}
            == {"spot", "standard"}
        ):
            provisioning_only = True
        else:
            reasons.append("environment_fingerprint_mismatch")
    directly_comparable = (
        not reasons
        and environment_equal
        and baseline["kind"] == "set"
        and candidate["kind"] == "set"
        and baseline["status"] == "VALID_CANONICAL_SET"
        and candidate["status"] == "VALID_CANONICAL_SET"
    )
    if directly_comparable:
        return {"reasons": [], "status": "DIRECTLY_COMPARABLE", "warnings": []}
    if not allow_exploratory:
        if baseline["kind"] == "run" or candidate["kind"] == "run":
            reasons.append("derived_run_requires_exploratory")
        if baseline["profile"] != "canonical" or candidate["profile"] != "canonical":
            reasons.append("experiment_evidence_requires_exploratory")
        if provisioning_only:
            reasons.append("provisioning_mismatch_requires_exploratory")
        if not reasons:
            reasons.append("direct_comparison_requires_two_canonical_sets")
        return {"reasons": sorted(set(reasons)), "status": "INCOMPARABLE", "warnings": []}
    if reasons:
        return {"reasons": sorted(set(reasons)), "status": "INCOMPARABLE", "warnings": []}
    if baseline["kind"] == "run" or candidate["kind"] == "run":
        warnings.append("single_run_evidence_has_no_independent_run_variation")
    if baseline["profile"] != "canonical" or candidate["profile"] != "canonical":
        warnings.append("experiment_evidence_is_exploratory")
    if provisioning_only:
        warnings.append("provisioning_models_differ_comparison_is_exploratory")
    return {
        "reasons": [],
        "status": "COMPARABLE_WITH_WARNINGS",
        "warnings": sorted(set(warnings)),
    }


CONTINUOUS_STATISTICS = {
    "allocation_per_operation",
    "mean_time",
    "sample_mean",
    "throughput",
}
CLASSIFICATIONS = (
    "MATERIAL_IMPROVEMENT",
    "IMPROVEMENT",
    "NEUTRAL",
    "WARNING",
    "POSSIBLE_REGRESSION",
    "INCOMPARABLE",
    "INVALID",
)


def health_metric_name(metric: dict[str, Any]) -> str | None:
    name = metric["identity"].get("metricName")
    return name if isinstance(name, str) else None


def healthy_consensus(name: str, value: dict[str, Any]) -> bool | None:
    if not value["allEqual"]:
        return None
    unanimous = value["unanimousValue"]
    if name == "errors":
        return not isinstance(unanimous, bool) and isinstance(unanimous, (int, float)) and unanimous == 0
    if name == "analysis_status":
        return unanimous == "VALID"
    if name == "status":
        return unanimous == "PASS"
    if name == "review_required" or name.startswith("flag_"):
        return unanimous is False
    return None


def classify_metric(
    metric_id: str, baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "absoluteDelta": None,
        "baseline": {
            "value": baseline["value"],
            "variationPct": baseline["variationPct"],
            "variationUnavailableReason": baseline["variationUnavailableReason"],
        },
        "benefitPct": None,
        "candidate": {
            "value": candidate["value"],
            "variationPct": candidate["variationPct"],
            "variationUnavailableReason": candidate["variationUnavailableReason"],
        },
        "classification": None,
        "deltaPct": None,
        "direction": baseline["direction"],
        "identity": baseline["identity"],
        "materialLimitPct": None,
        "metricId": metric_id,
        "neutralLimitPct": None,
        "percentile": baseline.get("percentile"),
        "policyId": "diagnostic-only-v1",
        "reason": "diagnostic_metric_has_no_ordered_policy",
        "statistic": baseline["statistic"],
        "unit": baseline["unit"],
        "variationPct": None,
    }
    statistic = baseline["statistic"]
    continuous = statistic in CONTINUOUS_STATISTICS or statistic.startswith("sample_percentile_")
    if continuous and baseline["direction"] in {"higher", "lower"}:
        result["policyId"] = "continuous-relative-v1"
        baseline_value = baseline["value"]
        candidate_value = candidate["value"]
        if baseline_value == 0:
            result["reason"] = "baseline_median_zero"
            return result
        if baseline["variationPct"] is None or candidate["variationPct"] is None:
            result["reason"] = "independent_variation_unavailable"
            return result
        absolute_delta = candidate_value - baseline_value
        delta_pct = absolute_delta / abs(baseline_value) * 100
        variation = max(baseline["variationPct"], candidate["variationPct"])
        neutral = max(5, variation)
        material = max(10, 2 * variation)
        benefit = delta_pct if baseline["direction"] == "higher" else -delta_pct
        if abs(benefit) <= neutral:
            classification = "NEUTRAL"
        elif benefit > 0:
            classification = "MATERIAL_IMPROVEMENT" if benefit >= material else "IMPROVEMENT"
        else:
            classification = "POSSIBLE_REGRESSION" if -benefit >= material else "WARNING"
        result.update(
            {
                "absoluteDelta": absolute_delta,
                "benefitPct": benefit,
                "classification": classification,
                "deltaPct": delta_pct,
                "materialLimitPct": material,
                "neutralLimitPct": neutral,
                "reason": None,
                "variationPct": variation,
            }
        )
        return result
    name = health_metric_name(baseline)
    is_health = name in {"errors", "analysis_status", "status", "review_required"} or bool(
        name and name.startswith("flag_")
    )
    if is_health and isinstance(baseline["value"], dict) and isinstance(candidate["value"], dict):
        result["policyId"] = "health-consensus-v1"
        baseline_health = healthy_consensus(name or "", baseline["value"])
        candidate_health = healthy_consensus(name or "", candidate["value"])
        if baseline_health is not True:
            classification = "INVALID"
        elif candidate_health is True:
            classification = "NEUTRAL"
        elif candidate_health is False and (name == "review_required" or str(name).startswith("flag_")):
            classification = "WARNING"
        else:
            classification = "INVALID"
        result.update({"classification": classification, "reason": None})
        return result
    if baseline["aggregationKind"] == "consensus":
        result["policyId"] = "categorical-observation-v1"
        if (
            baseline["value"]["allEqual"]
            and candidate["value"]["allEqual"]
            and baseline["value"]["unanimousValue"] == candidate["value"]["unanimousValue"]
        ):
            result.update({"classification": "NEUTRAL", "reason": None})
        else:
            result["reason"] = "categorical_change_has_no_ordered_policy"
    return result


def compact_evidence(view: dict[str, Any]) -> dict[str, Any]:
    return {
        "benchmarkConfigFingerprint": view["benchmarkConfigFingerprint"],
        "environmentFingerprint": view["environmentFingerprint"],
        "evidenceId": view["id"],
        "evidenceKind": view["kind"],
        "manifestDigest": view["manifestDigest"],
        "memberCount": view["memberCount"],
        "metricsDigest": view["metricsDigest"],
        "mode": view["mode"],
        "presetId": view["presetId"],
        "profile": view["profile"],
        "source": view["source"],
        "status": view["status"],
        "suite": view["suite"],
    }


def comparison_identity(
    baseline: dict[str, Any], candidate: dict[str, Any], allow_exploratory: bool
) -> dict[str, Any]:
    def evidence_identity(view: dict[str, Any]) -> dict[str, Any]:
        return {
            "evidenceId": view["id"],
            "evidenceKind": view["kind"],
            "manifestDigest": view["manifestDigest"],
            "metricsDigest": view["metricsDigest"],
        }

    return {
        "baseline": evidence_identity(baseline),
        "candidate": evidence_identity(candidate),
        "comparisonPolicy": {"id": COMPARISON_POLICY_ID, "schemaVersion": 1},
        "requestedMode": "exploratory" if allow_exploratory else "direct",
        "schemaVersion": COMPARISON_SCHEMA_VERSION,
    }


def markdown_escape(value: Any) -> str:
    text = str(value).replace("\\", "\\\\").replace("|", "\\|")
    return "".join(" " if ord(character) < 32 or ord(character) == 127 else character for character in text)


def display_number(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        rendered = f"{value:.6f}".rstrip("0").rstrip(".")
        return "0" if rendered == "-0" else rendered
    if isinstance(value, dict):
        if value.get("allEqual"):
            return markdown_escape(value.get("unanimousValue"))
        return markdown_escape(value.get("distinctValues"))
    return markdown_escape(value)


def render_comparison_markdown(document: dict[str, Any]) -> bytes:
    compatibility = document["compatibility"]
    summary = document["summary"]
    lines = [
        "# Cloud benchmark comparison",
        "",
        f"Comparison ID: `{document['comparisonId']}`",
        "",
        "## Evidence",
        "",
        "| Role | Kind | ID | Commit | Profile | Mode | Members |",
        "|---|---|---|---|---|---|---:|",
    ]
    for role in ("baseline", "candidate"):
        evidence = document[role]
        lines.append(
            "| "
            + " | ".join(
                markdown_escape(value)
                for value in (
                    role,
                    evidence["evidenceKind"],
                    evidence["evidenceId"],
                    evidence["source"]["commit"],
                    evidence["profile"],
                    evidence["mode"],
                    evidence["memberCount"],
                )
            )
            + " |"
        )
    lines.extend(["", "## Compatibility", "", f"Status: **{compatibility['status']}**"])
    if compatibility["reasons"]:
        lines.extend(["", "Reasons:", "", *[f"- `{markdown_escape(item)}`" for item in compatibility["reasons"]]])
    if compatibility["warnings"]:
        lines.extend(["", "Warnings:", "", *[f"- `{markdown_escape(item)}`" for item in compatibility["warnings"]]])
    lines.extend(
        [
            "",
            "## Classification summary",
            "",
            "| Classification | Count |",
            "|---|---:|",
            *[f"| {name} | {summary['classificationCounts'][name]} |" for name in CLASSIFICATIONS],
            f"| UNCLASSIFIED | {summary['unclassified']} |",
        ]
    )
    groups = (
        ("Continuous performance", lambda item: item["policyId"] == "continuous-relative-v1"),
        ("Categorical and health findings", lambda item: item["policyId"] in {"health-consensus-v1", "categorical-observation-v1"}),
        ("Diagnostic and unclassified observations", lambda item: item["policyId"] == "diagnostic-only-v1"),
    )
    for title, predicate in groups:
        rows = [item for item in document["metrics"] if predicate(item)]
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                "| Metric | Statistic | Baseline | Candidate | Unit | Delta % | Classification | Note |",
                "|---|---|---:|---:|---|---:|---|---|",
            ]
        )
        for item in rows:
            statistic = item["statistic"]
            if statistic.startswith("sample_percentile_"):
                statistic += " (median of run percentiles)"
            lines.append(
                "| "
                + " | ".join(
                    (
                        markdown_escape(item["metricId"]),
                        markdown_escape(statistic),
                        display_number(item["baseline"]["value"]),
                        display_number(item["candidate"]["value"]),
                        markdown_escape(item["unit"]),
                        display_number(item["deltaPct"]),
                        markdown_escape(item["classification"] or "UNCLASSIFIED"),
                        markdown_escape(item["reason"] or ""),
                    )
                )
                + " |"
            )
        if not rows:
            lines.append("| _none_ | — | — | — | — | — | — | — |")
    lines.extend(
        [
            "",
            "## Evidence limitations",
            "",
            "Set percentiles are medians of independent run percentiles, not pooled request percentiles.",
            "Single-run evidence has no independent-run variation and receives no synthetic confidence interval.",
            "This Phase 3 report is evidence for review and is not a hard performance gate.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def write_comparison_artifacts(
    results_root: Path, comparison_id: str, document: dict[str, Any]
) -> Path:
    json_bytes = canonical_json_bytes(document)
    markdown_bytes = render_comparison_markdown(document)
    checksum_bytes = (
        f"{sha256_bytes(json_bytes)}  comparison.json\n"
        f"{sha256_bytes(markdown_bytes)}  comparison.md\n"
    ).encode("utf-8")
    expected = {
        "comparison-checksums.sha256": checksum_bytes,
        "comparison.json": json_bytes,
        "comparison.md": markdown_bytes,
    }
    destination = results_root.resolve() / "comparisons" / comparison_id / "v1"
    if destination.exists():
        try:
            actual = {
                entry.name: entry.read_bytes()
                for entry in destination.iterdir()
                if entry.is_file() and not entry.is_symlink()
            }
        except OSError as error:
            raise fail_contradiction(f"Cannot validate existing comparison output: {error}") from error
        if actual != expected or {entry.name for entry in destination.iterdir()} != set(expected):
            raise fail_contradiction(f"Existing comparison artifact collision: {destination}")
        return destination
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = destination.parent / f".v1.{uuid.uuid4().hex}"
        staging.mkdir()
    except OSError as error:
        raise fail_config(f"Cannot create comparison output directory: {error}") from error
    try:
        try:
            for name, content in expected.items():
                atomic_write_bytes(staging / name, content)
            os.replace(staging, destination)
        except OSError as error:
            raise fail_config(f"Cannot finalize comparison output: {error}") from error
    finally:
        if staging.exists():
            for child in staging.iterdir():
                child.unlink()
            staging.rmdir()
    return destination


GCS_BUCKET_RE = re.compile(r"^gs://([a-z0-9][a-z0-9._-]{1,61}[a-z0-9])$")
CRC32C_RE = re.compile(r"^[A-Za-z0-9+/]{6}==$")
MD5_RE = re.compile(r"^[A-Za-z0-9+/]{22}==$")
RECEIPT_SCHEMA_VERSION = 1


def make_crc32c_table() -> tuple[int, ...]:
    values = []
    for byte in range(256):
        crc = byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
        values.append(crc)
    return tuple(values)


CRC32C_TABLE = make_crc32c_table()


def validate_gcs_bucket(value: str) -> str:
    if not isinstance(value, str) or GCS_BUCKET_RE.fullmatch(value) is None:
        raise fail_config(
            "GSE_BENCHMARK_GCS_BUCKET must be one bucket URI such as gs://example-bucket"
        )
    return value


def split_gcs_uri(uri: str) -> tuple[str, str]:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if match is None or any(ord(character) < 32 for character in uri):
        raise fail_contradiction(f"Invalid immutable GCS object URI: {uri!r}")
    return match.group(1), match.group(2)


def crc32c_file(path: Path) -> str:
    crc = 0xFFFFFFFF
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                for byte in chunk:
                    crc = CRC32C_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    except OSError as error:
        raise fail_invalid(f"Cannot calculate CRC32C for {path}: {error}") from error
    value = (crc ^ 0xFFFFFFFF).to_bytes(4, "big")
    return base64.b64encode(value).decode("ascii")


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise fail_invalid(f"Cannot calculate MD5 for {path}: {error}") from error
    return base64.b64encode(digest.digest()).decode("ascii")


def local_object_integrity(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        raise fail_invalid(f"Upload source is missing, non-regular, or symlinked: {path}")
    return {
        "crc32c": crc32c_file(path),
        "md5": md5_file(path),
        "sha256": sha256_file(path),
        "size": str(path.stat().st_size),
    }


def regular_files(root: Path) -> list[Path]:
    if not root.is_dir() or root.is_symlink():
        raise fail_invalid(f"Evidence directory is missing or symlinked: {root}")
    files: list[Path] = []
    for current, directories, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        for directory in directories:
            if (current_path / directory).is_symlink():
                raise fail_invalid(f"Evidence contains a symlinked directory: {current_path / directory}")
        for name in names:
            path = current_path / name
            if not path.is_file() or path.is_symlink():
                raise fail_invalid(f"Evidence contains a non-regular or symlinked file: {path}")
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def checked_relative(path: Path, owner: Path) -> str:
    try:
        relative = path.resolve().relative_to(owner.resolve())
    except ValueError as error:
        raise fail_contradiction(f"Upload source escapes its evidence owner: {path}") from error
    text = relative.as_posix()
    if (
        not text
        or text.startswith("/")
        or "\\" in text
        or "#" in text
        or "?" in text
        or any(part in {"", ".", ".."} for part in relative.parts)
        or any(ord(character) < 32 for character in text)
    ):
        raise fail_contradiction(f"Unsafe upload relative path: {text!r}")
    return text


def upload_object(role: str, owner: Path, path: Path, uri: str) -> dict[str, Any]:
    integrity = local_object_integrity(path)
    return {
        "crc32c": integrity["crc32c"],
        "md5": integrity["md5"],
        "relativePath": checked_relative(path, owner),
        "role": role,
        "sha256": "sha256:" + integrity["sha256"],
        "size": integrity["size"],
        "sourcePath": path.resolve(),
        "uri": uri,
    }


def results_root_for_evidence(root: Path, kind: str) -> Path:
    if kind == "run":
        if root.name != "v1" or root.parent.parent.name != "runs" or root.parent.parent.parent.name != "derived":
            raise fail_contradiction("Derived-run evidence is outside the fixed results layout")
        return root.parents[3]
    if root.name != "v1" or root.parent.parent.name != "sets":
        raise fail_contradiction("Set evidence is outside the fixed results layout")
    return root.parents[2]


def run_upload_plan(root: Path, results_root: Path, bucket: str) -> dict[str, Any]:
    view = validate_run_evidence(root)
    expected_root = results_root / "derived" / "runs" / view["id"] / "v1"
    if root.resolve() != expected_root.resolve():
        raise fail_contradiction("Derived-run directory does not match its validated run ID")
    raw = results_root / view["id"]
    output, manifest, _ = derive_manifest(raw, evidence_profile=view["profile"])
    if output.resolve() != root.resolve() or "sha256:" + sha256_file(output / "benchmark-manifest.json") != view["manifestDigest"]:
        raise fail_contradiction("Derived-run source reconstruction differs from the supplied evidence")
    metadata, _ = read_properties(raw / "metadata.txt", metadata=True)
    record_path = orchestration_path_for(raw, metadata, None)
    _, record_digest, _ = validate_orchestration(
        raw,
        metadata,
        read_properties(raw / "status.properties")[0],
        record_path,
    )
    if manifest.get("evidence", {}).get("orchestrationRecordSha256") != record_digest:
        raise fail_contradiction("Derived run no longer binds its orchestration record")
    commit = view["source"]["commit"]
    prefix = f"{bucket}/general-search-engine"
    objects = [
        upload_object(
            "raw", raw, path,
            f"{prefix}/raw/{commit}/{view['id']}/{checked_relative(path, raw)}",
        )
        for path in regular_files(raw)
    ]
    record_owner = record_path.parent
    objects.append(
        upload_object(
            "orchestration", record_owner, record_path,
            f"{prefix}/orchestration/{commit}/{view['id']}/{record_path.name}",
        )
    )
    log_path = record_path.with_suffix(".log")
    if log_path.exists() or log_path.is_symlink():
        objects.append(
            upload_object(
                "orchestration", record_owner, log_path,
                f"{prefix}/orchestration/{commit}/{view['id']}/{log_path.name}",
            )
        )
    objects.extend(
        upload_object(
            "derived-run", root, path,
            f"{prefix}/derived/runs/{view['id']}/v1/{checked_relative(path, root)}",
        )
        for path in regular_files(root)
    )
    return {
        "_manifestPath": root / "benchmark-manifest.json",
        "_orchestrationPath": record_path.resolve(),
        "objects": sorted(objects, key=lambda item: item["uri"]),
        "source": {
            "benchmarkConfigFingerprint": view["benchmarkConfigFingerprint"],
            "environmentFingerprint": view["environmentFingerprint"],
            "evidenceProfile": view["profile"],
            "id": view["id"],
            "kind": "derived-run",
            "manifestSha256": view["manifestDigest"],
            "sourceCommit": commit,
        },
    }


def deduplicate_upload_objects(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_uri: dict[str, dict[str, Any]] = {}
    for item in objects:
        existing = by_uri.get(item["uri"])
        if existing is None:
            by_uri[item["uri"]] = item
        elif any(existing[key] != item[key] for key in ("sha256", "size", "crc32c", "md5")):
            raise fail_contradiction(f"Upload URI maps to contradictory source bytes: {item['uri']}")
    return [by_uri[uri] for uri in sorted(by_uri)]


def set_upload_plan(root: Path, results_root: Path, bucket: str) -> dict[str, Any]:
    view = validate_set_evidence(root, results_root)
    expected_root = results_root / "sets" / view["id"] / "v1"
    if root.resolve() != expected_root.resolve():
        raise fail_contradiction("Set directory does not match its validated set ID")
    manifest = require_object(read_json(root / "benchmark-set-manifest.json"), "set manifest")
    member_objects: list[dict[str, Any]] = []
    for index, raw_member in enumerate(require_list(manifest.get("members"), "set members")):
        member = require_object(raw_member, f"set member {index}")
        manifest_path = safe_results_reference(results_root, member.get("manifestReference"))
        member_plan = run_upload_plan(manifest_path.parent, results_root, bucket)
        source = member_plan["source"]
        checks = {
            "run ID": (source["id"], member.get("rawRunId")),
            "manifest digest": (source["manifestSha256"], member.get("manifestSha256")),
            "profile": (source["evidenceProfile"], view["profile"]),
            "source commit": (source["sourceCommit"], view["source"]["commit"]),
            "environment fingerprint": (source["environmentFingerprint"], view["environmentFingerprint"]),
            "benchmark fingerprint": (source["benchmarkConfigFingerprint"], view["benchmarkConfigFingerprint"]),
        }
        for label, (actual, expected) in checks.items():
            if actual != expected:
                raise fail_contradiction(f"Set member {index} {label} differs during upload planning")
        orchestration_path = safe_results_reference(results_root, member.get("orchestrationReference"))
        if orchestration_path.resolve() != member_plan["_orchestrationPath"]:
            raise fail_contradiction(f"Set member {index} orchestration reference differs")
        if "sha256:" + sha256_file(orchestration_path) != member.get("orchestrationSha256"):
            raise fail_contradiction(f"Set member {index} orchestration digest differs")
        metrics_path = safe_results_reference(results_root, member.get("metricsReference"))
        if metrics_path.resolve() != manifest_path.parent / "normalized-metrics.json":
            raise fail_contradiction(f"Set member {index} metrics reference differs")
        if "sha256:" + sha256_file(metrics_path) != member.get("metricsSha256"):
            raise fail_contradiction(f"Set member {index} metrics digest differs")
        member_objects.extend(member_plan["objects"])
    prefix = f"{bucket}/general-search-engine/sets/{view['id']}/v1"
    set_objects = [
        upload_object(
            "benchmark-set", root, path, f"{prefix}/{checked_relative(path, root)}"
        )
        for path in regular_files(root)
    ]
    return {
        "_manifestPath": root / "benchmark-set-manifest.json",
        "objects": deduplicate_upload_objects([*member_objects, *set_objects]),
        "source": {
            "benchmarkConfigFingerprint": view["benchmarkConfigFingerprint"],
            "environmentFingerprint": view["environmentFingerprint"],
            "evidenceProfile": view["profile"],
            "id": view["id"],
            "kind": "benchmark-set",
            "manifestSha256": view["manifestDigest"],
            "sourceCommit": view["source"]["commit"],
        },
    }


def plan_evidence_upload(operand: Path, results_root: Path, bucket: str) -> dict[str, Any]:
    canonical_bucket = validate_gcs_bucket(bucket)
    root, kind = evidence_directory(operand)
    expected_results = results_root.resolve()
    if results_root_for_evidence(root, kind).resolve() != expected_results:
        raise fail_config("Upload evidence is outside the configured results root")
    plan = (
        set_upload_plan(root, expected_results, canonical_bucket)
        if kind == "set"
        else run_upload_plan(root, expected_results, canonical_bucket)
    )
    plan["bucket"] = canonical_bucket
    return plan


def normalized_remote_metadata(metadata: Any, uri: str) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        raise fail_upload(f"Remote object metadata is not an object: {uri}")
    bucket, name = split_gcs_uri(uri)
    generation = str(metadata.get("generation", ""))
    size = str(metadata.get("size", ""))
    custom = metadata.get("custom_fields")
    if metadata.get("bucket") != bucket or metadata.get("name") != name:
        raise fail_upload(f"Remote object identity differs: {uri}")
    if re.fullmatch(r"[1-9][0-9]*", generation) is None:
        raise fail_upload(f"Remote object generation is invalid: {uri}")
    if re.fullmatch(r"0|[1-9][0-9]*", size) is None:
        raise fail_upload(f"Remote object size is invalid: {uri}")
    crc32c = metadata.get("crc32c_hash")
    if not isinstance(crc32c, str) or CRC32C_RE.fullmatch(crc32c) is None:
        raise fail_upload(f"Remote object CRC32C is unavailable: {uri}")
    if not isinstance(custom, dict) or set(custom) != {"gse-sha256"}:
        raise fail_upload(f"Remote object SHA-256 metadata is unavailable: {uri}")
    sha256 = custom.get("gse-sha256")
    if not isinstance(sha256, str) or SHA256_RE.fullmatch(sha256) is None:
        raise fail_upload(f"Remote object SHA-256 metadata is invalid: {uri}")
    md5 = metadata.get("md5_hash")
    if md5 is not None and (not isinstance(md5, str) or MD5_RE.fullmatch(md5) is None):
        raise fail_upload(f"Remote object MD5 metadata is invalid: {uri}")
    return {
        "bucket": bucket,
        "crc32c": crc32c,
        "generation": generation,
        "md5": md5,
        "name": name,
        "sha256": sha256,
        "size": size,
    }


def verify_remote_upload_object(item: dict[str, Any], metadata: Any) -> dict[str, Any]:
    remote = normalized_remote_metadata(metadata, item["uri"])
    expected_sha = item["sha256"].removeprefix("sha256:")
    checks = {
        "size": (remote["size"], item["size"]),
        "CRC32C": (remote["crc32c"], item["crc32c"]),
        "SHA-256 metadata": (remote["sha256"], expected_sha),
    }
    if remote["md5"] is not None:
        checks["MD5"] = (remote["md5"], item["md5"])
    for label, (actual, expected) in checks.items():
        if actual != expected:
            raise fail_upload(f"Remote object {label} differs: {item['uri']}")
    entry = {
        "crc32c": remote["crc32c"],
        "generation": remote["generation"],
        "relativePath": item["relativePath"],
        "role": item["role"],
        "sha256": item["sha256"],
        "size": remote["size"],
        "uri": item["uri"],
    }
    if remote["md5"] is not None:
        entry["md5"] = remote["md5"]
    return entry


class GcloudStorage:
    def _run(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["gcloud", *arguments],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as error:
            raise fail_upload(f"Cannot execute gcloud storage command: {error}") from error

    def describe(self, uri: str) -> dict[str, Any] | None:
        result = self._run([
            "storage", "objects", "describe", uri,
            "--format=json(bucket,name,generation,size,crc32c_hash,md5_hash,custom_fields)",
        ])
        if result.returncode != 0:
            return None
        try:
            value = json.loads(result.stdout, object_pairs_hook=strict_object)
        except (BenchmarkV2Error, json.JSONDecodeError) as error:
            raise fail_upload(f"Cannot parse remote object metadata for {uri}") from error
        if not isinstance(value, dict):
            raise fail_upload(f"Remote object metadata is not an object: {uri}")
        return value

    def create(self, source: Path, uri: str, sha256_hex: str) -> None:
        result = self._run([
            "storage", "cp", str(source), uri,
            "--if-generation-match=0",
            f"--custom-metadata=gse-sha256={sha256_hex}",
            "--quiet",
        ])
        if result.returncode != 0:
            raise fail_upload(f"Create-only GCS upload failed: {uri}")


def upload_and_verify_object(item: dict[str, Any], storage: Any) -> dict[str, Any]:
    current = local_object_integrity(item["sourcePath"])
    if any(
        current[key] != item[key]
        for key in ("crc32c", "md5", "size")
    ) or "sha256:" + current["sha256"] != item["sha256"]:
        raise fail_contradiction(f"Upload source changed after planning: {item['sourcePath']}")
    metadata = storage.describe(item["uri"])
    if metadata is None:
        try:
            storage.create(item["sourcePath"], item["uri"], current["sha256"])
        except BenchmarkV2Error as error:
            metadata = storage.describe(item["uri"])
            if metadata is None:
                raise error
        if metadata is None:
            metadata = storage.describe(item["uri"])
    if metadata is None:
        raise fail_upload(f"Uploaded object is missing during verification: {item['uri']}")
    return verify_remote_upload_object(item, metadata)


def receipt_documents(plan: dict[str, Any], objects: list[dict[str, Any]]) -> tuple[dict[str, Any], bytes, bytes]:
    identity = {
        "bucket": plan["bucket"],
        "kind": "cloud-benchmark-upload-receipt",
        "objects": sorted(objects, key=lambda item: item["uri"]),
        "schemaVersion": RECEIPT_SCHEMA_VERSION,
        "source": plan["source"],
    }
    receipt_id = "gse-upload-receipt-v1-" + sha256_bytes(canonical_json_bytes(identity))
    receipt = {**identity, "receiptId": receipt_id}
    content = canonical_json_bytes(receipt)
    checksum = f"{sha256_bytes(content)}  upload-receipt.json\n".encode("utf-8")
    return receipt, content, checksum


def receipt_upload_objects(
    bucket: str, receipt: dict[str, Any], receipt_path: Path, checksum_path: Path
) -> list[dict[str, Any]]:
    prefix = f"{bucket}/general-search-engine/receipts/{receipt['receiptId']}/v1"
    return [
        upload_object("receipt", receipt_path.parent, receipt_path, f"{prefix}/upload-receipt.json"),
        upload_object("receipt", checksum_path.parent, checksum_path, f"{prefix}/upload-receipt.sha256"),
    ]


def write_immutable_directory(destination: Path, files: dict[str, bytes]) -> None:
    if destination.exists():
        if not destination.is_dir() or destination.is_symlink():
            raise fail_contradiction(f"Immutable artifact path is not a directory: {destination}")
        entries = list(destination.iterdir())
        if {entry.name for entry in entries} != set(files):
            raise fail_contradiction(f"Immutable artifact file set differs: {destination}")
        if any(not entry.is_file() or entry.is_symlink() for entry in entries):
            raise fail_contradiction(f"Immutable artifact contains a non-regular file: {destination}")
        if any((destination / name).read_bytes() != content for name, content in files.items()):
            raise fail_contradiction(f"Immutable artifact collision: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        for name, content in files.items():
            atomic_write_bytes(staging / name, content)
        os.replace(staging, destination)
    except OSError as error:
        raise fail_contradiction(f"Cannot finalize immutable artifact directory: {error}") from error
    finally:
        if staging.exists():
            for child in staging.iterdir():
                child.unlink()
            staging.rmdir()


def upload_evidence(
    operand: Path,
    results_root: Path,
    bucket: str,
    *,
    storage: Any | None = None,
    confirmed: bool = False,
    dry_run: bool = False,
) -> tuple[Path | None, dict[str, Any]]:
    plan = plan_evidence_upload(operand, results_root, bucket)
    if dry_run:
        return None, plan
    if not confirmed:
        raise fail_config("Upload requires --confirm-upload before contacting GCS")
    backend = storage if storage is not None else GcloudStorage()
    verified = [upload_and_verify_object(item, backend) for item in plan["objects"]]
    receipt, content, checksum = receipt_documents(plan, verified)
    with tempfile.TemporaryDirectory(prefix="gse-upload-receipt.") as temporary:
        temporary_root = Path(temporary)
        receipt_path = temporary_root / "upload-receipt.json"
        checksum_path = temporary_root / "upload-receipt.sha256"
        receipt_path.write_bytes(content)
        checksum_path.write_bytes(checksum)
        for item in receipt_upload_objects(plan["bucket"], receipt, receipt_path, checksum_path):
            upload_and_verify_object(item, backend)
    destination = (
        results_root.resolve() / "upload-receipts" / receipt["receiptId"] / "v1"
    )
    write_immutable_directory(
        destination,
        {"upload-receipt.json": content, "upload-receipt.sha256": checksum},
    )
    return destination, receipt


REGISTRY_ENTRY_KEYS = {
    "benchmarkConfigFingerprint",
    "environmentFingerprint",
    "evidenceProfile",
    "manifestGeneration",
    "manifestUri",
    "setId",
    "setManifestSha256",
    "sourceCommit",
    "uploadReceiptId",
    "uploadReceiptSha256",
}


def validate_baseline_registry(path: Path) -> dict[str, Any]:
    try:
        source_bytes = path.read_bytes()
    except OSError as error:
        raise fail_registry(f"Cannot read baseline registry {path}: {error}") from error
    try:
        document = json.loads(source_bytes.decode("utf-8"), object_pairs_hook=strict_object)
    except BenchmarkV2Error as error:
        raise fail_registry(str(error)) from error
    except (UnicodeError, json.JSONDecodeError) as error:
        raise fail_registry(f"Cannot parse baseline registry {path}: {error}") from error
    if not isinstance(document, dict):
        raise fail_registry("Baseline registry must be an object")
    try:
        if source_bytes != canonical_json_bytes(document):
            raise fail_registry("Baseline registry is not canonical JSON")
    except BenchmarkV2Error as error:
        raise fail_registry(str(error)) from error
    if set(document) != {"baselines", "kind", "schemaVersion"}:
        raise fail_registry("Baseline registry top-level fields differ")
    if document.get("kind") != "cloud-benchmark-baseline-registry" or document.get("schemaVersion") != 1:
        raise fail_registry("Baseline registry kind or schema is unsupported")
    baselines = document.get("baselines")
    if not isinstance(baselines, dict):
        raise fail_registry("Baseline registry baselines must be an object")
    if list(baselines) != sorted(baselines):
        raise fail_registry("Baseline registry names are not sorted")
    for name, raw_entry in baselines.items():
        if not BASELINE_NAME_RE.fullmatch(name):
            raise fail_registry(f"Invalid baseline name: {name}")
        if not isinstance(raw_entry, dict):
            raise fail_registry(f"Baseline {name} must be an object")
        allowed = REGISTRY_ENTRY_KEYS | {"releaseLabel"}
        if set(raw_entry) - allowed or not REGISTRY_ENTRY_KEYS <= set(raw_entry):
            raise fail_registry(f"Baseline {name} fields differ")
        set_id = raw_entry.get("setId")
        if not isinstance(set_id, str) or not SET_ID_RE.fullmatch(set_id):
            raise fail_registry(f"Baseline {name} has an invalid set ID")
        for key in ("setManifestSha256", "environmentFingerprint", "benchmarkConfigFingerprint", "uploadReceiptSha256"):
            value = raw_entry.get(key)
            if not isinstance(value, str) or not PREFIXED_SHA256_RE.fullmatch(value):
                raise fail_registry(f"Baseline {name} has an invalid {key}")
        if raw_entry.get("evidenceProfile") != "canonical":
            raise fail_registry(f"Baseline {name} is not canonical")
        commit = raw_entry.get("sourceCommit")
        if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
            raise fail_registry(f"Baseline {name} has an invalid source commit")
        receipt_id = raw_entry.get("uploadReceiptId")
        if not isinstance(receipt_id, str) or not RECEIPT_ID_RE.fullmatch(receipt_id):
            raise fail_registry(f"Baseline {name} has an invalid upload receipt ID")
        generation = raw_entry.get("manifestGeneration")
        if not isinstance(generation, str) or not re.fullmatch(r"[1-9][0-9]*", generation):
            raise fail_registry(f"Baseline {name} has an invalid manifest generation")
        uri = raw_entry.get("manifestUri")
        expected_uri = re.compile(
            rf"^gs://[a-z0-9][a-z0-9._-]{{1,61}}[a-z0-9]/general-search-engine/sets/"
            rf"{re.escape(set_id)}/v1/benchmark-set-manifest\.json$"
        )
        if (
            not isinstance(uri, str)
            or expected_uri.fullmatch(uri) is None
        ):
            raise fail_registry(f"Baseline {name} has an invalid immutable manifest URI")
        if "releaseLabel" in raw_entry:
            label = raw_entry["releaseLabel"]
            if not isinstance(label, str) or not label or len(label) > 100 or "\n" in label or "\r" in label:
                raise fail_registry(f"Baseline {name} has an invalid release label")
    return document


def resolve_registry_baseline(
    name: str, registry_path: Path, results_root: Path
) -> Path:
    if not BASELINE_NAME_RE.fullmatch(name):
        raise fail_config(f"Baseline operand is neither a path nor a valid registry name: {name}")
    registry = validate_baseline_registry(registry_path)
    entry = registry["baselines"].get(name)
    if entry is None:
        raise fail_registry(f"Unknown baseline name: {name}")
    root = results_root.resolve() / "sets" / entry["setId"] / "v1"
    if not root.is_dir():
        raise fail_registry(f"Registered baseline has no local set: {name}")
    try:
        view = validate_set_evidence(root, results_root)
    except BenchmarkV2Error as error:
        raise fail_registry(f"Registered baseline local set is invalid: {error}") from error
    expected = {
        "benchmarkConfigFingerprint": view["benchmarkConfigFingerprint"],
        "environmentFingerprint": view["environmentFingerprint"],
        "evidenceProfile": view["profile"],
        "setId": view["id"],
        "setManifestSha256": view["manifestDigest"],
        "sourceCommit": view["source"]["commit"],
    }
    if any(entry.get(key) != value for key, value in expected.items()):
        raise fail_registry(f"Registered baseline local binding differs: {name}")
    return root


def validate_immutable_baseline_name(
    registry: dict[str, Any], name: str, proposed_entry: dict[str, Any]
) -> bool:
    if not BASELINE_NAME_RE.fullmatch(name):
        raise fail_registry(f"Invalid baseline name: {name}")
    baselines = registry.get("baselines")
    if not isinstance(baselines, dict):
        raise fail_registry("Baseline registry baselines must be an object")
    existing = baselines.get(name)
    if existing is None:
        return False
    if existing != proposed_entry:
        raise fail_registry(f"Immutable baseline name already has different evidence: {name}")
    return True


def valid_base64(value: Any, pattern: re.Pattern[str], field: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise fail_registry(f"Upload receipt {field} is invalid")
    try:
        base64.b64decode(value, validate=True)
    except ValueError as error:
        raise fail_registry(f"Upload receipt {field} is invalid") from error
    return value


def validate_upload_receipt(path: Path, results_root: Path) -> tuple[Path, dict[str, Any], str]:
    candidate = path.resolve()
    root = candidate.parent if candidate.is_file() and candidate.name == "upload-receipt.json" else candidate
    try:
        verify_exact_checksum_file(root, "upload-receipt.sha256", ("upload-receipt.json",))
        receipt, content = canonical_document(root / "upload-receipt.json")
    except BenchmarkV2Error as error:
        raise fail_registry(f"Upload receipt is invalid: {error}") from error
    if set(receipt) != {"bucket", "kind", "objects", "receiptId", "schemaVersion", "source"}:
        raise fail_registry("Upload receipt top-level fields differ")
    if receipt.get("kind") != "cloud-benchmark-upload-receipt" or receipt.get("schemaVersion") != 1:
        raise fail_registry("Upload receipt kind or schema is unsupported")
    receipt_id = receipt.get("receiptId")
    if not isinstance(receipt_id, str) or RECEIPT_ID_RE.fullmatch(receipt_id) is None:
        raise fail_registry("Upload receipt ID is invalid")
    expected_root = results_root.resolve() / "upload-receipts" / receipt_id / "v1"
    if root != expected_root:
        raise fail_registry("Upload receipt is outside its fixed local identity path")
    bucket = receipt.get("bucket")
    try:
        validate_gcs_bucket(bucket)
    except BenchmarkV2Error as error:
        raise fail_registry(str(error)) from error
    source = receipt.get("source")
    if not isinstance(source, dict) or set(source) != {
        "benchmarkConfigFingerprint",
        "environmentFingerprint",
        "evidenceProfile",
        "id",
        "kind",
        "manifestSha256",
        "sourceCommit",
    }:
        raise fail_registry("Upload receipt source fields differ")
    if source.get("kind") not in {"derived-run", "benchmark-set"}:
        raise fail_registry("Upload receipt source kind is unsupported")
    if source.get("evidenceProfile") not in {"experiment", "canonical"}:
        raise fail_registry("Upload receipt evidence profile is invalid")
    source_id = source.get("id")
    expected_id = (
        SET_ID_RE if source.get("kind") == "benchmark-set" else re.compile(r"^[A-Za-z0-9._-]+$")
    )
    if not isinstance(source_id, str) or expected_id.fullmatch(source_id) is None:
        raise fail_registry("Upload receipt source ID is invalid")
    if not isinstance(source.get("sourceCommit"), str) or COMMIT_RE.fullmatch(source["sourceCommit"]) is None:
        raise fail_registry("Upload receipt source commit is invalid")
    for key in ("manifestSha256", "benchmarkConfigFingerprint"):
        if not isinstance(source.get(key), str) or PREFIXED_SHA256_RE.fullmatch(source[key]) is None:
            raise fail_registry(f"Upload receipt source {key} is invalid")
    environment_fingerprint = source.get("environmentFingerprint")
    if environment_fingerprint is not None and (
        not isinstance(environment_fingerprint, str)
        or PREFIXED_SHA256_RE.fullmatch(environment_fingerprint) is None
    ):
        raise fail_registry("Upload receipt source environmentFingerprint is invalid")
    raw_objects = receipt.get("objects")
    if not isinstance(raw_objects, list) or not raw_objects:
        raise fail_registry("Upload receipt objects must be a non-empty array")
    uris: list[str] = []
    for index, raw in enumerate(raw_objects):
        if not isinstance(raw, dict):
            raise fail_registry(f"Upload receipt object {index} must be an object")
        required = {"crc32c", "generation", "relativePath", "role", "sha256", "size", "uri"}
        if set(raw) not in {frozenset(required), frozenset(required | {"md5"})}:
            raise fail_registry(f"Upload receipt object {index} fields differ")
        if raw.get("role") not in {"raw", "orchestration", "derived-run", "benchmark-set"}:
            raise fail_registry(f"Upload receipt object {index} role is invalid")
        relative = raw.get("relativePath")
        if (
            not isinstance(relative, str)
            or not relative
            or relative.startswith("/")
            or "\\" in relative
            or "#" in relative
            or "?" in relative
            or any(part in {"", ".", ".."} for part in Path(relative).parts)
            or any(ord(character) < 32 for character in relative)
        ):
            raise fail_registry(f"Upload receipt object {index} relative path is invalid")
        uri = raw.get("uri")
        if not isinstance(uri, str) or not uri.startswith(bucket + "/general-search-engine/"):
            raise fail_registry(f"Upload receipt object {index} URI is invalid")
        try:
            split_gcs_uri(uri)
        except BenchmarkV2Error as error:
            raise fail_registry(str(error)) from error
        uris.append(uri)
        if not isinstance(raw.get("generation"), str) or re.fullmatch(r"[1-9][0-9]*", raw["generation"]) is None:
            raise fail_registry(f"Upload receipt object {index} generation is invalid")
        if not isinstance(raw.get("size"), str) or re.fullmatch(r"0|[1-9][0-9]*", raw["size"]) is None:
            raise fail_registry(f"Upload receipt object {index} size is invalid")
        if not isinstance(raw.get("sha256"), str) or PREFIXED_SHA256_RE.fullmatch(raw["sha256"]) is None:
            raise fail_registry(f"Upload receipt object {index} SHA-256 is invalid")
        valid_base64(raw.get("crc32c"), CRC32C_RE, f"object {index} CRC32C")
        if "md5" in raw:
            valid_base64(raw["md5"], MD5_RE, f"object {index} MD5")
    if uris != sorted(uris) or len(uris) != len(set(uris)):
        raise fail_registry("Upload receipt object URIs are not sorted and unique")
    identity = {key: value for key, value in receipt.items() if key != "receiptId"}
    expected_receipt_id = "gse-upload-receipt-v1-" + sha256_bytes(canonical_json_bytes(identity))
    if receipt_id != expected_receipt_id:
        raise fail_registry("Upload receipt ID contradicts its identity projection")
    return root, receipt, "sha256:" + sha256_bytes(content)


def verify_recorded_remote_object(entry: dict[str, Any], storage: Any) -> None:
    metadata = storage.describe(entry["uri"])
    if metadata is None:
        raise fail_upload(f"Registered receipt object is missing: {entry['uri']}")
    remote = normalized_remote_metadata(metadata, entry["uri"])
    expected = {
        "CRC32C": (remote["crc32c"], entry["crc32c"]),
        "generation": (remote["generation"], entry["generation"]),
        "SHA-256 metadata": (remote["sha256"], entry["sha256"].removeprefix("sha256:")),
        "size": (remote["size"], entry["size"]),
    }
    if "md5" in entry:
        expected["MD5"] = (remote["md5"], entry["md5"])
    for label, (actual, wanted) in expected.items():
        if actual != wanted:
            raise fail_upload(f"Registered receipt object {label} differs: {entry['uri']}")


def matching_receipt_paths(results_root: Path, set_id: str, manifest_digest: str) -> list[Path]:
    parent = results_root.resolve() / "upload-receipts"
    if not parent.is_dir():
        return []
    matches: list[Path] = []
    for candidate in sorted(parent.glob("*/v1")):
        try:
            root, receipt, _ = validate_upload_receipt(candidate, results_root)
        except BenchmarkV2Error:
            continue
        source = receipt["source"]
        if (
            source["kind"] == "benchmark-set"
            and source["id"] == set_id
            and source["manifestSha256"] == manifest_digest
        ):
            matches.append(root)
    return matches


def atomic_replace_registry(path: Path, document: dict[str, Any]) -> None:
    content = canonical_json_bytes(document)
    try:
        handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        with os.fdopen(handle, "wb") as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        validate_baseline_registry(temporary)
        os.replace(temporary, path)
        try:
            directory_handle = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_handle)
            finally:
                os.close(directory_handle)
        except OSError:
            pass
    except BenchmarkV2Error:
        raise
    except OSError as error:
        raise fail_registry(f"Cannot atomically update baseline registry: {error}") from error
    finally:
        if "temporary" in locals() and temporary.exists():
            temporary.unlink()


def register_cloud_baseline(
    name: str,
    set_operand: Path,
    results_root: Path,
    registry_path: Path,
    *,
    receipt_path: Path | None = None,
    release_label: str | None = None,
    storage: Any | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    try:
        root, kind = evidence_directory(set_operand)
        if kind != "set":
            raise fail_registry("Only a completed canonical set can be registered")
        if results_root_for_evidence(root, kind).resolve() != results_root.resolve():
            raise fail_registry("Baseline set is outside the configured results root")
        view = validate_set_evidence(root, results_root.resolve())
    except BenchmarkV2Error as error:
        if error.exit_code == EXIT_REGISTRY:
            raise
        raise fail_registry(f"Baseline set is invalid: {error}") from error
    if view["status"] != "VALID_CANONICAL_SET" or view["profile"] != "canonical":
        raise fail_registry("Only VALID_CANONICAL_SET evidence can be registered")
    if release_label is not None and (
        not release_label or len(release_label) > 100 or "\n" in release_label or "\r" in release_label
    ):
        raise fail_registry("Baseline release label is invalid")
    if receipt_path is None:
        matches = matching_receipt_paths(results_root, view["id"], view["manifestDigest"])
        if not matches:
            raise fail_registry("No verified local upload receipt binds the canonical set")
        if len(matches) != 1:
            raise fail_registry("Multiple upload receipts bind the set; use --receipt")
        selected_receipt = matches[0]
    else:
        selected_receipt = receipt_path
    receipt_root, receipt, receipt_digest = validate_upload_receipt(selected_receipt, results_root)
    source = receipt["source"]
    expected_source = {
        "benchmarkConfigFingerprint": view["benchmarkConfigFingerprint"],
        "environmentFingerprint": view["environmentFingerprint"],
        "evidenceProfile": "canonical",
        "id": view["id"],
        "kind": "benchmark-set",
        "manifestSha256": view["manifestDigest"],
        "sourceCommit": view["source"]["commit"],
    }
    if source != expected_source:
        raise fail_registry("Upload receipt does not bind the exact canonical set")
    manifest_uri = (
        f"{receipt['bucket']}/general-search-engine/sets/{view['id']}/v1/benchmark-set-manifest.json"
    )
    manifest_entry = next((item for item in receipt["objects"] if item["uri"] == manifest_uri), None)
    if manifest_entry is None or manifest_entry["sha256"] != view["manifestDigest"]:
        raise fail_registry("Upload receipt lacks the exact canonical set manifest")
    entry = {
        "benchmarkConfigFingerprint": view["benchmarkConfigFingerprint"],
        "environmentFingerprint": view["environmentFingerprint"],
        "evidenceProfile": "canonical",
        "manifestGeneration": manifest_entry["generation"],
        "manifestUri": manifest_uri,
        "setId": view["id"],
        "setManifestSha256": view["manifestDigest"],
        "sourceCommit": view["source"]["commit"],
        "uploadReceiptId": receipt["receiptId"],
        "uploadReceiptSha256": receipt_digest,
    }
    if release_label is not None:
        entry["releaseLabel"] = release_label
    registry = validate_baseline_registry(registry_path)
    if not BASELINE_NAME_RE.fullmatch(name):
        raise fail_registry(f"Invalid baseline name: {name}")
    if name in registry["baselines"]:
        raise fail_registry(f"Immutable baseline name already exists: {name}")
    candidate = {
        **registry,
        "baselines": {
            key: value
            for key, value in sorted({**registry["baselines"], name: entry}.items())
        },
    }
    if dry_run:
        return entry
    backend = storage if storage is not None else GcloudStorage()
    for item in receipt["objects"]:
        verify_recorded_remote_object(item, backend)
    prefix = f"{receipt['bucket']}/general-search-engine/receipts/{receipt['receiptId']}/v1"
    for item in receipt_upload_objects(
        receipt["bucket"], receipt,
        receipt_root / "upload-receipt.json",
        receipt_root / "upload-receipt.sha256",
    ):
        metadata = backend.describe(item["uri"])
        if metadata is None:
            raise fail_upload(f"Remote upload receipt object is missing: {item['uri']}")
        verify_remote_upload_object(item, metadata)
        if not item["uri"].startswith(prefix + "/"):
            raise fail_registry("Remote receipt path contradicts its receipt ID")
    atomic_replace_registry(registry_path, candidate)
    return entry


def compare_benchmarks(
    baseline_operand: str | Path,
    candidate_operand: str | Path,
    *,
    results_root: Path,
    registry_path: Path,
    allow_exploratory: bool = False,
) -> tuple[Path, dict[str, Any], int]:
    results = results_root.resolve()
    baseline_path = Path(baseline_operand)
    if not baseline_path.exists():
        baseline_path = resolve_registry_baseline(str(baseline_operand), registry_path, results)
    candidate_path = Path(candidate_operand)
    if not candidate_path.exists():
        raise fail_config(f"Candidate evidence operand does not exist: {candidate_operand}")
    baseline = load_comparison_evidence(baseline_path, results)
    candidate = load_comparison_evidence(candidate_path, results)
    compatibility = compatibility_decision(baseline, candidate, allow_exploratory)
    identity = comparison_identity(baseline, candidate, allow_exploratory)
    comparison_id = "gse-comparison-v1-" + sha256_bytes(canonical_json_bytes(identity))
    metric_results: list[dict[str, Any]] = []
    if compatibility["status"] in {"DIRECTLY_COMPARABLE", "COMPARABLE_WITH_WARNINGS"}:
        metric_results = [
            classify_metric(metric_id, baseline["metrics"][metric_id], candidate["metrics"][metric_id])
            for metric_id in sorted(baseline["metrics"])
        ]
    counts = {name: 0 for name in CLASSIFICATIONS}
    unclassified = 0
    for metric in metric_results:
        classification = metric["classification"]
        if classification is None:
            unclassified += 1
        else:
            counts[classification] += 1
    document = {
        "baseline": compact_evidence(baseline),
        "candidate": compact_evidence(candidate),
        "comparisonId": comparison_id,
        "compatibility": compatibility,
        "identity": identity,
        "kind": "benchmark-comparison",
        "metrics": metric_results,
        "policy": {"id": COMPARISON_POLICY_ID, "schemaVersion": 1},
        "requestedMode": "exploratory" if allow_exploratory else "direct",
        "schemaVersion": COMPARISON_SCHEMA_VERSION,
        "status": "COMPLETE",
        "summary": {
            "classificationCounts": counts,
            "metricsCompared": len(metric_results),
            "unclassified": unclassified,
        },
    }
    output = write_comparison_artifacts(results, comparison_id, document)
    exit_code = EXIT_INCOMPARABLE if compatibility["status"] == "INCOMPARABLE" else 0
    return output, document, exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GeneralSearchEngine Cloud Benchmark V2 analysis")
    parser.add_argument("--version", action="version", version="benchmark_v2 schema 1")
    subparsers = parser.add_subparsers(dest="command", required=True)
    manifest = subparsers.add_parser("manifest", help="derive a run manifest and normalized metrics")
    manifest.add_argument("raw_run_dir", type=Path)
    manifest.add_argument("--orchestration-record", type=Path)
    manifest.add_argument("--output-dir", type=Path)
    manifest.add_argument(
        "--evidence-profile", choices=("experiment", "canonical"), default="experiment"
    )
    def add_plan_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("--evidence-profile", choices=("experiment", "canonical"), required=True)
        command.add_argument("--repeats", type=int, required=True)
        command.add_argument("--mode", required=True)
        command.add_argument("--preset-id")
        command.add_argument("--repository", required=True)
        command.add_argument("--commit", required=True)
        command.add_argument("--control", action="append", default=[])

    validate_set = subparsers.add_parser("set-validate", help=argparse.SUPPRESS)
    add_plan_arguments(validate_set)
    initialize = subparsers.add_parser("set-init", help=argparse.SUPPRESS)
    initialize.add_argument("workspace", type=Path)
    add_plan_arguments(initialize)
    next_slot = subparsers.add_parser("set-next", help=argparse.SUPPRESS)
    next_slot.add_argument("workspace", type=Path)
    begin = subparsers.add_parser("set-begin", help=argparse.SUPPRESS)
    begin.add_argument("workspace", type=Path)
    begin.add_argument("--slot", type=int, required=True)
    record = subparsers.add_parser("set-record", help=argparse.SUPPRESS)
    record.add_argument("workspace", type=Path)
    record.add_argument("--slot", type=int, required=True)
    record.add_argument("--v1-exit", type=int, required=True)
    reconcile = subparsers.add_parser("set-reconcile", help=argparse.SUPPRESS)
    reconcile.add_argument("workspace", type=Path)
    authorize = subparsers.add_parser("set-authorize", help=argparse.SUPPRESS)
    authorize.add_argument("workspace", type=Path)
    authorize.add_argument("--slot", type=int, required=True)
    authorize.add_argument("--reason", required=True)
    authorize.add_argument("--confirm-no-score-selection", action="store_true")
    value = subparsers.add_parser("set-value", help=argparse.SUPPRESS)
    value.add_argument("workspace", type=Path)
    value.add_argument("key")
    finalize = subparsers.add_parser("set-finalize", help=argparse.SUPPRESS)
    finalize.add_argument("workspace", type=Path)
    compare = subparsers.add_parser("compare", help="compare completed benchmark evidence")
    compare.add_argument("--allow-exploratory", action="store_true")
    compare.add_argument("--results-root", type=Path, required=True)
    compare.add_argument("--registry", type=Path, required=True)
    compare.add_argument("baseline")
    compare.add_argument("candidate")
    registry_validate = subparsers.add_parser(
        "registry-validate", help="validate the read-only baseline registry"
    )
    registry_validate.add_argument("registry", type=Path)
    registry_list = subparsers.add_parser("registry-list", help=argparse.SUPPRESS)
    registry_list.add_argument("registry", type=Path)
    upload = subparsers.add_parser("upload", help="retain verified evidence in immutable GCS objects")
    upload.add_argument("--results-root", type=Path, required=True)
    upload.add_argument("--bucket", required=True)
    upload.add_argument("--dry-run", action="store_true")
    upload.add_argument("--confirm-upload", action="store_true")
    upload.add_argument("operand", type=Path)
    register = subparsers.add_parser("baseline-register", help="register a verified canonical set")
    register.add_argument("--results-root", type=Path, required=True)
    register.add_argument("--registry", type=Path, required=True)
    register.add_argument("--receipt", type=Path)
    register.add_argument("--release-label")
    register.add_argument("--dry-run", action="store_true")
    register.add_argument("name")
    register.add_argument("set_operand", type=Path)
    return parser


def main(arguments: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("ERROR: benchmark_v2.py requires Python 3.11 or newer", file=sys.stderr)
        return EXIT_CONFIG
    try:
        options = build_parser().parse_args(arguments)
        if options.command == "manifest":
            output_dir, manifest, metrics = derive_manifest(
                options.raw_run_dir,
                orchestration_record=options.orchestration_record,
                output_directory=options.output_dir,
                evidence_profile=options.evidence_profile,
            )
            print(f"Manifest: {output_dir / 'benchmark-manifest.json'}")
            print(f"Normalized metrics: {output_dir / 'normalized-metrics.json'}")
            print(f"Status: {manifest['status']}; metrics={len(metrics['metrics'])}")
            return 0
        if options.command in {"set-validate", "set-init"}:
            controls = parse_controls(options.control)
            plan = validate_set_plan_inputs(
                options.evidence_profile,
                options.repeats,
                options.mode,
                options.preset_id,
                options.repository,
                options.commit,
                controls,
            )
            if options.command == "set-validate":
                print(f"Set plan: VALID; profile={plan['evidenceProfile']}; slots={plan['repeats']}")
            else:
                root, _ = initialize_set_workspace(
                    options.workspace,
                    options.evidence_profile,
                    options.repeats,
                    options.mode,
                    options.preset_id,
                    options.repository,
                    options.commit,
                    controls,
                )
                print(f"Set workspace: {root}")
            return 0
        if options.command == "set-next":
            _, _, checkpoint = load_set_workspace(options.workspace)
            current = checkpoint.get("currentAttempt")
            if isinstance(current, dict):
                print(f"RUNNING\t{current['slot']}\t{current['attempt']}")
            elif checkpoint["state"] == "COMPLETE":
                print(f"COMPLETE\t{checkpoint['finalSetId']}")
            elif checkpoint["state"] != "READY":
                print(f"{checkpoint['state']}\t-")
            elif checkpoint["nextPendingSlot"] is None:
                print("FINALIZE\t-")
            else:
                slot = checkpoint_slot(checkpoint, int(checkpoint["nextPendingSlot"]))
                print(f"PENDING\t{slot['slot']}\t{int(slot['attemptCount']) + 1}")
            return 0
        if options.command == "set-begin":
            intent = begin_set_attempt(options.workspace, options.slot)
            print(f"{intent['pointer']}\t{intent['log']}\t{intent['attempt']}")
            return 0
        if options.command == "set-record":
            if options.v1_exit < 0 or options.v1_exit > 255:
                raise fail_config("V1 exit must be between 0 and 255")
            result = record_set_attempt(options.workspace, options.slot, options.v1_exit)
            print(f"Attempt recorded: slot={options.slot}; outcome={result}")
            return result
        if options.command == "set-reconcile":
            result = reconcile_running_attempt(options.workspace)
            print(f"Attempt reconciliation: {result}")
            return result
        if options.command == "set-authorize":
            path = authorize_set_replacement(
                options.workspace,
                options.slot,
                options.reason,
                options.confirm_no_score_selection,
            )
            print(f"Replacement authorization: {path}")
            return 0
        if options.command == "set-value":
            _, plan, checkpoint = load_set_workspace(options.workspace)
            value: Any = {"plan": plan, "checkpoint": checkpoint}
            for component in options.key.split("."):
                if not isinstance(value, dict) or component not in value:
                    raise fail_config(f"Unknown set value: {options.key}")
                value = value[component]
            if value is None:
                print("")
            elif isinstance(value, (str, int, float, bool)):
                print(str(value).lower() if isinstance(value, bool) else value)
            else:
                raise fail_config(f"Set value is not scalar: {options.key}")
            return 0
        if options.command == "set-finalize":
            output, manifest = finalize_benchmark_set(options.workspace)
            print(f"Benchmark set: {output}")
            print(f"Status: {manifest['status']}; members={len(manifest['members'])}")
            return 0
        if options.command == "registry-validate":
            registry = validate_baseline_registry(options.registry)
            print(f"Baseline registry: VALID; baselines={len(registry['baselines'])}")
            return 0
        if options.command == "registry-list":
            registry = validate_baseline_registry(options.registry)
            for name, entry in registry["baselines"].items():
                print(f"{name}\t{entry['setId']}\t{entry['sourceCommit']}")
            return 0
        if options.command == "upload":
            destination, result = upload_evidence(
                options.operand,
                options.results_root,
                options.bucket,
                confirmed=options.confirm_upload,
                dry_run=options.dry_run,
            )
            if options.dry_run:
                print(f"Upload plan: VALID; source={result['source']['kind']}; objects={len(result['objects'])}")
                print(f"Bucket: {result['bucket']}")
                for item in result["objects"]:
                    print(
                        f"Object: {item['role']}\t{item['size']}\t"
                        f"{item['sha256']}\t{item['uri']}"
                    )
            else:
                print(f"Upload receipt: {destination}")
                print(f"Receipt ID: {result['receiptId']}; objects={len(result['objects'])}")
            return 0
        if options.command == "baseline-register":
            entry = register_cloud_baseline(
                options.name,
                options.set_operand,
                options.results_root,
                options.registry,
                receipt_path=options.receipt,
                release_label=options.release_label,
                dry_run=options.dry_run,
            )
            action = "Registration plan" if options.dry_run else "Baseline registered"
            print(f"{action}: {options.name}; set={entry['setId']}")
            if options.dry_run:
                print(f"Manifest: {entry['manifestUri']}#{entry['manifestGeneration']}")
                print(f"Receipt: {entry['uploadReceiptId']} {entry['uploadReceiptSha256']}")
            return 0
        if options.command == "compare":
            output, document, result = compare_benchmarks(
                options.baseline,
                options.candidate,
                results_root=options.results_root,
                registry_path=options.registry,
                allow_exploratory=options.allow_exploratory,
            )
            print(f"Comparison: {output}")
            print(
                f"Compatibility: {document['compatibility']['status']}; "
                f"metrics={document['summary']['metricsCompared']}"
            )
            return result
        raise fail_config(f"Unsupported command: {options.command}")
    except BenchmarkV2Error as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
