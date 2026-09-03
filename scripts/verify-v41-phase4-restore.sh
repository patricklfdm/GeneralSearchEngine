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
    scripts/v4/storage_inspector.py \
    scripts/v41/backup_format.py \
    scripts/v41/restore_crash_inspector.py \
    scripts/v41/test_restore_crash_inspector.py
"$python_command" -m unittest scripts.v41.test_restore_crash_inspector

./mvnw -q \
    -Dtest=V41PublicApiFoundationTest,V41SemanticRestorePublicApiTest,V41SemanticRestorePhase4Test \
    test

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v41-phase4.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
process_class=io.github.patricklfdm.generalsearch.durability.harness.V41RestoreHarnessProcess
classpath=target/test-classes:target/classes

normal="$work_dir/normal"
mkdir -p "$normal"
java -cp "$classpath" "$process_class" produce "$normal"
java -cp "$classpath" "$process_class" recover "$normal"

barriers=(
    v41-restore-after-marker-force-v1
    v41-restore-after-metadata-force-v1
    v41-restore-after-checkpoint-rename-v1
    v41-restore-after-wal-force-v1
    v41-restore-after-manifest-force-v1
    v41-restore-after-manifest-rename-v1
    v41-restore-before-final-rename-v1
    v41-restore-after-final-rename-v1
    v41-restore-after-parent-force-v1
    v41-restore-before-return-v1
)

for barrier in "${barriers[@]}"; do
    case_dir="$work_dir/$barrier"
    mkdir -p "$case_dir"
    set +e
    java \
        -Dgse.v4.crashBarrier="$barrier" \
        -Dgse.v4.crashAction=halt \
        -cp "$classpath" \
        "$process_class" crash "$case_dir"
    exit_code=$?
    set -e
    if [[ "$exit_code" -ne 86 ]]; then
        echo "unexpected restore crash exit at $barrier: $exit_code" >&2
        exit 1
    fi
    "$python_command" -m scripts.v41.restore_crash_inspector \
        "$case_dir" "$barrier"
    java -cp "$classpath" "$process_class" recover "$case_dir"
done

echo "V4.1 Phase 4 semantic restore and crash matrix: PASS"
