#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./compare-cloud-benchmark.sh [--allow-exploratory] BASELINE CANDIDATE

BASELINE and CANDIDATE are completed Phase 1 run or Phase 2 set directories/manifests.
Only BASELINE may also be a name from docs/v3/cloud-benchmark-baselines.json.
EOF
}

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$repo_root"

allow_exploratory=false
if [ "${1:-}" = "--allow-exploratory" ]; then
  allow_exploratory=true
  shift
elif [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
elif [[ "${1:-}" == -* ]]; then
  echo "ERROR: Unknown option: ${1:-}" >&2
  exit 2
fi

[ "$#" -eq 2 ] || { usage >&2; exit 2; }
[[ "$1" != -* ]] || { echo 'ERROR: Baseline operand must not begin with a hyphen' >&2; exit 2; }
[[ "$2" != -* ]] || { echo 'ERROR: Candidate operand must not begin with a hyphen' >&2; exit 2; }

results_root=${GSE_BENCHMARK_RESULTS_ROOT:-benchmark-results/v3-production}
command=(python3 scripts/cloud/benchmark_v2.py compare
  --results-root "$results_root"
  --registry docs/v3/cloud-benchmark-baselines.json)
if [ "$allow_exploratory" = true ]; then
  command+=(--allow-exploratory)
fi
command+=("$1" "$2")
exec "${command[@]}"
