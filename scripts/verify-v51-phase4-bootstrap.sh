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
mkdir -p target/v51-bootstrap
work=$(mktemp -d "$root/target/v51-bootstrap/run.XXXXXX")
echo "v51BootstrapEvidence=$work/evidence"
python3 -m scripts.v51.bootstrap_harness "$work/evidence"
