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
python3 -m unittest scripts.v52.test_measurement_model scripts.v52.test_measurement_trace scripts.v52.test_measurement_oracle scripts.v52.test_measurement_runtime_evidence scripts.v52.test_measurement_load scripts.v52.test_measurement_samples scripts.v52.test_measurement_bundle scripts.v52.test_measurement_projection scripts.v52.test_measurement_stream scripts.v52.test_measurement_history scripts.v52.test_measurement_publication scripts.v52.test_measurement_window
mkdir -p target/v52-measurement-runtime
work_dir=$(mktemp -d "$root/target/v52-measurement-runtime/run.XXXXXX")
echo "v52MeasurementConsumerEvidence=$work_dir/evidence"
timeout --signal=TERM --kill-after=10s 900s python3 -m scripts.v52.measurement_runtime "$work_dir/evidence" --exercise-load
