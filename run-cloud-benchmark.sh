#!/usr/bin/env bash
set -euo pipefail

readonly EXIT_CONFIG=2
readonly EXIT_PROVISION=10
readonly EXIT_REMOTE_SETUP=20
readonly EXIT_BENCHMARK=30
readonly EXIT_INTERRUPTED=40
readonly EXIT_COLLECTION=50
readonly EXIT_CHECKSUM=60
readonly EXIT_CLEANUP=70
readonly STATE_DIR=/var/lib/gse-cloud-benchmark

usage() {
  printf '%s\n' \
    'Usage: ./run-cloud-benchmark.sh [--dry-run] [--keep-vm] MODE' \
    '' \
    'Run the existing V3 production benchmark suite on one ephemeral GCP Compute Engine VM.' \
    '' \
    'Modes:' \
    '  quick  full  concurrency  soak  all' \
    '' \
    'Options:' \
    '  --dry-run  Validate and print the plan without creating, deleting, SSHing, or copying.' \
    '  --keep-vm  Retain the VM for debugging and print its exact deletion command.' \
    '  --help     Show this help without requiring gcloud or repository configuration.' \
    '' \
    'Required or resolved configuration:' \
    '  GSE_GCP_PROJECT                 Explicit project, or current gcloud project' \
    '  GSE_GCP_ZONE                    Explicit zone, or current gcloud compute zone' \
    '' \
    'Important overrides:' \
    '  GSE_CLOUD_MACHINE_TYPE          Default: c3d-standard-30' \
    '  GSE_CLOUD_PROVISIONING          spot (default) or standard' \
    '  GSE_CLOUD_IMAGE                 Optional exact image; otherwise resolve image family' \
    '  GSE_CLOUD_IMAGE_PROJECT         Default: ubuntu-os-cloud' \
    '  GSE_CLOUD_IMAGE_FAMILY          Default: ubuntu-2404-lts-amd64' \
    '  GSE_CLOUD_BOOT_DISK_SIZE        Default: 100GB' \
    '  GSE_CLOUD_BOOT_DISK_TYPE        Default: pd-balanced' \
    '  GSE_CLOUD_MAX_RUN_DURATION      Bounded duration; mode-derived by default' \
    '  GSE_GCP_NETWORK / GSE_GCP_SUBNET' \
    '  GSE_CLOUD_USE_IAP               Default: false' \
    '  GSE_CLOUD_EXTERNAL_IP           Default: true' \
    '  GSE_PERF_JVM_OPTIONS            Default: -Xms8g -Xmx16g' \
    '  GSE_CONCURRENCY_DOCUMENTS' \
    '  GSE_CONCURRENCY_THREAD_GROUPS' \
    '  GSE_SOAK_SECONDS'
}

dry_run=false
keep_vm=false
mode=
for argument in "$@"; do
  case "$argument" in
    --help|-h)
      usage
      exit 0
      ;;
    --dry-run) dry_run=true ;;
    --keep-vm) keep_vm=true ;;
    --*)
      echo "Unknown option: $argument" >&2
      usage >&2
      exit "$EXIT_CONFIG"
      ;;
    *)
      if [ -n "$mode" ]; then
        echo "Only one benchmark mode may be supplied" >&2
        usage >&2
        exit "$EXIT_CONFIG"
      fi
      mode=$argument
      ;;
  esac
done

case "$mode" in
  quick|full|concurrency|soak|all) ;;
  *)
    echo "A mode is required: quick, full, concurrency, soak, or all" >&2
    usage >&2
    exit "$EXIT_CONFIG"
    ;;
esac

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$repo_root"

fail() {
  code=$1
  shift
  echo "ERROR: $*" >&2
  exit "$code"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$EXIT_CONFIG" "Required command not found: $1"
}

validate_boolean() {
  name=$1
  value=$2
  case "$value" in
    true|false) ;;
    *) fail "$EXIT_CONFIG" "$name must be true or false (got: $value)" ;;
  esac
}

require_single_line() {
  name=$1
  value=$2
  case "$value" in
    *$'\n'*|*$'\r'*) fail "$EXIT_CONFIG" "$name must be a single line" ;;
  esac
}

