#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

mode=${1:-quick}
case "$mode" in
  quick|full|concurrency|soak|investigation|stabilized-investigation|ranked-v31|final-v34|all) ;;
  *)
    echo "usage: $0 [quick|full|concurrency|soak|investigation|stabilized-investigation|ranked-v31|final-v34|all]" >&2
    exit 2
    ;;
esac

investigation_cell=${GSE_SOAK_INVESTIGATION_CELL:-}
soak_profile=${GSE_SOAK_PROFILE:-none}
soak_update_mode=revision
soak_per_query_metrics=false
soak_writers=${GSE_SOAK_WRITERS:-1}
soak_index_cycles=${GSE_SOAK_INDEX_CYCLES:-true}
stabilization_purpose=${GSE_SOAK_STABILIZATION_PURPOSE:-}
stabilization_seconds=0
stabilization_window_seconds=60
allow_reduced_stabilization_test=false

if [ "$mode" = investigation ] || [ "$mode" = stabilized-investigation ]; then
  case "$investigation_cell" in
    read-only) expected_writers=0; soak_update_mode=none ;;
    stable-update) expected_writers=1; soak_update_mode=stable ;;
    revision-update) expected_writers=1; soak_update_mode=revision ;;
    *)
      echo "GSE_SOAK_INVESTIGATION_CELL must be read-only, stable-update, or revision-update" >&2
      exit 2
      ;;
  esac
  if [ -n "${GSE_SOAK_WRITERS+x}" ] && [ "$GSE_SOAK_WRITERS" != "$expected_writers" ]; then
    echo "GSE_SOAK_WRITERS conflicts with $investigation_cell (expected $expected_writers)" >&2
    exit 2
  fi
  if [ -n "${GSE_SOAK_INDEX_CYCLES+x}" ] && [ "$GSE_SOAK_INDEX_CYCLES" != false ]; then
    echo "GSE_SOAK_INDEX_CYCLES conflicts with investigation mode (expected false)" >&2
    exit 2
  fi
  soak_writers=$expected_writers
  soak_index_cycles=false
  soak_per_query_metrics=true
  if [ "$mode" = stabilized-investigation ]; then
    case "$stabilization_purpose" in
      screening) expected_seconds=600; stabilization_seconds=300; stabilization_window_seconds=60; expected_profile=none ;;
      confirmation) expected_seconds=1800; stabilization_seconds=300; stabilization_window_seconds=60; expected_profile=none ;;
      profile) expected_seconds=600; stabilization_seconds=300; stabilization_window_seconds=60; expected_profile=jfr ;;
      reduced-test)
        stabilization_seconds=${GSE_SOAK_STABILIZATION_SECONDS:-10}
        stabilization_window_seconds=${GSE_SOAK_STABILIZATION_WINDOW_SECONDS:-2}
        expected_seconds=${GSE_SOAK_SECONDS:-12}
        expected_profile=${GSE_SOAK_PROFILE:-none}
        allow_reduced_stabilization_test=true
        for numeric in "$stabilization_seconds" "$stabilization_window_seconds" "$expected_seconds"; do
          [[ "$numeric" =~ ^[1-9][0-9]*$ ]] || {
            echo "reduced-test durations must be positive integers" >&2
            exit 2
          }
        done
        if [ "$stabilization_seconds" -ne $((5 * stabilization_window_seconds)) ] \
            || [ "$expected_seconds" -lt 12 ]; then
          echo "reduced-test requires five positive windows and at least 12 measurement seconds" >&2
          exit 2
        fi
        ;;
      *)
        echo "GSE_SOAK_STABILIZATION_PURPOSE must be screening, confirmation, profile, or reduced-test" >&2
        exit 2
        ;;
    esac
    for pair in \
      "GSE_SOAK_SECONDS:${GSE_SOAK_SECONDS:-}:$expected_seconds" \
      "GSE_SOAK_STABILIZATION_SECONDS:${GSE_SOAK_STABILIZATION_SECONDS:-}:$stabilization_seconds" \
      "GSE_SOAK_STABILIZATION_WINDOW_SECONDS:${GSE_SOAK_STABILIZATION_WINDOW_SECONDS:-}:$stabilization_window_seconds" \
      "GSE_SOAK_PROFILE:${GSE_SOAK_PROFILE:-}:$expected_profile"; do
      IFS=: read -r name supplied expected <<< "$pair"
      if [ -n "$supplied" ] && [ "$supplied" != "$expected" ]; then
        echo "$name conflicts with stabilization purpose $stabilization_purpose (expected $expected)" >&2
        exit 2
      fi
    done
    soak_profile=$expected_profile
    if [ "$stabilization_purpose" != reduced-test ]; then
      for pair in \
        "GSE_SOAK_READERS:${GSE_SOAK_READERS:-}:16" \
        "GSE_SOAK_DOCUMENTS:${GSE_SOAK_DOCUMENTS:-}:100000"; do
        IFS=: read -r name supplied expected <<< "$pair"
        if [ -n "$supplied" ] && [ "$supplied" != "$expected" ]; then
          echo "$name conflicts with production stabilization (expected $expected)" >&2
          exit 2
        fi
      done
    fi
  elif [ -n "$stabilization_purpose" ]; then
    echo "GSE_SOAK_STABILIZATION_PURPOSE is only valid in stabilized-investigation mode" >&2
    exit 2
  fi
