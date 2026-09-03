#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || -z "$1" ]]; then
    echo "usage: $0 <published-version>" >&2
    exit 2
fi

version=$1
if [[ "$version" == *-SNAPSHOT ]]; then
    echo "published verification requires a non-SNAPSHOT version" >&2
    exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd -- "$script_dir/.." && pwd)
verification_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-published-$version.XXXXXX")
download_dir="$verification_root/downloads"
maven_repo="$verification_root/m2"
gpg_home="$verification_root/gpg"
trap 'rm -rf -- "$verification_root"' EXIT
mkdir -p "$download_dir" "$maven_repo" "$gpg_home"
chmod 700 "$gpg_home"

fetch() {
    local url=$1
    local destination=$2
    local attempt
    for attempt in $(seq 1 20); do
        if curl --fail --silent --show-error --location \
                --output "$destination" "$url"; then
            return 0
        fi
        if [[ $attempt -lt 20 ]]; then
            sleep 15
        fi
    done
    echo "published artifact did not become available: $url" >&2
    return 1
}

gpg --batch --yes --dearmor --output "$gpg_home/pubring.gpg" \
    "$project_dir/.github/release-signing-key.asc"

group_path=io/github/patricklfdm
repository=https://repo1.maven.org/maven2
artifacts=(general-search-engine general-search-engine-processor)
for artifact in "${artifacts[@]}"; do
    base="$artifact-$version"
    base_url="$repository/$group_path/$artifact/$version"
    files=("$base.pom" "$base.jar" "$base-sources.jar" "$base-javadoc.jar")
    for filename in "${files[@]}"; do
        local_file="$download_dir/$filename"
        fetch "$base_url/$filename" "$local_file"
        fetch "$base_url/$filename.asc" "$local_file.asc"
        fetch "$base_url/$filename.sha1" "$local_file.sha1"

        expected_sha1=$(awk '{print $1}' "$local_file.sha1")
        actual_sha1=$(sha1sum "$local_file" | awk '{print $1}')
        if [[ "$actual_sha1" != "$expected_sha1" ]]; then
            echo "SHA-1 mismatch for $filename" >&2
            exit 1
        fi
        gpgv --keyring "$gpg_home/pubring.gpg" "$local_file.asc" "$local_file"
    done
done

service_entry=META-INF/services/javax.annotation.processing.Processor
processor_class=io.github.patricklfdm.generalsearch.processor.SearchFieldsProcessor
format_fixture=io/github/patricklfdm/generalsearch/durability/v4-format-1.0-fixtures.tsv
core_jar="$download_dir/general-search-engine-$version.jar"
processor_jar="$download_dir/general-search-engine-processor-$version.jar"

manifest_version() {
    unzip -p "$1" META-INF/MANIFEST.MF \
        | tr -d '\r' \
        | sed -n 's/^Implementation-Version: //p' \
        | tail -n 1
}

for jar_file in "$core_jar" "$processor_jar"; do
    if [[ "$(manifest_version "$jar_file")" != "$version" ]]; then
        echo "published manifest version mismatch: $jar_file" >&2
        exit 1
    fi
done
if jar tf "$core_jar" | grep -Fxq "$service_entry"; then
    echo "published core JAR contains processor service entry" >&2
    exit 1
fi
if ! jar tf "$processor_jar" | grep -Fxq "$service_entry"; then
    echo "published processor JAR is missing processor service entry" >&2
    exit 1
fi
service_implementation=$(
    unzip -p "$processor_jar" "$service_entry" \
        | tr -d '\r' \
        | sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' \
        | tr -d '[:space:]'
)
if [[ "$service_implementation" != "$processor_class" ]]; then
    echo "published processor service entry is '$service_implementation'" >&2
    exit 1
fi

"$project_dir/mvnw" --batch-mode --no-transfer-progress \
    -Dmaven.repo.local="$maven_repo" \
    -f "$project_dir/compatibility/v3-style-consumer/pom.xml" \
    -Dgse.version="$version" clean test

major=${version%%.*}
if [[ "$major" =~ ^[0-9]+$ ]] && (( major >= 4 )); then
    if ! jar tf "$core_jar" | grep -Fxq "$format_fixture"; then
        echo "published V4 core JAR is missing immutable format 1.0 fixtures" >&2
        exit 1
    fi
    "$project_dir/mvnw" --batch-mode --no-transfer-progress \
        -Dmaven.repo.local="$maven_repo" \
        -f "$project_dir/compatibility/v4-style-consumer/pom.xml" \
        -Dgse.version="$version" clean test
    consumer_summary="clean V3 and V4 consumers"
else
    consumer_summary="clean V3 consumer"
fi

echo "Published release verification: PASS (8 artifacts, signatures, SHA-1 files, and $consumer_summary)"
