#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

skip_build=false
if [[ "${1:-}" == "--skip-build" ]]; then
    skip_build=true
elif [[ $# -ne 0 ]]; then
    echo "usage: $0 [--skip-build]" >&2
    exit 2
fi

if [[ "$skip_build" == false ]]; then
    ./mvnw -q clean -Dtest=V40DurablePerformancePhase6Test test
    ./mvnw -q -Pjmh -DskipTests package
fi

if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
else
    python_command=python3
fi

"$python_command" -m py_compile \
    scripts/v4/evidence.py \
    scripts/v4/durable_cloud_lane.py \
    scripts/v4/durable_cloud_workflow.py \
    scripts/v4/durable_cloud_set.py \
    scripts/v4/durable_remote_failure.py \
    scripts/v4/durable_performance.py \
    scripts/v4/test_phase6_performance.py \
    scripts/v4/test_durable_cloud_workflow.py \
    scripts/v4/test_durable_cloud_set.py
"$python_command" -m unittest \
    scripts.v4.test_phase6_performance \
    scripts.v4.test_durable_cloud_workflow \
    scripts.v4.test_durable_cloud_set

java -jar target/benchmarks.jar \
    'V40DurableMutationBenchmark.*Completion' \
    -p documentCount=1000 \
    -p bulkSize=10 \
    -f 1 -wi 0 -i 1 -r 100ms -foe true

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v40-phase6.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
source_sha=$(git rev-parse HEAD)
source_state=clean
if [[ -n "$(git status --porcelain)" ]]; then
    source_state=dirty
fi

"$python_command" -m scripts.v4.durable_performance run \
    --workspace "$work_dir/performance" \
    --source-sha "$source_sha" \
    --source-state "$source_state" \
    --profile smoke \
    --duration-seconds 2 \
    --classpath target/benchmarks.jar
"$python_command" -m scripts.v4.durable_performance validate \
    "$work_dir/performance/evidence"

"$python_command" -m scripts.v4.durable_cloud_lane \
    --output "$work_dir/fake-cloud-performance" \
    --source-sha "$source_sha" \
    --source-state "$source_state" \
    --profile canonical \
    --phase phase6-performance
"$python_command" -m scripts.v4.durable_harness validate \
    "$work_dir/fake-cloud-performance"

"$python_command" -m scripts.v4.durable_remote_failure writer \
    --workspace "$work_dir/preserved-disk" \
    --source-sha "$source_sha"
"$python_command" -m scripts.v4.durable_remote_failure recover \
    --workspace "$work_dir/preserved-disk" \
    --source-sha "$source_sha"
"$python_command" -m scripts.v4.durable_remote_failure validate \
    "$work_dir/preserved-disk/evidence"

scripts/v4/test_durable_cloud_runner.sh

echo "V4.0 Phase 6 durable performance and operational evidence: PASS"
