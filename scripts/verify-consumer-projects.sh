#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"

mvn -q -f "${project_dir}/reactor/pom.xml" -DskipTests install
mvn -q -f "${project_dir}/compatibility/pom.xml" clean test

echo "Independent v1-style and v2-style consumer compilation: PASS"
