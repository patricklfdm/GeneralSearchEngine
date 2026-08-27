#!/usr/bin/env bash
set -euo pipefail

repo_url=$1
requested_commit=$2
mode=$3
state_dir=${4:-/var/lib/gse-cloud-benchmark}
workspace=$HOME/GeneralSearchEngine
state_file="$state_dir/state.properties"
remote_log="$state_dir/remote-benchmark.log"
benchmark_exit_code=
result_path=
remote_commit=
final_state=REMOTE_SETUP_FAIL
state_finalized=false

install -d -m 0750 "$state_dir"
exec > >(tee -a "$remote_log") 2>&1

write_state() {
  state=$1
  temporary="$state_file.tmp.$$"
  {
    printf 'state=%s\n' "$state"
    printf 'updated_utc=%s\n' "$(date -u +%Y%m%dT%H%M%SZ)"
    printf 'requested_commit=%s\n' "$requested_commit"
    printf 'benchmark_mode=%s\n' "$mode"
    printf 'benchmark_pid=%s\n' "$$"
    if [ -n "$remote_commit" ]; then
      printf 'remote_commit=%s\n' "$remote_commit"
    fi
    if [ -n "$benchmark_exit_code" ]; then
      printf 'benchmark_exit_code=%s\n' "$benchmark_exit_code"
    fi
    if [ -n "$result_path" ]; then
      printf 'result_path=%s\n' "$result_path"
    fi
  } > "$temporary"
  mv "$temporary" "$state_file"
}

finish_remote_state() {
  exit_code=$?
  trap - EXIT
  if [ "$state_finalized" != true ]; then
    write_state "$final_state"
  fi
  exit "$exit_code"
}
trap finish_remote_state EXIT

write_state REMOTE_SETUP
if [ -e "$workspace" ]; then
  echo "Remote workspace already exists: $workspace" >&2
  exit 20
fi

install -d "$workspace"
git -C "$workspace" init --quiet
git -C "$workspace" remote add origin "$repo_url"
cd "$workspace"
git fetch --quiet --depth=1 origin "$requested_commit"
git checkout --quiet --detach "$requested_commit"
remote_commit=$(git rev-parse HEAD)
if [ "$remote_commit" != "$requested_commit" ]; then
  echo "Remote checkout mismatch: requested $requested_commit, got $remote_commit" >&2
  exit 20
fi
if [ -n "$(git status --short)" ]; then
  echo "Remote checkout is unexpectedly dirty" >&2
  git status --short >&2
  exit 20
fi

git rev-parse HEAD
git status --short
java -version
./mvnw -version

final_state=RUNNING
write_state RUNNING
set +e
scripts/run-v3-production-performance.sh "$mode"
benchmark_exit_code=$?
set -e

results_root=$(realpath benchmark-results/v3-production)
latest_file="$results_root/LATEST"
if [ ! -f "$latest_file" ]; then
  final_state=ARTIFACT_MISSING
  write_state "$final_state"
  state_finalized=true
  trap - EXIT
  exit "$benchmark_exit_code"
fi

latest_value=$(sed -n '1p' "$latest_file")
if [ -z "$latest_value" ] || [ "$(wc -l < "$latest_file")" -ne 1 ]; then
  echo "Remote LATEST is empty or contains multiple lines" >&2
  final_state=ARTIFACT_INVALID
  write_state "$final_state"
  state_finalized=true
  trap - EXIT
  exit "$benchmark_exit_code"
fi
result_path=$(realpath -e -- "$latest_value")
case "$result_path" in
  "$results_root"/*) ;;
  *)
    echo "Remote result escaped the expected root: $result_path" >&2
    final_state=ARTIFACT_INVALID
    write_state "$final_state"
    state_finalized=true
    trap - EXIT
    exit "$benchmark_exit_code"
    ;;
esac
if [ "$(dirname "$result_path")" != "$results_root" ] || [ ! -d "$result_path" ]; then
  echo "Remote result is not a direct run directory: $result_path" >&2
  final_state=ARTIFACT_INVALID
  write_state "$final_state"
  state_finalized=true
  trap - EXIT
  exit "$benchmark_exit_code"
fi

if [ "$benchmark_exit_code" -eq 0 ]; then
  final_state=BENCHMARK_PASS
else
  final_state=BENCHMARK_FAIL
fi
write_state "$final_state"
state_finalized=true
trap - EXIT
exit "$benchmark_exit_code"
