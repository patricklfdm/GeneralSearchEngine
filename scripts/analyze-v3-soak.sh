#!/usr/bin/env bash
set -euo pipefail

export LC_ALL=C

die() {
  echo "ERROR: $*" >&2
  exit 2
}

[ "$#" -eq 1 ] || die "usage: $0 SOAK_DIRECTORY"
soak_dir=$1
samples_file="$soak_dir/soak-samples.csv"
summary_file="$soak_dir/soak-summary.properties"
config_file="$soak_dir/soak-config.properties"

for required_file in "$samples_file" "$summary_file" "$config_file"; do
  [ -f "$required_file" ] || die "missing soak evidence: $required_file"
done

read_property() {
  property_file=$1
  property_name=$2
  if ! property_result=$(awk -v wanted="$property_name" '
      index($0, wanted "=") == 1 {
        count++
        print substr($0, length(wanted) + 2)
      }
      END { if (count != 1) exit 2 }
    ' "$property_file"); then
    die "$property_file must contain exactly one $property_name property"
  fi
}

require_uint() {
  value_name=$1
  value=$2
  [[ "$value" =~ ^[0-9]+$ ]] || die "$value_name must be an unsigned integer"
}

require_positive_uint() {
  value_name=$1
  value=$2
  require_uint "$value_name" "$value"
  [ "$value" -gt 0 ] || die "$value_name must be positive"
}

require_decimal() {
  value_name=$1
  value=$2
  [[ "$value" =~ ^[0-9]+([.][0-9]+)?$ ]] \
    || die "$value_name must be a finite non-negative decimal"
}

read_property "$config_file" status
config_status=$property_result
[ "$config_status" = CONFIGURED ] || die "soak configuration status must be CONFIGURED"
read_property "$config_file" documents
documents=$property_result
require_positive_uint documents "$documents"
read_property "$config_file" readers
readers=$property_result
require_positive_uint readers "$readers"
read_property "$config_file" writers
writers=$property_result
require_uint writers "$writers"
read_property "$config_file" seconds
seconds=$property_result
require_positive_uint seconds "$seconds"
read_property "$config_file" sample_seconds
sample_seconds=$property_result
require_positive_uint sample_seconds "$sample_seconds"
read_property "$config_file" top_k
top_k=$property_result
require_positive_uint top_k "$top_k"
read_property "$config_file" corpus_profile
corpus_profile=$property_result
[ -n "$corpus_profile" ] || die "corpus_profile must not be empty"
read_property "$config_file" index_cycles
index_cycles=$property_result
case "$index_cycles" in true|false) ;; *) die "index_cycles must be true or false" ;; esac

read_property "$summary_file" status
summary_status=$property_result
[ "$summary_status" = PASS ] || die "soak summary status must be PASS"
read_property "$summary_file" errors
summary_errors=$property_result
require_uint errors "$summary_errors"
[ "$summary_errors" -eq 0 ] || die "soak summary contains errors"

for property_name in \
  run_seconds read_operations write_operations index_cycles gc_count gc_time_ms \
  final_document_count final_snapshot_version final_writer_queue_depth \
  read_ops_per_second write_ops_per_second \
  read_latency_samples read_latency_p50_us read_latency_p95_us read_latency_p99_us \
  read_latency_max_us write_latency_samples write_latency_p50_us write_latency_p95_us \
  write_latency_p99_us write_latency_max_us; do
  read_property "$summary_file" "$property_name"
  printf -v "summary_${property_name}" '%s' "$property_result"
done

for property_name in \
  read_operations write_operations index_cycles gc_count gc_time_ms final_document_count \
  final_snapshot_version final_writer_queue_depth read_latency_samples \
  write_latency_samples; do
  value_name="summary_${property_name}"
  require_uint "$property_name" "${!value_name}"
