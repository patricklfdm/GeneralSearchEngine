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
    scripts/v41/backup_format.py \
    scripts/v41/evidence.py \
    scripts/v41/operational_harness.py \
    scripts/v41/fake_cloud_lane.py \
    scripts/v41/test_backup_format.py \
    scripts/v41/test_phase1_infrastructure.py
"$python_command" -m unittest \
    scripts.v41.test_backup_format \
    scripts.v41.test_phase1_infrastructure

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v41-phase1.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
source_sha=$(git rev-parse HEAD)
source_state=clean
if [[ -n "$(git status --porcelain)" ]]; then
    source_state=dirty
fi

for termination in internal-halt external-kill; do
    "$python_command" -m scripts.v41.operational_harness run \
        --workspace "$work_dir/$termination" \
        --source-sha "$source_sha" \
        --source-state "$source_state" \
        --termination "$termination"
    "$python_command" -m scripts.v41.operational_harness validate \
        "$work_dir/$termination/evidence"
done

for profile in experiment canonical failure-drill; do
    "$python_command" -m scripts.v41.fake_cloud_lane \
        --output "$work_dir/fake-$profile" \
        --source-sha "$source_sha" \
        --source-state "$source_state" \
        --profile "$profile"
    "$python_command" -m scripts.v41.operational_harness validate \
        "$work_dir/fake-$profile"
done

echo "V4.1 Phase 1 operational foundation: PASS"
