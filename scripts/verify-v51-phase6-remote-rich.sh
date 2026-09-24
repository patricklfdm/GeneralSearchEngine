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
"$python_command" -m unittest scripts.v51.test_remote_rich scripts.v51.test_remote_schedule_evidence
mkdir -p target/v51-remote-rich
work_dir=$(mktemp -d "$root/target/v51-remote-rich/run.XXXXXX")
echo "v51RemoteRichEvidence=$work_dir"
# Full frozen windows take 1080 seconds before startup/restore/validation.
# This is a local process-group backstop; each original cell ceiling remains enforced.
timeout --signal=TERM --kill-after=5s 2400s "$python_command" -m scripts.v51.remote_rich_qualification "$work_dir/evidence"
echo 'v51RemoteRich=PASS execution=local-guest-rich-workload-only paidCloud=false fullRemoteQualification=false'
