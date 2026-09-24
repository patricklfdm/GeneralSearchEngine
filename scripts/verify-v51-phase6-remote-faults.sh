#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --skip-build ) ]]; then
  echo "usage: $0 [--skip-build]" >&2
  exit 2
fi
if [[ $# -eq 0 ]]; then
  ./mvnw -f reactor/pom.xml package
fi
python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
"$python_command" -m unittest scripts.v51.test_remote_faults scripts.v51.test_cloud_workload_contract
mkdir -p target/v51-remote-faults
work_dir=$(mktemp -d "$root/target/v51-remote-faults/run.XXXXXX")
echo "v51RemoteFaultEvidence=$work_dir"
timeout --signal=TERM --kill-after=5s 2400s "$python_command" -m scripts.v51.remote_fault_qualification "$work_dir/evidence"
echo 'v51RemoteFaults=PASS execution=local-guest-faults-only paidCloud=false fullRemoteQualification=false'
