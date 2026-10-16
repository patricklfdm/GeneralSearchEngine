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
python3 -m unittest scripts.v52.test_measurement_model scripts.v52.test_measurement_trace scripts.v52.test_measurement_oracle scripts.v52.test_measurement_runtime_evidence scripts.v52.test_measurement_load scripts.v52.test_measurement_samples scripts.v52.test_measurement_bundle scripts.v52.test_measurement_projection scripts.v52.test_measurement_stream scripts.v52.test_measurement_history scripts.v52.test_measurement_publication scripts.v52.test_measurement_window scripts.v52.test_measurement_m01 scripts.v52.test_measurement_authority_budget scripts.v52.test_measurement_m01_evidence scripts.v52.test_measurement_m01_set scripts.v52.test_measurement_options scripts.v52.test_measurement_minimum scripts.v52.test_measurement_minimum_evidence scripts.v52.test_measurement_recovery scripts.v52.test_measurement_generations scripts.v52.test_measurement_recovery_evidence scripts.v52.test_measurement_machine scripts.v52.test_measurement_verified scripts.v52.test_cloud_suite scripts.v52.test_remote_topology scripts.v52.test_remote_bootstrap_evidence scripts.v52.test_remote_identity scripts.v52.test_remote_runtime_qualification scripts.v52.test_remote_command scripts.v52.test_remote_slots scripts.v52.test_remote_owned_history scripts.v52.test_remote_history scripts.v52.test_remote_history_qualification scripts.v52.test_remote_ssh scripts.v52.test_remote_voter scripts.v52.test_remote_voter_ssh scripts.v52.test_remote_voter_lifecycle scripts.v52.test_remote_delivery scripts.v52.test_remote_partition scripts.v52.test_remote_restart scripts.v52.test_remote_formal scripts.v52.test_remote_python
mkdir -p target/v52-measurement-runtime
work_dir=$(mktemp -d "$root/target/v52-measurement-runtime/run.XXXXXX")
echo "v52MeasurementConsumerEvidence=$work_dir/evidence"
timeout --signal=TERM --kill-after=10s 900s python3 -m scripts.v52.measurement_runtime "$work_dir/evidence" --exercise-load
python3 -m scripts.v52.remote_bootstrap_qualification "$work_dir/remote-bootstrap"
python3 -m scripts.v52.remote_runtime_qualification "$work_dir/remote-runtime"
python3 -m scripts.v52.remote_command_qualification "$work_dir/remote-commands"
python3 -m scripts.v52.remote_owned_history "$work_dir/owned-history"
