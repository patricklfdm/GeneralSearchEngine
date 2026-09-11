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

if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
else
    python_command=python3
fi

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v44-phase2.XXXXXX")
completed=false
cleanup() {
    if [[ "$completed" == true ]]; then
        rm -rf -- "$work_dir"
    else
        echo "V4.4 Phase 2 failure workspace retained: $work_dir" >&2
    fi
}
trap cleanup EXIT
receipts="$work_dir/receipts"
mkdir -p "$receipts"

pass_gate() {
    local gate_id=$1
    shift
    "$@"
    printf 'gateId=%s\nstatus=PASS\n' "$gate_id" \
        >"$receipts/$gate_id.receipt"
}

if [[ "$skip_build" == false ]]; then
    ./mvnw -q -DskipTests package
fi
test -f target/general-search-engine-4.4.0-SNAPSHOT.jar

"$python_command" -m py_compile \
    scripts/v44/local_matrix.py \
    scripts/v44/test_phase2_matrix.py
"$python_command" -m unittest scripts.v44.test_phase2_matrix
"$python_command" -m scripts.v44.local_matrix check-map

pass_gate v44-targeted-junit \
    ./mvnw -q -Dtest=V44FinalDurableMatrixPhase2Test test
pass_gate v40-recovery-crash \
    scripts/verify-v40-phase3-recovery.sh --skip-build
pass_gate v40-checkpoint-crash \
    scripts/verify-v40-phase4-checkpoints.sh --skip-build
pass_gate v40-lifecycle \
    scripts/verify-v40-phase5-hardening.sh --skip-build
pass_gate v41-backup-crash \
    scripts/verify-v41-phase3-backup.sh --skip-build
pass_gate v41-restore-crash \
    scripts/verify-v41-phase4-restore.sh --skip-build
pass_gate v41-cleanup-crash \
    scripts/verify-v41-phase5-cleanup.sh
pass_gate v42-format-migration \
    scripts/verify-v42-phase3-format-migration.sh --skip-build
pass_gate v42-transform-migration \
    scripts/verify-v42-phase4-transform-migration.sh --skip-build
pass_gate v43-derived-reopen \
    scripts/verify-v43-phase4-text-images.sh --skip-build
pass_gate v43-derived-lifecycle \
    scripts/verify-v43-phase5-lifecycle.sh --skip-build

if [[ ! -f target/compat-baselines/published-general-search-engine-4.3.0.jar ]]; then
    scripts/verify-v44-published-v43-baseline.sh
else
    scripts/verify-v44-published-v43-baseline.sh --skip-resolve
fi
pass_gate v44-paired-published43 scripts/verify-v44-paired-baseline.sh
pass_gate v44-local-replacement \
    "$python_command" -m scripts.v44.local_matrix replacement \
        --workspace "$work_dir/replacement"

source_sha=$(git rev-parse HEAD)
source_state=clean
if [[ -n "$(git status --porcelain)" ]]; then
    source_state=dirty
fi
"$python_command" -m scripts.v44.local_matrix record \
    --receipts "$receipts" \
    --output "$work_dir/matrix-evidence" \
    --source-sha "$source_sha" \
    --source-state "$source_state"
"$python_command" -m scripts.v44.local_matrix validate \
    "$work_dir/matrix-evidence"

completed=true
echo "V4.4 Phase 2 complete local final-durable matrix: PASS"
