#!/usr/bin/env bash
set -euo pipefail

run_dir=${1:-}
[ -n "$run_dir" ] && [ -d "$run_dir" ] || {
  echo "usage: $0 SOAK_RESULT_DIRECTORY" >&2
  exit 2
}

config="$run_dir/soak-config.properties"
summary="$run_dir/soak-stabilization-summary.properties"
samples="$run_dir/soak-stabilization-samples.csv"
for evidence in "$config" "$summary" "$samples"; do
  [ -s "$evidence" ] || { echo "missing stabilization evidence: $evidence" >&2; exit 2; }
done

property() {
  key=$1
  file=$2
  awk -F= -v wanted="$key" '$1 == wanted { sub(/^[^=]*=/, ""); print; found=1 } END { exit !found }' "$file"
}

purpose=$(property stabilization_purpose "$config")
seconds=$(property stabilization_seconds "$config")
window_seconds=$(property stabilization_window_seconds "$config")
sample_seconds=$(property sample_seconds "$config")
documents=$(property documents "$config")
readers=$(property readers "$config")
case "$purpose" in screening|confirmation|profile|reduced-test) ;; *) echo "invalid stabilization purpose" >&2; exit 2 ;; esac
for numeric in "$seconds" "$window_seconds" "$sample_seconds" "$documents" "$readers"; do
  [[ "$numeric" =~ ^[1-9][0-9]*$ ]] || { echo "invalid positive stabilization configuration" >&2; exit 2; }
done
[ "$seconds" -eq $((5 * window_seconds)) ] || { echo "stabilization must contain five windows" >&2; exit 2; }

computed=$(mktemp "${TMPDIR:-/tmp}/gse-stabilization.XXXXXX")
trap 'rm -f -- "$computed"' EXIT
awk -F, -v duration="$seconds" -v width="$window_seconds" \
    -v sample_seconds="$sample_seconds" -v documents="$documents" -v readers="$readers" '
BEGIN {
  expected_header="timestamp,elapsed_s,used_heap_bytes,committed_heap_bytes,max_heap_bytes,read_ops,read_latency_ns,text_ops,text_latency_ns,bool_ops,bool_latency_ns,phrase_ops,phrase_latency_ns,fuzzy_ops,fuzzy_latency_ns,errors,snapshot_version,document_count,gc_count,gc_time_ms"
  names[0]="aggregate"; names[1]="text"; names[2]="bool"; names[3]="phrase"; names[4]="fuzzy"
  opcol[0]=6; latcol[0]=7; opcol[1]=8; latcol[1]=9; opcol[2]=10; latcol[2]=11
  opcol[3]=12; latcol[3]=13; opcol[4]=14; latcol[4]=15
  monotonic=1; no_errors=1; documents_unchanged=1; snapshot_unchanged=1
}
NR == 1 { if ($0 != expected_header) exit 80; next }
{
  if (NF != 20 || $1 == "" || $2 !~ /^[0-9]+([.][0-9]+)?$/) exit 81
  for (column=3; column<=20; column++) if ($column !~ /^[0-9]+$/) exit 81
  window=int($2 / width) + 1; if (window > 5) window=5
  count[window]++
  if (!(window SUBSEP "first" in seen)) {
    seen[window,"first"]=1; first_elapsed[window]=$2
    for (metric=0; metric<5; metric++) { first_op[window,metric]=$(opcol[metric]); first_lat[window,metric]=$(latcol[metric]) }
  }
  last_elapsed[window]=$2
  for (metric=0; metric<5; metric++) { last_op[window,metric]=$(opcol[metric]); last_lat[window,metric]=$(latcol[metric]) }
  if (NR == 2) { loaded_snapshot=$17; loaded_documents=$18 }
  if ($16 != 0) no_errors=0
  if ($17 != loaded_snapshot) snapshot_unchanged=0
  if ($18 != documents) documents_unchanged=0
  if (NR > 2) {
    if ($2 < previous_elapsed || $6 < previous_read || $7 < previous_read_latency || $16 < previous_errors || $19 < previous_gc_count || $20 < previous_gc_time) monotonic=0
    for (metric=1; metric<5; metric++) if ($(opcol[metric]) < previous_op[metric] || $(latcol[metric]) < previous_lat[metric]) monotonic=0
  }
  previous_elapsed=$2; previous_read=$6; previous_read_latency=$7; previous_errors=$16; previous_gc_count=$19; previous_gc_time=$20
  for (metric=1; metric<5; metric++) { previous_op[metric]=$(opcol[metric]); previous_lat[metric]=$(latcol[metric]) }
  rows++
}
END {
  if (NR <= 1) exit 82
  expected=int((duration / sample_seconds) * 0.95) + 1
  sample_coverage=(rows >= expected); window_coverage=1; positive_coverage=1; finite_positive=1
  for (window=1; window<=5; window++) if (count[window] < 2) window_coverage=0
  for (metric=0; metric<5; metric++) {
    minimum_rate=-1; maximum_rate=0; sum_rate=0; minimum_latency=-1; maximum_latency=0; sum_latency=0
    for (window=3; window<=5; window++) {
      elapsed=last_elapsed[window]-first_elapsed[window]; operations=last_op[window,metric]-first_op[window,metric]; latency=last_lat[window,metric]-first_lat[window,metric]
      if (count[window] < 2) {
        rate=0; mean_latency=0
      } else if (elapsed <= 0 || operations <= 0 || latency <= 0) {
        positive_coverage=0; rate=0; mean_latency=0
      } else {
        rate=operations/elapsed; mean_latency=latency/operations
      }
      if (count[window] >= 2 && (rate <= 0 || mean_latency <= 0 || rate != rate || mean_latency != mean_latency)) finite_positive=0
      if (minimum_rate < 0 || rate < minimum_rate) minimum_rate=rate; if (rate > maximum_rate) maximum_rate=rate; sum_rate+=rate
      if (minimum_latency < 0 || mean_latency < minimum_latency) minimum_latency=mean_latency; if (mean_latency > maximum_latency) maximum_latency=mean_latency; sum_latency+=mean_latency
    }
    rate_stable[metric]=(sum_rate > 0 && (maximum_rate-minimum_rate)/(sum_rate/3.0) <= 0.05)
    latency_stable[metric]=(sum_latency > 0 && (maximum_latency-minimum_latency)/(sum_latency/3.0) <= 0.10)
  }
  minimum_query=last_op[5,1]; maximum_query=last_op[5,1]
  for (metric=2; metric<5; metric++) { if (last_op[5,metric] < minimum_query) minimum_query=last_op[5,metric]; if (last_op[5,metric] > maximum_query) maximum_query=last_op[5,metric] }
  query_balance=(maximum_query-minimum_query <= readers)
  latency_evidence=1
  for (metric=1; metric<5; metric++) if (last_lat[5,metric] <= 0) latency_evidence=0
  ready=sample_coverage && window_coverage && positive_coverage && finite_positive && monotonic && no_errors && documents_unchanged && snapshot_unchanged && query_balance && latency_evidence
  for (metric=0; metric<5; metric++) ready=ready && rate_stable[metric] && latency_stable[metric]
  print "sample_coverage=" bool(sample_coverage); print "window_coverage=" bool(window_coverage); print "positive_coverage=" bool(positive_coverage)
  print "finite_positive=" bool(finite_positive); print "monotonic=" bool(monotonic); print "no_errors=" bool(no_errors)
  print "documents_unchanged=" bool(documents_unchanged); print "snapshot_unchanged=" bool(snapshot_unchanged)
  print "query_balance=" bool(query_balance)
  print "latency_evidence=" bool(latency_evidence)
  for (metric=0; metric<5; metric++) { print names[metric] "_rate_stable=" bool(rate_stable[metric]); print names[metric] "_latency_stable=" bool(latency_stable[metric]) }
  print "raw_ready=" bool(ready)
}
function bool(value) { return value ? "true" : "false" }
' "$samples" > "$computed" || { echo "malformed stabilization samples" >&2; exit 2; }