duration_to_seconds() {
  duration=$1
  if [[ "$duration" =~ ^([1-9][0-9]*)([smhd]?)$ ]]; then
    amount=${BASH_REMATCH[1]}
    unit=${BASH_REMATCH[2]}
    case "$unit" in
      ''|s) multiplier=1; maximum_amount=604800 ;;
      m) multiplier=60; maximum_amount=10080 ;;
      h) multiplier=3600; maximum_amount=168 ;;
      d) multiplier=86400; maximum_amount=7 ;;
    esac
    if [ "${#amount}" -gt "${#maximum_amount}" ] \
        || { [ "${#amount}" -eq "${#maximum_amount}" ] && [[ "$amount" > "$maximum_amount" ]]; }; then
      fail "$EXIT_CONFIG" "GSE_CLOUD_MAX_RUN_DURATION must not exceed 7 days"
    fi
    duration_seconds=$((amount * multiplier))
  else
    fail "$EXIT_CONFIG" "Invalid duration '$duration' (use a positive number with s, m, h, or d)"
  fi
}

shell_join() {
  joined=
  printf -v joined '%q ' "$@"
  printf '%s' "${joined% }"
}

property_value() {
  wanted=$1
  content=$2
  property_result=
  while IFS='=' read -r key value; do
    if [ "$key" = "$wanted" ]; then
      property_result=$value
      return 0
    fi
  done <<< "$content"
  return 1
}

export CLOUDSDK_CORE_DISABLE_PROMPTS=1

require_command git
require_command gcloud
require_command sha256sum
require_command realpath

git rev-parse --show-toplevel >/dev/null 2>&1 \
  || fail "$EXIT_CONFIG" "Run this command from the GeneralSearchEngine Git repository"
actual_root=$(git rev-parse --show-toplevel)
[ "$actual_root" = "$repo_root" ] \
  || fail "$EXIT_CONFIG" "Repository root mismatch: expected $repo_root, got $actual_root"
[ -f pom.xml ] && [ -x mvnw ] && [ -f scripts/run-v3-production-performance.sh ] \
  || fail "$EXIT_CONFIG" "This does not look like the GeneralSearchEngine repository"

dirty=$(git status --porcelain --untracked-files=normal)
if [ -n "$dirty" ]; then
  echo "$dirty" >&2
  fail "$EXIT_CONFIG" "Working tree is dirty; commit, stash, or remove local changes before benchmarking"
fi

commit=$(git rev-parse HEAD)
short_commit=${commit:0:8}
repo_url=${GSE_CLOUD_REPO_URL:-https://github.com/patricklfdm/GeneralSearchEngine.git}
for pair in \
  "GSE_CLOUD_REPO_URL=$repo_url" \
  "GSE_PERF_JVM_OPTIONS=${GSE_PERF_JVM_OPTIONS:--Xms8g -Xmx16g}" \
  "GSE_CONCURRENCY_THREAD_GROUPS=${GSE_CONCURRENCY_THREAD_GROUPS:-}"; do
  require_single_line "${pair%%=*}" "${pair#*=}"
done

remote_check_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-cloud-commit.XXXXXX")
cleanup_remote_check() {
  rm -rf -- "$remote_check_dir"
}
git -C "$remote_check_dir" init --quiet
if ! git -C "$remote_check_dir" fetch --quiet --depth=1 "$repo_url" "$commit"; then
  cleanup_remote_check
  fail "$EXIT_CONFIG" "Commit $commit is not fetchable from $repo_url; push it before benchmarking"
fi
fetched_commit=$(git -C "$remote_check_dir" rev-parse FETCH_HEAD)
cleanup_remote_check
[ "$fetched_commit" = "$commit" ] \
  || fail "$EXIT_CONFIG" "Remote commit verification mismatch: expected $commit, got $fetched_commit"

active_account=$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | sed -n '1p')
[ -n "$active_account" ] || fail "$EXIT_CONFIG" "No active gcloud account; run: gcloud auth login"

project=${GSE_GCP_PROJECT:-}
if [ -z "$project" ]; then
  project=$(gcloud config get-value project 2>/dev/null || true)
fi
case "$project" in ''|'(unset)') fail "$EXIT_CONFIG" "Set GSE_GCP_PROJECT or configure a gcloud project" ;; esac

zone=${GSE_GCP_ZONE:-}
if [ -z "$zone" ]; then
  zone=$(gcloud config get-value compute/zone 2>/dev/null || true)
fi
case "$zone" in ''|'(unset)') fail "$EXIT_CONFIG" "Set GSE_GCP_ZONE or configure a gcloud compute zone" ;; esac

