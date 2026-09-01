#!/usr/bin/env bash
set -euo pipefail

readonly EXIT_CONFIG=2
readonly EXIT_INCOMPATIBLE_SET=83

usage() {
  cat <<'EOF'
Usage:
  ./run-cloud-benchmark-set.sh [--dry-run] --evidence-profile PROFILE --repeats N [--preset ID] [--confirm-paid-run] MODE
  ./run-cloud-benchmark-set.sh --resume WORKSPACE [--confirm-paid-run]
  ./run-cloud-benchmark-set.sh --replace WORKSPACE --slot N --reason TEXT --confirm-no-score-selection --confirm-paid-run

Profiles:
  canonical   3..10 independent Standard VM runs with a frozen production preset
  experiment  1..10 independent V1 runs; not baseline eligible

Canonical modes:
  full  concurrency  soak  ranked-v31  final-v34  all

Dry run performs only read-only repository/GCP validation and creates no workspace or VM.
Every command that can create a VM requires --confirm-paid-run.
EOF
}

fail() {
  code=$1
  shift
  echo "ERROR: $*" >&2
  exit "$code"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$EXIT_CONFIG" "Required command not found: $1"
}

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$repo_root"
analyzer="$repo_root/scripts/cloud/benchmark_v2.py"

dry_run=false
confirm_paid=false
confirm_no_selection=false
profile=
repeats=
preset_id=
resume_workspace=
replace_workspace=
slot=
reason=
mode=

while [ "$#" -gt 0 ]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --dry-run) dry_run=true; shift ;;
    --confirm-paid-run) confirm_paid=true; shift ;;
    --confirm-no-score-selection) confirm_no_selection=true; shift ;;
    --evidence-profile) [ "$#" -ge 2 ] || fail "$EXIT_CONFIG" '--evidence-profile requires a value'; profile=$2; shift 2 ;;
    --repeats) [ "$#" -ge 2 ] || fail "$EXIT_CONFIG" '--repeats requires a value'; repeats=$2; shift 2 ;;
    --preset) [ "$#" -ge 2 ] || fail "$EXIT_CONFIG" '--preset requires a value'; preset_id=$2; shift 2 ;;
    --resume) [ "$#" -ge 2 ] || fail "$EXIT_CONFIG" '--resume requires a workspace'; resume_workspace=$2; shift 2 ;;
    --replace) [ "$#" -ge 2 ] || fail "$EXIT_CONFIG" '--replace requires a workspace'; replace_workspace=$2; shift 2 ;;
    --slot) [ "$#" -ge 2 ] || fail "$EXIT_CONFIG" '--slot requires a value'; slot=$2; shift 2 ;;
    --reason) [ "$#" -ge 2 ] || fail "$EXIT_CONFIG" '--reason requires a value'; reason=$2; shift 2 ;;
    --*) fail "$EXIT_CONFIG" "Unknown option: $1" ;;
    *) [ -z "$mode" ] || fail "$EXIT_CONFIG" 'Only one benchmark mode may be supplied'; mode=$1; shift ;;
  esac
done

require_command git
require_command gcloud
require_command python3
require_command realpath
require_command tee
[ -f "$analyzer" ] || fail "$EXIT_CONFIG" "Missing analyzer: $analyzer"

form=new
if [ -n "$resume_workspace" ]; then form=resume; fi
if [ -n "$replace_workspace" ]; then
  [ "$form" = new ] || fail "$EXIT_CONFIG" '--resume and --replace are mutually exclusive'
  form=replace
fi
if [ "$form" != new ]; then
  [ "$dry_run" = false ] || fail "$EXIT_CONFIG" '--dry-run is only valid for a new set'
  [ -z "$profile$repeats$preset_id$mode" ] \
    || fail "$EXIT_CONFIG" 'Resume/replace reads profile, repeats, preset, and mode from the immutable plan'
