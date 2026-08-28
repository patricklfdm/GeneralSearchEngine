#!/usr/bin/env bash
set -euo pipefail

export LC_ALL=C

die() {
  echo "ERROR: $*" >&2
  exit 2
}

[ "$#" -eq 1 ] || die "usage: $0 SOAK_DIRECTORY"
soak_dir=$1
samples_file="$soak_dir/soak-query-samples.csv"
summary_file="$soak_dir/soak-summary.properties"
config_file="$soak_dir/soak-config.properties"
base_analysis_file="$soak_dir/soak-analysis.properties"

for required_file in \
  "$samples_file" "$summary_file" "$config_file" "$base_analysis_file"; do
  [ -f "$required_file" ] || die "missing investigation evidence: $required_file"
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

read_property "$base_analysis_file" analysis_status
[ "$property_result" = VALID ] || die "base soak analysis is not VALID"
read_property "$base_analysis_file" review_required
base_review_required=$property_result
case "$base_review_required" in true|false) ;; *) die "invalid base review flag" ;; esac

for property_name in \
  status documents readers writers seconds sample_seconds top_k corpus_profile \
  index_cycles update_mode per_query_metrics investigation_cell; do
  read_property "$config_file" "$property_name"
  printf -v "config_${property_name}" '%s' "$property_result"
done

[ "$config_status" = CONFIGURED ] || die "soak configuration status must be CONFIGURED"
require_positive_uint documents "$config_documents"
require_positive_uint readers "$config_readers"
require_uint writers "$config_writers"
require_positive_uint seconds "$config_seconds"
require_positive_uint sample_seconds "$config_sample_seconds"
require_positive_uint top_k "$config_top_k"
[ -n "$config_corpus_profile" ] || die "corpus profile must not be empty"
[ "$config_index_cycles" = false ] || die "investigation index cycles must be false"
[ "$config_per_query_metrics" = true ] || die "per-query metrics must be enabled"

case "$config_investigation_cell" in
  read-only)
    [ "$config_writers" -eq 0 ] && [ "$config_update_mode" = none ] \
      || die "read-only cell has inconsistent writers or update mode"
    ;;
  stable-update)
    [ "$config_writers" -eq 1 ] && [ "$config_update_mode" = stable ] \
      || die "stable-update cell has inconsistent writers or update mode"
    ;;
  revision-update)
    [ "$config_writers" -eq 1 ] && [ "$config_update_mode" = revision ] \
      || die "revision-update cell has inconsistent writers or update mode"
    ;;
  *) die "unknown investigation cell: $config_investigation_cell" ;;
esac

for property_name in \
  status errors run_seconds read_operations write_operations index_cycles \
  final_document_count initial_snapshot_version final_snapshot_version \
  initial_corpus_sha256 final_corpus_sha256 corpus_changed; do
  read_property "$summary_file" "$property_name"
  printf -v "summary_${property_name}" '%s' "$property_result"
done

[ "$summary_status" = PASS ] || die "soak summary status must be PASS"
for property_name in \
  errors read_operations write_operations index_cycles final_document_count \
  initial_snapshot_version final_snapshot_version; do
  value_name="summary_${property_name}"
  require_uint "$property_name" "${!value_name}"
done
require_decimal run_seconds "$summary_run_seconds"
[ "$summary_errors" -eq 0 ] || die "soak summary contains errors"
[ "$summary_index_cycles" -eq 0 ] || die "investigation summary contains index cycles"
[ "$summary_final_document_count" -eq "$config_documents" ] \
  || die "final document count does not match configuration"
[[ "$summary_initial_corpus_sha256" =~ ^[0-9a-f]{64}$ ]] \
  || die "initial corpus digest is malformed"
[[ "$summary_final_corpus_sha256" =~ ^[0-9a-f]{64}$ ]] \
  || die "final corpus digest is malformed"
case "$summary_corpus_changed" in true|false) ;; *) die "invalid corpus_changed value" ;; esac

case "$config_investigation_cell" in
  read-only)
    [ "$summary_write_operations" -eq 0 ] \
      && [ "$summary_initial_snapshot_version" -eq "$summary_final_snapshot_version" ] \
      && [ "$summary_corpus_changed" = false ] \
      && [ "$summary_initial_corpus_sha256" = "$summary_final_corpus_sha256" ] \
      || die "read-only summary violates its state contract"
    ;;
  stable-update)
    [ "$summary_write_operations" -gt 0 ] \
      && [ "$summary_final_snapshot_version" -gt "$summary_initial_snapshot_version" ] \
      && [ "$summary_corpus_changed" = false ] \
      && [ "$summary_initial_corpus_sha256" = "$summary_final_corpus_sha256" ] \
      || die "stable-update summary violates its state contract"
    ;;
  revision-update)
    [ "$summary_write_operations" -gt 0 ] \
      && [ "$summary_final_snapshot_version" -gt "$summary_initial_snapshot_version" ] \
      && [ "$summary_corpus_changed" = true ] \
      && [ "$summary_initial_corpus_sha256" != "$summary_final_corpus_sha256" ] \
      || die "revision-update summary violates its state contract"
    ;;
