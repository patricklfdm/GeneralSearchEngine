#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

mode=${1:-quick}
case "$mode" in
  quick|full|concurrency|soak|investigation|all) ;;
  *)
    echo "usage: $0 [quick|full|concurrency|soak|investigation|all]" >&2
    exit 2
    ;;
esac

investigation_cell=${GSE_SOAK_INVESTIGATION_CELL:-}
soak_profile=${GSE_SOAK_PROFILE:-none}
soak_update_mode=revision
soak_per_query_metrics=false
soak_writers=${GSE_SOAK_WRITERS:-1}
soak_index_cycles=${GSE_SOAK_INDEX_CYCLES:-true}

if [ "$mode" = investigation ]; then
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
else
  [ -z "$investigation_cell" ] \
    || { echo "GSE_SOAK_INVESTIGATION_CELL is only valid in investigation mode" >&2; exit 2; }
  [ "$soak_profile" = none ] \
    || { echo "GSE_SOAK_PROFILE is only valid in investigation mode" >&2; exit 2; }
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
if { [ "$mode" = soak ] || [ "$mode" = investigation ] || [ "$mode" = all ]; } \
    && [ ! -x scripts/analyze-v3-soak.sh ]; then
  echo "Missing executable soak analyzer: scripts/analyze-v3-soak.sh" >&2
  exit 2
fi
if [ "$mode" = investigation ] && [ ! -x scripts/analyze-v3-soak-investigation.sh ]; then
  echo "Missing executable investigation analyzer: scripts/analyze-v3-soak-investigation.sh" >&2
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

concurrency_documents=${GSE_CONCURRENCY_DOCUMENTS:-100000}
if [[ ! "$concurrency_documents" =~ ^[1-9][0-9]*$ ]]; then
  echo "GSE_CONCURRENCY_DOCUMENTS must be a positive integer" >&2
  exit 2
fi
if [ -n "${GSE_CONCURRENCY_THREAD_GROUPS:-}" ]; then
  read -r -a thread_groups <<< "$GSE_CONCURRENCY_THREAD_GROUPS"
elif [ "$mode" = "quick" ]; then
  thread_groups=("4,1")
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

{
  echo "started_utc=$timestamp"
  echo "mode=$mode"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "git_branch=$(git branch --show-current)"
  echo "logical_cpus=$(getconf _NPROCESSORS_ONLN)"
  echo "java_home=${JAVA_HOME:-unset}"
  echo "jvm_options=$jvm_options"
  echo "jmh_forks=$forks"
  echo "jmh_warmups=$warmups"
  echo "jmh_iterations=$iterations"
  echo "jmh_duration=$duration"
  echo "concurrency_documents=$concurrency_documents"
  printf 'concurrency_thread_groups=%s\n' "${thread_groups[*]}"
  echo "soak_index_cycles=$soak_index_cycles"
  echo "soak_investigation_cell=${investigation_cell:-none}"
  echo "soak_update_mode=$soak_update_mode"
  echo "soak_per_query_metrics=$soak_per_query_metrics"
  echo "soak_profile=$soak_profile"
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
./mvnw clean -Pjmh -DskipTests package 2>&1 | tee "$run_dir/build.log"

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

run_soak() {
  soak_seconds=${GSE_SOAK_SECONDS:-1800}
  soak_readers=${GSE_SOAK_READERS:-16}
  soak_documents=${GSE_SOAK_DOCUMENTS:-100000}
  echo "Running ${soak_seconds}s production soak..."
  mkdir -p "$run_dir/soak"
  soak_jvm_args=("${jvm_args[@]}")
  if [ "$soak_profile" = jfr ]; then
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
  printf 'soak_java_command=' >> "$run_dir/metadata.txt"
  printf '%q ' "${soak_command[@]}" >> "$run_dir/metadata.txt"
  printf '\n' >> "$run_dir/metadata.txt"
  "${soak_command[@]}" 2>&1 | tee "$run_dir/soak.log"

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

  if [ "$mode" = investigation ]; then
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
  all)
    run_benchmarks
    run_soak
    ;;
esac
