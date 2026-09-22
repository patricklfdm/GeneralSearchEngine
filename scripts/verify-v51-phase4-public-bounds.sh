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
python3 -m unittest scripts.v51.test_public_bounds_evidence
mkdir -p target/v51-public-bounds
work=$(mktemp -d "$root/target/v51-public-bounds/run.XXXXXX")
echo "v51PublicBoundsEvidence=$work/evidence"
python3 -m scripts.v51.public_bounds_harness "$work/evidence"
