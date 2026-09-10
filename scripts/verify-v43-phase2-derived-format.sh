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
        -Dtest=V43PublicApiFoundationTest,V43DerivedFormatPhase2Test,V43PublishedV42FormatCompatibilityTest,V42FormatInspectionPhase2Test,V41StructuralVerificationTest \
        test
fi

if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
else
    python_command=python3
fi

"$python_command" -m py_compile \
    scripts/v43/derived_format_v12.py \
    scripts/v43/test_derived_format_v12.py
"$python_command" -m unittest scripts.v43.test_derived_format_v12
"$python_command" -m scripts.v43.derived_format_v12 inspect \
    src/test/resources/compatibility/v43-derived-v12

echo "V4.3 Phase 2 exact derived format and inspection: PASS"
