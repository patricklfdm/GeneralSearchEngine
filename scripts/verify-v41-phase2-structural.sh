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
        -Dtest=V41PublicApiFoundationTest,V41StructuralPublicApiTest,V41StructuralVerificationTest \
        test
fi

if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
else
    python_command=python3
fi

"$python_command" -m py_compile \
    scripts/v4/storage_inspector.py \
    scripts/v4/test_phase2_storage_inspector.py \
    scripts/v4/test_phase4_checkpoint_fixtures.py \
    scripts/v4/test_phase7_release_fixtures.py \
    scripts/v41/backup_format.py \
    scripts/v41/test_backup_format.py
"$python_command" -m unittest \
    scripts.v4.test_phase2_storage_inspector \
    scripts.v4.test_phase4_checkpoint_fixtures \
    scripts.v4.test_phase7_release_fixtures \
    scripts.v41.test_backup_format

echo "V4.1 Phase 2 codec-free structural verification: PASS"
