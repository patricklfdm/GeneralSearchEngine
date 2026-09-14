#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"
if command -v python3.11 >/dev/null 2>&1; then python_command=python3.11; else python_command=python3; fi

"$python_command" -m py_compile \
    scripts/v44/cloud_set.py scripts/v44/test_phase6_registration.py
"$python_command" -m unittest scripts.v44.test_phase6_registration

expected=$'v4.4.0-final-durable-cloud\tf1435bdf528138363986542ecafac563dbee0cf9dbed60f781ada27ff53c6465\t6301d855a92a3b2de8d9c338232a520fb9dd2b36'
actual=$("$python_command" -m scripts.v44.cloud_set registry-list \
    docs/v4x/v4.4/cloud-benchmark-baselines.json)
[[ "$actual" = "$expected" ]] || {
    echo "V4.4 registered baseline identity differs" >&2
    exit 1
}

echo "V4.4 Phase 6 append-only registration: PASS"
