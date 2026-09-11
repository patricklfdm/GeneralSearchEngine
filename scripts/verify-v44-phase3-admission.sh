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

if [[ "$skip_build" == false ]]; then
    ./mvnw -q -DskipTests package
fi

scripts/verify-version-alignment.sh 4.4.0-SNAPSHOT
"$python_command" -m py_compile \
    scripts/v44/admission.py \
    scripts/v44/test_phase3_admission.py
"$python_command" -m unittest scripts.v44.test_phase3_admission
"$python_command" -m scripts.v44.admission --check-production-delta
"$python_command" -m scripts.v44.api_inventory compare \
    target/general-search-engine-4.4.0-SNAPSHOT.jar \
    src/test/resources/compatibility/v44-public-api-inventory-v1.json
./mvnw -q -Dtest=V44FinalDurableMatrixPhase2Test test

echo "V4.4 Phase 3 zero-production-change admission: PASS"
