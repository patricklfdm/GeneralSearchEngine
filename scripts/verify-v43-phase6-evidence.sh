#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"
skip_build=false
if [[ "${1:-}" = --skip-build ]]; then skip_build=true
elif [[ $# -ne 0 ]]; then echo "usage: $0 [--skip-build]" >&2; exit 2; fi
if [[ "$skip_build" = false ]]; then ./mvnw -q clean -Pjmh -DskipTests package; fi
[[ -f target/benchmarks.jar ]] || { echo "target/benchmarks.jar is required" >&2; exit 2; }
if command -v python3.11 >/dev/null 2>&1; then python_command=python3.11; else python_command=python3; fi

"$python_command" -m py_compile \
  scripts/v43/derived_format_v12.py scripts/v43/evidence.py \
  scripts/v43/fake_cloud_lane.py scripts/v43/fast_reopen_performance.py \
  scripts/v43/fast_reopen_cloud_workflow.py scripts/v43/fast_reopen_cloud_set.py \
  scripts/v43/test_phase6_evidence.py
"$python_command" -m unittest \
  scripts.v43.test_derived_format_v12 scripts.v43.test_phase6_evidence
bash -n scripts/v43/remote_fast_reopen_stage.sh \
  scripts/v43/run_fast_reopen_cloud_member.sh

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v43-phase6.XXXXXX")
cleanup() { local status=$?; if [[ $status -eq 0 ]]; then rm -rf "$work_dir"; else echo "Phase 6 failure workspace retained: $work_dir" >&2; fi; }
trap cleanup EXIT

scripts/verify-v43-published-v42-baseline.sh
published_jar=target/compat-baselines/published-general-search-engine-4.2.0.jar
mkdir -p "$work_dir/published-control"
javac -cp "$published_jar" -d "$work_dir/published-control" \
  scripts/v43/PublishedV42FastReopenControl.java
source_sha=$(git rev-parse HEAD); source_state=clean
[[ -z "$(git status --porcelain)" ]] || source_state=dirty
"$python_command" -m scripts.v43.fast_reopen_performance run-local \
  --workspace "$work_dir/local" --source-sha "$source_sha" \
  --source-state "$source_state" --java-profile smoke --duration-seconds 1 \
  --timeout-seconds 300 --classpath target/benchmarks.jar \
  --published-classpath "$work_dir/published-control:$published_jar"
"$python_command" -m scripts.v43.fast_reopen_performance validate \
  "$work_dir/local/evidence"

for profile in experiment canonical failure-drill; do
  "$python_command" -m scripts.v43.fake_cloud_lane \
    --output "$work_dir/fake-$profile" --source-sha "$source_sha" \
    --source-state "$source_state" --profile "$profile"
done

GSE_V43_GCP_PROJECT=gse-benchmark GSE_V43_GCP_ZONE=us-west4-a \
GSE_V43_CLOUD_IMAGE=ubuntu-2404-noble-amd64-v20260826 \
GSE_V43_GCS_BUCKET=gs://gse-dry-run-placeholder \
GSE_V43_SOURCE_SHA="$source_sha" GSE_V43_RUN_ID=123456789 \
GSE_V43_RUN_ATTEMPT=1 GSE_V43_SLOT=1 GSE_V43_PROFILE=experiment \
GSE_V43_DURATION_SECONDS=1800 GSE_V43_OUTPUT="$work_dir/cloud-output" \
scripts/v43/run_fast_reopen_cloud_member.sh --dry-run

scripts/verify-v43-phase5-lifecycle.sh --skip-build
echo "V4.3 Phase 6 fast-reopen performance and evidence lane: PASS"
