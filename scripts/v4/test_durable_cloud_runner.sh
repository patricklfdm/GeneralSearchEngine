#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$repo_root"

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v40-cloud-runner.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT

common=(
  GSE_V4_GCP_PROJECT=fake-project
  GSE_V4_GCP_ZONE=us-west4-a
  GSE_V4_CLOUD_IMAGE=ubuntu-2404-noble-amd64-v20260826
  GSE_V4_SOURCE_SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  GSE_V4_RUN_ID=12345
  GSE_V4_SLOT=1
  GSE_V4_PROFILE=experiment
  GSE_V4_DURATION_SECONDS=120
  GSE_V4_OUTPUT="$work_dir/evidence"
)

output=$(env "${common[@]}" scripts/v4/run_durable_cloud_member.sh --dry-run)
grep -q 'v40CloudMemberDryRun=PASS' <<< "$output"
grep -q 'pd-balanced, 200 GiB, retained independently' <<< "$output"
grep -q 'machine:  c3d-standard-30' <<< "$output"

set +e
env "${common[@]}" GSE_V4_MACHINE_TYPE=c3d-standard-60 \
  scripts/v4/run_durable_cloud_member.sh --dry-run \
  >"$work_dir/invalid.out" 2>&1
status=$?
set -e
[[ $status -eq 2 ]]
grep -q 'machine substitution is forbidden' "$work_dir/invalid.out"

workflow=.github/workflows/v4-durable-performance.yml
grep -q 'workflow_dispatch:' "$workflow"
grep -q 'provisioning-model=STANDARD' scripts/v4/run_durable_cloud_member.sh
grep -q 'auto-delete=no' scripts/v4/run_durable_cloud_member.sh
grep -q 'GSE_BENCHMARK_GCS_BUCKET' "$workflow"
grep -q 'run_durable_cloud_member.sh --confirm-paid-run' "$workflow"
grep -q 'runStatus=%s' scripts/v4/run_durable_cloud_member.sh
grep -q 'always() && needs.preflight.outputs.retention' "$workflow"
grep -q 'durable_cloud_workflow plan-summary' "$workflow"
grep -q 'runStatus=NOT_STARTED' "$workflow"
grep -q 'python3 unzip' scripts/v4/remote_durable_member.sh

mkdir -p "$work_dir/fake-bin"
printf '#!/usr/bin/env bash\nexit 1\n' > "$work_dir/fake-bin/gcloud"
chmod +x "$work_dir/fake-bin/gcloud"
set +e
env PATH="$work_dir/fake-bin:$PATH" "${common[@]}" \
  scripts/v4/run_durable_cloud_member.sh --confirm-paid-run \
  >"$work_dir/member-failure.out" 2>&1
member_failure_status=$?
set -e
[[ $member_failure_status -eq 10 ]]
grep -q '^runStatus=FAIL$' "$work_dir/evidence/cloud-member.properties"
grep -q '^cleanup=PASS$' "$work_dir/evidence/cloud-member.properties"

failure_output=$(env \
  GSE_V4_GCP_PROJECT=fake-project \
  GSE_V4_GCP_ZONE=us-west4-a \
  GSE_V4_CLOUD_IMAGE=ubuntu-2404-noble-amd64-v20260826 \
  GSE_V4_SOURCE_SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  GSE_V4_RUN_ID=12345 \
  GSE_V4_OUTPUT="$work_dir/failure" \
  scripts/v4/run_durable_failure_drill.sh --dry-run)
grep -q 'v40FailureDrillDryRun=PASS' <<< "$failure_output"
grep -q 'auto-delete disabled' <<< "$failure_output"
grep -q 'writer-vm-deleted' scripts/v4/durable_remote_failure.py
grep -q 'run_durable_failure_drill.sh --confirm-paid-run' \
  .github/workflows/v4-durable-failure-drill.yml
grep -q 'runStatus=%s' scripts/v4/run_durable_failure_drill.sh
grep -q 'if:.*always()' .github/workflows/v4-durable-failure-drill.yml
grep -q 'runStatus=NOT_STARTED' .github/workflows/v4-durable-failure-drill.yml
grep -q 'python3 unzip' scripts/v4/remote_durable_failure.sh

set +e
env \
  PATH="$work_dir/fake-bin:$PATH" \
  GSE_V4_GCP_PROJECT=fake-project \
  GSE_V4_GCP_ZONE=us-west4-a \
  GSE_V4_CLOUD_IMAGE=ubuntu-2404-noble-amd64-v20260826 \
  GSE_V4_SOURCE_SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  GSE_V4_RUN_ID=12345 \
  GSE_V4_OUTPUT="$work_dir/failure-confirmed" \
  scripts/v4/run_durable_failure_drill.sh --confirm-paid-run \
  >"$work_dir/failure-confirmed.out" 2>&1
failure_status=$?
set -e
[[ $failure_status -eq 10 ]]
grep -q '^runStatus=FAIL$' \
  "$work_dir/failure-confirmed/cloud-cleanup.properties"
grep -q '^persistentDiskDeleted=PASS$' \
  "$work_dir/failure-confirmed/cloud-cleanup.properties"

echo "V4 durable cloud runner dry-run contract: PASS"
