#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd -- "$script_dir/.." && pwd)

if [[ -n "${MAVEN_CMD:-}" ]]; then
    maven_command=("$MAVEN_CMD")
elif [[ -x "$project_dir/mvnw" ]]; then
    maven_command=("$project_dir/mvnw")
else
    maven_command=(mvn)
fi

evaluate() {
    local pom=$1
    local expression=$2

    "${maven_command[@]}" --batch-mode --no-transfer-progress \
        -Dstyle.color=never -q -f "$project_dir/$pom" \
        help:evaluate -Dexpression="$expression" -DforceStdout \
        | tr -d '\r' | tail -n 1
}

expected_version=${1:-$(evaluate pom.xml project.version)}
if [[ -z "$expected_version" ]]; then
    echo "expected version must not be empty" >&2
    exit 1
fi

checks=(
    "pom.xml:project.version"
    "general-search-engine-processor/pom.xml:project.version"
    "reactor/pom.xml:project.version"
    "examples/travel-search/pom.xml:project.version"
    "compatibility/v1-style-consumer/pom.xml:gse.version"
    "compatibility/v2-style-consumer/pom.xml:gse.version"
)

for check in "${checks[@]}"; do
    pom=${check%%:*}
    expression=${check#*:}
    actual_version=$(evaluate "$pom" "$expression")
    if [[ "$actual_version" != "$expected_version" ]]; then
        echo "$pom resolves $expression to '$actual_version'; expected '$expected_version'" >&2
        exit 1
    fi
done

echo "Version alignment: PASS ($expected_version)"
