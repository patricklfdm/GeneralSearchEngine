#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-soak-investigation-test.XXXXXX")
trap 'rm -rf -- "$test_root"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

create_fixture() {
  directory=$1
  cell=$2
  mkdir -p "$directory"
  case "$cell" in
    read-only)
      writers=0; update_mode=none; writes=0
      initial_snapshot=1; final_snapshot=1
      initial_digest=$(printf 'a%.0s' {1..64})
      final_digest=$initial_digest; corpus_changed=false
      ;;
    stable-update)
      writers=1; update_mode=stable; writes=600
      initial_snapshot=1; final_snapshot=601
      initial_digest=$(printf 'b%.0s' {1..64})
      final_digest=$initial_digest; corpus_changed=false
      ;;
    revision-update)
      writers=1; update_mode=revision; writes=600
      initial_snapshot=1; final_snapshot=601
      initial_digest=$(printf 'c%.0s' {1..64})
      final_digest=$(printf 'd%.0s' {1..64}); corpus_changed=true
      ;;
    *) fail "unknown fixture cell: $cell" ;;
  esac

  cat > "$directory/soak-config.properties" <<EOF
status=CONFIGURED
documents=100
readers=4
writers=$writers
seconds=60
sample_seconds=1
top_k=10
corpus_profile=zipf-en-medium-4
index_cycles=false
update_mode=$update_mode
per_query_metrics=true
investigation_cell=$cell
EOF
  cat > "$directory/soak-summary.properties" <<EOF
status=PASS
errors=0
run_seconds=60.100
read_operations=2440
write_operations=$writes
index_cycles=0
final_document_count=100
initial_snapshot_version=$initial_snapshot
final_snapshot_version=$final_snapshot
initial_corpus_sha256=$initial_digest
final_corpus_sha256=$final_digest
corpus_changed=$corpus_changed
EOF
  for query in text bool phrase fuzzy; do
    cat >> "$directory/soak-summary.properties" <<EOF
${query}_read_operations=610
${query}_read_ops_per_second=10.150
${query}_read_latency_samples=610
${query}_read_latency_p50_us=1.000
${query}_read_latency_p95_us=1.000
${query}_read_latency_p99_us=1.000
${query}_read_latency_max_us=1.000
EOF
  done
  cat > "$directory/soak-analysis.properties" <<EOF
analysis_status=VALID
review_required=false
EOF
  {
    echo 'timestamp,elapsed_s,text_ops,text_latency_ns,bool_ops,bool_latency_ns,phrase_ops,phrase_latency_ns,fuzzy_ops,fuzzy_latency_ns'
    for second in $(seq 0 60); do
      operations=$((10 * (second + 1)))
      latency=$((1000 * operations))
      printf '2026-08-28T00:00:%02dZ,%d.000,%d,%d,%d,%d,%d,%d,%d,%d\n' \
        "$((second % 60))" "$second" \
        "$operations" "$latency" "$operations" "$latency" \
        "$operations" "$latency" "$operations" "$latency"
    done
  } > "$directory/soak-query-samples.csv"
}

for cell in read-only stable-update revision-update; do
  fixture="$test_root/$cell"
  create_fixture "$fixture" "$cell"
  "$repo_root/scripts/analyze-v3-soak-investigation.sh" "$fixture" \
    > "$fixture/investigation.properties"
  "$repo_root/scripts/analyze-v3-soak-investigation.sh" "$fixture" \
    > "$fixture/investigation-repeat.properties"
  cmp "$fixture/investigation.properties" \
    "$fixture/investigation-repeat.properties" >/dev/null \
    || fail "$cell analysis was not deterministic"
  grep -Fx 'analysis_status=VALID' "$fixture/investigation.properties" >/dev/null \
    || fail "$cell fixture was not valid"
  grep -Fx "investigation_cell=$cell" "$fixture/investigation.properties" >/dev/null \
    || fail "$cell identity was not retained"
  grep -Fx 'review_required=false' "$fixture/investigation.properties" >/dev/null \
    || fail "$cell unexpectedly requires review"
done

rate_drift="$test_root/rate-drift"
cp -R "$test_root/read-only" "$rate_drift"
awk -F, 'BEGIN { OFS="," }
  NR == 1 { print; next }
  $2 + 0 >= 50 {
    operations = 500 + 5 * ($2 + 0 - 49)
    for (column = 3; column <= 9; column += 2) {
      $column = operations
      $(column + 1) = operations * 1000
    }
  }
  { print }
