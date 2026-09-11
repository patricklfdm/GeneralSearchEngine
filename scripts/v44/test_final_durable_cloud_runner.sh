#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$repo_root"

work_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-v44-cloud-dry-run.XXXXXXXX")
trap 'rm -rf -- "$work_root"' EXIT

run_dry() {
    local profile=$1 slot=$2
    GSE_V44_GCP_PROJECT=gse-benchmark \
    GSE_V44_GCP_ZONE=us-west4-a \
    GSE_V44_CLOUD_IMAGE=ubuntu-2404-noble-amd64-v20260906 \
    GSE_V44_GCS_BUCKET=gs://gse-v44-fake-bucket \
    GSE_V44_SOURCE_SHA=4444444444444444444444444444444444444444 \
    GSE_V44_RUN_ID=44001 \
    GSE_V44_RUN_ATTEMPT=1 \
    GSE_V44_SLOT="$slot" \
    GSE_V44_PROFILE="$profile" \
    GSE_V44_DURATION_SECONDS=3600 \
    GSE_V44_OUTPUT="$work_root/$profile-$slot" \
        scripts/v44/run_final_durable_cloud_member.sh --dry-run
    [[ ! -e "$work_root/$profile-$slot" ]]
}

run_dry experiment 1
for slot in 1 2 3; do run_dry canonical "$slot"; done
run_dry failure-drill 1

if GSE_V44_GCP_PROJECT=gse-benchmark \
    GSE_V44_GCP_ZONE=us-west4-a \
    GSE_V44_CLOUD_IMAGE=unfrozen-image \
    GSE_V44_GCS_BUCKET=gs://gse-v44-fake-bucket \
    GSE_V44_SOURCE_SHA=4444444444444444444444444444444444444444 \
    GSE_V44_RUN_ID=44001 GSE_V44_RUN_ATTEMPT=1 GSE_V44_SLOT=1 \
    GSE_V44_PROFILE=experiment GSE_V44_DURATION_SECONDS=3600 \
    GSE_V44_OUTPUT="$work_root/rejected" \
        scripts/v44/run_final_durable_cloud_member.sh --dry-run; then
    echo "unfrozen cloud image was accepted" >&2
    exit 1
fi

echo "V4.4 final-durable cloud runner dry-run: PASS (no GCP)"
