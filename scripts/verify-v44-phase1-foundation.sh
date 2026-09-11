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
    ./mvnw -q -DskipTests package
fi

scripts/verify-version-alignment.sh 4.4.0-SNAPSHOT

python_command=python3
if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
fi

"$python_command" -m py_compile \
    scripts/v44/api_inventory.py \
    scripts/v44/evidence.py \
    scripts/v44/final_matrix.py \
    scripts/v44/crash_harness.py \
    scripts/v44/fake_cloud_lane.py \
    scripts/v44/toolchain_manifest.py \
    scripts/v44/test_phase1_infrastructure.py
"$python_command" -m unittest scripts.v44.test_phase1_infrastructure
"$python_command" -m scripts.v44.final_matrix \
    src/test/resources/compatibility/v44-final-matrix-v1
"$python_command" -m scripts.v44.toolchain_manifest \
    docs/v4x/v4.4/release-toolchain.json
"$python_command" -m scripts.v44.api_inventory compare \
    target/general-search-engine-4.4.0-SNAPSHOT.jar \
    src/test/resources/compatibility/v44-public-api-inventory-v1.json

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v44-phase1.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
source_sha=$(git rev-parse HEAD)
source_state=clean
if [[ -n "$(git status --porcelain)" ]]; then
    source_state=dirty
fi

for case_id in \
    graceful-close runtime-halt external-kill startup-failure \
    injected-io-failure malformed-bytes corrupt-bytes; do
    "$python_command" -m scripts.v44.crash_harness run \
        --workspace "$work_dir/$case_id" \
        --source-sha "$source_sha" \
        --source-state "$source_state" \
        --case "$case_id"
    "$python_command" -m scripts.v44.crash_harness validate \
        "$work_dir/$case_id/evidence"
done

# Bind the new orchestration discipline to an inherited production authority
# transition before Phase 2 expands the complete V4.4 matrix.  Keep the original
# V4 evidence schema instead of translating it into a stronger V4.4 claim.
production_bridge="$work_dir/production-wal-after-force"
"$python_command" -m scripts.v4.durable_harness run \
    --workspace "$production_bridge" \
    --source-sha "$source_sha" \
    --source-state "$source_state" \
    --scenario phase3-recovery \
    --termination external-kill \
    --barrier v4-wal-after-force-v1
"$python_command" -m scripts.v4.durable_harness validate \
    "$production_bridge/evidence"

for profile in experiment canonical failure-drill; do
    "$python_command" -m scripts.v44.fake_cloud_lane \
        --output "$work_dir/fake-$profile" \
        --source-sha "$source_sha" \
        --source-state "$source_state" \
        --profile "$profile"
    "$python_command" -m scripts.v44.crash_harness validate \
        "$work_dir/fake-$profile"
done

echo "V4.4 Phase 1 final-hardening foundation: PASS"
