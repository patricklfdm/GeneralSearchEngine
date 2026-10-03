#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
if [[ $# -ne 0 ]]; then
  echo "usage: $0" >&2
  exit 2
fi
python3 -m unittest scripts.v51.test_cloud_preflight scripts.v51.test_cloud_recent_cleanup scripts.v51.test_cloud_identity_setup scripts.v51.test_cloud_cleanup_deployment scripts.v51.test_cloud_cleanup_observation scripts.v51.test_cloud_permissions scripts.v51.test_cloud_credential_diagnostics scripts.v51.test_cloud_cleanup_fixture scripts.v51.test_cloud_fixture_driver scripts.v51.test_cloud_topology_fixture scripts.v51.test_cloud_runner_precheck
mkdir -p target/v51-cloud-preflight
work_dir=$(mktemp -d "$root/target/v51-cloud-preflight/run.XXXXXX")
timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_preflight_qualification "$work_dir/evidence"
timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_identity_qualification "$work_dir/identities"
python3 -m scripts.v51.cloud_permissions_qualification "$work_dir/permissions"
python3 -m scripts.v51.cloud_cleanup_deployment generate --source "$(git rev-parse HEAD)" --output "$work_dir/deployment-review"
python3 -m scripts.v51.cloud_cleanup_deployment validate --source "$(git rev-parse HEAD)" --output "$work_dir/deployment-review"
python3 -m scripts.v51.cloud_runner_review generate --source "$(git rev-parse HEAD)" --output "$work_dir/runner-review"
python3 -m scripts.v51.cloud_runner_review validate --source "$(git rev-parse HEAD)" --output "$work_dir/runner-review"
python3 -m scripts.v51.cloud_cleanup_fixture generate --source "$(git rev-parse HEAD)" --output "$work_dir/single-disk-review"
python3 -m scripts.v51.cloud_cleanup_fixture validate --source "$(git rev-parse HEAD)" --output "$work_dir/single-disk-review"
timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_cleanup_fixture_qualification "$work_dir/single-disk-qualification" --source "$(git rev-parse HEAD)"
timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_fixture_driver_qualification "$work_dir/fixture-driver" --source "$(git rev-parse HEAD)"
timeout --signal=TERM --kill-after=5s 240s python3 -m scripts.v51.cloud_topology_qualification "$work_dir/topology-fixture" --source "$(git rev-parse HEAD)"
