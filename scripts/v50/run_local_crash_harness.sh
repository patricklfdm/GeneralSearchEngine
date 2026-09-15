#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root"

if [[ $# -ne 1 ]]; then
  echo "usage: $0 WORKSPACE" >&2
  exit 2
fi
workspace=$1
if [[ -z "$workspace" || "$workspace" == "/" ]]; then
  echo "unsafe workspace" >&2
  exit 2
fi
[[ ! -e "$workspace" && ! -L "$workspace" ]] || {
  echo "workspace must be fresh and absent" >&2
  exit 2
}
mkdir -p "$workspace"
workspace=$(cd "$workspace" && pwd)
case "$workspace" in
  /tmp/*|"$root"/target/*) ;;
  *) echo "workspace must be under /tmp or target" >&2; exit 2 ;;
esac

python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
record_event() {
  "$python_command" - "$workspace/process-events.jsonl" "$@" <<'PY'
import json
from pathlib import Path
import sys
path = Path(sys.argv[1])
action = sys.argv[2]
sequence = len(path.read_text().splitlines()) if path.exists() else 0
event = {"sequence": sequence, "action": action}
if action == "concurrent":
    event["pids"] = {f"node-{i}": int(pid) for i, pid in enumerate(sys.argv[3:], 1)}
else:
    event.update(node=sys.argv[3], pid=int(sys.argv[4]), generation=int(sys.argv[5]))
    if len(sys.argv) > 6:
        event["exitCode"] = int(sys.argv[6])
with path.open("a") as output:
    output.write(json.dumps(event, sort_keys=True) + "\n")
PY
}

worker_class=io.github.patricklfdm.generalsearch.replication.V50ReplicaFixtureWorker
class_path=general-search-engine-replication/target/test-classes
[[ -f "$class_path/io/github/patricklfdm/generalsearch/replication/V50ReplicaFixtureWorker.class" ]] || {
  echo "fixture worker is not compiled" >&2
  exit 1
}

pids=()
cleanup_processes() {
  local pid
  for pid in "${pids[@]:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup_processes EXIT

for node in 1 2 3; do
  node_dir="$workspace/node-$node"
  mkdir -p "$node_dir"
  java -cp "$class_path" "$worker_class" "node-$node" "$node_dir" 1 \
    >"$node_dir/stdout.log" 2>"$node_dir/stderr.log" &
  pids+=("$!")
done

for node in 1 2 3; do
  ready="$workspace/node-$node/ready.properties"
  for _ in $(seq 1 200); do
    [[ -s "$ready" ]] && break
    sleep 0.05
  done
  [[ -s "$ready" ]] || { echo "node-$node did not reach the ready barrier" >&2; exit 1; }
  record_event ready "node-$node" "${pids[$((node - 1))]}" 1
done
for pid in "${pids[@]}"; do kill -0 "$pid"; done
record_event concurrent "${pids[@]}"

# Crash only the resolved configured-leader PID; never use a process-name pattern.
leader_pid=${pids[0]}
kill -9 "$leader_pid"
set +e
wait "$leader_pid" 2>/dev/null
leader_status=$?
set -e
[[ "$leader_status" -eq 137 ]] || { echo "leader was not killed by SIGKILL" >&2; exit 1; }
record_event crash node-1 "$leader_pid" 1 "$leader_status"
pids[0]=""

rm -f "$workspace/node-1/ready.properties"
java -cp "$class_path" "$worker_class" node-1 "$workspace/node-1" 2 \
  >>"$workspace/node-1/stdout.log" 2>>"$workspace/node-1/stderr.log" &
pids[0]=$!
for _ in $(seq 1 200); do
  grep -Fq 'generation=2' "$workspace/node-1/ready.properties" 2>/dev/null && break
  sleep 0.05
done
grep -Fq 'generation=2' "$workspace/node-1/ready.properties"
record_event ready node-1 "${pids[0]}" 2

# Exercise the storage-fault command path independently on node 3. The exact
# captured PID must terminate with the fixture's classified exit code, then a
# fresh generation must reach the ready barrier.
mkdir -p "$workspace/node-3/commands"
: > "$workspace/node-3/commands/storage-fault"
storage_pid=${pids[2]}
for _ in $(seq 1 200); do
  ! kill -0 "$storage_pid" 2>/dev/null && break
  sleep 0.05
done
if kill -0 "$storage_pid" 2>/dev/null; then
  echo "node-3 did not terminate after the storage-fault command" >&2
  exit 1
fi
set +e
wait "$storage_pid"
storage_status=$?
set -e
[[ "$storage_status" -eq 20 ]] || {
  echo "node-3 storage-fault exit was $storage_status; expected 20" >&2
  exit 1
}
pids[2]=""
grep -Fq 'exitCode=20' "$workspace/node-3/storage-fault.properties"
record_event storage-fault node-3 "$storage_pid" 1 "$storage_status"

rm -f "$workspace/node-3/commands/storage-fault" \
  "$workspace/node-3/ready.properties"
java -cp "$class_path" "$worker_class" node-3 "$workspace/node-3" 2 \
  >>"$workspace/node-3/stdout.log" 2>>"$workspace/node-3/stderr.log" &
pids[2]=$!
for _ in $(seq 1 200); do
  grep -Fq 'generation=2' "$workspace/node-3/ready.properties" 2>/dev/null && break
  sleep 0.05
done
grep -Fq 'generation=2' "$workspace/node-3/ready.properties"
record_event ready node-3 "${pids[2]}" 2
for pid in "${pids[@]}"; do kill -0 "$pid"; done
record_event concurrent "${pids[@]}"

# Stop the exact remaining workers before checksumming their final raw logs.
generations=(2 1 2)
for index in 0 1 2; do
  pid=${pids[$index]}
  kill -9 "$pid"
  set +e
  wait "$pid" 2>/dev/null
  cleanup_status=$?
  set -e
  [[ "$cleanup_status" -eq 137 ]] || exit 1
  record_event cleanup "node-$((index + 1))" "$pid" "${generations[$index]}" "$cleanup_status"
  pids[$index]=""
done

source_sha=$(git rev-parse HEAD)
"$python_command" -m scripts.v50.evidence write-harness \
  "$workspace/evidence" --source-sha "$source_sha" --workspace "$workspace"
"$python_command" -m scripts.v50.evidence validate "$workspace/evidence"

echo "v50LocalCrashHarness=PASS voters=3 crash=SIGKILL storageFault=20 restartGeneration=2"
