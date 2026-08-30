#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$repo_root"

trim_space() {
  local value=$1
  value=${value#"${value%%[![:space:]]*}"}
  value=${value%"${value##*[![:space:]]}"}
  printf '%s' "$value"
}

unique_colon_fact() {
  local wanted=$1
  local content=$2
  local key value
  local count=0
  local result=
  while IFS=: read -r key value; do
    if [ "$key" = "$wanted" ]; then
      count=$((count + 1))
      result=$(trim_space "$value")
    fi
  done <<< "$content"
  if [ "$count" -ne 1 ] || [ -z "$result" ] \
      || [[ "$result" == *$'\n'* ]] || [[ "$result" == *$'\r'* ]]; then
    echo "Expected exactly one non-empty $wanted fact" >&2
    return 1
  fi
  printf '%s' "$result"
}

unique_java_property() {
  local wanted=$1
  local content=$2
  local line key value
  local count=0
  local result=
  while IFS= read -r line; do
    case "$line" in
      *=*)
        key=$(trim_space "${line%%=*}")
        value=$(trim_space "${line#*=}")
        if [ "$key" = "$wanted" ]; then
          count=$((count + 1))
          result=$value
        fi
        ;;
    esac
  done <<< "$content"
  if [ "$count" -ne 1 ] || [ -z "$result" ] \
      || [[ "$result" == *$'\n'* ]] || [[ "$result" == *$'\r'* ]]; then
    echo "Expected exactly one non-empty $wanted Java property" >&2
    return 1
  fi
  printf '%s' "$result"
}

require_positive_integer() {
  local name=$1
  local value=$2
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || {
    echo "$name must be a positive integer" >&2
    return 1
  }
}

lscpu_facts=$(LC_ALL=C lscpu)
cpu_vendor=$(unique_colon_fact 'Vendor ID' "$lscpu_facts")
cpu_model=$(unique_colon_fact 'Model name' "$lscpu_facts")
cpu_sockets=$(unique_colon_fact 'Socket(s)' "$lscpu_facts")
cpu_cores_per_socket=$(unique_colon_fact 'Core(s) per socket' "$lscpu_facts")
cpu_threads_per_core=$(unique_colon_fact 'Thread(s) per core' "$lscpu_facts")
require_positive_integer cpu_sockets "$cpu_sockets"
require_positive_integer cpu_cores_per_socket "$cpu_cores_per_socket"
require_positive_integer cpu_threads_per_core "$cpu_threads_per_core"

memory_kib=
memory_fact_count=0
while read -r key value unit extra; do
  if [ "$key" = 'MemTotal:' ]; then
    memory_fact_count=$((memory_fact_count + 1))
    memory_kib=$value
    [ "$unit" = kB ] && [ -z "${extra:-}" ] || {
      echo 'MemTotal must use the exact /proc/meminfo kB shape' >&2
      exit 2
    }
  fi
done < /proc/meminfo
[ "$memory_fact_count" -eq 1 ] || {
  echo 'Expected exactly one MemTotal fact in /proc/meminfo' >&2
  exit 2
}
require_positive_integer memory_kib "$memory_kib"
if [ "${#memory_kib}" -gt 13 ] \
    || { [ "${#memory_kib}" -eq 13 ] && [[ "$memory_kib" > 8796093022207 ]]; }; then
  echo 'MemTotal is too large for checked byte conversion' >&2
  exit 2
fi
memory_bytes=$((10#$memory_kib * 1024))

java_properties=$(LC_ALL=C java -XshowSettings:properties -version 2>&1)
java_vendor=$(unique_java_property java.vendor "$java_properties")
java_runtime_version=$(unique_java_property java.runtime.version "$java_properties")
java_vm_name=$(unique_java_property java.vm.name "$java_properties")
java_vm_version=$(unique_java_property java.vm.version "$java_properties")

source_repository=${GSE_CLOUD_SOURCE_REPOSITORY:-}
if [ -z "$source_repository" ]; then
  source_repository=$(git config --get remote.origin.url || true)
fi
if [ -z "$source_repository" ] || [[ "$source_repository" == *$'\n'* ]] \
    || [[ "$source_repository" == *$'\r'* ]]; then
  echo 'source_repository must be a non-empty single-line repository URL' >&2
  exit 2
fi

benchmark_suite=${GSE_BENCHMARK_SUITE:-v3-production}
case "$benchmark_suite" in
  v3-production|v3.1-ranked-suite-v1) ;;
  *)
    echo 'GSE_BENCHMARK_SUITE must be v3-production or v3.1-ranked-suite-v1' >&2
    exit 2
    ;;
esac

printf '%s\n' \
  'evidence_schema_version=1' \
  "benchmark_suite=$benchmark_suite" \
  'benchmark_suite_schema_version=1' \
  "source_repository=$source_repository" \
  "kernel_release=$(uname -r)" \
  "memory_bytes=$memory_bytes" \
  "cpu_vendor=$cpu_vendor" \
  "cpu_model=$cpu_model" \
  "cpu_sockets=$cpu_sockets" \
  "cpu_cores_per_socket=$cpu_cores_per_socket" \
  "cpu_threads_per_core=$cpu_threads_per_core" \
  "java_vendor=$java_vendor" \
  "java_runtime_version=$java_runtime_version" \
  "java_vm_name=$java_vm_name" \
  "java_vm_version=$java_vm_version"
