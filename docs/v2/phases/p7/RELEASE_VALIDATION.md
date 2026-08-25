# GeneralSearchEngine v2 P7 release validation

## Status

P7 is `COMPLETED`. Correctness, compatibility, consumer, release, signature, artifact,
reproducibility, the 141-row representative JMH regression matrix, and the target-machine
long-soak gate all pass. Release conversion and publication remain separate actions.

All performance data is environment- and workload-specific regression evidence, not a
universal latency, throughput, allocation, scaling, or capacity guarantee.

## Accepted automated gates

- `mvn clean test`: PASS, 118 tests;
- `mvn clean -Papi-compat test`: PASS, 3 frozen v1 fixture tests;
- `mvn clean -Partifact-compat verify`: PASS against published v1.0.0;
- `mvn -f reactor/pom.xml clean test`: PASS, 118 core plus 4 processor tests;
- `bash scripts/verify-consumer-projects.sh`: PASS for both independent consumers;
- `mvn -f reactor/pom.xml clean -Prelease verify`: PASS for strict Javadocs, artifacts,
  POM/JAR signatures, and both modules;
- `bash scripts/verify-reproducible-build.sh`: PASS for all six JARs;
- reduced v2 soak: PASS with 2,000 documents, 2 readers, 2 writers, and 3 seconds;
- target-machine v2 soak: PASS with 100,000 documents, 8 readers, 2 writers, and
  300.11 seconds; 10,459 unranked searches, 10,628 ranked searches, 19,888 mutations,
  2,701 index cycles, and final version 15,682.

The mixed P7 oracle covers structured and analyzed-text boolean queries, BM25 ranking,
single and explicit-bulk mutations, structured/text index drop and recreation, and old
snapshot isolation. Analyzer exceptions during add/update publish neither documents nor
text/ranking metadata. Mutation failure and rejection metrics are published before
completion callbacks can observe them; P7 found and fixed the previous ordering race.

## Target-machine concurrency soak

Run from the repository root in the IntelliJ terminal. The default below lasts five
minutes and exercises concurrent structured/text queries, ranked retrieval, mutations,
and dynamic Range index build/drop cycles:

```bash
mvn -DskipTests test-compile

java -cp target/test-classes:target/classes \
  io.github.patricklfdm.generalsearch.benchmark.V2EngineConcurrencySoak \
  --documents=100000 --readers=8 --writers=2 --seconds=300 --seed=7007
```

Acceptance requires `status=PASS`, no worker exception or hang, non-zero unranked,
ranked, mutation, and index-cycle counts, and successful final exhaustive state
comparison. Preserve the final summary output line or paste it back for review.

## Representative P7 JMH regression matrix

Build the benchmark JAR once:

```bash
mvn -Pjmh -DskipTests clean package
```

Then run these four independently resumable groups:

```bash
java -jar target/benchmarks.jar \
  '.*(RangeIndexComparisonBenchmark|MutationBatchScalingBenchmark|DynamicIndexBuildBenchmark).*' \
  -prof gc -rf json -rff target/jmh-p7-structured.json

java -jar target/benchmarks.jar \
  '.*(TextTermQueryBenchmark|TextIndexPublicationBenchmark|TextIndexBuildBenchmark).*' \
  -prof gc -rf json -rff target/jmh-p7-text.json

java -jar target/benchmarks.jar \
  '.*(Bm25TopKBenchmark|Bm25MultiTermBenchmark|RankedMetadataPublicationBenchmark).*' \
  -prof gc -rf json -rff target/jmh-p7-ranking.json

java -jar target/benchmarks.jar '.*ExplicitBulkMutationBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p7-bulk.json
```

Expected primary rows are 34 structured, 37 text, 62 ranking, and 8 bulk: 141 total.
Every benchmark setup assertion must pass. Compare only against the corresponding P3,
P4, P5, or P6 baseline on the same machine/JDK. Treat an adverse movement above 20%
whose error intervals do not overlap as an investigation trigger, not an automatic
regression verdict; rerun the affected rows before drawing a conclusion.

The formal matrix is accepted and documented in
[`PERFORMANCE_BASELINE.md`](PERFORMANCE_BASELINE.md). All 141 rows and
setup assertions passed. Two high-variance timing rows retained stable allocation; a
targeted explicit-bulk confirmation ruled out the only apparent repeatable regression.

## Baseline map and v1 comparison

| Area | Accepted evidence | P7 interpretation |
|---|---|---|
| v1 Range and mutation | [`../../../v1/PERFORMANCE_BASELINE.md`](../../../v1/PERFORMANCE_BASELINE.md) | historical v1 workload reference |
| estimates/statistics | [`../p1/PERFORMANCE_BASELINE.md`](../p1/PERFORMANCE_BASELINE.md) | establishes estimation/materialization split |
| bitmap/publication | [`../p2/PERFORMANCE_BASELINE.md`](../p2/PERFORMANCE_BASELINE.md) | accepts structural-sharing representation |
| cost-aware planner | [`../p3/PERFORMANCE_BASELINE.md`](../p3/PERFORMANCE_BASELINE.md) | preserves selective index benefit and avoids broad-index regressions |
| analyzed text | [`../p4/PERFORMANCE_BASELINE.md`](../p4/PERFORMANCE_BASELINE.md) | 58 accepted query/publication/build rows |
| BM25/top-K | [`../p5/PERFORMANCE_BASELINE.md`](../p5/PERFORMANCE_BASELINE.md) | 70 accepted ranking/publication/build rows |
| explicit bulk | [`../p6/PERFORMANCE_BASELINE.md`](../p6/PERFORMANCE_BASELINE.md) | 8 accepted success/rollback rows |

The v1 and v2 mutation benchmarks do not expose identical APIs or internal
representations, so their absolute numbers must not be advertised as a direct speedup.
The strongest cross-version conclusion is behavioral: v2 retains one immutable
publication per accepted batch, adds bounded explicit bulk, and removes the v1
planner's need to materialize every broad Range candidate before choosing scan.
