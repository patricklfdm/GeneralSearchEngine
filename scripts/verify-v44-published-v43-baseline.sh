#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

skip_resolve=false
if [[ "${1:-}" == "--skip-resolve" ]]; then
    skip_resolve=true
elif [[ $# -ne 0 ]]; then
    echo "usage: $0 [--skip-resolve]" >&2
    exit 2
fi

published_jar=target/compat-baselines/published-general-search-engine-4.3.0.jar
if [[ "$skip_resolve" == false ]]; then
    isolated_repo=$(mktemp -d "${TMPDIR:-/tmp}/gse-v44-published-m2.XXXXXX")
    trap 'rm -rf "$isolated_repo"' EXIT
    ./mvnw -q -Dmaven.repo.local="$isolated_repo" \
        org.apache.maven.plugins:maven-dependency-plugin:3.9.0:copy \
        -Dartifact=io.github.patricklfdm:general-search-engine:4.3.0 \
        -DoutputDirectory=target/compat-baselines \
        -Dmdep.stripVersion=false
    resolved=target/compat-baselines/general-search-engine-4.3.0.jar
    mkdir -p target/compat-baselines
    cp "$resolved" "$published_jar"
fi

test -f "$published_jar"
expected=c5ecf5cf311c734481e95f14bdcfffb466fa132dde424a2b6b4a58fe41778583
actual=$(sha256sum "$published_jar" | awk '{print $1}')
test "$actual" = "$expected"

python_command=python3
if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
fi
"$python_command" -m scripts.v44.api_inventory compare \
    "$published_jar" \
    src/test/resources/compatibility/v44-public-api-inventory-v1.json

if [[ -f target/general-search-engine-4.4.0-SNAPSHOT.jar ]]; then
    "$python_command" -m scripts.v44.api_inventory compare \
        target/general-search-engine-4.4.0-SNAPSHOT.jar \
        src/test/resources/compatibility/v44-public-api-inventory-v1.json
fi

echo "V4.4 published 4.3 baseline: PASS (sha256=$actual)"
