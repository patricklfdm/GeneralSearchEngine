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
"$python_command" -m unittest scripts.v51.test_full_size
mkdir -p target/v51-full-size
work_dir=$(mktemp -d "$root/target/v51-full-size/run.XXXXXX")
echo "v51FullSizeEvidence=$work_dir"
timeout --signal=TERM --kill-after=5s 600s "$python_command" -m scripts.v51.full_size_harness "$work_dir/evidence"
echo 'v51FullSize=PASS execution=local-component-boundaries paidCloud=false fullRemoteQualification=false'
