#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd -- "$script_dir/.." && pwd)
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/gse-v41-phase5.XXXXXX")
trap 'rm -rf -- "$work_dir"' EXIT

cd "$project_dir"
python3 -m unittest scripts.v41.test_cleanup_crash_inspector
./mvnw -q \
    -Dtest=V41PublicApiFoundationTest,V41CleanupPublicApiTest,V41SafeCleanupPhase5Test \
    test

classpath="target/test-classes:target/classes"
barriers=(
    v41-cleanup-before-delete-v1
    v41-cleanup-after-delete-v1
    v41-cleanup-before-directory-force-v1
    v41-cleanup-after-directory-force-v1
    v41-cleanup-before-post-verify-v1
    v41-cleanup-after-post-verify-v1
)

for scope in live operation; do
    for barrier in "${barriers[@]}"; do
        workspace="$work_dir/$scope/$barrier"
        mkdir -p "$workspace"
        set +e
        java -cp "$classpath" \
            io.github.patricklfdm.generalsearch.durability.harness.V41CleanupHarnessProcess \
            crash "$workspace" "$barrier" "$scope" \
            >"$workspace/crash.log" 2>&1
        exit_code=$?
        set -e
        if [[ $exit_code -ne 86 ]]; then
            cat "$workspace/crash.log" >&2
            echo "cleanup crash case did not halt at $scope/$barrier" >&2
            exit 1
        fi
        grep -Fq "\"barrierId\":\"$barrier\"" "$workspace/crash.log"
        python3 -m scripts.v41.cleanup_crash_inspector "$workspace" "$scope"
        java -cp "$classpath" \
            io.github.patricklfdm.generalsearch.durability.harness.V41CleanupHarnessProcess \
            recover "$workspace" ignored "$scope"
    done
done

echo "V4.1 Phase 5 plan-bound safe cleanup matrix: PASS (12 crash cases)"
