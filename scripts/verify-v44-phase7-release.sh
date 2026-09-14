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

"$project_dir/scripts/verify-version-alignment.sh" 4.4.0

if rg -n '4\.4\.0-SNAPSHOT' \
        "$project_dir/pom.xml" \
        "$project_dir/general-search-engine-processor/pom.xml" \
        "$project_dir/reactor/pom.xml" \
        "$project_dir/examples/travel-search/pom.xml" \
        "$project_dir/compatibility"; then
    echo "V4.4 release candidate still contains an active SNAPSHOT coordinate" >&2
    exit 1
fi

(
    cd "$project_dir"
    python3 -m unittest \
        scripts.v44.test_phase6_registration \
        scripts.v44.test_phase7_release_fixtures \
        scripts.v44.test_candidate_artifacts
    python3 -m scripts.v44.candidate_artifacts validate-manifest
    python3 -m scripts.v44.cloud_set registry-list \
        docs/v4x/v4.4/cloud-benchmark-baselines.json
    python3 -m scripts.v44.toolchain_manifest \
        docs/v4x/v4.4/release-toolchain.json
)

if [[ "$skip_consumers" == false ]]; then
    "$project_dir/scripts/verify-consumer-projects.sh"
fi

echo "V4.4 Phase 7 release-candidate validation: PASS"
