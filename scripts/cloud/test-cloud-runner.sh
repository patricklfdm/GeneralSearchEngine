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
  if grep -F -- "$unexpected" "$file" >/dev/null; then
    fail "Did not expect '$unexpected' in $file"
  fi
}

mkdir -p "$test_repo/scripts/cloud" "$test_repo/benchmark-results/v3-production" "$fake_bin"
cp "$source_root/run-cloud-benchmark.sh" "$test_repo/"
cp "$source_root/pom.xml" "$source_root/mvnw" "$test_repo/"
cp "$source_root/scripts/run-v3-production-performance.sh" "$test_repo/scripts/"
cp "$source_root/scripts/cloud/remote-bootstrap.sh" \
  "$source_root/scripts/cloud/remote-run-benchmark.sh" \
  "$source_root/scripts/cloud/spot-shutdown.sh" \
  "$test_repo/scripts/cloud/"
cp "$source_root/benchmark-results/v3-production/.gitignore" \
  "$test_repo/benchmark-results/v3-production/"

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
assert_not_contains "$fake_state/commands.log" 'compute instances create'
assert_not_contains "$fake_state/commands.log" 'compute instances delete'
assert_not_contains "$fake_state/commands.log" 'compute ssh'
assert_not_contains "$fake_state/commands.log" 'compute scp'

reset_fake
set +e
env "${common_environment[@]}" FAKE_GCLOUD_SCENARIO=standard-dry \
  GSE_CLOUD_PROVISIONING=standard \
  "$test_repo/run-cloud-benchmark.sh" --dry-run full > "$output_file" 2>&1
standard_exit=$?
set -e
[ "$standard_exit" -eq 0 ] || fail "Standard dry run returned $standard_exit"
assert_not_contains "$output_file" '--provisioning-model=SPOT'
assert_not_contains "$output_file" '--instance-termination-action=STOP'
assert_contains "$output_file" '--instance-termination-action=DELETE'

run_expect 0 success quick
assert_contains "$output_file" 'Local benchmark result:'
assert_contains "$fake_state/commands.log" 'compute instances delete'
success_record=$(find "$test_repo/benchmark-results/v3-production/cloud-orchestration" \
  -name '*.properties' -type f | sort | tail -n 1)
assert_contains "$success_record" 'checksum_verified=true'
assert_contains "$success_record" 'primary_exit_code=0'
assert_contains "$success_record" 'cleanup_succeeded=true'

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
