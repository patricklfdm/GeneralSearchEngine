#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--skip-build" ) ]]; then
  echo "usage: $0 [--skip-build]" >&2
  exit 2
fi
if [[ $# -eq 0 ]]; then
  ./mvnw -f reactor/pom.xml test
fi
python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
"$python_command" -m unittest scripts.v50.test_admission_format
mkdir -p target/v50-admission-foundation
"$python_command" -m scripts.v50.admission_evidence \
  --output target/v50-admission-foundation/receipt.json
scripts/verify-v50-phase0-contract.sh
echo 'v50PublicAdmissionStepA=PASS publicRuntime=disabled offlineAuthorityGate=separate'
