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
    scripts/v4/test_phase2_storage_inspector.py
"$python_command" -m unittest scripts.v4.test_phase2_storage_inspector

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v40-phase2.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
source_sha=$(git rev-parse HEAD)
source_state=clean
if [[ -n "$(git status --porcelain)" ]]; then
    source_state=dirty
fi

barriers=(
    v4-wal-before-sequence-v1
    v4-wal-after-sequence-v1
    v4-wal-partial-header-v1
    v4-wal-partial-payload-v1
    v4-wal-partial-trailer-v1
    v4-wal-complete-before-force-v1
    v4-wal-after-force-v1
    v4-wal-before-publication-v1
    v4-wal-after-publication-v1
    v4-wal-before-future-completion-v1
)

for barrier in "${barriers[@]}"; do
    case_dir="$work_dir/internal-$barrier"
    "$python_command" -m scripts.v4.durable_harness run \
        --workspace "$case_dir" \
        --source-sha "$source_sha" \
        --source-state "$source_state" \
        --scenario phase2-wal \
        --termination internal-halt \
        --barrier "$barrier"
    "$python_command" -m scripts.v4.durable_harness validate \
        "$case_dir/evidence"
done

external_dir="$work_dir/external-after-force"
"$python_command" -m scripts.v4.durable_harness run \
    --workspace "$external_dir" \
    --source-sha "$source_sha" \
    --source-state "$source_state" \
    --scenario phase2-wal \
    --termination external-kill \
    --barrier v4-wal-after-force-v1
"$python_command" -m scripts.v4.durable_harness validate \
    "$external_dir/evidence"

echo "V4.0 Phase 2 production WAL crash-barrier matrix: PASS"
