#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$repo_root"

exec python3 scripts/cloud/benchmark_v2.py upload \
  --results-root benchmark-results/v3-production \
  --bucket "${GSE_BENCHMARK_GCS_BUCKET:-}" \
  "$@"
