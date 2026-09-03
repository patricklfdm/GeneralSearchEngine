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
    scripts/v41/backup_crash_inspector.py \
    scripts/v41/test_backup_format.py \
    scripts/v41/test_backup_crash_inspector.py
"$python_command" -m unittest \
    scripts.v41.test_backup_format \
    scripts.v41.test_backup_crash_inspector

./mvnw -q \
    -Dtest=V41PublicApiFoundationTest,V41BackupPublicApiTest,V41LiveBackupPhase3Test \
    test

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v41-phase3.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
process_class=io.github.patricklfdm.generalsearch.durability.harness.V41BackupHarnessProcess
classpath=target/test-classes:target/classes

normal="$work_dir/normal"
mkdir -p "$normal"
java -cp "$classpath" "$process_class" produce "$normal"
"$python_command" -m scripts.v41.backup_format inspect "$normal/backup"

barriers=(
    v41-backup-before-writer-cut-v1
    v41-backup-after-b-selection-v1
    v41-backup-after-wal-cut-v1
    v41-backup-after-source-checkpoint-authority-v1
    v41-backup-after-checkpoint-pin-v1
    v41-backup-after-marker-force-v1
    v41-backup-during-metadata-copy-v1
    v41-backup-after-metadata-force-v1
    v41-backup-during-checkpoint-copy-v1
    v41-backup-after-checkpoint-force-v1
    v41-backup-after-manifest-force-v1
    v41-backup-after-manifest-rename-v1
    v41-backup-before-final-rename-v1
    v41-backup-after-final-rename-v1
    v41-backup-after-parent-force-v1
    v41-backup-before-future-completion-v1
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
        echo "unexpected backup crash exit at $barrier: $exit_code" >&2
        exit 1
    fi
    "$python_command" -m scripts.v41.backup_crash_inspector \
        "$case_dir" "$barrier"
    java -cp "$classpath" "$process_class" recover-source "$case_dir"
done

echo "V4.1 Phase 3 live backup and crash matrix: PASS"