done
for property_name in \
  run_seconds read_ops_per_second write_ops_per_second \
  read_latency_p50_us read_latency_p95_us read_latency_p99_us read_latency_max_us \
  write_latency_p50_us write_latency_p95_us write_latency_p99_us write_latency_max_us; do
  value_name="summary_${property_name}"
  require_decimal "$property_name" "${!value_name}"
done

[ "$summary_final_document_count" -eq "$documents" ] \
  || die "final document count does not match configured documents"

awk -F, \
  -v expected_header='timestamp,elapsed_s,used_heap_bytes,committed_heap_bytes,max_heap_bytes,read_ops,write_ops,index_cycles,errors,writer_queue_depth,writer_queue_capacity,snapshot_version,document_count,gc_count,gc_time_ms' \
  -v configured_seconds="$seconds" \
  -v sample_interval="$sample_seconds" \
  -v expected_documents="$documents" \
  -v configured_readers="$readers" \
  -v configured_writers="$writers" \
  -v configured_top_k="$top_k" \
  -v configured_corpus="$corpus_profile" \
  -v configured_index_cycles="$index_cycles" \
  -v summary_run_seconds="$summary_run_seconds" \
  -v summary_read_operations="$summary_read_operations" \
  -v summary_write_operations="$summary_write_operations" \
  -v summary_index_cycles="$summary_index_cycles" \
  -v summary_gc_count="$summary_gc_count" \
  -v summary_gc_time_ms="$summary_gc_time_ms" \
  -v summary_final_snapshot="$summary_final_snapshot_version" \
  -v summary_final_queue="$summary_final_writer_queue_depth" \
  -v summary_read_rate="$summary_read_ops_per_second" \
  -v summary_write_rate="$summary_write_ops_per_second" \
  -v summary_read_samples="$summary_read_latency_samples" \
  -v summary_read_p50="$summary_read_latency_p50_us" \
  -v summary_read_p95="$summary_read_latency_p95_us" \
  -v summary_read_p99="$summary_read_latency_p99_us" \
  -v summary_read_max="$summary_read_latency_max_us" \
  -v summary_write_samples="$summary_write_latency_samples" \
  -v summary_write_p50="$summary_write_latency_p50_us" \
  -v summary_write_p95="$summary_write_latency_p95_us" \
  -v summary_write_p99="$summary_write_latency_p99_us" \
  -v summary_write_max="$summary_write_latency_max_us" '
  function fail(message) {
    print "ERROR: " message > "/dev/stderr"
    fatal = 1
    exit 2
  }
  function uint(value) { return value ~ /^[0-9]+$/ }
  function decimal(value) { return value ~ /^[0-9]+([.][0-9]+)?$/ }
  function boolean(value) { return value ? "true" : "false" }
  NR == 1 {
    if ($0 != expected_header) fail("unexpected soak-samples.csv header")
    next
  }
  {
    if (NF != 15) fail("sample row " NR " has " NF " columns instead of 15")
    if ($1 == "" || !decimal($2)) fail("sample row " NR " has an invalid timestamp or elapsed value")
    for (column = 3; column <= 15; column++) {
      if (!uint($column)) fail("sample row " NR " has a non-integer counter in column " column)
    }

    elapsed = $2 + 0
    used = $3 + 0
    committed = $4 + 0
    maximum = $5 + 0
    reads = $6 + 0
    writes = $7 + 0
    cycles = $8 + 0
    errors = $9 + 0
    queue = $10 + 0
    capacity = $11 + 0
    snapshot = $12 + 0
    documents = $13 + 0
    gc_count = $14 + 0
    gc_time = $15 + 0

    bucket = int(elapsed * 6 / configured_seconds) + 1
    if (bucket < 1) bucket = 1
    if (bucket > 6) bucket = 6
    if (errors > bucket_error_max[bucket]) bucket_error_max[bucket] = errors
    if (documents != expected_documents) bucket_document_mismatches[bucket]++

    if (maximum == 0 || committed > maximum || used > maximum) {
      fail("sample row " NR " has an invalid heap relationship")
    }
    if (capacity == 0 || queue > capacity) fail("sample row " NR " has an invalid writer queue")
    if (documents != expected_documents) fail("document count changed at sample row " NR)
    if (errors != 0) fail("error count is non-zero at sample row " NR)

    if (sample_count > 0) {
      if (elapsed <= previous_elapsed) fail("elapsed time is not strictly increasing at sample row " NR)
      if (reads < previous_reads || writes < previous_writes || cycles < previous_cycles ||
          snapshot < previous_snapshot || gc_count < previous_gc_count ||
          gc_time < previous_gc_time) {
        fail("cumulative counter regressed at sample row " NR)
      }
      if (capacity != queue_capacity) fail("writer queue capacity changed at sample row " NR)
    } else {
      first_elapsed = elapsed
      first_snapshot = snapshot
      queue_capacity = capacity
    }

    if (bucket_samples[bucket] == 0) {
      bucket_first_elapsed[bucket] = elapsed
      bucket_first_reads[bucket] = reads
      bucket_first_writes[bucket] = writes
      bucket_first_cycles[bucket] = cycles
      bucket_first_gc_count[bucket] = gc_count
      bucket_first_gc_time[bucket] = gc_time
      bucket_heap_min[bucket] = used
      bucket_heap_max[bucket] = used
    }
    bucket_last_elapsed[bucket] = elapsed
    bucket_last_reads[bucket] = reads
    bucket_last_writes[bucket] = writes
    bucket_last_cycles[bucket] = cycles
    bucket_last_gc_count[bucket] = gc_count
    bucket_last_gc_time[bucket] = gc_time
    bucket_heap_sum[bucket] += used
    if (used < bucket_heap_min[bucket]) bucket_heap_min[bucket] = used
    if (used > bucket_heap_max[bucket]) bucket_heap_max[bucket] = used
    if (queue > bucket_queue_max[bucket]) bucket_queue_max[bucket] = queue
    if (queue > 0) {
      bucket_queue_nonzero[bucket]++
      queue_nonzero_total++
    }
    bucket_samples[bucket]++
    if (queue > queue_maximum) queue_maximum = queue
    if (committed > committed_maximum) committed_maximum = committed
    if (maximum > heap_maximum) heap_maximum = maximum

    sample_count++
    previous_elapsed = elapsed
    previous_reads = reads
    previous_writes = writes
    previous_cycles = cycles
    previous_snapshot = snapshot
    previous_gc_count = gc_count
    previous_gc_time = gc_time
  }
  END {
    if (fatal) exit 2
    minimum_samples = int(configured_seconds / sample_interval * 0.95) + 1
    if (sample_count < minimum_samples) fail("insufficient sample count")
    if (first_elapsed > 2 * sample_interval) fail("first sample is too late")
    if (previous_elapsed < configured_seconds) fail("final elapsed time did not reach configured duration")
    if (summary_run_seconds + 0 < configured_seconds) fail("summary run duration is too short")
    if (summary_read_operations + 0 < previous_reads ||
        summary_write_operations + 0 < previous_writes ||
        summary_index_cycles + 0 < previous_cycles ||
        summary_gc_count + 0 < previous_gc_count ||
        summary_gc_time_ms + 0 < previous_gc_time ||
        summary_final_snapshot + 0 < previous_snapshot) {
      fail("summary counters precede the final sample")
    }
    if (summary_final_queue + 0 > queue_capacity) fail("summary queue depth is invalid")
    mutation_expected = configured_writers + 0 > 0 || configured_index_cycles == "true"
    if (mutation_expected && previous_snapshot <= first_snapshot) {
      fail("snapshot version did not advance")
    }
    if (!mutation_expected && previous_snapshot != first_snapshot) {
      fail("snapshot version changed without a configured mutation source")
    }
    if (configured_writers + 0 == 0 && (summary_write_operations + 0 != 0 ||
        summary_write_samples + 0 != 0 || summary_write_rate + 0 != 0)) {
      fail("zero-writer summary contains write activity")
    }
    if (configured_index_cycles == "true" && summary_index_cycles + 0 == 0) {
      fail("dynamic index cycles were enabled but did not advance")
    }
    if (configured_index_cycles == "false" && summary_index_cycles + 0 != 0) {
      fail("dynamic index cycles were disabled but advanced")
    }

    for (bucket = 1; bucket <= 6; bucket++) {
      if (bucket_samples[bucket] < 2) fail("bucket " bucket " has insufficient samples")
      duration = bucket_last_elapsed[bucket] - bucket_first_elapsed[bucket]
      if (duration <= 0) fail("bucket " bucket " has no elapsed coverage")
      bucket_duration[bucket] = duration
      bucket_read_rate[bucket] = (bucket_last_reads[bucket] - bucket_first_reads[bucket]) / duration
      bucket_write_rate[bucket] = (bucket_last_writes[bucket] - bucket_first_writes[bucket]) / duration
      bucket_cycle_rate[bucket] = (bucket_last_cycles[bucket] - bucket_first_cycles[bucket]) / duration
      bucket_gc_rate[bucket] = (bucket_last_gc_time[bucket] - bucket_first_gc_time[bucket]) / duration
      bucket_gc_count_delta[bucket] = bucket_last_gc_count[bucket] - bucket_first_gc_count[bucket]
      bucket_heap_average[bucket] = bucket_heap_sum[bucket] / bucket_samples[bucket]
    }

    early = 2
    late = 6
    if (bucket_read_rate[early] <= 0) {
      fail("early steady read rate is not positive")
    }
    if (configured_writers + 0 > 0 && bucket_write_rate[early] <= 0) {
      fail("early steady write rate is not positive")
    }
    if (configured_writers + 0 == 0) {
      for (bucket = 1; bucket <= 6; bucket++) {
        if (bucket_write_rate[bucket] != 0) fail("zero-writer bucket contains writes")
      }
    }
    read_drift = (bucket_read_rate[late] / bucket_read_rate[early] - 1) * 100
    write_drift = configured_writers + 0 > 0 \
      ? (bucket_write_rate[late] / bucket_write_rate[early] - 1) * 100 \
      : 0
    heap_average_growth = bucket_heap_average[late] - bucket_heap_average[early]
    heap_minimum_growth = bucket_heap_min[late] - bucket_heap_min[early]
    read_rate_drift = read_drift <= -10
    write_rate_drift = write_drift <= -10
    heap_band_growth = heap_average_growth >= 536870912 || heap_minimum_growth >= 536870912
    heap_no_plateau = bucket_heap_average[4] > bucket_heap_average[3] \
      && bucket_heap_average[5] > bucket_heap_average[4] \
      && bucket_heap_average[6] > bucket_heap_average[5] \
      && heap_average_growth >= 536870912
    gc_time_high = bucket_gc_rate[late] > 50
    writer_queue_sustained = queue_nonzero_total / sample_count >= 0.10 \
      || queue_maximum >= queue_capacity * 0.01
    review_required = read_rate_drift || write_rate_drift || heap_band_growth \
      || heap_no_plateau || gc_time_high || writer_queue_sustained

    print "analysis_version=1"
    print "analysis_status=VALID"
    print "review_required=" boolean(review_required)
    print "configured_seconds=" configured_seconds
    print "configured_sample_seconds=" sample_interval
    print "configured_documents=" expected_documents
    print "configured_readers=" configured_readers
    print "configured_writers=" configured_writers
    print "configured_top_k=" configured_top_k
    print "configured_corpus_profile=" configured_corpus
    print "configured_index_cycles=" configured_index_cycles
    print "sample_count=" sample_count
    printf "first_elapsed_s=%.6f\n", first_elapsed
    printf "final_elapsed_s=%.6f\n", previous_elapsed
    print "writer_queue_capacity=" queue_capacity
    print "writer_queue_nonzero_samples=" queue_nonzero_total + 0
    print "writer_queue_maximum=" queue_maximum + 0
    printf "committed_heap_max_bytes=%.0f\n", committed_maximum
    printf "max_heap_bytes=%.0f\n", heap_maximum
    printf "summary_run_seconds=%.6f\n", summary_run_seconds
    print "summary_read_operations=" summary_read_operations
    print "summary_write_operations=" summary_write_operations
    print "summary_index_cycles=" summary_index_cycles
    print "summary_gc_count=" summary_gc_count
    print "summary_gc_time_ms=" summary_gc_time_ms
    print "summary_final_snapshot_version=" summary_final_snapshot
    print "summary_final_writer_queue_depth=" summary_final_queue
    printf "summary_read_ops_per_second=%.6f\n", summary_read_rate
    printf "summary_write_ops_per_second=%.6f\n", summary_write_rate
    print "summary_read_latency_samples=" summary_read_samples
    printf "summary_read_latency_p50_us=%.6f\n", summary_read_p50
    printf "summary_read_latency_p95_us=%.6f\n", summary_read_p95
    printf "summary_read_latency_p99_us=%.6f\n", summary_read_p99
    printf "summary_read_latency_max_us=%.6f\n", summary_read_max
    print "summary_write_latency_samples=" summary_write_samples
    printf "summary_write_latency_p50_us=%.6f\n", summary_write_p50
    printf "summary_write_latency_p95_us=%.6f\n", summary_write_p95
    printf "summary_write_latency_p99_us=%.6f\n", summary_write_p99
    printf "summary_write_latency_max_us=%.6f\n", summary_write_max
    print "early_bucket=2"
    print "late_bucket=6"
    printf "read_rate_drift_pct=%.6f\n", read_drift
    printf "write_rate_drift_pct=%.6f\n", write_drift
    printf "heap_average_growth_bytes=%.0f\n", heap_average_growth
    printf "heap_minimum_growth_bytes=%.0f\n", heap_minimum_growth
    print "flag_read_rate_drift=" boolean(read_rate_drift)
    print "flag_write_rate_drift=" boolean(write_rate_drift)
    print "flag_heap_band_growth=" boolean(heap_band_growth)
    print "flag_heap_no_plateau=" boolean(heap_no_plateau)
    print "flag_gc_time_high=" boolean(gc_time_high)
    print "flag_writer_queue_sustained=" boolean(writer_queue_sustained)
    for (bucket = 1; bucket <= 6; bucket++) {
      prefix = "bucket_" bucket "_"
      printf "%sfirst_elapsed_s=%.6f\n", prefix, bucket_first_elapsed[bucket]
      printf "%slast_elapsed_s=%.6f\n", prefix, bucket_last_elapsed[bucket]
      print prefix "sample_count=" bucket_samples[bucket]
      printf "%sread_ops_per_second=%.6f\n", prefix, bucket_read_rate[bucket]
      printf "%swrite_ops_per_second=%.6f\n", prefix, bucket_write_rate[bucket]
      printf "%sindex_cycles_per_second=%.6f\n", prefix, bucket_cycle_rate[bucket]
      printf "%sused_heap_average_bytes=%.0f\n", prefix, bucket_heap_average[bucket]
      printf "%sused_heap_minimum_bytes=%.0f\n", prefix, bucket_heap_min[bucket]
      printf "%sused_heap_maximum_bytes=%.0f\n", prefix, bucket_heap_max[bucket]
      print prefix "gc_count_delta=" bucket_gc_count_delta[bucket]
      printf "%sgc_time_ms_per_second=%.6f\n", prefix, bucket_gc_rate[bucket]
      print prefix "writer_queue_nonzero_samples=" bucket_queue_nonzero[bucket] + 0
      print prefix "writer_queue_maximum=" bucket_queue_max[bucket] + 0
      print prefix "error_maximum=" bucket_error_max[bucket] + 0
      print prefix "document_count_mismatches=" bucket_document_mismatches[bucket] + 0
    }
  }
' "$samples_file"
