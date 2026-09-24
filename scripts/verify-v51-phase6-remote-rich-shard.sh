#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
if [[ $# -ne 1 || ! "$1" =~ ^(published-controls|automatic-healthy|automatic-concurrent)$ ]]; then
  echo "usage: $0 {published-controls|automatic-healthy|automatic-concurrent}" >&2
  exit 2
fi
: "${GITHUB_SHA:?exact source required}"
: "${V51_RICH_INPUTS:?prepared inputs required}"
python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
"$python_command" -m unittest scripts.v51.test_remote_rich scripts.v51.test_remote_schedule_evidence scripts.v51.test_remote_rich_shards
# Whole cells retain their original ceilings and cleanup; no measurement retry.
timeout --signal=TERM --kill-after=5s 2400s "$python_command" -m scripts.v51.remote_rich_shards run \
  "target/v51-remote-rich-shard/$1" --shard "$1" --source "$GITHUB_SHA" \
  --build-manifest target/ci-v51-build/manifest.json --inputs "$V51_RICH_INPUTS"
