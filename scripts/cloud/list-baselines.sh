#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$repo_root"

[ "$#" -eq 0 ] || { echo 'Usage: scripts/cloud/list-baselines.sh' >&2; exit 2; }
exec python3 scripts/cloud/benchmark_v2.py registry-list \
  docs/v3/cloud-benchmark-baselines.json