else
  [ -n "$profile" ] && [ -n "$repeats" ] && [ -n "$mode" ] \
    || fail "$EXIT_CONFIG" 'A new set requires --evidence-profile, --repeats, and MODE'
  [[ "$repeats" =~ ^[1-9][0-9]*$ ]] || fail "$EXIT_CONFIG" '--repeats must be a positive integer'
  if [ "$profile" = canonical ]; then
    if [ "$mode" = ranked-v31 ]; then
      expected_preset=v3.1-ranked-v1
    elif [ "$mode" = final-v34 ]; then
      expected_preset=v3.4-final-in-memory-v1
    else
      expected_preset="v3-production-${mode}-v1"
    fi
    if [ -z "$preset_id" ]; then preset_id=$expected_preset; fi
    [ "$preset_id" = "$expected_preset" ] \
      || fail "$EXIT_CONFIG" "Canonical mode $mode requires preset $expected_preset"
  fi
fi
if [ "$form" = replace ]; then
  [ -n "$slot" ] && [[ "$slot" =~ ^[1-9][0-9]*$ ]] \
    || fail "$EXIT_CONFIG" '--replace requires a positive --slot'
  [ -n "$reason" ] || fail "$EXIT_CONFIG" '--replace requires --reason'
  [ "$confirm_no_selection" = true ] \
    || fail "$EXIT_CONFIG" '--replace requires --confirm-no-score-selection'
  [ "$confirm_paid" = true ] || fail "$EXIT_CONFIG" '--replace requires --confirm-paid-run'
elif [ -n "$slot$reason" ] || [ "$confirm_no_selection" = true ]; then
  fail "$EXIT_CONFIG" '--slot, --reason, and --confirm-no-score-selection are replacement-only'
fi

set_value() {
  python3 "$analyzer" set-value "$workspace" "$1"
}

require_expected_override() {
  variable=$1
  expected=$2
  if [ -n "${!variable+x}" ] && [ "${!variable}" != "$expected" ]; then
    fail "$EXIT_CONFIG" "$variable conflicts with preset $preset_id (expected: $expected)"
  fi
}

