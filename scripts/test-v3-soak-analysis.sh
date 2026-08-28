#!/usr/bin/env bash
set -euo pipefail

source_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
analyzer="$source_root/scripts/analyze-v3-soak.sh"
test_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-soak-analysis-test.XXXXXX")

cleanup() {
  rm -rf -- "$test_root"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_contains() {
  file=$1
  expected=$2
  grep -F -- "$expected" "$file" >/dev/null \
    || fail "Expected '$expected' in $file"
}

write_config() {
  directory=$1
  index_cycles=$2
  mkdir -p "$directory"
  {
    echo 'status=CONFIGURED'
    echo 'documents=100000'
    echo 'readers=16'
    echo 'writers=1'
    echo 'seconds=600'
    echo 'sample_seconds=10'
    echo 'top_k=10'
    echo 'corpus_profile=zipf-en-medium-4'
    echo "index_cycles=$index_cycles"
  } > "$directory/soak-config.properties"
}

write_samples() {
  directory=$1
  mode=$2
  index_cycles=$3
  samples="$directory/soak-samples.csv"
  echo 'timestamp,elapsed_s,used_heap_bytes,committed_heap_bytes,max_heap_bytes,read_ops,write_ops,index_cycles,errors,writer_queue_depth,writer_queue_capacity,snapshot_version,document_count,gc_count,gc_time_ms' \
    > "$samples"
  reads=0
  writes=0
  cycles=0
  for ((sample = 0; sample <= 60; sample++)); do
    elapsed=$((sample * 10))
    bucket=$((elapsed / 100))
    if [ "$bucket" -gt 5 ]; then bucket=5; fi
    if [ "$sample" -gt 0 ]; then
      read_rate=100
      if [ "$mode" = drifting ]; then read_rate=$((100 - bucket * 5)); fi
      reads=$((reads + read_rate * 10))
      writes=$((writes + 100))
      if [ "$index_cycles" = true ]; then cycles=$((cycles + 10)); fi
    fi
    used_heap=$((2147483648 + (sample % 5) * 10485760))
    if [ "$mode" = drifting ]; then
      used_heap=$((used_heap + sample * 15728640))
    fi
    queue=0
    if [ "$mode" = queue_pressure ]; then queue=2000; fi
    sample_reads=$reads
    if [ "$mode" = counter_regression ] && [ "$sample" -eq 30 ]; then
      sample_reads=$((reads - 2000))
    fi
    printf '2026-08-27T00:00:%02dZ,%d,%d,8589934592,17179869184,%d,%d,%d,0,%d,100000,%d,100000,%d,%d\n' \
      "$sample" "$elapsed" "$used_heap" "$sample_reads" "$writes" "$cycles" \
      "$queue" "$((100 + writes + cycles * 2))" "$sample" "$((sample * 2))" \
      >> "$samples"
  done
  final_reads=$reads
  final_writes=$writes
  final_cycles=$cycles
}

write_summary() {
  directory=$1
  {
    echo 'status=PASS'
    echo 'errors=0'
    echo 'run_seconds=600.500'
    echo "read_operations=$final_reads"
    echo "write_operations=$final_writes"
    echo "index_cycles=$final_cycles"
    echo 'gc_count=60'
    echo 'gc_time_ms=120'
    echo 'final_document_count=100000'
    echo "final_snapshot_version=$((100 + final_writes + final_cycles * 2))"
    echo 'final_writer_queue_depth=0'
    echo 'read_ops_per_second=90.000'
    echo 'write_ops_per_second=10.000'
    echo 'read_latency_samples=20000'
    echo 'read_latency_p50_us=1000.000'
    echo 'read_latency_p95_us=2000.000'
    echo 'read_latency_p99_us=3000.000'
    echo 'read_latency_max_us=4000.000'
    echo 'write_latency_samples=20000'
    echo 'write_latency_p50_us=500.000'
    echo 'write_latency_p95_us=700.000'
    echo 'write_latency_p99_us=900.000'
    echo 'write_latency_max_us=1200.000'
  } > "$directory/soak-summary.properties"
}

make_fixture() {
  name=$1
  mode=$2
  index_cycles=${3:-true}
  directory="$test_root/$name"
  write_config "$directory" "$index_cycles"
  write_samples "$directory" "$mode" "$index_cycles"
  write_summary "$directory"
}

make_fixture stable stable true
"$analyzer" "$test_root/stable" > "$test_root/stable-1.properties"
"$analyzer" "$test_root/stable" > "$test_root/stable-2.properties"
cmp "$test_root/stable-1.properties" "$test_root/stable-2.properties" \
  || fail 'Stable analysis output was not deterministic'
assert_contains "$test_root/stable-1.properties" 'analysis_status=VALID'
assert_contains "$test_root/stable-1.properties" 'review_required=false'
assert_contains "$test_root/stable-1.properties" 'flag_read_rate_drift=false'
assert_contains "$test_root/stable-1.properties" 'writer_queue_nonzero_samples=0'
assert_contains "$test_root/stable-1.properties" 'writer_queue_maximum=0'
assert_contains "$test_root/stable-1.properties" 'bucket_6_error_maximum=0'
assert_contains "$test_root/stable-1.properties" 'bucket_6_document_count_mismatches=0'

make_fixture no_cycles stable false
"$analyzer" "$test_root/no_cycles" > "$test_root/no-cycles.properties"
assert_contains "$test_root/no-cycles.properties" 'configured_index_cycles=false'
assert_contains "$test_root/no-cycles.properties" 'summary_index_cycles=0'

make_fixture drifting drifting true
"$analyzer" "$test_root/drifting" > "$test_root/drifting.properties"
assert_contains "$test_root/drifting.properties" 'review_required=true'
assert_contains "$test_root/drifting.properties" 'flag_read_rate_drift=true'
assert_contains "$test_root/drifting.properties" 'flag_heap_band_growth=true'

make_fixture queue queue_pressure true
"$analyzer" "$test_root/queue" > "$test_root/queue.properties"
assert_contains "$test_root/queue.properties" 'flag_writer_queue_sustained=true'

make_fixture malformed stable true
sed -i '1s/timestamp/bad_timestamp/' "$test_root/malformed/soak-samples.csv"
if "$analyzer" "$test_root/malformed" > /dev/null 2>&1; then
  fail 'Malformed CSV unexpectedly passed'
fi

make_fixture regression counter_regression true
if "$analyzer" "$test_root/regression" > /dev/null 2>&1; then
  fail 'Counter regression unexpectedly passed'
fi

echo 'V3 soak analysis tests: PASS'