machine_type=${GSE_CLOUD_MACHINE_TYPE:-c3d-standard-30}
provisioning=${GSE_CLOUD_PROVISIONING:-spot}
image_project=${GSE_CLOUD_IMAGE_PROJECT:-ubuntu-os-cloud}
image_family=${GSE_CLOUD_IMAGE_FAMILY:-ubuntu-2404-lts-amd64}
requested_image=${GSE_CLOUD_IMAGE:-}
boot_disk_size=${GSE_CLOUD_BOOT_DISK_SIZE:-100GB}
boot_disk_type=${GSE_CLOUD_BOOT_DISK_TYPE:-pd-balanced}
network=${GSE_GCP_NETWORK:-}
subnet=${GSE_GCP_SUBNET:-}
use_iap=${GSE_CLOUD_USE_IAP:-false}
external_ip=${GSE_CLOUD_EXTERNAL_IP:-true}
jvm_options=${GSE_PERF_JVM_OPTIONS:--Xms8g -Xmx16g}

case "$provisioning" in spot|standard) ;; *) fail "$EXIT_CONFIG" "GSE_CLOUD_PROVISIONING must be spot or standard" ;; esac
validate_boolean GSE_CLOUD_USE_IAP "$use_iap"
validate_boolean GSE_CLOUD_EXTERNAL_IP "$external_ip"
if [ "$use_iap" = false ] && [ "$external_ip" = false ]; then
  fail "$EXIT_CONFIG" "IAP and external IP cannot both be disabled"
fi
if [ "$use_iap" = true ] && [ "$external_ip" = true ]; then
  fail "$EXIT_CONFIG" "IAP mode requires GSE_CLOUD_EXTERNAL_IP=false"
fi
[ -n "$jvm_options" ] || fail "$EXIT_CONFIG" "GSE_PERF_JVM_OPTIONS must not be empty"

for pair in \
  "GSE_GCP_PROJECT=$project" \
  "GSE_GCP_ZONE=$zone" \
  "GSE_CLOUD_MACHINE_TYPE=$machine_type" \
  "GSE_CLOUD_PROVISIONING=$provisioning" \
  "GSE_CLOUD_IMAGE_PROJECT=$image_project" \
  "GSE_CLOUD_IMAGE_FAMILY=$image_family" \
  "GSE_CLOUD_IMAGE=$requested_image" \
  "GSE_CLOUD_BOOT_DISK_SIZE=$boot_disk_size" \
  "GSE_CLOUD_BOOT_DISK_TYPE=$boot_disk_type" \
  "GSE_GCP_NETWORK=$network" \
  "GSE_GCP_SUBNET=$subnet"; do
  require_single_line "${pair%%=*}" "${pair#*=}"
done

if [ -n "${GSE_CONCURRENCY_DOCUMENTS:-}" ] \
    && [[ ! "$GSE_CONCURRENCY_DOCUMENTS" =~ ^[1-9][0-9]*$ ]]; then
  fail "$EXIT_CONFIG" "GSE_CONCURRENCY_DOCUMENTS must be a positive integer"
fi
if [ -n "${GSE_CONCURRENCY_THREAD_GROUPS:-}" ]; then
  read -r -a requested_thread_groups <<< "$GSE_CONCURRENCY_THREAD_GROUPS"
  [ "${#requested_thread_groups[@]}" -gt 0 ] \
    || fail "$EXIT_CONFIG" "GSE_CONCURRENCY_THREAD_GROUPS must not be empty"
  for group in "${requested_thread_groups[@]}"; do
    [[ "$group" =~ ^[1-9][0-9]*,[1-9][0-9]*$ ]] \
      || fail "$EXIT_CONFIG" "Invalid concurrency thread group: $group (expected readers,writers)"
  done
fi

soak_seconds=${GSE_SOAK_SECONDS:-1800}
[[ "$soak_seconds" =~ ^[1-9][0-9]*$ ]] \
  || fail "$EXIT_CONFIG" "GSE_SOAK_SECONDS must be a positive integer"
if [ "${#soak_seconds}" -gt 6 ] || [ "$soak_seconds" -gt 597600 ]; then
  fail "$EXIT_CONFIG" "GSE_SOAK_SECONDS plus the 2-hour recovery grace must fit within 7 days"
fi
if [ -n "${GSE_CLOUD_MAX_RUN_DURATION:-}" ]; then
  duration_to_seconds "$GSE_CLOUD_MAX_RUN_DURATION"
else
  case "$mode" in
    quick) duration_seconds=7200 ;;
    full) duration_seconds=43200 ;;
    concurrency) duration_seconds=28800 ;;
    soak) duration_seconds=$((soak_seconds + 7200)) ;;
    all) duration_seconds=86400 ;;
  esac
  [ "$duration_seconds" -le 604800 ] \
    || fail "$EXIT_CONFIG" "Requested soak plus recovery grace exceeds the 7-day v1 cap"
fi
max_run_duration="${duration_seconds}s"
if { [ "$mode" = soak ] || [ "$mode" = all ]; } \
    && [ "$duration_seconds" -lt $((soak_seconds + 7200)) ]; then
  fail "$EXIT_CONFIG" "Max run duration must exceed the requested soak by at least 2 hours"
