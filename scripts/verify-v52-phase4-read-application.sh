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
python3 -m unittest scripts.v51.test_public_command_inspector scripts.v52.test_public_reads_evidence
mkdir -p target/v52-public-read-application
work=$(mktemp -d "$root/target/v52-public-read-application/run.XXXXXX")
echo "v52PublicReadApplicationEvidence=$work/evidence"
timeout --signal=TERM --kill-after=5s 600s python3 -m scripts.v52.public_read_application_harness "$work/evidence"
