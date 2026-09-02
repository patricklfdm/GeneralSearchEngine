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
    ./mvnw -q -DskipTests test-compile
fi

if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
else
    python_command=python3
fi

"$python_command" -m py_compile \
    scripts/v4/evidence.py \
    scripts/v4/storage_inspector.py \
    scripts/v4/durable_harness.py \
    scripts/v4/durable_cloud_lane.py \
    scripts/v4/test_phase4_checkpoint_fixtures.py
"$python_command" -m unittest scripts.v4.test_phase4_checkpoint_fixtures

./mvnw -q -Dtest=V40DurableCheckpointPhase4Test test

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v40-phase4.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
source_sha=$(git rev-parse HEAD)
source_state=clean
if [[ -n "$(git status --porcelain)" ]]; then
    source_state=dirty
fi

barriers=(
    v4-checkpoint-after-old-wal-force-v1
    v4-checkpoint-after-new-wal-header-force-v1
    v4-checkpoint-partial-data-v1
    v4-checkpoint-after-data-force-v1
    v4-checkpoint-after-data-publication-v1
    v4-checkpoint-partial-manifest-v1
    v4-checkpoint-after-manifest-force-v1
    v4-checkpoint-after-manifest-rename-v1
    v4-checkpoint-after-directory-force-v1
    v4-checkpoint-before-wal-cleanup-v1
    v4-checkpoint-after-wal-cleanup-v1
)

for barrier in "${barriers[@]}"; do
    case_dir="$work_dir/internal-$barrier"
    "$python_command" -m scripts.v4.durable_harness run \
        --workspace "$case_dir" \
        --source-sha "$source_sha" \
        --source-state "$source_state" \
        --scenario phase4-checkpoint \
        --termination internal-halt \
        --barrier "$barrier"
    "$python_command" -m scripts.v4.durable_harness validate \
        "$case_dir/evidence"
done

for barrier in \
    v4-checkpoint-partial-manifest-v1 \
    v4-checkpoint-after-directory-force-v1; do
    case_dir="$work_dir/external-$barrier"
    "$python_command" -m scripts.v4.durable_harness run \
        --workspace "$case_dir" \
        --source-sha "$source_sha" \
        --source-state "$source_state" \
        --scenario phase4-checkpoint \
        --termination external-kill \
        --barrier "$barrier"
    "$python_command" -m scripts.v4.durable_harness validate \
        "$case_dir/evidence"
done

"$python_command" -m scripts.v4.durable_cloud_lane \
    --output "$work_dir/fake-cloud-checkpoint" \
    --source-sha "$source_sha" \
    --source-state "$source_state" \
    --profile failure-drill \
    --phase phase4-checkpoint
"$python_command" -m scripts.v4.durable_harness validate \
    "$work_dir/fake-cloud-checkpoint"

echo "V4.0 Phase 4 checkpoint crash matrix: PASS"
