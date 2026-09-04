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
        -Dtest=V42PublicApiFoundationTest,V42FormatInspectionPhase2Test,V41StructuralVerificationTest \
        test
fi

if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
else
    python_command=python3
fi

"$python_command" -m py_compile \
    scripts/v42/storage_format_v11.py \
    scripts/v42/test_storage_format_v11.py
"$python_command" -m unittest scripts.v42.test_storage_format_v11

echo "V4.2 Phase 2 dual-minor format inspection: PASS"
