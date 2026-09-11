#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

skip_build=false
skip_consumers=false
skip_canonical=false
for argument in "$@"; do
    case "$argument" in
        --skip-build) skip_build=true ;;
        --skip-consumers) skip_consumers=true ;;
        --skip-canonical-build) skip_canonical=true ;;
        *) echo "usage: $0 [--skip-build] [--skip-consumers] [--skip-canonical-build]" >&2; exit 2 ;;
    esac
done

if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
else
    python_command=python3
fi

if [[ "$skip_build" == false ]]; then
    # The following API inventory gate consumes the packaged main JAR. `test`
    # alone leaves no JAR after `clean`, so build through `package` while still
    # executing the complete test suite.
    ./mvnw -q clean package
fi
test -f target/general-search-engine-4.4.0-SNAPSHOT.jar

scripts/verify-version-alignment.sh 4.4.0-SNAPSHOT
"$python_command" -m py_compile \
    scripts/v44/canonical_reproducibility.py \
    scripts/v44/cloud_workflow.py \
    scripts/v44/cloud_evidence.py \
    scripts/v44/cloud_set.py \
    scripts/v44/test_phase5_reproducibility.py \
    scripts/v44/test_phase5_cloud_readiness.py
"$python_command" -m unittest \
    scripts.v44.test_phase5_reproducibility \
    scripts.v44.test_phase5_cloud_readiness

"$python_command" -m scripts.v44.admission --check-production-delta
"$python_command" -m scripts.v44.api_inventory compare \
    target/general-search-engine-4.4.0-SNAPSHOT.jar \
    src/test/resources/compatibility/v44-public-api-inventory-v1.json

if [[ ! -f target/compat-baselines/published-general-search-engine-4.3.0.jar ]]; then
    scripts/verify-v44-published-v43-baseline.sh
else
    scripts/verify-v44-published-v43-baseline.sh --skip-resolve
fi
scripts/verify-v44-paired-baseline.sh

work_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-v44-phase5.XXXXXXXX")
trap 'rm -rf -- "$work_root"' EXIT
source_sha=$(git rev-parse HEAD)
source_state=clean
if [[ -n "$(git status --porcelain)" ]]; then source_state=dirty; fi
for profile in experiment canonical failure-drill; do
    "$python_command" -m scripts.v44.fake_cloud_lane \
        --output "$work_root/fake-$profile" \
        --source-sha "$source_sha" --source-state "$source_state" \
        --profile "$profile"
done
scripts/v44/test_final_durable_cloud_runner.sh

grep -Eq 'workflow_dispatch:' .github/workflows/v44-final-durable-evidence.yml
! grep -Eq '^  (push|schedule):' .github/workflows/v44-final-durable-evidence.yml
grep -Eq 'max-parallel: 1' .github/workflows/v44-final-durable-evidence.yml
grep -Eq 'environment: cloud-benchmark' .github/workflows/v44-final-durable-evidence.yml
grep -Eq 'v4\.4-final-durable/' .github/workflows/v44-final-durable-evidence.yml
grep -Eq 'Status:.*Phase 5 draft' docs/v4x/v4.4/V5_HANDOFF.md

if [[ "$skip_consumers" == false ]]; then
    scripts/verify-consumer-projects.sh
fi
if [[ "$skip_canonical" == false ]]; then
    scripts/verify-v44-canonical-build.sh
fi

echo "V4.4 Phase 5 stabilization and no-GCP readiness: PASS"
