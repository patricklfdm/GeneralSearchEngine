#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
skip_build=false
skip_python=false
for arg in "$@"; do
  case "$arg" in
    --skip-build) skip_build=true ;;
    --skip-python-tests) skip_python=true ;;
    *) echo "usage: $0 [--skip-build [--skip-python-tests]]" >&2; exit 2 ;;
  esac
done
if $skip_python && ! $skip_build; then
  echo '--skip-python-tests requires --skip-build and the separate required Python CI lanes' >&2
  exit 2
fi
if ! $skip_build; then
  ./mvnw -f reactor/pom.xml package
fi
scripts/verify-version-alignment.sh 5.1.0-SNAPSHOT
scripts/verify-v50-phase0-contract.sh
python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
"$python_command" -m scripts.v51.contract
if ! $skip_python; then
  "$python_command" -m unittest discover -s scripts/v51 -t . -p 'test_*.py'
fi
mkdir -p target/v51-foundation
work_dir=$(mktemp -d "$root/target/v51-foundation/run.XXXXXX")
echo "v51FoundationEvidence=$work_dir/evidence"
"$python_command" -m scripts.v51.foundation "$work_dir/evidence"
echo 'v51Phase1Foundation=PASS execution=independent-foundation-only automaticRuntime=not-executed paidCloud=disabled'