fi

if [ "${GSE_CONCURRENCY_DOCUMENTS:-}" = 1000000 ] && [ "$jvm_options" = '-Xms8g -Xmx16g' ]; then
  echo "WARNING: 1M concurrency with the default 16-GB max heap is high risk; use -Xms32g -Xmx64g." >&2
fi
if [ "$soak_seconds" -gt 21600 ]; then
  echo "WARNING: requested soak exceeds 6 hours." >&2
fi

gcloud compute machine-types describe "$machine_type" \
  --project="$project" --zone="$zone" --format='value(name)' >/dev/null \
  || fail "$EXIT_CONFIG" "Machine type $machine_type is unavailable in $zone or Compute Engine access failed"

if [ -n "$requested_image" ]; then
  image_description=$(gcloud compute images describe "$requested_image" \
    --project="$image_project" --format='value(name,id,selfLink,creationTimestamp)') \
    || fail "$EXIT_CONFIG" "Cannot resolve exact image $image_project/$requested_image"
else
  image_description=$(gcloud compute images describe-from-family "$image_family" \
    --project="$image_project" --format='value(name,id,selfLink,creationTimestamp)') \
    || fail "$EXIT_CONFIG" "Cannot resolve image family $image_project/$image_family"
fi
IFS=$'\t' read -r resolved_image resolved_image_id resolved_image_self_link resolved_image_created_at <<< "$image_description"
[ -n "$resolved_image" ] && [ -n "$resolved_image_id" ] && [ -n "$resolved_image_self_link" ] \
  && [ -n "$resolved_image_created_at" ] \
  || fail "$EXIT_CONFIG" "Image resolution returned incomplete immutable identity"

region=${zone%-*}
if [ -n "$network" ]; then
  gcloud compute networks describe "$network" --project="$project" --format='value(name)' >/dev/null \
    || fail "$EXIT_CONFIG" "Existing network not found: $network"
fi
if [ -n "$subnet" ]; then
  gcloud compute networks subnets describe "$subnet" --project="$project" --region="$region" \
    --format='value(name)' >/dev/null \
    || fail "$EXIT_CONFIG" "Existing subnet not found in $region: $subnet"
elif [ -z "$network" ]; then
  network=default
  gcloud compute networks describe "$network" --project="$project" --format='value(name)' >/dev/null \
    || fail "$EXIT_CONFIG" "No explicit network/subnet and the project has no usable default network"
fi

timestamp=$(date -u +%Y%m%dt%H%M%Sz)
instance="gse-bench-${mode}-${short_commit}-${timestamp}-${RANDOM}"
instance=${instance:0:63}
instance=${instance%-}
if gcloud compute instances describe "$instance" --project="$project" --zone="$zone" \
    --format='value(name)' >/dev/null 2>&1; then
  fail "$EXIT_CONFIG" "Generated instance name already exists: $instance"
fi

labels="purpose=gse-benchmark,gse-mode=$mode,gse-commit=$short_commit,gse-created=${timestamp:0:8}"
create_command=(compute instances create "$instance"
  "--project=$project"
  "--zone=$zone"
  "--machine-type=$machine_type"
  "--image-project=$image_project"
  "--image=$resolved_image"
  "--boot-disk-size=$boot_disk_size"
  "--boot-disk-type=$boot_disk_type"
  --boot-disk-auto-delete
  --no-service-account
  --no-scopes
  "--max-run-duration=$max_run_duration"
  "--labels=$labels")
if [ "$provisioning" = spot ]; then
  create_command+=(--provisioning-model=SPOT --instance-termination-action=STOP
    "--metadata-from-file=shutdown-script=$repo_root/scripts/cloud/spot-shutdown.sh")
else
  create_command+=(--instance-termination-action=DELETE)
fi
if [ -n "$network" ]; then create_command+=("--network=$network"); fi
if [ -n "$subnet" ]; then create_command+=("--subnet=$subnet"); fi
if [ "$external_ip" = false ]; then create_command+=(--no-address); fi
create_command+=(--quiet)

ssh_transport=external_ip
ssh_common=("--project=$project" "--zone=$zone" --quiet)
if [ "$use_iap" = true ]; then
  ssh_transport=iap
  ssh_common+=(--tunnel-through-iap)
fi

