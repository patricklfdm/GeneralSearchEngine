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
[[ -f target/benchmarks.jar ]] || {
  echo "target/benchmarks.jar is required" >&2
  exit 2
}

if command -v python3.11 >/dev/null 2>&1; then
  python_command=python3.11
else
  python_command=python3
fi

"$python_command" -m py_compile \
  scripts/v42/evidence.py \
  scripts/v42/fake_cloud_lane.py \
  scripts/v42/migration_performance.py \
  scripts/v42/migration_cloud_workflow.py \
  scripts/v42/migration_cloud_set.py \
  scripts/v42/test_phase6_evidence.py
"$python_command" -m unittest scripts.v42.test_phase6_evidence
bash -n scripts/v42/remote_storage_evolution_stage.sh
bash -n scripts/v42/run_storage_evolution_cloud_member.sh

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v42-phase6.XXXXXX")
cleanup_work_dir() {
  local status=$?
  if [[ $status -eq 0 ]]; then
    rm -rf "$work_dir"
  else
    echo "Phase 6 failure workspace retained: $work_dir" >&2
  fi
}
trap cleanup_work_dir EXIT

published_dir="$work_dir/published"
mkdir -p "$published_dir"
./mvnw -q \
  org.apache.maven.plugins:maven-dependency-plugin:3.9.0:copy \
  -Dartifact=io.github.patricklfdm:general-search-engine:4.1.0:jar \
  -DoutputDirectory="$published_dir"
published_jar="$published_dir/general-search-engine-4.1.0.jar"
echo "36aa783cef653ead26d2500a847b70bb1f8222d224c8a83de55419de46814bcb  $published_jar" \
  | sha256sum --check --strict
mkdir -p "$work_dir/published-probe"
javac -cp "$published_jar" -d "$work_dir/published-probe" \
  scripts/v42/PublishedV41MigrationCloudProbe.java

source_sha=$(git rev-parse HEAD)
source_state=clean
if [[ -n "$(git status --porcelain)" ]]; then source_state=dirty; fi
"$python_command" -m scripts.v42.migration_performance run-local \
  --workspace "$work_dir/local" \
  --source-sha "$source_sha" \
  --source-state "$source_state" \
  --java-profile smoke \
  --duration-seconds 1 \
  --timeout-seconds 300 \
  --classpath target/benchmarks.jar \
  --published-classpath "$work_dir/published-probe:$published_jar"
"$python_command" -m scripts.v42.migration_performance validate \
  "$work_dir/local/evidence"

for profile in experiment canonical failure-drill; do
  "$python_command" -m scripts.v42.fake_cloud_lane \
    --output "$work_dir/fake-$profile" \
    --source-sha "$source_sha" \
    --source-state "$source_state" \
    --profile "$profile"
done

GSE_V42_GCP_PROJECT=gse-benchmark \
GSE_V42_GCP_ZONE=us-west4-a \
GSE_V42_CLOUD_IMAGE=ubuntu-2404-noble-amd64-v20260826 \
GSE_V42_GCS_BUCKET=gs://gse-dry-run-placeholder \
GSE_V42_SOURCE_SHA="$source_sha" \
GSE_V42_RUN_ID=123456789 \
GSE_V42_RUN_ATTEMPT=1 \
GSE_V42_SLOT=1 \
GSE_V42_PROFILE=experiment \
GSE_V42_DURATION_SECONDS=1800 \
GSE_V42_OUTPUT="$work_dir/cloud-output" \
scripts/v42/run_storage_evolution_cloud_member.sh --dry-run

scripts/verify-v42-phase5-lifecycle.sh --skip-build

echo "V4.2 Phase 6 performance, replacement-host and cloud evidence: PASS"