computed_property() { property "$1" "$computed"; }
for flag in sample_coverage window_coverage positive_coverage finite_positive monotonic no_errors \
  documents_unchanged snapshot_unchanged query_balance latency_evidence aggregate_rate_stable aggregate_latency_stable \
  text_rate_stable text_latency_stable bool_rate_stable bool_latency_stable \
  phrase_rate_stable phrase_latency_stable fuzzy_rate_stable fuzzy_latency_stable; do
  expected=$(computed_property "$flag")
  actual=$(property "readiness_$flag" "$summary")
  [ "$actual" = "$expected" ] || { echo "Java/shell readiness mismatch: $flag" >&2; exit 2; }
done

raw_ready=$(computed_property raw_ready)
java_status=$(property stabilization_status "$summary")
measurement_started=$(property measurement_started "$summary")
corpus_unchanged=false
[ "$(property loaded_corpus_sha256 "$summary")" = \
    "$(property post_corpus_sha256 "$summary")" ] && corpus_unchanged=true
zero_mutations=false
[ "$(property write_operations "$summary")" = 0 ] \
  && [ "$(property index_cycles "$summary")" = 0 ] && zero_mutations=true
for pair in "corpus_unchanged:$corpus_unchanged" "zero_mutations:$zero_mutations"; do
  name=${pair%%:*}; actual=${pair#*:}
  [ "$(property "readiness_$name" "$summary")" = "$actual" ] \
    || { echo "Java/shell readiness mismatch: $name" >&2; exit 2; }
done
for flag in "$corpus_unchanged" "$zero_mutations"; do
  [ "$flag" = true ] || raw_ready=false
done
expected_status=NOT_READY
[ "$raw_ready" = true ] && expected_status=READY
[ "$java_status" = "$expected_status" ] || { echo "Java stabilization status mismatch" >&2; exit 2; }
case "$measurement_started" in true|false) ;; *) echo "invalid measurement_started" >&2; exit 2 ;; esac
if [ "$java_status" = NOT_READY ] && [ "$measurement_started" != false ]; then
  echo "NOT_READY evidence claims measurement started" >&2
  exit 2
fi
if [ "$java_status" = READY ] && [ "$measurement_started" = true ]; then
  handoff=$(property stabilization_handoff_seconds "$summary")
  awk -v value="$handoff" 'BEGIN { exit !(value >= 0 && value == value) }' \
    || { echo "invalid stabilization handoff" >&2; exit 2; }
fi

printf '%s\n' \
  'analysis_version=1' \
  'analysis_status=VALID' \
  "stabilization_status=$java_status" \
  "measurement_started=$measurement_started" \
  "review_required=$([ "$java_status" = READY ] && echo false || echo true)" \
  "stabilization_purpose=$purpose" \
  "sample_count=$(property sample_count "$summary")"
