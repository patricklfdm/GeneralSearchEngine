# V3.3 Phase 4 hardening and decision baseline

## Scope and comparison boundary

This record captures publication, concurrency, cursor-retention, expensive-query, and
deep-page evidence after the Phase 3 strict search-after implementation. The branch
starts from protected-master merge commit `521e65e`. Phase 4 changes no production
source or public descriptor; it adds deterministic hardening fixtures, diagnostic
benchmark surfaces, and the required timeout/cancellation and preparation decision.

These short WSL2 measurements are local diagnostics. They are not canonical cloud
evidence, numerical CI thresholds, or cross-machine performance claims. Raw JMH JSON
remains disposable under `target/`.

## Environment and protocols

- captured: 2026-08-30, America/Los_Angeles;
- OS: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64;
- CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs;
- memory visible to WSL2: 15 GiB, with 4 GiB swap;
- JVM: OpenJDK 21.0.12, 64-bit Server VM;
- JMH: 1.37;
- expensive-query protocol: one fork, one 300 ms warmup, two 300 ms measurements,
  GC profiler; and
- concurrency protocol: one fork, eight group threads, one 500 ms warmup, three
  500 ms throughput and sample-time measurements.

The depth-100 matrix command is:

```bash
java -jar target/benchmarks.jar 'V33PaginationHardeningBenchmark.*' \
  -p documentCount=10000 -p pageSize=10 -p pageDepth=100 \
  -p queryKind=phrase,fuzzy,dense-bool,expensive-filter \
  -f 1 -wi 1 -i 2 -w 300ms -r 300ms -prof gc \
  -rf json -rff target/v33-phase4-hardening-depth100.json -foe true
```

## Publication and controlled concurrency

Deterministic fixtures cover successful add, update, remove, bulk add/update/remove,
dynamic index create, and dynamic index drop. A publication before continuation
capture rejects the old cursor as `STALE_SNAPSHOT`. A barrier after capture proves
each admitted continuation completes wholly from its old snapshot for all eight
publication kinds.

Failed duplicate add, missing update, failed atomic bulk add/update, and duplicate
dynamic-index create leave the snapshot version unchanged and the cursor usable. An
idempotent drop of a known field with no index also publishes nothing and leaves the
cursor usable.

Three readers reuse and branch from the same cursor under an analyzer barrier while a
writer publishes and drains its queue. All three readers return the captured hit bits
and count, while a new invocation rejects the old cursor as stale. This proves that
cursor retention and admitted page execution do not block writer progress.

The mixed JMH group contains two ordinary readers, two disabled page readers, one
exact page reader, one highlighted reader, one Explain reader, and one writer over
10,000 documents. Publication intentionally races the gap between first and second
page, so stale continuation is a successful expected outcome.

| Operation | Mean sample | p50 | p95 | p99 |
|---|---:|---:|---:|---:|
| ordinary | 7,107.094 us | 6,950.912 | 9,859.072 | 13,378.355 |
| disabled page pair | 7,353.301 us | 6,930.432 | 9,989.325 | 14,719.713 |
| exact page pair | 7,377.633 us | 7,172.096 | 10,056.499 | 13,219.430 |
| highlighted | 7,177.379 us | 7,036.928 | 9,987.686 | 12,044.206 |
| Explain | 381.715 us | 288.768 | 693.248 | 1,089.536 |
| writer | 5,966.037 us | 5,804.032 | 6,913.229 | 10,516.726 |

The sample-mode window completes 256 writer publications, observes 617 expected stale
continuations and one successful race, and records zero writer-queue buildup. The
separate throughput-mode window completes 263 publications. Correctness does not rely
on these race counts; the barrier fixtures deterministically prove both accepted and
stale outcomes.

## Cursor retained-heap envelope

`V33CursorRetentionProbe` runs each cardinality in an isolated fixed 256 MiB JVM after
10,000 warmup cursor creations. Each measurement takes the minimum used heap across
six requested full-GC observations before retention, while live, and after release.

```bash
for cursor_count in 1 1000 100000; do
  java -Xms256m -Xmx256m -cp target/benchmarks.jar \
    io.github.patricklfdm.generalsearch.benchmark.jmh.V33CursorRetentionProbe \
    "$cursor_count"
done
```

