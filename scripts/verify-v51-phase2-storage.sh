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
scripts/verify-version-alignment.sh
python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
"$python_command" -m unittest scripts.v51.test_storage_inspector
mkdir -p target/v51-storage
work=$(mktemp -d "$root/target/v51-storage/run.XXXXXX")
echo "v51StorageEvidence=$work/evidence"
"$python_command" -m scripts.v51.storage_harness "$work/evidence"
echo 'v51Storage=PASS execution=automatic-root-ledger-only publicRuntime=false'
