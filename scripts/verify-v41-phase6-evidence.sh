#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

skip_build=false
if [[ "${1:-}" == --skip-build ]]; then
  skip_build=true
elif [[ $# -ne 0 ]]; then
  echo "usage: $0 [--skip-build]" >&2
  exit 2
fi

if [[ "$skip_build" == false ]]; then
  ./mvnw -q clean -Pjmh -DskipTests package
fi
[[ -f target/benchmarks.jar ]] || { echo "target/benchmarks.jar is required" >&2; exit 2; }

if command -v python3.11 >/dev/null 2>&1; then
  python_command=python3.11
else
  python_command=python3
fi

"$python_command" -m py_compile \
  scripts/v41/operational_evidence.py \
  scripts/v41/operational_cloud_workflow.py \
  scripts/v41/operational_cloud_set.py \
  scripts/v41/test_phase6_evidence.py
"$python_command" -m unittest scripts.v41.test_phase6_evidence
bash -n scripts/v41/remote_operational_stage.sh
bash -n scripts/v41/run_operational_cloud_member.sh

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v41-phase6.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
source_sha=$(git rev-parse HEAD)
source_state=clean
if [[ -n "$(git status --porcelain)" ]]; then source_state=dirty; fi

"$python_command" -m scripts.v41.operational_evidence run-local \
  --workspace "$work_dir/local" \
  --source-sha "$source_sha" \
  --source-state "$source_state" \
  --java-profile smoke \
  --duration-seconds 1 \
  --timeout-seconds 300 \
  --classpath target/benchmarks.jar
"$python_command" -m scripts.v41.operational_evidence validate \
  "$work_dir/local/evidence"

for profile in experiment canonical failure-drill; do
  "$python_command" -m scripts.v41.fake_cloud_lane \
    --output "$work_dir/fake-$profile" \
    --source-sha "$source_sha" \
    --source-state "$source_state" \
    --profile "$profile"
done

GSE_V41_GCP_PROJECT=gse-benchmark \
GSE_V41_GCP_ZONE=us-west4-a \
GSE_V41_CLOUD_IMAGE=ubuntu-2404-noble-amd64-v20260826 \
GSE_V41_GCS_BUCKET=gs://gse-dry-run-placeholder \
GSE_V41_SOURCE_SHA="$source_sha" \
GSE_V41_RUN_ID=123456789 \
GSE_V41_RUN_ATTEMPT=1 \
GSE_V41_SLOT=1 \
GSE_V41_PROFILE=experiment \
GSE_V41_DURATION_SECONDS=1800 \
GSE_V41_OUTPUT="$work_dir/cloud-output" \
scripts/v41/run_operational_cloud_member.sh --dry-run

echo "V4.1 Phase 6 operational evidence: PASS"
