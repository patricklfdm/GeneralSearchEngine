#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd -- "$script_dir/.." && pwd)
require_signatures=false

if [[ "${1:-}" == "--require-signatures" ]]; then
    require_signatures=true
    shift
fi
if [[ $# -gt 1 ]]; then
    echo "usage: $0 [--require-signatures] [version]" >&2
    exit 2
fi

if [[ -n "${MAVEN_CMD:-}" ]]; then
    maven_command=("$MAVEN_CMD")
elif [[ -x "$project_dir/mvnw" ]]; then
    maven_command=("$project_dir/mvnw")
else
    maven_command=(mvn)
fi

evaluate_version() {
    "${maven_command[@]}" --batch-mode --no-transfer-progress \
        -Dstyle.color=never -q -f "$project_dir/pom.xml" \
        help:evaluate -Dexpression=project.version -DforceStdout \
        | tr -d '\r' | tail -n 1
}

version=${1:-$(evaluate_version)}
"$script_dir/verify-version-alignment.sh" "$version"

core_base="general-search-engine-$version"
processor_base="general-search-engine-processor-$version"
core_target="$project_dir/target"
processor_target="$project_dir/general-search-engine-processor/target"
core_jar="$core_target/$core_base.jar"
processor_jar="$processor_target/$processor_base.jar"
service_entry=META-INF/services/javax.annotation.processing.Processor
processor_class=io.github.patricklfdm.generalsearch.processor.SearchFieldsProcessor

artifacts=(
    "$core_jar"
    "$core_target/$core_base-sources.jar"
    "$core_target/$core_base-javadoc.jar"
    "$processor_jar"
    "$processor_target/$processor_base-sources.jar"
    "$processor_target/$processor_base-javadoc.jar"
)

for artifact in "${artifacts[@]}"; do
    if [[ ! -s "$artifact" ]]; then
        echo "missing or empty release artifact: $artifact" >&2
        exit 1
    fi
done

manifest_version() {
    unzip -p "$1" META-INF/MANIFEST.MF \
        | tr -d '\r' \
        | sed -n 's/^Implementation-Version: //p' \
        | tail -n 1
}

for artifact in "$core_jar" "$processor_jar"; do
    actual_version=$(manifest_version "$artifact")
    if [[ "$actual_version" != "$version" ]]; then
        echo "$artifact has Implementation-Version '$actual_version'; expected '$version'" >&2
        exit 1
    fi
done

if jar tf "$core_jar" | grep -Fxq "$service_entry"; then
    echo "core JAR must not contain $service_entry" >&2
    exit 1
fi
if ! jar tf "$processor_jar" | grep -Fxq "$service_entry"; then
    echo "processor JAR is missing $service_entry" >&2
    exit 1
fi

service_implementation=$(
    unzip -p "$processor_jar" "$service_entry" \
        | tr -d '\r' \
        | sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' \
        | tr -d '[:space:]'
)
if [[ "$service_implementation" != "$processor_class" ]]; then
    echo "processor service entry resolves to '$service_implementation'; expected '$processor_class'" >&2
    exit 1
fi

if [[ "$require_signatures" == true ]]; then
    signatures=(
        "$core_target/$core_base.jar.asc:$core_jar"
        "$core_target/$core_base-sources.jar.asc:$core_target/$core_base-sources.jar"
        "$core_target/$core_base-javadoc.jar.asc:$core_target/$core_base-javadoc.jar"
        "$core_target/$core_base.pom.asc:$project_dir/pom.xml"
        "$processor_target/$processor_base.jar.asc:$processor_jar"
        "$processor_target/$processor_base-sources.jar.asc:$processor_target/$processor_base-sources.jar"
        "$processor_target/$processor_base-javadoc.jar.asc:$processor_target/$processor_base-javadoc.jar"
        "$processor_target/$processor_base.pom.asc:$project_dir/general-search-engine-processor/pom.xml"
    )
    gpg_home=$(mktemp -d "${TMPDIR:-/tmp}/gse-artifact-signatures.XXXXXX")
    trap 'rm -rf -- "$gpg_home"' EXIT
    chmod 700 "$gpg_home"
    gpg --batch --yes --dearmor --output "$gpg_home/pubring.gpg" \
        "$project_dir/.github/release-signing-key.asc"

    for pair in "${signatures[@]}"; do
        signature=${pair%%:*}
        signed_file=${pair#*:}
        if [[ ! -s "$signature" ]]; then
            echo "missing or empty release signature: $signature" >&2
            exit 1
        fi
        gpgv --keyring "$gpg_home/pubring.gpg" "$signature" "$signed_file"
    done
fi

signature_summary=""
if [[ "$require_signatures" == true ]]; then
    signature_summary=" and 8 signatures"
fi
echo "Release artifact integrity: PASS (6 JARs$signature_summary, version $version)"
