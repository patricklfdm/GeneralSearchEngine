#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

./mvnw clean -Pjmh -DskipTests package
java -jar target/benchmarks.jar \
  'PositionalTextIndexBenchmark.publishPositionSensitiveMutationBatch' \
  -p analysisMode=default-adapter \
  -p documentCount=10000 \
  -p mutationBatchSize=1 \
  -p tokenCount=16 \
  -f 1 -wi 0 -i 1 -r 100ms -foe true
