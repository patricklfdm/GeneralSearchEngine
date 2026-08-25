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

"${maven_command[@]}" --batch-mode --no-transfer-progress \
    -q -f "${project_dir}/reactor/pom.xml" \
    -pl :travel-search-example -am compile

java -cp "${project_dir}/target/classes:${project_dir}/examples/travel-search/target/classes" \
    example.travel.TravelSearchDemo
