#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

if [[ "${1:-}" != "--skip-build" ]]; then
  ./mvnw clean -Pjmh -DskipTests package
fi

[[ -f target/benchmarks.jar ]] || {
  echo 'missing target/benchmarks.jar; build the JMH profile first' >&2
  exit 1
}

test_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-v34-phase4.XXXXXX")
trap 'rm -rf "$test_root"' EXIT

GSE_PERF_RESULTS_ROOT="$test_root/results" \
GSE_PERF_SKIP_BUILD=true \
GSE_V34_SUITE_PROFILE=reduced-test \
GSE_PERF_JVM_OPTIONS='-Xms256m -Xmx1g -XX:+UseG1GC' \
GSE_V34_COLD_DOCUMENTS=100 \
GSE_V34_COLD_TOKENS=8 \
GSE_V34_COLD_BATCH_SIZE=50 \
GSE_V34_COLD_REPEATS=2 \
GSE_V34_EXTREME_DOCUMENTS=100 \
GSE_V34_EXTREME_TOKENS=16 \
GSE_V34_BURST_PRODUCERS=1,2 \
GSE_V34_BURST_BATCH_SIZES=1,5 \
GSE_V34_BURST_BATCHES_PER_PRODUCER=2 \
GSE_V34_BURST_DOCUMENTS=1000 \
GSE_V34_BURST_READERS=2 \
GSE_V34_BURST_QUEUE_CAPACITY=8 \
GSE_SOAK_SECONDS=6 \
GSE_V34_LONG_RUN_DOCUMENTS=1000 \
GSE_V34_LONG_RUN_READERS=6 \
GSE_V34_LONG_RUN_WARMUP_SECONDS=1 \
GSE_V34_LONG_RUN_WINDOW_SECONDS=2 \
GSE_V34_LONG_RUN_SAMPLE_MILLIS=250 \
GSE_V34_LONG_RUN_STEADY_MILLIS=20 \
GSE_V34_LONG_RUN_BURST_EVERY_SECONDS=2 \
GSE_V34_LONG_RUN_BURST_PRODUCERS=2 \
GSE_V34_LONG_RUN_BURST_BATCH_SIZE=5 \
GSE_V34_LONG_RUN_LIFECYCLE_EVERY_SECONDS=2 \
GSE_V34_LONG_RUN_QUEUE_CAPACITY=64 \
scripts/run-v3-production-performance.sh final-v34

run_dir=$(sed -n '1p' "$test_root/results/LATEST")
suite="$run_dir/v34-final"
test -d "$suite/long-run"
grep -q '^status=PASS$' "$run_dir/status.properties"
grep -q '^schema=v3.4-final-in-memory-suite-v1$' "$suite/suite-config.properties"
grep -q '^profile=reduced-test$' "$suite/suite-config.properties"
grep -q '^status=PASS$' "$suite/suite-summary.properties"
grep -q '^coldSummary=SUCCESS ' "$suite/cold.log"
test "$(grep -c '^extremeAxis=' "$suite/extreme.log")" -eq 9
grep -q '^extremeSummary=SUCCESS axes=9 ' "$suite/extreme.log"
test "$(grep -c '^burstCell=SUCCESS ' "$suite/burst.log")" -eq 4
grep -q '^burstMatrix=SUCCESS cells=4 ' "$suite/burst.log"
grep -q '^status=SUCCESS$' "$suite/long-run/summary.properties"
(
  cd "$suite/long-run"
  sha256sum -c manifest.sha256
)
(
  cd "$run_dir"
  sha256sum -c checksums.sha256
)