configure_preset() {
  if [ -n "${GSE_BENCHMARK_PRESET_ID+x}" ] \
      && [ "$GSE_BENCHMARK_PRESET_ID" != "$preset_id" ]; then
    fail "$EXIT_CONFIG" "GSE_BENCHMARK_PRESET_ID conflicts with the immutable set preset"
  fi
  run_environment=(
    "GSE_CLOUD_REPO_URL=$repository"
    "GSE_GCP_PROJECT=$project"
    "GSE_GCP_ZONE=$zone"
    "GSE_CLOUD_MACHINE_TYPE=$machine_type"
    "GSE_CLOUD_PROVISIONING=$provisioning"
    "GSE_CLOUD_IMAGE_PROJECT=$image_project"
    "GSE_CLOUD_IMAGE_FAMILY=$image_family"
    "GSE_CLOUD_IMAGE=$resolved_image"
    "GSE_CLOUD_BOOT_DISK_SIZE=$boot_disk_size"
    "GSE_CLOUD_BOOT_DISK_TYPE=$boot_disk_type"
    "GSE_CLOUD_USE_IAP=$use_iap"
    "GSE_CLOUD_EXTERNAL_IP=$external_ip"
    "GSE_PERF_JVM_OPTIONS=$jvm_options"
  )
  [ -z "$network" ] || run_environment+=("GSE_GCP_NETWORK=$network")
  [ -z "$subnet" ] || run_environment+=("GSE_GCP_SUBNET=$subnet")
  [ -z "$max_run_duration" ] || run_environment+=("GSE_CLOUD_MAX_RUN_DURATION=$max_run_duration")
  [ -z "$preset_id" ] || run_environment+=("GSE_BENCHMARK_PRESET_ID=$preset_id")
  case "$preset_id" in
    v3-production-full-v1)
      require_expected_override GSE_JMH_FORKS 2
      require_expected_override GSE_JMH_WARMUPS 3
      require_expected_override GSE_JMH_ITERATIONS 5
      require_expected_override GSE_JMH_DURATION 1s
      require_expected_override GSE_CONCURRENCY_DOCUMENTS 100000
      require_expected_override GSE_CONCURRENCY_THREAD_GROUPS '1,1 4,1 16,1'
      run_environment+=(GSE_JMH_FORKS=2 GSE_JMH_WARMUPS=3 GSE_JMH_ITERATIONS=5 GSE_JMH_DURATION=1s
        GSE_CONCURRENCY_DOCUMENTS=100000 'GSE_CONCURRENCY_THREAD_GROUPS=1,1 4,1 16,1')
      ;;
    v3-production-concurrency-v1)
      require_expected_override GSE_JMH_FORKS 2
      require_expected_override GSE_JMH_WARMUPS 3
      require_expected_override GSE_JMH_ITERATIONS 5
      require_expected_override GSE_JMH_DURATION 1s
      require_expected_override GSE_CONCURRENCY_DOCUMENTS 100000
      require_expected_override GSE_CONCURRENCY_THREAD_GROUPS '1,1 4,1 8,1 16,1 24,1 30,1'
      run_environment+=(GSE_JMH_FORKS=2 GSE_JMH_WARMUPS=3 GSE_JMH_ITERATIONS=5 GSE_JMH_DURATION=1s
        GSE_CONCURRENCY_DOCUMENTS=100000 'GSE_CONCURRENCY_THREAD_GROUPS=1,1 4,1 8,1 16,1 24,1 30,1')
      ;;
    v3-production-soak-v1)
      require_expected_override GSE_SOAK_SECONDS 1800
      require_expected_override GSE_SOAK_READERS 16
      require_expected_override GSE_SOAK_WRITERS 1
      require_expected_override GSE_SOAK_DOCUMENTS 100000
      require_expected_override GSE_SOAK_INDEX_CYCLES true
      run_environment+=(GSE_SOAK_SECONDS=1800 GSE_SOAK_READERS=16 GSE_SOAK_WRITERS=1
        GSE_SOAK_DOCUMENTS=100000 GSE_SOAK_INDEX_CYCLES=true)
      ;;
    v3-production-all-v1)
      require_expected_override GSE_JMH_FORKS 2
      require_expected_override GSE_JMH_WARMUPS 3
      require_expected_override GSE_JMH_ITERATIONS 5
      require_expected_override GSE_JMH_DURATION 1s
      require_expected_override GSE_CONCURRENCY_DOCUMENTS 100000
      require_expected_override GSE_CONCURRENCY_THREAD_GROUPS '1,1 4,1 16,1'
      require_expected_override GSE_SOAK_SECONDS 1800
      require_expected_override GSE_SOAK_READERS 16
      require_expected_override GSE_SOAK_WRITERS 1
      require_expected_override GSE_SOAK_DOCUMENTS 100000
      require_expected_override GSE_SOAK_INDEX_CYCLES true
      run_environment+=(GSE_JMH_FORKS=2 GSE_JMH_WARMUPS=3 GSE_JMH_ITERATIONS=5 GSE_JMH_DURATION=1s
        GSE_CONCURRENCY_DOCUMENTS=100000 'GSE_CONCURRENCY_THREAD_GROUPS=1,1 4,1 16,1'
        GSE_SOAK_SECONDS=1800 GSE_SOAK_READERS=16 GSE_SOAK_WRITERS=1
        GSE_SOAK_DOCUMENTS=100000 GSE_SOAK_INDEX_CYCLES=true)
      ;;
    v3.1-ranked-v1)
      require_expected_override GSE_CLOUD_MAX_RUN_DURATION 3600s
      require_expected_override GSE_PERF_JVM_OPTIONS '-Xms32g -Xmx64g'
      require_expected_override GSE_JMH_FORKS 2
      require_expected_override GSE_JMH_WARMUPS 3
      require_expected_override GSE_JMH_ITERATIONS 5
      require_expected_override GSE_JMH_DURATION 1s
      require_expected_override GSE_CONCURRENCY_DOCUMENTS 1000000
      require_expected_override GSE_CONCURRENCY_THREAD_GROUPS '16,1'
      [ "$max_run_duration" = 3600s ] \
        || fail "$EXIT_CONFIG" \
          "GSE_CLOUD_MAX_RUN_DURATION conflicts with preset $preset_id (expected: 3600s)"
      [ "$jvm_options" = '-Xms32g -Xmx64g' ] \
        || fail "$EXIT_CONFIG" \
          "GSE_PERF_JVM_OPTIONS conflicts with preset $preset_id (expected: -Xms32g -Xmx64g)"
      run_environment+=(GSE_JMH_FORKS=2 GSE_JMH_WARMUPS=3 GSE_JMH_ITERATIONS=5 GSE_JMH_DURATION=1s
        GSE_CONCURRENCY_DOCUMENTS=1000000 'GSE_CONCURRENCY_THREAD_GROUPS=16,1')
      ;;
    v3.4-final-in-memory-v1)
      require_expected_override GSE_CLOUD_MAX_RUN_DURATION 10800s
      require_expected_override GSE_PERF_JVM_OPTIONS '-Xms16g -Xmx16g -XX:+UseG1GC'
      require_expected_override GSE_V34_SUITE_PROFILE production
      require_expected_override GSE_V34_COLD_DOCUMENTS 100000
      require_expected_override GSE_V34_COLD_TOKENS 16
      require_expected_override GSE_V34_COLD_BATCH_SIZE 1000
      require_expected_override GSE_V34_COLD_REPEATS 5
      require_expected_override GSE_V34_COLD_SEED 34
      require_expected_override GSE_V34_EXTREME_DOCUMENTS 1000
      require_expected_override GSE_V34_EXTREME_TOKENS 64
      require_expected_override GSE_V34_EXTREME_SEED 34
      require_expected_override GSE_V34_BURST_PRODUCERS '1,4,16'
      require_expected_override GSE_V34_BURST_BATCH_SIZES '1,100,1000'
      require_expected_override GSE_V34_BURST_BATCHES_PER_PRODUCER 4
      require_expected_override GSE_V34_BURST_DOCUMENTS 64000
      require_expected_override GSE_V34_BURST_READERS 4
      require_expected_override GSE_V34_BURST_QUEUE_CAPACITY 32
      require_expected_override GSE_V34_LONG_RUN_DOCUMENTS 10000
      require_expected_override GSE_V34_LONG_RUN_READERS 6
      require_expected_override GSE_V34_LONG_RUN_WARMUP_SECONDS 30
      require_expected_override GSE_V34_LONG_RUN_WINDOW_SECONDS 60
      require_expected_override GSE_V34_LONG_RUN_SAMPLE_MILLIS 1000
      require_expected_override GSE_V34_LONG_RUN_STEADY_MILLIS 25
      require_expected_override GSE_V34_LONG_RUN_BURST_EVERY_SECONDS 60
      require_expected_override GSE_V34_LONG_RUN_BURST_PRODUCERS 4
      require_expected_override GSE_V34_LONG_RUN_BURST_BATCH_SIZE 100
      require_expected_override GSE_V34_LONG_RUN_LIFECYCLE_EVERY_SECONDS 120
      require_expected_override GSE_V34_LONG_RUN_QUEUE_CAPACITY 1000
      case "${GSE_SOAK_SECONDS:-1800}" in 1800|7200) ;;
        *) fail "$EXIT_CONFIG" 'GSE_SOAK_SECONDS must be 1800 or 7200 for final-v34' ;;
      esac
      [ "$max_run_duration" = 10800s ] \
        || fail "$EXIT_CONFIG" \
          "GSE_CLOUD_MAX_RUN_DURATION conflicts with preset $preset_id (expected: 10800s)"
      [ "$jvm_options" = '-Xms16g -Xmx16g -XX:+UseG1GC' ] \
        || fail "$EXIT_CONFIG" \
          "GSE_PERF_JVM_OPTIONS conflicts with preset $preset_id (expected: -Xms16g -Xmx16g -XX:+UseG1GC)"
      run_environment+=(
        GSE_V34_SUITE_PROFILE=production GSE_V34_COLD_DOCUMENTS=100000
        GSE_V34_COLD_TOKENS=16 GSE_V34_COLD_BATCH_SIZE=1000 GSE_V34_COLD_REPEATS=5
        GSE_V34_COLD_SEED=34 GSE_V34_EXTREME_DOCUMENTS=1000
        GSE_V34_EXTREME_TOKENS=64 GSE_V34_EXTREME_SEED=34
        GSE_V34_BURST_PRODUCERS=1,4,16 GSE_V34_BURST_BATCH_SIZES=1,100,1000
        GSE_V34_BURST_BATCHES_PER_PRODUCER=4 GSE_V34_BURST_DOCUMENTS=64000
        GSE_V34_BURST_READERS=4 GSE_V34_BURST_QUEUE_CAPACITY=32
        GSE_V34_LONG_RUN_DOCUMENTS=10000 GSE_V34_LONG_RUN_READERS=6
        GSE_V34_LONG_RUN_WARMUP_SECONDS=30 GSE_V34_LONG_RUN_WINDOW_SECONDS=60
        GSE_V34_LONG_RUN_SAMPLE_MILLIS=1000 GSE_V34_LONG_RUN_STEADY_MILLIS=25
        GSE_V34_LONG_RUN_BURST_EVERY_SECONDS=60 GSE_V34_LONG_RUN_BURST_PRODUCERS=4
        GSE_V34_LONG_RUN_BURST_BATCH_SIZE=100 GSE_V34_LONG_RUN_LIFECYCLE_EVERY_SECONDS=120
        GSE_V34_LONG_RUN_QUEUE_CAPACITY=1000
        "GSE_SOAK_SECONDS=${GSE_SOAK_SECONDS:-1800}")
      ;;
  esac
}

