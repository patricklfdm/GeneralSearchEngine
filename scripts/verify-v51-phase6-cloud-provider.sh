#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
if [[ $# -ne 0 ]]; then
  echo "usage: $0" >&2
  exit 2
fi
python3 -m unittest scripts.v51.test_cloud_provider scripts.v51.test_cloud_package
mkdir -p target/v51-cloud-provider
work_dir=$(mktemp -d "$root/target/v51-cloud-provider/run.XXXXXX")
echo "v51ProviderEvidence=$work_dir/evidence"
timeout --signal=TERM --kill-after=5s 120s python3 -m scripts.v51.cloud_provider_qualification "$work_dir/evidence"
echo 'v51Provider=PASS execution=offline-provider-http paidCloud=false fullRemoteQualification=false'
