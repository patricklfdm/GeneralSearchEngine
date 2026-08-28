#!/usr/bin/env python3
"""Deterministic Cloud Benchmark V2 evidence derivation.

The remote workload remains Bash/Java.  This dependency-free Python 3.11+ utility
validates recovered V1 evidence and writes only to the sibling derived tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


EXIT_CONFIG = 2
EXIT_INVALID_EVIDENCE = 80
EXIT_UNSUPPORTED = 81
EXIT_CONTRADICTION = 82

MANIFEST_SCHEMA_VERSION = 1
METRICS_SCHEMA_VERSION = 1
FINGERPRINT_SCHEMA_VERSION = 1
SUPPORTED_RAW_SCHEMAS = {0, 1}
CANONICAL_MODES = {"full", "concurrency", "soak", "all"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
CURRENT_CONCURRENCY_RE = re.compile(
    r"^concurrent-(?:latency|throughput)-([1-9][0-9]*)-([1-9][0-9]*)$"
)
LEGACY_CONCURRENCY_RE = re.compile(
    r"^concurrent-read-write-([1-9][0-9]*)-([1-9][0-9]*)$"
)
SYNTHETIC_PERCENTILE_RE = re.compile(r"^(?:read:|write:)?p[0-9.]+$")


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
    fingerprint_payload = {
        "provider": common["provider"],
        "zone": common["zone"],
        "machineType": common["machineType"],
        "provisioning": common["provisioning"],
        "cpu": common["cpu"],
        "memoryBytes": common["memoryBytes"],
        "image": {
            "project": common["image"]["project"],
            "resolvedName": common["image"]["resolvedName"],
            "id": common["image"]["id"],
        },
        "kernelRelease": common["kernelRelease"],
        "java": common["java"],
        "jvmOptions": common["jvmOptions"],
    }
    return common, fingerprint(fingerprint_payload), True


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
        raise fail_config(f"Unsupported command: {options.command}")
    except BenchmarkV2Error as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
