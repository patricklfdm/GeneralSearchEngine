# V3.2 Phase 5 highlighting hardening and profiling baseline

## Scope and comparison eligibility

This record captures lifecycle, mutation, dynamic-index, mixed-concurrency, scaling,
allocation, latency, and retained-memory evidence from the Phase 4 production
implementation. The independent branch starts from protected merge commit `1dd81d1`.
Tests and benchmark surfaces were added before profiling; no production source was
changed in Phase 5.

These short, single-fork WSL2 results are local diagnostics. They are not canonical
evidence, do not replace either immutable cloud family, and must not be used as a
cross-machine numerical gate. Raw JSON and JFR recordings remain disposable under
`target/`.

## Environment and protocols

- captured: 2026-08-30, America/Los_Angeles;
- OS: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64;
- CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs;
- memory visible to WSL2: 15 GiB, with 4 GiB swap;
- JVM: OpenJDK 21.0.12, 64-bit Server VM;
- JMH: 1.37;
- scale protocol: one fork, one or two 500 ms warmups, one to three 500 ms
  measurements, GC profiler; and
- concurrency protocol: one fork, ten group threads, one 500 ms warmup, three 500 ms
  sample-time measurements.

The representative top-K command is:

```bash
java -jar target/benchmarks.jar 'V32HighlightScaleBenchmark.*Search' \
  -p documentCount=10000 -p topK=1,10,100 \
  -p requestedFieldCount=1 -p sourceTokenCount=16 \
  -p queryKind=text -p outcome=highlighted \
  -p contextCharacters=40 -p maxFragmentsPerField=3 \
  -f 1 -wi 2 -w 500ms -i 3 -r 500ms -prof gc -foe true
```

The `-Xmx10g` 1M run uses one 500 ms warmup and one 500 ms measurement because it is
a bounded capacity/shape observation, not a latency claim.

## Top-K scaling

| Top K | Ordinary time | Highlighted time | Ordinary allocation | Highlighted allocation | Allocation delta |
|---:|---:|---:|---:|---:|---:|
| 1 | 1,142.570 us/op | 1,279.979 us/op | 878,010.562 B/op | 908,270.724 B/op | +30,260.162 B/op |
| 10 | 1,240.374 us/op | 1,297.165 us/op | 878,444.580 B/op | 935,027.745 B/op | +56,583.165 B/op |
| 100 | 1,270.129 us/op | 2,199.551 us/op | 883,076.377 B/op | 3,603,731.488 B/op | +2,720,655.111 B/op |

The explicit cost grows with returned hits as designed. The top-100 timing interval is
wide and makes no universal latency statement. Fragment/span cardinality and immutable
result construction are deliberately consumed, so the pressure cannot be optimized
away as dead output.

## Requested-field, source-length, and outcome shapes

The table below uses BOOL/BOOST, top K 10, context 40, cap 3, and 10,000 documents.

| Outcome | Fields | Source tokens | Mean time | Allocation |
|---|---:|---:|---:|---:|
| highlighted | 1 | 16 | 6,771.803 us/op | 3,293,486.703 B/op |
| highlighted | 1 | 256 | 8,549.381 us/op | 7,323,613.966 B/op |
| highlighted | 3 | 16 | 6,625.806 us/op | 3,833,869.789 B/op |
| highlighted | 3 | 256 | 10,460.256 us/op | 16,200,537.327 B/op |
| unrelated requested fields | 1 | 16 | 6,615.604 us/op | 3,265,621.604 B/op |
| unrelated requested fields | 1 | 256 | 8,053.672 us/op | 7,164,325.394 B/op |
| unrelated requested fields | 3 | 16 | 6,667.475 us/op | 3,865,428.594 B/op |
| unrelated requested fields | 3 | 256 | 9,992.729 us/op | 16,042,848.006 B/op |
| no hit | 1 | 16 | 0.522 us/op | 2,945.070 B/op |
| no hit | 3 | 256 | 0.585 us/op | 2,977.225 B/op |

