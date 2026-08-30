#!/usr/bin/env bash
set -euo pipefail

source_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-cloud-runner-test.XXXXXX")
test_repo="$test_root/repository"
remote_repo="$test_root/remote.git"
fake_bin="$test_root/bin"
fake_state="$test_root/fake-state"
output_file="$test_root/output.log"

cleanup() {
  rm -rf -- "$test_root"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  if [ -f "$output_file" ]; then
    sed -n '1,240p' "$output_file" >&2
  fi
  if [ -f "$fake_state/commands.log" ]; then
    echo 'Fake gcloud commands:' >&2
    sed -n '1,240p' "$fake_state/commands.log" >&2
  fi
  exit 1
}

assert_contains() {
  file=$1
  expected=$2
  grep -F -- "$expected" "$file" >/dev/null \
    || fail "Expected '$expected' in $file"
}

assert_not_contains() {
  file=$1
  unexpected=$2
  if [ -f "$file" ] && grep -F -- "$unexpected" "$file" >/dev/null; then
    fail "Did not expect '$unexpected' in $file"
  fi
}

mkdir -p "$test_repo/scripts/cloud" "$test_repo/benchmark-results/v3-production" "$fake_bin"
cp "$source_root/run-cloud-benchmark.sh" "$test_repo/"
cp "$source_root/pom.xml" "$source_root/mvnw" "$test_repo/"
cp "$source_root/scripts/run-v3-production-performance.sh" \
  "$source_root/scripts/analyze-v3-soak.sh" \
  "$source_root/scripts/analyze-v3-soak-investigation.sh" \
  "$source_root/scripts/analyze-v3-soak-stabilization.sh" \
  "$test_repo/scripts/"
cp "$source_root/scripts/cloud/remote-bootstrap.sh" \
  "$source_root/scripts/cloud/remote-run-benchmark.sh" \
  "$source_root/scripts/cloud/collect-benchmark-system-facts.sh" \
  "$source_root/scripts/cloud/spot-shutdown.sh" \
  "$test_repo/scripts/cloud/"
cp "$source_root/benchmark-results/v3-production/.gitignore" \
  "$test_repo/benchmark-results/v3-production/"

# The only-script Maven Wrapper falls back from ZIP to tar.gz when unzip is absent,
# but distributionSha256Sum pins the ZIP. Keep unzip an explicit VM prerequisite.
assert_contains "$test_repo/scripts/cloud/remote-bootstrap.sh" '  unzip'

git -C "$test_repo" init --quiet
git -C "$test_repo" config user.name 'Cloud Runner Test'
git -C "$test_repo" config user.email 'cloud-runner@example.test'
git -C "$test_repo" add .
git -C "$test_repo" commit --quiet -m 'test fixture'
git clone --quiet --bare "$test_repo" "$remote_repo"

ln -s "$source_root/scripts/cloud/fake-gcloud.sh" "$fake_bin/gcloud"

common_environment=(
  "PATH=$fake_bin:$PATH"
  "FAKE_GCLOUD_STATE_DIR=$fake_state"
  "FAKE_GCLOUD_REPO=$test_repo"
  "GSE_CLOUD_REPO_URL=$remote_repo"
  'GSE_GCP_PROJECT=fake-project'
  'GSE_GCP_ZONE=us-central1-a'
)

reset_fake() {
  rm -rf -- "$fake_state"
  mkdir -p "$fake_state"
  : > "$output_file"
}

run_expect() {
  expected_exit=$1
  scenario=$2
  shift 2
  reset_fake
  set +e
  env "${common_environment[@]}" "FAKE_GCLOUD_SCENARIO=$scenario" \
    "$test_repo/run-cloud-benchmark.sh" "$@" > "$output_file" 2>&1
  actual_exit=$?
  set -e
  if [ "$actual_exit" -ne "$expected_exit" ]; then
    fail "Scenario $scenario returned $actual_exit; expected $expected_exit"
  fi
}

PATH=/nonexistent /bin/bash "$test_repo/run-cloud-benchmark.sh" --help \
  > "$output_file" 2>&1 || fail '--help required an external command'
assert_contains "$output_file" 'Usage: ./run-cloud-benchmark.sh'

set +e
PATH=/nonexistent /bin/bash "$test_repo/run-cloud-benchmark.sh" invalid \
  > "$output_file" 2>&1
invalid_exit=$?
set -e
[ "$invalid_exit" -eq 2 ] || fail "Invalid mode returned $invalid_exit instead of 2"

