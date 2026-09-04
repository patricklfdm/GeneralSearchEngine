#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 9 ]]; then
  echo "usage: remote_storage_evolution_stage.sh STAGE SOURCE_SHA JAVA_PROFILE DURATION MOUNT SOURCE_DEVICE TARGET_DEVICE TRANSPORT OUTPUT" >&2
  exit 2
fi

stage=$1
source_sha=$2
java_profile=$3
duration_seconds=$4
mount_root=$5
source_device=$6
target_device=$7
transport=$8
output=$9

case "$stage" in source-migrate|target|rollback) ;; *) echo "invalid stage" >&2; exit 2 ;; esac
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid source SHA" >&2; exit 2; }
[[ "$java_profile" = production ]] || { echo "cloud Java profile must be production" >&2; exit 2; }
[[ "$duration_seconds" = 1800 ]] || { echo "invalid frozen duration" >&2; exit 2; }
[[ "$mount_root" = /mnt/gse-v42-evolution ]] || { echo "invalid mount root" >&2; exit 2; }
[[ "$output" = "$mount_root"/* ]] || { echo "output must be on a data disk" >&2; exit 2; }

sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  openjdk-21-jdk-headless git ca-certificates python3 unzip curl

mount_device() {
  local device=$1
  local mount_point=$2
  local label=$3
  local deadline=$((SECONDS + 60))
  while [[ ! -b "$device" && $SECONDS -lt $deadline ]]; do sleep 1; done
  [[ -b "$device" ]] || { echo "data device did not appear: $device" >&2; return 20; }
  if ! sudo blkid -s TYPE -o value "$device" | grep -qx ext4; then
    sudo mkfs.ext4 -F -L "$label" "$device"
  fi
  sudo install -d -m 0755 "$mount_point"
  if ! mountpoint -q "$mount_point"; then
    sudo mount -o defaults "$device" "$mount_point"
  fi
  sudo chown "$(id -u):$(id -g)" "$mount_point"
}

source_mount="$mount_root/source"
target_mount="$mount_root/target"
case "$stage" in
  source-migrate)
    [[ "$source_device" = /dev/disk/by-id/google-gse-v42-source ]] || exit 2
    [[ "$target_device" = /dev/disk/by-id/google-gse-v42-target ]] || exit 2
    [[ "$transport" = - ]] || exit 2
    mount_device "$source_device" "$source_mount" gse-v42-source
    mount_device "$target_device" "$target_mount" gse-v42-target
    ;;
  target)
    [[ "$source_device" = - ]] || exit 2
    [[ "$target_device" = /dev/disk/by-id/google-gse-v42-target ]] || exit 2
    [[ "$transport" = "$HOME"/* ]] || exit 2
    mount_device "$target_device" "$target_mount" gse-v42-target
    ;;
  rollback)
    [[ "$source_device" = /dev/disk/by-id/google-gse-v42-source ]] || exit 2
    [[ "$target_device" = - ]] || exit 2
    [[ "$transport" = "$HOME"/* ]] || exit 2
    mount_device "$source_device" "$source_mount" gse-v42-source
    ;;
esac

repo="$HOME/GeneralSearchEngine"
git init "$repo"
git -C "$repo" remote add origin https://github.com/patricklfdm/GeneralSearchEngine.git
git -C "$repo" fetch --depth=1 origin "$source_sha"
git -C "$repo" checkout --detach "$source_sha"
test "$(git -C "$repo" rev-parse HEAD)" = "$source_sha"
test -z "$(git -C "$repo" status --porcelain)"
cd "$repo"

mkdir -p "$output"
if [[ "$stage" = source-migrate ]]; then
  ./mvnw -q clean -Pjmh -DskipTests package
  java -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.engine.V42MigrationEvidenceProbe \
    source "$java_profile" "$source_mount/store" "$output/backup" \
    "$output/source.properties" "$duration_seconds"
  python3 -m scripts.v41.backup_format inspect "$output/backup"
  java -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.engine.V42MigrationEvidenceProbe \
    migrate "$java_profile" "$source_mount/store" "$target_mount/store" \
    "$output/source.properties" "$output/migration.properties"
  tar -C "$mount_root" -czf "$HOME/v42-source-migration-output.tar.gz" \
    "${output#"$mount_root"/}"
elif [[ "$stage" = target ]]; then
  ./mvnw -q clean -Pjmh -DskipTests package
  java -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.engine.V42MigrationEvidenceProbe \
    target "$java_profile" "$target_mount/store" \
    "$transport/migration.properties" "$output/target.properties" \
    "$duration_seconds"
  tar -C "$mount_root" -czf "$HOME/v42-target-output.tar.gz" \
    "${output#"$mount_root"/}"
else
  published_jar="$HOME/general-search-engine-4.1.0.jar"
  curl --fail --silent --show-error --location \
    --output "$published_jar" \
    https://repo1.maven.org/maven2/io/github/patricklfdm/general-search-engine/4.1.0/general-search-engine-4.1.0.jar
  echo "36aa783cef653ead26d2500a847b70bb1f8222d224c8a83de55419de46814bcb  $published_jar" \
    | sha256sum --check --strict
  mkdir -p "$HOME/v42-published-probe"
  javac -cp "$published_jar" -d "$HOME/v42-published-probe" \
    scripts/v42/PublishedV41MigrationCloudProbe.java
  java -cp "$HOME/v42-published-probe:$published_jar" \
    PublishedV41MigrationCloudProbe "$java_profile" "$source_mount/store" \
    "$transport/source.properties"
  source_digest=$(awk -F= '$1 == "source.directorySha256" { print $2 }' \
    "$transport/source.properties")
  source_sequence=$(awk -F= '$1 == "source.sequence" { print $2 }' \
    "$transport/source.properties")
  source_oracle=$(awk -F= '$1 == "source.oracleChecksum" { print $2 }' \
    "$transport/source.properties")
  printf 'schemaVersion=gse-v42-published-rollback-properties-v1\nstatus=PASS\nprofile=%s\npublishedVersion=4.1.0\nsourceDirectorySha256=%s\nsourceSequence=%s\nsourceOracleChecksum=%s\n' \
    "$java_profile" "$source_digest" "$source_sequence" "$source_oracle" \
    > "$output/rollback.properties"
  tar -C "$mount_root" -czf "$HOME/v42-rollback-output.tar.gz" \
    "${output#"$mount_root"/}"
fi

sync "$mount_root"
echo "v42RemoteStorageEvolutionStage=PASS stage=$stage source=$source_sha"
