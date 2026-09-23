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
python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
"$python_command" -m scripts.v51.performance_plan
"$python_command" -m unittest scripts.v51.test_performance_runtime scripts.v51.test_performance_artifacts
mkdir -p target/v51-performance
work_dir=$(mktemp -d "$root/target/v51-performance/run.XXXXXX")
echo "v51PerformanceEvidence=$work_dir/evidence"
# The controller reserves the final 60 seconds for owned-process cleanup.
# GNU timeout is an outer process-group backstop, not an enlarged stage budget.
timeout --signal=TERM --kill-after=5s 900s "$python_command" -m scripts.v51.performance_harness "$work_dir/evidence"
echo 'v51Performance=PASS execution=local-public-runtime-only paidCloud=false'
