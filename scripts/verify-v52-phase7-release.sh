#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --skip-consumers ) ]]; then
    echo "usage: $0 [--skip-consumers]" >&2
    exit 2
fi
scripts/verify-version-alignment.sh 5.2.0
python3 -m unittest scripts.v52.test_phase7_release_fixtures scripts.v52.test_candidate_artifacts scripts.test_build_coordinates
python3 -m scripts.v52.toolchain_manifest docs/v5x/v5.2/release-toolchain.json
python3 -m scripts.v52.candidate_artifacts validate-manifest
python3 -c 'from scripts.v52.release_baseline import check; check()'
if [[ "${1:-}" != --skip-consumers ]]; then
    scripts/verify-consumer-projects.sh
fi
echo "V5.2 Phase 7 release-candidate validation: PASS"
