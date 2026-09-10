#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

expected_sha=8dba2f09b861e3ed5fe7edde8226632c2248fe49582e0f3cb2c3fcb1cd958191
published_jar=target/compat-baselines/published-general-search-engine-4.2.0.jar
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v43-published-v42.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT

if [[ ! -f "$published_jar" ]]; then
    mkdir -p target/compat-baselines
    ./mvnw --batch-mode --no-transfer-progress -Dstyle.color=never -q \
        -Dmaven.repo.local="$work_dir/m2" \
        org.apache.maven.plugins:maven-dependency-plugin:3.9.0:copy \
        -Dartifact=io.github.patricklfdm:general-search-engine:4.2.0:jar \
        -DoutputDirectory=target/compat-baselines \
        -Dmdep.stripVersion=false -Dmdep.overWriteReleases=true
    mv target/compat-baselines/general-search-engine-4.2.0.jar "$published_jar"
fi

actual_sha=$(sha256sum "$published_jar" | awk '{print $1}')
if [[ "$actual_sha" != "$expected_sha" ]]; then
    echo "published 4.2.0 JAR checksum differs" >&2
    exit 1
fi

javac -cp "$published_jar" -d "$work_dir/classes" \
    scripts/v43/PublishedV42ColdReopenProbe.java
java -cp "$published_jar:$work_dir/classes" PublishedV42ColdReopenProbe \
    "$work_dir/store" "${GSE_V43_BASELINE_DOCUMENTS:-20000}"
