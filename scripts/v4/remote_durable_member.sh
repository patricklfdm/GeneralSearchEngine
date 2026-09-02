#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 6 ]]; then
  echo "usage: remote_durable_member.sh SOURCE_SHA PROFILE DURATION_SECONDS MOUNT DEVICE EVIDENCE" >&2
  exit 2
fi

source_sha=$1
profile=$2
duration_seconds=$3
mount_point=$4
device=$5
evidence_workspace=$6

[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid source SHA" >&2; exit 2; }
case "$profile" in experiment|canonical) ;; *) echo "invalid performance profile" >&2; exit 2 ;; esac
[[ "$duration_seconds" =~ ^[1-9][0-9]*$ ]] || { echo "invalid duration" >&2; exit 2; }
[[ "$mount_point" = /mnt/gse-v4-durable ]] || { echo "invalid mount point" >&2; exit 2; }
[[ "$device" = /dev/disk/by-id/google-gse-v4-data ]] || { echo "invalid device" >&2; exit 2; }
[[ "$evidence_workspace" = "$mount_point"/evidence-* ]] \
  || { echo "evidence workspace must be on the durable mount" >&2; exit 2; }

sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  openjdk-21-jdk-headless git ca-certificates python3 unzip

deadline=$((SECONDS + 60))
while [[ ! -b "$device" && $SECONDS -lt $deadline ]]; do sleep 1; done
[[ -b "$device" ]] || { echo "durable device did not appear" >&2; exit 20; }

if ! sudo blkid -s TYPE -o value "$device" | grep -qx ext4; then
  sudo mkfs.ext4 -F -L gse-v40-durable "$device"
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

filesystem=$(findmnt -n -o FSTYPE --target "$mount_point")
device_identity=$(lsblk -dn -o NAME,MODEL,SERIAL "$device" | tr -s ' ' '_')
export GSE_V4_CLOUD_PROVIDER=gcp
export GSE_V4_EVIDENCE_PROFILE=$profile
export GSE_V4_CLOUD_MACHINE_TYPE=${GSE_V4_CLOUD_MACHINE_TYPE:-unknown}
export GSE_V4_CLOUD_IMAGE=${GSE_V4_CLOUD_IMAGE:-unknown}
export GSE_V4_CLOUD_ZONE=${GSE_V4_CLOUD_ZONE:-unknown}
export GSE_V4_FILESYSTEM=$filesystem
export GSE_V4_DEVICE=$device_identity

python3 -m scripts.v4.durable_performance run \
  --workspace "$evidence_workspace" \
  --source-sha "$source_sha" \
  --source-state clean \
  --profile production \
  --duration-seconds "$duration_seconds" \
  --timeout-seconds "$((duration_seconds + 1800))" \
  --classpath target/benchmarks.jar
python3 -m scripts.v4.durable_performance validate \
  "$evidence_workspace/evidence"
sync "$mount_point"
echo "v40RemoteDurableMember=PASS profile=$profile source=$source_sha"