' "$rate_drift/soak-query-samples.csv" \
  > "$rate_drift/query.tmp"
mv "$rate_drift/query.tmp" "$rate_drift/soak-query-samples.csv"
sed -i \
  -e 's/^read_operations=2440$/read_operations=2220/' \
  -e 's/^.*_read_operations=610$/&_placeholder/' \
  "$rate_drift/soak-summary.properties"
sed -i \
  -e 's/^\(.*_read_operations\)=610_placeholder$/\1=555/' \
  "$rate_drift/soak-summary.properties"
"$repo_root/scripts/analyze-v3-soak-investigation.sh" "$rate_drift" \
  > "$rate_drift/investigation.properties"
grep -Fx 'flag_text_read_rate_drift=true' \
  "$rate_drift/investigation.properties" >/dev/null \
  || fail 'per-query rate drift was not flagged'
grep -Fx 'review_required=true' "$rate_drift/investigation.properties" >/dev/null \
  || fail 'per-query drift did not require review'

latency_drift="$test_root/latency-drift"
cp -R "$test_root/read-only" "$latency_drift"
awk -F, 'BEGIN { OFS="," }
  NR == 1 { print; next }
  $2 + 0 >= 50 { $4 = 500000 + ($3 - 500) * 2000 }
  { print }
' "$latency_drift/soak-query-samples.csv" \
  > "$latency_drift/query.tmp"
mv "$latency_drift/query.tmp" "$latency_drift/soak-query-samples.csv"
"$repo_root/scripts/analyze-v3-soak-investigation.sh" "$latency_drift" \
  > "$latency_drift/investigation.properties"
grep -Fx 'flag_text_mean_latency_drift=true' \
  "$latency_drift/investigation.properties" >/dev/null \
  || fail 'per-query mean-latency drift was not flagged'

bad_digest="$test_root/bad-digest"
cp -R "$test_root/stable-update" "$bad_digest"
sed -i 's/^corpus_changed=false$/corpus_changed=true/' \
  "$bad_digest/soak-summary.properties"
if "$repo_root/scripts/analyze-v3-soak-investigation.sh" "$bad_digest" \
    >/dev/null 2>&1; then
  fail 'stable-update accepted a changed corpus digest'
fi

bad_counter="$test_root/bad-counter"
cp -R "$test_root/read-only" "$bad_counter"
sed -i '3s/,20,20000,/,1,20000,/' "$bad_counter/soak-query-samples.csv"
if "$repo_root/scripts/analyze-v3-soak-investigation.sh" "$bad_counter" \
    >/dev/null 2>&1; then
  fail 'regressing query counter was accepted'
fi

bad_header="$test_root/bad-header"
cp -R "$test_root/revision-update" "$bad_header"
sed -i '1s/text_ops/text_operations/' "$bad_header/soak-query-samples.csv"
if "$repo_root/scripts/analyze-v3-soak-investigation.sh" "$bad_header" \
    >/dev/null 2>&1; then
  fail 'unexpected query CSV header was accepted'
fi

unbalanced="$test_root/unbalanced"
cp -R "$test_root/read-only" "$unbalanced"
sed -i \
  -e 's/^read_operations=2440$/read_operations=2430/' \
  -e 's/^text_read_operations=610$/text_read_operations=600/' \
  "$unbalanced/soak-summary.properties"
if "$repo_root/scripts/analyze-v3-soak-investigation.sh" "$unbalanced" \
    >/dev/null 2>&1; then
  fail 'unbalanced query summary was accepted'
fi

duplicate="$test_root/duplicate"
cp -R "$test_root/read-only" "$duplicate"
echo 'writers=0' >> "$duplicate/soak-config.properties"
if "$repo_root/scripts/analyze-v3-soak-investigation.sh" "$duplicate" \
    >/dev/null 2>&1; then
  fail 'duplicate property was accepted'
fi

nonfinite="$test_root/nonfinite"
cp -R "$test_root/read-only" "$nonfinite"
sed -i 's/^run_seconds=60.100$/run_seconds=NaN/' \
  "$nonfinite/soak-summary.properties"
if "$repo_root/scripts/analyze-v3-soak-investigation.sh" "$nonfinite" \
    >/dev/null 2>&1; then
  fail 'non-finite property was accepted'
fi

echo 'V3 soak investigation analysis tests: PASS'
