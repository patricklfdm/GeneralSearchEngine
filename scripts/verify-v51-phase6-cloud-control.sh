#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
if [[ $# -ne 0 ]]; then
  echo "usage: $0" >&2
  exit 2
fi
python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
"$python_command" -m unittest scripts.v51.test_cloud_authority scripts.v51.test_cloud_runner
mkdir -p target/v51-cloud-control
work_dir=$(mktemp -d "$root/target/v51-cloud-control/run.XXXXXX")
echo "v51CloudControlEvidence=$work_dir/evidence"
timeout --signal=TERM --kill-after=5s 120s "$python_command" -m scripts.v51.cloud_qualification "$work_dir/evidence"
echo 'v51CloudControl=PASS execution=fake-v51-cloud-control paidCloud=false fullRemoteQualification=false'
