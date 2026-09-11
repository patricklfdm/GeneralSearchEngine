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
    ./mvnw -q -Pjmh -DskipTests package
fi
test -f target/benchmarks.jar || {
    echo "target/benchmarks.jar is required; rerun without --skip-build" >&2
    exit 2
}

scripts/verify-version-alignment.sh 4.4.0-SNAPSHOT
"$python_command" -m py_compile \
    scripts/v44/local_hardening.py \
    scripts/v44/test_phase4_hardening.py
"$python_command" -m unittest scripts.v44.test_phase4_hardening
"$python_command" -m scripts.v44.admission --check-production-delta

# These four deterministic cases own the migration count recorded by Phase 4:
# two catalog interruptions and two identity interruptions.  The scale probe
# intentionally does not invent a second migration implementation.
scripts/verify-v42-phase4-transform-migration.sh --skip-build

source_sha=$(git rev-parse HEAD)
source_state=clean
if [[ -n "$(git status --short --untracked-files=all)" ]]; then
    source_state=dirty
fi
workspace=$(mktemp -u "${TMPDIR:-/tmp}/gse-v44-phase4.XXXXXXXX")

set +e
"$python_command" -m scripts.v44.local_hardening run \
    --workspace "$workspace" \
    --source-sha "$source_sha" \
    --source-state "$source_state" \
    --duration-seconds 2 \
    --timeout-seconds 240 \
    --classpath target/benchmarks.jar
status=$?
set -e
if [[ $status -ne 0 ]]; then
    echo "V4.4 Phase 4 failure workspace retained: $workspace" >&2
    exit "$status"
fi

"$python_command" -m scripts.v44.local_hardening validate "$workspace/evidence"
if [[ -e "$workspace/probe" ]]; then
    echo "V4.4 Phase 4 probe cleanup differs: $workspace/probe" >&2
    exit 2
fi

echo "V4.4 Phase 4 local scale and resource hardening: PASS"