else
  [ -z "$investigation_cell" ] \
    || { echo "GSE_SOAK_INVESTIGATION_CELL is only valid in investigation mode" >&2; exit 2; }
  [ "$soak_profile" = none ] \
    || { echo "GSE_SOAK_PROFILE is only valid in investigation mode" >&2; exit 2; }
  [ -z "$stabilization_purpose" ] \
    || { echo "GSE_SOAK_STABILIZATION_PURPOSE is only valid in stabilized-investigation mode" >&2; exit 2; }
fi
case "$soak_profile" in
  none|jfr) ;;
  *) echo "GSE_SOAK_PROFILE must be none or jfr" >&2; exit 2 ;;
esac
case "$soak_index_cycles" in
  true|false) ;;
  *)
    echo "GSE_SOAK_INDEX_CYCLES must be true or false" >&2
    exit 2
    ;;
esac
if { [ "$mode" = soak ] || [ "$mode" = investigation ] \
    || [ "$mode" = stabilized-investigation ] || [ "$mode" = all ]; } \
    && [ ! -x scripts/analyze-v3-soak.sh ]; then
  echo "Missing executable soak analyzer: scripts/analyze-v3-soak.sh" >&2
  exit 2
fi
if [ "$mode" = investigation ] && [ ! -x scripts/analyze-v3-soak-investigation.sh ]; then
  echo "Missing executable investigation analyzer: scripts/analyze-v3-soak-investigation.sh" >&2
  exit 2
fi
if [ "$mode" = stabilized-investigation ] \
    && [ ! -x scripts/analyze-v3-soak-stabilization.sh ]; then
  echo "Missing executable stabilization analyzer: scripts/analyze-v3-soak-stabilization.sh" >&2
  exit 2
fi
if [ "$soak_profile" = jfr ] && ! command -v jfr >/dev/null 2>&1; then
  echo "GSE_SOAK_PROFILE=jfr requires the jfr command" >&2
  exit 2
fi

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

jvm_options=${GSE_PERF_JVM_OPTIONS:--Xms2g -Xmx6g}
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

if [ "$mode" = ranked-v31 ]; then
  concurrency_documents=${GSE_CONCURRENCY_DOCUMENTS:-1000000}
else
  concurrency_documents=${GSE_CONCURRENCY_DOCUMENTS:-100000}
fi
if [[ ! "$concurrency_documents" =~ ^[1-9][0-9]*$ ]]; then
  echo "GSE_CONCURRENCY_DOCUMENTS must be a positive integer" >&2
  exit 2
fi
if [ -n "${GSE_CONCURRENCY_THREAD_GROUPS:-}" ]; then
  read -r -a thread_groups <<< "$GSE_CONCURRENCY_THREAD_GROUPS"
elif [ "$mode" = "quick" ]; then
  thread_groups=("4,1")
elif [ "$mode" = ranked-v31 ]; then
  thread_groups=("16,1")
else
  thread_groups=("1,1" "4,1" "16,1")
fi
if [ "${#thread_groups[@]}" -eq 0 ]; then
  echo "GSE_CONCURRENCY_THREAD_GROUPS must contain at least one reader,writer group" >&2
  exit 2
fi
for group in "${thread_groups[@]}"; do
  if [[ ! "$group" =~ ^[1-9][0-9]*,[1-9][0-9]*$ ]]; then
    echo "Invalid concurrency thread group: $group (expected readers,writers)" >&2
    exit 2
  fi
done

