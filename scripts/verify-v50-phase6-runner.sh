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
mkdir -p target/v50-cloud-local
work=$(mktemp -d "$root/target/v50-cloud-local/run.XXXXXX")
"$python_command" -m scripts.v50.cloud_entry fake --output "$work/fake"
"$python_command" -m scripts.v50.cloud_bundle "$work/artifacts" --control-jar "$control_jar"
timeout --signal=TERM --kill-after=10s 250s "$python_command" -m scripts.v50.performance_harness \
  "$work/volumes" --control-jar "$control_jar" --volume-layout --java "$work/artifacts/bundle/jre/bin/java"
echo "v50Phase6B=PASS execution=local-volume-layout-and-fake-runner-only evidence=$work"
