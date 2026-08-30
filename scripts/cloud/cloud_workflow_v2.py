#!/usr/bin/env python3
"""No-cloud control plane for the manual Cloud Benchmark V2 workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any, Iterable


EXIT_CONFIG = 2
EXIT_CONTRADICTION = 82
MAX_ARTIFACT_BYTES = 100 * 1024 * 1024
REPOSITORY = "https://github.com/patricklfdm/GeneralSearchEngine.git"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SET_ID_RE = re.compile(r"^gse-set-v1-[0-9a-f]{64}$")
RECEIPT_ID_RE = re.compile(r"^gse-upload-receipt-v1-[0-9a-f]{64}$")
PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
ZONE_RE = re.compile(r"^[a-z][a-z0-9-]*-[a-z0-9]+-[a-z]$")
IMAGE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
BUCKET_RE = re.compile(r"^gs://[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
WIF_RE = re.compile(
    r"^projects/[0-9]+/locations/global/workloadIdentityPools/"
    r"[a-z0-9-]{4,32}/providers/[a-z0-9-]{4,32}$"
)
SERVICE_ACCOUNT_RE = re.compile(
    r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$"
)
SET_CHECKSUM_FILES = (
    "benchmark-set-manifest.json",
    "aggregate-metrics.json",
    "set-attempt-audit.json",
)
SET_FILES = SET_CHECKSUM_FILES + (
    "set-checksums.sha256",
)
DERIVED_FILES = (
    "benchmark-manifest.json",
    "normalized-metrics.json",
    "derived-checksums.sha256",
)
EXIT_CATEGORIES = {
    0: "success",
    2: "configuration",
    10: "provisioning",
    20: "remote-setup",
    30: "benchmark",
    40: "spot-interruption",
    50: "artifact-collection",
    60: "checksum-evidence",
    70: "cleanup",
    80: "evidence-invalid",
    81: "unsupported-schema",
    82: "evidence-contradiction",
    83: "set-incompatible",
    84: "comparison-incompatible",
    85: "registry-invalid",
    86: "durable-upload",
}


class WorkflowError(Exception):
    def __init__(self, message: str, code: int = EXIT_CONFIG):
        super().__init__(message)
        self.code = code


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkflowError(f"Cannot read canonical JSON {path.name}: {error}", EXIT_CONTRADICTION) from error


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = canonical_bytes(value)
    if path.exists() and path.read_bytes() != content:
        raise WorkflowError(f"Refusing to replace different workflow state: {path.name}", EXIT_CONTRADICTION)
    path.write_bytes(content)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def single_line(value: str, label: str) -> str:
    if not value or value != value.strip() or any(character in value for character in "\r\n\0"):
        raise WorkflowError(f"{label} must be a nonempty trimmed single line")
    return value


def git(repository: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if check and result.returncode != 0:
        raise WorkflowError(f"Git validation failed: {' '.join(arguments)}")
    return result


def normalize_remote(value: str) -> str:
    normalized = value.strip().removesuffix(".git")
    if normalized == "git@github.com:patricklfdm/GeneralSearchEngine":
        return REPOSITORY.removesuffix(".git")
    return normalized


def validate_source(repository: Path, source_commit: str, trusted_ref: str) -> None:
    if COMMIT_RE.fullmatch(source_commit) is None:
        raise WorkflowError("source_commit must be an exact lowercase 40-character SHA")
    origin = git(repository, "remote", "get-url", "origin").stdout.strip()
    if normalize_remote(origin) != REPOSITORY.removesuffix(".git"):
        raise WorkflowError("origin is not the reviewed GeneralSearchEngine repository")
    object_result = git(repository, "cat-file", "-e", f"{source_commit}^{{commit}}", check=False)
    if object_result.returncode != 0:
        raise WorkflowError("source_commit is not an available commit in the reviewed repository")
    ancestor = git(repository, "merge-base", "--is-ancestor", source_commit, trusted_ref, check=False)
    if ancestor.returncode != 0:
        raise WorkflowError(f"source_commit must be reachable from protected {trusted_ref}")


def make_plan(options: argparse.Namespace) -> dict[str, Any]:
    allowed = {
        "evidence_profile": {"experiment", "canonical"},
        "mode": {"quick", "full", "concurrency", "soak", "ranked-v31", "all"},
        "repeats": {"1", "3", "5"},
        "provisioning": {"spot", "standard"},
        "machine_type": {"c3d-standard-30", "c3d-standard-60"},
        "soak_duration": {"30m", "2h"},
        "retention": {"actions", "gcs"},
    }
    values = {name: str(getattr(options, name)) for name in allowed}
    for name, choices in allowed.items():
        if values[name] not in choices:
            raise WorkflowError(f"Unsupported {name}: {values[name]!r}")

    profile = values["evidence_profile"]
    mode = values["mode"]
    repeats = int(values["repeats"])
    if profile == "canonical":
        if mode == "quick":
            raise WorkflowError("Canonical workflow does not accept quick mode")
        if repeats not in {3, 5}:
            raise WorkflowError("Canonical workflow requires three or five repeats")
        if values["provisioning"] != "standard":
            raise WorkflowError("Canonical workflow requires Standard provisioning")
        if values["retention"] != "gcs":
            raise WorkflowError("Canonical workflow requires GCS retention")
    if values["soak_duration"] == "2h" and not (
        profile == "experiment" and repeats == 1 and mode in {"soak", "all"}
    ):
        raise WorkflowError("Two-hour soak is limited to a one-repeat soak/all experiment")
    if mode not in {"soak", "all"} and values["soak_duration"] != "30m":
        raise WorkflowError("Non-soak modes require the default 30m soak duration")

    requested = options.source_commit or options.dispatch_sha
    source_commit = single_line(requested, "source_commit")
    validate_source(Path(options.repository_root).resolve(), source_commit, options.trusted_ref)
    soak_seconds = 7200 if values["soak_duration"] == "2h" else 1800
    max_runtime = {
        "quick": 7200,
        "full": 21600,
        "concurrency": 21600,
        "soak": soak_seconds + 7200,
        "ranked-v31": 3600,
        "all": max(21600, soak_seconds + 7200),
    }[mode]
    run_id = single_line(str(options.run_id), "run_id")
    run_attempt = single_line(str(options.run_attempt), "run_attempt")
    if not run_id.isdigit() or not run_attempt.isdigit():
        raise WorkflowError("GitHub run ID and attempt must be decimal integers")
    request = {
        "evidenceProfile": profile,
        "machineType": values["machine_type"],
        "mode": mode,
        "provisioning": values["provisioning"],
        "repeats": repeats,
        "retention": values["retention"],
        "soakDuration": values["soak_duration"],
    }
    derived = {
        "maxVmRuntimeSeconds": max_runtime,
        "presetId": (
            "v3.1-ranked-v1"
            if profile == "canonical" and mode == "ranked-v31"
            else f"v3-production-{mode}-v1" if profile == "canonical" else None
        ),
        "soakSeconds": soak_seconds,
    }
    if mode == "ranked-v31":
        derived["jvmOptions"] = "-Xms32g -Xmx64g"
    return {
        "artifact": {"name": f"cloud-performance-{run_id}-{run_attempt}-{profile}", "retentionDays": 14},
        "derived": derived,
        "kind": "cloud-benchmark-workflow-plan",
        "request": request,
        "run": {"attempt": int(run_attempt), "id": int(run_id)},
        "schemaVersion": 1,
        "source": {"commit": source_commit, "repository": REPOSITORY, "trustedRef": options.trusted_ref},
    }


def validate_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict) or plan.get("kind") != "cloud-benchmark-workflow-plan" or plan.get("schemaVersion") != 1:
        raise WorkflowError("Workflow plan schema is unsupported", EXIT_CONTRADICTION)
    expected = {"artifact", "derived", "kind", "request", "run", "schemaVersion", "source"}
    if set(plan) != expected:
        raise WorkflowError("Workflow plan fields differ", EXIT_CONTRADICTION)
    return plan


def write_github_output(path: str | None, values: dict[str, str]) -> None:
    if not path:
        return
    output = Path(path)
    with output.open("a", encoding="utf-8") as handle:
        for name, value in values.items():
            if not re.fullmatch(r"[a-z_][a-z0-9_]*", name) or any(c in value for c in "\r\n\0"):
                raise WorkflowError("Unsafe GitHub output")
            handle.write(f"{name}={value}\n")


def validate_config(plan: dict[str, Any], environment: dict[str, str]) -> None:
    checks = {
        "GSE_CLOUD_WIF_PROVIDER": WIF_RE,
        "GSE_CLOUD_SERVICE_ACCOUNT": SERVICE_ACCOUNT_RE,
        "GSE_GCP_PROJECT": PROJECT_RE,
        "GSE_GCP_ZONE": ZONE_RE,
        "GSE_CLOUD_IMAGE": IMAGE_RE,
    }
    for name, pattern in checks.items():
        value = single_line(environment.get(name, ""), name)
        if pattern.fullmatch(value) is None:
            raise WorkflowError(f"{name} has an invalid reviewed value")
    bucket = environment.get("GSE_BENCHMARK_GCS_BUCKET", "")
    if plan["request"]["retention"] == "gcs":
        if not bucket:
            raise WorkflowError("GSE_BENCHMARK_GCS_BUCKET must be one exact gs://bucket URI")
        if BUCKET_RE.fullmatch(single_line(bucket, "GSE_BENCHMARK_GCS_BUCKET")) is None:
            raise WorkflowError("GSE_BENCHMARK_GCS_BUCKET must be one exact gs://bucket URI")
    elif bucket and (bucket != bucket.strip() or any(c in bucket for c in "\r\n\0") or BUCKET_RE.fullmatch(bucket) is None):
        raise WorkflowError("Configured GSE_BENCHMARK_GCS_BUCKET has an invalid value")


def verify_checksums(root: Path, checksum_name: str, names: Iterable[str]) -> None:
    checksum = root / checksum_name
    if not checksum.is_file() or checksum.is_symlink():
        raise WorkflowError(f"Missing safe checksum file: {checksum_name}", EXIT_CONTRADICTION)
    expected = [f"{sha256_file(root / name)}  {name}" for name in names]
    try:
        actual = checksum.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise WorkflowError(f"Cannot read {checksum_name}: {error}", EXIT_CONTRADICTION) from error
    if actual != expected:
        raise WorkflowError(f"Checksum verification failed: {checksum_name}", EXIT_CONTRADICTION)


def locate_set(results_root: Path, plan: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    candidates: list[tuple[Path, dict[str, Any]]] = []
    sets_root = results_root / "sets"
    for manifest_path in sorted(sets_root.glob("gse-set-v1-*/v1/benchmark-set-manifest.json")):
        root = manifest_path.parent
        if root.is_symlink() or any(not (root / name).is_file() or (root / name).is_symlink() for name in SET_FILES):
            continue
        if {path.name for path in root.iterdir()} != set(SET_FILES):
            continue
        manifest = read_json(manifest_path)
        request = plan["request"]
        source = manifest.get("source", {}) if isinstance(manifest, dict) else {}
        if (
            manifest.get("source", {}).get("commit") == plan["source"]["commit"]
            and manifest.get("evidenceProfile") == request["evidenceProfile"]
            and manifest.get("mode") == request["mode"]
            and len(manifest.get("members", [])) == request["repeats"]
            and source.get("repository") == REPOSITORY
        ):
            candidates.append((root, manifest))
    if len(candidates) != 1:
        raise WorkflowError(f"Expected exactly one completed matching set; found {len(candidates)}", EXIT_CONTRADICTION)
    root, manifest = candidates[0]
    set_id = manifest.get("setId")
    if not isinstance(set_id, str) or SET_ID_RE.fullmatch(set_id) is None or root.parent.name != set_id:
        raise WorkflowError("Completed set identity is invalid", EXIT_CONTRADICTION)
    expected_status = "VALID_CANONICAL_SET" if plan["request"]["evidenceProfile"] == "canonical" else "VALID_EXPERIMENT_SET"
    if manifest.get("status") != expected_status:
        raise WorkflowError("Completed set status contradicts the workflow profile", EXIT_CONTRADICTION)
    verify_checksums(root, "set-checksums.sha256", SET_CHECKSUM_FILES)
    return root, manifest


def exit_category(code: int) -> str:
    return EXIT_CATEGORIES.get(code, "workflow-infrastructure")


def benchmark_result(options: argparse.Namespace) -> dict[str, Any]:
    plan = validate_plan(read_json(Path(options.plan)))
    dry_exit = int(options.dry_run_exit)
    benchmark_exit = int(options.benchmark_exit)
    primary_exit = dry_exit if dry_exit else benchmark_exit
    stage = "dry-run" if dry_exit else "benchmark"
    result: dict[str, Any] = {
        "benchmark": {"dryRunExit": dry_exit, "exit": benchmark_exit, "status": "failed" if primary_exit else "complete"},
        "kind": "cloud-benchmark-workflow-result",
        "primary": {"category": exit_category(primary_exit), "exit": primary_exit, "stage": stage if primary_exit else "complete"},
        "schemaVersion": 1,
        "set": None,
        "upload": {"exit": None, "receipt": None, "status": "pending"},
    }
    if primary_exit == 0:
        try:
            root, manifest = locate_set(Path(options.results_root).resolve(), plan)
            result["set"] = {
                "id": manifest["setId"],
                "memberCount": len(manifest["members"]),
                "relativePath": root.relative_to(Path(options.results_root).resolve()).as_posix(),
                "status": manifest["status"],
            }
        except WorkflowError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            result["benchmark"]["status"] = "failed"
            result["primary"] = {
                "category": exit_category(error.code),
                "exit": error.code,
                "stage": "set-discovery",
            }
    return result


def validate_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("kind") != "cloud-benchmark-workflow-result" or value.get("schemaVersion") != 1:
        raise WorkflowError("Workflow result schema is unsupported", EXIT_CONTRADICTION)
    return value


def receipt_for_set(results_root: Path, set_id: str) -> tuple[Path, dict[str, Any]]:
    matches = []
    for path in sorted((results_root / "upload-receipts").glob("gse-upload-receipt-v1-*/v1/upload-receipt.json")):
        receipt = read_json(path)
        source = receipt.get("source", {}) if isinstance(receipt, dict) else {}
        if source.get("kind") == "benchmark-set" and source.get("id") == set_id:
            matches.append((path.parent, receipt))
    if len(matches) != 1:
        raise WorkflowError(f"Expected exactly one upload receipt for {set_id}; found {len(matches)}", EXIT_CONTRADICTION)
    root, receipt = matches[0]
    receipt_id = receipt.get("receiptId")
    if not isinstance(receipt_id, str) or RECEIPT_ID_RE.fullmatch(receipt_id) is None or root.parent.name != receipt_id:
        raise WorkflowError("Upload receipt identity is invalid", EXIT_CONTRADICTION)
    if set(receipt) != {"bucket", "kind", "objects", "receiptId", "schemaVersion", "source"}:
        raise WorkflowError("Upload receipt fields differ", EXIT_CONTRADICTION)
    verify_checksums(root, "upload-receipt.sha256", ("upload-receipt.json",))
    return root, receipt


def update_upload(options: argparse.Namespace) -> dict[str, Any]:
    plan = validate_plan(read_json(Path(options.plan)))
    result = validate_result(read_json(Path(options.result)))
    upload_exit = int(options.upload_exit)
    retention = plan["request"]["retention"]
    if result["primary"]["exit"] != 0:
        result["upload"] = {"exit": None, "receipt": None, "status": "not-run"}
    elif retention == "actions":
        result["upload"] = {"exit": None, "receipt": None, "status": "not-requested"}
    elif upload_exit:
        result["upload"] = {"exit": upload_exit, "receipt": None, "status": "failed"}
    else:
        _, receipt = receipt_for_set(Path(options.results_root).resolve(), result["set"]["id"])
        objects = receipt.get("objects")
        if not isinstance(objects, list) or not objects:
            raise WorkflowError("Upload receipt object inventory is empty", EXIT_CONTRADICTION)
        manifest_uri = next(
            (item.get("uri") for item in objects if isinstance(item, dict) and item.get("uri", "").endswith("/benchmark-set-manifest.json")),
            None,
        )
        if not isinstance(manifest_uri, str) or not manifest_uri.startswith("gs://"):
            raise WorkflowError("Upload receipt has no immutable set manifest URI", EXIT_CONTRADICTION)
        result["upload"] = {
            "exit": 0,
            "receipt": {"id": receipt["receiptId"], "manifestUri": manifest_uri, "objectCount": len(objects)},
            "status": "complete",
        }
    return result


def safe_results_path(results_root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        raise WorkflowError("Artifact reference must be a portable relative path", EXIT_CONTRADICTION)
    parts = Path(value).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise WorkflowError("Artifact reference escapes the results root", EXIT_CONTRADICTION)
    path = results_root.joinpath(*parts)
    resolved = path.resolve()
    try:
        resolved.relative_to(results_root.resolve())
    except ValueError as error:
        raise WorkflowError("Artifact reference escapes the results root", EXIT_CONTRADICTION) from error
    return path


def require_regular(path: Path) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise WorkflowError(f"Artifact source is unavailable: {path.name}", EXIT_CONTRADICTION) from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise WorkflowError(f"Artifact source is not a regular file: {path.name}", EXIT_CONTRADICTION)
    if path.name.startswith("gha-creds-"):
        raise WorkflowError("Generated credential files are forbidden in artifacts", EXIT_CONTRADICTION)


def locate_failure_workspace(results_root: Path, plan: dict[str, Any]) -> Path | None:
    request = plan["request"]
    candidates: list[Path] = []
    for plan_path in sorted((results_root / "sets" / "in-progress").glob("*/set-plan.json")):
        workspace = plan_path.parent
        if workspace.is_symlink() or not workspace.is_dir():
            continue
        try:
            workspace.resolve().relative_to(results_root.resolve())
            set_plan = read_json(plan_path)
        except (ValueError, WorkflowError):
            continue
        if not isinstance(set_plan, dict):
            continue
        source = set_plan.get("source", {})
        controls = set_plan.get("controls", {})
        if (
            set_plan.get("kind") == "benchmark-set-plan"
            and set_plan.get("schemaVersion") == 1
            and set_plan.get("evidenceProfile") == request["evidenceProfile"]
            and set_plan.get("mode") == request["mode"]
            and set_plan.get("repeats") == request["repeats"]
            and set_plan.get("presetId") == plan["derived"]["presetId"]
            and source.get("commit") == plan["source"]["commit"]
            and source.get("repository") == REPOSITORY
            and controls.get("provisioning", "").lower() == request["provisioning"]
            and controls.get("machineType") == request["machineType"]
        ):
            candidates.append(workspace)
    if len(candidates) > 1:
        raise WorkflowError(
            f"Expected at most one matching failed set workspace; found {len(candidates)}",
            EXIT_CONTRADICTION,
        )
    return candidates[0] if candidates else None


def require_workspace_file(workspace: Path, path: Path) -> Path:
    try:
        path.resolve(strict=True).relative_to(workspace.resolve())
        relative = path.relative_to(workspace)
    except (OSError, ValueError) as error:
        raise WorkflowError(
            "Failed set diagnostic path escapes its workspace", EXIT_CONTRADICTION
        ) from error
    current = workspace
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise WorkflowError("Failed set diagnostic path contains a symlink", EXIT_CONTRADICTION)
    return path


def failure_diagnostic_sources(
    results_root: Path, plan: dict[str, Any]
) -> list[tuple[Path, Path]]:
    workspace = locate_failure_workspace(results_root, plan)
    if workspace is None:
        return []
    prefix = Path("failure-diagnostics")
    workspace_prefix = prefix / "workspace" / workspace.name
    sources: list[tuple[Path, Path]] = [
        (workspace / "set-plan.json", workspace_prefix / "set-plan.json"),
        (workspace / "checkpoint.json", workspace_prefix / "checkpoint.json"),
    ]
    attempts = sorted(workspace.glob("attempts/slot-*/attempt-*.json"))
    replacements = sorted(workspace.glob("replacements/slot-*/replacement-*.json"))
    for record_path in [*attempts, *replacements]:
        require_workspace_file(workspace, record_path)
        relative = record_path.relative_to(workspace)
        sources.append((record_path, workspace_prefix / relative))
    for attempt_path in attempts:
        attempt = read_json(attempt_path)
        if not isinstance(attempt, dict):
            raise WorkflowError("Failed set attempt record is invalid", EXIT_CONTRADICTION)
        member = attempt.get("member")
        if isinstance(member, dict):
            manifest = safe_results_path(results_root, member.get("manifestReference"))
            metrics = safe_results_path(results_root, member.get("metricsReference"))
            if (
                manifest.name != "benchmark-manifest.json"
                or metrics.name != "normalized-metrics.json"
                or manifest.parent != metrics.parent
            ):
                raise WorkflowError("Failed set member references are invalid", EXIT_CONTRADICTION)
            for name in DERIVED_FILES:
                source = manifest.parent / name
                sources.append((source, prefix / "evidence" / source.relative_to(results_root)))
        orchestration = attempt.get("orchestration")
        if isinstance(orchestration, dict):
            source = safe_results_path(results_root, orchestration.get("reference"))
            sources.append((source, prefix / "evidence" / source.relative_to(results_root)))
            retained_log = source.with_suffix(".log")
            if retained_log.exists():
                sources.append(
                    (retained_log, prefix / "evidence" / retained_log.relative_to(results_root))
                )
    return sources


def stage_artifact(options: argparse.Namespace) -> dict[str, Any]:
    plan_path = Path(options.plan).resolve()
    result_path = Path(options.result).resolve()
    summary_path = Path(options.summary).resolve()
    plan = validate_plan(read_json(plan_path))
    result = validate_result(read_json(result_path))
    results_root = Path(options.results_root).resolve()
    staging = Path(options.staging).resolve()
    if staging.exists():
        if staging.is_symlink() or any(staging.iterdir()):
            raise WorkflowError("Artifact staging directory must be new or empty")
    else:
        staging.mkdir(parents=True)

    sources: list[tuple[Path, Path]] = [
        (plan_path, Path("workflow-plan.json")),
        (result_path, Path("workflow-result.json")),
        (summary_path, Path("workflow-summary.md")),
    ]
    set_info = result.get("set")
    if isinstance(set_info, dict):
        set_root = safe_results_path(results_root, set_info["relativePath"])
        manifest = read_json(set_root / "benchmark-set-manifest.json")
        sources.extend((set_root / name, Path("evidence") / set_info["relativePath"] / name) for name in SET_FILES)
        for member in manifest.get("members", []):
            if not isinstance(member, dict):
                raise WorkflowError("Set member is invalid", EXIT_CONTRADICTION)
            manifest_path = safe_results_path(results_root, member.get("manifestReference"))
            derived_root = manifest_path.parent
            sources.extend(
                (derived_root / name, Path("evidence") / derived_root.relative_to(results_root) / name)
                for name in DERIVED_FILES
            )
            orchestration = safe_results_path(results_root, member.get("orchestrationReference"))
            sources.append((orchestration, Path("evidence") / orchestration.relative_to(results_root)))
            retained_log = orchestration.with_suffix(".log")
            if retained_log.exists():
                sources.append((retained_log, Path("evidence") / retained_log.relative_to(results_root)))
    receipt_info = result.get("upload", {}).get("receipt")
    if isinstance(receipt_info, dict):
        receipt_root = results_root / "upload-receipts" / receipt_info["id"] / "v1"
        for name in ("upload-receipt.json", "upload-receipt.sha256"):
            sources.append((receipt_root / name, Path("evidence/upload-receipts") / receipt_info["id"] / "v1" / name))
    if result["primary"]["exit"] != 0:
        sources.extend(failure_diagnostic_sources(results_root, plan))

    total = 0
    seen: dict[str, Path] = {}
    for source, relative in sources:
        require_regular(source)
        relative_text = relative.as_posix()
        if relative.is_absolute() or ".." in relative.parts:
            raise WorkflowError("Artifact destination is unsafe or duplicated", EXIT_CONTRADICTION)
        prior = seen.get(relative_text)
        if prior is not None:
            if prior.resolve() == source.resolve():
                continue
            raise WorkflowError("Artifact destination is unsafe or duplicated", EXIT_CONTRADICTION)
        seen[relative_text] = source
        size = source.stat().st_size
        total += size
        if total > MAX_ARTIFACT_BYTES:
            raise WorkflowError("Lightweight artifact exceeds the 100 MiB limit")
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination, follow_symlinks=False)

    checksum_entries = []
    for path in sorted(staging.rglob("*")):
        if path.is_file() and path.name != "artifact-checksums.sha256":
            checksum_entries.append(f"{sha256_file(path)}  {path.relative_to(staging).as_posix()}")
    checksum_path = staging / "artifact-checksums.sha256"
    checksum_path.write_text("\n".join(checksum_entries) + "\n", encoding="utf-8")
    total += checksum_path.stat().st_size
    if total > MAX_ARTIFACT_BYTES:
        raise WorkflowError("Lightweight artifact exceeds the 100 MiB limit")
    return {"fileCount": len(checksum_entries) + 1, "sizeBytes": total}


def markdown(value: Any) -> str:
    text = str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;").replace("\r", " ").replace("\n", " ")


def render_summary(plan: dict[str, Any], result: dict[str, Any] | None) -> str:
    request = plan["request"]
    rows = [
        ("Run", f"{plan['run']['id']} / attempt {plan['run']['attempt']}"),
        ("Source commit", plan["source"]["commit"]),
        ("Evidence profile", request["evidenceProfile"]),
        ("Mode / repeats", f"{request['mode']} / {request['repeats']}"),
        ("Provisioning / machine", f"{request['provisioning']} / {request['machineType']}"),
        ("Soak duration", request["soakDuration"]),
        ("Retention", request["retention"]),
        ("GitHub artifact", f"{plan['artifact']['name']} ({plan['artifact']['retentionDays']} days)"),
    ]
    lines = ["# Cloud Benchmark V2 manual run", "", "| Field | Value |", "|---|---|"]
    lines.extend(f"| {markdown(label)} | `{markdown(value)}` |" for label, value in rows)
    lines.extend(["", "## Outcome", ""])
    if result is None:
        lines.append("Workflow result state is missing; the run is an infrastructure failure.")
    else:
        primary = result["primary"]
        lines.append(f"Primary status: **{'PASS' if primary['exit'] == 0 else 'FAIL'}** (`{markdown(primary['category'])}`, exit `{primary['exit']}`).")
        set_info = result.get("set")
        if isinstance(set_info, dict):
            lines.append(f"Set: `{markdown(set_info['id'])}`; `{markdown(set_info['status'])}`; members `{set_info['memberCount']}`.")
        upload = result.get("upload", {})
        lines.append(f"Durable upload: `{markdown(upload.get('status', 'unknown'))}`.")
        receipt = upload.get("receipt")
        if isinstance(receipt, dict):
            lines.append(f"Receipt: `{markdown(receipt['id'])}`; objects `{receipt['objectCount']}`; manifest `{markdown(receipt['manifestUri'])}`.")
    lines.extend(
        [
            "",
            "> No baseline comparison was performed. This workflow does not establish a production SLA or automatically promote a baseline.",
            "",
        ]
    )
    return "\n".join(lines)


def render_plan_summary(plan: dict[str, Any]) -> str:
    request = plan["request"]
    return "\n".join(
        [
            "# Cloud Benchmark V2 preflight",
            "",
            f"Validated protected source commit `{markdown(plan['source']['commit'])}`.",
            "",
            "| Profile | Mode | Repeats | Provisioning | Machine | Soak | Retention |",
            "|---|---|---:|---|---|---|---|",
            "| "
            + " | ".join(
                markdown(value)
                for value in (
                    request["evidenceProfile"],
                    request["mode"],
                    request["repeats"],
                    request["provisioning"],
                    request["machineType"],
                    request["soakDuration"],
                    request["retention"],
                )
            )
            + " |",
            "",
            "> Preflight requested no OIDC token and performed no cloud mutation.",
            "",
        ]
    )


def assert_fresh(results_root: Path) -> None:
    root = results_root.resolve()
    if root.is_symlink():
        raise WorkflowError("Benchmark results root must not be a symlink")
    patterns = (
        "sets/gse-set-v1-*/v1/benchmark-set-manifest.json",
        "upload-receipts/gse-upload-receipt-v1-*/v1/upload-receipt.json",
    )
    if any(any(root.glob(pattern)) for pattern in patterns):
        raise WorkflowError("Ephemeral workflow results root already contains completed evidence")


def final_exit(result: dict[str, Any] | None, outcomes: Iterable[str]) -> int:
    if result is None:
        return EXIT_CONFIG
    primary = int(result["primary"]["exit"])
    if primary:
        return primary
    upload = result.get("upload", {})
    upload_exit = upload.get("exit")
    if isinstance(upload_exit, int) and upload_exit:
        return upload_exit
    if any(value != "success" for value in outcomes):
        return EXIT_CONFIG
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    for option in ("evidence-profile", "mode", "repeats", "provisioning", "machine-type", "soak-duration", "retention"):
        plan.add_argument(f"--{option}", required=True)
    plan.add_argument("--source-commit", default="")
    plan.add_argument("--dispatch-sha", required=True)
    plan.add_argument("--repository-root", required=True)
    plan.add_argument("--trusted-ref", default="origin/master")
    plan.add_argument("--run-id", required=True)
    plan.add_argument("--run-attempt", required=True)
    plan.add_argument("--output", required=True)
    plan.add_argument("--github-output")

    config = commands.add_parser("validate-config")
    config.add_argument("--plan", required=True)

    result = commands.add_parser("benchmark-result")
    result.add_argument("--plan", required=True)
    result.add_argument("--results-root", required=True)
    result.add_argument("--dry-run-exit", required=True)
    result.add_argument("--benchmark-exit", required=True)
    result.add_argument("--output", required=True)
    result.add_argument("--github-output")

    upload = commands.add_parser("record-upload")
    upload.add_argument("--plan", required=True)
    upload.add_argument("--result", required=True)
    upload.add_argument("--results-root", required=True)
    upload.add_argument("--upload-exit", required=True)

    summary = commands.add_parser("summary")
    summary.add_argument("--plan", required=True)
    summary.add_argument("--result", required=True)
    summary.add_argument("--output", required=True)
    summary.add_argument("--github-step-summary")

    plan_summary = commands.add_parser("plan-summary")
    plan_summary.add_argument("--plan", required=True)
    plan_summary.add_argument("--github-step-summary", required=True)

    fresh = commands.add_parser("assert-fresh")
    fresh.add_argument("--results-root", required=True)

    artifact = commands.add_parser("stage-artifact")
    artifact.add_argument("--plan", required=True)
    artifact.add_argument("--result", required=True)
    artifact.add_argument("--summary", required=True)
    artifact.add_argument("--results-root", required=True)
    artifact.add_argument("--staging", required=True)

    gate = commands.add_parser("final-exit")
    gate.add_argument("--result", required=True)
    gate.add_argument("--outcome", action="append", default=[])
    return root


def main(arguments: list[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    try:
        if options.command == "plan":
            value = make_plan(options)
            write_json(Path(options.output), value)
            write_github_output(
                options.github_output,
                {
                    "artifact_name": value["artifact"]["name"],
                    "jvm_options": value["derived"].get(
                        "jvmOptions", "-Xms8g -Xmx16g"
                    ),
                    "max_vm_runtime_seconds": str(value["derived"]["maxVmRuntimeSeconds"]),
                    "soak_seconds": str(value["derived"]["soakSeconds"]),
                    "source_commit": value["source"]["commit"],
                },
            )
        elif options.command == "validate-config":
            validate_config(validate_plan(read_json(Path(options.plan))), dict(os.environ))
            print("Cloud workflow configuration: PASS")
        elif options.command == "benchmark-result":
            value = benchmark_result(options)
            write_json(Path(options.output), value)
            set_path = ""
            if value["set"] is not None:
                set_path = str(Path(options.results_root).resolve() / value["set"]["relativePath"])
            write_github_output(options.github_output, {"primary_exit": str(value["primary"]["exit"]), "set_path": set_path})
        elif options.command == "record-upload":
            try:
                value = update_upload(options)
            except WorkflowError as error:
                value = validate_result(read_json(Path(options.result)))
                value["upload"] = {"exit": error.code, "receipt": None, "status": "failed"}
                print(f"ERROR: {error}", file=sys.stderr)
            Path(options.result).write_bytes(canonical_bytes(value))
        elif options.command == "summary":
            plan = validate_plan(read_json(Path(options.plan)))
            try:
                result = validate_result(read_json(Path(options.result)))
            except WorkflowError:
                result = None
            content = render_summary(plan, result)
            Path(options.output).write_text(content, encoding="utf-8")
            if options.github_step_summary:
                with Path(options.github_step_summary).open("a", encoding="utf-8") as handle:
                    handle.write(content)
        elif options.command == "plan-summary":
            value = validate_plan(read_json(Path(options.plan)))
            with Path(options.github_step_summary).open("a", encoding="utf-8") as handle:
                handle.write(render_plan_summary(value))
        elif options.command == "assert-fresh":
            assert_fresh(Path(options.results_root))
        elif options.command == "stage-artifact":
            staged = stage_artifact(options)
            print(f"Workflow artifact staging: PASS; files={staged['fileCount']}; bytes={staged['sizeBytes']}")
        elif options.command == "final-exit":
            try:
                result = validate_result(read_json(Path(options.result)))
            except WorkflowError:
                result = None
            return final_exit(result, options.outcome)
        return 0
    except WorkflowError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return error.code
    except (OSError, ValueError) as error:
        print(f"ERROR: Workflow infrastructure failure: {error}", file=sys.stderr)
        return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