| Live cursors | Retained delta | Per-cursor envelope | Post-release residual |
|---:|---:|---:|---:|
| 1 | 88 B | 88.000 B | 112 B |
| 1,000 | 44,120 B | 44.120 B | 192 B |
| 100,000 | 4,401,512 B | 44.015 B | 32 B |

The one-object cell is below the reliable resolution of a process-heap delta and is
reported only for completeness. The 1,000 and 100,000 cells converge near 44 bytes per
live cursor including the retaining list reference envelope on this compressed-oops
JVM. Full release returns to the baseline within 32–192 bytes of measurement noise.

Independent reflection still supplies the semantic proof: every cursor has exactly
two direct references and three primitive fields, retains no engine or snapshot graph,
and the engine has no cursor registry. A hardening fixture keeps 100,000 distinct
cursors live while an update publishes, drains the writer queue, and makes sampled
cursors stale.

## Expensive-query and deep-page evidence

The depth-100 matrix uses 10,000 full matches and page size 10:

| Query | Disabled time | Exact time | Disabled allocation | Exact allocation |
|---|---:|---:|---:|---:|
| high-frequency phrase | 3,238.697 us | 3,172.667 us | 1,326,885 B/op | 1,326,917 B/op |
| fuzzy vocabulary | 1,427.502 us | 1,440.723 us | 1,087,914 B/op | 1,087,938 B/op |
| dense BOOL/BOOST | 7,654.507 us | 7,487.344 us | 4,974,967 B/op | 4,974,985 B/op |
| expensive filter | 3,406.092 us | 3,487.852 us | 847,178 B/op | 847,204 B/op |

Exact-minus-disabled allocation remains approximately 18–32 B/op in these paired
cells and adds no per-match object. The short latency points are not statistically
separated and make no claim that either total mode is faster.

The explicit deep-page cell uses 20,000 dense BOOL matches, page size 10, and depth
1,000:

| Total mode | Mean time | Allocation |
|---|---:|---:|
| disabled | 16,353.066 us/op | 9,230,276 B/op |
| exact | 15,879.682 us/op | 9,710,287 B/op |

The latency points overlap in interpretation and remain dominated by complete
candidate/query evaluation. The exact-cell allocation difference is the same
fork-dependent scalar-replacement shape already recorded in Phase 3, scaled with the
20,000-candidate corpus; it is not evidence of exact-count object allocation. V3.3
continues to claim neither index seeking nor O(page-size) continuation.

## Timeout, cancellation, and prepared-query decision

Phase 4 explicitly defers timeout/cancellation and prepared queries. No contract
amendment or implementation is accepted for V3.3.

The evidence shows useful cooperative checkpoints inside engine-owned candidate,
phrase, fuzzy, BOOL, and page loops, but does not establish a consumer latency budget
or a safe complete control surface. The engine cannot preempt arbitrary application
analyzers, field extractors, or structured-filter callbacks. A correct public feature
would also need frozen clock, expiry, exception, failure-precedence, exact-total,
lifecycle, metrics, and ordinary/page/highlight/Explain composition semantics.

The heaviest reviewed individual continuation is approximately 16 ms locally. Deep
cursor setup is cumulative repeated full evaluation rather than one unbounded
invocation. That evidence does not justify charging every normal request for a
speculative cancellation control or exposing a partial guarantee that cannot cover
consumer callbacks.

Prepared queries are also deferred. Depth and query-family evidence remains dominated
by candidate evaluation, scoring, and callbacks; it does not show logical
normalization as a material retained hotspot. No snapshot-bound physical plan, global
cache, or thread-local request cache is introduced.

## Cloud and stopping boundary

No paid cloud run is required. Phase 4 changes no production code, stored index shape,
protected workflow, cloud preset, or immutable evidence family. `v3.0.0-cloud` and
`v3.1.0-ranked-cloud` remain unchanged.

The engineering stopping decision is to retain the Phase 3 implementation as-is.
Correctness, retained-memory, and writer progress are established without a cursor
registry, snapshot pinning, cancellation API, prepared query, or speculative physical
optimization.
