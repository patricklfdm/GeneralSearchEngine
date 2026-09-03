#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 8 ]]; then
  echo "usage: remote_operational_stage.sh STAGE SOURCE_SHA JAVA_PROFILE DURATION MOUNT DEVICE TRANSPORT OUTPUT" >&2
  exit 2
fi

stage=$1
source_sha=$2
java_profile=$3
duration_seconds=$4
mount_point=$5
device=$6
transport=$7
output=$8

case "$stage" in source|restore) ;; *) echo "invalid stage" >&2; exit 2 ;; esac
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid source SHA" >&2; exit 2; }
[[ "$java_profile" = production ]] || { echo "cloud Java profile must be production" >&2; exit 2; }
[[ "$duration_seconds" =~ ^[1-9][0-9]*$ ]] || { echo "invalid duration" >&2; exit 2; }
[[ "$mount_point" = /mnt/gse-v41-operational ]] || { echo "invalid mount point" >&2; exit 2; }
[[ "$device" = /dev/disk/by-id/google-gse-v41-data ]] || { echo "invalid device" >&2; exit 2; }
[[ "$output" = "$mount_point"/* ]] || { echo "output must be on the data disk" >&2; exit 2; }

sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  openjdk-21-jdk-headless git ca-certificates python3 unzip

deadline=$((SECONDS + 60))
while [[ ! -b "$device" && $SECONDS -lt $deadline ]]; do sleep 1; done
[[ -b "$device" ]] || { echo "data device did not appear" >&2; exit 20; }
if ! sudo blkid -s TYPE -o value "$device" | grep -qx ext4; then
  sudo mkfs.ext4 -F -L gse-v41-operational "$device"
fi
sudo install -d -m 0755 "$mount_point"
if ! mountpoint -q "$mount_point"; then
  sudo mount -o defaults "$device" "$mount_point"
fi
sudo chown "$(id -u):$(id -g)" "$mount_point"

repo="$HOME/GeneralSearchEngine"
git init "$repo"
git -C "$repo" remote add origin https://github.com/patricklfdm/GeneralSearchEngine.git
git -C "$repo" fetch --depth=1 origin "$source_sha"
git -C "$repo" checkout --detach "$source_sha"
test "$(git -C "$repo" rev-parse HEAD)" = "$source_sha"
test -z "$(git -C "$repo" status --porcelain)"

cd "$repo"
./mvnw -q clean -Pjmh -DskipTests package
mkdir -p "$output"

if [[ "$stage" = source ]]; then
  [[ "$transport" = - ]] || { echo "source transport must be '-'" >&2; exit 2; }
  java -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.engine.V41OperationalEvidenceProbe \
    source "$java_profile" "$mount_point/source-store" "$output/backup" \
    "$output/source.properties" "$duration_seconds"
  python3 -m scripts.v41.backup_format inspect "$output/backup"
  tar -C "$mount_point" -czf "$HOME/v41-source-output.tar.gz" \
    "${output#"$mount_point"/}"
else
  [[ "$transport" = "$HOME"/* ]] || { echo "restore transport must be under HOME" >&2; exit 2; }
  python3 -m scripts.v41.backup_format inspect "$transport/backup"
  java -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.engine.V41OperationalEvidenceProbe \
    restore "$java_profile" "$transport/backup" "$mount_point/restore-store" \
    "$transport/source.properties" "$output/restore.properties" \
    "$duration_seconds"
  tar -C "$mount_point" -czf "$HOME/v41-restore-output.tar.gz" \
    "${output#"$mount_point"/}"
fi

sync "$mount_point"
echo "v41RemoteOperationalStage=PASS stage=$stage source=$source_sha"
