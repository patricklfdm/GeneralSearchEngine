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

set +e
"$source_root/run-cloud-benchmark.sh" --evidence-profile experiment quick > "$output" 2>&1
v1_profile_exit=$?
set -e
[ "$v1_profile_exit" -eq 2 ] || fail "V1 evidence-profile option returned $v1_profile_exit"
assert_contains "$output" 'Unknown option: --evidence-profile'

env "${common[@]}" "$test_repo/run-cloud-benchmark-set.sh" --dry-run \
  --evidence-profile canonical --repeats 3 full > "$output" 2>&1 \
  || fail 'Canonical set dry run failed'
assert_contains "$output" 'Set dry run complete: no workspace or cloud resource was created.'
test ! -d "$test_repo/benchmark-results/v3-production/sets" \
  || fail 'Dry run created a set workspace'

env "${common[@]}" "$test_repo/run-cloud-benchmark-set.sh" --dry-run \
  --evidence-profile canonical --repeats 3 ranked-v31 > "$output" 2>&1 \
  || fail 'V3.1 ranked canonical set dry run failed'
assert_contains "$output" 'Preset:              v3.1-ranked-v1'
assert_contains "$output" 'GSE_CONCURRENCY_DOCUMENTS=1000000'
assert_contains "$output" 'GSE_CONCURRENCY_THREAD_GROUPS=16,1'
assert_contains "$output" 'GSE_PERF_JVM_OPTIONS=-Xms32g -Xmx64g'

env "${common[@]}" "$test_repo/run-cloud-benchmark-set.sh" --dry-run \
  --evidence-profile canonical --repeats 3 final-v34 > "$output" 2>&1 \
  || fail 'V3.4 final canonical set dry run failed'
assert_contains "$output" 'Preset:              v3.4-final-in-memory-v1'
assert_contains "$output" 'GSE_BENCHMARK_PRESET_ID=v3.4-final-in-memory-v1'
assert_contains "$output" 'GSE_PERF_JVM_OPTIONS=-Xms16g -Xmx16g -XX:+UseG1GC'
assert_contains "$output" 'GSE_CLOUD_MAX_RUN_DURATION=10800s'
assert_contains "$output" 'GSE_SOAK_SECONDS=1800'
assert_contains "$output" 'GSE_V34_SUITE_PROFILE=production'
assert_contains "$output" 'GSE_V34_BURST_PRODUCERS=1,4,16'
assert_contains "$output" 'GSE_V34_LONG_RUN_WINDOW_SECONDS=60'
assert_contains "$output" 'Final-v34 slot cap:  3 VM-hours per slot'
assert_contains "$output" 'Worst-case VM-hours: 9'
assert_contains "$output" 'Worst-case vCPU-hours: 270'

set +e
env "${common[@]}" GSE_SOAK_SECONDS=21600 \
  "$test_repo/run-cloud-benchmark-set.sh" --dry-run \
  --evidence-profile canonical --repeats 3 final-v34 > "$output" 2>&1
final_duration_exit=$?
set -e
[ "$final_duration_exit" -eq 2 ] \
  || fail "V3.4 unsupported duration returned $final_duration_exit"
assert_contains "$output" 'GSE_SOAK_SECONDS must be 1800 or 7200 for final-v34'

set +e
env "${common[@]}" GSE_V34_COLD_DOCUMENTS=99999 \
  "$test_repo/run-cloud-benchmark-set.sh" --dry-run \
  --evidence-profile canonical --repeats 3 final-v34 > "$output" 2>&1
final_config_exit=$?
set -e
[ "$final_config_exit" -eq 2 ] \
  || fail "V3.4 changed suite configuration returned $final_config_exit"
assert_contains "$output" 'GSE_V34_COLD_DOCUMENTS conflicts with preset v3.4-final-in-memory-v1'

set +e
env "${common[@]}" GSE_PERF_JVM_OPTIONS='-Xms8g -Xmx16g' \
  "$test_repo/run-cloud-benchmark-set.sh" --dry-run \
  --evidence-profile canonical --repeats 3 ranked-v31 > "$output" 2>&1
ranked_heap_exit=$?
set -e
[ "$ranked_heap_exit" -eq 2 ] \
  || fail "V3.1 ranked heap conflict returned $ranked_heap_exit"
assert_contains "$output" 'GSE_PERF_JVM_OPTIONS conflicts with preset v3.1-ranked-v1'

