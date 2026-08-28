#!/usr/bin/env bash
set -euo pipefail

source_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-benchmark-set-test.XXXXXX")
test_repo="$test_root/repository"
fake_bin="$test_root/bin"
output="$test_root/output.log"

cleanup() { rm -rf -- "$test_root"; }
trap cleanup EXIT
fail() { echo "FAIL: $*" >&2; sed -n '1,260p' "$output" >&2 || true; exit 1; }
assert_contains() { grep -F -- "$2" "$1" >/dev/null || fail "Expected '$2' in $1"; }

mkdir -p "$test_repo/scripts/cloud" "$test_repo/benchmark-results/v3-production" "$fake_bin"
cp "$source_root/run-cloud-benchmark-set.sh" "$test_repo/"
cp "$source_root/scripts/cloud/benchmark_v2.py" \
  "$source_root/scripts/cloud/test_benchmark_v2.py" \
  "$test_repo/scripts/cloud/"
cp "$source_root/scripts/cloud/fake-benchmark-set-v1.sh" "$test_repo/run-cloud-benchmark.sh"
cp "$source_root/scripts/cloud/fake-gcloud.sh" "$fake_bin/gcloud"
cp "$source_root/.gitignore" "$test_repo/"
cp "$source_root/benchmark-results/v3-production/.gitignore" "$test_repo/benchmark-results/v3-production/"
chmod +x "$test_repo/run-cloud-benchmark.sh" "$test_repo/run-cloud-benchmark-set.sh" "$fake_bin/gcloud"

git -C "$test_repo" init --quiet
git -C "$test_repo" config user.name 'Benchmark Set Test'
git -C "$test_repo" config user.email 'benchmark-set@example.test'
git -C "$test_repo" add .
git -C "$test_repo" commit --quiet -m fixture

common=(
  "PATH=$fake_bin:$PATH"
  "PYTHONPATH=$test_repo"
  "FAKE_GCLOUD_STATE_DIR=$test_root/gcloud-state"
  "FAKE_SET_COUNTER_FILE=$test_root/counter"
  'GSE_GCP_PROJECT=fake-project'
  'GSE_GCP_ZONE=us-west4-a'
  'GSE_CLOUD_PROVISIONING=standard'
  'GSE_CLOUD_IMAGE=ubuntu-2404-noble-amd64-v20260801'
  'GSE_CLOUD_REPO_URL=https://github.com/patricklfdm/GeneralSearchEngine.git'
)
mkdir -p "$test_root/gcloud-state"

env "${common[@]}" "$test_repo/run-cloud-benchmark-set.sh" --dry-run \
  --evidence-profile canonical --repeats 3 full > "$output" 2>&1 \
  || fail 'Canonical set dry run failed'
assert_contains "$output" 'Set dry run complete: no workspace or cloud resource was created.'
test ! -d "$test_repo/benchmark-results/v3-production/sets" \
  || fail 'Dry run created a set workspace'

set +e
env "${common[@]}" "$test_repo/run-cloud-benchmark-set.sh" \
  --evidence-profile canonical --repeats 3 full > "$output" 2>&1
unconfirmed_exit=$?
set -e
[ "$unconfirmed_exit" -eq 2 ] || fail "Unconfirmed paid set returned $unconfirmed_exit"
test ! -d "$test_repo/benchmark-results/v3-production/sets" \
  || fail 'Unconfirmed run created a set workspace'

env "${common[@]}" "$test_repo/run-cloud-benchmark-set.sh" \
  --evidence-profile canonical --repeats 3 --confirm-paid-run full > "$output" 2>&1 \
  || fail 'Three-member canonical set failed'
assert_contains "$output" 'Status: VALID_CANONICAL_SET; members=3'
workspace=$(find "$test_repo/benchmark-results/v3-production/sets/in-progress" -mindepth 1 -maxdepth 1 -type d | sed -n '1p')
[ -n "$workspace" ] || fail 'Canonical set workspace is missing'
assert_contains "$workspace/checkpoint.json" '"state":"COMPLETE"'
final_manifest=$(find "$test_repo/benchmark-results/v3-production/sets" -path '*/v1/benchmark-set-manifest.json' -type f | sed -n '1p')
[ -n "$final_manifest" ] || fail 'Final set manifest is missing'
assert_contains "$final_manifest" '"status":"VALID_CANONICAL_SET"'

set +e
env "${common[@]}" FAKE_SET_INFRA_ORDINAL=4 \
  "$test_repo/run-cloud-benchmark-set.sh" --evidence-profile canonical --repeats 3 \
  --confirm-paid-run full > "$output" 2>&1
infrastructure_exit=$?
set -e
[ "$infrastructure_exit" -eq 10 ] \
  || fail "Infrastructure-invalid set returned $infrastructure_exit instead of 10"
blocked_workspace=
for candidate in "$test_repo"/benchmark-results/v3-production/sets/in-progress/*; do
  if grep -F '"state":"BLOCKED_INFRASTRUCTURE"' "$candidate/checkpoint.json" >/dev/null 2>&1; then
    blocked_workspace=$candidate
  fi
done
[ -n "$blocked_workspace" ] || fail 'Infrastructure-invalid workspace is missing'
assert_contains "$blocked_workspace/checkpoint.json" '"state":"BLOCKED_INFRASTRUCTURE"'

set +e
env "${common[@]}" "$test_repo/run-cloud-benchmark-set.sh" --replace "$blocked_workspace" \
  --slot 1 --reason 'synthetic provisioning failure' --confirm-paid-run \
  > "$output" 2>&1
missing_attestation_exit=$?
set -e
[ "$missing_attestation_exit" -eq 2 ] \
  || fail "Replacement without attestation returned $missing_attestation_exit"

env "${common[@]}" "$test_repo/run-cloud-benchmark-set.sh" --replace "$blocked_workspace" \
  --slot 1 --reason 'synthetic provisioning failure' --confirm-no-score-selection \
  --confirm-paid-run > "$output" 2>&1 || fail 'Explicit infrastructure replacement failed'
assert_contains "$output" 'Status: VALID_CANONICAL_SET; members=3'
assert_contains "$blocked_workspace/checkpoint.json" '"state":"COMPLETE"'
replacement=$(find "$blocked_workspace/replacements/slot-001" -name 'replacement-*.json' -type f | sed -n '1p')
[ -n "$replacement" ] || fail 'Replacement authorization was not retained'
assert_contains "$replacement" '"confirmedWithoutScoreSelection":true'

echo 'Cloud Benchmark V2 set runner tests: PASS'