local_results_root="$repo_root/benchmark-results/v3-production"
printf '%s\n' \
  "GeneralSearchEngine cloud benchmark" \
  "Commit:       $commit" \
  "Mode:         $mode" \
  "Project:      $project" \
  "Zone:         $zone" \
  "Machine:      $machine_type" \
  "Provisioning: ${provisioning^^}" \
  "Image family: $image_family" \
  "Resolved:     $resolved_image ($resolved_image_id)" \
  "JVM:          $jvm_options" \
  "Boot disk:    $boot_disk_type $boot_disk_size" \
  "Max runtime:  $max_run_duration" \
  "SSH path:     $ssh_transport" \
  "Instance:     $instance" \
  "Local output: $local_results_root"

remote_environment=(env
  "GSE_CLOUD_PROVIDER=gcp"
  "GSE_CLOUD_PROJECT=$project"
  "GSE_CLOUD_ZONE=$zone"
  "GSE_CLOUD_MACHINE_TYPE=$machine_type"
  "GSE_CLOUD_PROVISIONING=$provisioning"
  "GSE_CLOUD_INSTANCE_NAME=$instance"
  "GSE_CLOUD_IMAGE_PROJECT=$image_project"
  "GSE_CLOUD_IMAGE_FAMILY=$image_family"
  "GSE_CLOUD_IMAGE=$resolved_image"
  "GSE_CLOUD_IMAGE_ID=$resolved_image_id"
  "GSE_CLOUD_IMAGE_SELF_LINK=$resolved_image_self_link"
  "GSE_CLOUD_IMAGE_CREATED_AT=$resolved_image_created_at"
  "GSE_PERF_JVM_OPTIONS=$jvm_options")

if [ "$mode" = concurrency ]; then
  remote_environment+=("GSE_CONCURRENCY_DOCUMENTS=${GSE_CONCURRENCY_DOCUMENTS:-100000}")
  remote_environment+=("GSE_CONCURRENCY_THREAD_GROUPS=${GSE_CONCURRENCY_THREAD_GROUPS:-1,1 4,1 8,1 16,1 24,1 30,1}")
else
  if [ -n "${GSE_CONCURRENCY_DOCUMENTS:-}" ]; then
    remote_environment+=("GSE_CONCURRENCY_DOCUMENTS=$GSE_CONCURRENCY_DOCUMENTS")
  fi
  if [ -n "${GSE_CONCURRENCY_THREAD_GROUPS:-}" ]; then
    remote_environment+=("GSE_CONCURRENCY_THREAD_GROUPS=$GSE_CONCURRENCY_THREAD_GROUPS")
  fi
fi
for variable in GSE_SOAK_SECONDS GSE_SOAK_READERS GSE_SOAK_WRITERS GSE_SOAK_DOCUMENTS \
  GSE_JMH_FORKS GSE_JMH_WARMUPS GSE_JMH_ITERATIONS GSE_JMH_DURATION; do
  if [ -n "${!variable:-}" ]; then
    remote_environment+=("$variable=${!variable}")
  fi
done

remote_command=$(shell_join "${remote_environment[@]}" bash -s -- \
  "$repo_url" "$commit" "$mode" "$STATE_DIR")

echo "Remote benchmark command: $remote_command"
echo "Cleanup plan: gcloud compute instances delete $instance --project=$project --zone=$zone --quiet"

if [ "$dry_run" = true ]; then
  printf 'Create command: gcloud '
  printf '%q ' "${create_command[@]}"
  printf '\nDry run complete: no cloud resources were mutated.\n'
  exit 0
fi

mkdir -p "$local_results_root/cloud-orchestration"
orchestration_record="$local_results_root/cloud-orchestration/$instance.properties"
orchestration_log="$local_results_root/cloud-orchestration/$instance.log"
orchestrator_started=$(date -u +%Y%m%dT%H%M%SZ)
orchestrator_finished=
stage=PREFLIGHT_COMPLETE
primary_exit_code=0
ssh_exit_code=
remote_state=
remote_benchmark_exit_code=
remote_commit=
artifact_recovered=false
checksum_verified=false
preempted=false
run_complete=false
provision_attempted=false
cleanup_attempted=false
cleanup_succeeded=false
local_result_path=
recovery_restart_attempted=false

