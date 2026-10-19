#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
if [[ $# -eq 0 ]]; then
  ./mvnw -f reactor/pom.xml package
elif [[ $# -ne 1 || "$1" != --skip-build ]]; then
  echo "usage: $0 [--skip-build]" >&2
  exit 2
fi
python3 -m unittest scripts.v52.test_remote_python_histories scripts.v52.test_remote_python_runtime scripts.v52.test_remote_python_runtime_evidence scripts.v52.test_remote_partition scripts.v52.test_remote_restart scripts.v52.test_remote_formal
mkdir -p target/v52-installed-histories
work_dir=$(mktemp -d "$root/target/v52-installed-histories/run.XXXXXX")
echo "v52InstalledHistoriesEvidence=$work_dir/evidence"
python3 -u -m scripts.v52.remote_python_histories "$work_dir/evidence"
