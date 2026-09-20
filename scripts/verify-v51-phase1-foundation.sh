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
scripts/verify-version-alignment.sh 5.1.0-SNAPSHOT
scripts/verify-v50-phase0-contract.sh
python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
"$python_command" -m scripts.v51.contract
"$python_command" -m unittest discover -s scripts/v51 -t . -p 'test_*.py'
mkdir -p target/v51-foundation
work_dir=$(mktemp -d "$root/target/v51-foundation/run.XXXXXX")
echo "v51FoundationEvidence=$work_dir/evidence"
"$python_command" -m scripts.v51.foundation "$work_dir/evidence"
echo 'v51Phase1Foundation=PASS execution=independent-foundation-only automaticRuntime=disabled paidCloud=disabled'
