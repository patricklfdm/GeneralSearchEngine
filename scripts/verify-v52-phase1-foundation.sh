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
python3 -m unittest scripts.test_build_coordinates
python3 -m unittest discover -s scripts/v52 -t . -p 'test_*.py'
mkdir -p target/v52-foundation
work_dir=$(mktemp -d "$root/target/v52-foundation/run.XXXXXX")
echo "v52FoundationEvidence=$work_dir/evidence"
python3 -m scripts.v52.foundation "$work_dir/evidence"
