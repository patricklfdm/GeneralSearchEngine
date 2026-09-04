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
        -Dtest=V42MigrationLifecyclePhase5Test,V42MigrationOracleTest \
        test
fi

if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
else
    python_command=python3
fi

"$python_command" -m py_compile \
    scripts/v42/evidence.py \
    scripts/v42/production_migration_harness.py

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v42-phase5.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
source_sha=$(git rev-parse HEAD)

barriers=(
    v42-migration-before-marker-publication-v1
    v42-migration-after-marker-force-v1
    v42-migration-after-staging-force-v1
    v42-migration-before-metadata-write-v1
    v42-migration-after-metadata-force-v1
    v42-migration-before-checkpoint-write-v1
    v42-migration-after-checkpoint-rename-v1
    v42-migration-before-wal-write-v1
    v42-migration-after-wal-force-v1
    v42-migration-before-manifest-write-v1
    v42-migration-after-manifest-rename-v1
    v42-migration-before-staging-verification-v1
    v42-migration-after-staging-verification-v1
    v42-migration-before-final-rename-v1
    v42-migration-after-final-rename-v1
    v42-migration-before-parent-force-v1
    v42-migration-after-parent-force-v1
    v42-migration-before-final-verification-v1
    v42-migration-after-final-verification-v1
    v42-migration-before-final-source-compare-v1
    v42-migration-after-final-source-compare-v1
    v42-migration-before-marker-delete-v1
    v42-migration-after-marker-delete-v1
    v42-migration-after-marker-parent-force-v1
    v42-migration-before-return-v1
)

for barrier in "${barriers[@]}"; do
    case_name=${barrier#v42-migration-}
    "$python_command" -m scripts.v42.production_migration_harness run \
        --workspace "$work_dir/$case_name" \
        --source-sha "$source_sha" \
        --barrier "$barrier" \
        --scenario catalog
    "$python_command" -m scripts.v42.production_migration_harness validate \
        "$work_dir/$case_name/evidence"
done

"$python_command" -m scripts.v42.production_migration_harness lifecycle \
    --workspace "$work_dir/lifecycle" \
    --source-sha "$source_sha"
"$python_command" -m scripts.v42.production_migration_harness validate \
    "$work_dir/lifecycle/evidence"

scripts/verify-v42-phase4-transform-migration.sh --skip-build

echo "V4.2 Phase 5 lifecycle, authority, cleanup and rollback matrix: PASS"