set +e
env "${common[@]}" GSE_CLOUD_MAX_RUN_DURATION=3601s \
  "$test_repo/run-cloud-benchmark-set.sh" --dry-run \
  --evidence-profile canonical --repeats 3 ranked-v31 > "$output" 2>&1
ranked_runtime_exit=$?
set -e
[ "$ranked_runtime_exit" -eq 2 ] \
  || fail "V3.1 ranked runtime conflict returned $ranked_runtime_exit"
assert_contains "$output" 'GSE_CLOUD_MAX_RUN_DURATION conflicts with preset v3.1-ranked-v1'

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

workspace_count_before=$(find "$test_repo/benchmark-results/v3-production/sets/in-progress" \
  -mindepth 1 -maxdepth 1 -type d | wc -l)

env "${common[@]}" GSE_CLOUD_PROVISIONING=spot \
  "$test_repo/run-cloud-benchmark-set.sh" --dry-run \
  --evidence-profile experiment --repeats 1 quick > "$output" 2>&1 \
  || fail 'One-slot experiment dry run failed'
assert_contains "$output" 'Set evidence profile: experiment'
assert_contains "$output" 'Independent slots:   1'
assert_contains "$output" 'Preset:              none'
workspace_count_after=$(find "$test_repo/benchmark-results/v3-production/sets/in-progress" \
  -mindepth 1 -maxdepth 1 -type d | wc -l)
[ "$workspace_count_after" -eq "$workspace_count_before" ] \
  || fail 'Experiment dry run created a set workspace'

set +e
env "${common[@]}" GSE_CLOUD_PROVISIONING=spot \
  "$test_repo/run-cloud-benchmark-set.sh" \
  --evidence-profile experiment --repeats 1 quick > "$output" 2>&1
unconfirmed_experiment_exit=$?
set -e
[ "$unconfirmed_experiment_exit" -eq 2 ] \
  || fail "Unconfirmed experiment returned $unconfirmed_experiment_exit"
workspace_count_after=$(find "$test_repo/benchmark-results/v3-production/sets/in-progress" \
  -mindepth 1 -maxdepth 1 -type d | wc -l)
[ "$workspace_count_after" -eq "$workspace_count_before" ] \
  || fail 'Unconfirmed experiment created a set workspace'

set +e
env "${common[@]}" GSE_CLOUD_PROVISIONING=spot \
  "$test_repo/run-cloud-benchmark-set.sh" --dry-run \
  --evidence-profile experiment --repeats 1 \
  --preset v3-production-soak-v1 full > "$output" 2>&1
mismatched_preset_exit=$?
set -e
[ "$mismatched_preset_exit" -eq 2 ] \
  || fail "Mismatched experiment preset returned $mismatched_preset_exit"
assert_contains "$output" 'Set mode full is incompatible with preset v3-production-soak-v1'
workspace_count_after=$(find "$test_repo/benchmark-results/v3-production/sets/in-progress" \
  -mindepth 1 -maxdepth 1 -type d | wc -l)
[ "$workspace_count_after" -eq "$workspace_count_before" ] \
  || fail 'Mismatched experiment preset created a set workspace'

env "${common[@]}" GSE_CLOUD_PROVISIONING=spot \
  "$test_repo/run-cloud-benchmark-set.sh" \
  --evidence-profile experiment --repeats 1 \
  --confirm-paid-run quick > "$output" 2>&1 \
  || fail 'One-slot Spot experiment failed'
assert_contains "$output" 'Status: VALID_EXPERIMENT_SET; members=1'
experiment_manifest=$(find "$test_repo/benchmark-results/v3-production/sets" \
  -path '*/v1/benchmark-set-manifest.json' -type f \
  -exec grep -l '"status":"VALID_EXPERIMENT_SET"' {} \; | sed -n '1p')
[ -n "$experiment_manifest" ] || fail 'Experiment final manifest is missing'
assert_contains "$experiment_manifest" '"evidenceProfile":"experiment"'
assert_contains "$experiment_manifest" '"presetId":null'

set +e
"$test_repo/run-cloud-benchmark-set.sh" --resume "$workspace" \
  --evidence-profile experiment --confirm-paid-run > "$output" 2>&1
resume_profile_exit=$?
set -e
[ "$resume_profile_exit" -eq 2 ] \
  || fail "Resume profile override returned $resume_profile_exit"
assert_contains "$output" 'Resume/replace reads profile, repeats, preset, and mode from the immutable plan'

echo 'Cloud Benchmark V2 set runner tests: PASS'
