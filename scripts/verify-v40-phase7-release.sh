#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd -- "$script_dir/.." && pwd)
skip_consumers=false

if [[ ${1:-} == "--skip-consumers" ]]; then
    skip_consumers=true
elif [[ $# -ne 0 ]]; then
    echo "usage: $0 [--skip-consumers]" >&2
    exit 2
fi

"$project_dir/scripts/verify-version-alignment.sh" 4.0.0

if rg -n '4\.0\.0-SNAPSHOT' \
        "$project_dir/pom.xml" \
        "$project_dir/general-search-engine-processor/pom.xml" \
        "$project_dir/reactor/pom.xml" \
        "$project_dir/examples/travel-search/pom.xml" \
        "$project_dir/compatibility"; then
    echo "V4.0 release candidate still contains an active SNAPSHOT coordinate" >&2
    exit 1
fi

(
    cd "$project_dir"
    python3 -m unittest scripts.v4.test_phase7_release_fixtures
)

if [[ "$skip_consumers" == false ]]; then
    "$project_dir/scripts/verify-consumer-projects.sh"
fi

echo "V4.0 Phase 7 release-candidate validation: PASS"