run_expect 0 dry-run --dry-run concurrency
assert_contains "$output_file" 'Dry run complete: no cloud resources were mutated.'
assert_contains "$output_file" '--image=ubuntu-2404-noble-amd64-v20260801'
assert_not_contains "$output_file" '--image-family='
assert_contains "$output_file" '--provisioning-model=SPOT'
assert_contains "$output_file" '--instance-termination-action=STOP'
assert_contains "$output_file" '--no-service-account'
assert_contains "$output_file" '--no-scopes'
assert_contains "$output_file" '--max-run-duration=28800s'
assert_contains "$output_file" "GSE_CLOUD_SOURCE_REPOSITORY=$remote_repo"
assert_not_contains "$fake_state/commands.log" 'compute instances create'

run_expect 0 ranked-v31-dry --dry-run ranked-v31
assert_contains "$output_file" '--max-run-duration=3600s'
assert_contains "$output_file" 'GSE_CONCURRENCY_DOCUMENTS=1000000'
assert_contains "$output_file" 'GSE_CONCURRENCY_THREAD_GROUPS=16\,1'
assert_contains "$output_file" 'GSE_PERF_JVM_OPTIONS=-Xms32g\ -Xmx64g'
assert_not_contains "$fake_state/commands.log" 'compute instances create'

reset_fake
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=confirmation-dry \
  GSE_CLOUD_PROVISIONING=standard \
  GSE_GCP_ZONE=us-west4-a \
  GSE_CLOUD_IMAGE=ubuntu-2404-noble-amd64-v20260826 \
  GSE_SOAK_INVESTIGATION_CELL=revision-update \
  GSE_SOAK_STABILIZATION_PURPOSE=confirmation \
  "$test_repo/run-cloud-benchmark.sh" --dry-run stabilized-investigation \
  > "$output_file" 2>&1
confirmation_exit=$?
set -e
[ "$confirmation_exit" -eq 0 ] \
  || fail "Confirmation dry run returned $confirmation_exit"
assert_contains "$output_file" 'GSE_SOAK_STABILIZATION_PURPOSE=confirmation'
assert_contains "$output_file" 'GSE_SOAK_SECONDS=1800'
assert_contains "$output_file" '--max-run-duration=9300s'

reset_fake
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=profile-dry \
  GSE_CLOUD_PROVISIONING=standard \
  GSE_GCP_ZONE=us-west4-a \
  GSE_CLOUD_IMAGE=ubuntu-2404-noble-amd64-v20260826 \
  GSE_SOAK_INVESTIGATION_CELL=stable-update \
  GSE_SOAK_STABILIZATION_PURPOSE=profile \
  "$test_repo/run-cloud-benchmark.sh" --dry-run stabilized-investigation \
  > "$output_file" 2>&1
profile_exit=$?
set -e
[ "$profile_exit" -eq 0 ] || fail "Profile dry run returned $profile_exit"
assert_contains "$output_file" 'GSE_SOAK_STABILIZATION_PURPOSE=profile'
assert_contains "$output_file" 'GSE_SOAK_PROFILE=jfr'
assert_contains "$output_file" '--max-run-duration=8100s'

reset_fake
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=reduced-rejected \
  GSE_SOAK_INVESTIGATION_CELL=stable-update \
  GSE_SOAK_STABILIZATION_PURPOSE=reduced-test \
  "$test_repo/run-cloud-benchmark.sh" --dry-run stabilized-investigation \
  > "$output_file" 2>&1
reduced_exit=$?
set -e
[ "$reduced_exit" -eq 2 ] || fail "Cloud reduced-test returned $reduced_exit"
assert_contains "$output_file" 'reduced-test is local-only'
test ! -s "$fake_state/commands.log" \
  || fail 'Cloud reduced-test called gcloud before failing'

reset_fake
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=stabilized-dry \
  GSE_CLOUD_PROVISIONING=standard \
  GSE_GCP_ZONE=us-west4-a \
  GSE_CLOUD_IMAGE=ubuntu-2404-noble-amd64-v20260826 \
  GSE_SOAK_INVESTIGATION_CELL=stable-update \
  GSE_SOAK_STABILIZATION_PURPOSE=screening \
  "$test_repo/run-cloud-benchmark.sh" --dry-run stabilized-investigation \
  > "$output_file" 2>&1
stabilized_exit=$?
set -e
[ "$stabilized_exit" -eq 0 ] \
  || fail "Stabilized dry run returned $stabilized_exit"
assert_contains "$output_file" 'Mode:         stabilized-investigation'
assert_contains "$output_file" 'GSE_SOAK_STABILIZATION_PURPOSE=screening'
assert_contains "$output_file" 'GSE_SOAK_STABILIZATION_SECONDS=300'
assert_contains "$output_file" 'GSE_SOAK_STABILIZATION_WINDOW_SECONDS=60'
assert_contains "$output_file" '--max-run-duration=8100s'
assert_not_contains "$fake_state/commands.log" 'compute instances create'
assert_not_contains "$fake_state/commands.log" 'compute instances delete'
assert_not_contains "$fake_state/commands.log" 'compute ssh'
assert_not_contains "$fake_state/commands.log" 'compute scp'

