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
python3 -m unittest scripts.v52.test_public_read_hardening_evidence scripts.v52.test_public_reads_evidence
mkdir -p target/v52-read-hardening
work=$(mktemp -d "$root/target/v52-read-hardening/run.XXXXXX")
echo "v52ReadHardeningEvidence=$work/evidence"
timeout --signal=TERM --kill-after=5s 900s python3 -m scripts.v52.public_read_hardening_harness "$work/evidence"
