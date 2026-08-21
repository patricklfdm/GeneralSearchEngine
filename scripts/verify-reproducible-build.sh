#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd -- "$script_dir/.." && pwd)
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/general-search-engine-repro.XXXXXX")
trap 'rm -rf -- "$work_dir"' EXIT

if [[ -n "${MAVEN_CMD:-}" ]]; then
    maven_command=("$MAVEN_CMD")
elif [[ -x "$project_dir/mvnw" ]]; then
    maven_command=("$project_dir/mvnw")
else
    maven_command=(mvn)
fi

build_and_capture() {
    local destination=$1
    "${maven_command[@]}" -q -Prelease -DskipTests clean package
    mkdir -p "$destination"

    mapfile -t artifacts < <(
        find target -maxdepth 1 -type f \
            -name 'general-search-engine-*.jar' \
            -printf '%f\n' | sort
    )
    if [[ ${#artifacts[@]} -ne 3 ]]; then
        echo "expected main, sources, and javadoc JARs; found ${#artifacts[@]}" >&2
        printf '  %s\n' "${artifacts[@]}" >&2
        return 1
    fi
    for artifact in "${artifacts[@]}"; do
        cp "target/$artifact" "$destination/$artifact"
    done
}

cd "$project_dir"
build_and_capture "$work_dir/first"
build_and_capture "$work_dir/second"

while IFS= read -r artifact; do
    cmp "$work_dir/first/$artifact" "$work_dir/second/$artifact"
done < <(find "$work_dir/first" -maxdepth 1 -type f -printf '%f\n' | sort)

echo "Reproducible release artifacts:"
sha256sum target/general-search-engine-*.jar
