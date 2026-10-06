#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
lane=all
if [[ $# -eq 2 && "$1" == --lane && "$2" =~ ^(admission|cleanup|storage)$ ]]; then
  lane=$2
elif [[ $# -ne 0 ]]; then
  echo "usage: $0 [--lane admission|cleanup|storage]" >&2
  exit 2
fi
mkdir -p target/v51-cloud-preflight
work_dir=$(mktemp -d "$root/target/v51-cloud-preflight/run.XXXXXX")
echo "v51CloudPreflightEvidence=$work_dir lane=$lane"
if [[ "$lane" == all || "$lane" == admission ]]; then
  python3 -m unittest scripts.v51.test_cloud_preflight scripts.v51.test_cloud_recent_cleanup scripts.v51.test_cloud_identity_setup scripts.v51.test_cloud_cleanup_deployment scripts.v51.test_cloud_cleanup_observation scripts.v51.test_cloud_permissions scripts.v51.test_cloud_credential_diagnostics scripts.v51.test_cloud_runner_precheck scripts.v51.test_cloud_runner_artifacts scripts.v51.test_cloud_runner_admission scripts.v51.test_cloud_runner_prepared scripts.v51.test_cloud_runner_entry
  timeout --signal=TERM --kill-after=5s 180s python3 -m scripts.v51.cloud_runner_admission_qualification "$work_dir/runner-admission"
  timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_preflight_qualification "$work_dir/evidence"
  timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_identity_qualification "$work_dir/identities"
  python3 -m scripts.v51.cloud_permissions_qualification "$work_dir/permissions"
  python3 -m scripts.v51.cloud_cleanup_deployment generate --source "$(git rev-parse HEAD)" --output "$work_dir/deployment-review"
  python3 -m scripts.v51.cloud_cleanup_deployment validate --source "$(git rev-parse HEAD)" --output "$work_dir/deployment-review"
  python3 -m scripts.v51.cloud_runner_review generate --source "$(git rev-parse HEAD)" --output "$work_dir/runner-review"
  python3 -m scripts.v51.cloud_runner_review validate --source "$(git rev-parse HEAD)" --output "$work_dir/runner-review"
fi
if [[ "$lane" == all || "$lane" == cleanup ]]; then
  python3 -m unittest scripts.v51.test_cloud_cleanup_fixture scripts.v51.test_cloud_fixture_driver scripts.v51.test_cloud_topology_fixture scripts.v51.test_cloud_experiment_resources
  python3 -m scripts.v51.cloud_cleanup_fixture generate --source "$(git rev-parse HEAD)" --output "$work_dir/single-disk-review"
  python3 -m scripts.v51.cloud_cleanup_fixture validate --source "$(git rev-parse HEAD)" --output "$work_dir/single-disk-review"
  timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_cleanup_fixture_qualification "$work_dir/single-disk-qualification" --source "$(git rev-parse HEAD)"
  timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_fixture_driver_qualification "$work_dir/fixture-driver" --source "$(git rev-parse HEAD)"
  timeout --signal=TERM --kill-after=5s 240s python3 -m scripts.v51.cloud_topology_qualification "$work_dir/topology-fixture" --source "$(git rev-parse HEAD)"
  timeout --signal=TERM --kill-after=5s 600s python3 -m scripts.v51.cloud_experiment_resource_qualification "$work_dir/experiment-resources" --source "$(git rev-parse HEAD)"
fi
if [[ "$lane" == all || "$lane" == storage ]]; then
  python3 -m unittest scripts.v51.test_cloud_runner_storage scripts.v51.test_cloud_runner_storage_entry scripts.v51.test_cloud_runner_resources scripts.v51.test_cloud_runner_iap scripts.v51.test_cloud_runner_connections scripts.v51.test_cloud_runner_guest_setup scripts.v51.test_cloud_runner_failure scripts.v51.test_cloud_runner_owned scripts.v51.test_guest_native_session
  timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_runner_storage_qualification "$work_dir/runner-storage"
  timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_runner_storage_entry_qualification "$work_dir/runner-storage-entry"
  timeout --signal=TERM --kill-after=5s 600s python3 -m scripts.v51.cloud_runner_resource_qualification "$work_dir/runner-resource-entry"
fi
