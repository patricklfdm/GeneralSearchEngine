#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"

mvn -q -f "${project_dir}/reactor/pom.xml" \
    -pl :travel-search-example -am compile

java -cp "${project_dir}/target/classes:${project_dir}/examples/travel-search/target/classes" \
    example.travel.TravelSearchDemo
