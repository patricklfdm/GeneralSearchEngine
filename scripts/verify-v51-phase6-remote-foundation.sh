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
"$python_command" -m unittest scripts.v51.test_remote_command scripts.v51.test_remote_schedule scripts.v51.test_remote_schedule_evidence scripts.v51.test_remote_budget scripts.v51.test_remote_collection
mkdir -p target/v51-remote-foundation
work_dir=$(mktemp -d "$root/target/v51-remote-foundation/run.XXXXXX")
echo "v51RemoteFoundationEvidence=$work_dir/evidence"
timeout --signal=TERM --kill-after=5s 120s "$python_command" -m scripts.v51.remote_qualification "$work_dir/evidence"
echo 'v51RemoteFoundation=PASS execution=local-remote-control-only paidCloud=false fullRemoteQualification=false'
