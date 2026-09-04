#!/usr/bin/env bash
set -euo pipefail

readonly EXIT_CONFIG=2
readonly EXIT_PROVISION=10
readonly EXIT_REMOTE=20
readonly EXIT_COLLECTION=30
readonly EXIT_CLEANUP=40

confirm=false
if [[ "${1:-}" == --confirm-paid-run && $# -eq 1 ]]; then
  confirm=true
elif [[ "${1:-}" != --dry-run || $# -ne 1 ]]; then
  echo "usage: run_storage_evolution_cloud_member.sh --dry-run|--confirm-paid-run" >&2
  exit "$EXIT_CONFIG"
fi

required=(GSE_V42_GCP_PROJECT GSE_V42_GCP_ZONE GSE_V42_CLOUD_IMAGE
  GSE_V42_GCS_BUCKET GSE_V42_SOURCE_SHA GSE_V42_RUN_ID GSE_V42_RUN_ATTEMPT
  GSE_V42_SLOT GSE_V42_PROFILE GSE_V42_DURATION_SECONDS GSE_V42_OUTPUT)
for variable in "${required[@]}"; do
  [[ -n "${!variable:-}" ]] || { echo "ERROR: $variable is required" >&2; exit "$EXIT_CONFIG"; }
done
[[ "$GSE_V42_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || exit "$EXIT_CONFIG"
[[ "$GSE_V42_RUN_ID" =~ ^[0-9]+$ && "$GSE_V42_RUN_ATTEMPT" =~ ^[1-9][0-9]*$ ]] || exit "$EXIT_CONFIG"
[[ "$GSE_V42_SLOT" =~ ^[1-9][0-9]*$ ]] || exit "$EXIT_CONFIG"
case "$GSE_V42_PROFILE" in experiment|canonical|failure-drill) ;; *) exit "$EXIT_CONFIG" ;; esac
[[ "$GSE_V42_DURATION_SECONDS" = 1800 ]] || { echo "ERROR: frozen duration is 1800 seconds" >&2; exit "$EXIT_CONFIG"; }
if [[ "$GSE_V42_PROFILE" = canonical ]]; then
  [[ "$GSE_V42_SLOT" =~ ^[123]$ ]] || exit "$EXIT_CONFIG"
else
  [[ "$GSE_V42_SLOT" = 1 ]] || exit "$EXIT_CONFIG"
fi
[[ "$GSE_V42_GCS_BUCKET" =~ ^gs://[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$ ]] || exit "$EXIT_CONFIG"
machine_type=${GSE_V42_MACHINE_TYPE:-c3d-standard-30}
[[ "$machine_type" = c3d-standard-30 ]] || exit "$EXIT_CONFIG"

prefix="gse-v42-${GSE_V42_RUN_ID}-${GSE_V42_RUN_ATTEMPT}-${GSE_V42_SLOT}"
prefix=${prefix:0:48}
source_vm="$prefix-source"
replacement_target_vm="$prefix-target"
rollback_vm="$prefix-rollback"
source_disk="$prefix-source-data"
target_disk="$prefix-target-data"
mount_root=/mnt/gse-v42-evolution
output=$(realpath -m "$GSE_V42_OUTPUT")
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
[[ "$output" = "$repo_root"/* || "$output" = /tmp/* ]] || exit "$EXIT_CONFIG"
staging_uri="${GSE_V42_GCS_BUCKET}/v4.2-storage-evolution/${GSE_V42_SOURCE_SHA}/${GSE_V42_RUN_ID}-${GSE_V42_RUN_ATTEMPT}/${GSE_V42_PROFILE}/member-${GSE_V42_SLOT}/transport"

printf '%s\n' \
  "V4.2 storage-evolution member plan" \
  "  source:       $GSE_V42_SOURCE_SHA" \
  "  profile:      $GSE_V42_PROFILE" \
  "  project:      $GSE_V42_GCP_PROJECT" \
  "  zone:         $GSE_V42_GCP_ZONE" \
  "  machine:      $machine_type" \
  "  image:        $GSE_V42_CLOUD_IMAGE" \
  "  source disk:  $source_disk (pd-balanced, 200 GiB)" \
  "  target disk:  $target_disk (pd-balanced, 200 GiB)" \
  "  duration:     $GSE_V42_DURATION_SECONDS seconds" \
  "  rollback:     published GeneralSearchEngine 4.1.0" \
  "  staging:      $staging_uri"
if [[ "$confirm" == false ]]; then
  echo "v42CloudMemberDryRun=PASS"
  exit 0
fi

command -v gcloud >/dev/null || exit "$EXIT_CONFIG"
mkdir -p "$output"
run_status=FAIL
source_vm_deleted=NOT_APPLICABLE
replacement_target_vm_deleted=NOT_APPLICABLE
rollback_vm_deleted=NOT_APPLICABLE
source_disk_deleted=NOT_APPLICABLE
target_disk_deleted=NOT_APPLICABLE
staging_object_deleted=NOT_APPLICABLE
source_vm_owned=false
replacement_target_vm_owned=false
rollback_vm_owned=false
source_disk_owned=false
target_disk_owned=false
staging_owned=false

delete_instance() {
  local name=$1
  if gcloud compute instances describe "$name" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" >/dev/null 2>&1; then
    gcloud compute instances delete "$name" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --quiet >/dev/null
  fi
  ! gcloud compute instances describe "$name" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" >/dev/null 2>&1
}

delete_disk() {
  local name=$1
  if gcloud compute disks describe "$name" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" >/dev/null 2>&1; then
    local deleted=false
    for _ in 1 2 3 4 5; do
      if gcloud compute disks delete "$name" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --quiet >/dev/null 2>&1; then deleted=true; break; fi
      sleep 3
    done
    [[ "$deleted" == true ]] || return 1
  fi
  ! gcloud compute disks describe "$name" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" >/dev/null 2>&1
}

cleanup_value_complete() { [[ "$1" = PASS || "$1" = NOT_APPLICABLE ]]; }

cleanup() {
  local code=0
  if [[ "$source_vm_owned" == true ]]; then
    if delete_instance "$source_vm"; then source_vm_deleted=PASS; source_vm_owned=false; else source_vm_deleted=FAIL; code=$EXIT_CLEANUP; fi
  fi
  if [[ "$replacement_target_vm_owned" == true ]]; then
    if delete_instance "$replacement_target_vm"; then replacement_target_vm_deleted=PASS; replacement_target_vm_owned=false; else replacement_target_vm_deleted=FAIL; code=$EXIT_CLEANUP; fi
  fi
  if [[ "$rollback_vm_owned" == true ]]; then
    if delete_instance "$rollback_vm"; then rollback_vm_deleted=PASS; rollback_vm_owned=false; else rollback_vm_deleted=FAIL; code=$EXIT_CLEANUP; fi
  fi
  if [[ "$target_disk_owned" == true ]]; then
    if delete_disk "$target_disk"; then target_disk_deleted=PASS; target_disk_owned=false; else target_disk_deleted=FAIL; code=$EXIT_CLEANUP; fi
  fi
  if [[ "$source_disk_owned" == true ]]; then
    if delete_disk "$source_disk"; then source_disk_deleted=PASS; source_disk_owned=false; else source_disk_deleted=FAIL; code=$EXIT_CLEANUP; fi
  fi
  if [[ "$staging_owned" == true ]]; then
    if gcloud storage rm --recursive "$staging_uri" >/dev/null 2>&1 && ! gcloud storage ls "$staging_uri" >/dev/null 2>&1; then
      staging_object_deleted=PASS; staging_owned=false
    else staging_object_deleted=FAIL; code=$EXIT_CLEANUP; fi
  fi
  return "$code"
}

write_receipt() {
  local cleanup_status=FAIL
  if cleanup_value_complete "$source_vm_deleted" && cleanup_value_complete "$replacement_target_vm_deleted" \
      && cleanup_value_complete "$rollback_vm_deleted" && cleanup_value_complete "$source_disk_deleted" \
      && cleanup_value_complete "$target_disk_deleted" && cleanup_value_complete "$staging_object_deleted"; then cleanup_status=PASS; fi
  printf 'sourceCommit=%s\nprofile=%s\nslot=%s\nrunStatus=%s\nsourceVmDeleted=%s\nreplacementTargetVmDeleted=%s\nrollbackVmDeleted=%s\nsourceDiskDeleted=%s\ntargetDiskDeleted=%s\nstagingObjectDeleted=%s\ncleanup=%s\n' \
    "$GSE_V42_SOURCE_SHA" "$GSE_V42_PROFILE" "$GSE_V42_SLOT" "$run_status" \
    "$source_vm_deleted" "$replacement_target_vm_deleted" "$rollback_vm_deleted" \
    "$source_disk_deleted" "$target_disk_deleted" "$staging_object_deleted" "$cleanup_status" \
    > "$output/cloud-member.properties"
}

bound_log() { [[ ! -f "$1" ]] || { tail -c 16384 "$1" > "$1.bounded" 2>/dev/null || true; mv "$1.bounded" "$1"; }; }
sanitize_output() {
  rm -rf "$output/source-migration-output" "$output/target-output" "$output/rollback-output"
  rm -f "$output"/*.tar.gz "$output/gcs-permission"*
  bound_log "$output/source-remote.log"
  bound_log "$output/target-remote.log"
  bound_log "$output/rollback-remote.log"
}
finalize() {
  local primary=$? cleanup_code=0
  trap - EXIT
  cleanup || cleanup_code=$?
  mkdir -p "$output" || true
  sanitize_output || true
  write_receipt || true
  if [[ $primary -ne 0 ]]; then exit "$primary"; fi
  if [[ $cleanup_code -ne 0 ]]; then exit "$EXIT_CLEANUP"; fi
}
trap finalize EXIT

wait_for_ssh() {
  local vm=$1 deadline=$((SECONDS + 180))
  until gcloud compute ssh "$vm" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --command=true --quiet >/dev/null 2>&1; do
    [[ $SECONDS -lt $deadline ]] || return 1
    sleep 5
  done
}
create_disk() { gcloud compute disks create "$1" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --type=pd-balanced --size=200GB --quiet; }
create_vm() {
  local vm=$1; shift
  local disks=()
  while [[ $# -gt 0 ]]; do disks+=(--disk="name=$1,device-name=$2,mode=rw,boot=no,auto-delete=no"); shift 2; done
  gcloud compute instances create "$vm" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" \
    --machine-type="$machine_type" --provisioning-model=STANDARD --image-project=ubuntu-os-cloud \
    --image="$GSE_V42_CLOUD_IMAGE" --boot-disk-size=100GB --boot-disk-type=pd-balanced \
    --boot-disk-auto-delete "${disks[@]}" --no-service-account --no-scopes \
    --max-run-duration=5400s --instance-termination-action=DELETE \
    --metadata=block-project-ssh-keys=TRUE,enable-oslogin=FALSE \
    --labels="purpose=gse-v42-evolution,slot=$GSE_V42_SLOT" --quiet
}

probe="$output/gcs-permission-probe.txt"
readback="$output/gcs-permission-readback.txt"
probe_uri="$staging_uri/permission-probe.txt"
printf 'v42-storage-evolution\nsource=%s\nrun=%s\nslot=%s\n' "$GSE_V42_SOURCE_SHA" "$GSE_V42_RUN_ID" "$GSE_V42_SLOT" > "$probe"
gcloud storage cp "$probe" "$probe_uri" >/dev/null || exit "$EXIT_CONFIG"
staging_owned=true
gcloud storage cp "$probe_uri" "$readback" >/dev/null || exit "$EXIT_CONFIG"
cmp -s "$probe" "$readback" || exit "$EXIT_CONFIG"
gcloud storage rm "$probe_uri" >/dev/null || exit "$EXIT_CONFIG"
! gcloud storage objects describe "$probe_uri" >/dev/null 2>&1 || exit "$EXIT_CONFIG"
staging_owned=false
staging_object_deleted=PASS
rm -f "$probe" "$readback"
echo "v42GcsPermissionProbe=PASS"

for vm in "$source_vm" "$replacement_target_vm" "$rollback_vm"; do
  ! gcloud compute instances describe "$vm" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" >/dev/null 2>&1 || { echo "ERROR: pre-existing VM $vm" >&2; exit "$EXIT_PROVISION"; }
done
for disk in "$source_disk" "$target_disk"; do
  ! gcloud compute disks describe "$disk" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" >/dev/null 2>&1 || { echo "ERROR: pre-existing disk $disk" >&2; exit "$EXIT_PROVISION"; }
done

if create_disk "$source_disk"; then
  source_disk_owned=true
else
  gcloud compute disks describe "$source_disk" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" >/dev/null 2>&1 && source_disk_owned=true
  exit "$EXIT_PROVISION"
fi
if create_disk "$target_disk"; then
  target_disk_owned=true
else
  gcloud compute disks describe "$target_disk" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" >/dev/null 2>&1 && target_disk_owned=true
  exit "$EXIT_PROVISION"
fi
if create_vm "$source_vm" "$source_disk" gse-v42-source "$target_disk" gse-v42-target; then
  source_vm_owned=true
else
  gcloud compute instances describe "$source_vm" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" >/dev/null 2>&1 && source_vm_owned=true
  exit "$EXIT_PROVISION"
fi
wait_for_ssh "$source_vm" || exit "$EXIT_REMOTE"
gcloud compute scp scripts/v42/remote_storage_evolution_stage.sh "$source_vm:~/" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
source_mount="$mount_root/source"
source_command=$(printf 'bash ~/remote_storage_evolution_stage.sh source-migrate %q production %q %q %q %q - %q' \
  "$GSE_V42_SOURCE_SHA" "$GSE_V42_DURATION_SECONDS" "$mount_root" \
  /dev/disk/by-id/google-gse-v42-source /dev/disk/by-id/google-gse-v42-target \
  "$source_mount/source-migration-output")
gcloud compute ssh "$source_vm" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --command="$source_command" --quiet > "$output/source-remote.log" 2>&1 || exit "$EXIT_REMOTE"
gcloud compute scp "$source_vm:~/v42-source-migration-output.tar.gz" "$output/" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --quiet || exit "$EXIT_COLLECTION"
tar -xzf "$output/v42-source-migration-output.tar.gz" -C "$output" || exit "$EXIT_COLLECTION"
python3 -m scripts.v41.backup_format inspect \
  "$output/source-migration-output/backup" || exit "$EXIT_COLLECTION"
delete_instance "$source_vm" || exit "$EXIT_CLEANUP"
source_vm_deleted=PASS; source_vm_owned=false

if create_vm "$replacement_target_vm" "$target_disk" gse-v42-target; then
  replacement_target_vm_owned=true
else
  gcloud compute instances describe "$replacement_target_vm" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" >/dev/null 2>&1 && replacement_target_vm_owned=true
  exit "$EXIT_PROVISION"
fi
wait_for_ssh "$replacement_target_vm" || exit "$EXIT_REMOTE"
gcloud compute scp scripts/v42/remote_storage_evolution_stage.sh "$replacement_target_vm:~/" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
gcloud compute ssh "$replacement_target_vm" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --command='mkdir -p ~/v42-transport' --quiet || exit "$EXIT_REMOTE"
gcloud compute scp "$output/source-migration-output/migration.properties" "$replacement_target_vm:~/v42-transport/" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
target_command=$(printf 'bash ~/remote_storage_evolution_stage.sh target %q production %q %q - %q %s %q' \
  "$GSE_V42_SOURCE_SHA" "$GSE_V42_DURATION_SECONDS" "$mount_root" \
  /dev/disk/by-id/google-gse-v42-target '$HOME/v42-transport' "$mount_root/target/target-output")
gcloud compute ssh "$replacement_target_vm" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --command="$target_command" --quiet > "$output/target-remote.log" 2>&1 || exit "$EXIT_REMOTE"
gcloud compute scp "$replacement_target_vm:~/v42-target-output.tar.gz" "$output/" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --quiet || exit "$EXIT_COLLECTION"
tar -xzf "$output/v42-target-output.tar.gz" -C "$output" || exit "$EXIT_COLLECTION"
delete_instance "$replacement_target_vm" || exit "$EXIT_CLEANUP"
replacement_target_vm_deleted=PASS; replacement_target_vm_owned=false

if create_vm "$rollback_vm" "$source_disk" gse-v42-source; then
  rollback_vm_owned=true
else
  gcloud compute instances describe "$rollback_vm" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" >/dev/null 2>&1 && rollback_vm_owned=true
  exit "$EXIT_PROVISION"
fi
wait_for_ssh "$rollback_vm" || exit "$EXIT_REMOTE"
gcloud compute scp scripts/v42/remote_storage_evolution_stage.sh "$rollback_vm:~/" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
gcloud compute ssh "$rollback_vm" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --command='mkdir -p ~/v42-transport' --quiet || exit "$EXIT_REMOTE"
gcloud compute scp "$output/source-migration-output/source.properties" "$rollback_vm:~/v42-transport/" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
rollback_command=$(printf 'bash ~/remote_storage_evolution_stage.sh rollback %q production %q %q %q - %s %q' \
  "$GSE_V42_SOURCE_SHA" "$GSE_V42_DURATION_SECONDS" "$mount_root" \
  /dev/disk/by-id/google-gse-v42-source '$HOME/v42-transport' "$mount_root/source/rollback-output")
gcloud compute ssh "$rollback_vm" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --command="$rollback_command" --quiet > "$output/rollback-remote.log" 2>&1 || exit "$EXIT_REMOTE"
gcloud compute scp "$rollback_vm:~/v42-rollback-output.tar.gz" "$output/" --project="$GSE_V42_GCP_PROJECT" --zone="$GSE_V42_GCP_ZONE" --quiet || exit "$EXIT_COLLECTION"
tar -xzf "$output/v42-rollback-output.tar.gz" -C "$output" || exit "$EXIT_COLLECTION"
delete_instance "$rollback_vm" || exit "$EXIT_CLEANUP"
rollback_vm_deleted=PASS; rollback_vm_owned=false
delete_disk "$target_disk" || exit "$EXIT_CLEANUP"
target_disk_deleted=PASS; target_disk_owned=false
delete_disk "$source_disk" || exit "$EXIT_CLEANUP"
source_disk_deleted=PASS; source_disk_owned=false

python3 -m scripts.v42.migration_performance assemble \
  --source-sha "$GSE_V42_SOURCE_SHA" --source-state clean \
  --profile "$GSE_V42_PROFILE" --java-profile production \
  --duration-seconds "$GSE_V42_DURATION_SECONDS" --slot "$GSE_V42_SLOT" \
  --source-properties "$output/source-migration-output/source.properties" \
  --migration-properties "$output/source-migration-output/migration.properties" \
  --target-properties "$output/target-output/target.properties" \
  --rollback-properties "$output/rollback-output/rollback.properties" \
  --backup "$output/source-migration-output/backup" --output "$output/evidence" \
  --stdout-log "$output/source-remote.log" --stderr-log "$output/target-remote.log" \
  --source-vm-deleted --replacement-target-vm-deleted --rollback-vm-deleted \
  --source-disk-deleted --target-disk-deleted --staging-object-deleted \
  || exit "$EXIT_COLLECTION"
python3 -m scripts.v42.migration_performance validate "$output/evidence" || exit "$EXIT_COLLECTION"

sanitize_output
run_status=PASS
write_receipt
echo "v42CloudMember=PASS profile=$GSE_V42_PROFILE slot=$GSE_V42_SLOT"
