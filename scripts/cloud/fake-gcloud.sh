#!/usr/bin/env bash
set -euo pipefail

: "${FAKE_GCLOUD_STATE_DIR:?FAKE_GCLOUD_STATE_DIR is required}"
scenario=${FAKE_GCLOUD_SCENARIO:-success}
command_log="$FAKE_GCLOUD_STATE_DIR/commands.log"
mkdir -p "$FAKE_GCLOUD_STATE_DIR"
printf '%q ' "$@" >> "$command_log"
printf '\n' >> "$command_log"

instance_file="$FAKE_GCLOUD_STATE_DIR/instance"
status_file="$FAKE_GCLOUD_STATE_DIR/status"
remote_state_file="$FAKE_GCLOUD_STATE_DIR/remote-state.properties"
marker_file="$FAKE_GCLOUD_STATE_DIR/interruption.properties"
remote_result_dir="$FAKE_GCLOUD_STATE_DIR/remote-result"
remote_result_path="/home/fake/GeneralSearchEngine/benchmark-results/v3-production/${scenario}-run"

argument_value() {
  prefix=$1
  shift
  argument_result=
  for item in "$@"; do
    case "$item" in
      "$prefix"*) argument_result=${item#"$prefix"}; return 0 ;;
    esac
  done
  return 1
}

create_result() {
  result_status=$1
  include_checksum=$2
  rm -rf -- "$remote_result_dir"
  mkdir -p "$remote_result_dir"
  printf 'status=%s\nmode=quick\nexit_code=%s\n' \
    "$result_status" "$([ "$result_status" = PASS ] && printf 0 || printf 1)" \
    > "$remote_result_dir/status.properties"
  printf 'git_commit=%s\n' "$(git -C "$FAKE_GCLOUD_REPO" rev-parse HEAD)" \
    > "$remote_result_dir/metadata.txt"
  printf 'fake-environment=true\n' > "$remote_result_dir/environment.txt"
  if [ "$include_checksum" = true ]; then
    (
      cd "$remote_result_dir"
      find . -type f ! -name checksums.sha256 -print0 \
        | sort -z \
        | xargs -0 sha256sum > checksums.sha256
    )
  fi
}

case "${1:-} ${2:-} ${3:-}" in
  'auth list '*)
    printf 'fake@example.test\n'
    ;;
  'config get-value project')
    printf 'fake-project\n'
    ;;
  'config get-value compute/zone')
    printf 'us-central1-a\n'
    ;;
  'compute machine-types describe')
    printf 'c3d-standard-30\n'
    ;;
  'compute images describe-from-family'|'compute images describe')
    printf 'ubuntu-2404-noble-amd64-v20260801\t123456789\thttps://compute.example/images/123456789\t2026-08-01T00:00:00Z\n'
    ;;
  'compute networks describe'|'compute networks subnets')
    printf 'default\n'
    ;;
  'compute instances create')
    printf '%s\n' "${4:-fake-instance}" > "$instance_file"
    printf 'RUNNING\n' > "$status_file"
    if [ "$scenario" = create_partial_failure ]; then exit 1; fi
    ;;
  'compute instances describe')
    [ -f "$instance_file" ] || exit 1
    if printf '%s\n' "$@" | grep -q 'value(status)'; then
      sed -n '1p' "$status_file"
    else
      sed -n '1p' "$instance_file"
    fi
    ;;
  'compute instances delete')
    if [ "$scenario" = cleanup_failure ]; then exit 1; fi
    rm -f -- "$instance_file" "$status_file"
    ;;
  'compute instances start')
    printf 'RUNNING\n' > "$status_file"
    printf 'preempted=true\nobserved_utc=20260827T000000Z\n' > "$marker_file"
    ;;
  'compute ssh '*)
    [ -f "$instance_file" ] || exit 1
    [ "$(sed -n '1p' "$status_file")" = RUNNING ] || exit 255
    argument_value '--command=' "$@" || argument_result=
    case "$argument_result" in
      true) ;;
      'bash -s -- '*'/var/lib/gse-cloud-benchmark')
        if [ "$scenario" = bootstrap_preempted ]; then
          printf 'state=BOOTSTRAPPING\nupdated_utc=20260827T000000Z\n' > "$remote_state_file"
          printf 'TERMINATED\n' > "$status_file"
          exit 255
        fi
        printf 'state=READY\nupdated_utc=20260827T000000Z\n' > "$remote_state_file"
        ;;
      env\ *)
        requested_commit=$(git -C "$FAKE_GCLOUD_REPO" rev-parse HEAD)
        if [ "$scenario" = preempted ]; then
          create_result RUNNING false
          printf 'state=RUNNING\nrequested_commit=%s\nremote_commit=%s\nbenchmark_exit_code=\nresult_path=%s\n' \
            "$requested_commit" "$requested_commit" "$remote_result_path" > "$remote_state_file"
          printf 'TERMINATED\n' > "$status_file"
          exit 255
        fi
        if [ "$scenario" = benchmark_fail ]; then
          create_result FAIL true
          printf 'state=BENCHMARK_FAIL\nrequested_commit=%s\nremote_commit=%s\nbenchmark_exit_code=1\nresult_path=%s\n' \
            "$requested_commit" "$requested_commit" "$remote_result_path" > "$remote_state_file"
          exit 1
        fi
        create_result PASS true
        if [ "$scenario" = checksum_failure ]; then
          printf 'tampered=true\n' >> "$remote_result_dir/metadata.txt"
        fi
        printf 'state=BENCHMARK_PASS\nrequested_commit=%s\nremote_commit=%s\nbenchmark_exit_code=0\nresult_path=%s\n' \
          "$requested_commit" "$requested_commit" "$remote_result_path" > "$remote_state_file"
        ;;
      'sudo cat /var/lib/gse-cloud-benchmark/state.properties')
        cat "$remote_state_file"
        ;;
      'sudo cat /var/lib/gse-cloud-benchmark/interruption.properties')
        cat "$marker_file"
        ;;
      bash\ -c\ *)
        if [ "$scenario" = bad_result_path ]; then
          printf '/etc\n'
        else
          printf '%s\n' "$remote_result_path"
        fi
        ;;
      *)
        echo "Unsupported fake SSH command: $argument_result" >&2
        exit 98
        ;;
    esac
    ;;
  'compute scp '*)
    if [ "$scenario" = scp_failure ]; then exit 1; fi
    destination=${5:-}
    if [[ "$destination" == --* ]] || [ -z "$destination" ]; then
      echo "Fake scp could not identify destination" >&2
      exit 98
    fi
    cp -R "$remote_result_dir" "$destination/${scenario}-run"
    ;;
  *)
    echo "Unsupported fake gcloud command: $*" >&2
    exit 99
    ;;
esac
