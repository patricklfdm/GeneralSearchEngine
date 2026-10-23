#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
skip_build=false
lane=all
lane_set=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-build) [[ "$skip_build" == false ]] || exit 2; skip_build=true; shift ;;
    --lane) [[ "$lane_set" == false && $# -ge 2 ]] || exit 2; lane=$2; lane_set=true; shift 2 ;;
    *) echo "usage: $0 [--skip-build] [--lane all|unit|consumers|commands|installed]" >&2; exit 2 ;;
  esac
done
case "$lane" in all|unit|consumers|commands|installed) ;; *) exit 2 ;; esac
if [[ "$skip_build" == false ]]; then ./mvnw -f reactor/pom.xml package; fi
if [[ "$lane" == all || "$lane" == unit ]]; then
python3 -m unittest scripts.v52.test_measurement_model scripts.v52.test_measurement_trace scripts.v52.test_measurement_oracle scripts.v52.test_measurement_runtime_evidence scripts.v52.test_measurement_load scripts.v52.test_measurement_samples scripts.v52.test_measurement_bundle scripts.v52.test_measurement_projection scripts.v52.test_measurement_stream scripts.v52.test_measurement_history scripts.v52.test_measurement_publication scripts.v52.test_measurement_window scripts.v52.test_measurement_m01 scripts.v52.test_measurement_authority_budget scripts.v52.test_measurement_m01_evidence scripts.v52.test_measurement_m01_set scripts.v52.test_measurement_options scripts.v52.test_measurement_minimum scripts.v52.test_measurement_minimum_evidence scripts.v52.test_measurement_recovery scripts.v52.test_measurement_generations scripts.v52.test_measurement_recovery_evidence scripts.v52.test_measurement_machine scripts.v52.test_measurement_verified scripts.v52.test_cloud_suite scripts.v52.test_cloud_drill_shards scripts.v52.test_remote_topology scripts.v52.test_remote_bootstrap_evidence scripts.v52.test_remote_identity scripts.v52.test_remote_runtime_qualification scripts.v52.test_remote_command scripts.v52.test_remote_slots scripts.v52.test_remote_owned_history scripts.v52.test_remote_history scripts.v52.test_remote_history_qualification scripts.v52.test_remote_ssh scripts.v52.test_remote_voter scripts.v52.test_remote_voter_ssh scripts.v52.test_remote_voter_lifecycle scripts.v52.test_remote_delivery scripts.v52.test_remote_partition scripts.v52.test_remote_restart scripts.v52.test_remote_formal scripts.v52.test_remote_python scripts.v52.test_remote_python_runtime scripts.v52.test_remote_python_runtime_evidence scripts.v52.test_remote_python_histories scripts.v52.test_remote_host_domains scripts.v51.test_runtime_process_generations scripts.v52.test_remote_bound_receivers scripts.v52.test_cloud_authority scripts.v52.test_cloud_control scripts.v52.test_cloud_provider scripts.v52.test_cloud_identity scripts.v52.test_cloud_credentials scripts.v52.test_cloud_wire_policy scripts.v52.test_cloud_inputs scripts.v52.test_cloud_prepared scripts.v52.test_cloud_ci scripts.v52.test_cloud_artifacts scripts.v52.test_cloud_preflight scripts.v52.test_cloud_native_cleanup scripts.v52.test_cloud_acquisition_context scripts.v52.test_cloud_cleanup_bundle scripts.v52.test_cloud_recent_cleanup scripts.v52.test_cloud_native_runner scripts.v52.test_cloud_iap scripts.v52.test_cloud_volume scripts.v52.test_cloud_storage scripts.v52.test_remote_java scripts.v52.test_remote_java_evidence scripts.v52.test_cloud_java scripts.v52.test_cloud_staging scripts.v52.test_cloud_member scripts.v52.test_cloud_member_factory scripts.v52.test_cloud_evidence_parts scripts.v52.test_cloud_retention scripts.v52.test_cloud_member_evidence scripts.v52.test_cloud_set_evidence scripts.v52.test_cloud_evidence_read
fi
if [[ "$lane" == unit ]]; then exit 0; fi
mkdir -p target/v52-measurement-runtime
work_dir=$(mktemp -d "$root/target/v52-measurement-runtime/run.XXXXXX")
echo "v52MeasurementConsumerEvidence=$work_dir/evidence"
if [[ "$lane" == all || "$lane" == consumers ]]; then
timeout --signal=TERM --kill-after=10s 900s python3 -m scripts.v52.measurement_runtime "$work_dir/evidence" --exercise-load
python3 -m scripts.v52.remote_bootstrap_qualification "$work_dir/remote-bootstrap"
python3 -m scripts.v52.remote_runtime_qualification "$work_dir/remote-runtime"
fi
if [[ "$lane" == all || "$lane" == commands ]]; then
python3 -m scripts.v52.remote_command_qualification "$work_dir/remote-commands"
python3 -m scripts.v52.remote_owned_history "$work_dir/owned-history"
fi
if [[ "$lane" == all || "$lane" == installed ]]; then
python3 -m scripts.v52.cloud_volume_qualification "$work_dir/native-storage-root" --allow-sudo-namespace
python3 -m scripts.v52.remote_java_qualification "$work_dir/native-java"
fi
