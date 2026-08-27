#!/usr/bin/env bash
set -euo pipefail

state_dir=${1:-/var/lib/gse-cloud-benchmark}
state_file="$state_dir/state.properties"

sudo install -d -m 0750 -o "$(id -un)" -g "$(id -gn)" "$state_dir"

write_state() {
  state=$1
  temporary="$state_file.tmp.$$"
  {
    printf 'state=%s\n' "$state"
    printf 'updated_utc=%s\n' "$(date -u +%Y%m%dT%H%M%SZ)"
  } > "$temporary"
  mv "$temporary" "$state_file"
}

write_state BOOTSTRAPPING

sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  openjdk-21-jdk-headless \
  git \
  ca-certificates \
  curl \
  unzip

java -version
git --version
unzip -v | sed -n '1p'

write_state READY
