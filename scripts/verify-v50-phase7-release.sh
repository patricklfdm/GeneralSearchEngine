#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --skip-consumers ) ]]; then
    echo "usage: $0 [--skip-consumers]" >&2
    exit 2
fi
scripts/verify-version-alignment.sh 5.0.0
python3 -m unittest scripts.v50.test_phase7_release_fixtures scripts.v50.test_candidate_artifacts
python3 -m scripts.v50.toolchain_manifest docs/v5x/v5.0/release-toolchain.json
python3 -m scripts.v50.candidate_artifacts validate-manifest
python3 -m scripts.v50.cloud_baseline check \
    --review docs/v5x/v5.0/phase6-cloud-review.json \
    --registry docs/v5x/v5.0/cloud-benchmark-baselines.json
if [[ "${1:-}" != --skip-consumers ]]; then
    scripts/verify-consumer-projects.sh
fi
echo "V5.0 Phase 7 release-candidate validation: PASS"