Returned hits cause every nonempty explicitly requested field to be extracted,
offset-analyzed, and sequence-validated even when that field produces no evidence.
That preserves the frozen requested-field failure behavior. The no-hit path performs
capability and canonical request validation but no source analysis, so its result is
independent of configured source length.

## Corpus scaling and retained shape

The following TEXT top-10 cells use one requested 16-token source field:

| Corpus | Ordinary time | Highlighted time | Ordinary allocation | Highlighted allocation | Delta |
|---:|---:|---:|---:|---:|---:|
| 100,000 | 20,618.968 us/op | 20,983.207 us/op | 8,798,768.320 B/op | 9,099,531.213 B/op | +300,762.893 B/op |
| 1,000,000 | 177,637.985 us/op | 171,148.497 us/op | 88,015,162.667 B/op | 88,352,514.667 B/op | +337,352.000 B/op |

The highlighting delta remains the same order of magnitude while canonical search
work scales tenfold with the corpus. The lower 1M highlighted point estimate is short
run noise, not an improvement. Structurally, `TextIndexSnapshot` retains no offset,
highlight, evidence, or sidecar field, and instrumented ordinary indexing, mutation,
dynamic build, search, and Explain invoke the offset path zero times.

## Mixed concurrency

The group contains four highlighted readers, four ordinary readers, one Explain
reader, and one update writer over 10,000 documents:

| Operation | Mean sample | p50 | p95 | p99 |
|---|---:|---:|---:|---:|
| highlighted reader | 7,841.773 us | 7,471.104 us | 11,835.802 us | 15,351.153 us |
| ordinary reader | 7,907.279 us | 7,544.832 us | 11,816.960 us | 15,379.661 us |
| Explain reader | 443.012 us | 424.192 us | 817.152 us | 1,571.348 us |
| writer | 6,205.971 us | 6,037.504 us | 7,520.256 us | 10,318.643 us |

All 246 sampled writer publications complete and the observed queue maximum is zero.
The highlighted and ordinary reader distributions overlap; the evidence establishes
progress and absence of a highlighting-specific concurrency cliff, not a claim that
highlighting improves latency.

## JFR profile and stopping decision

One 500 ms warmup and one 1 s instrumented measurement profile both TEXT and nested
BOOL/BOOST highlighted search at 10,000 documents and top K 10. The recordings are
hotspot locators only.

BOOL/BOOST allocation samples are led by integer lookup, canonical ranked-candidate
construction, `ScoreMatch`, and fuzzy evaluation. TEXT CPU samples are dominated by
`TextIndexSnapshot.documentLength` and persistent-map access. Offset normalization,
mapped-source construction, span construction, fragment construction, and phrase
witness work appear only as individually small samples. Old-object inspection finds
no retained highlight/evidence/offset-token/snapshot candidate; one JDK concurrent-map
array from benchmark infrastructure is the only sampled leak candidate.

No production optimization is accepted in Phase 5. The residual pressure either
belongs to unchanged canonical ranking or to the explicitly requested top-K source
analysis and immutable output. Removing requested-field validation, weakening Unicode
source mapping, storing offsets, or changing scoring/index representation would exceed
the evidence and frozen contract. The correct engineering decision is to stop.

## Correctness and cloud boundary

Focused hardening covers add/update/remove/bulk snapshot publication, dynamic text
build with journal replay, cancelled drop/create, admitted read across close, failed
analysis with no publication, mixed readers/writer, exact source projection, zero
ordinary offset calls, and the retained snapshot field shape. The complete core suite
contains 343 passing tests.

No paid cloud run is required. Phase 5 adds local benchmark surfaces but no protected
workflow, cloud preset, metric identity, stored index shape, or immutable evidence
family. A future canonical highlight lane still requires its own separately reviewed
mode, cost, retention, and comparison contract.

## Reproduction boundary

Build and execute the bounded discovery gates with:

```bash
scripts/verify-jmh-smoke.sh
```

The smoke cells prove benchmark discovery and bounded execution only. They are not
latency, allocation, concurrency, or retained-memory thresholds.
