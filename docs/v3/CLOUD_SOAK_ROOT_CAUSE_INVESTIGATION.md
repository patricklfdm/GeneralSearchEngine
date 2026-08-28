# V3 cloud soak root-cause investigation contract

Status: frozen before implementation on 2026-08-28.

## Trigger and objective

The completed [cloud soak diagnostic results](CLOUD_SOAK_DIAGNOSTIC_RESULTS.md)
establish a reproducible duration-dependent signal on Standard C3D-30. Three
independent 600-second runs of both maximum-contrast configurations showed
approximately six percent early-to-late read-rate decline. Two independent 30-minute
production-configuration runs then measured 536.320 and 536.368 read ops/s with
-11.291% and -12.007% read drift.

Heap maximum, dynamic range-index lifecycle, GC saturation, and writer backlog did not
explain the signal. The existing aggregate soak still cannot distinguish:

- a time-dependent search/runtime effect on an unchanged snapshot;
- mutation or snapshot-publication state that accumulates even when content is stable;
- changing corpus terms, selectivity, or candidates after document revisions;
- a query-specific TEXT, BOOL, PHRASE, or FUZZY path.

This phase adds benchmark-only controls and evidence needed to separate those cases. It
does not optimize the engine. A reproducible factor and query path must be identified
before a product change is proposed.

## Scope and non-goals

This phase may change only `src/jmh`, benchmark orchestration and analysis scripts,
their tests, CI wiring, and documentation. It must not change `src/main`, search truth,
scoring, result ordering, snapshot publication, index implementation, public API,
release coordinates, or the default behavior of existing benchmark modes.

The investigation must not call the observed heap movement a leak. Sampled used heap
is not a post-full-GC live-set measurement. JFR evidence is diagnostic sampling, not a
portable allocation or CPU SLA.

Existing `quick`, `full`, `concurrency`, `soak`, and `all` invocations retain their
current arguments, default workload, filenames, and analysis semantics. Historical
soak evidence must remain analyzable. Raw generated evidence remains ignored by Git and
must not be modified after its run-level checksum manifest is created.

## Dedicated investigation mode

Add `investigation` to the local production runner and cloud orchestrator. It runs only
the production soak and requires:

```text
GSE_SOAK_INVESTIGATION_CELL=read-only|stable-update|revision-update
```

The three cells map to Java workload configuration as follows:

| Cell | Readers | Writers | Update mode | Index cycles |
|---|---:|---:|---|---:|
| `read-only` | 16 | 0 | `none` | false |
| `stable-update` | 16 | 1 | `stable` | false |
| `revision-update` | 16 | 1 | `revision` | false |

`stable` repeatedly replaces each selected document with its deterministic revision-zero
content. It must still execute real `engine.update(...).join()` calls and publish new
snapshots; it is not a skipped or short-circuited writer loop. `revision` retains the
existing per-document revision behavior. `none` starts no writer or lifecycle worker.

The investigation mode derives writer count, update mode, disabled lifecycle, and
enabled per-query metrics from the selected cell. Explicit
`GSE_SOAK_WRITERS` or `GSE_SOAK_INDEX_CYCLES` values that conflict with the cell fail
before a VM is created. Missing or unknown cells also fail with configuration exit code
2 before provisioning. The selected cell and every effective value appear in local
metadata, the remote command, and `soak-config.properties`.

Add:

```text
GSE_SOAK_PROFILE=none|jfr
```

It defaults to `none` and is accepted only in `investigation` mode. Comparative timing
runs always use `none`. A later profile-only target/control pair uses `jfr`; its timing
must not be combined with unprofiled evidence.

All existing duration, document-count, corpus, top-K, JVM, image, machine, and network
overrides retain their current validation. Investigation mode derives the same
`soak_seconds + 7200` maximum VM duration used by `soak`.

## Java workload contract

Extend the JMH-only `V3ProductionSoak` command with exact, strictly validated values:

```text
--update-mode=none|stable|revision
--per-query-metrics=true|false
```

Default values preserve the existing soak: `revision` and `false`. Java-side boolean
parsing must reject values other than lowercase `true` or `false` rather than silently
mapping an unknown value to false.

`writers=0` is legal only with `update-mode=none`. A positive writer count is illegal
with `none`, and `stable` or `revision` requires at least one writer. Investigation mode
further freezes mutation cells to one writer. Readers, duration, sample interval,
documents, and top K remain positive.