reset_fake
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=investigation-dry \
  GSE_CLOUD_PROVISIONING=standard \
  GSE_SOAK_INVESTIGATION_CELL=read-only GSE_SOAK_PROFILE=jfr \
  "$test_repo/run-cloud-benchmark.sh" --dry-run investigation \
  > "$output_file" 2>&1
investigation_exit=$?
set -e
[ "$investigation_exit" -eq 0 ] \
  || fail "Investigation dry run returned $investigation_exit"
assert_contains "$output_file" 'Mode:         investigation'
assert_contains "$output_file" 'GSE_SOAK_INVESTIGATION_CELL=read-only'
assert_contains "$output_file" 'GSE_SOAK_PROFILE=jfr'
assert_contains "$output_file" 'GSE_SOAK_WRITERS=0'
assert_contains "$output_file" 'GSE_SOAK_INDEX_CYCLES=false'
assert_contains "$output_file" '--max-run-duration=9000s'
assert_not_contains "$fake_state/commands.log" 'compute instances create'

reset_fake
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=invalid-investigation \
  GSE_SOAK_INVESTIGATION_CELL=read-only GSE_SOAK_WRITERS=1 \
  "$test_repo/run-cloud-benchmark.sh" --dry-run investigation \
  > "$output_file" 2>&1
invalid_investigation_exit=$?
set -e
[ "$invalid_investigation_exit" -eq 2 ] \
  || fail "Conflicting investigation config returned $invalid_investigation_exit"
assert_contains "$output_file" 'GSE_SOAK_WRITERS conflicts with read-only'
test ! -s "$fake_state/commands.log" \
  || fail 'Invalid investigation config called gcloud before failing'

reset_fake
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=standard-dry \
  GSE_CLOUD_PROVISIONING=standard GSE_SOAK_INDEX_CYCLES=false \
  "$test_repo/run-cloud-benchmark.sh" --dry-run full > "$output_file" 2>&1
standard_exit=$?
set -e
[ "$standard_exit" -eq 0 ] || fail "Standard dry run returned $standard_exit"
assert_not_contains "$output_file" '--provisioning-model=SPOT'
assert_not_contains "$output_file" '--instance-termination-action=STOP'
assert_contains "$output_file" '--instance-termination-action=DELETE'
assert_contains "$output_file" 'GSE_SOAK_INDEX_CYCLES=false'

reset_fake
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=invalid-soak-boolean \
  GSE_SOAK_INDEX_CYCLES=invalid \
  "$test_repo/run-cloud-benchmark.sh" --dry-run soak > "$output_file" 2>&1
invalid_soak_boolean_exit=$?
set -e
[ "$invalid_soak_boolean_exit" -eq 2 ] \
  || fail "Invalid soak boolean returned $invalid_soak_boolean_exit instead of 2"
assert_contains "$output_file" 'GSE_SOAK_INDEX_CYCLES must be true or false'
assert_not_contains "$fake_state/commands.log" 'compute instances create'

run_expect 0 success quick
assert_contains "$output_file" 'Local benchmark result:'
assert_contains "$fake_state/commands.log" 'compute instances delete'
success_record=$(find "$test_repo/benchmark-results/v3-production/cloud-orchestration" \
  -name '*.properties' -type f | sort | tail -n 1)
assert_contains "$success_record" 'checksum_verified=true'
assert_contains "$success_record" 'primary_exit_code=0'
assert_contains "$success_record" 'cleanup_succeeded=true'

reset_fake
pointer_parent="$test_root/pointer-control"
mkdir -p "$pointer_parent"
pointer_file="$pointer_parent/attempt-001.orchestration-pointer"
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=pointer-success \
  GSE_CLOUD_ORCHESTRATION_POINTER_FILE="$pointer_file" \
  GSE_BENCHMARK_PRESET_ID=v3-production-full-v1 \
  "$test_repo/run-cloud-benchmark.sh" quick > "$output_file" 2>&1
pointer_exit=$?
set -e
[ "$pointer_exit" -eq 0 ] || fail "Pointer scenario returned $pointer_exit"
[ -f "$pointer_file" ] || fail 'V1 did not create the orchestration pointer'
pointer_record=$(sed -n '1p' "$pointer_file")
[ -n "$pointer_record" ] && [ -f "$pointer_record" ] \
  || fail 'V1 pointer did not bind an existing orchestration record'
assert_contains "$fake_state/commands.log" 'GSE_BENCHMARK_PRESET_ID=v3-production-full-v1'

