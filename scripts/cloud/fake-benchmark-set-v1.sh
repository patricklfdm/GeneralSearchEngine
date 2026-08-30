#!/usr/bin/env bash
set -euo pipefail

# Test-only V1 replacement used by test-benchmark-set-runner.sh. It creates
# deterministic schema-1 fixture evidence and never calls gcloud.
: "${FAKE_SET_COUNTER_FILE:?FAKE_SET_COUNTER_FILE is required}"

for argument in "$@"; do
  if [ "$argument" = --dry-run ]; then
    echo 'Fake V1 dry run complete: no cloud resources were mutated.'
    printf 'GSE_CONCURRENCY_DOCUMENTS=%s\n' \
      "${GSE_CONCURRENCY_DOCUMENTS:-unset}"
    printf 'GSE_CONCURRENCY_THREAD_GROUPS=%s\n' \
      "${GSE_CONCURRENCY_THREAD_GROUPS:-unset}"
    printf 'GSE_PERF_JVM_OPTIONS=%s\n' "${GSE_PERF_JVM_OPTIONS:-unset}"
    exit 0
  fi
done

mode=${!#}
case "$mode" in
  quick|full|concurrency|soak|investigation|stabilized-investigation|ranked-v31|all) ;;
  *) echo "Fake set V1 received unsupported mode: $mode" >&2; exit 2 ;;
esac
ordinal=0
if [ -f "$FAKE_SET_COUNTER_FILE" ]; then ordinal=$(sed -n '1p' "$FAKE_SET_COUNTER_FILE"); fi
ordinal=$((ordinal + 1))
printf '%s\n' "$ordinal" > "$FAKE_SET_COUNTER_FILE"

if [ -n "${FAKE_SET_INFRA_ORDINAL:-}" ] && [ "$ordinal" -eq "$FAKE_SET_INFRA_ORDINAL" ]; then
  results_root="$(pwd)/benchmark-results/v3-production"
  mkdir -p "$results_root/cloud-orchestration"
  record="$results_root/cloud-orchestration/gse-fake-set-infra-$ordinal.properties"
  printf '%s\n' \
    'project=fake-project' \
    "instance_name=gse-fake-set-infra-$ordinal" \
    'stage=FINISHED' \
    'primary_exit_code=10' > "$record"
  printf '%s\n' "$record" > "$GSE_CLOUD_ORCHESTRATION_POINTER_FILE"
  echo 'Synthetic provisioning failure after orchestration allocation' >&2
  exit 10
fi

python3 - "$ordinal" "$mode" <<'PY'
import os
import subprocess
import sys
from pathlib import Path

from scripts.cloud.test_benchmark_v2 import Fixture

ordinal = int(sys.argv[1])
mode = sys.argv[2]
root = Path.cwd()
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
run_id = f"20260828T{ordinal:06d}Z-{commit[:12]}-{mode}"
fixture = Fixture(
    root,
    run_id=run_id,
    mode=mode,
    instance=f"gse-fake-set-{ordinal}",
)
fixture.metadata["git_commit"] = commit
fixture.metadata["source_repository"] = "https://github.com/patricklfdm/GeneralSearchEngine.git"
fixture.metadata["cloud_project"] = "fake-project"
fixture.metadata["cloud_provisioning"] = os.environ.get("GSE_CLOUD_PROVISIONING", "spot")
fixture.metadata["cloud_image"] = "ubuntu-2404-noble-amd64-v20260801"
fixture.metadata["cloud_image_id"] = "123456789"
fixture.metadata["cloud_image_self_link"] = "https://compute.example/images/123456789"
fixture.metadata["cloud_image_created_at"] = "2026-08-01T00:00:00Z"
fixture.rewrite_metadata()
fixture.orchestration["project"] = "fake-project"
fixture.orchestration["requested_commit"] = commit
fixture.orchestration["remote_commit"] = commit
fixture.orchestration["provisioning"] = fixture.metadata["cloud_provisioning"].upper()
fixture.orchestration["max_run_duration"] = os.environ.get(
    "GSE_CLOUD_MAX_RUN_DURATION", fixture.orchestration["max_run_duration"]
)
fixture.orchestration["resolved_image"] = "ubuntu-2404-noble-amd64-v20260801"
fixture.orchestration["resolved_image_id"] = "123456789"
fixture.orchestration["resolved_image_self_link"] = "https://compute.example/images/123456789"
fixture.orchestration["resolved_image_created_at"] = "2026-08-01T00:00:00Z"
fixture.rewrite_orchestration()
fixture.refresh_checksums()
pointer = Path(os.environ["GSE_CLOUD_ORCHESTRATION_POINTER_FILE"])
pointer.write_text(str(fixture.orchestration_path.resolve()) + "\n", encoding="utf-8")
print(f"Cloud orchestration record: {fixture.orchestration_path}")
print(f"Local benchmark result: {fixture.raw}")
PY
