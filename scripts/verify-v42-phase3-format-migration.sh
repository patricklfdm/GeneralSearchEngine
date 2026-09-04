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
    ./mvnw -q \
        -Dtest=V42MigrationPublicApiTest,V42FormatMigrationPhase3Test,V42FormatInspectionPhase2Test,V41LiveBackupPhase3Test,V41SemanticRestorePhase4Test \
        test
fi

if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
else
    python_command=python3
fi

"$python_command" -m py_compile \
    scripts/v42/storage_format_v11.py \
    scripts/v42/test_storage_format_v11.py \
    scripts/v42/production_migration_harness.py
"$python_command" -m unittest scripts.v42.test_storage_format_v11

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v42-phase3.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
source_sha=$(git rev-parse HEAD)
process_class="io.github.patricklfdm.generalsearch.durability.harness.V42ProductionMigrationHarnessProcess"

java -cp target/test-classes:target/classes "$process_class" \
    produce-v11 "$work_dir/v11-live" "$work_dir/v11-backup" unused
"$python_command" -m scripts.v42.storage_format_v11 \
    inspect-store "$work_dir/v11-live"
"$python_command" -m scripts.v42.storage_format_v11 \
    inspect-backup "$work_dir/v11-backup"

for barrier in \
    v42-migration-before-final-rename-v1 \
    v42-migration-after-parent-force-v1; do
    case_name=${barrier#v42-migration-}
    "$python_command" -m scripts.v42.production_migration_harness run \
        --workspace "$work_dir/$case_name" \
        --source-sha "$source_sha" \
        --barrier "$barrier"
    "$python_command" -m scripts.v42.production_migration_harness validate \
        "$work_dir/$case_name/evidence"
done

scripts/verify-v42-phase2-format.sh --skip-build

echo "V4.2 Phase 3 format-only migration and production V1.1 matrix: PASS"
