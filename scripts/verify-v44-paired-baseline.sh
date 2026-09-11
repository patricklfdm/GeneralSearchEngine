#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

published_jar=target/compat-baselines/published-general-search-engine-4.3.0.jar
current_jar=target/general-search-engine-4.4.0-SNAPSHOT.jar
test -f "$published_jar"
test -f "$current_jar"

expected=c5ecf5cf311c734481e95f14bdcfffb466fa132dde424a2b6b4a58fe41778583
test "$(sha256sum "$published_jar" | awk '{print $1}')" = "$expected"

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v44-paired.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
javac -cp "$published_jar" -d "$work_dir/classes" \
    scripts/v44/PairedPublishedV43Probe.java

documents=${GSE_V44_BASELINE_DOCUMENTS:-20000}
published_output=$(java -cp "$published_jar:$work_dir/classes" \
    PairedPublishedV43Probe published-4-3 "$work_dir/published-store" "$documents")
current_output=$(java -cp "$current_jar:$work_dir/classes" \
    PairedPublishedV43Probe current-source "$work_dir/current-store" "$documents")
printf '%s\n%s\n' "$published_output" "$current_output"

published_digest=$(sed -n 's/.*semanticDigest=\([0-9a-f]\{64\}\).*/\1/p' \
    <<<"$published_output")
current_digest=$(sed -n 's/.*semanticDigest=\([0-9a-f]\{64\}\).*/\1/p' \
    <<<"$current_output")
test -n "$published_digest"
test "$published_digest" = "$current_digest"
echo "V4.4 paired published-4.3/current calibration: PASS digest=$current_digest"
