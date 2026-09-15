#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
if [[ $# -eq 0 ]]; then
  ./mvnw -f reactor/pom.xml clean test
elif [[ $# -ne 1 || "$1" != --skip-build ]]; then
  echo "usage: $0 [--skip-build]" >&2
  exit 2
fi
python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
"$python_command" -m unittest scripts.v50.test_storage_format
mkdir -p target/v50-storage
work_parent=$(mktemp -d "$root/target/v50-storage/run.XXXXXX")
echo "v50Phase2Evidence=$work_parent/evidence"
"$python_command" -m scripts.v50.storage_harness "$work_parent/evidence"
echo "v50Phase2Storage=PASS productionRuntime=disabled paidCloud=disabled"
