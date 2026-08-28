#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-investigation-runner-test.XXXXXX")
trap 'rm -rf -- "$test_root"' EXIT

expect_config_failure() {
  name=$1
  expected=$2
  shift 2
  result_root="$test_root/$name-results"
  output="$test_root/$name.log"
  set +e
  env GSE_PERF_RESULTS_ROOT="$result_root" "$@" > "$output" 2>&1
  exit_code=$?
  set -e
  [ "$exit_code" -eq 2 ] \
    || { echo "FAIL: $name returned $exit_code instead of 2" >&2; exit 1; }
  grep -F -- "$expected" "$output" >/dev/null \
    || { echo "FAIL: $name did not report $expected" >&2; exit 1; }
  [ ! -e "$result_root" ] \
    || { echo "FAIL: $name created a result directory" >&2; exit 1; }
}

runner="$repo_root/scripts/run-v3-production-performance.sh"
expect_config_failure missing-cell \
  'GSE_SOAK_INVESTIGATION_CELL must be' \
  "$runner" investigation
expect_config_failure writer-conflict \
  'GSE_SOAK_WRITERS conflicts with read-only' \
  GSE_SOAK_INVESTIGATION_CELL=read-only GSE_SOAK_WRITERS=1 \
  "$runner" investigation
expect_config_failure lifecycle-conflict \
  'GSE_SOAK_INDEX_CYCLES conflicts with investigation mode' \
  GSE_SOAK_INVESTIGATION_CELL=stable-update GSE_SOAK_INDEX_CYCLES=true \
  "$runner" investigation
expect_config_failure profile-outside-investigation \
  'GSE_SOAK_PROFILE is only valid in investigation mode' \
  GSE_SOAK_PROFILE=jfr "$runner" soak
expect_config_failure cell-outside-investigation \
  'GSE_SOAK_INVESTIGATION_CELL is only valid in investigation mode' \
  GSE_SOAK_INVESTIGATION_CELL=read-only "$runner" quick
expect_config_failure missing-stabilization-purpose \
  'GSE_SOAK_STABILIZATION_PURPOSE must be' \
  GSE_SOAK_INVESTIGATION_CELL=stable-update \
  "$runner" stabilized-investigation
expect_config_failure screening-duration-conflict \
  'GSE_SOAK_SECONDS conflicts with stabilization purpose screening' \
  GSE_SOAK_INVESTIGATION_CELL=stable-update \
  GSE_SOAK_STABILIZATION_PURPOSE=screening GSE_SOAK_SECONDS=12 \
  "$runner" stabilized-investigation
expect_config_failure reduced-window-conflict \
  'reduced-test requires five positive windows' \
  GSE_SOAK_INVESTIGATION_CELL=stable-update \
  GSE_SOAK_STABILIZATION_PURPOSE=reduced-test \
  GSE_SOAK_STABILIZATION_SECONDS=9 \
  GSE_SOAK_STABILIZATION_WINDOW_SECONDS=2 \
  "$runner" stabilized-investigation

echo 'V3 investigation runner validation tests: PASS'