write_record() {
  temporary="$orchestration_record.tmp.$$"
  {
    printf 'provider=gcp\nproject=%s\nzone=%s\n' "$project" "$zone"
    printf 'instance_name=%s\nmachine_type=%s\nprovisioning=%s\n' "$instance" "$machine_type" "${provisioning^^}"
    printf 'requested_image_family=%s\nresolved_image=%s\n' "$image_family" "$resolved_image"
    printf 'resolved_image_id=%s\nresolved_image_self_link=%s\n' "$resolved_image_id" "$resolved_image_self_link"
    printf 'resolved_image_created_at=%s\n' "$resolved_image_created_at"
    printf 'boot_disk_type=%s\nboot_disk_size=%s\nmax_run_duration=%s\n' "$boot_disk_type" "$boot_disk_size" "$max_run_duration"
    printf 'network=%s\nsubnet=%s\nssh_transport=%s\n' "$network" "$subnet" "$ssh_transport"
    printf 'requested_commit=%s\nbenchmark_mode=%s\n' "$commit" "$mode"
    printf 'remote_commit=%s\n' "$remote_commit"
    printf 'orchestrator_started_utc=%s\norchestrator_finished_utc=%s\n' "$orchestrator_started" "$orchestrator_finished"
    printf 'stage=%s\nssh_exit_code=%s\nremote_state=%s\n' "$stage" "$ssh_exit_code" "$remote_state"
    printf 'remote_benchmark_exit_code=%s\n' "$remote_benchmark_exit_code"
    printf 'artifact_recovered=%s\nchecksum_verified=%s\n' "$artifact_recovered" "$checksum_verified"
    printf 'preempted=%s\nrun_complete=%s\n' "$preempted" "$run_complete"
    printf 'primary_exit_code=%s\nprovision_attempted=%s\n' "$primary_exit_code" "$provision_attempted"
    printf 'cleanup_attempted=%s\ncleanup_succeeded=%s\n' "$cleanup_attempted" "$cleanup_succeeded"
    printf 'local_result_path=%s\n' "$local_result_path"
  } > "$temporary"
  mv "$temporary" "$orchestration_record"
}

instance_exists() {
  gcloud compute instances describe "$instance" --project="$project" --zone="$zone" \
    --format='value(name)' >/dev/null 2>&1
}

cleanup_instance() {
  if [ "$provision_attempted" != true ]; then
    cleanup_succeeded=true
    return 0
  fi
  if [ "$keep_vm" = true ]; then
    cleanup_succeeded=true
    echo "VM retained by --keep-vm. Delete it with:" >&2
    echo "gcloud compute instances delete $instance --project=$project --zone=$zone --quiet" >&2
    return 0
  fi
  cleanup_attempted=true
  if ! instance_exists; then
    cleanup_succeeded=true
    return 0
  fi
  if gcloud compute instances delete "$instance" --project="$project" --zone="$zone" --quiet; then
    cleanup_succeeded=true
    return 0
  fi
  cleanup_succeeded=false
  echo "WARNING: VM CLEANUP FAILED" >&2
  echo "Project: $project" >&2
  echo "Zone: $zone" >&2
  echo "Instance: $instance" >&2
  return 1
}

finish_orchestration() {
  observed_exit=$?
  trap - EXIT INT TERM
  if [ "$primary_exit_code" -eq 0 ] && [ "$observed_exit" -ne 0 ]; then
    primary_exit_code=$observed_exit
  fi
  stage=CLEANUP
  write_record || true
  cleanup_failed=false
  cleanup_instance || cleanup_failed=true
  if [ "$cleanup_failed" = true ] && [ "$primary_exit_code" -eq 0 ]; then
    primary_exit_code=$EXIT_CLEANUP
  fi
  orchestrator_finished=$(date -u +%Y%m%dT%H%M%SZ)
  stage=FINISHED
  write_record || true
  echo "Cloud orchestration record: $orchestration_record"
  if [ -n "$local_result_path" ]; then
    echo "Local benchmark result: $local_result_path"
  fi
  exit "$primary_exit_code"
}
trap finish_orchestration EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
write_record

run_ssh() {
  gcloud compute ssh "$instance" "${ssh_common[@]}" "$@"
}

wait_for_ssh() {
  attempts=${1:-20}
  delay=${2:-15}
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if run_ssh --command=true >/dev/null 2>&1; then
      return 0
    fi
    if [ "$attempt" -lt "$attempts" ]; then sleep "$delay"; fi
  done
  return 1
}

fetch_remote_file() {
  path=$1
  remote_file_content=
  if remote_file_content=$(run_ssh --command="sudo cat $(printf '%q' "$path")" 2>/dev/null); then
    return 0
  fi
  return 1
}

fetch_remote_state() {
  if fetch_remote_file "$STATE_DIR/state.properties"; then
    property_value state "$remote_file_content" || true
    remote_state=$property_result
    property_value benchmark_exit_code "$remote_file_content" || true
    remote_benchmark_exit_code=$property_result
    property_value remote_commit "$remote_file_content" || true
    remote_commit=$property_result
    write_record
    return 0
  fi
  return 1
}

