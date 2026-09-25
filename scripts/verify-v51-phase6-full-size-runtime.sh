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
"$python_command" -m unittest scripts.v51.test_full_size_runtime
mkdir -p target/v51-full-size-runtime
work_dir=$(mktemp -d "$root/target/v51-full-size-runtime/run.XXXXXX")
echo "v51FullSizeRuntimeEvidence=$work_dir"
timeout --signal=TERM --kill-after=15s 1200s "$python_command" -m scripts.v51.full_size_runtime "$work_dir/evidence"
echo 'v51FullSizeRuntime=PASS execution=local-public-full-size-runtime paidCloud=false fullRemoteQualification=false'
