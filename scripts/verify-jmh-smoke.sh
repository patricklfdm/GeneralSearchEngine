#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

./mvnw clean -Pjmh -DskipTests package
java -jar target/benchmarks.jar \
  'V32AnalyzerBaselineBenchmark.analyzeTerms' \
  -p shape=nfkc \
  -p tokenCount=16 \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'PositionalTextIndexBenchmark.publishPositionSensitiveMutationBatch' \
  -p analysisMode=default-adapter \
  -p documentCount=10000 \
  -p mutationBatchSize=1 \
  -p tokenCount=16 \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V31PhraseFeatureBenchmark.search' \
  -p documentCount=1000 \
  -p scenario=low-s0 \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V31MinimumShouldMatchBenchmark.search' \
  -p documentCount=1000 \
  -p shouldWidth=4 \
  -p minimum=all \
  -p withMust=true \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V31FuzzyDictionaryBenchmark.traverse' \
  -p vocabularySize=1000 \
  -p scenario=unicode-near \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V31TextDictionaryBenchmark.publish' \
  -p vocabularySize=1000 \
  -p mutationBatchSize=1 \
  -p transition=added \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V31ConcurrentMixedWorkloadBenchmark.mixed' \
  -p documentCount=1000 \
  -tg 2,1 -bm thrpt -tu s \
  -f 1 -wi 0 -i 1 -r 100ms -foe true
