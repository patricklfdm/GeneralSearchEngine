#!/usr/bin/env bash
set -u

state_dir=/var/lib/gse-cloud-benchmark
marker="$state_dir/interruption.properties"
temporary="$marker.tmp.$$"

install -d -m 0755 "$state_dir"
preempted=unknown
if metadata_value=$(curl --fail --silent --show-error --max-time 2 \
    -H 'Metadata-Flavor: Google' \
    'http://metadata.google.internal/computeMetadata/v1/instance/preempted' 2>/dev/null); then
  case "${metadata_value,,}" in
    true|false) preempted=${metadata_value,,} ;;
  esac
fi

{
  printf 'preempted=%s\n' "$preempted"
  printf 'observed_utc=%s\n' "$(date -u +%Y%m%dT%H%M%SZ)"
} > "$temporary"
mv "$temporary" "$marker"

exit 0
