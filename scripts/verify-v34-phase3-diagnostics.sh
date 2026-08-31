#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

if [[ "${1:-}" != "--skip-build" ]]; then
  ./mvnw clean -Pjmh -DskipTests package
fi

benchmark_jar=target/benchmarks.jar
if [[ ! -f "$benchmark_jar" ]]; then
  echo "missing $benchmark_jar; build the JMH profile first" >&2
  exit 1
fi

test_root=$(mktemp -d "${TMPDIR:-/tmp}/gse-v34-phase3.XXXXXX")
trap 'rm -rf "$test_root"' EXIT

source_commit=$(git rev-parse HEAD)
if [[ -n "$(git status --short)" ]]; then
  tree_state=dirty
else
  tree_state=clean
fi

java -cp "$benchmark_jar" \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V34BurstRecoveryProbe \
  --producers=1,4 \
  --batch-sizes=1,10 \
  --batches-per-producer=2 \
  --documents=1000 \
  --readers=2 \
  --queue-capacity=8 \
  --timeout-seconds=60

java -cp "$benchmark_jar" \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V34LongRunCalibration \
  --output="$test_root/long-run" \
  --documents=1000 \
  --readers=6 \
  --seconds=6 \
  --warmup-seconds=1 \
  --window-seconds=2 \
  --sample-millis=250 \
  --top-k=10 \
  --steady-millis=20 \
  --burst-every-seconds=2 \
  --burst-producers=4 \
  --burst-batch-size=10 \
  --lifecycle-every-seconds=2 \
  --queue-capacity=64 \
  --source-commit="$source_commit" \
  --tree-state="$tree_state"

for evidence in \
  config.properties \
  samples.csv \
  windows.csv \
  summary.properties \
  manifest.sha256; do
  test -s "$test_root/long-run/$evidence"
done

grep -q '^status=SUCCESS$' "$test_root/long-run/summary.properties"
test "$(wc -l < "$test_root/long-run/manifest.sha256")" -eq 4
