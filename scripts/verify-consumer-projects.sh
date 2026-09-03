#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"

if [[ -n "${MAVEN_CMD:-}" ]]; then
    maven_command=("$MAVEN_CMD")
elif [[ -x "$project_dir/mvnw" ]]; then
    maven_command=("$project_dir/mvnw")
else
    maven_command=(mvn)
fi

consumer_repository=${GSE_CONSUMER_MAVEN_REPO:-${project_dir}/target/consumer-maven-repository}
mkdir -p "$consumer_repository"

"${maven_command[@]}" --batch-mode --no-transfer-progress \
    -Dmaven.repo.local="$consumer_repository" \
    -q -f "${project_dir}/reactor/pom.xml" -DskipTests install
"${maven_command[@]}" --batch-mode --no-transfer-progress \
    -Dmaven.repo.local="$consumer_repository" \
    -q -f "${project_dir}/compatibility/pom.xml" clean test

echo "Independent v1-style, v2-style, v3-style, and v4-style consumer compilation: PASS"