load_plan() {
  workspace=$(realpath "$1")
  [ -d "$workspace" ] || fail "$EXIT_CONFIG" "Set workspace does not exist: $workspace"
  profile=$(set_value plan.evidenceProfile)
  repeats=$(set_value plan.repeats)
  mode=$(set_value plan.mode)
  preset_id=$(set_value plan.presetId)
  repository=$(set_value plan.source.repository)
  commit=$(set_value plan.source.commit)
  project=$(set_value plan.controls.project)
  zone=$(set_value plan.controls.zone)
  machine_type=$(set_value plan.controls.machineType)
  provisioning=$(set_value plan.controls.provisioning)
  image_project=$(set_value plan.controls.imageProject)
  image_family=$(set_value plan.controls.imageFamily)
  resolved_image=$(set_value plan.controls.resolvedImage)
  boot_disk_size=$(set_value plan.controls.bootDiskSize)
  boot_disk_type=$(set_value plan.controls.bootDiskType)
  network=$(set_value plan.controls.network)
  subnet=$(set_value plan.controls.subnet)
  use_iap=$(set_value plan.controls.useIap)
  external_ip=$(set_value plan.controls.externalIp)
  jvm_options=$(set_value plan.controls.jvmOptions)
  max_run_duration=$(set_value plan.controls.maxRunDuration)
  [ "$(git rev-parse HEAD)" = "$commit" ] \
    || fail "$EXIT_CONFIG" "Workspace targets commit $commit; check it out before resuming"
  configure_preset
}

