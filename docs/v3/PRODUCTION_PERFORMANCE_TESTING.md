# V3 production performance testing

## Purpose

The 3.0.0 release baseline is bounded release evidence. This follow-up suite adds the
production-shape coverage that was intentionally not claimed by that baseline:

- 10k, 100k, and 1M document scaling for TEXT, BOOL, PHRASE, and FUZZY;
- top-K scaling at 10, 100, and 1,000 results;
- uniform short single-field, Zipf-like medium four-field, and Zipf-like bilingual
  long four-field synthetic corpora;
- mixed reads and snapshot mutations at 1:1, 4:1, and 16:1 reader/writer ratios, with
  sampled p50/p95/p99/max latency and GC allocation evidence;
- an opt-in 30-minute read/write/dynamic-index soak with one-second heap, GC, writer
  queue, snapshot, and operation-count samples.

This still is not a portable SLA. The bilingual corpus is deterministic and
representative, not a claim to reproduce a particular private production corpus.

## Persistent output

Every run is written to:

```text
benchmark-results/v3-production/<UTC timestamp>-<commit>-<mode>/
```

Unlike `target/`, this location survives `mvn clean`. Generated result directories are
ignored by Git. Each run contains `environment.txt`, `metadata.txt`, `status.properties`,
the build log, JMH JSON/log pairs or soak CSV/properties, and `checksums.sha256`. The
`LATEST` file points to the newest local run. A complete run has `status=PASS`; a failed
or interrupted run remains useful but must not be presented as complete evidence.

## Commands

Run a short end-to-end validation first:

```bash
scripts/run-v3-production-performance.sh quick
```

Run the full JMH matrix only on an otherwise idle machine:

```bash
scripts/run-v3-production-performance.sh full
```

Run only the three concurrency ratios, recording latency and throughput separately:

```bash
scripts/run-v3-production-performance.sh concurrency
```

Run the default 30-minute soak separately:

```bash
scripts/run-v3-production-performance.sh soak
```

Run both the full matrix and soak in one result directory:

```bash
scripts/run-v3-production-performance.sh all
```

The defaults use `-Xms2g -Xmx6g`. Override them and the run length without editing the
script, for example:

```bash
GSE_PERF_JVM_OPTIONS='-Xms4g -Xmx8g' \
GSE_SOAK_READERS=8 \
GSE_SOAK_SECONDS=1800 \
scripts/run-v3-production-performance.sh soak
```

Useful JMH overrides are `GSE_JMH_FORKS`, `GSE_JMH_WARMUPS`,
`GSE_JMH_ITERATIONS`, and `GSE_JMH_DURATION`. Reduced values are diagnostic only and
must be recorded with the result.

## Review protocol

Before comparing two runs, confirm the commit, Java version, heap settings, logical
CPU count, working-tree state, and run status. For JMH JSON, compare the primary score,
confidence interval, sampled percentiles, `gc.alloc.rate.norm`, and GC counts; do not
treat small one-run differences as regressions.

For soak output, require all of the following:

- `soak-summary.properties` reports `status=PASS` and `errors=0`;
- the writer queue does not remain near capacity;
- used heap reaches a bounded operating band rather than rising monotonically for the
  entire steady-state window;
- late-run operation rate and GC time do not show sustained degradation, and the
  whole-run bounded-reservoir p95/p99 remains acceptable for the target workload;
- final document count is unchanged and snapshot version continues to advance.

When requesting result analysis, provide the complete timestamped result directory,
not just copied console lines. The JSON, CSV, metadata, and checksums are needed to
distinguish engine behavior from environment noise.

The reviewed follow-up evidence and bounded gate decision are recorded in the
[production performance results](PRODUCTION_PERFORMANCE_RESULTS.md).

When a cloud soak shows sustained throughput or heap-band drift, use the frozen
[cloud soak diagnostics contract](CLOUD_SOAK_DIAGNOSTICS.md) before proposing an engine
optimization. Its flags trigger review and controlled experiments; they are not SLAs.

For reproducible C3D execution independent of a developer workstation, use the
[GCP cloud performance runner](CLOUD_PERFORMANCE_TESTING.md). It invokes this same
benchmark suite rather than maintaining a second workload implementation.
