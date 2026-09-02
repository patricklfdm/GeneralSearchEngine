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
    scripts/v4/test_phase1_infrastructure.py
"$python_command" -m unittest scripts.v4.test_phase1_infrastructure

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v40-phase1.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
source_sha=$(git rev-parse HEAD)
source_state=clean
if [[ -n "$(git status --porcelain)" ]]; then
    source_state=dirty
fi

for termination in internal-halt external-kill; do
    "$python_command" -m scripts.v4.durable_harness run \
        --workspace "$work_dir/$termination" \
        --source-sha "$source_sha" \
        --source-state "$source_state" \
        --termination "$termination" \
        --barrier phase1-scaffold-v1
    "$python_command" -m scripts.v4.durable_harness validate \
        "$work_dir/$termination/evidence"
done

for profile in experiment failure-drill; do
    "$python_command" -m scripts.v4.durable_cloud_lane \
        --output "$work_dir/cloud-$profile" \
        --source-sha "$source_sha" \
        --source-state "$source_state" \
        --profile "$profile"
    "$python_command" -m scripts.v4.durable_harness validate \
        "$work_dir/cloud-$profile"
done

echo "V4.0 Phase 1 crash harness and fake cloud foundation: PASS"
