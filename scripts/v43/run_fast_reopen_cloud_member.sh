#!/usr/bin/env bash
set -euo pipefail

readonly EXIT_CONFIG=2 EXIT_PROVISION=10 EXIT_REMOTE=20 EXIT_COLLECTION=30 EXIT_CLEANUP=40
confirm=false
if [[ "${1:-}" = --confirm-paid-run && $# -eq 1 ]]; then confirm=true
elif [[ "${1:-}" != --dry-run || $# -ne 1 ]]; then
  echo "usage: run_fast_reopen_cloud_member.sh --dry-run|--confirm-paid-run" >&2; exit "$EXIT_CONFIG"
fi
required=(GSE_V43_GCP_PROJECT GSE_V43_GCP_ZONE GSE_V43_CLOUD_IMAGE
  GSE_V43_GCS_BUCKET GSE_V43_SOURCE_SHA GSE_V43_RUN_ID GSE_V43_RUN_ATTEMPT
  GSE_V43_SLOT GSE_V43_PROFILE GSE_V43_DURATION_SECONDS GSE_V43_OUTPUT)
for variable in "${required[@]}"; do [[ -n "${!variable:-}" ]] || { echo "ERROR: $variable is required" >&2; exit "$EXIT_CONFIG"; }; done
[[ "$GSE_V43_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || exit "$EXIT_CONFIG"
[[ "$GSE_V43_RUN_ID" =~ ^[0-9]+$ && "$GSE_V43_RUN_ATTEMPT" =~ ^[1-9][0-9]*$ ]] || exit "$EXIT_CONFIG"
case "$GSE_V43_PROFILE" in experiment|canonical|failure-drill) ;; *) exit "$EXIT_CONFIG" ;; esac
[[ "$GSE_V43_DURATION_SECONDS" = 1800 ]] || exit "$EXIT_CONFIG"
if [[ "$GSE_V43_PROFILE" = canonical ]]; then [[ "$GSE_V43_SLOT" =~ ^[123]$ ]] || exit "$EXIT_CONFIG"
else [[ "$GSE_V43_SLOT" = 1 ]] || exit "$EXIT_CONFIG"; fi
[[ "$GSE_V43_GCS_BUCKET" =~ ^gs://[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$ ]] || exit "$EXIT_CONFIG"
machine=${GSE_V43_MACHINE_TYPE:-c3d-standard-30}; [[ "$machine" = c3d-standard-30 ]] || exit "$EXIT_CONFIG"
prefix="gse-v43-${GSE_V43_RUN_ID}-${GSE_V43_RUN_ATTEMPT}-${GSE_V43_SLOT}"; prefix=${prefix:0:48}
source_vm="$prefix-source"; replacement_vm="$prefix-replace"
primary_disk="$prefix-primary"; target_disk="$prefix-target"
mount_root=/mnt/gse-v43-fast-reopen
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
output=$(realpath -m "$GSE_V43_OUTPUT")
[[ "$output" = "$repo_root"/* || "$output" = /tmp/* ]] || exit "$EXIT_CONFIG"
staging_uri="${GSE_V43_GCS_BUCKET}/v4.3-fast-reopen/${GSE_V43_SOURCE_SHA}/${GSE_V43_RUN_ID}-${GSE_V43_RUN_ATTEMPT}/${GSE_V43_PROFILE}/member-${GSE_V43_SLOT}/transport"
printf '%s\n' "V4.3 fast-reopen member plan" \
  "  source:       $GSE_V43_SOURCE_SHA" "  profile:      $GSE_V43_PROFILE" \
  "  project:      $GSE_V43_GCP_PROJECT" "  zone:         $GSE_V43_GCP_ZONE" \
  "  machine:      $machine" "  image:        $GSE_V43_CLOUD_IMAGE" \
  "  primary disk: $primary_disk (pd-balanced, 200 GiB)" \
  "  target disk:  $target_disk (pd-balanced, 200 GiB)" \
  "  boot disk:    auto-delete pd-balanced, 100 GiB" \
  "  peak disks:   400 GiB data / 500 GiB including boot" \
  "  duration:     $GSE_V43_DURATION_SECONDS seconds" \
  "  published:    GeneralSearchEngine 4.2.0" "  staging:      $staging_uri"
if [[ "$confirm" = false ]]; then echo "v43CloudMemberDryRun=PASS"; exit 0; fi

command -v gcloud >/dev/null || exit "$EXIT_CONFIG"; mkdir -p "$output"
run_status=FAIL; source_vm_deleted=NOT_APPLICABLE; replacement_vm_deleted=NOT_APPLICABLE
primary_disk_deleted=NOT_APPLICABLE; target_disk_deleted=NOT_APPLICABLE; staging_object_deleted=NOT_APPLICABLE
source_vm_owned=false; replacement_vm_owned=false; primary_disk_owned=false; target_disk_owned=false; staging_owned=false
delete_instance() {
  local name=$1
  if gcloud compute instances describe "$name" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" >/dev/null 2>&1; then
    gcloud compute instances delete "$name" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" --quiet >/dev/null
  fi
  ! gcloud compute instances describe "$name" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" >/dev/null 2>&1
}
delete_disk() {
  local name=$1
  if gcloud compute disks describe "$name" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" >/dev/null 2>&1; then
    local deleted=false
    for _ in 1 2 3 4 5; do
      if gcloud compute disks delete "$name" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" --quiet >/dev/null 2>&1; then deleted=true; break; fi
      sleep 3
    done
    [[ "$deleted" = true ]] || return 1
  fi
  ! gcloud compute disks describe "$name" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" >/dev/null 2>&1
}
complete() { [[ "$1" = PASS || "$1" = NOT_APPLICABLE ]]; }
write_receipt() {
  local cleanup=FAIL
  if complete "$source_vm_deleted" && complete "$replacement_vm_deleted" \
      && complete "$primary_disk_deleted" && complete "$target_disk_deleted" \
      && complete "$staging_object_deleted"; then cleanup=PASS; fi
  printf 'sourceCommit=%s\nprofile=%s\nslot=%s\nrunStatus=%s\nsourceVmDeleted=%s\nreplacementVmDeleted=%s\nprimaryDiskDeleted=%s\ntargetDiskDeleted=%s\nstagingObjectDeleted=%s\ncleanup=%s\n' \
    "$GSE_V43_SOURCE_SHA" "$GSE_V43_PROFILE" "$GSE_V43_SLOT" "$run_status" \
    "$source_vm_deleted" "$replacement_vm_deleted" "$primary_disk_deleted" \
    "$target_disk_deleted" "$staging_object_deleted" "$cleanup" > "$output/cloud-member.properties"
}
cleanup() {
  local code=0
  if [[ "$source_vm_owned" = true ]]; then delete_instance "$source_vm" && { source_vm_deleted=PASS; source_vm_owned=false; } || { source_vm_deleted=FAIL; code=$EXIT_CLEANUP; }; fi
  if [[ "$replacement_vm_owned" = true ]]; then delete_instance "$replacement_vm" && { replacement_vm_deleted=PASS; replacement_vm_owned=false; } || { replacement_vm_deleted=FAIL; code=$EXIT_CLEANUP; }; fi
  if [[ "$target_disk_owned" = true ]]; then delete_disk "$target_disk" && { target_disk_deleted=PASS; target_disk_owned=false; } || { target_disk_deleted=FAIL; code=$EXIT_CLEANUP; }; fi
  if [[ "$primary_disk_owned" = true ]]; then delete_disk "$primary_disk" && { primary_disk_deleted=PASS; primary_disk_owned=false; } || { primary_disk_deleted=FAIL; code=$EXIT_CLEANUP; }; fi
  if [[ "$staging_owned" = true ]]; then
    if gcloud storage rm --recursive "$staging_uri" >/dev/null 2>&1 && ! gcloud storage ls "$staging_uri" >/dev/null 2>&1; then staging_object_deleted=PASS; staging_owned=false
    else staging_object_deleted=FAIL; code=$EXIT_CLEANUP; fi
  fi
  return "$code"
}
bound_log() { [[ ! -f "$1" ]] || { tail -c 16384 "$1" > "$1.bounded" 2>/dev/null || true; mv "$1.bounded" "$1"; }; }
sanitize() { rm -rf "$output/source-output" "$output/replacement-output"; rm -f "$output"/*.tar.gz "$output"/gcs-*; bound_log "$output/source-remote.log"; bound_log "$output/replacement-remote.log"; }
finalize() {
  local primary=$? cleanup_code=0; trap - EXIT; cleanup || cleanup_code=$?
  mkdir -p "$output" || true; sanitize || true; write_receipt || true
  if [[ $primary -ne 0 ]]; then exit "$primary"; fi
  if [[ $cleanup_code -ne 0 ]]; then exit "$EXIT_CLEANUP"; fi
}
trap finalize EXIT
wait_ssh() { local vm=$1 deadline=$((SECONDS + 180)); until gcloud compute ssh "$vm" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" --command=true --quiet >/dev/null 2>&1; do [[ $SECONDS -lt $deadline ]] || return 1; sleep 5; done; }
create_disk() { gcloud compute disks create "$1" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" --type=pd-balanced --size=200GB --quiet; }
create_vm() {
  local vm=$1
  gcloud compute instances create "$vm" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" \
    --machine-type="$machine" --provisioning-model=STANDARD --image-project=ubuntu-os-cloud \
    --image="$GSE_V43_CLOUD_IMAGE" --boot-disk-size=100GB --boot-disk-type=pd-balanced \
    --boot-disk-auto-delete \
    --disk="name=$primary_disk,device-name=gse-v43-primary,mode=rw,boot=no,auto-delete=no" \
    --disk="name=$target_disk,device-name=gse-v43-target,mode=rw,boot=no,auto-delete=no" \
    --no-service-account --no-scopes --max-run-duration=5400s --instance-termination-action=DELETE \
    --metadata=block-project-ssh-keys=TRUE,enable-oslogin=FALSE \
    --labels="purpose=gse-v43-reopen,slot=$GSE_V43_SLOT" --quiet
}

probe="$output/gcs-permission-probe.txt"; readback="$output/gcs-permission-readback.txt"; probe_uri="$staging_uri/permission-probe.txt"
printf 'v43-fast-reopen\nsource=%s\nrun=%s\nslot=%s\n' "$GSE_V43_SOURCE_SHA" "$GSE_V43_RUN_ID" "$GSE_V43_SLOT" > "$probe"
gcloud storage cp "$probe" "$probe_uri" >/dev/null || exit "$EXIT_CONFIG"; staging_owned=true
gcloud storage cp "$probe_uri" "$readback" >/dev/null || exit "$EXIT_CONFIG"; cmp -s "$probe" "$readback" || exit "$EXIT_CONFIG"
gcloud storage rm "$probe_uri" >/dev/null || exit "$EXIT_CONFIG"; ! gcloud storage objects describe "$probe_uri" >/dev/null 2>&1 || exit "$EXIT_CONFIG"
staging_owned=false; staging_object_deleted=PASS; rm -f "$probe" "$readback"; echo "v43GcsPermissionProbe=PASS"
for vm in "$source_vm" "$replacement_vm"; do ! gcloud compute instances describe "$vm" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" >/dev/null 2>&1 || exit "$EXIT_PROVISION"; done
for disk in "$primary_disk" "$target_disk"; do ! gcloud compute disks describe "$disk" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" >/dev/null 2>&1 || exit "$EXIT_PROVISION"; done

if create_disk "$primary_disk"; then primary_disk_owned=true; else gcloud compute disks describe "$primary_disk" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" >/dev/null 2>&1 && primary_disk_owned=true; exit "$EXIT_PROVISION"; fi
if create_disk "$target_disk"; then target_disk_owned=true; else gcloud compute disks describe "$target_disk" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" >/dev/null 2>&1 && target_disk_owned=true; exit "$EXIT_PROVISION"; fi
if create_vm "$source_vm"; then source_vm_owned=true; else gcloud compute instances describe "$source_vm" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" >/dev/null 2>&1 && source_vm_owned=true; exit "$EXIT_PROVISION"; fi
wait_ssh "$source_vm" || exit "$EXIT_REMOTE"
gcloud compute scp scripts/v43/remote_fast_reopen_stage.sh "$source_vm:~/" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
source_command=$(printf 'bash ~/remote_fast_reopen_stage.sh source %q production %q %q %q %q - %q' "$GSE_V43_SOURCE_SHA" "$GSE_V43_DURATION_SECONDS" "$mount_root" /dev/disk/by-id/google-gse-v43-primary /dev/disk/by-id/google-gse-v43-target "$mount_root/primary/source-output")
gcloud compute ssh "$source_vm" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" --command="$source_command" --quiet > "$output/source-remote.log" 2>&1 || exit "$EXIT_REMOTE"
gcloud compute scp "$source_vm:~/v43-source-output.tar.gz" "$output/" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" --quiet || exit "$EXIT_COLLECTION"
tar -xzf "$output/v43-source-output.tar.gz" -C "$output" || exit "$EXIT_COLLECTION"
python3 -m scripts.v43.derived_format_v12 inspect-backup "$output/source-output/backup" || exit "$EXIT_COLLECTION"
delete_instance "$source_vm" || exit "$EXIT_CLEANUP"; source_vm_deleted=PASS; source_vm_owned=false

if create_vm "$replacement_vm"; then replacement_vm_owned=true; else gcloud compute instances describe "$replacement_vm" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" >/dev/null 2>&1 && replacement_vm_owned=true; exit "$EXIT_PROVISION"; fi
wait_ssh "$replacement_vm" || exit "$EXIT_REMOTE"
gcloud compute scp scripts/v43/remote_fast_reopen_stage.sh "$replacement_vm:~/" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
gcloud compute ssh "$replacement_vm" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" --command='mkdir -p ~/v43-transport' --quiet || exit "$EXIT_REMOTE"
gcloud compute scp "$output/source-output/source.properties" "$replacement_vm:~/v43-transport/" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
replacement_command=$(printf 'bash ~/remote_fast_reopen_stage.sh replacement %q production %q %q %q %q %s %q' "$GSE_V43_SOURCE_SHA" "$GSE_V43_DURATION_SECONDS" "$mount_root" /dev/disk/by-id/google-gse-v43-primary /dev/disk/by-id/google-gse-v43-target '$HOME/v43-transport' "$mount_root/primary/replacement-output")
gcloud compute ssh "$replacement_vm" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" --command="$replacement_command" --quiet > "$output/replacement-remote.log" 2>&1 || exit "$EXIT_REMOTE"
gcloud compute scp "$replacement_vm:~/v43-replacement-output.tar.gz" "$output/" --project="$GSE_V43_GCP_PROJECT" --zone="$GSE_V43_GCP_ZONE" --quiet || exit "$EXIT_COLLECTION"
tar -xzf "$output/v43-replacement-output.tar.gz" -C "$output" || exit "$EXIT_COLLECTION"
delete_instance "$replacement_vm" || exit "$EXIT_CLEANUP"; replacement_vm_deleted=PASS; replacement_vm_owned=false
delete_disk "$target_disk" || exit "$EXIT_CLEANUP"; target_disk_deleted=PASS; target_disk_owned=false
delete_disk "$primary_disk" || exit "$EXIT_CLEANUP"; primary_disk_deleted=PASS; primary_disk_owned=false

python3 -m scripts.v43.fast_reopen_performance assemble \
  --source-sha "$GSE_V43_SOURCE_SHA" --source-state clean --profile "$GSE_V43_PROFILE" \
  --java-profile production --duration-seconds "$GSE_V43_DURATION_SECONDS" --slot "$GSE_V43_SLOT" \
  --published-properties "$output/source-output/published.properties" \
  --source-properties "$output/source-output/source.properties" \
  --replacement-properties "$output/replacement-output/replacement.properties" \
  --backup "$output/source-output/backup" --output "$output/evidence" \
  --stdout-log "$output/source-remote.log" --stderr-log "$output/replacement-remote.log" \
  --source-vm-deleted --replacement-vm-deleted --primary-disk-deleted \
  --target-disk-deleted --staging-object-deleted || exit "$EXIT_COLLECTION"
python3 -m scripts.v43.fast_reopen_performance validate "$output/evidence" || exit "$EXIT_COLLECTION"
sanitize; run_status=PASS; write_receipt
echo "v43CloudMember=PASS profile=$GSE_V43_PROFILE slot=$GSE_V43_SLOT"