if [ "$form" = new ]; then
  repository=${GSE_CLOUD_REPO_URL:-https://github.com/patricklfdm/GeneralSearchEngine.git}
  commit=$(git rev-parse HEAD)
  [ "$(git status --porcelain --untracked-files=normal)" = "" ] \
    || fail "$EXIT_CONFIG" 'Working tree is dirty; commit before creating a benchmark set'
  project=${GSE_GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}
  zone=${GSE_GCP_ZONE:-$(gcloud config get-value compute/zone 2>/dev/null || true)}
  [ -n "$project" ] && [ "$project" != '(unset)' ] || fail "$EXIT_CONFIG" 'Set GSE_GCP_PROJECT'
  [ -n "$zone" ] && [ "$zone" != '(unset)' ] || fail "$EXIT_CONFIG" 'Set GSE_GCP_ZONE'
  machine_type=${GSE_CLOUD_MACHINE_TYPE:-c3d-standard-30}
  provisioning=${GSE_CLOUD_PROVISIONING:-spot}
  if [ "$profile" = canonical ]; then
    [ "$provisioning" = standard ] \
      || fail "$EXIT_CONFIG" 'Canonical sets require GSE_CLOUD_PROVISIONING=standard'
  fi
  image_project=${GSE_CLOUD_IMAGE_PROJECT:-ubuntu-os-cloud}
  image_family=${GSE_CLOUD_IMAGE_FAMILY:-ubuntu-2404-lts-amd64}
  requested_image=${GSE_CLOUD_IMAGE:-}
  if [ -n "$requested_image" ]; then
    image_description=$(gcloud compute images describe "$requested_image" --project="$image_project" \
      --format='value(name,id,selfLink,creationTimestamp)')
  else
    image_description=$(gcloud compute images describe-from-family "$image_family" --project="$image_project" \
      --format='value(name,id,selfLink,creationTimestamp)')
  fi
  IFS=$'\t' read -r resolved_image resolved_image_id resolved_image_self_link resolved_image_created_at <<< "$image_description"
  [ -n "$resolved_image" ] && [ -n "$resolved_image_id" ] && [ -n "$resolved_image_self_link" ] \
    && [ -n "$resolved_image_created_at" ] || fail "$EXIT_CONFIG" 'Image resolution returned incomplete identity'
  case "$mode" in
    ranked-v31) default_jvm_options='-Xms32g -Xmx64g' ;;
    final-v34) default_jvm_options='-Xms16g -Xmx16g -XX:+UseG1GC' ;;
    *) default_jvm_options='-Xms8g -Xmx16g' ;;
  esac
  jvm_options=${GSE_PERF_JVM_OPTIONS:-$default_jvm_options}
  boot_disk_size=${GSE_CLOUD_BOOT_DISK_SIZE:-100GB}
  boot_disk_type=${GSE_CLOUD_BOOT_DISK_TYPE:-pd-balanced}
  network=${GSE_GCP_NETWORK:-}
  subnet=${GSE_GCP_SUBNET:-}
  if [ -z "$network" ] && [ -z "$subnet" ]; then network=default; fi
  use_iap=${GSE_CLOUD_USE_IAP:-false}
  external_ip=${GSE_CLOUD_EXTERNAL_IP:-true}
  if [ -n "${GSE_CLOUD_MAX_RUN_DURATION:-}" ]; then
    max_run_duration=$GSE_CLOUD_MAX_RUN_DURATION
  else
    case "$mode" in
      quick) max_run_duration=7200s ;;
      full) max_run_duration=43200s ;;
      concurrency) max_run_duration=28800s ;;
      ranked-v31) max_run_duration=3600s ;;
      final-v34) max_run_duration=10800s ;;
      soak|investigation) max_run_duration=$((${GSE_SOAK_SECONDS:-1800} + 7200))s ;;
      stabilized-investigation)
        case "${GSE_SOAK_STABILIZATION_PURPOSE:-}" in
          confirmation) max_run_duration=9300s ;;
          *) max_run_duration=8100s ;;
        esac
        ;;
      all) max_run_duration=86400s ;;
    esac
  fi
  configure_preset
  plan_arguments=(
    --evidence-profile "$profile" --repeats "$repeats" --mode "$mode"
    --repository "$repository" --commit "$commit"
    --control "project=$project" --control "zone=$zone" --control "machineType=$machine_type"
    --control "provisioning=$provisioning" --control "imageProject=$image_project"
    --control "imageFamily=$image_family" --control "resolvedImage=$resolved_image"
    --control "resolvedImageId=$resolved_image_id" --control "resolvedImageSelfLink=$resolved_image_self_link"
    --control "resolvedImageCreatedAt=$resolved_image_created_at" --control "jvmOptions=$jvm_options"
    --control "bootDiskSize=$boot_disk_size" --control "bootDiskType=$boot_disk_type"
    --control "network=$network" --control "subnet=$subnet" --control "useIap=$use_iap"
    --control "externalIp=$external_ip" --control "maxRunDuration=$max_run_duration"
  )
  [ -z "$preset_id" ] || plan_arguments+=(--preset-id "$preset_id")
  python3 "$analyzer" set-validate "${plan_arguments[@]}"
  env "${run_environment[@]}" "$repo_root/run-cloud-benchmark.sh" --dry-run "$mode"
  printf '%s\n' \
    "Set evidence profile: $profile" \
    "Independent slots:   $repeats" \
    "Preset:              ${preset_id:-none}" \
    "Exact image:         $resolved_image ($resolved_image_id)" \
    "Worst-case VMs:      $repeats" \
    "Execution:           sequential; cleanup after every V1 attempt"
  if [ "$mode" = final-v34 ]; then
    case "$machine_type" in
      c3d-standard-30) final_vcpu_count=30 ;;
      c3d-standard-60) final_vcpu_count=60 ;;
      *) final_vcpu_count=unknown ;;
    esac
    printf '%s\n' \
      "Final-v34 slot cap:  3 VM-hours per slot" \
      "Worst-case VM-hours: $((repeats * 3))"
    if [ "$final_vcpu_count" != unknown ]; then
      printf '%s\n' "Worst-case vCPU-hours: $((repeats * 3 * final_vcpu_count))"
    fi
  fi
  if [ "$dry_run" = true ]; then
    echo 'Set dry run complete: no workspace or cloud resource was created.'
    exit 0
  fi
  [ "$confirm_paid" = true ] || fail "$EXIT_CONFIG" 'A new set requires --confirm-paid-run'
  workspace_id="$(date -u +%Y%m%dT%H%M%SZ)-${commit:0:12}-${mode}-$(printf '%04x' "$RANDOM")"
  workspace="$repo_root/benchmark-results/v3-production/sets/in-progress/$workspace_id"
  python3 "$analyzer" set-init "$workspace" "${plan_arguments[@]}"
