#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 9 ]]; then
  echo "usage: remote_fast_reopen_stage.sh STAGE SOURCE_SHA JAVA_PROFILE DURATION MOUNT PRIMARY_DEVICE TARGET_DEVICE TRANSPORT OUTPUT" >&2
  exit 2
fi
stage=$1; source_sha=$2; java_profile=$3; duration=$4; mount_root=$5
primary_device=$6; target_device=$7; transport=$8; output=$9
case "$stage" in source|replacement) ;; *) exit 2 ;; esac
[[ "$source_sha" =~ ^[0-9a-f]{40}$ && "$java_profile" = production ]] || exit 2
[[ "$duration" = 1800 && "$mount_root" = /mnt/gse-v43-fast-reopen ]] || exit 2
[[ "$output" = "$mount_root"/* ]] || exit 2

sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  openjdk-21-jdk-headless git ca-certificates python3 unzip curl

mount_device() {
  local device=$1 mount_point=$2 label=$3 deadline=$((SECONDS + 60))
  while [[ ! -b "$device" && $SECONDS -lt $deadline ]]; do sleep 1; done
  [[ -b "$device" ]] || return 20
  if ! sudo blkid -s TYPE -o value "$device" | grep -qx ext4; then
    sudo mkfs.ext4 -F -L "$label" "$device"
  fi
  sudo install -d -m 0755 "$mount_point"
  mountpoint -q "$mount_point" || sudo mount -o defaults "$device" "$mount_point"
  sudo chown "$(id -u):$(id -g)" "$mount_point"
}
primary_mount="$mount_root/primary"; target_mount="$mount_root/target"
[[ "$primary_device" = /dev/disk/by-id/google-gse-v43-primary ]] || exit 2
[[ "$target_device" = /dev/disk/by-id/google-gse-v43-target ]] || exit 2
mount_device "$primary_device" "$primary_mount" gse-v43-primary
mount_device "$target_device" "$target_mount" gse-v43-target
if [[ "$stage" = source ]]; then
  [[ "$transport" = - ]] || exit 2
else
  [[ "$transport" = "$HOME"/* ]] || exit 2
fi

repo="$HOME/GeneralSearchEngine"
git init "$repo"
git -C "$repo" remote add origin https://github.com/patricklfdm/GeneralSearchEngine.git
git -C "$repo" fetch --depth=1 origin "$source_sha"
git -C "$repo" checkout --detach "$source_sha"
test "$(git -C "$repo" rev-parse HEAD)" = "$source_sha"
test -z "$(git -C "$repo" status --porcelain)"
cd "$repo"
mkdir -p "$output"
./mvnw -q clean -Pjmh -DskipTests package

if [[ "$stage" = source ]]; then
  published_jar="$HOME/general-search-engine-4.2.0.jar"
  curl --fail --silent --show-error --location --output "$published_jar" \
    https://repo1.maven.org/maven2/io/github/patricklfdm/general-search-engine/4.2.0/general-search-engine-4.2.0.jar
  echo "8dba2f09b861e3ed5fe7edde8226632c2248fe49582e0f3cb2c3fcb1cd958191  $published_jar" \
    | sha256sum --check --strict
  mkdir -p "$HOME/v43-published-control"
  javac -cp "$published_jar" -d "$HOME/v43-published-control" \
    scripts/v43/PublishedV42FastReopenControl.java
  java -cp "$HOME/v43-published-control:$published_jar" \
    PublishedV42FastReopenControl "$java_profile" \
    "$primary_mount/published-store" "$output/published.properties"
  java -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.engine.V43FastReopenEvidenceProbe \
    source "$java_profile" "$primary_mount" "$target_mount" \
    "$output/source.properties"
  cp -a "$primary_mount/canonical-backup" "$output/backup"
  python3 -m scripts.v43.derived_format_v12 inspect-backup "$output/backup"
  tar -C "$primary_mount" -czf "$HOME/v43-source-output.tar.gz" \
    "$(basename "$output")"
else
  java -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.engine.V43FastReopenEvidenceProbe \
    replacement "$java_profile" "$primary_mount" "$target_mount" \
    "$transport/source.properties" "$output/replacement.properties" "$duration"
  tar -C "$primary_mount" -czf "$HOME/v43-replacement-output.tar.gz" \
    "$(basename "$output")"
fi
sync "$mount_root"
echo "v43RemoteFastReopenStage=PASS stage=$stage source=$source_sha"
