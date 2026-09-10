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
        -Dtest=V43StructuredImagesPhase3Test,V43DerivedFormatPhase2Test,V42FormatMigrationPhase3Test,V42TransformMigrationPhase4Test \
        test
fi

if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
else
    python_command=python3
fi

"$python_command" -m py_compile \
    scripts/v43/derived_format_v12.py \
    scripts/v43/structured_image_harness.py \
    scripts/v43/test_derived_format_v12.py
"$python_command" -m unittest scripts.v43.test_derived_format_v12

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v43-phase3.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
source_sha=$(git rev-parse HEAD)
source_state=clean
if [[ -n "$(git status --porcelain)" ]]; then
    source_state=dirty
fi

barriers=(
    v43-derived-before-component-rename-v1
    v43-derived-after-component-parent-force-v1
    v43-derived-before-catalog-publication-v1
    v43-derived-after-catalog-parent-force-v1
)
terminations=(internal-halt external-kill internal-halt external-kill)
for index in "${!barriers[@]}"; do
    case_dir="$work_dir/case-$index"
    "$python_command" -m scripts.v43.structured_image_harness run \
        --workspace "$case_dir" \
        --source-sha "$source_sha" \
        --source-state "$source_state" \
        --barrier "${barriers[$index]}" \
        --termination "${terminations[$index]}"
    "$python_command" -m scripts.v43.structured_image_harness validate \
        "$case_dir/evidence"
done

echo "V4.3 Phase 3 structured images and direct migration: PASS"
