#!/usr/bin/env bash
set -euo pipefail

source_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-benchmark-upload-test.XXXXXX")
test_repo="$test_root/repository"
fake_bin="$test_root/bin"
fake_state="$test_root/fake-gcs"
output="$test_root/output.log"

cleanup() { rm -rf -- "$test_root"; }
trap cleanup EXIT
fail() {
  echo "FAIL: $*" >&2
  sed -n '1,260p' "$output" >&2 || true
  sed -n '1,260p' "$fake_state/commands.log" >&2 || true
  exit 1
}
assert_contains() { grep -F -- "$2" "$1" >/dev/null || fail "Expected '$2' in $1"; }

mkdir -p \
  "$test_repo/scripts/cloud" \
  "$test_repo/docs/v3" \
  "$test_repo/benchmark-results/v3-production" \
  "$fake_bin" \
  "$fake_state"
cp "$source_root/upload-cloud-benchmark.sh" \
  "$source_root/register-cloud-baseline.sh" \
  "$test_repo/"
cp "$source_root/scripts/cloud/benchmark_v2.py" \
  "$source_root/scripts/cloud/test_benchmark_v2.py" \
  "$source_root/scripts/cloud/test_benchmark_upload_v2.py" \
  "$test_repo/scripts/cloud/"
cp "$source_root/scripts/cloud/fake-gcloud-storage.py" "$fake_bin/gcloud"
cp "$source_root/docs/v3/cloud-benchmark-baselines.json" "$test_repo/docs/v3/"
chmod +x \
  "$test_repo/upload-cloud-benchmark.sh" \
  "$test_repo/register-cloud-baseline.sh" \
  "$fake_bin/gcloud"

set_path=$(
  cd "$test_repo"
  PYTHONPATH="$test_repo" python3 -c \
    'from pathlib import Path; from scripts.cloud.test_benchmark_upload_v2 import create_canonical_set; print(create_canonical_set(Path.cwd()))'
)

common=(
  "PATH=$fake_bin:$PATH"
  "PYTHONPATH=$test_repo"
  "FAKE_GCS_STATE_DIR=$fake_state"
  'GSE_BENCHMARK_GCS_BUCKET=gs://gse-fixture-bucket'
)

env "${common[@]}" "$test_repo/upload-cloud-benchmark.sh" \
  --dry-run "$set_path" > "$output" 2>&1 \
  || fail 'Upload dry run failed'
assert_contains "$output" 'Upload plan: VALID; source=benchmark-set'
assert_contains "$output" 'Object: benchmark-set'
assert_contains "$output" '/general-search-engine/sets/'
test ! -f "$fake_state/commands.log" || fail 'Upload dry run contacted fake GCS'

set +e
env "${common[@]}" "$test_repo/upload-cloud-benchmark.sh" \
  "$set_path" > "$output" 2>&1
unconfirmed_exit=$?
set -e
[ "$unconfirmed_exit" -eq 2 ] || fail "Unconfirmed upload returned $unconfirmed_exit"
test ! -f "$fake_state/commands.log" || fail 'Unconfirmed upload contacted fake GCS'

env "${common[@]}" "$test_repo/upload-cloud-benchmark.sh" \
  --confirm-upload "$set_path" > "$output" 2>&1 \
  || fail 'Confirmed fake upload failed'
assert_contains "$output" 'Receipt ID: gse-upload-receipt-v1-'
receipt=$(find "$test_repo/benchmark-results/v3-production/upload-receipts" \
  -mindepth 2 -maxdepth 2 -type d -name v1 | sed -n '1p')
[ -n "$receipt" ] || fail 'Local upload receipt is missing'
assert_contains "$receipt/upload-receipt.json" '"kind":"cloud-benchmark-upload-receipt"'

cp_count_before=$(grep -c '"storage","cp"' "$fake_state/commands.log")
env "${common[@]}" "$test_repo/upload-cloud-benchmark.sh" \
  --confirm-upload "$set_path" > "$output" 2>&1 \
  || fail 'Idempotent fake upload retry failed'
cp_count_after=$(grep -c '"storage","cp"' "$fake_state/commands.log")
[ "$cp_count_before" -eq "$cp_count_after" ] \
  || fail 'Idempotent retry attempted another object creation'

while IFS= read -r command; do
  case "$command" in
    *'"storage","cp"'*)
      case "$command" in
        *'--if-generation-match=0'*'--custom-metadata=gse-sha256='*) ;;
        *) fail 'Fake upload omitted create-only or SHA-256 metadata' ;;
      esac
      ;;
  esac
done < "$fake_state/commands.log"

registry="$test_repo/docs/v3/cloud-benchmark-baselines.json"
registry_before=$(sha256sum "$registry" | awk '{print $1}')
env "${common[@]}" "$test_repo/register-cloud-baseline.sh" \
  --dry-run --receipt "$receipt" --release-label 'v3 fixture' \
  v3-fixture "$set_path" > "$output" 2>&1 \
  || fail 'Baseline registration dry run failed'
assert_contains "$output" 'Registration plan: v3-fixture'
assert_contains "$output" 'Manifest: gs://gse-fixture-bucket/general-search-engine/sets/'
assert_contains "$output" 'Receipt: gse-upload-receipt-v1-'
[ "$registry_before" = "$(sha256sum "$registry" | awk '{print $1}')" ] \
  || fail 'Registration dry run mutated the registry'

env "${common[@]}" "$test_repo/register-cloud-baseline.sh" \
  --receipt "$receipt" --release-label 'v3 fixture' \
  v3-fixture "$set_path" > "$output" 2>&1 \
  || fail 'Verified baseline registration failed'
assert_contains "$output" 'Baseline registered: v3-fixture'
assert_contains "$registry" '"v3-fixture"'

registered_before=$(sha256sum "$registry" | awk '{print $1}')
set +e
env "${common[@]}" "$test_repo/register-cloud-baseline.sh" \
  --receipt "$receipt" v3-fixture "$set_path" > "$output" 2>&1
duplicate_exit=$?
set -e
[ "$duplicate_exit" -eq 85 ] || fail "Duplicate baseline returned $duplicate_exit"
[ "$registered_before" = "$(sha256sum "$registry" | awk '{print $1}')" ] \
  || fail 'Duplicate baseline changed the registry'

if grep -E '"(compute|iam|buckets|rm|mv|delete)"' "$fake_state/commands.log" >/dev/null; then
  fail 'Phase 5 invoked a forbidden cloud mutation command'
fi

echo 'Cloud Benchmark V2 upload and registration runner tests: PASS'