write_metadata_if_set() {
  key=$1
  variable=$2
  value=${!variable-}
  if [ -n "$value" ]; then
    printf '%s=%s\n' "$key" "$value"
  fi
}

if [ "$mode" = ranked-v31 ]; then
  benchmark_suite=v3.1-ranked-suite-v1
elif [ "$mode" = final-v34 ]; then
  benchmark_suite=v3.4-final-in-memory-suite-v1
else
  benchmark_suite=v3-production
fi
system_facts=$(GSE_BENCHMARK_SUITE="$benchmark_suite" \
  scripts/cloud/collect-benchmark-system-facts.sh)

{
  printf '%s\n' "$system_facts"
  echo "started_utc=$timestamp"
  echo "mode=$mode"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "git_branch=$(git branch --show-current)"
  echo "logical_cpus=$(getconf _NPROCESSORS_ONLN)"
  echo "java_home=${JAVA_HOME:-unset}"
  echo "java_runtime=$(java -version 2>&1 | sed -n '1p')"
  echo "jvm_options=$jvm_options"
  echo "jmh_forks=$forks"
  echo "jmh_warmups=$warmups"
  echo "jmh_iterations=$iterations"
  echo "jmh_duration=$duration"
  echo "concurrency_documents=$concurrency_documents"
  printf 'concurrency_thread_groups=%s\n' "${thread_groups[*]}"
  echo "v31_document_counts=100000,1000000"
  if [ "$mode" = final-v34 ]; then
    echo "v34_suite_profile=${GSE_V34_SUITE_PROFILE:-production}"
    echo "v34_cold_documents=${GSE_V34_COLD_DOCUMENTS:-100000}"
    echo "v34_cold_tokens=${GSE_V34_COLD_TOKENS:-16}"
    echo "v34_cold_batch_size=${GSE_V34_COLD_BATCH_SIZE:-1000}"
    echo "v34_cold_repeats=${GSE_V34_COLD_REPEATS:-5}"
    echo "v34_cold_seed=${GSE_V34_COLD_SEED:-34}"
    echo "v34_extreme_documents=${GSE_V34_EXTREME_DOCUMENTS:-1000}"
    echo "v34_extreme_tokens=${GSE_V34_EXTREME_TOKENS:-64}"
    echo "v34_extreme_seed=${GSE_V34_EXTREME_SEED:-34}"
    echo "v34_burst_producers=${GSE_V34_BURST_PRODUCERS:-1,4,16}"
    echo "v34_burst_batch_sizes=${GSE_V34_BURST_BATCH_SIZES:-1,100,1000}"
    echo "v34_burst_batches_per_producer=${GSE_V34_BURST_BATCHES_PER_PRODUCER:-4}"
    echo "v34_burst_documents=${GSE_V34_BURST_DOCUMENTS:-64000}"
    echo "v34_burst_readers=${GSE_V34_BURST_READERS:-4}"
    echo "v34_burst_queue_capacity=${GSE_V34_BURST_QUEUE_CAPACITY:-32}"
    echo "v34_long_run_seconds=${GSE_SOAK_SECONDS:-1800}"
    echo "v34_long_run_documents=${GSE_V34_LONG_RUN_DOCUMENTS:-10000}"
    echo "v34_long_run_readers=${GSE_V34_LONG_RUN_READERS:-6}"
    echo "v34_long_run_warmup_seconds=${GSE_V34_LONG_RUN_WARMUP_SECONDS:-30}"
    echo "v34_long_run_window_seconds=${GSE_V34_LONG_RUN_WINDOW_SECONDS:-60}"
    echo "v34_long_run_sample_millis=${GSE_V34_LONG_RUN_SAMPLE_MILLIS:-1000}"
    echo "v34_long_run_steady_millis=${GSE_V34_LONG_RUN_STEADY_MILLIS:-25}"
    echo "v34_long_run_burst_every_seconds=${GSE_V34_LONG_RUN_BURST_EVERY_SECONDS:-60}"
    echo "v34_long_run_burst_producers=${GSE_V34_LONG_RUN_BURST_PRODUCERS:-4}"
    echo "v34_long_run_burst_batch_size=${GSE_V34_LONG_RUN_BURST_BATCH_SIZE:-100}"
    echo "v34_long_run_lifecycle_every_seconds=${GSE_V34_LONG_RUN_LIFECYCLE_EVERY_SECONDS:-120}"
    echo "v34_long_run_queue_capacity=${GSE_V34_LONG_RUN_QUEUE_CAPACITY:-1000}"
  fi
  echo "soak_index_cycles=$soak_index_cycles"
  echo "soak_investigation_cell=${investigation_cell:-none}"
  echo "soak_update_mode=$soak_update_mode"
  echo "soak_per_query_metrics=$soak_per_query_metrics"
  echo "soak_profile=$soak_profile"
  echo "soak_stabilization_purpose=${stabilization_purpose:-none}"
  echo "soak_stabilization_seconds=$stabilization_seconds"
  echo "soak_stabilization_window_seconds=$stabilization_window_seconds"
  if [ "$mode" = stabilized-investigation ] && [ "$soak_profile" = jfr ]; then
    echo 'jfr_configuration=jdk-profile'
    echo 'jfr_recording_start_phase=MEASURE_SELECTED_CELL'
    echo 'jfr_recording_stop_phase=MEASUREMENT_WORKERS_JOINED'
    echo 'jfr_recording_scope=measurement-only'
  fi
  write_metadata_if_set cloud_provider GSE_CLOUD_PROVIDER
  write_metadata_if_set cloud_project GSE_CLOUD_PROJECT
  write_metadata_if_set cloud_zone GSE_CLOUD_ZONE
  write_metadata_if_set cloud_machine_type GSE_CLOUD_MACHINE_TYPE
  write_metadata_if_set cloud_provisioning GSE_CLOUD_PROVISIONING
  write_metadata_if_set cloud_instance_name GSE_CLOUD_INSTANCE_NAME
  write_metadata_if_set cloud_image_project GSE_CLOUD_IMAGE_PROJECT
  write_metadata_if_set cloud_image_family GSE_CLOUD_IMAGE_FAMILY
  write_metadata_if_set cloud_image GSE_CLOUD_IMAGE
  write_metadata_if_set cloud_image_id GSE_CLOUD_IMAGE_ID
  write_metadata_if_set cloud_image_self_link GSE_CLOUD_IMAGE_SELF_LINK
  write_metadata_if_set cloud_image_created_at GSE_CLOUD_IMAGE_CREATED_AT
  write_metadata_if_set benchmark_preset_id GSE_BENCHMARK_PRESET_ID
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
  if command -v dpkg-query >/dev/null 2>&1; then
    echo "jdk_packages_begin"
    dpkg-query -W -f='${binary:Package}=${Version}\n' 'openjdk-21-*' 2>/dev/null || true
    echo "jdk_packages_end"
  fi
} > "$run_dir/environment.txt" 2>&1

