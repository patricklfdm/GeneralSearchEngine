#!/usr/bin/env bash
set -euo pipefail

readonly EXIT_CONFIG=2
readonly EXIT_PROVISION=10
readonly EXIT_REMOTE=20
readonly EXIT_COLLECTION=30
readonly EXIT_CLEANUP=40

confirm=false
if [[ "${1:-}" == "--confirm-paid-run" ]]; then
  confirm=true
elif [[ "${1:-}" != "--dry-run" || $# -ne 1 ]]; then
  echo "usage: run_durable_cloud_member.sh --dry-run|--confirm-paid-run" >&2
  exit "$EXIT_CONFIG"
fi

required=(
  GSE_V4_GCP_PROJECT GSE_V4_GCP_ZONE GSE_V4_CLOUD_IMAGE
  GSE_V4_SOURCE_SHA GSE_V4_RUN_ID GSE_V4_SLOT GSE_V4_PROFILE
  GSE_V4_DURATION_SECONDS GSE_V4_OUTPUT
)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || { echo "ERROR: $name is required" >&2; exit "$EXIT_CONFIG"; }
done
[[ "$GSE_V4_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR: invalid source SHA" >&2; exit "$EXIT_CONFIG"; }
[[ "$GSE_V4_RUN_ID" =~ ^[0-9]+$ ]] || { echo "ERROR: invalid run ID" >&2; exit "$EXIT_CONFIG"; }
[[ "$GSE_V4_SLOT" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR: invalid slot" >&2; exit "$EXIT_CONFIG"; }
case "$GSE_V4_PROFILE" in experiment|canonical) ;; *) echo "ERROR: invalid profile" >&2; exit "$EXIT_CONFIG" ;; esac
[[ "$GSE_V4_DURATION_SECONDS" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR: invalid duration" >&2; exit "$EXIT_CONFIG"; }

machine_type=${GSE_V4_MACHINE_TYPE:-c3d-standard-30}
[[ "$machine_type" = c3d-standard-30 ]] || { echo "ERROR: machine substitution is forbidden" >&2; exit "$EXIT_CONFIG"; }
name="gse-v40-${GSE_V4_RUN_ID}-${GSE_V4_SLOT}"
name=${name:0:51}
writer_vm="$name-writer"
disk="$name-data"
mount_point=/mnt/gse-v4-durable
remote_evidence="$mount_point/evidence-${GSE_V4_SLOT}"
output=$(realpath -m "$GSE_V4_OUTPUT")
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
[[ "$output" = "$repo_root"/* || "$output" = /tmp/* ]] \
  || { echo "ERROR: output must be under the repository or /tmp" >&2; exit "$EXIT_CONFIG"; }

printf '%s\n' \
  "V4 durable cloud member plan" \
  "  source:   $GSE_V4_SOURCE_SHA" \
  "  profile:  $GSE_V4_PROFILE" \
  "  project:  $GSE_V4_GCP_PROJECT" \
  "  zone:     $GSE_V4_GCP_ZONE" \
  "  machine:  $machine_type" \
  "  image:    $GSE_V4_CLOUD_IMAGE" \
  "  disk:     $disk (pd-balanced, 200 GiB, retained independently)" \
  "  duration: $GSE_V4_DURATION_SECONDS seconds"
if [[ "$confirm" == false ]]; then
  echo "v40CloudMemberDryRun=PASS"
  exit 0
fi

command -v gcloud >/dev/null || { echo "ERROR: gcloud is required" >&2; exit "$EXIT_CONFIG"; }
mkdir -p "$output"
resources_created=false
run_status=FAIL
cleanup() {
  local status=0
  if [[ "$resources_created" == true ]]; then
    if gcloud compute instances describe "$writer_vm" \
        --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" \
        >/dev/null 2>&1; then
      gcloud compute instances delete "$writer_vm" \
        --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" --quiet \
        >/dev/null 2>&1 || status=$EXIT_CLEANUP
    fi
    if gcloud compute disks describe "$disk" \
        --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" \
        >/dev/null 2>&1; then
      local deleted=false
      for _ in 1 2 3 4 5; do
        if gcloud compute disks delete "$disk" \
            --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" --quiet \
            >/dev/null 2>&1; then
          deleted=true
          break
        fi
        sleep 3
      done
      [[ "$deleted" == true ]] || status=$EXIT_CLEANUP
    fi
  fi
  return "$status"
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
  printf 'sourceCommit=%s\nprofile=%s\nslot=%s\nrunStatus=%s\ncleanup=%s\n' \
    "$GSE_V4_SOURCE_SHA" "$GSE_V4_PROFILE" "$GSE_V4_SLOT" \
    "$run_status" "$cleanup_status" \
    > "$output/cloud-member.properties" || true
  if [[ $primary_status -ne 0 ]]; then
    exit "$primary_status"
  fi
  if [[ $cleanup_code -ne 0 ]]; then
    exit "$EXIT_CLEANUP"
  fi
}
trap finalize EXIT

gcloud compute disks create "$disk" \
  --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" \
  --type=pd-balanced --size=200GB --quiet || exit "$EXIT_PROVISION"
resources_created=true
gcloud compute instances create "$writer_vm" \
  --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" \
  --machine-type="$machine_type" --provisioning-model=STANDARD \
  --image-project=ubuntu-os-cloud --image="$GSE_V4_CLOUD_IMAGE" \
  --boot-disk-size=100GB --boot-disk-type=pd-balanced --boot-disk-auto-delete \
  --disk="name=$disk,device-name=gse-v4-data,mode=rw,boot=no,auto-delete=no" \
  --no-service-account --no-scopes \
  --max-run-duration="$((GSE_V4_DURATION_SECONDS + 3600))s" \
  --instance-termination-action=DELETE \
  --labels="purpose=gse-v40-durable,slot=$GSE_V4_SLOT" \
  --quiet || exit "$EXIT_PROVISION"

deadline=$((SECONDS + 180))
until gcloud compute ssh "$writer_vm" \
    --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" \
    --command=true --quiet >/dev/null 2>&1; do
  [[ $SECONDS -lt $deadline ]] || { echo "ERROR: SSH timeout" >&2; exit "$EXIT_REMOTE"; }
  sleep 5
done

gcloud compute scp scripts/v4/remote_durable_member.sh "$writer_vm:~/" \
  --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" --quiet
remote_command=$(printf \
  'GSE_V4_CLOUD_MACHINE_TYPE=%q GSE_V4_CLOUD_IMAGE=%q GSE_V4_CLOUD_ZONE=%q bash ~/remote_durable_member.sh %q %q %q %q %q %q' \
  "$machine_type" "$GSE_V4_CLOUD_IMAGE" "$GSE_V4_GCP_ZONE" \
  "$GSE_V4_SOURCE_SHA" "$GSE_V4_PROFILE" "$GSE_V4_DURATION_SECONDS" \
  "$mount_point" /dev/disk/by-id/google-gse-v4-data "$remote_evidence")
gcloud compute ssh "$writer_vm" \
  --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" \
  --command="$remote_command" --quiet || exit "$EXIT_REMOTE"

gcloud compute scp --recurse "$writer_vm:$remote_evidence/evidence" "$output/" \
  --project="$GSE_V4_GCP_PROJECT" --zone="$GSE_V4_GCP_ZONE" --quiet \
  || exit "$EXIT_COLLECTION"
python3 -m scripts.v4.durable_performance validate "$output/evidence" \
  || exit "$EXIT_COLLECTION"

run_status=PASS
echo "v40CloudMember=PASS slot=$GSE_V4_SLOT output=$output"
