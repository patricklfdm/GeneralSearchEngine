#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"
test_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-stabilization-e2e.XXXXXX")
trap 'rm -rf -- "$test_root"' EXIT

./mvnw --batch-mode --no-transfer-progress -Dstyle.color=never \
  clean -Pjmh -DskipTests package >/dev/null

default_output="$test_root/default"
mkdir -p "$default_output"
java -Xms256m -Xmx1g -cp target/benchmarks.jar \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V3ProductionSoak \
  "--output=$default_output" --documents=1000 --readers=2 --writers=1 \
  --seconds=2 --sample-seconds=1 --top-k=10 \
  --corpus-profile=zipf-en-medium-4 --index-cycles=true \
  --update-mode=revision --per-query-metrics=false
[ ! -e "$default_output/soak-stabilization-samples.csv" ]
[ ! -e "$default_output/soak-stabilization-summary.properties" ]
[ ! -e "$default_output/profile.jfr" ]

not_ready_output="$test_root/not-ready"
mkdir -p "$not_ready_output"
set +e
java -Xms256m -Xmx1g -cp target/benchmarks.jar \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V3ProductionSoak \
  "--output=$not_ready_output" --documents=1000 --readers=4 --writers=1 \
  --seconds=12 --sample-seconds=1 --top-k=10 \
  --corpus-profile=zipf-en-medium-4 --index-cycles=false \
  --update-mode=stable --per-query-metrics=true \
  --stabilization-purpose=reduced-test --stabilization-seconds=5 \
  --stabilization-window-seconds=1 --allow-reduced-stabilization-test=true \
  "--jfr-output=$not_ready_output/profile.jfr" >/dev/null 2>&1
not_ready_exit=$?
set -e
[ "$not_ready_exit" -ne 0 ]
scripts/analyze-v3-soak-stabilization.sh "$not_ready_output" \
  > "$not_ready_output/soak-stabilization-analysis.properties"
grep -Fx 'analysis_status=VALID' \
  "$not_ready_output/soak-stabilization-analysis.properties" >/dev/null
grep -Fx 'stabilization_status=NOT_READY' \
  "$not_ready_output/soak-stabilization-analysis.properties" >/dev/null
grep -Fx 'measurement_started=false' \
  "$not_ready_output/soak-stabilization-analysis.properties" >/dev/null
[ ! -e "$not_ready_output/soak-samples.csv" ]
[ ! -e "$not_ready_output/soak-query-samples.csv" ]
[ ! -e "$not_ready_output/profile.jfr" ]

run_cell() {
  cell=$1
  update_mode=$2
  jfr=$3
  output="$test_root/$cell"
  mkdir -p "$output"
  command=(java -Xms256m -Xmx1g -cp target/benchmarks.jar
    io.github.patricklfdm.generalsearch.benchmark.jmh.V3ProductionSoak
    "--output=$output"
    --documents=1000
    --readers=4
    --writers=1
    --seconds=12
    --sample-seconds=1
    --top-k=10
    --corpus-profile=zipf-en-medium-4
    --index-cycles=false
    "--update-mode=$update_mode"
    --per-query-metrics=true
    --stabilization-purpose=reduced-test
    --stabilization-seconds=25
    --stabilization-window-seconds=5
    --allow-reduced-stabilization-test=true)
  if [ "$jfr" = true ]; then
    command+=("--jfr-output=$output/profile.jfr")
  fi
  "${command[@]}"
  scripts/analyze-v3-soak-stabilization.sh "$output" \
    > "$output/soak-stabilization-analysis.properties"
  scripts/analyze-v3-soak.sh "$output" > "$output/soak-analysis.properties"
  scripts/analyze-v3-soak-investigation.sh "$output" \
    > "$output/soak-investigation-analysis.properties"
  grep -Fx 'stabilization_status=READY' \
    "$output/soak-stabilization-analysis.properties" >/dev/null
  grep -Fx 'measurement_started=true' \
    "$output/soak-stabilization-analysis.properties" >/dev/null
  awk -F, 'NR == 2 { exit !($6 == 0 && $7 == 0 && $8 == 0 && $9 == 0) }' \
    "$output/soak-samples.csv"
  awk -F, 'NR == 2 { exit !($3 == 0 && $4 == 0 && $5 == 0 && $6 == 0 && $7 == 0 && $8 == 0 && $9 == 0 && $10 == 0) }' \
    "$output/soak-query-samples.csv"
  [ "$(grep -Ec '^measurement_gc_(count|time_ms)=[0-9]+$' \
      "$output/soak-summary.properties")" -eq 2 ]
  if [ "$jfr" = true ]; then
    [ -s "$output/profile.jfr" ]
    jfr summary "$output/profile.jfr" > "$output/profile-summary.txt"
    [ -s "$output/profile-summary.txt" ]
  fi
  (cd "$output" && find . -type f ! -name checksums.sha256 -print0 \
    | sort -z | xargs -0 sha256sum > checksums.sha256 \
    && sha256sum -c checksums.sha256 >/dev/null)
}

run_cell stable-update stable false
run_cell revision-update revision true

echo 'V3 soak stabilization reduced end-to-end tests: PASS'
