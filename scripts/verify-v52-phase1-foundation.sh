#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
skip_build=false
skip_python=false
for arg in "$@"; do
  case "$arg" in
    --skip-build) [[ "$skip_build" == false ]] || exit 2; skip_build=true ;;
    --skip-python) [[ "$skip_python" == false ]] || exit 2; skip_python=true ;;
    *) echo "usage: $0 [--skip-build [--skip-python]]" >&2; exit 2 ;;
  esac
done
[[ "$skip_python" == false || "$skip_build" == true ]] || exit 2
if [[ "$skip_build" == false ]]; then ./mvnw -f reactor/pom.xml package; fi
scripts/verify-version-alignment.sh
python3 -m unittest scripts.test_build_coordinates
if [[ "$skip_python" == false ]]; then python3 -m unittest discover -s scripts/v52 -t . -p 'test_*.py'; fi
mkdir -p target/v52-foundation
work_dir=$(mktemp -d "$root/target/v52-foundation/run.XXXXXX")
echo "v52FoundationEvidence=$work_dir/evidence"
python3 -m scripts.v52.foundation "$work_dir/evidence"
python3 -m scripts.v52.measurement_foundation "$work_dir/measurement"
python3 -m scripts.v52.measurement_trace_foundation "$work_dir/measurement-trace"
