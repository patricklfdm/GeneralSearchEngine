#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$repo_root"

exec python3 scripts/cloud/benchmark_v2.py baseline-register \
  --results-root benchmark-results/v3-production \
  --registry docs/v3/cloud-benchmark-baselines.json \
  "$@"
