#!/usr/bin/env bash
set -euo pipefail

readonly EXIT_CONFIG=2 EXIT_PROVISION=10 EXIT_REMOTE=20 EXIT_COLLECTION=30 EXIT_CLEANUP=40
confirm=false
if [[ "${1:-}" = --confirm-paid-run && $# -eq 1 ]]; then confirm=true
elif [[ "${1:-}" != --dry-run || $# -ne 1 ]]; then
  echo "usage: run_final_durable_cloud_member.sh --dry-run|--confirm-paid-run" >&2; exit "$EXIT_CONFIG"
fi
required=(GSE_V44_GCP_PROJECT GSE_V44_GCP_ZONE GSE_V44_CLOUD_IMAGE
  GSE_V44_GCS_BUCKET GSE_V44_SOURCE_SHA GSE_V44_RUN_ID GSE_V44_RUN_ATTEMPT
  GSE_V44_SLOT GSE_V44_PROFILE GSE_V44_DURATION_SECONDS GSE_V44_OUTPUT)
for variable in "${required[@]}"; do [[ -n "${!variable:-}" ]] || { echo "ERROR: $variable is required" >&2; exit "$EXIT_CONFIG"; }; done
[[ "$GSE_V44_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || exit "$EXIT_CONFIG"
[[ "$GSE_V44_RUN_ID" =~ ^[0-9]+$ && "$GSE_V44_RUN_ATTEMPT" =~ ^[1-9][0-9]*$ ]] || exit "$EXIT_CONFIG"
case "$GSE_V44_PROFILE" in experiment|canonical|failure-drill) ;; *) exit "$EXIT_CONFIG" ;; esac
[[ "$GSE_V44_DURATION_SECONDS" = 3600 ]] || exit "$EXIT_CONFIG"
if [[ "$GSE_V44_PROFILE" = canonical ]]; then [[ "$GSE_V44_SLOT" =~ ^[123]$ ]] || exit "$EXIT_CONFIG"
else [[ "$GSE_V44_SLOT" = 1 ]] || exit "$EXIT_CONFIG"; fi
[[ "$GSE_V44_GCS_BUCKET" =~ ^gs://[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$ ]] || exit "$EXIT_CONFIG"
[[ "$GSE_V44_GCP_PROJECT" == gse-benchmark \
    && "$GSE_V44_GCP_ZONE" == us-west4-a \
    && "$GSE_V44_CLOUD_IMAGE" == ubuntu-2404-noble-amd64-v20260906 ]] \
    || exit "$EXIT_CONFIG"
machine=${GSE_V44_MACHINE_TYPE:-c3d-standard-30}; [[ "$machine" = c3d-standard-30 ]] || exit "$EXIT_CONFIG"
prefix="gse-v44-${GSE_V44_RUN_ID}-${GSE_V44_RUN_ATTEMPT}-${GSE_V44_SLOT}"; prefix=${prefix:0:48}
source_vm="$prefix-source"; replacement_vm="$prefix-replace"
data_disk="$prefix-data"; target_disk="$prefix-target"
mount_root=/mnt/gse-v44-final-durable
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
output=$(realpath -m "$GSE_V44_OUTPUT")
[[ "$output" = "$repo_root"/* || "$output" = /tmp/* ]] || exit "$EXIT_CONFIG"
staging_uri="${GSE_V44_GCS_BUCKET}/v4.4-final-durable/${GSE_V44_SOURCE_SHA}/${GSE_V44_RUN_ID}-${GSE_V44_RUN_ATTEMPT}/${GSE_V44_PROFILE}/member-${GSE_V44_SLOT}/transport"
printf '%s\n' "V4.4 final-durable member plan" \
  "  source:       $GSE_V44_SOURCE_SHA" "  profile:      $GSE_V44_PROFILE" \
  "  project:      $GSE_V44_GCP_PROJECT" "  zone:         $GSE_V44_GCP_ZONE" \
  "  machine:      $machine" "  image:        $GSE_V44_CLOUD_IMAGE" \
  "  data disk:    $data_disk (pd-balanced, 200 GiB)" \
  "  target disk:  $target_disk (pd-balanced, 200 GiB)" \
  "  boot disk:    auto-delete pd-balanced, 100 GiB" \
  "  peak disks:   400 GiB data / 500 GiB including boot" \
  "  duration:     $GSE_V44_DURATION_SECONDS seconds" \
  "  published:    GeneralSearchEngine 4.3.0" "  staging:      $staging_uri"
if [[ "$confirm" = false ]]; then echo "v44CloudMemberDryRun=PASS"; exit 0; fi

command -v gcloud >/dev/null || exit "$EXIT_CONFIG"; mkdir -p "$output"
run_status=FAIL; source_vm_deleted=NOT_APPLICABLE; replacement_vm_deleted=NOT_APPLICABLE
data_disk_deleted=NOT_APPLICABLE; target_disk_deleted=NOT_APPLICABLE; staging_object_deleted=NOT_APPLICABLE
source_vm_owned=false; replacement_vm_owned=false; data_disk_owned=false; target_disk_owned=false; staging_owned=false
delete_instance() {
  local name=$1
  if gcloud compute instances describe "$name" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" >/dev/null 2>&1; then
    gcloud compute instances delete "$name" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" --quiet >/dev/null
  fi
  ! gcloud compute instances describe "$name" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" >/dev/null 2>&1
}
delete_disk() {
  local name=$1
  if gcloud compute disks describe "$name" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" >/dev/null 2>&1; then
    local deleted=false
    for _ in 1 2 3 4 5; do
      if gcloud compute disks delete "$name" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" --quiet >/dev/null 2>&1; then deleted=true; break; fi
      sleep 3
    done
    [[ "$deleted" = true ]] || return 1
  fi
  ! gcloud compute disks describe "$name" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" >/dev/null 2>&1
}
complete() { [[ "$1" = PASS || "$1" = NOT_APPLICABLE ]]; }
write_receipt() {
  local cleanup=FAIL
  if complete "$source_vm_deleted" && complete "$replacement_vm_deleted" \
      && complete "$data_disk_deleted" && complete "$target_disk_deleted" \
      && complete "$staging_object_deleted"; then cleanup=PASS; fi
  printf 'sourceCommit=%s\nprofile=%s\nslot=%s\nrunStatus=%s\nsourceVmDeleted=%s\nreplacementVmDeleted=%s\ndataDiskDeleted=%s\ntargetDiskDeleted=%s\nstagingObjectDeleted=%s\ncleanup=%s\n' \
    "$GSE_V44_SOURCE_SHA" "$GSE_V44_PROFILE" "$GSE_V44_SLOT" "$run_status" \
    "$source_vm_deleted" "$replacement_vm_deleted" "$data_disk_deleted" \
    "$target_disk_deleted" "$staging_object_deleted" "$cleanup" > "$output/cloud-member.properties"
}
cleanup() {
  local code=0
  if [[ "$source_vm_owned" = true ]]; then delete_instance "$source_vm" && { source_vm_deleted=PASS; source_vm_owned=false; } || { source_vm_deleted=FAIL; code=$EXIT_CLEANUP; }; fi
  if [[ "$replacement_vm_owned" = true ]]; then delete_instance "$replacement_vm" && { replacement_vm_deleted=PASS; replacement_vm_owned=false; } || { replacement_vm_deleted=FAIL; code=$EXIT_CLEANUP; }; fi
  if [[ "$target_disk_owned" = true ]]; then delete_disk "$target_disk" && { target_disk_deleted=PASS; target_disk_owned=false; } || { target_disk_deleted=FAIL; code=$EXIT_CLEANUP; }; fi
  if [[ "$data_disk_owned" = true ]]; then delete_disk "$data_disk" && { data_disk_deleted=PASS; data_disk_owned=false; } || { data_disk_deleted=FAIL; code=$EXIT_CLEANUP; }; fi
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
wait_ssh() { local vm=$1 deadline=$((SECONDS + 180)); until gcloud compute ssh "$vm" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" --command=true --quiet >/dev/null 2>&1; do [[ $SECONDS -lt $deadline ]] || return 1; sleep 5; done; }
create_disk() { gcloud compute disks create "$1" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" --type=pd-balanced --size=200GB --quiet; }
create_vm() {
  local vm=$1
  gcloud compute instances create "$vm" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" \
    --machine-type="$machine" --provisioning-model=STANDARD --image-project=ubuntu-os-cloud \
    --image="$GSE_V44_CLOUD_IMAGE" --boot-disk-size=100GB --boot-disk-type=pd-balanced \
    --boot-disk-auto-delete \
    --disk="name=$data_disk,device-name=gse-v44-data,mode=rw,boot=no,auto-delete=no" \
    --disk="name=$target_disk,device-name=gse-v44-target,mode=rw,boot=no,auto-delete=no" \
    --no-service-account --no-scopes --max-run-duration=10800s --instance-termination-action=DELETE \
    --metadata=block-project-ssh-keys=TRUE,enable-oslogin=FALSE \
    --labels="purpose=gse-v44-final,slot=$GSE_V44_SLOT" --quiet
}

probe="$output/gcs-permission-probe.txt"; readback="$output/gcs-permission-readback.txt"; probe_uri="$staging_uri/permission-probe.txt"
printf 'v44-final-durable\nsource=%s\nrun=%s\nslot=%s\n' "$GSE_V44_SOURCE_SHA" "$GSE_V44_RUN_ID" "$GSE_V44_SLOT" > "$probe"
gcloud storage cp "$probe" "$probe_uri" >/dev/null || exit "$EXIT_CONFIG"; staging_owned=true
gcloud storage cp "$probe_uri" "$readback" >/dev/null || exit "$EXIT_CONFIG"; cmp -s "$probe" "$readback" || exit "$EXIT_CONFIG"
gcloud storage rm "$probe_uri" >/dev/null || exit "$EXIT_CONFIG"; ! gcloud storage objects describe "$probe_uri" >/dev/null 2>&1 || exit "$EXIT_CONFIG"
staging_owned=false; staging_object_deleted=PASS; rm -f "$probe" "$readback"; echo "v44GcsPermissionProbe=PASS"
for vm in "$source_vm" "$replacement_vm"; do ! gcloud compute instances describe "$vm" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" >/dev/null 2>&1 || exit "$EXIT_PROVISION"; done
for disk in "$data_disk" "$target_disk"; do ! gcloud compute disks describe "$disk" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" >/dev/null 2>&1 || exit "$EXIT_PROVISION"; done

if create_disk "$data_disk"; then data_disk_owned=true; else gcloud compute disks describe "$data_disk" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" >/dev/null 2>&1 && data_disk_owned=true; exit "$EXIT_PROVISION"; fi
if create_disk "$target_disk"; then target_disk_owned=true; else gcloud compute disks describe "$target_disk" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" >/dev/null 2>&1 && target_disk_owned=true; exit "$EXIT_PROVISION"; fi
if create_vm "$source_vm"; then source_vm_owned=true; else gcloud compute instances describe "$source_vm" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" >/dev/null 2>&1 && source_vm_owned=true; exit "$EXIT_PROVISION"; fi
wait_ssh "$source_vm" || exit "$EXIT_REMOTE"
gcloud compute scp scripts/v44/remote_final_durable_stage.sh "$source_vm:~/" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
source_command=$(printf 'bash ~/remote_final_durable_stage.sh source %q production %q %q %q %q - %q' "$GSE_V44_SOURCE_SHA" "$GSE_V44_DURATION_SECONDS" "$mount_root" /dev/disk/by-id/google-gse-v44-data /dev/disk/by-id/google-gse-v44-target "$mount_root/data/source-output")
gcloud compute ssh "$source_vm" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" --command="$source_command" --quiet > "$output/source-remote.log" 2>&1 || exit "$EXIT_REMOTE"
gcloud compute scp "$source_vm:~/v44-source-output.tar.gz" "$output/" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" --quiet || exit "$EXIT_COLLECTION"
tar -xzf "$output/v44-source-output.tar.gz" -C "$output" || exit "$EXIT_COLLECTION"
python3 -m scripts.v43.derived_format_v12 inspect-backup "$output/source-output/backup" || exit "$EXIT_COLLECTION"
delete_instance "$source_vm" || exit "$EXIT_CLEANUP"; source_vm_deleted=PASS; source_vm_owned=false

if create_vm "$replacement_vm"; then replacement_vm_owned=true; else gcloud compute instances describe "$replacement_vm" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" >/dev/null 2>&1 && replacement_vm_owned=true; exit "$EXIT_PROVISION"; fi
wait_ssh "$replacement_vm" || exit "$EXIT_REMOTE"
gcloud compute scp scripts/v44/remote_final_durable_stage.sh "$replacement_vm:~/" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
gcloud compute ssh "$replacement_vm" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" --command='mkdir -p ~/v44-transport' --quiet || exit "$EXIT_REMOTE"
gcloud compute scp "$output/source-output/source.properties" "$replacement_vm:~/v44-transport/" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
replacement_command=$(printf 'bash ~/remote_final_durable_stage.sh replacement %q production %q %q %q %q %s %q' "$GSE_V44_SOURCE_SHA" "$GSE_V44_DURATION_SECONDS" "$mount_root" /dev/disk/by-id/google-gse-v44-data /dev/disk/by-id/google-gse-v44-target '$HOME/v44-transport' "$mount_root/data/replacement-output")
gcloud compute ssh "$replacement_vm" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" --command="$replacement_command" --quiet > "$output/replacement-remote.log" 2>&1 || exit "$EXIT_REMOTE"
gcloud compute scp "$replacement_vm:~/v44-replacement-output.tar.gz" "$output/" --project="$GSE_V44_GCP_PROJECT" --zone="$GSE_V44_GCP_ZONE" --quiet || exit "$EXIT_COLLECTION"
tar -xzf "$output/v44-replacement-output.tar.gz" -C "$output" || exit "$EXIT_COLLECTION"
delete_instance "$replacement_vm" || exit "$EXIT_CLEANUP"; replacement_vm_deleted=PASS; replacement_vm_owned=false
delete_disk "$target_disk" || exit "$EXIT_CLEANUP"; target_disk_deleted=PASS; target_disk_owned=false
delete_disk "$data_disk" || exit "$EXIT_CLEANUP"; data_disk_deleted=PASS; data_disk_owned=false

python3 -m scripts.v44.cloud_evidence assemble \
  --source-sha "$GSE_V44_SOURCE_SHA" --source-state clean --profile "$GSE_V44_PROFILE" \
  --duration-seconds "$GSE_V44_DURATION_SECONDS" --slot "$GSE_V44_SLOT" \
  --published42-properties "$output/source-output/published42.properties" \
  --source-properties "$output/source-output/source.properties" \
  --replacement-properties "$output/replacement-output/replacement.properties" \
  --published43-output "$output/source-output/published43.txt" \
  --current-output "$output/source-output/current.txt" \
  --backup "$output/source-output/backup" --output "$output/evidence" \
  --stdout-log "$output/source-remote.log" --stderr-log "$output/replacement-remote.log" \
  --source-vm-deleted --replacement-vm-deleted --data-disk-deleted \
  --target-disk-deleted --staging-object-deleted || exit "$EXIT_COLLECTION"
python3 -m scripts.v44.cloud_evidence validate "$output/evidence" || exit "$EXIT_COLLECTION"
sanitize; run_status=PASS; write_receipt
echo "v44CloudMember=PASS profile=$GSE_V44_PROFILE slot=$GSE_V44_SLOT"
