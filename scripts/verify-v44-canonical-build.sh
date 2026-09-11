#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--validate-only" ) ]]; then
    echo "usage: $0 [--validate-only]" >&2
    exit 2
fi

if command -v python3.11 >/dev/null 2>&1; then
    python_command=python3.11
else
    python_command=python3
fi

manifest=docs/v4x/v4.4/release-toolchain.json
"$python_command" -m scripts.v44.toolchain_manifest "$manifest"
"$python_command" -m unittest scripts.v44.test_phase5_reproducibility

if [[ "${1:-}" == "--validate-only" ]]; then
    echo "V4.4 canonical build contract: PASS (execution skipped)"
    exit 0
fi

command -v docker >/dev/null || {
    echo "Docker is required for canonical byte identity" >&2
    exit 2
}

image=$("$python_command" -c \
    'import json; print(json.load(open("docs/v4x/v4.4/release-toolchain.json"))["container"]["image"])')
index_digest=$("$python_command" -c \
    'import json; print(json.load(open("docs/v4x/v4.4/release-toolchain.json"))["container"]["indexDigest"])')
image_reference="${image%@*}@${index_digest}"
maven_version=$("$python_command" -c \
    'import json; print(json.load(open("docs/v4x/v4.4/release-toolchain.json"))["mavenWrapper"]["version"])')
maven_url=$("$python_command" -c \
    'import json; print(json.load(open("docs/v4x/v4.4/release-toolchain.json"))["mavenWrapper"]["distributionUrl"])')
maven_sha256=$("$python_command" -c \
    'import json; print(json.load(open("docs/v4x/v4.4/release-toolchain.json"))["mavenWrapper"]["distributionSha256Sum"])')
maven_archive_name=${maven_url##*/}

if ! docker image inspect "$image_reference" >/dev/null 2>&1; then
    docker pull "$image_reference"
fi
observed_architecture=$(docker image inspect "$image_reference" --format '{{.Architecture}}')
observed_digests=$(docker image inspect "$image_reference" --format '{{join .RepoDigests "\n"}}')
[[ "$observed_architecture" == amd64 ]] || {
    echo "canonical image architecture differs: $observed_architecture" >&2
    exit 2
}
grep -Fqx "eclipse-temurin@${index_digest}" <<<"$observed_digests" || {
    echo "canonical image index digest differs" >&2
    exit 2
}

work_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-v44-canonical.XXXXXXXX")
trap 'rm -rf -- "$work_root"' EXIT
mkdir -p "$work_root/one" "$work_root/two" "$work_root/m2"

# The frozen Temurin image deliberately contains only the JDK and does not ship
# unzip. Maven Wrapper otherwise changes the requested .zip URL to .tar.gz and
# then compares that archive with the frozen ZIP checksum. Stage the exact ZIP
# once, verify it on the host and again in each container, and extract it with
# the JDK's jar tool so canonical execution has no mutable package-install step.
maven_archive="$work_root/$maven_archive_name"
if command -v curl >/dev/null 2>&1; then
    curl --fail --silent --show-error --location \
        --output "$maven_archive" "$maven_url"
elif command -v wget >/dev/null 2>&1; then
    wget --quiet --output-document="$maven_archive" "$maven_url"
else
    echo "curl or wget is required to acquire the frozen Maven distribution" >&2
    exit 2
fi
echo "$maven_sha256  $maven_archive" | sha256sum --check --status || {
    echo "frozen Maven distribution SHA-256 differs" >&2
    exit 2
}
git archive HEAD | tar -x -C "$work_root/one"
git archive HEAD | tar -x -C "$work_root/two"

build_capture() {
    local workspace=$1
    local capture=$2
    mkdir -p "$capture"
    docker run --rm --platform linux/amd64 \
        --user "$(id -u):$(id -g)" \
        --env LANG=C.UTF-8 --env LC_ALL=C.UTF-8 --env TZ=UTC \
        --env HOME=/tmp/gse-home \
        --env GSE_MAVEN_ARCHIVE="/toolchain/$maven_archive_name" \
        --env GSE_MAVEN_SHA256="$maven_sha256" \
        --env GSE_MAVEN_HOME="/tmp/gse-maven/apache-maven-$maven_version" \
        --volume "$workspace:/workspace" \
        --volume "$work_root/m2:/tmp/gse-home/.m2" \
        --volume "$maven_archive:/toolchain/$maven_archive_name:ro" \
        --workdir /workspace \
        "$image_reference" \
        bash -ceu 'umask 0022; settings=$(java -XshowSettings:properties -version 2>&1); test "$(sed -n "s/^ *java.version = //p" <<<"$settings")" = "21.0.12"; test "$(sed -n "s/^ *java.runtime.version = //p" <<<"$settings")" = "21.0.12+8-LTS"; echo "$GSE_MAVEN_SHA256  $GSE_MAVEN_ARCHIVE" | sha256sum --check --status; mkdir -p /tmp/gse-maven; cd /tmp/gse-maven; jar xf "$GSE_MAVEN_ARCHIVE"; cd /workspace; bash "$GSE_MAVEN_HOME/bin/mvn" -q -f reactor/pom.xml -Prelease -DskipTests clean package'
    find "$workspace/target" "$workspace/general-search-engine-processor/target" \
        -maxdepth 1 -type f \
        \( -name 'general-search-engine-*.jar' \
        -o -name 'general-search-engine-processor-*.jar' \) \
        -exec cp {} "$capture/" \;
    cp "$workspace/pom.xml" "$capture/general-search-engine.pom"
    cp "$workspace/general-search-engine-processor/pom.xml" \
        "$capture/general-search-engine-processor.pom"
}

build_capture "$work_root/one" "$work_root/capture-one"
build_capture "$work_root/two" "$work_root/capture-two"

output=target/v44-canonical-reproducibility
[[ ! -e "$output" ]] || {
    echo "canonical evidence output already exists: $output" >&2
    exit 2
}
"$python_command" -m scripts.v44.canonical_reproducibility record \
    --first "$work_root/capture-one" \
    --second "$work_root/capture-two" \
    --output "$output" \
    --source-sha "$(git rev-parse HEAD)"
"$python_command" -m scripts.v44.canonical_reproducibility validate "$output"
echo "V4.4 canonical two-workspace release build: PASS"
