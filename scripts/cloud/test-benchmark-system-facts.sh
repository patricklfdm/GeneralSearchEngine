#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$repo_root"

fixture_repository=https://example.test/patricklfdm/GeneralSearchEngine.git
facts=$(GSE_CLOUD_SOURCE_REPOSITORY=$fixture_repository \
  scripts/cloud/collect-benchmark-system-facts.sh)

property() {
  local wanted=$1
  local count=0
  local result=
  local key value
  while IFS='=' read -r key value; do
    if [ "$key" = "$wanted" ]; then
      count=$((count + 1))
      result=$value
    fi
  done <<< "$facts"
  [ "$count" -eq 1 ] && [ -n "$result" ] || {
    echo "FAIL: expected one non-empty $wanted property" >&2
    exit 1
  }
  printf '%s' "$result"
}

[ "$(property evidence_schema_version)" = 1 ]
[ "$(property benchmark_suite)" = v3-production ]
[ "$(property benchmark_suite_schema_version)" = 1 ]
[ "$(property source_repository)" = "$fixture_repository" ]
[ "$(property kernel_release)" = "$(uname -r)" ]

memory_kib=$(sed -n 's/^MemTotal:[[:space:]]*\([0-9][0-9]*\)[[:space:]]*kB$/\1/p' \
  /proc/meminfo)
[[ "$memory_kib" =~ ^[1-9][0-9]*$ ]]
[ "$(property memory_bytes)" -eq $((10#$memory_kib * 1024)) ]

for key in memory_bytes cpu_sockets cpu_cores_per_socket cpu_threads_per_core; do
  value=$(property "$key")
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || {
    echo "FAIL: $key is not a positive integer" >&2
    exit 1
  }
done

for key in cpu_vendor cpu_model java_vendor java_runtime_version java_vm_name java_vm_version; do
  property "$key" >/dev/null
done

line_count=$(printf '%s\n' "$facts" | sed -n '$=')
[ "$line_count" -eq 15 ] || {
  echo "FAIL: expected 15 schema-1 fact lines, got $line_count" >&2
  exit 1
}

echo 'Benchmark schema-1 system fact tests: PASS'
