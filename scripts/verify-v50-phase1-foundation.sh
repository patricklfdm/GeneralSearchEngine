#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"

skip_build=false
if [[ "${1:-}" == "--skip-build" ]]; then
  skip_build=true
elif [[ $# -ne 0 ]]; then
  echo "usage: $0 [--skip-build]" >&2
  exit 2
fi

if [[ "$skip_build" == false ]]; then
  ./mvnw -f reactor/pom.xml clean test
fi

scripts/verify-version-alignment.sh 5.0.0-SNAPSHOT
scripts/verify-v50-phase0-contract.sh

python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
"$python_command" -m py_compile \
  scripts/v50/replicated_history_model.py \
  scripts/v50/deterministic_transport.py \
  scripts/v50/evidence.py \
  scripts/v50/replica_fixture.py \
  scripts/v50/fake_cloud_lane.py \
  scripts/v50/cloud_workflow.py \
  scripts/v50/test_replicated_history_model.py \
  scripts/v50/test_deterministic_transport.py \
  scripts/v50/test_replica_fixture.py \
  scripts/v50/test_phase1_infrastructure.py
"$python_command" -m unittest \
  scripts.v50.test_replicated_history_model \
  scripts.v50.test_deterministic_transport \
  scripts.v50.test_replica_fixture \
  scripts.v50.test_phase1_infrastructure

expected_v44=0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5
grep -Fq "$expected_v44" docs/v4x/v4.4/candidate-artifacts.sha256
grep -Fq "$expected_v44" pom.xml

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v50-phase1.XXXXXX")
"$python_command" -m scripts.v50.replica_fixture generate "$work_dir/replica-fixture"
"$python_command" -m scripts.v50.replica_fixture inspect "$work_dir/replica-fixture"
scripts/v50/run_local_crash_harness.sh "$work_dir/crash"
source_sha=$(git rev-parse HEAD)
for profile in experiment canonical failure-drill; do
  "$python_command" -m scripts.v50.fake_cloud_lane \
    --output "$work_dir/fake-$profile" \
    --source-sha "$source_sha" \
    --profile "$profile"
  "$python_command" -m scripts.v50.evidence validate "$work_dir/fake-$profile"
done
"$python_command" -m scripts.v50.fake_cloud_lane \
  --output "$work_dir/fake-provision-failure" \
  --source-sha "$source_sha" \
  --profile experiment \
  --inject-failure provision-node-2
"$python_command" -m scripts.v50.evidence validate "$work_dir/fake-provision-failure"

"$python_command" -m scripts.v50.cloud_workflow plan \
  --profile canonical --source-sha "$source_sha" \
  --output "$work_dir/workflow-plan.json"
"$python_command" -m scripts.v50.cloud_workflow summary \
  --profile canonical --source-sha "$source_sha" \
  --output "$work_dir/workflow-summary.md"

grep -Fq '"votersPerTopology": 3' "$work_dir/workflow-plan.json"
grep -Fq '"votersConcurrent": true' "$work_dir/workflow-plan.json"
grep -Fq 'fake only; no GCP' "$work_dir/workflow-summary.md"

if rg -q 'ServerSocket|SocketChannel|AsynchronousServerSocketChannel' \
    general-search-engine-replication/src/main/java; then
  echo "Phase 1 replication artifact must not expose production networking" >&2
  exit 1
fi

echo "v50Phase1Foundation=PASS productionReplication=disabled paidCloud=disabled"