recover_confirmed_spot_interruption() {
  [ "$provisioning" = spot ] || return 1
  [ "$recovery_restart_attempted" = false ] || return 1
  recovery_status=$(gcloud compute instances describe "$instance" --project="$project" --zone="$zone" \
    --format='value(status)' 2>/dev/null || true)
  [ "$recovery_status" = TERMINATED ] || return 1

  recovery_restart_attempted=true
  stage=INTERRUPTION_RECOVERY
  write_record
  if ! gcloud compute instances start "$instance" --project="$project" --zone="$zone" --quiet \
      >> "$orchestration_log" 2>&1; then
    return 1
  fi
  wait_for_ssh 40 15 || return 1
  fetch_remote_state || true
  if fetch_remote_file "$STATE_DIR/interruption.properties"; then
    property_value preempted "$remote_file_content" || true
    if [ "$property_result" = true ]; then
      preempted=true
      remote_state=INTERRUPTED
      write_record
      return 0
    fi
  fi
  return 1
}

stage=PROVISIONING
provision_attempted=true
write_record
if ! gcloud "${create_command[@]}" 2>&1 | tee -a "$orchestration_log"; then
  primary_exit_code=$EXIT_PROVISION
  exit "$primary_exit_code"
fi

stage=WAITING_FOR_SSH
write_record
if ! wait_for_ssh 20 15; then
  echo "VM did not become reachable by SSH within 5 minutes" >&2
  if recover_confirmed_spot_interruption; then
    primary_exit_code=$EXIT_INTERRUPTED
  else
    primary_exit_code=$EXIT_REMOTE_SETUP
  fi
  exit "$primary_exit_code"
fi

stage=BOOTSTRAPPING
write_record
set +e
run_ssh --command="bash -s -- $(printf '%q' "$STATE_DIR")" \
  < "$repo_root/scripts/cloud/remote-bootstrap.sh" 2>&1 | tee -a "$orchestration_log"
bootstrap_exit=${PIPESTATUS[0]}
set -e
if [ "$bootstrap_exit" -ne 0 ]; then
  fetch_remote_state || true
  if recover_confirmed_spot_interruption; then
    primary_exit_code=$EXIT_INTERRUPTED
  else
    primary_exit_code=$EXIT_REMOTE_SETUP
  fi
  exit "$primary_exit_code"
fi

stage=BENCHMARK_RUNNING
write_record
set +e
run_ssh --command="$remote_command" \
  < "$repo_root/scripts/cloud/remote-run-benchmark.sh" 2>&1 | tee -a "$orchestration_log"
ssh_exit_code=${PIPESTATUS[0]}
set -e

fetch_remote_state || true
instance_status=$(gcloud compute instances describe "$instance" --project="$project" --zone="$zone" \
  --format='value(status)' 2>/dev/null || true)

if [ "$ssh_exit_code" -ne 0 ] && [ "$remote_state" != BENCHMARK_FAIL ]; then
  if [ "$instance_status" = RUNNING ]; then
    for retry in 1 2 3; do
      sleep 5
      fetch_remote_state && break
    done
  elif [ "$provisioning" = spot ] && [ "$instance_status" = TERMINATED ]; then
    recover_confirmed_spot_interruption || true
  fi
fi

if [ "$remote_state" = REMOTE_SETUP_FAIL ] || [ "$remote_state" = REMOTE_SETUP ] || [ "$remote_state" = READY ]; then
  primary_exit_code=$EXIT_REMOTE_SETUP
  exit "$primary_exit_code"
fi
if [ "$preempted" = true ]; then
  primary_exit_code=$EXIT_INTERRUPTED
elif [ -z "$remote_state" ] || { [ "$remote_state" != BENCHMARK_PASS ] && [ "$remote_state" != BENCHMARK_FAIL ]; }; then
  primary_exit_code=$EXIT_COLLECTION
fi

