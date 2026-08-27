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

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  openjdk-21-jdk-headless \
  git \
  ca-certificates \
  curl

java -version
git --version

write_state READY