reset_fake
mkdir -p "$pointer_parent/existing"
existing_pointer="$pointer_parent/existing/pointer"
printf 'occupied\n' > "$existing_pointer"
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=pointer-existing \
  GSE_CLOUD_ORCHESTRATION_POINTER_FILE="$existing_pointer" \
  "$test_repo/run-cloud-benchmark.sh" quick > "$output_file" 2>&1
existing_pointer_exit=$?
set -e
[ "$existing_pointer_exit" -eq 2 ] || fail "Existing pointer returned $existing_pointer_exit"
assert_contains "$output_file" 'Orchestration pointer target must not already exist'
assert_not_contains "$fake_state/commands.log" 'compute instances create'

run_expect 30 benchmark_fail quick
assert_contains "$fake_state/commands.log" 'compute instances delete'

run_expect 60 checksum_failure quick
test -d "$test_repo/benchmark-results/v3-production/quarantine" \
  || fail 'Checksum failure was not quarantined'

run_expect 50 scp_failure quick
assert_contains "$output_file" 'Artifact copy failed'
assert_contains "$fake_state/commands.log" 'compute instances delete'

run_expect 40 preempted quick
assert_contains "$fake_state/commands.log" 'compute instances start'
assert_contains "$fake_state/commands.log" 'compute instances delete'
test -d "$test_repo/benchmark-results/v3-production/partial" \
  || fail 'Interrupted evidence was not retained as partial'
preempted_record=$(sed -n 's/^Cloud orchestration record: //p' "$output_file" | tail -n 1)
assert_contains "$preempted_record" 'interruption_evidence=spot_instance_terminated'
assert_contains "$preempted_record" 'shutdown_marker_preempted=true'
assert_contains "$preempted_record" 'recovery_restart_succeeded=true'

run_expect 40 preempted_marker_missing quick
assert_contains "$fake_state/commands.log" 'compute instances start'
assert_contains "$fake_state/commands.log" 'compute instances delete'
test ! -f "$fake_state/interruption.properties" \
  || fail 'Marker-missing scenario unexpectedly created a shutdown marker'
markerless_record=$(sed -n 's/^Cloud orchestration record: //p' "$output_file" | tail -n 1)
assert_contains "$markerless_record" 'preempted=true'
assert_contains "$markerless_record" 'interruption_evidence=spot_instance_terminated'
assert_contains "$markerless_record" 'shutdown_marker_preempted=missing'
assert_contains "$markerless_record" 'primary_exit_code=40'
test -d "$test_repo/benchmark-results/v3-production/partial" \
  || fail 'Marker-missing interruption evidence was not retained as partial'

run_expect 40 bootstrap_preempted quick
assert_contains "$fake_state/commands.log" 'compute instances start'
assert_contains "$fake_state/commands.log" 'compute instances delete'

run_expect 50 bad_result_path quick
assert_contains "$output_file" 'Remote result discovery returned an invalid path'

run_expect 10 create_partial_failure quick
assert_contains "$fake_state/commands.log" 'compute instances create'
assert_contains "$fake_state/commands.log" 'compute instances delete'

run_expect 70 cleanup_failure quick
assert_contains "$output_file" 'VM CLEANUP FAILED'

run_expect 0 keep_vm --keep-vm quick
assert_not_contains "$fake_state/commands.log" 'compute instances delete'
assert_contains "$output_file" 'VM retained by --keep-vm'

reset_fake
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=iap \
  GSE_CLOUD_USE_IAP=true GSE_CLOUD_EXTERNAL_IP=false \
  "$test_repo/run-cloud-benchmark.sh" quick > "$output_file" 2>&1
iap_exit=$?
set -e
[ "$iap_exit" -eq 0 ] || fail "IAP scenario returned $iap_exit"
assert_contains "$fake_state/commands.log" '--tunnel-through-iap'
assert_contains "$fake_state/commands.log" '--no-address'

reset_fake
printf 'dirty\n' >> "$test_repo/pom.xml"
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=dirty \
  "$test_repo/run-cloud-benchmark.sh" quick > "$output_file" 2>&1
dirty_exit=$?
set -e
[ "$dirty_exit" -eq 2 ] || fail "Dirty-tree scenario returned $dirty_exit"
assert_contains "$output_file" 'Working tree is dirty'
git -C "$test_repo" restore pom.xml

printf '\n<!-- unpushed -->\n' >> "$test_repo/pom.xml"
git -C "$test_repo" add pom.xml
git -C "$test_repo" commit --quiet -m 'unpushed fixture commit'
reset_fake
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=unavailable-commit \
  "$test_repo/run-cloud-benchmark.sh" quick > "$output_file" 2>&1
unavailable_exit=$?
set -e
[ "$unavailable_exit" -eq 2 ] || fail "Unavailable-commit scenario returned $unavailable_exit"
assert_contains "$output_file" 'is not fetchable'

echo 'Cloud runner fake-gcloud tests: PASS'
