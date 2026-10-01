#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
if [[ $# -ne 0 ]]; then
  echo "usage: $0" >&2
  exit 2
fi
python3 -m unittest scripts.v51.test_cloud_preflight scripts.v51.test_cloud_identity_setup scripts.v51.test_cloud_cleanup_deployment scripts.v51.test_cloud_cleanup_observation scripts.v51.test_cloud_permissions
mkdir -p target/v51-cloud-preflight
work_dir=$(mktemp -d "$root/target/v51-cloud-preflight/run.XXXXXX")
timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_preflight_qualification "$work_dir/evidence"
timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_identity_qualification "$work_dir/identities"
python3 -m scripts.v51.cloud_permissions_qualification "$work_dir/permissions"
python3 -m scripts.v51.cloud_cleanup_deployment generate --source "$(git rev-parse HEAD)" --output "$work_dir/deployment-review"
python3 -m scripts.v51.cloud_cleanup_deployment validate --source "$(git rev-parse HEAD)" --output "$work_dir/deployment-review"