echo "Building the JMH uber-JAR..."
if [ "${GSE_PERF_SKIP_BUILD:-false}" = true ]; then
  if [ "$mode" != final-v34 ] \
      || [ "${GSE_V34_SUITE_PROFILE:-production}" != reduced-test ]; then
    echo 'GSE_PERF_SKIP_BUILD=true is restricted to local final-v34 reduced-test verification' >&2
    exit 2
  fi
  [ -f target/benchmarks.jar ] || {
    echo 'GSE_PERF_SKIP_BUILD=true requires target/benchmarks.jar' >&2
    exit 2
  }
  echo 'Build skipped for local reduced-test verification.' | tee "$run_dir/build.log"
else
  ./mvnw clean -Pjmh -DskipTests package 2>&1 | tee "$run_dir/build.log"
fi

read -r -a jvm_args <<< "$jvm_options"

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
  for group in "${thread_groups[@]}"; do
    label=${group/,/-}
    run_jmh "concurrent-latency-$label" \
      'V3ConcurrentMixedWorkloadBenchmark.mixed' \
      -p "documentCount=$concurrency_documents" \
      -tg "$group" -bm sample -tu us -prof gc
    run_jmh "concurrent-throughput-$label" \
      'V3ConcurrentMixedWorkloadBenchmark.mixed' \
      -p "documentCount=$concurrency_documents" \
      -tg "$group" -bm thrpt -tu s -prof gc
  done
}

