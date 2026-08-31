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

java -cp "$benchmark_jar" \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V34ColdBuildProcessRunner \
  --documents=1000 \
  --tokens=8 \
  --batch-size=250 \
  --repeats=2 \
  --timeout-seconds=60

java -cp "$benchmark_jar" \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V34ExtremeCorpusProbe \
  --documents=100 \
  --tokens=16 \
  --axis=all

java -cp "$benchmark_jar" \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V34HeapMatrixRunner \
  --heaps=256m,512m \
  --documents=1000 \
  --tokens=8 \
  --operations=25 \
  --require-no-swap=false \
  --timeout-seconds=60
