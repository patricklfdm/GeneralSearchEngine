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
python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
mkdir -p target/v51-runtime
work=$(mktemp -d "$root/target/v51-runtime/run.XXXXXX")
echo "v51RuntimeEvidence=$work/evidence"
"$python_command" -m scripts.v51.runtime_harness "$work/evidence"
echo 'v51Runtime=PASS execution=internal-runtime-real-tcp publicRuntime=false'