run_ranked_v31() {
  run_jmh v31-phrase \
    'V31PhraseFeatureBenchmark.search' \
    -p documentCount=100000,1000000 \
    -p scenario=low-s0,high-s0,low-s1,high-s1,low-s2,high-s2,low-s4,high-s4,repeated,analyzer-gap,same-position \
    -bm avgt -tu ms -prof gc

  run_jmh v31-bool \
    'V31MinimumShouldMatchBenchmark.search' \
    -p documentCount=100000,1000000 \
    -p shouldWidth=4,16,64 \
    -p minimum=one,half,all \
    -p withMust=false,true \
    -bm avgt -tu ms -prof gc

  run_jmh v31-fuzzy \
    'V31FuzzyDictionaryBenchmark.traverse' \
    -p vocabularySize=100000,1000000 \
    -p scenario=short-exact,long-near,unicode-near,sparse-miss,dense-hit \
    -bm avgt -tu ms -prof gc

  run_jmh v31-text-build \
    'V31TextDictionaryBenchmark.build' \
    -p vocabularySize=100000,1000000 \
    -p mutationBatchSize=1 \
    -p transition=unchanged \
    -bm avgt -tu ms -prof gc

  run_jmh v31-text-publication \
    'V31TextDictionaryBenchmark.publish' \
    -p vocabularySize=100000,1000000 \
    -p mutationBatchSize=1,100 \
    -p transition=unchanged,added,removed \
    -bm avgt -tu ms -prof gc

  for group in "${thread_groups[@]}"; do
    label=${group/,/-}
    run_jmh "v31-concurrent-latency-$label" \
      'V31ConcurrentMixedWorkloadBenchmark.mixed' \
      -p "documentCount=$concurrency_documents" \
      -tg "$group" -bm sample -tu us -prof gc
    run_jmh "v31-concurrent-throughput-$label" \
      'V31ConcurrentMixedWorkloadBenchmark.mixed' \
      -p "documentCount=$concurrency_documents" \
      -tg "$group" -bm thrpt -tu s -prof gc
  done
}

