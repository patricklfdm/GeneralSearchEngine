#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
if [[ $# -eq 0 ]]; then
  ./mvnw -f reactor/pom.xml clean package
elif [[ $# -ne 1 || "$1" != --skip-build ]]; then
  echo "usage: $0 [--skip-build]" >&2
  exit 2
fi
python_command=python3
command -v python3.11 >/dev/null 2>&1 && python_command=python3.11
control_jar=${GSE_V50_CONTROL_JAR:-$root/target/v50-control/general-search-engine-4.4.0.jar}
if [[ ! -f "$control_jar" && -z "${GSE_V50_CONTROL_JAR:-}" ]]; then
  ./mvnw -q org.apache.maven.plugins:maven-dependency-plugin:3.9.0:copy \
    -Dartifact=io.github.patricklfdm:general-search-engine:4.4.0 -DoutputDirectory="$root/target/v50-control"
fi
"$python_command" -m unittest scripts.v50.test_cloud_remote
mkdir -p target/v50-remote-workload
work_parent=$(mktemp -d "$root/target/v50-remote-workload/run.XXXXXX")
echo "v50RemoteWorkloadEvidence=$work_parent/qualification"
"$python_command" -m scripts.v50.cloud_bundle "$work_parent/artifacts" --control-jar "$control_jar" --remote-workload
timeout --signal=TERM --kill-after=30s 490s "$python_command" -m scripts.v50.cloud_remote_local \
  "$work_parent/qualification" --bundle "$work_parent/artifacts"
"$python_command" -m scripts.v50.test_cloud_remote --evidence "$work_parent/qualification/runner" \
  --output "$work_parent/semantic-negatives.json"
echo 'v50RemoteAdapter=PASS execution=local-remote-workload-only'
