#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 9 ]]; then
    echo "usage: remote_final_durable_stage.sh STAGE SOURCE_SHA JAVA_PROFILE DURATION MOUNT DATA_DEVICE TARGET_DEVICE TRANSPORT OUTPUT" >&2
    exit 2
fi
stage=$1
source_sha=$2
java_profile=$3
duration=$4
mount_root=$5
data_device=$6
target_device=$7
transport=$8
output=$9
case "$stage" in source|replacement) ;; *) exit 2 ;; esac
[[ "$source_sha" =~ ^[0-9a-f]{40}$ && "$java_profile" == production ]] || exit 2
[[ "$duration" == 3600 && "$mount_root" == /mnt/gse-v44-final-durable ]] || exit 2
[[ "$output" == "$mount_root"/* ]] || exit 2

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
data_mount="$mount_root/data"
target_mount="$mount_root/target"
[[ "$data_device" == /dev/disk/by-id/google-gse-v44-data ]] || exit 2
[[ "$target_device" == /dev/disk/by-id/google-gse-v44-target ]] || exit 2
mount_device "$data_device" "$data_mount" gse-v44-data
mount_device "$target_device" "$target_mount" gse-v44-target
if [[ "$stage" == source ]]; then
    [[ "$transport" == - ]] || exit 2
else
    [[ "$transport" == "$HOME"/* ]] || exit 2
fi

repo="$HOME/GeneralSearchEngine"
git init -q "$repo"
git -C "$repo" remote add origin https://github.com/patricklfdm/GeneralSearchEngine.git
git -C "$repo" fetch --depth=1 origin "$source_sha"
git -C "$repo" checkout -q --detach "$source_sha"
test "$(git -C "$repo" rev-parse HEAD)" = "$source_sha"
test -z "$(git -C "$repo" status --porcelain)"
cd "$repo"
mkdir -p "$output"
./mvnw -q clean -Pjmh -DskipTests package

if [[ "$stage" == source ]]; then
    published42="$HOME/general-search-engine-4.2.0.jar"
    published43="$HOME/general-search-engine-4.3.0.jar"
    curl --fail --silent --show-error --location --output "$published42" \
        https://repo1.maven.org/maven2/io/github/patricklfdm/general-search-engine/4.2.0/general-search-engine-4.2.0.jar
    echo "8dba2f09b861e3ed5fe7edde8226632c2248fe49582e0f3cb2c3fcb1cd958191  $published42" \
        | sha256sum --check --strict
    curl --fail --silent --show-error --location --output "$published43" \
        https://repo1.maven.org/maven2/io/github/patricklfdm/general-search-engine/4.3.0/general-search-engine-4.3.0.jar
    echo "c5ecf5cf311c734481e95f14bdcfffb466fa132dde424a2b6b4a58fe41778583  $published43" \
        | sha256sum --check --strict

    mkdir -p "$HOME/v44-published42" "$HOME/v44-paired"
    javac -cp "$published42" -d "$HOME/v44-published42" \
        scripts/v43/PublishedV42FastReopenControl.java
    javac -cp "$published43" -d "$HOME/v44-paired" \
        scripts/v44/PairedPublishedV43Probe.java
    java -cp "$HOME/v44-published42:$published42" \
        PublishedV42FastReopenControl "$java_profile" \
        "$data_mount/published42-store" "$output/published42.properties"
    java -cp "$HOME/v44-paired:$published43" PairedPublishedV43Probe \
        published-4-3 "$data_mount/published43-store" 20000 \
        > "$output/published43.txt"
    java -cp "$HOME/v44-paired:target/general-search-engine-4.4.0-SNAPSHOT.jar" \
        PairedPublishedV43Probe current-source "$data_mount/current-paired-store" 20000 \
        > "$output/current.txt"
    java -cp target/benchmarks.jar \
        io.github.patricklfdm.generalsearch.engine.V43FastReopenEvidenceProbe \
        source "$java_profile" "$data_mount" "$target_mount" \
        "$output/source.properties"
    cp -a "$data_mount/canonical-backup" "$output/backup"
    python3 -m scripts.v43.derived_format_v12 inspect-backup "$output/backup"
    tar -C "$data_mount" -czf "$HOME/v44-source-output.tar.gz" \
        "$(basename "$output")"
else
    java -cp target/benchmarks.jar \
        io.github.patricklfdm.generalsearch.engine.V43FastReopenEvidenceProbe \
        replacement "$java_profile" "$data_mount" "$target_mount" \
        "$transport/source.properties" "$output/replacement.properties" "$duration"
    tar -C "$data_mount" -czf "$HOME/v44-replacement-output.tar.gz" \
        "$(basename "$output")"
fi
sync "$mount_root"
echo "v44RemoteFinalDurableStage=PASS stage=$stage source=$source_sha"
