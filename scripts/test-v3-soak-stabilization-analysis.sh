#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-stabilization-analysis-test.XXXXXX")
trap 'rm -rf -- "$test_root"' EXIT

write_fixture() {
  directory=$1
  status=$2
  error_value=$3
  mkdir -p "$directory"
  cat > "$directory/soak-config.properties" <<EOF
documents=100
readers=4
sample_seconds=1
stabilization_purpose=reduced-test
stabilization_seconds=10
stabilization_window_seconds=2
EOF
  awk -v final_error="$error_value" 'BEGIN {
    print "timestamp,elapsed_s,used_heap_bytes,committed_heap_bytes,max_heap_bytes,read_ops,read_latency_ns,text_ops,text_latency_ns,bool_ops,bool_latency_ns,phrase_ops,phrase_latency_ns,fuzzy_ops,fuzzy_latency_ns,errors,snapshot_version,document_count,gc_count,gc_time_ms"
    for (second=0; second<=10; second++) {
      error=(second == 10 ? final_error : 0)
      printf "2026-01-01T00:00:%02dZ,%d,1000,2000,4000,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,41,100,%d,%d\n", second, second, second*400, second*460000, second*100, second*100000, second*100, second*110000, second*100, second*120000, second*100, second*130000, error, second, second
    }
  }' > "$directory/soak-stabilization-samples.csv"
  measurement_started=false
  [ "$status" = READY ] && measurement_started=true
  no_errors=true
  [ "$error_value" -eq 0 ] || no_errors=false
  cat > "$directory/soak-stabilization-summary.properties" <<EOF
stabilization_status=$status
measurement_started=$measurement_started
stabilization_purpose=reduced-test
sample_count=11
loaded_corpus_sha256=same
post_corpus_sha256=same
write_operations=0
index_cycles=0
readiness_sample_coverage=true
readiness_window_coverage=true
readiness_positive_coverage=true
readiness_finite_positive=true
readiness_monotonic=true
readiness_no_errors=$no_errors
readiness_documents_unchanged=true
readiness_snapshot_unchanged=true
readiness_corpus_unchanged=true
readiness_zero_mutations=true
readiness_query_balance=true
readiness_latency_evidence=true
readiness_aggregate_rate_stable=true
readiness_aggregate_latency_stable=true
readiness_text_rate_stable=true
readiness_text_latency_stable=true
readiness_bool_rate_stable=true
readiness_bool_latency_stable=true
readiness_phrase_rate_stable=true
readiness_phrase_latency_stable=true
readiness_fuzzy_rate_stable=true
readiness_fuzzy_latency_stable=true
stabilization_handoff_seconds=0.125
EOF
}

ready="$test_root/ready"
write_fixture "$ready" READY 0
output=$($repo_root/scripts/analyze-v3-soak-stabilization.sh "$ready")
printf '%s\n' "$output" | grep -Fx 'analysis_version=1' >/dev/null
printf '%s\n' "$output" | grep -Fx 'analysis_status=VALID' >/dev/null
printf '%s\n' "$output" | grep -Fx 'stabilization_status=READY' >/dev/null
printf '%s\n' "$output" | grep -Fx 'measurement_started=true' >/dev/null

not_ready="$test_root/not-ready"
write_fixture "$not_ready" NOT_READY 1
output=$($repo_root/scripts/analyze-v3-soak-stabilization.sh "$not_ready")
printf '%s\n' "$output" | grep -Fx 'stabilization_status=NOT_READY' >/dev/null
printf '%s\n' "$output" | grep -Fx 'measurement_started=false' >/dev/null

mismatch="$test_root/mismatch"
cp -R "$not_ready" "$mismatch"
sed -i 's/stabilization_status=NOT_READY/stabilization_status=READY/' \
  "$mismatch/soak-stabilization-summary.properties"
if "$repo_root/scripts/analyze-v3-soak-stabilization.sh" "$mismatch" >/dev/null 2>&1; then
  echo 'FAIL: Java/shell readiness mismatch was accepted' >&2
  exit 1
fi

malformed="$test_root/malformed"
cp -R "$ready" "$malformed"
sed -i '1s/timestamp/bad_timestamp/' "$malformed/soak-stabilization-samples.csv"
if "$repo_root/scripts/analyze-v3-soak-stabilization.sh" "$malformed" >/dev/null 2>&1; then
  echo 'FAIL: malformed stabilization header was accepted' >&2
  exit 1
fi

echo 'V3 soak stabilization analysis tests: PASS'