else
  if [ "$form" = resume ]; then
    workspace=$resume_workspace
  else
    workspace=$replace_workspace
  fi
  load_plan "$workspace"
  if [ "$form" = replace ]; then
    python3 "$analyzer" set-authorize "$workspace" --slot "$slot" --reason "$reason" \
      --confirm-no-score-selection
  fi
fi

run_set() {
  while true; do
    next=$(python3 "$analyzer" set-next "$workspace")
    IFS=$'\t' read -r state next_slot next_attempt <<< "$next"
    case "$state" in
      RUNNING)
        set +e
        python3 "$analyzer" set-reconcile "$workspace"
        reconcile_exit=$?
        set -e
        [ "$reconcile_exit" -eq 0 ] || return "$reconcile_exit"
        ;;
      PENDING)
        [ "$confirm_paid" = true ] \
          || fail "$EXIT_CONFIG" "Set has pending slot $next_slot; resume requires --confirm-paid-run"
        begin=$(python3 "$analyzer" set-begin "$workspace" --slot "$next_slot")
        IFS=$'\t' read -r pointer_file log_file next_attempt <<< "$begin"
        set +e
        env "${run_environment[@]}" \
          "GSE_CLOUD_ORCHESTRATION_POINTER_FILE=$pointer_file" \
          "$repo_root/run-cloud-benchmark.sh" "$mode" 2>&1 | tee "$log_file"
        v1_exit=${PIPESTATUS[0]}
        python3 "$analyzer" set-record "$workspace" --slot "$next_slot" --v1-exit "$v1_exit"
        record_exit=$?
        set -e
        [ "$record_exit" -eq 0 ] || return "$record_exit"
        ;;
      FINALIZE)
        python3 "$analyzer" set-finalize "$workspace"
        return 0
        ;;
      COMPLETE)
        echo "Benchmark set already complete: $next_slot"
        return 0
        ;;
      BLOCKED_INFRASTRUCTURE)
        echo "Set stopped after infrastructure-invalid slot. Use --replace with explicit attestation." >&2
        return "$EXIT_INCOMPATIBLE_SET"
        ;;
      *)
        echo "Set cannot continue from state $state" >&2
        return "$EXIT_INCOMPATIBLE_SET"
        ;;
    esac
  done
}

run_set