esac

for query in text bool phrase fuzzy; do
  for suffix in \
    read_operations read_ops_per_second read_latency_samples \
    read_latency_p50_us read_latency_p95_us read_latency_p99_us \
    read_latency_max_us; do
    read_property "$summary_file" "${query}_${suffix}"
    printf -v "summary_${query}_${suffix}" '%s' "$property_result"
  done
  for suffix in read_operations read_latency_samples; do
    value_name="summary_${query}_${suffix}"
    require_positive_uint "${query}_${suffix}" "${!value_name}"
  done
  for suffix in \
    read_ops_per_second read_latency_p50_us read_latency_p95_us \
    read_latency_p99_us read_latency_max_us; do
    value_name="summary_${query}_${suffix}"
    require_decimal "${query}_${suffix}" "${!value_name}"
  done
done

awk -F, \
  -v expected_header='timestamp,elapsed_s,text_ops,text_latency_ns,bool_ops,bool_latency_ns,phrase_ops,phrase_latency_ns,fuzzy_ops,fuzzy_latency_ns' \
  -v cell="$config_investigation_cell" \
  -v seconds="$config_seconds" \
  -v sample_seconds="$config_sample_seconds" \
  -v documents="$config_documents" \
  -v readers="$config_readers" \
  -v writers="$config_writers" \
  -v top_k="$config_top_k" \
  -v corpus="$config_corpus_profile" \
  -v update_mode="$config_update_mode" \
  -v base_review="$base_review_required" \
  -v total_reads="$summary_read_operations" \
  -v total_writes="$summary_write_operations" \
  -v run_seconds="$summary_run_seconds" \
  -v initial_snapshot="$summary_initial_snapshot_version" \
  -v final_snapshot="$summary_final_snapshot_version" \
  -v initial_digest="$summary_initial_corpus_sha256" \
  -v final_digest="$summary_final_corpus_sha256" \
  -v corpus_changed="$summary_corpus_changed" \
  -v text_summary_ops="$summary_text_read_operations" \
  -v bool_summary_ops="$summary_bool_read_operations" \
  -v phrase_summary_ops="$summary_phrase_read_operations" \
  -v fuzzy_summary_ops="$summary_fuzzy_read_operations" \
  -v text_summary_rate="$summary_text_read_ops_per_second" \
  -v bool_summary_rate="$summary_bool_read_ops_per_second" \
  -v phrase_summary_rate="$summary_phrase_read_ops_per_second" \
  -v fuzzy_summary_rate="$summary_fuzzy_read_ops_per_second" \
  -v text_summary_samples="$summary_text_read_latency_samples" \
  -v bool_summary_samples="$summary_bool_read_latency_samples" \
  -v phrase_summary_samples="$summary_phrase_read_latency_samples" \
  -v fuzzy_summary_samples="$summary_fuzzy_read_latency_samples" \
  -v text_summary_p50="$summary_text_read_latency_p50_us" \
  -v bool_summary_p50="$summary_bool_read_latency_p50_us" \
  -v phrase_summary_p50="$summary_phrase_read_latency_p50_us" \
  -v fuzzy_summary_p50="$summary_fuzzy_read_latency_p50_us" \
  -v text_summary_p95="$summary_text_read_latency_p95_us" \
  -v bool_summary_p95="$summary_bool_read_latency_p95_us" \
  -v phrase_summary_p95="$summary_phrase_read_latency_p95_us" \
  -v fuzzy_summary_p95="$summary_fuzzy_read_latency_p95_us" \
  -v text_summary_p99="$summary_text_read_latency_p99_us" \
  -v bool_summary_p99="$summary_bool_read_latency_p99_us" \
  -v phrase_summary_p99="$summary_phrase_read_latency_p99_us" \
  -v fuzzy_summary_p99="$summary_fuzzy_read_latency_p99_us" \
  -v text_summary_max="$summary_text_read_latency_max_us" \
  -v bool_summary_max="$summary_bool_read_latency_max_us" \
  -v phrase_summary_max="$summary_phrase_read_latency_max_us" \
  -v fuzzy_summary_max="$summary_fuzzy_read_latency_max_us" '
  function fail(message) {
    print "ERROR: " message > "/dev/stderr"
    fatal = 1
    exit 2
  }
  function uint(value) { return value ~ /^[0-9]+$/ }
  function decimal(value) { return value ~ /^[0-9]+([.][0-9]+)?$/ }
  function boolean(value) { return value ? "true" : "false" }
  function query_name(idx) {
    return idx == 1 ? "text" : idx == 2 ? "bool" : idx == 3 ? "phrase" : "fuzzy"
  }
  function summary_ops(idx) {
    return idx == 1 ? text_summary_ops : idx == 2 ? bool_summary_ops : \
      idx == 3 ? phrase_summary_ops : fuzzy_summary_ops
  }
  function summary_rate(idx) {
    return idx == 1 ? text_summary_rate : idx == 2 ? bool_summary_rate : \
      idx == 3 ? phrase_summary_rate : fuzzy_summary_rate
  }
  function summary_samples(idx) {
    return idx == 1 ? text_summary_samples : idx == 2 ? bool_summary_samples : \
      idx == 3 ? phrase_summary_samples : fuzzy_summary_samples
  }
  function summary_p50(idx) {
    return idx == 1 ? text_summary_p50 : idx == 2 ? bool_summary_p50 : \
      idx == 3 ? phrase_summary_p50 : fuzzy_summary_p50
  }
  function summary_p95(idx) {
    return idx == 1 ? text_summary_p95 : idx == 2 ? bool_summary_p95 : \
      idx == 3 ? phrase_summary_p95 : fuzzy_summary_p95
  }
  function summary_p99(idx) {
    return idx == 1 ? text_summary_p99 : idx == 2 ? bool_summary_p99 : \
      idx == 3 ? phrase_summary_p99 : fuzzy_summary_p99
  }
  function summary_max(idx) {
    return idx == 1 ? text_summary_max : idx == 2 ? bool_summary_max : \
      idx == 3 ? phrase_summary_max : fuzzy_summary_max
  }
  NR == 1 {
    if ($0 != expected_header) fail("unexpected soak-query-samples.csv header")
    next
  }
  {
    if (NF != 10) fail("query sample row " NR " has " NF " columns instead of 10")
    if ($1 == "" || !decimal($2)) fail("query sample row " NR " has invalid time")
    for (column = 3; column <= 10; column++) {
      if (!uint($column)) fail("query sample row " NR " has a non-integer counter")
    }
    elapsed = $2 + 0
    bucket = int(elapsed * 6 / seconds) + 1
    if (bucket < 1) bucket = 1
    if (bucket > 6) bucket = 6
    for (query = 1; query <= 4; query++) {
      operation_column = 1 + query * 2
      latency_column = operation_column + 1
      operations[query] = $(operation_column) + 0
      latency[query] = $(latency_column) + 0
      if (sample_count > 0 && (operations[query] < previous_operations[query] ||
          latency[query] < previous_latency[query])) {
        fail("per-query cumulative counter regressed at row " NR)
      }
      if (bucket_samples[bucket] == 0) {
        bucket_first_operations[bucket, query] = operations[query]
        bucket_first_latency[bucket, query] = latency[query]
      }
      bucket_last_operations[bucket, query] = operations[query]
      bucket_last_latency[bucket, query] = latency[query]
      previous_operations[query] = operations[query]
      previous_latency[query] = latency[query]
    }
    if (sample_count > 0 && elapsed <= previous_elapsed) {
      fail("query elapsed time is not strictly increasing at row " NR)
    }
    if (bucket_samples[bucket] == 0) bucket_first_elapsed[bucket] = elapsed
    bucket_last_elapsed[bucket] = elapsed
    bucket_samples[bucket]++
    if (sample_count == 0) first_elapsed = elapsed
    previous_elapsed = elapsed
    sample_count++
  }
  END {
    if (fatal) exit 2
    minimum_samples = int(seconds / sample_seconds * 0.95) + 1
    if (sample_count < minimum_samples) fail("insufficient query sample count")
    if (first_elapsed > 2 * sample_seconds) fail("first query sample is too late")
    if (previous_elapsed < seconds) fail("final query sample did not reach duration")
    if (run_seconds + 0 < seconds) fail("summary run duration is too short")

    query_sum = 0
    minimum_query_ops = -1
    maximum_query_ops = 0
    for (query = 1; query <= 4; query++) {
      expected = summary_ops(query) + 0
      query_sum += expected
      if (expected < previous_operations[query]) {
        fail("query summary counter precedes final query sample")
      }
      if (minimum_query_ops < 0 || expected < minimum_query_ops) minimum_query_ops = expected
      if (expected > maximum_query_ops) maximum_query_ops = expected
    }
    if (query_sum != total_reads + 0) fail("per-query summary does not sum to total reads")
    if (maximum_query_ops - minimum_query_ops > readers + 0) {
      fail("per-query summary is not deterministically balanced")
    }

    for (bucket = 1; bucket <= 6; bucket++) {
      if (bucket_samples[bucket] < 2) fail("query bucket " bucket " has insufficient samples")
      duration = bucket_last_elapsed[bucket] - bucket_first_elapsed[bucket]
      if (duration <= 0) fail("query bucket " bucket " has no elapsed coverage")
      bucket_duration[bucket] = duration
      for (query = 1; query <= 4; query++) {
        operation_delta = bucket_last_operations[bucket, query] - \
          bucket_first_operations[bucket, query]
        latency_delta = bucket_last_latency[bucket, query] - \
          bucket_first_latency[bucket, query]
        if (operation_delta <= 0) fail("query bucket has no completed operations")
        bucket_rate[bucket, query] = operation_delta / duration
        bucket_mean_latency_us[bucket, query] = latency_delta / operation_delta / 1000
      }
    }

    early = 2
    late = 6
    review = 0
    for (query = 1; query <= 4; query++) {
      rate_drift[query] = (bucket_rate[late, query] / bucket_rate[early, query] - 1) * 100
      latency_drift[query] = \
        (bucket_mean_latency_us[late, query] / bucket_mean_latency_us[early, query] - 1) * 100
      rate_flag[query] = rate_drift[query] <= -10
      latency_flag[query] = latency_drift[query] >= 10
      review = review || rate_flag[query] || latency_flag[query]
    }

    print "analysis_version=1"
    print "analysis_status=VALID"
    print "investigation_cell=" cell
    print "review_required=" boolean(review)
    print "base_review_required=" base_review
    print "configured_seconds=" seconds
    print "configured_sample_seconds=" sample_seconds
    print "configured_documents=" documents
    print "configured_readers=" readers
    print "configured_writers=" writers
    print "configured_top_k=" top_k
    print "configured_corpus_profile=" corpus
    print "configured_update_mode=" update_mode
    print "configured_index_cycles=false"
    print "sample_count=" sample_count
    printf "first_elapsed_s=%.6f\n", first_elapsed
    printf "final_elapsed_s=%.6f\n", previous_elapsed
    printf "summary_run_seconds=%.6f\n", run_seconds
    print "summary_read_operations=" total_reads
    print "summary_write_operations=" total_writes
    print "summary_initial_snapshot_version=" initial_snapshot
    print "summary_final_snapshot_version=" final_snapshot
    print "summary_initial_corpus_sha256=" initial_digest
    print "summary_final_corpus_sha256=" final_digest
    print "summary_corpus_changed=" corpus_changed
    print "early_bucket=2"
    print "late_bucket=6"
    for (query = 1; query <= 4; query++) {
      name = query_name(query)
      print "summary_" name "_read_operations=" summary_ops(query)
      printf "summary_%s_read_ops_per_second=%.6f\n", name, summary_rate(query)
      print "summary_" name "_read_latency_samples=" summary_samples(query)
      printf "summary_%s_read_latency_p50_us=%.6f\n", name, summary_p50(query)
      printf "summary_%s_read_latency_p95_us=%.6f\n", name, summary_p95(query)
      printf "summary_%s_read_latency_p99_us=%.6f\n", name, summary_p99(query)
      printf "summary_%s_read_latency_max_us=%.6f\n", name, summary_max(query)
      printf "%s_read_rate_drift_pct=%.6f\n", name, rate_drift[query]
      printf "%s_mean_latency_drift_pct=%.6f\n", name, latency_drift[query]
      print "flag_" name "_read_rate_drift=" boolean(rate_flag[query])
      print "flag_" name "_mean_latency_drift=" boolean(latency_flag[query])
    }
    for (bucket = 1; bucket <= 6; bucket++) {
      printf "bucket_%d_first_elapsed_s=%.6f\n", bucket, bucket_first_elapsed[bucket]
      printf "bucket_%d_last_elapsed_s=%.6f\n", bucket, bucket_last_elapsed[bucket]
      print "bucket_" bucket "_sample_count=" bucket_samples[bucket]
      for (query = 1; query <= 4; query++) {
        name = query_name(query)
        printf "bucket_%d_%s_ops_per_second=%.6f\n", \
          bucket, name, bucket_rate[bucket, query]
        printf "bucket_%d_%s_mean_latency_us=%.6f\n", \
          bucket, name, bucket_mean_latency_us[bucket, query]
      }
    }
  }
' "$samples_file"