run_final_v34() {
  suite_profile=${GSE_V34_SUITE_PROFILE:-production}
  case "$suite_profile" in
    production|reduced-test) ;;
    *) echo "GSE_V34_SUITE_PROFILE must be production or reduced-test" >&2; return 2 ;;
  esac

  if [ "$suite_profile" = production ]; then
    cold_documents=100000; cold_tokens=16; cold_batch_size=1000; cold_repeats=5
    cold_seed=34; cold_timeout=600
    extreme_documents=1000; extreme_tokens=64; extreme_seed=34
    burst_producers=1,4,16; burst_batch_sizes=1,100,1000
    burst_batches=4; burst_documents=64000; burst_readers=4
    burst_queue=32; burst_timeout=180
    long_seconds=${GSE_SOAK_SECONDS:-1800}; long_documents=10000; long_readers=6
    long_warmup=30; long_window=60; long_sample=1000; long_steady=25
    long_burst_every=60; long_burst_producers=4; long_burst_batch=100
    long_lifecycle=120; long_queue=1000
  else
    cold_documents=${GSE_V34_COLD_DOCUMENTS:-1000}
    cold_tokens=${GSE_V34_COLD_TOKENS:-8}
    cold_batch_size=${GSE_V34_COLD_BATCH_SIZE:-250}
    cold_repeats=${GSE_V34_COLD_REPEATS:-2}
    cold_seed=${GSE_V34_COLD_SEED:-34}; cold_timeout=60
    extreme_documents=${GSE_V34_EXTREME_DOCUMENTS:-100}
    extreme_tokens=${GSE_V34_EXTREME_TOKENS:-16}
    extreme_seed=${GSE_V34_EXTREME_SEED:-34}
    burst_producers=${GSE_V34_BURST_PRODUCERS:-1,4}
    burst_batch_sizes=${GSE_V34_BURST_BATCH_SIZES:-1,10}
    burst_batches=${GSE_V34_BURST_BATCHES_PER_PRODUCER:-2}
    burst_documents=${GSE_V34_BURST_DOCUMENTS:-1000}
    burst_readers=${GSE_V34_BURST_READERS:-2}
    burst_queue=${GSE_V34_BURST_QUEUE_CAPACITY:-8}; burst_timeout=60
    long_seconds=${GSE_SOAK_SECONDS:-6}
    long_documents=${GSE_V34_LONG_RUN_DOCUMENTS:-1000}
    long_readers=${GSE_V34_LONG_RUN_READERS:-6}
    long_warmup=${GSE_V34_LONG_RUN_WARMUP_SECONDS:-1}
    long_window=${GSE_V34_LONG_RUN_WINDOW_SECONDS:-2}
    long_sample=${GSE_V34_LONG_RUN_SAMPLE_MILLIS:-250}
    long_steady=${GSE_V34_LONG_RUN_STEADY_MILLIS:-20}
    long_burst_every=${GSE_V34_LONG_RUN_BURST_EVERY_SECONDS:-2}
    long_burst_producers=${GSE_V34_LONG_RUN_BURST_PRODUCERS:-4}
    long_burst_batch=${GSE_V34_LONG_RUN_BURST_BATCH_SIZE:-10}
    long_lifecycle=${GSE_V34_LONG_RUN_LIFECYCLE_EVERY_SECONDS:-2}
    long_queue=${GSE_V34_LONG_RUN_QUEUE_CAPACITY:-64}
  fi

  if [ "$suite_profile" = production ]; then
    for pair in \
      "GSE_V34_COLD_DOCUMENTS:${GSE_V34_COLD_DOCUMENTS:-100000}:100000" \
      "GSE_V34_COLD_TOKENS:${GSE_V34_COLD_TOKENS:-16}:16" \
      "GSE_V34_COLD_BATCH_SIZE:${GSE_V34_COLD_BATCH_SIZE:-1000}:1000" \
      "GSE_V34_COLD_REPEATS:${GSE_V34_COLD_REPEATS:-5}:5" \
      "GSE_V34_COLD_SEED:${GSE_V34_COLD_SEED:-34}:34" \
      "GSE_V34_EXTREME_DOCUMENTS:${GSE_V34_EXTREME_DOCUMENTS:-1000}:1000" \
      "GSE_V34_EXTREME_TOKENS:${GSE_V34_EXTREME_TOKENS:-64}:64" \
      "GSE_V34_EXTREME_SEED:${GSE_V34_EXTREME_SEED:-34}:34" \
      "GSE_V34_BURST_PRODUCERS:${GSE_V34_BURST_PRODUCERS:-1,4,16}:1,4,16" \
      "GSE_V34_BURST_BATCH_SIZES:${GSE_V34_BURST_BATCH_SIZES:-1,100,1000}:1,100,1000" \
      "GSE_V34_BURST_BATCHES_PER_PRODUCER:${GSE_V34_BURST_BATCHES_PER_PRODUCER:-4}:4" \
      "GSE_V34_BURST_DOCUMENTS:${GSE_V34_BURST_DOCUMENTS:-64000}:64000" \
      "GSE_V34_BURST_READERS:${GSE_V34_BURST_READERS:-4}:4" \
      "GSE_V34_BURST_QUEUE_CAPACITY:${GSE_V34_BURST_QUEUE_CAPACITY:-32}:32" \
      "GSE_V34_LONG_RUN_DOCUMENTS:${GSE_V34_LONG_RUN_DOCUMENTS:-10000}:10000" \
      "GSE_V34_LONG_RUN_READERS:${GSE_V34_LONG_RUN_READERS:-6}:6" \
      "GSE_V34_LONG_RUN_WARMUP_SECONDS:${GSE_V34_LONG_RUN_WARMUP_SECONDS:-30}:30" \
      "GSE_V34_LONG_RUN_WINDOW_SECONDS:${GSE_V34_LONG_RUN_WINDOW_SECONDS:-60}:60" \
      "GSE_V34_LONG_RUN_SAMPLE_MILLIS:${GSE_V34_LONG_RUN_SAMPLE_MILLIS:-1000}:1000" \
      "GSE_V34_LONG_RUN_STEADY_MILLIS:${GSE_V34_LONG_RUN_STEADY_MILLIS:-25}:25" \
      "GSE_V34_LONG_RUN_BURST_EVERY_SECONDS:${GSE_V34_LONG_RUN_BURST_EVERY_SECONDS:-60}:60" \
      "GSE_V34_LONG_RUN_BURST_PRODUCERS:${GSE_V34_LONG_RUN_BURST_PRODUCERS:-4}:4" \
      "GSE_V34_LONG_RUN_BURST_BATCH_SIZE:${GSE_V34_LONG_RUN_BURST_BATCH_SIZE:-100}:100" \
      "GSE_V34_LONG_RUN_LIFECYCLE_EVERY_SECONDS:${GSE_V34_LONG_RUN_LIFECYCLE_EVERY_SECONDS:-120}:120" \
      "GSE_V34_LONG_RUN_QUEUE_CAPACITY:${GSE_V34_LONG_RUN_QUEUE_CAPACITY:-1000}:1000"; do
      IFS=: read -r name supplied expected <<< "$pair"
      [ "$supplied" = "$expected" ] || {
        echo "$name conflicts with v3.4-final-in-memory-v1 (expected $expected)" >&2
        return 2
      }
    done
    case "$long_seconds" in 1800|7200) ;; *)
      echo "GSE_SOAK_SECONDS must be 1800 or 7200 for final-v34" >&2; return 2 ;;
    esac
  fi

  suite_dir="$run_dir/v34-final"
  mkdir -p "$suite_dir/long-run"
  cat > "$suite_dir/suite-config.properties" <<EOF