Reader workers retain the deterministic four-query rotation in canonical order:
`TEXT`, `BOOL`, `PHRASE`, `FUZZY`. Per-query measurement must not change request
construction, scoring, limits, or validation. Each completed search records its query
kind, elapsed nanoseconds, and operation count after result-limit validation.

## Corpus and snapshot identity

Investigation runs record `initial_snapshot_version` and `final_snapshot_version`.

- `read-only` requires zero writes, zero index cycles, and an unchanged snapshot
  version;
- `stable-update` requires positive writes, an advancing snapshot version, and unchanged
  corpus content;
- `revision-update` requires positive writes, an advancing snapshot version, and changed
  corpus content.

Corpus identity is SHA-256 over every active document in ascending business-ID order.
Each record encodes `id`, `category`, `popularity`, `title`, `body`, `tags`, and `summary`
in that order. Integral values use fixed-width big-endian bytes. Each UTF-8 string is
preceded by its four-byte big-endian byte length. Missing IDs are a hard failure. The
initial and final digests are written to the summary as lowercase hexadecimal along with
`corpus_changed=true|false`.

Digest computation occurs outside the timed interval: once after fixture creation and
once after all workers have joined. Its cost is evidence-generation overhead and must
not enter throughput or latency measurements.

## Per-query evidence

When per-query metrics are enabled, write
`soak-query-samples.csv` alongside the existing evidence. Its exact header is:

```text
timestamp,elapsed_s,text_ops,text_latency_ns,bool_ops,bool_latency_ns,phrase_ops,phrase_latency_ns,fuzzy_ops,fuzzy_latency_ns
```

Operation and latency fields are cumulative unsigned counters. The sampler writes this
row from the same sampling loop and elapsed-time observation as `soak-samples.csv`.
Per-query cumulative latency is the sum of completed operation latency, not wall-clock
worker time. Sampling concurrent counters is approximate; monotonicity is required but
cross-column transactional equality is not claimed for intermediate rows.

The summary adds, for each lowercase query prefix `text`, `bool`, `phrase`, and `fuzzy`:

- `*_read_operations` and `*_read_ops_per_second`;
- `*_read_latency_samples`;
- `*_read_latency_p50_us`, `*_read_latency_p95_us`,
  `*_read_latency_p99_us`, and `*_read_latency_max_us`.

Each reader retains one bounded deterministic latency reservoir per query kind. At the
final summary, per-query operation counts sum exactly to total reads. Every kind has a
positive count, and the difference between the largest and smallest kind count is at
most the configured reader count because each worker rotates deterministically.

The existing aggregate sample, summary, latency, heap, GC, queue, correctness, and
lifecycle evidence remains present. Investigation instrumentation overhead is part of
all investigation cells, including the read-only control, but not the existing soak
mode.

## Deterministic investigation analyzer

Add `scripts/analyze-v3-soak-investigation.sh SOAK_DIRECTORY`. It reads the existing
config, samples, summary, base analysis, and the new per-query sample data. It writes a
locale-independent deterministic properties report to standard output without mutating
input.

The production runner captures output to a temporary file and atomically renames it to
`soak/soak-investigation-analysis.properties` before `checksums.sha256` is generated. A
failure leaves no final-name partial report and fails the run.

The analyzer uses the same six elapsed-time buckets and bucket-two versus bucket-six
steady comparison as the base analyzer. For each query and bucket it emits:

- operation rate from cumulative operation deltas;
- mean latency in microseconds from cumulative latency/count deltas;
- sample coverage and first/last elapsed time.

For each query it also emits early-to-late rate drift and mean-latency drift. A rate
decline of at least ten percent and a mean-latency increase of at least ten percent are
recorded as separate review flags. These flags prioritize investigation; they are not
SLAs and do not fail structurally valid evidence.

The schema begins with:

```text
analysis_version=1
analysis_status=VALID
investigation_cell=...
review_required=...
```

Keys use stable query and bucket order, contain no generated timestamp, and produce
byte-identical output for identical input.

Hard validation rejects:

- missing, duplicate, non-finite, negative, or malformed properties and counters;
- an unexpected CSV header or row width;
- non-monotonic elapsed time, operation count, or cumulative latency;
- insufficient duration or sample coverage under the existing 95-percent rule;
- final per-query counts that do not sum to total reads;
- unbalanced query rotation beyond the reader-count bound;
- cell/writer/update/lifecycle combinations that violate this contract;
- corpus or snapshot behavior inconsistent with the selected cell;
- a base analysis that is missing or not structurally valid.

