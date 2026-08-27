#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

mode=${1:-quick}
case "$mode" in
  quick|full|concurrency|soak|all) ;;
  *)
    echo "usage: $0 [quick|full|concurrency|soak|all]" >&2
    exit 2
    ;;
esac

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
commit=$(git rev-parse --short=12 HEAD)
results_root=${GSE_PERF_RESULTS_ROOT:-benchmark-results/v3-production}
run_dir="$results_root/${timestamp}-${commit}-${mode}"
mkdir -p "$run_dir"
run_dir=$(cd "$run_dir" && pwd)

status_file="$run_dir/status.properties"
printf 'status=RUNNING\nmode=%s\nstarted_utc=%s\n' \
  "$mode" "$timestamp" > "$status_file"
printf '%s\n' "$run_dir" > "$results_root/LATEST"

finish() {
  exit_code=$?
  finished=$(date -u +%Y%m%dT%H%M%SZ)
  if [ "$exit_code" -eq 0 ]; then
    status=PASS
  else
    status=FAIL
  fi
  printf 'status=%s\nmode=%s\nstarted_utc=%s\nfinished_utc=%s\nexit_code=%d\n' \
    "$status" "$mode" "$timestamp" "$finished" "$exit_code" > "$status_file"
  (
    cd "$run_dir"
    find . -type f ! -name checksums.sha256 -print0 \
      | sort -z \
      | xargs -0 sha256sum > checksums.sha256
  )
  echo "Persistent results: $run_dir"
}
trap finish EXIT

{
  echo "started_utc=$timestamp"
  echo "mode=$mode"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "git_branch=$(git branch --show-current)"
  echo "logical_cpus=$(getconf _NPROCESSORS_ONLN)"
  echo "java_home=${JAVA_HOME:-unset}"
  echo "jvm_options=${GSE_PERF_JVM_OPTIONS:--Xms2g -Xmx6g}"
  echo "working_tree_begin"
  git status --short
  echo "working_tree_end"
} > "$run_dir/metadata.txt"

{
  uname -a
  java -version
  ./mvnw -version
  if command -v lscpu >/dev/null 2>&1; then
    lscpu
  fi
  if command -v free >/dev/null 2>&1; then
    free -h
  fi
} > "$run_dir/environment.txt" 2>&1

echo "Building the JMH uber-JAR..."
./mvnw clean -Pjmh -DskipTests package 2>&1 | tee "$run_dir/build.log"

jvm_options=${GSE_PERF_JVM_OPTIONS:--Xms2g -Xmx6g}
read -r -a jvm_args <<< "$jvm_options"

if [ "$mode" = "quick" ]; then
  forks=${GSE_JMH_FORKS:-1}
  warmups=${GSE_JMH_WARMUPS:-1}
  iterations=${GSE_JMH_ITERATIONS:-2}
  duration=${GSE_JMH_DURATION:-300ms}
else
  forks=${GSE_JMH_FORKS:-2}
  warmups=${GSE_JMH_WARMUPS:-3}
  iterations=${GSE_JMH_ITERATIONS:-5}
  duration=${GSE_JMH_DURATION:-1s}
fi

run_jmh() {
  name=$1
  benchmark=$2
  shift 2
  echo "Running $name..."
  java -jar target/benchmarks.jar "$benchmark" \
    -f "$forks" -wi "$warmups" -i "$iterations" \
    -w "$duration" -r "$duration" -foe true \
    -jvmArgs "$jvm_options" \
    -rf json -rff "$run_dir/$name.json" \
    "$@" 2>&1 | tee "$run_dir/$name.log"
}

run_benchmarks() {
  if [ "$mode" = "quick" ]; then
    document_counts=10000,100000
  else
    document_counts=10000,100000,1000000
  fi

  run_jmh document-scale \
    'V3ScaleAndCorpusBenchmark.search' \
    -p "documentCount=$document_counts" \
    -p topK=10 \
    -p corpusProfile=uniform-en-short-1 \
    -p queryType=TEXT,BOOL,PHRASE,FUZZY \
    -bm avgt -tu ms -prof gc

  run_jmh top-k-scale \
    'V3ScaleAndCorpusBenchmark.search' \
    -p documentCount=100000 \
    -p topK=10,100,1000 \
    -p corpusProfile=uniform-en-short-1 \
    -p queryType=TEXT,BOOL,PHRASE,FUZZY \
    -bm avgt -tu ms -prof gc

  run_jmh corpus-shape \
    'V3ScaleAndCorpusBenchmark.search' \
    -p documentCount=10000 \
    -p topK=10 \
    -p corpusProfile=uniform-en-short-1,zipf-en-medium-4,zipf-bilingual-long-4 \
    -p queryType=TEXT,BOOL,PHRASE,FUZZY \
    -bm avgt -tu ms -prof gc

  run_concurrency
}

run_concurrency() {
  if [ "$mode" = "quick" ]; then
    thread_groups=("4,1")
  else
    thread_groups=("1,1" "4,1" "16,1")
  fi
  for group in "${thread_groups[@]}"; do
    label=${group/,/-}
    run_jmh "concurrent-latency-$label" \
      'V3ConcurrentMixedWorkloadBenchmark.mixed' \
      -p documentCount=100000 \
      -tg "$group" -bm sample -tu us -prof gc
    run_jmh "concurrent-throughput-$label" \
      'V3ConcurrentMixedWorkloadBenchmark.mixed' \
      -p documentCount=100000 \
      -tg "$group" -bm thrpt -tu s -prof gc
  done
}

run_soak() {
  soak_seconds=${GSE_SOAK_SECONDS:-1800}
  soak_readers=${GSE_SOAK_READERS:-16}
  soak_writers=${GSE_SOAK_WRITERS:-1}
  soak_documents=${GSE_SOAK_DOCUMENTS:-100000}
  echo "Running ${soak_seconds}s production soak..."
  java "${jvm_args[@]}" -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.benchmark.jmh.V3ProductionSoak \
    "--output=$run_dir/soak" \
    "--seconds=$soak_seconds" \
    "--readers=$soak_readers" \
    "--writers=$soak_writers" \
    "--documents=$soak_documents" \
    --sample-seconds=1 \
    --top-k=10 \
    --corpus-profile=zipf-en-medium-4 \
    --index-cycles=true 2>&1 | tee "$run_dir/soak.log"
}

case "$mode" in
  quick|full) run_benchmarks ;;
  concurrency) run_concurrency ;;
  soak) run_soak ;;
  all)
    run_benchmarks
    run_soak
    ;;
esac