status=CONFIGURED
schema=v3.4-final-in-memory-suite-v1
profile=$suite_profile
cold_documents=$cold_documents
cold_tokens=$cold_tokens
cold_batch_size=$cold_batch_size
cold_repeats=$cold_repeats
cold_seed=$cold_seed
extreme_documents=$extreme_documents
extreme_tokens=$extreme_tokens
extreme_seed=$extreme_seed
burst_producers=$burst_producers
burst_batch_sizes=$burst_batch_sizes
burst_batches_per_producer=$burst_batches
burst_documents=$burst_documents
burst_readers=$burst_readers
burst_queue_capacity=$burst_queue
long_run_seconds=$long_seconds
long_run_documents=$long_documents
long_run_readers=$long_readers
long_run_warmup_seconds=$long_warmup
long_run_window_seconds=$long_window
long_run_sample_millis=$long_sample
long_run_top_k=10
long_run_steady_millis=$long_steady
long_run_burst_every_seconds=$long_burst_every
long_run_burst_producers=$long_burst_producers
long_run_burst_batch_size=$long_burst_batch
long_run_lifecycle_every_seconds=$long_lifecycle
long_run_queue_capacity=$long_queue
EOF

  JAVA_TOOL_OPTIONS="$jvm_options" java -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.benchmark.jmh.V34ColdBuildProcessRunner \
    --documents="$cold_documents" --tokens="$cold_tokens" \
    --batch-size="$cold_batch_size" --repeats="$cold_repeats" \
    --seed="$cold_seed" --timeout-seconds="$cold_timeout" \
    2>&1 | tee "$suite_dir/cold.log"

  java "${jvm_args[@]}" -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.benchmark.jmh.V34ExtremeCorpusProbe \
    --documents="$extreme_documents" --tokens="$extreme_tokens" \
    --seed="$extreme_seed" --axis=all 2>&1 | tee "$suite_dir/extreme.log"

  java "${jvm_args[@]}" -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.benchmark.jmh.V34BurstRecoveryProbe \
    --producers="$burst_producers" --batch-sizes="$burst_batch_sizes" \
    --batches-per-producer="$burst_batches" --documents="$burst_documents" \
    --readers="$burst_readers" --queue-capacity="$burst_queue" \
    --timeout-seconds="$burst_timeout" 2>&1 | tee "$suite_dir/burst.log"

  long_kind=local-calibration
  if [ "$suite_profile" = production ]; then long_kind=final-v34-cloud; fi
  java "${jvm_args[@]}" -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.benchmark.jmh.V34LongRunCalibration \
    --output="$suite_dir/long-run" --documents="$long_documents" \
    --readers="$long_readers" --seconds="$long_seconds" \
    --warmup-seconds="$long_warmup" --window-seconds="$long_window" \
    --sample-millis="$long_sample" --top-k=10 --steady-millis="$long_steady" \
    --burst-every-seconds="$long_burst_every" \
    --burst-producers="$long_burst_producers" \
    --burst-batch-size="$long_burst_batch" \
    --lifecycle-every-seconds="$long_lifecycle" \
    --queue-capacity="$long_queue" --source-commit="$(git rev-parse HEAD)" \
    --tree-state="$(if [ -z "$(git status --short)" ]; then echo clean; else echo dirty; fi)" \
    --run-kind="$long_kind" 2>&1 | tee "$suite_dir/long-run.log"

  printf 'status=PASS\nprofile=%s\nlong_run_seconds=%s\n' \
    "$suite_profile" "$long_seconds" > "$suite_dir/suite-summary.properties"
}