The base analyzer is extended only as required to support a valid zero-writer read-only
run. For that cell, write operations and write latency samples must be zero, snapshot
version must remain unchanged, write drift is emitted as zero, and write review flags
remain false. For every existing positive-writer fixture and retained historical run,
base analysis behavior remains unchanged.

## Bounded JFR evidence

JFR is a profile-only follow-up, never part of the unprofiled comparison matrix. When
`GSE_SOAK_PROFILE=jfr`, the runner pre-creates the soak output directory and starts the
built-in JDK recorder with `settings=profile`, disk storage, dump-on-exit, and a 512 MiB
maximum recording size. It writes:

- `soak/profile.jfr`;
- `soak/profile-summary.txt` from the same JDK's `jfr summary` command;
- the exact Java and JFR command lines in metadata.

The run fails if the recording is missing or empty or `jfr summary` cannot parse it.
Both files are included in the run checksum manifest. Profiling uses no downloaded
agent, privileged VM setting, or product instrumentation.

The report may use execution and object-allocation samples to identify candidate code
paths, but it must record sampling limitations. Profiled rates cannot be compared
numerically with the unprofiled baseline.

## Cloud experiment

The initial unprofiled screening uses one fresh VM for each cell in this order:

1. `revision-update`;
2. `read-only`;
3. `stable-update`.

Every cell freezes:

- one exact clean pushed commit;
- Standard `c3d-standard-30` in `us-west4-a`;
- exact `ubuntu-2404-noble-amd64-v20260826` image and recorded JDK package;
- `-Xms8g -Xmx16g`;
- 600 seconds, one-second samples, 100,000 documents, 16 readers;
- top K 10, `zipf-en-medium-4`, lifecycle disabled, and profiling disabled;
- one independent ephemeral VM with no overlap and verified cleanup.

The primary outcomes are aggregate and per-query bucket-two-to-bucket-six read-rate
drift. Per-query mean-latency drift, whole-run latency, throughput, heap, GC, and queue
evidence are secondary outcomes.

Interpret the cells as follows:

| Observation | Supported next hypothesis |
|---|---|
| Similar drift in all three | Static search/runtime or another shared time effect |
| `stable-update` and `revision-update` drift, `read-only` does not | Mutation/snapshot accumulation independent of content |
| `revision-update` drifts materially more than `stable-update` | Corpus revision, selectivity, or content-dependent index state |
| Only one query kind separates cells | That query pipeline becomes the bounded investigation target |

A single run never establishes attribution. Select the strongest relevant contrast and
bring both cells to three independent Standard runs, reversing order between rounds. If
the first screening shows no meaningful separation, the default maximum contrast is
`revision-update` versus `read-only`.

For this phase, a differentiating factor is supported only when:

1. the drift contrast has the same direction in all three rounds;
2. the absolute difference between group mean drift is at least three percentage
   points; and
3. that difference is at least twice the larger group sample standard deviation.

Apply the rule to aggregate drift and independently to each query kind. Secondary
metrics may explain a supported primary contrast but cannot establish one alone.

If no contrast passes, close the phase as inconclusive without JFR or engine changes.
If a contrast passes, run both selected cells for 1,800 seconds, reversing their most
recent order. The same contrast must remain directionally consistent. Then run one
separate 600-second JFR target/control pair solely to collect candidate CPU and
allocation paths. Do not reuse profiled throughput as confirmation evidence.

## Completion gates

Implementation is ready for paid execution only after all of the following pass:

- shell syntax checks for every changed script;
- Java unit tests for strict argument and cell compatibility validation;
- deterministic per-query counter, reservoir, corpus-digest, and snapshot assertions;
- analyzer fixtures for all three cells, per-query drift, malformed data, counter
  regression, unbalanced queries, digest mismatch, and zero-writer behavior;
- proof that existing default soak behavior and historical analysis remain compatible;
- fake-gcloud propagation, dry-run, invalid-cell, conflicting-variable, profile, failure,
  collection, checksum, and cleanup tests;
- Maven reactor tests and the existing cloud no-GCP suite;
- one no-cost reduced local run of each cell with analysis included in checksums;
- three paid-cell dry runs showing exact frozen controls and no mutation;
- manual sequential execution and review of the initial three paid screening cells.

The phase closes with a report referencing every retained run, group statistics,
per-query contrasts, corpus/snapshot evidence, uncertainty, and any JFR limitations. It
must explicitly choose one outcome: inconclusive without product work, a narrower
benchmark experiment, or a separately contracted engine investigation. No product fix
belongs to this branch.
