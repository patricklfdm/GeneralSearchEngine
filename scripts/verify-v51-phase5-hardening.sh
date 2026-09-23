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
python3 -m unittest scripts.v51.test_hardening_evidence scripts.v51.test_public_pressure_evidence
mkdir -p target/v51-hardening
work=$(mktemp -d "$root/target/v51-hardening/run.XXXXXX")
echo "v51HardeningEvidence=$work/evidence"
python3 -m scripts.v51.hardening_harness "$work/evidence"