run_soak() {
  if [ "$mode" = stabilized-investigation ]; then
    soak_seconds=$expected_seconds
  else
    soak_seconds=${GSE_SOAK_SECONDS:-1800}
  fi
  soak_readers=${GSE_SOAK_READERS:-16}
  soak_documents=${GSE_SOAK_DOCUMENTS:-100000}
  echo "Running ${soak_seconds}s production soak..."
  mkdir -p "$run_dir/soak"
  soak_jvm_args=("${jvm_args[@]}")
  if [ "$soak_profile" = jfr ] && [ "$mode" = investigation ]; then
    soak_jvm_args+=("-XX:StartFlightRecording=filename=$run_dir/soak/profile.jfr,settings=profile,disk=true,dumponexit=true,maxsize=512m")
  fi
  soak_command=(java "${soak_jvm_args[@]}" -cp target/benchmarks.jar
    io.github.patricklfdm.generalsearch.benchmark.jmh.V3ProductionSoak \
    "--output=$run_dir/soak" \
    "--seconds=$soak_seconds" \
    "--readers=$soak_readers" \
    "--writers=$soak_writers" \
    "--documents=$soak_documents" \
    --sample-seconds=1 \
    --top-k=10 \
    --corpus-profile=zipf-en-medium-4 \
    "--index-cycles=$soak_index_cycles" \
    "--update-mode=$soak_update_mode" \
    "--per-query-metrics=$soak_per_query_metrics")
  if [ "$mode" = stabilized-investigation ]; then
    soak_command+=(
      "--stabilization-purpose=$stabilization_purpose"
      "--stabilization-seconds=$stabilization_seconds"
      "--stabilization-window-seconds=$stabilization_window_seconds"
      "--allow-reduced-stabilization-test=$allow_reduced_stabilization_test")
    if [ "$soak_profile" = jfr ]; then
      soak_command+=("--jfr-output=$run_dir/soak/profile.jfr")
    fi
  fi
  printf 'soak_java_command=' >> "$run_dir/metadata.txt"
  printf '%q ' "${soak_command[@]}" >> "$run_dir/metadata.txt"
  printf '\n' >> "$run_dir/metadata.txt"
  set +e
  "${soak_command[@]}" 2>&1 | tee "$run_dir/soak.log"
  soak_exit_code=${PIPESTATUS[0]}
  set -e

  if [ "$mode" = stabilized-investigation ]; then
    stabilization_file="$run_dir/soak/soak-stabilization-analysis.properties"
    stabilization_temporary="$stabilization_file.tmp.$$"
    if scripts/analyze-v3-soak-stabilization.sh "$run_dir/soak" \
        > "$stabilization_temporary"; then
      mv "$stabilization_temporary" "$stabilization_file"
    else
      rm -f -- "$stabilization_temporary"
      return 1
    fi
    if [ "$soak_exit_code" -ne 0 ]; then
      return "$soak_exit_code"
    fi
  elif [ "$soak_exit_code" -ne 0 ]; then
    return "$soak_exit_code"
  fi

  if [ "$soak_profile" = jfr ]; then
    printf 'jfr_summary_command=jfr summary %q\n' \
      "$run_dir/soak/profile.jfr" >> "$run_dir/metadata.txt"
    [ -s "$run_dir/soak/profile.jfr" ] \
      || { echo "JFR profile was not created" >&2; return 1; }
    jfr summary "$run_dir/soak/profile.jfr" > "$run_dir/soak/profile-summary.txt"
    [ -s "$run_dir/soak/profile-summary.txt" ] \
      || { echo "JFR summary was not created" >&2; return 1; }
  fi

  analysis_file="$run_dir/soak/soak-analysis.properties"
  analysis_temporary="$analysis_file.tmp.$$"
  if scripts/analyze-v3-soak.sh "$run_dir/soak" > "$analysis_temporary"; then
    mv "$analysis_temporary" "$analysis_file"
  else
    rm -f -- "$analysis_temporary"
    return 1
  fi

  if [ "$mode" = investigation ] || [ "$mode" = stabilized-investigation ]; then
    investigation_file="$run_dir/soak/soak-investigation-analysis.properties"
    investigation_temporary="$investigation_file.tmp.$$"
    if scripts/analyze-v3-soak-investigation.sh "$run_dir/soak" \
        > "$investigation_temporary"; then
      mv "$investigation_temporary" "$investigation_file"
    else
      rm -f -- "$investigation_temporary"
      return 1
    fi
  fi
}

case "$mode" in
  quick|full) run_benchmarks ;;
  concurrency) run_concurrency ;;
  soak) run_soak ;;
  investigation) run_soak ;;
  stabilized-investigation) run_soak ;;
  ranked-v31) run_ranked_v31 ;;
  final-v34) run_final_v34 ;;
  all)
    run_benchmarks
    run_soak
    ;;
esac
