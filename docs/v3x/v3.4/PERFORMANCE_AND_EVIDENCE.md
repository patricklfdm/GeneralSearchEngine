# V3.4 performance and evidence contract

## Evidence anchors

Published `v3.3.0` at
`b399ee999e65ca363e68503720dedd4ddd2b3c2e` is the source, behavior, artifact, and
compatibility anchor. Its published core JAR SHA-256 is:

```text
18fb6439be074b39e5f22e2b01fba327ee919a4997e6429551481ef7fb8754f4
```

Existing immutable cloud families retain their original meaning:

- `v3.0.0-cloud` remains the frozen general regression family; and
- `v3.1.0-ranked-cloud` remains the ranked phrase-slop/BOOL/fuzzy feature family.

V3.4 does not append metrics or cells to either family. Selected unchanged cells may
be rerun for regression context only when the existing preset and environment identity
remain exact. New hardening cells belong to the independent
`v3.4.0-in-memory-cloud` family.

## Evidence classes

V3.4 separates four classes that must not be averaged together:

1. **correctness gates** — deterministic pass/fail oracles;
2. **local diagnostics** — profiling and resource-shape investigation;
3. **cloud experiment evidence** — calibration or one-off two-hour investigation;
4. **canonical evidence** — three or more eligible Standard members under the exact
   final preset and environment rules.

A faster diagnostic cell cannot excuse a failed correctness gate. An experiment cannot
be registered as a canonical member. A cross-hardware result is exploratory unless it
has its own family and repeated eligible members.

## Common evidence identity

Every retained result records at least:

- source commit, tree cleanliness, version, suite schema, mode, and preset;
- workload name, deterministic seed, corpus generator version, document/field/index
  counts, vocabulary/position shape, and mutation history;
- machine type, provisioning model, CPU vendor/model, image identity, kernel, and disk;
- Java vendor/runtime/VM, collector, complete JVM options, heap, and processor count;
- fork/warmup/measurement configuration, duration, start/end time, and exit state;
- operation counts, checksums/oracle outcome, latency/throughput distribution,
  allocation, GC, heap, queue, publication, and error fields applicable to the cell;
  and
- artifact location, manifest/checksum, retention, cleanup, and comparison eligibility.

Missing identity is an evidence failure, not a reason to infer a default.

## Required local surfaces

### Cold process and construction

Use independent JVM processes and distinguish:

```text
process start
-> engine construction
-> initial document generation/load
-> initial structured index availability
-> initial text index availability
-> ready-to-search checkpoint
-> first verified query
```

Dynamic structured and text index builds run separately after the ready checkpoint.
Required scales are at least 100k and 1M documents when the local machine can complete
the cell within its declared resource cap. Each retained configuration uses at least
five independent processes and reports individual values plus median and variation.

Timing excludes dependency download and project compilation. Corpus construction time
is reported separately from engine ingestion rather than silently subtracted.

### Extreme corpus matrix

Deterministic generators cover these independent axes before any composed stress cell:

- very long text values;
- one very high-frequency term;
- large vocabulary and sparse vocabulary;
- Zipf-heavy term frequency;
- multiple indexed text fields;
- bilingual and Unicode-heavy text;
- repeated terms and large logical position gaps; and
- position-heavy exact/sloppy phrase and fuzzy vocabulary cases.

Each cell records match/score/order/Explain checksums against existing independent
oracles. Invalid analyzer output and overflow boundaries remain correctness tests, not
performance samples.

### Heap matrix

Required diagnostic heap sizes are `4g`, `8g`, and `16g`. A `32g` cell is optional and
is retained only when the machine has sufficient physical memory without swapping.
Every cell uses an explicitly recorded collector and equal corpus/workload identity.

The matrix reports:

- peak and post-settle used heap;
- live-set estimate and full-GC measurement method;
- allocation rate and bytes per operation;
- GC count, pause distribution, and CPU time;
- document/index/posting/cursor counts; and
- success, controlled rejection, or resource exhaustion.

An out-of-memory result may be useful diagnostic evidence but is never a passing
baseline member. Different heap sizes are sensitivity cells, not direct repeats.

### Multi-producer burst and recovery

Required producer counts are `1`, `4`, and `16`; required submitted batch sizes are
`1`, `100`, and `1,000`. The reviewed matrix may prune redundant cross-products only
after a written calibration decision preserves the low, medium, and saturation edges.

Record submission rate, admission/completion latency, queue depth, writer batch size,
publication rate, reader latency, failures, executor rejection, GC, and the time from
last submission to queue drainage. Every successful cell finishes with a complete
document/index/query oracle and zero unresolved mutation futures.

Producer concurrency never changes the one-writer architecture. A test harness must
not use unbounded submission without an explicit operation and memory cap.

### Local long-run calibration

Before paid execution, bounded 30-minute and reduced-duration cells prove that the
sampler, window aggregation, oracle checkpoints, queue telemetry, artifact capture,
failure injection, and cleanup work. Local calibration is not the required two-hour
release run.

## Required two-hour run

One exact final-candidate source identity runs a two-hour controlled mixed workload.
It includes ordinary, ranked, highlighted, paged/exact-total, and Explain readers;
bounded mutation bursts; steady mutation; and dynamic structured/text index lifecycle.

Acceptance requires:

- zero unexpected exception or semantic-oracle failure;
- writer progress in every active writer window;
- no unresolved future and complete queue drainage at the final checkpoint;
- monotonically valid publication/snapshot evidence;
- bounded live-state behavior after declared warmup and burst recovery windows;
- no unexplained sustained throughput or p99 drift; and
- complete manifests, raw windows, checksums, diagnostics, and cleanup evidence.

Phase 0 freezes no universal numeric plateau or drift percentage. Phase 3 calibration
must define workload-specific review bands from repeated comparable histories before a
number can fail the release. A reviewer may reject unexplained monotonic drift even
when a provisional band is not crossed.

## Final canonical set

The final set uses:

- mode `final-v34`;
- preset `v3.4-final-in-memory-v1`;
- suite `v3.4-final-in-memory-suite-v1`;
- Standard `c3d-standard-30` provisioning;
- the fixed 30-minute canonical window;
- one exact image, Java 21 runtime, JVM option set, and final `3.4.0` source commit;
- GCS retention with complete manifests and cleanup receipts; and
- at least three independent eligible members.

The reviewed report preserves every member, median, variation, exclusions, reasoned
comparison eligibility, and raw artifact reference. The accepted registration name is
`v3.4.0-in-memory-cloud`.

The required two-hour run is a separate one-repeat Standard/GCS experiment using the
same V3.4 preset and a distinct duration fingerprint. It is supplemental evidence and
cannot be admitted as a 30-minute canonical member.

## Cross-hardware policy

Cross-hardware validation is optional. A secondary AWS, local Intel, or different GCP
CPU result uses a different environment fingerprint and baseline family. It may reveal
hardware-sensitive behavior but cannot be aggregated with the C3D canonical set or
used as a direct replacement.

## Regression and optimization policy

V3.4 begins with measurement and review, not a fixed `+5%` failure rule. A material
ordinary-path, correctness, writer-progress, retained-memory, or construction
regression triggers profiling. It does not automatically authorize implementation.

Any accepted production fix must retain before/after evidence under an identical
workload, rerun all affected correctness and compatibility gates, and invalidate every
earlier V3.4 member built from the unfixed source identity.
