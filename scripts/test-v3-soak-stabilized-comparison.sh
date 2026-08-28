#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-stabilized-comparison-test.XXXXXX")
trap 'rm -rf -- "$test_root"' EXIT

write_run() {
  name=$1
  cell=$2
  started=$3
  drift=$4
  rate=$5
  run="$test_root/$name"
  mkdir -p "$run/soak"
  cat > "$run/metadata.txt" <<EOF
started_utc=$started
git_commit=0123456789abcdef
logical_cpus=30
java_runtime=openjdk version 21.0.8
jvm_options=-Xms8g -Xmx16g
cloud_provider=gcp
cloud_zone=us-west4-a
cloud_machine_type=c3d-standard-30
cloud_provisioning=standard
cloud_image_project=ubuntu-os-cloud
cloud_image_family=ubuntu-2404-lts-amd64
cloud_image=ubuntu-2404-noble-amd64-v20260826
cloud_image_id=5563818848645508791
cloud_image_self_link=https://example.test/image
cloud_image_created_at=2026-08-26T04:39:04.320-07:00
working_tree_begin
working_tree_end
EOF
  cat > "$run/soak/soak-config.properties" <<EOF
stabilization_purpose=screening
documents=100000
readers=16
writers=1
seconds=600
sample_seconds=1
top_k=10
corpus_profile=zipf-en-medium-4
index_cycles=false
per_query_metrics=true
stabilization_seconds=300
stabilization_window_seconds=60
allow_reduced_stabilization_test=false
jfr_output=none
update_mode=$([ "$cell" = stable-update ] && echo stable || echo revision)
EOF
  printf '%s\n' 'analysis_status=VALID' 'stabilization_status=READY' \
    'measurement_started=true' > "$run/soak/soak-stabilization-analysis.properties"
  cat > "$run/soak/soak-analysis.properties" <<EOF
analysis_status=VALID
read_rate_drift_pct=$drift
summary_read_ops_per_second=$rate
EOF
  {
    printf 'analysis_status=VALID\ninvestigation_cell=%s\n' "$cell"
    printf 'summary_corpus_changed=%s\n' \
      "$([ "$cell" = stable-update ] && echo false || echo true)"
    for metric in text bool phrase fuzzy; do
      printf '%s_read_rate_drift_pct=%s\n' "$metric" "$drift"
      printf 'summary_%s_read_ops_per_second=%s\n' "$metric" "$rate"
    done
  } > "$run/soak/soak-investigation-analysis.properties"
  (cd "$run" && find . -type f ! -name checksums.sha256 -print0 \
    | sort -z | xargs -0 sha256sum > checksums.sha256)
}

# Argument order is R1,S1,R2,S2,R3,S3; timestamps prove S1,R1,R2,S2,S3,R3.
write_run r1 revision-update 20260101T000002Z 5.0 106.0
write_run s1 stable-update   20260101T000001Z 0.0 100.0
write_run r2 revision-update 20260101T000003Z 5.2 106.2
write_run s2 stable-update   20260101T000004Z 0.0 100.0
write_run r3 revision-update 20260101T000006Z 4.8 105.8
write_run s3 stable-update   20260101T000005Z 0.0 100.0

output=$($repo_root/scripts/compare-v3-soak-stabilized.sh \
  "$test_root/r1" "$test_root/s1" "$test_root/r2" "$test_root/s2" \
  "$test_root/r3" "$test_root/s3")
printf '%s\n' "$output" | grep -Fx 'comparison_status=VALID' >/dev/null
printf '%s\n' "$output" | grep -Fx 'aggregate_joint_supported=true' >/dev/null
printf '%s\n' "$output" | grep -Fx 'text_joint_supported=true' >/dev/null
printf '%s\n' "$output" | grep -Fx 'differentiating_factor_supported=true' >/dev/null

if "$repo_root/scripts/compare-v3-soak-stabilized.sh" \
    "$test_root/r1" "$test_root/s1" "$test_root/r2" "$test_root/s2" \
    "$test_root/r3" "$test_root/r3" >/dev/null 2>&1; then
  echo 'FAIL: duplicate comparison run was accepted' >&2
  exit 1
fi

echo 'V3 stabilized comparison tests: PASS'
