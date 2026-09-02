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
  'V32AnalyzerBaselineBenchmark.analyzeWithOffsets' \
  -p shape=combining \
  -p tokenCount=16 \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V32TextHighlightBenchmark.highlightedTextSearch' \
  -p documentCount=1000 \
  -p topK=10 \
  -p sourceTokenCount=16 \
  -p contextCharacters=40 \
  -p maxFragmentsPerField=3 \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V32QueryEvidenceHighlightBenchmark.highlightedSearch' \
  -p documentCount=1000 \
  -p topK=10 \
  -p sourceTokenCount=16 \
  -p queryKind=bool-boost \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V32HighlightScaleBenchmark.highlightedSearch' \
  -p documentCount=1000 \
  -p topK=10 \
  -p requestedFieldCount=3 \
  -p sourceTokenCount=16 \
  -p queryKind=bool-boost \
  -p outcome=highlighted \
  -p contextCharacters=40 \
  -p maxFragmentsPerField=3 \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V32HighlightConcurrencyBenchmark.mixed' \
  -p documentCount=1000 \
  -p topK=10 \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V33PaginationBaselineBenchmark.ordinaryRankedSearch' \
  -p documentCount=1000 \
  -p topK=10 \
  -p corpusShape=dense-ties \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V33PaginationBaselineBenchmark.firstPageExact' \
  -p documentCount=1000 \
  -p topK=10 \
  -p corpusShape=dense-ties \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V33SearchAfterBenchmark.continuationExact' \
  -p documentCount=1000 \
  -p pageSize=10 \
  -p pageDepth=10 \
  -p corpusShape=dense-ties \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V33PaginationHardeningBenchmark.continuationExact' \
  -p documentCount=1000 \
  -p pageSize=10 \
  -p pageDepth=10 \
  -p queryKind=dense-bool \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V33PaginationConcurrencyBenchmark.mixed' \
  -p documentCount=1000 \
  -p pageSize=10 \
  -tg 1,1,1,1,1,1 -bm thrpt -tu s \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V34FinalHardeningBaselineBenchmark.ordinaryRankedSearch' \
  -p documentCount=1000 \
  -p topK=10 \
  -p corpusShape=dense-ties \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -jar target/benchmarks.jar \
  'V34FinalHardeningBaselineBenchmark.highlightedSearch' \
  -p documentCount=1000 \
  -p topK=10 \
  -p corpusShape=sparse \
  -f 1 -wi 0 -i 1 -r 100ms -foe true

java -cp target/benchmarks.jar \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V33CursorRetentionProbe \
  1000

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

scripts/verify-v34-local-diagnostics.sh --skip-build
scripts/verify-v34-phase3-diagnostics.sh --skip-build
scripts/verify-v34-phase4-final-suite.sh --skip-build
scripts/verify-v40-phase4-checkpoints.sh --skip-build
scripts/verify-v40-phase5-hardening.sh --skip-build