stage=COLLECTING
write_record
discover_command='set -euo pipefail; root=$(realpath "$HOME/GeneralSearchEngine/benchmark-results/v3-production"); latest_file="$root/LATEST"; test -f "$latest_file"; test "$(wc -l < "$latest_file")" -eq 1; candidate=$(realpath -e -- "$(sed -n "1p" "$latest_file")"); case "$candidate" in "$root"/*) ;; *) exit 51 ;; esac; test "$(dirname "$candidate")" = "$root"; test -d "$candidate"; printf "%s\n" "$candidate"'
remote_result_path=
if remote_result_path=$(run_ssh --command="bash -c $(printf '%q' "$discover_command")" 2>/dev/null); then
  remote_result_path=${remote_result_path%$'\r'}
  if [ -z "$remote_result_path" ] || [[ "$remote_result_path" == *$'\n'* ]] \
      || [[ "$remote_result_path" != /* ]] \
      || [[ "$remote_result_path" != */GeneralSearchEngine/benchmark-results/v3-production/* ]]; then
    echo "Remote result discovery returned an invalid path" >&2
    primary_exit_code=$EXIT_COLLECTION
    exit "$primary_exit_code"
  fi
else
  if [ "$primary_exit_code" -eq "$EXIT_INTERRUPTED" ]; then
    echo "Interrupted run has no recoverable result directory" >&2
    exit "$primary_exit_code"
  fi
  primary_exit_code=$EXIT_COLLECTION
  exit "$primary_exit_code"
fi

result_name=$(basename -- "$remote_result_path")
case "$result_name" in ''|.|..) primary_exit_code=$EXIT_COLLECTION; exit "$primary_exit_code" ;; esac
final_result="$local_results_root/$result_name"
if [ -e "$final_result" ]; then
  echo "Refusing to overwrite existing result: $final_result" >&2
  primary_exit_code=$EXIT_COLLECTION
  exit "$primary_exit_code"
fi

staging_dir=$(mktemp -d "$local_results_root/.cloud-download.XXXXXX")
set +e
gcloud compute scp --recurse "$instance:$remote_result_path" "$staging_dir" \
  "${ssh_common[@]}" 2>&1 | tee -a "$orchestration_log"
scp_exit=${PIPESTATUS[0]}
set -e
if [ "$scp_exit" -ne 0 ] || [ ! -d "$staging_dir/$result_name" ]; then
  echo "Artifact copy failed; incomplete staging remains at $staging_dir" >&2
  if [ "$primary_exit_code" -ne "$EXIT_INTERRUPTED" ]; then primary_exit_code=$EXIT_COLLECTION; fi
  exit "$primary_exit_code"
fi
staged_result="$staging_dir/$result_name"

required_evidence=true
for evidence in status.properties metadata.txt environment.txt; do
  if [ ! -f "$staged_result/$evidence" ]; then required_evidence=false; fi
done

if [ "$primary_exit_code" -eq "$EXIT_INTERRUPTED" ]; then
  partial_root="$local_results_root/partial/$instance"
  mkdir -p "$partial_root"
  mv "$staged_result" "$partial_root/$result_name"
  local_result_path="$partial_root/$result_name"
  artifact_recovered=true
  if [ -f "$local_result_path/checksums.sha256" ] && \
      (cd "$local_result_path" && sha256sum -c checksums.sha256) >> "$orchestration_log" 2>&1; then
    checksum_verified=true
  fi
  exit "$primary_exit_code"
fi

if [ "$required_evidence" != true ]; then
  echo "Completed run is missing required evidence" >&2
  primary_exit_code=$EXIT_COLLECTION
  exit "$primary_exit_code"
fi

if [ ! -f "$staged_result/checksums.sha256" ]; then
  echo "Completed run is missing checksums.sha256" >&2
  quarantine_root="$local_results_root/quarantine/$instance"
  mkdir -p "$quarantine_root"
  mv "$staged_result" "$quarantine_root/$result_name"
  local_result_path="$quarantine_root/$result_name"
  artifact_recovered=true
  primary_exit_code=$EXIT_CHECKSUM
  exit "$primary_exit_code"
fi

if ! (cd "$staged_result" && sha256sum -c checksums.sha256) >> "$orchestration_log" 2>&1; then
  quarantine_root="$local_results_root/quarantine/$instance"
  mkdir -p "$quarantine_root"
  mv "$staged_result" "$quarantine_root/$result_name"
  local_result_path="$quarantine_root/$result_name"
  artifact_recovered=true
  primary_exit_code=$EXIT_CHECKSUM
  exit "$primary_exit_code"
fi

checksum_verified=true
status=$(sed -n 's/^status=//p' "$staged_result/status.properties" | sed -n '1p')
if [ "$remote_state" = BENCHMARK_PASS ] && [ "$status" = PASS ]; then
  run_complete=true
  primary_exit_code=0
elif [ "$remote_state" = BENCHMARK_FAIL ] && [ "$status" = FAIL ]; then
  run_complete=true
  primary_exit_code=$EXIT_BENCHMARK
else
  echo "Remote state and status.properties disagree" >&2
  quarantine_root="$local_results_root/quarantine/$instance"
  mkdir -p "$quarantine_root"
  mv "$staged_result" "$quarantine_root/$result_name"
  local_result_path="$quarantine_root/$result_name"
  artifact_recovered=true
  primary_exit_code=$EXIT_COLLECTION
  exit "$primary_exit_code"
fi

mv "$staged_result" "$final_result"
local_result_path=$final_result
artifact_recovered=true

exit "$primary_exit_code"
