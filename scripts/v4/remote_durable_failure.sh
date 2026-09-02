#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 6 ]]; then
  echo "usage: remote_durable_failure.sh SOURCE_SHA MODE MOUNT DEVICE WORKSPACE TIMEOUT" >&2
  exit 2
fi
source_sha=$1
mode=$2
mount_point=$3
device=$4
workspace=$5
timeout=$6
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid source SHA" >&2; exit 2; }
case "$mode" in writer|recover) ;; *) echo "invalid failure mode" >&2; exit 2 ;; esac
[[ "$mount_point" = /mnt/gse-v4-durable ]] || { echo "invalid mount point" >&2; exit 2; }
[[ "$device" = /dev/disk/by-id/google-gse-v4-data ]] || { echo "invalid device" >&2; exit 2; }
[[ "$workspace" = "$mount_point"/failure-* ]] || { echo "invalid workspace" >&2; exit 2; }
[[ "$timeout" =~ ^[1-9][0-9]*$ ]] || { echo "invalid timeout" >&2; exit 2; }

sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  openjdk-21-jdk-headless git ca-certificates python3 unzip
deadline=$((SECONDS + 60))
while [[ ! -b "$device" && $SECONDS -lt $deadline ]]; do sleep 1; done
[[ -b "$device" ]] || { echo "durable device did not appear" >&2; exit 20; }
if ! sudo blkid -s TYPE -o value "$device" | grep -qx ext4; then
  [[ "$mode" = writer ]] || { echo "recovery disk has no ext4 filesystem" >&2; exit 20; }
  sudo mkfs.ext4 -F -L gse-v40-durable "$device"
fi
sudo install -d -m 0755 "$mount_point"
sudo mount -o defaults "$device" "$mount_point"
sudo chown "$(id -u):$(id -g)" "$mount_point"

repo="$HOME/GeneralSearchEngine"
git init "$repo"
git -C "$repo" remote add origin https://github.com/patricklfdm/GeneralSearchEngine.git
git -C "$repo" fetch --depth=1 origin "$source_sha"
git -C "$repo" checkout --detach "$source_sha"
test "$(git -C "$repo" rev-parse HEAD)" = "$source_sha"
test -z "$(git -C "$repo" status --porcelain)"
cd "$repo"
./mvnw -q -DskipTests test-compile

export GSE_V4_CLOUD_MACHINE_TYPE=${GSE_V4_CLOUD_MACHINE_TYPE:-unknown}
export GSE_V4_CLOUD_IMAGE=${GSE_V4_CLOUD_IMAGE:-unknown}
export GSE_V4_CLOUD_ZONE=${GSE_V4_CLOUD_ZONE:-unknown}
export GSE_V4_FILESYSTEM=$(findmnt -n -o FSTYPE --target "$mount_point")
export GSE_V4_DEVICE=$(lsblk -dn -o NAME,MODEL,SERIAL "$device" | tr -s ' ' '_')
python3 -m scripts.v4.durable_remote_failure "$mode" \
  --workspace "$workspace" \
  --source-sha "$source_sha" \
  --timeout "$timeout"
sync "$mount_point"
echo "v40RemoteFailureHalf=PASS mode=$mode source=$source_sha"
