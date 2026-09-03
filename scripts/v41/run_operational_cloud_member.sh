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
  echo "usage: run_operational_cloud_member.sh --dry-run|--confirm-paid-run" >&2
  exit "$EXIT_CONFIG"
fi

required=(
  GSE_V41_GCP_PROJECT GSE_V41_GCP_ZONE GSE_V41_CLOUD_IMAGE GSE_V41_GCS_BUCKET
  GSE_V41_SOURCE_SHA GSE_V41_RUN_ID GSE_V41_RUN_ATTEMPT GSE_V41_SLOT
  GSE_V41_PROFILE GSE_V41_DURATION_SECONDS GSE_V41_OUTPUT
)
for variable in "${required[@]}"; do
  [[ -n "${!variable:-}" ]] || { echo "ERROR: $variable is required" >&2; exit "$EXIT_CONFIG"; }
done
[[ "$GSE_V41_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR: invalid source SHA" >&2; exit "$EXIT_CONFIG"; }
[[ "$GSE_V41_RUN_ID" =~ ^[0-9]+$ && "$GSE_V41_RUN_ATTEMPT" =~ ^[1-9][0-9]*$ ]] \
  || { echo "ERROR: invalid run identity" >&2; exit "$EXIT_CONFIG"; }
[[ "$GSE_V41_SLOT" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR: invalid slot" >&2; exit "$EXIT_CONFIG"; }
case "$GSE_V41_PROFILE" in experiment|canonical|failure-drill) ;; *) echo "ERROR: invalid profile" >&2; exit "$EXIT_CONFIG" ;; esac
[[ "$GSE_V41_DURATION_SECONDS" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR: invalid duration" >&2; exit "$EXIT_CONFIG"; }
[[ "$GSE_V41_DURATION_SECONDS" = 1800 ]] \
  || { echo "ERROR: every frozen V4.1 member must measure 1800 seconds" >&2; exit "$EXIT_CONFIG"; }
if [[ "$GSE_V41_PROFILE" = canonical ]]; then
  [[ "$GSE_V41_SLOT" =~ ^[123]$ ]] \
    || { echo "ERROR: canonical slot must be 1, 2, or 3" >&2; exit "$EXIT_CONFIG"; }
else
  [[ "$GSE_V41_SLOT" = 1 ]] \
    || { echo "ERROR: single-member profile requires slot 1" >&2; exit "$EXIT_CONFIG"; }
fi
[[ "$GSE_V41_GCS_BUCKET" =~ ^gs://[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$ ]] \
  || { echo "ERROR: GCS bucket must be one exact gs://bucket URI" >&2; exit "$EXIT_CONFIG"; }

machine_type=${GSE_V41_MACHINE_TYPE:-c3d-standard-30}
[[ "$machine_type" = c3d-standard-30 ]] || { echo "ERROR: machine substitution is forbidden" >&2; exit "$EXIT_CONFIG"; }
prefix="gse-v41-${GSE_V41_RUN_ID}-${GSE_V41_RUN_ATTEMPT}-${GSE_V41_SLOT}"
prefix=${prefix:0:48}
source_vm="$prefix-source"
source_disk="$prefix-source-data"
replacement_vm="$prefix-restore"
restore_disk="$prefix-restore-data"
mount_point=/mnt/gse-v41-operational
output=$(realpath -m "$GSE_V41_OUTPUT")
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
[[ "$output" = "$repo_root"/* || "$output" = /tmp/* ]] \
  || { echo "ERROR: output must be under the repository or /tmp" >&2; exit "$EXIT_CONFIG"; }
staging_uri="${GSE_V41_GCS_BUCKET}/v4.1-operational-safety/${GSE_V41_SOURCE_SHA}/${GSE_V41_RUN_ID}-${GSE_V41_RUN_ATTEMPT}/${GSE_V41_PROFILE}/member-${GSE_V41_SLOT}/transport"

printf '%s\n' \
  "V4.1 operational source-loss member plan" \
  "  source:       $GSE_V41_SOURCE_SHA" \
  "  profile:      $GSE_V41_PROFILE" \
  "  project:      $GSE_V41_GCP_PROJECT" \
  "  zone:         $GSE_V41_GCP_ZONE" \
  "  machine:      $machine_type" \
  "  image:        $GSE_V41_CLOUD_IMAGE" \
  "  source disk:  $source_disk (pd-balanced, 200 GiB)" \
  "  restore disk: $restore_disk (pd-balanced, 200 GiB, created after source deletion)" \
  "  duration:     $GSE_V41_DURATION_SECONDS seconds" \
  "  staging:      $staging_uri"
if [[ "$confirm" == false ]]; then
  echo "v41CloudMemberDryRun=PASS"
  exit 0
fi

command -v gcloud >/dev/null || { echo "ERROR: gcloud is required" >&2; exit "$EXIT_CONFIG"; }
mkdir -p "$output"
run_status=FAIL
source_vm_deleted=NOT_APPLICABLE
source_disk_deleted=NOT_APPLICABLE
replacement_vm_deleted=NOT_APPLICABLE
restore_disk_deleted=NOT_APPLICABLE
staging_object_deleted=NOT_APPLICABLE
source_vm_owned=false
source_disk_owned=false
replacement_vm_owned=false
restore_disk_owned=false
staging_owned=false

delete_instance() {
  local name=$1
  if gcloud compute instances describe "$name" --project="$GSE_V41_GCP_PROJECT" \
      --zone="$GSE_V41_GCP_ZONE" >/dev/null 2>&1; then
    gcloud compute instances delete "$name" --project="$GSE_V41_GCP_PROJECT" \
      --zone="$GSE_V41_GCP_ZONE" --quiet >/dev/null
  fi
  ! gcloud compute instances describe "$name" --project="$GSE_V41_GCP_PROJECT" \
    --zone="$GSE_V41_GCP_ZONE" >/dev/null 2>&1
}

delete_disk() {
  local name=$1
  if gcloud compute disks describe "$name" --project="$GSE_V41_GCP_PROJECT" \
      --zone="$GSE_V41_GCP_ZONE" >/dev/null 2>&1; then
    local deleted=false
    for _ in 1 2 3 4 5; do
      if gcloud compute disks delete "$name" --project="$GSE_V41_GCP_PROJECT" \
          --zone="$GSE_V41_GCP_ZONE" --quiet >/dev/null 2>&1; then
        deleted=true
        break
      fi
      sleep 3
    done
    [[ "$deleted" == true ]] || return 1
  fi
  ! gcloud compute disks describe "$name" --project="$GSE_V41_GCP_PROJECT" \
    --zone="$GSE_V41_GCP_ZONE" >/dev/null 2>&1
}

cleanup() {
  local status=0
  if [[ "$source_vm_owned" == true ]]; then
    if delete_instance "$source_vm"; then source_vm_deleted=PASS; source_vm_owned=false; else source_vm_deleted=FAIL; status=$EXIT_CLEANUP; fi
  fi
  if [[ "$source_disk_owned" == true ]]; then
    if delete_disk "$source_disk"; then source_disk_deleted=PASS; source_disk_owned=false; else source_disk_deleted=FAIL; status=$EXIT_CLEANUP; fi
  fi
  if [[ "$replacement_vm_owned" == true ]]; then
    if delete_instance "$replacement_vm"; then replacement_vm_deleted=PASS; replacement_vm_owned=false; else replacement_vm_deleted=FAIL; status=$EXIT_CLEANUP; fi
  fi
  if [[ "$restore_disk_owned" == true ]]; then
    if delete_disk "$restore_disk"; then restore_disk_deleted=PASS; restore_disk_owned=false; else restore_disk_deleted=FAIL; status=$EXIT_CLEANUP; fi
  fi
  if [[ "$staging_owned" == true ]]; then
    if gcloud storage rm --recursive "$staging_uri" >/dev/null 2>&1 \
        && ! gcloud storage ls "$staging_uri" >/dev/null 2>&1; then
      staging_object_deleted=PASS
      staging_owned=false
    else
      staging_object_deleted=FAIL
      status=$EXIT_CLEANUP
    fi
  fi
  return "$status"
}

write_receipt() {
  local cleanup_status=FAIL
  if [[ "$source_vm_deleted" = PASS && "$source_disk_deleted" = PASS \
      && "$replacement_vm_deleted" = PASS && "$restore_disk_deleted" = PASS \
      && "$staging_object_deleted" = PASS ]]; then
    cleanup_status=PASS
  fi
  printf 'sourceCommit=%s\nprofile=%s\nslot=%s\nrunStatus=%s\nsourceVmDeleted=%s\nsourceDiskDeleted=%s\nreplacementVmDeleted=%s\nrestoreDiskDeleted=%s\nstagingObjectDeleted=%s\ncleanup=%s\n' \
    "$GSE_V41_SOURCE_SHA" "$GSE_V41_PROFILE" "$GSE_V41_SLOT" "$run_status" \
    "$source_vm_deleted" "$source_disk_deleted" "$replacement_vm_deleted" \
    "$restore_disk_deleted" "$staging_object_deleted" "$cleanup_status" \
    > "$output/cloud-member.properties"
}

bound_log() {
  local path=$1
  if [[ -f "$path" ]]; then
    tail -c 16384 "$path" > "$path.bounded" 2>/dev/null || true
    mv "$path.bounded" "$path"
  fi
}

sanitize_output() {
  # Never retain or upload corpus-bearing transport material. Successful evidence
  # already embeds bounded log tails; failures retain only bounded diagnostic tails.
  rm -rf "$output/source-output" "$output/restore-output" \
    "$output/transport-download" "$output/v41-source-output.tar.gz" \
    "$output/v41-restore-output.tar.gz" "$output/bundle.tar.gz" \
    "$output/bundle.tar.gz.sha256"
  bound_log "$output/source-remote.log"
  bound_log "$output/restore-remote.log"
}

finalize() {
  local primary=$?
  local cleanup_code=0
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
  local vm=$1
  local deadline=$((SECONDS + 180))
  until gcloud compute ssh "$vm" --project="$GSE_V41_GCP_PROJECT" \
      --zone="$GSE_V41_GCP_ZONE" --command=true --quiet >/dev/null 2>&1; do
    [[ $SECONDS -lt $deadline ]] || { echo "ERROR: SSH timeout for $vm" >&2; return 1; }
    sleep 5
  done
}

create_disk() {
  gcloud compute disks create "$1" --project="$GSE_V41_GCP_PROJECT" \
    --zone="$GSE_V41_GCP_ZONE" --type=pd-balanced --size=200GB --quiet
}

create_vm() {
  local vm=$1
  local disk=$2
  gcloud compute instances create "$vm" --project="$GSE_V41_GCP_PROJECT" \
    --zone="$GSE_V41_GCP_ZONE" --machine-type="$machine_type" \
    --provisioning-model=STANDARD --image-project=ubuntu-os-cloud \
    --image="$GSE_V41_CLOUD_IMAGE" --boot-disk-size=100GB \
    --boot-disk-type=pd-balanced --boot-disk-auto-delete \
    --disk="name=$disk,device-name=gse-v41-data,mode=rw,boot=no,auto-delete=no" \
    --no-service-account --no-scopes --max-run-duration=5400s \
    --instance-termination-action=DELETE \
    --labels="purpose=gse-v41-operational,slot=$GSE_V41_SLOT" --quiet
}

# A retry never adopts or deletes resources from an earlier attempt.
for resource in "$source_vm" "$replacement_vm"; do
  if gcloud compute instances describe "$resource" --project="$GSE_V41_GCP_PROJECT" \
      --zone="$GSE_V41_GCP_ZONE" >/dev/null 2>&1; then
    echo "ERROR: refusing pre-existing instance $resource" >&2
    exit "$EXIT_PROVISION"
  fi
done
for resource in "$source_disk" "$restore_disk"; do
  if gcloud compute disks describe "$resource" --project="$GSE_V41_GCP_PROJECT" \
      --zone="$GSE_V41_GCP_ZONE" >/dev/null 2>&1; then
    echo "ERROR: refusing pre-existing disk $resource" >&2
    exit "$EXIT_PROVISION"
  fi
done
if gcloud storage ls "$staging_uri" >/dev/null 2>&1; then
  echo "ERROR: refusing pre-existing GCS staging prefix" >&2
  exit "$EXIT_PROVISION"
fi

if create_disk "$source_disk"; then
  source_disk_owned=true
else
  gcloud compute disks describe "$source_disk" --project="$GSE_V41_GCP_PROJECT" \
    --zone="$GSE_V41_GCP_ZONE" >/dev/null 2>&1 && source_disk_owned=true
  exit "$EXIT_PROVISION"
fi
if create_vm "$source_vm" "$source_disk"; then
  source_vm_owned=true
else
  gcloud compute instances describe "$source_vm" --project="$GSE_V41_GCP_PROJECT" \
    --zone="$GSE_V41_GCP_ZONE" >/dev/null 2>&1 && source_vm_owned=true
  exit "$EXIT_PROVISION"
fi
wait_for_ssh "$source_vm" || exit "$EXIT_REMOTE"
gcloud compute scp scripts/v41/remote_operational_stage.sh "$source_vm:~/" \
  --project="$GSE_V41_GCP_PROJECT" --zone="$GSE_V41_GCP_ZONE" --quiet \
  || exit "$EXIT_REMOTE"
source_remote=$(printf \
  'bash ~/remote_operational_stage.sh source %q production %q %q %q - %q' \
  "$GSE_V41_SOURCE_SHA" "$GSE_V41_DURATION_SECONDS" "$mount_point" \
  /dev/disk/by-id/google-gse-v41-data "$mount_point/source-output")
gcloud compute ssh "$source_vm" --project="$GSE_V41_GCP_PROJECT" \
  --zone="$GSE_V41_GCP_ZONE" --command="$source_remote" --quiet \
  > "$output/source-remote.log" 2>&1 || exit "$EXIT_REMOTE"
gcloud compute scp "$source_vm:~/v41-source-output.tar.gz" "$output/" \
  --project="$GSE_V41_GCP_PROJECT" --zone="$GSE_V41_GCP_ZONE" --quiet \
  || exit "$EXIT_COLLECTION"
tar -xzf "$output/v41-source-output.tar.gz" -C "$output" \
  || exit "$EXIT_COLLECTION"
python3 -m scripts.v41.backup_format inspect "$output/source-output/backup" \
  || exit "$EXIT_COLLECTION"
tar -C "$output/source-output" -czf "$output/bundle.tar.gz" backup
sha256sum "$output/bundle.tar.gz" | awk '{print $1}' \
  > "$output/bundle.tar.gz.sha256"
gcloud storage cp "$output/bundle.tar.gz" "$staging_uri/bundle.tar.gz" \
  || exit "$EXIT_COLLECTION"
staging_owned=true
gcloud storage cp "$output/bundle.tar.gz.sha256" \
  "$staging_uri/bundle.tar.gz.sha256" || exit "$EXIT_COLLECTION"
gcloud storage cp "$output/source-output/source.properties" \
  "$staging_uri/source.properties" || exit "$EXIT_COLLECTION"

delete_instance "$source_vm" || exit "$EXIT_CLEANUP"
source_vm_deleted=PASS
source_vm_owned=false
delete_disk "$source_disk" || exit "$EXIT_CLEANUP"
source_disk_deleted=PASS
source_disk_owned=false

# Remove every local source copy. The replacement stage can now succeed only by
# downloading the immutable bundle and source proof from GCS.
rm -rf "$output/source-output/backup" "$output/v41-source-output.tar.gz" \
  "$output/bundle.tar.gz" "$output/bundle.tar.gz.sha256"
mkdir -p "$output/transport-download"
gcloud storage cp "$staging_uri/bundle.tar.gz" \
  "$output/transport-download/bundle.tar.gz" || exit "$EXIT_COLLECTION"
gcloud storage cp "$staging_uri/bundle.tar.gz.sha256" \
  "$output/transport-download/bundle.tar.gz.sha256" || exit "$EXIT_COLLECTION"
gcloud storage cp "$staging_uri/source.properties" \
  "$output/transport-download/source.properties" || exit "$EXIT_COLLECTION"
test "$(sha256sum "$output/transport-download/bundle.tar.gz" | awk '{print $1}')" \
  = "$(cat "$output/transport-download/bundle.tar.gz.sha256")" \
  || exit "$EXIT_COLLECTION"
tar -xzf "$output/transport-download/bundle.tar.gz" \
  -C "$output/transport-download" || exit "$EXIT_COLLECTION"
python3 -m scripts.v41.backup_format inspect \
  "$output/transport-download/backup" || exit "$EXIT_COLLECTION"

if create_disk "$restore_disk"; then
  restore_disk_owned=true
else
  gcloud compute disks describe "$restore_disk" --project="$GSE_V41_GCP_PROJECT" \
    --zone="$GSE_V41_GCP_ZONE" >/dev/null 2>&1 && restore_disk_owned=true
  exit "$EXIT_PROVISION"
fi
if create_vm "$replacement_vm" "$restore_disk"; then
  replacement_vm_owned=true
else
  gcloud compute instances describe "$replacement_vm" --project="$GSE_V41_GCP_PROJECT" \
    --zone="$GSE_V41_GCP_ZONE" >/dev/null 2>&1 && replacement_vm_owned=true
  exit "$EXIT_PROVISION"
fi
wait_for_ssh "$replacement_vm" || exit "$EXIT_REMOTE"
gcloud compute scp scripts/v41/remote_operational_stage.sh "$replacement_vm:~/" \
  --project="$GSE_V41_GCP_PROJECT" --zone="$GSE_V41_GCP_ZONE" --quiet \
  || exit "$EXIT_REMOTE"
gcloud compute ssh "$replacement_vm" --project="$GSE_V41_GCP_PROJECT" \
  --zone="$GSE_V41_GCP_ZONE" --command='mkdir -p ~/v41-transport' --quiet \
  || exit "$EXIT_REMOTE"
gcloud compute scp --recurse "$output/transport-download/backup" \
  "$replacement_vm:~/v41-transport/" --project="$GSE_V41_GCP_PROJECT" \
  --zone="$GSE_V41_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
gcloud compute scp "$output/transport-download/source.properties" \
  "$replacement_vm:~/v41-transport/" --project="$GSE_V41_GCP_PROJECT" \
  --zone="$GSE_V41_GCP_ZONE" --quiet || exit "$EXIT_REMOTE"
restore_remote=$(printf \
  'bash ~/remote_operational_stage.sh restore %q production %q %q %q %s %q' \
  "$GSE_V41_SOURCE_SHA" "$GSE_V41_DURATION_SECONDS" "$mount_point" \
  /dev/disk/by-id/google-gse-v41-data '$HOME/v41-transport' \
  "$mount_point/restore-output")
gcloud compute ssh "$replacement_vm" --project="$GSE_V41_GCP_PROJECT" \
  --zone="$GSE_V41_GCP_ZONE" --command="$restore_remote" --quiet \
  > "$output/restore-remote.log" 2>&1 || exit "$EXIT_REMOTE"
gcloud compute scp "$replacement_vm:~/v41-restore-output.tar.gz" "$output/" \
  --project="$GSE_V41_GCP_PROJECT" --zone="$GSE_V41_GCP_ZONE" --quiet \
  || exit "$EXIT_COLLECTION"
tar -xzf "$output/v41-restore-output.tar.gz" -C "$output" \
  || exit "$EXIT_COLLECTION"

delete_instance "$replacement_vm" || exit "$EXIT_CLEANUP"
replacement_vm_deleted=PASS
replacement_vm_owned=false
delete_disk "$restore_disk" || exit "$EXIT_CLEANUP"
restore_disk_deleted=PASS
restore_disk_owned=false
gcloud storage rm --recursive "$staging_uri" >/dev/null \
  || exit "$EXIT_CLEANUP"
if gcloud storage ls "$staging_uri" >/dev/null 2>&1; then
  exit "$EXIT_CLEANUP"
fi
staging_object_deleted=PASS
staging_owned=false

python3 -m scripts.v41.operational_evidence assemble \
  --source-sha "$GSE_V41_SOURCE_SHA" --source-state clean \
  --profile "$GSE_V41_PROFILE" --java-profile production \
  --duration-seconds "$GSE_V41_DURATION_SECONDS" --slot "$GSE_V41_SLOT" \
  --provider gcp \
  --source-properties "$output/transport-download/source.properties" \
  --restore-properties "$output/restore-output/restore.properties" \
  --backup "$output/transport-download/backup" --output "$output/evidence" \
  --stdout-log "$output/source-remote.log" \
  --stderr-log "$output/restore-remote.log" \
  --source-vm-deleted --source-disk-deleted --replacement-vm-deleted \
  --restore-disk-deleted --staging-object-deleted \
  || exit "$EXIT_COLLECTION"
python3 -m scripts.v41.operational_evidence validate "$output/evidence" \
  || exit "$EXIT_COLLECTION"

sanitize_output
run_status=PASS
write_receipt
echo "v41CloudMember=PASS profile=$GSE_V41_PROFILE slot=$GSE_V41_SLOT"
