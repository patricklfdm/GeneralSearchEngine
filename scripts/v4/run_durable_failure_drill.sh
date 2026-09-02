#!/usr/bin/env bash
set -euo pipefail

readonly EXIT_CONFIG=2
readonly EXIT_PROVISION=10
readonly EXIT_REMOTE=20
readonly EXIT_COLLECTION=30
readonly EXIT_CLEANUP=40

confirm=false
if [[ "${1:-}" == "--confirm-paid-run" && $# -eq 1 ]]; then
  confirm=true
elif [[ "${1:-}" != "--dry-run" || $# -ne 1 ]]; then
  echo "usage: run_durable_failure_drill.sh --dry-run|--confirm-paid-run" >&2
  exit "$EXIT_CONFIG"
fi
for name in GSE_V4_GCP_PROJECT GSE_V4_GCP_ZONE GSE_V4_CLOUD_IMAGE \
    GSE_V4_SOURCE_SHA GSE_V4_RUN_ID GSE_V4_OUTPUT; do
  [[ -n "${!name:-}" ]] || { echo "ERROR: $name is required" >&2; exit "$EXIT_CONFIG"; }
done
[[ "$GSE_V4_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR: invalid source SHA" >&2; exit "$EXIT_CONFIG"; }
[[ "$GSE_V4_RUN_ID" =~ ^[0-9]+$ ]] || { echo "ERROR: invalid run ID" >&2; exit "$EXIT_CONFIG"; }
machine_type=${GSE_V4_MACHINE_TYPE:-c3d-standard-30}
[[ "$machine_type" = c3d-standard-30 ]] || { echo "ERROR: machine substitution is forbidden" >&2; exit "$EXIT_CONFIG"; }
base="gse-v40-f-${GSE_V4_RUN_ID}"
base=${base:0:48}
writer_vm="$base-writer"
recovery_vm="$base-recovery"
disk="$base-data"
mount_point=/mnt/gse-v4-durable
workspace="$mount_point/failure-${GSE_V4_RUN_ID}"
output=$(realpath -m "$GSE_V4_OUTPUT")
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
[[ "$output" = "$repo_root"/* || "$output" = /tmp/* ]] \
  || { echo "ERROR: output must be under the repository or /tmp" >&2; exit "$EXIT_CONFIG"; }

printf '%s\n' \
  "V4 preserved-disk failure-drill plan" \
  "  source:      $GSE_V4_SOURCE_SHA" \
  "  writer VM:   $writer_vm" \
  "  recovery VM: $recovery_vm" \
  "  disk:        $disk (pd-balanced, 200 GiB, auto-delete disabled)"
if [[ "$confirm" == false ]]; then
  echo "v40FailureDrillDryRun=PASS"
  exit 0
fi
command -v gcloud >/dev/null || { echo "ERROR: gcloud is required" >&2; exit "$EXIT_CONFIG"; }
mkdir -p "$output"
run_status=FAIL
cleanup() {
  local failed=0
  for vm in "$writer_vm" "$recovery_vm"; do
    if gcloud compute instances describe "$vm" --project="$GSE_V4_GCP_PROJECT" \
        --zone="$GSE_V4_GCP_ZONE" >/dev/null 2>&1; then
      gcloud compute instances delete "$vm" --project="$GSE_V4_GCP_PROJECT" \
        --zone="$GSE_V4_GCP_ZONE" --quiet >/dev/null 2>&1 || failed=1
    fi
  done
  if gcloud compute disks describe "$disk" --project="$GSE_V4_GCP_PROJECT" \
      --zone="$GSE_V4_GCP_ZONE" >/dev/null 2>&1; then
    local deleted=false
    for _ in 1 2 3 4 5; do
      if gcloud compute disks delete "$disk" --project="$GSE_V4_GCP_PROJECT" \
          --zone="$GSE_V4_GCP_ZONE" --quiet >/dev/null 2>&1; then
        deleted=true
        break
      fi
      sleep 3
    done
    [[ "$deleted" == true ]] || failed=1
  fi
  [[ $failed -eq 0 ]]
}
finalize() {
  local primary_status=$?
  local cleanup_status=PASS
  local cleanup_code=0
  trap - EXIT
  if cleanup; then
    cleanup_code=0
  else
    cleanup_code=$?
    cleanup_status=FAIL
  fi
  mkdir -p "$output" || true
  printf 'sourceCommit=%s\nprofile=failure-drill\nrunStatus=%s\nwriterVmDeleted=%s\nrecoveryVmDeleted=%s\npersistentDiskDeleted=%s\n' \
    "$GSE_V4_SOURCE_SHA" "$run_status" "$cleanup_status" \
    "$cleanup_status" "$cleanup_status" \
    > "$output/cloud-cleanup.properties" || true
  if [[ $primary_status -ne 0 ]]; then
    exit "$primary_status"
  fi
  if [[ $cleanup_code -ne 0 ]]; then
    exit "$EXIT_CLEANUP"
  fi
}
trap finalize EXIT

create_vm() {
  local vm=$1
  gcloud compute instances create "$vm" \
    --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" \
    --machine-type="$machine_type" --provisioning-model=STANDARD \
    --image-project=ubuntu-os-cloud --image="$GSE_V4_CLOUD_IMAGE" \
    --boot-disk-size=100GB --boot-disk-type=pd-balanced --boot-disk-auto-delete \
    --disk="name=$disk,device-name=gse-v4-data,mode=rw,boot=no,auto-delete=no" \
    --no-service-account --no-scopes --max-run-duration=3600s \
    --instance-termination-action=DELETE \
    --labels=purpose=gse-v40-failure-drill --quiet
}
wait_ssh() {
  local vm=$1 deadline=$((SECONDS + 180))
  until gcloud compute ssh "$vm" --project="$GSE_V4_GCP_PROJECT" \
      --zone="$GSE_V4_GCP_ZONE" --command=true --quiet >/dev/null 2>&1; do
    [[ $SECONDS -lt $deadline ]] || return 1
    sleep 5
  done
}
run_half() {
  local vm=$1 mode=$2
  gcloud compute scp scripts/v4/remote_durable_failure.sh "$vm:~/" \
    --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" --quiet
  local command
  command=$(printf \
    'GSE_V4_CLOUD_MACHINE_TYPE=%q GSE_V4_CLOUD_IMAGE=%q GSE_V4_CLOUD_ZONE=%q bash ~/remote_durable_failure.sh %q %q %q %q %q %q' \
    "$machine_type" "$GSE_V4_CLOUD_IMAGE" "$GSE_V4_GCP_ZONE" \
    "$GSE_V4_SOURCE_SHA" "$mode" "$mount_point" \
    /dev/disk/by-id/google-gse-v4-data "$workspace" 60)
  gcloud compute ssh "$vm" --project="$GSE_V4_GCP_PROJECT" \
    --zone="$GSE_V4_GCP_ZONE" --command="$command" --quiet
}

gcloud compute disks create "$disk" --project="$GSE_V4_GCP_PROJECT" \
  --zone="$GSE_V4_GCP_ZONE" --type=pd-balanced --size=200GB --quiet \
  || exit "$EXIT_PROVISION"
create_vm "$writer_vm" || exit "$EXIT_PROVISION"
wait_ssh "$writer_vm" || exit "$EXIT_REMOTE"
run_half "$writer_vm" writer || exit "$EXIT_REMOTE"
gcloud compute instances delete "$writer_vm" --project="$GSE_V4_GCP_PROJECT" \
  --zone="$GSE_V4_GCP_ZONE" --quiet || exit "$EXIT_PROVISION"

create_vm "$recovery_vm" || exit "$EXIT_PROVISION"
wait_ssh "$recovery_vm" || exit "$EXIT_REMOTE"
run_half "$recovery_vm" recover || exit "$EXIT_REMOTE"
gcloud compute scp --recurse "$recovery_vm:$workspace/evidence" "$output/" \
  --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" --quiet \
  || exit "$EXIT_COLLECTION"
python3 -m scripts.v4.durable_remote_failure validate "$output/evidence" \
  || exit "$EXIT_COLLECTION"

run_status=PASS
echo "v40FailureDrill=PASS output=$output"
