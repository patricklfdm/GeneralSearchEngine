# V3.2 performance and evidence contract

## Evidence anchors

Published `v3.1.0` is the source and compatibility anchor. Existing cloud evidence
families remain immutable:

- `v3.0.0-cloud` anchors the unchanged production TEXT/BOOL/PHRASE/FUZZY regression
  preset when environment and configuration identities match; and
- `v3.1.0-ranked-cloud` anchors the distinct phrase-slop/BOOL-minimum feature family.

Highlight metrics are not inserted into either frozen preset and are not compared
directly with either family. Phase 1 first captures a same-machine pre-change baseline
from exact signed `v3.1.0` and the unchanged current test/benchmark harness.

## Storage decision evidence

V3.2 freezes top-K re-analysis instead of stored offsets. The implementation must prove
the consequences of that decision rather than silently changing representation:

- no offset array/map/sidecar is retained in `TextIndexSnapshot`;
- ordinary index build, dynamic build, mutation publication, ordinary search, and
  Explain do not construct offset result objects;
- retained heap per document/token remains structurally unchanged;
- explicit highlighting cost scales with returned hits and requested source length,
  not total indexed document count; and
- no analyzer output, highlight evidence, or captured snapshot leaks after a call.

If measurements show top-K re-analysis is unacceptable, V3.2 does not silently add
stored offsets. That would change 1M retained-memory and publication costs and requires
a contract amendment with before/after evidence.

## Required local benchmark surfaces

### Ordinary-path regression

Run the existing text-index build, single/bulk mutation, dynamic build, TEXT, exact and
sloppy PHRASE, FUZZY, BOOL, Explain, concurrency, and reduced-soak cells. Compare exact
`v3.1.0` with each implementation stage on the same JDK/JVM and machine.

The built-in SimpleAnalyzer ordinary path receives special allocation inspection. Its
new capability must not make ordinary indexing/search derive or allocate
`OffsetAnalyzedToken` values.

### Offset analysis

Measure ordinary versus offset-aware SimpleAnalyzer for:

- ASCII, BMP Unicode, supplementary code points, combining sequences, and NFKC
  length-changing characters;
- short, medium, and long source fields;
- low/high token density and punctuation density;
- output term/position/offset count and normalized allocation per source unit; and
- single-thread and bounded concurrent analyzer invocation.

Correctness checks and source-range checksums are prepared outside the timed path.

### Highlighted search

Measure a matrix over:

- corpus sizes `100_000` and `1_000_000`;
- top K `1`, `10`, and `100`;
- one and three requested fields;
- short, medium, and long retained source values;
- TEXT, exact PHRASE, sloppy PHRASE, FUZZY, nested BOOL, and BOOST;
- sparse, dense, duplicate, and overlapping ranges;
- context `0`, `40`, and `160`;
- fragment caps `1`, `3`, and `10`; and
- no-hit, hit-with-no-requested-field-range, and fully highlighted cases.

Report mean time, distribution when the harness supports it, allocation per operation,
GC, fragment/span cardinality, and consumed checksums. Ordinary search with the same
embedded request is the local control, but highlighted overhead is reported as a
workload-specific delta rather than a universal percentage claim.

### Concurrency and lifecycle

Mixed evidence includes highlighted readers, ordinary readers, Explain, and one writer
performing bounded single/bulk updates. Record reader latency/throughput, writer
progress, queue depth, allocation/GC, errors, final document count, and final oracle
agreement. Dynamic build/drop and close are exercised separately from the timed steady
state.

## Profiling protocol

Each implementation stage follows:

```text
exact-v3.1 pre-change baseline
-> one narrow implementation change
-> focused correctness and compatibility
-> allocation/JFR or equivalent profile
-> focused benchmark rerun
-> ordinary regression suite
-> highlighted feature matrix when applicable
```

Profiles distinguish analyzer normalization/mapping, query execution, source
extraction, witness reconstruction, interval normalization, substring creation, result
object construction, and garbage collection. Optimization cannot change visible
ranges, fragment order, failure precedence, search/Explain semantics, or snapshot
isolation.

## Cloud boundary

Phase 0 creates no paid cloud run and changes no protected workflow. A future canonical
highlight lane requires a separately reviewed `v3.2-highlight-v1`-style preset and
mode with complete metric identities, bounded cost, Standard provisioning, immutable
retention, and the existing Cloud Benchmark V2 evidence lifecycle.

The unchanged regression lane remains directly comparable only when its preset,
suite, JMH parameters, JVM, configuration fingerprint, environment fingerprint, and
metric set remain identical. A highlight feature lane establishes its own family and
must never be registered as a replacement for `v3.0.0-cloud` or
`v3.1.0-ranked-cloud`.

## Acceptance policy

Correctness, compatibility, absence of ordinary-path offset allocation, bounded
highlight output, writer progress, cleanup, and evidence validity are hard gates.

No fixed latency/allocation percentage is frozen in Phase 0 because the project does
not yet have repeated comparable highlight histories. Material regressions require
profiling and review; they cannot be hidden by averaging unrelated cells. A numerical
CI threshold may be introduced only after multiple comparable runs justify a separate
contract.
