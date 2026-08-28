# V3 cloud soak early-window stabilization contract

Status: frozen before implementation on 2026-08-28.

## Trigger and objective

The completed [root-cause investigation results](CLOUD_SOAK_ROOT_CAUSE_RESULTS.md)
contain a directional but statistically unsupported revision-versus-stable contrast.
All three `revision-update` runs declined by approximately six percent. The first two
`stable-update` runs were flat, while the third began with a low bucket-two read rate
and recovered by 9.760% by bucket six. That valid run increased the stable group's
sample standard deviation enough that no aggregate or per-query contrast passed the
pre-registered rule.

This phase tests one narrower hypothesis: the measured interval starts before the
search runtime and VM have reached a sufficiently stable operating state. It adds an
explicit read-only stabilization phase and jointly evaluates within-run drift and
absolute measured throughput. It does not investigate or optimize the engine.

The phase must answer two questions without post-hoc exclusions:

1. can a fixed, independently validated read-only prelude eliminate the observed early-
   window variability before mutation begins;
2. after that prelude, does `revision-update` still differ reproducibly from
   `stable-update` in both time trajectory and absolute read rate?

## Scope and non-goals

This phase may change only `src/jmh`, benchmark orchestration and analysis scripts,
their tests, CI wiring, and documentation. It must not change `src/main`, public API,
query truth, scoring, result ordering, mutation semantics, snapshot publication,
index implementation, release coordinates, or existing benchmark defaults.

The stabilization prelude is experimental control, not an attempt to hide startup
cost. Load time, stabilization time, readiness evidence, handoff time, and measured
time remain separate and visible. A stabilized result is not comparable to an existing
unstabilized throughput baseline without an explicit label.

No result may be excluded because its score is inconvenient. A run is scientifically
invalid only when it violates a frozen configuration, evidence, correctness,
readiness, environment, checksum, collection, or cleanup condition defined here.
Infrastructure-invalid and readiness-failed runs remain retained evidence.

Existing `quick`, `full`, `concurrency`, `soak`, `investigation`, and `all` behavior,
arguments, files, and analysis remain unchanged. Historical results must remain
analyzable byte-for-byte. Raw generated evidence remains ignored by Git.

## Dedicated stabilized mode

Add `stabilized-investigation` to the local production runner and cloud orchestrator.
It runs only the production soak and requires:

```text
GSE_SOAK_INVESTIGATION_CELL=read-only|stable-update|revision-update
GSE_SOAK_STABILIZATION_PURPOSE=screening|confirmation|profile|reduced-test
```

The mode retains the existing investigation cell mappings:

| Cell | Measurement readers | Measurement writers | Update mode | Index cycles |
|---|---:|---:|---|---:|
| `read-only` | 16 | 0 | `none` | false |
| `stable-update` | 16 | 1 | `stable` | false |
| `revision-update` | 16 | 1 | `revision` | false |

Before every measurement cell, stabilization always uses 16 readers, zero writers,
the same four-query rotation, the same fixture, and no index lifecycle work. The
selected measurement writer and update mode do not begin until stabilization passes.

Add:

```text
GSE_SOAK_STABILIZATION_SECONDS=300
GSE_SOAK_STABILIZATION_WINDOW_SECONDS=60
```

Purpose derives and freezes the effective configuration:

| Purpose | Allowed cells | Stabilization | Measurement | Profile | Cloud |
|---|---|---:|---:|---|---:|
| `screening` | stable, revision | 300 s / 60 s windows | 600 s | none | yes |
| `confirmation` | stable, revision | 300 s / 60 s windows | 1,800 s | none | yes, only after joint support |
| `profile` | stable, revision | 300 s / 60 s windows | 600 s | jfr | yes, only after confirmation |
| `reduced-test` | read-only, stable, revision | five configurable windows | configurable | none or jfr | no |

The table uses the full cell names `stable-update` and `revision-update`. Production
purposes accept no duration or profile override that conflicts with their row. For
`reduced-test`, stabilization and window durations must be positive integers, the
window must be at least two seconds, stabilization must equal exactly five windows, and
measurement must be at least 12 seconds. The local runner derives the Java reduced-test
flag. The cloud orchestrator always rejects `reduced-test` before any GCP call. Reduced
output is diagnostic and cannot satisfy a paid gate.

The existing `GSE_SOAK_SECONDS` remains the measured duration and must be absent or
equal the purpose-derived value. Cloud maximum duration is stabilization seconds plus
measured seconds plus the existing 7,200-second recovery allowance: 8,100 seconds for
screening/profile and 9,300 seconds for confirmation.

`GSE_SOAK_PROFILE=none|jfr` remains accepted only in an investigation mode and must be
absent or equal the purpose-derived value. A later authorized `profile` purpose uses
measurement-only recording as defined below.

Missing cells, unknown values, conflicting writer or lifecycle overrides, an invalid
purpose or stabilization/window pair, a reduced-test purpose in cloud, or a duration or
profile conflict fail with configuration exit code 2 before a result directory or VM
is created. Every effective value appears in local metadata, the remote command,
`soak-config.properties`, and the orchestration record.

## Java phase state machine

Extend the JMH-only workload with exact, strictly validated arguments:

```text
--stabilization-purpose=none|screening|confirmation|profile|reduced-test
--stabilization-seconds=N
--stabilization-window-seconds=60
--allow-reduced-stabilization-test=true|false
--jfr-output=PATH
```

Defaults preserve existing behavior: purpose is `none`, stabilization is zero, the
reduced-test flag is false, and JFR output is absent. The runner passes true only for
`reduced-test`; Java requires those values to agree. `profile` requires a JFR output,
production non-profile purposes forbid it, and a reduced test permits it only for the
bounded JFR probe. Only lowercase `true` and `false` are accepted. A positive
stabilization duration requires a non-`none` purpose, per-query metrics, disabled index
cycles, and at most one measurement writer. Purpose, duration, and profile compatibility
is validated again in Java rather than trusting the shell runner.

The stabilized state machine is:

```text
LOAD_FIXTURE
  -> CAPTURE_LOADED_IDENTITY
  -> STABILIZE_READ_ONLY
  -> CAPTURE_POST_STABILIZATION_IDENTITY
  -> EVALUATE_READINESS
  -> MEASURE_SELECTED_CELL
  -> CAPTURE_FINAL_IDENTITY
  -> COMPLETE
```

If readiness fails, the state transitions to `NOT_READY`; no measurement worker starts
and no measured result is reported as passing. Any worker, correctness, identity, or
evidence failure transitions to `FAILED`.

## Read-only stabilization phase

Stabilization uses the already-loaded measurement fixture. It starts the configured
reader workers with the canonical deterministic rotation `TEXT`, `BOOL`, `PHRASE`,
`FUZZY`. It starts no writer and no lifecycle worker. Request construction, validation,
scoring, limits, and result consumption are identical to measured investigation reads.

Using the same fixture intentionally warms JVM compilation, query plans, engine read
paths, allocator behavior, and the VM CPU while leaving content and snapshot identity
unchanged. A separate training fixture is forbidden because it would not prove that the
measurement fixture itself was exercised. A mutation prelude is forbidden because it
would change the starting state of the revision cell.

The prelude has its own counters and latency reservoirs. They are never reused by the
measurement phase. After stabilization readers join, the workload verifies:

- zero writes and zero index cycles;
- no errors and unchanged document count;
- unchanged loaded and post-stabilization snapshot version;
- unchanged canonical corpus SHA-256;
- positive per-query operation counts whose maximum-minus-minimum difference is at most
  the configured reader count.

It then evaluates readiness and, if ready, creates fresh measurement counters,
reservoirs, workers, deadline, GC baselines, and elapsed-time origin. Stabilization
operations and time do not enter measured rates, latency percentiles, buckets, or drift.

Post-stabilization digest and readiness computation occur outside both phases. Record
`stabilization_handoff_seconds` from the final stabilization sample to the first
measurement sample. The paid run requires handoff at most 30 seconds. No intentional
sleep, explicit full GC, class-data reset, cache clear, or fixture rebuild is allowed
at the handoff.

## Stabilization evidence

Write `soak-stabilization-samples.csv` with the exact header:

```text
timestamp,elapsed_s,used_heap_bytes,committed_heap_bytes,max_heap_bytes,read_ops,read_latency_ns,text_ops,text_latency_ns,bool_ops,bool_latency_ns,phrase_ops,phrase_latency_ns,fuzzy_ops,fuzzy_latency_ns,errors,snapshot_version,document_count,gc_count,gc_time_ms
```

Operation and latency values are cumulative unsigned counters. Per-query latency is the
sum of completed search latency. Rows use the same timestamp and elapsed observation
for every field, are written at the configured one-second interval, and include a final
row after the stop signal.

Write `soak-stabilization-summary.properties` containing at least:

- configured and observed stabilization duration;
- total and per-query operations, rates, latency samples, p50/p95/p99/max;
- loaded and post-stabilization snapshot versions and corpus digests;
- document count, errors, GC count/time deltas, and final state;
- readiness status and every individual readiness flag;
- handoff duration when measurement starts.

The existing measured `soak-samples.csv`, `soak-query-samples.csv`, summary, base
analysis, and investigation analysis retain their schemas and begin from fresh counters
at measured elapsed time zero. Additive config and metadata properties may identify the
stabilization phase without changing historical parsers.

## Frozen readiness gate

The paid 300-second prelude is divided into five fixed 60-second elapsed-time windows.
The first two windows are warmup evidence and are not used for readiness. Windows three,
four, and five form the readiness band. Window rates and mean latency use cumulative
deltas between the first and last sample assigned to that window.

Window assignment is `min(floor(elapsed / window_seconds) + 1, 5)`. Thus paid windows
are `[0,60)`, `[60,120)`, `[120,180)`, `[180,240)`, and `[240,300]`; the final boundary
sample belongs to window five. The same formula applies to reduced tests.

For the aggregate and independently for TEXT, BOOL, PHRASE, and FUZZY, readiness
requires:

- at least 95% expected sample coverage overall and at least two samples per window;
- positive operation delta and elapsed coverage in every readiness window;
- operation-rate range divided by the three-window mean no greater than 5%;
- mean-latency range divided by the three-window mean no greater than 10%;
- no counter or elapsed-time regression;
- positive, finite computed rates and latency.

Readiness also requires all phase identity and correctness conditions above. Every
condition is conjunctive. Threshold equality passes. Rounding is only for report
formatting; decisions use unrounded double arithmetic.

Add `scripts/analyze-v3-soak-stabilization.sh SOAK_DIRECTORY`. It independently
recomputes the readiness decision from raw evidence, validates the Java summary, and
writes a locale-independent deterministic report to standard output. The runner
captures it atomically as `soak/soak-stabilization-analysis.properties`. Java and shell
decisions must agree exactly. A disagreement or malformed evidence fails the run.

The production runner captures the Java exit code instead of exiting immediately. If
stabilization evidence exists, it always runs the independent analyzer and atomically
publishes its report before returning the appropriate success or failure status. This
ensures a Java `NOT_READY` result is collected and checksummed without allowing the
measurement phase to start.

The report starts with:

```text
analysis_version=1
analysis_status=VALID
stabilization_status=READY
measurement_started=true
review_required=...
```

A Java `NOT_READY` result is valid retained diagnostic evidence but not a passing
comparison run. Its independent report uses `stabilization_status=NOT_READY` and
`measurement_started=false`; the cloud orchestrator collects it before cleanup.

## Measured absolute-rate evidence

For the aggregate and each query kind, the measured whole-run operation rate from the
existing summary is the absolute-rate outcome. The existing bucket-two-to-bucket-six
rate drift remains the trajectory outcome. Mean-latency drift, percentiles, heap, GC,
queue, snapshot, write rate, and handoff duration are secondary diagnostics.

The measurement summary additionally records GC count and time as deltas from
measurement start so stabilization GC does not enter measured GC evidence. Existing
absolute JVM GC properties remain available under their historical keys for
compatibility.

Absolute rates from stabilized runs must never be mixed with unstabilized historical
rates. They remain specific to the exact corpus, cell, VM, JDK, heap, reader count,
writer count, and stabilization policy.

## Deterministic paired comparison

Add:

```text
scripts/compare-v3-soak-stabilized.sh \
  REVISION_1 STABLE_1 REVISION_2 STABLE_2 REVISION_3 STABLE_3
```

Each argument is a complete result directory. The script validates unique runs,
identical commit and frozen environment, ready stabilization evidence, correct cell and
identity behavior, successful checksums, and three explicit paired rounds. Result start
times must prove the frozen alternating execution order even though arguments are
grouped semantically as revision then stable. It writes a deterministic properties
report without modifying any run.

For aggregate, TEXT, BOOL, PHRASE, and FUZZY, it reports group values, mean, sample
standard deviation, paired directions, contrasts, thresholds, and decisions for both:

1. bucket-two-to-bucket-six measured read-rate drift;
2. measured whole-run absolute read operations per second.

Means are arithmetic means. Sample standard deviation uses denominator `n - 1` with
`n = 3`. Decisions use unrounded values; threshold equality passes.

The drift gate is unchanged from the prior contract:

- paired revision-minus-stable drift contrast has one non-zero direction in all three
  rounds;
- absolute group mean drift difference is at least three percentage points;
- the difference is at least twice the larger drift sample standard deviation.

The absolute-rate gate requires:

- paired revision-minus-stable rate difference has one non-zero direction in all three
  rounds;
- absolute group mean rate difference is at least 3% of the stable control mean;
- the absolute rate difference is at least twice the larger rate sample standard
  deviation;
- rate-contrast direction agrees with drift-contrast direction.

A metric is `joint_supported=true` only when both gates pass. A differentiating factor
is supported only when aggregate is jointly supported and at least one query kind is
jointly supported in the same direction. Secondary metrics cannot override this rule.

## Cloud experiment and stopping rules

Implementation is validated without cloud resources first. Paid execution then uses
three paired rounds in this frozen order, reversing the previous experiment's final
order:

| Round | First | Second |
|---|---|---|
| 1 | `stable-update` | `revision-update` |
| 2 | `revision-update` | `stable-update` |
| 3 | `stable-update` | `revision-update` |

Every paid run freezes:

- one exact clean pushed commit;
- Standard `c3d-standard-30` in `us-west4-a`;
- exact image `ubuntu-2404-noble-amd64-v20260826`;
- the recorded OpenJDK 21 package;
- `-Xms8g -Xmx16g`;
- 300-second stabilization and 600-second measurement;
- 100,000 documents, 16 readers, one measurement writer;
- top K 10, `zipf-en-medium-4`, one-second samples;
- lifecycle and profiling disabled;
- one fresh ephemeral VM per run with no overlap and verified cleanup.

All six matrix commands use `GSE_SOAK_STABILIZATION_PURPOSE=screening`. Confirmation
and profile purposes are configuration-invalid for this matrix even though their runner
paths exist for later contract-authorized stages.

Runs are sequential. If a run is `NOT_READY`, stop paid execution and close the phase
as stabilization not demonstrated; do not retry readiness on another VM. An
infrastructure-invalid run caused by provisioning, SSH, collection, checksum, or
cleanup failure is retained and may be repeated once in the same matrix slot without
examining benchmark scores. Any configuration or scientific-validity failure stops the
matrix pending a new contract.

After six ready runs, generate the deterministic paired comparison exactly once. If the
joint support rule fails, close as inconclusive without JFR or product work. Do not add
runs to reduce an inconvenient standard deviation.

If joint support passes, run one `confirmation` purpose for each cell, reversing the
most recent order. Both drift and absolute-rate contrasts must retain their supported
direction. Failure closes the phase without JFR or product work.

Only after confirmation may one separate `profile` purpose target/control pair run.
Its rates are profile-only and never enter comparison statistics.

## Measurement-only JFR

In stabilized `profile` purpose, JFR must not start at JVM startup. The benchmark-only Java workload
starts the built-in JDK recording after stabilization is READY and immediately before
measurement workers are released. It stops after measurement workers join and writes
`soak/profile.jfr`. Use JDK `profile` settings, disk storage, dump-on-exit, and a 512 MiB
maximum size. The runner writes `soak/profile-summary.txt` with the same JDK's
`jfr summary` command.

Metadata records the exact Java command, JFR configuration, recording start/stop phase,
and summary command. Missing, empty, startup-inclusive, or unparsable recording evidence
fails the profile run. Both files enter the checksum manifest. No downloaded agent,
privileged VM setting, or product instrumentation is allowed.

JFR samples may identify candidate execution and allocation paths only. Profiled rates
cannot confirm a contrast, and sampling evidence cannot by itself authorize an engine
change.

## No-cost implementation gates

Implementation is ready for paid execution only after all of the following pass:

- shell syntax checks for every changed script;
- Java unit tests for phase transitions, defaults, strict arguments, and cell mapping;
- deterministic stabilization counters, latency reservoirs, identity, counter reset,
  GC delta, readiness, and handoff assertions;
- analyzer fixtures for READY and every NOT_READY condition, malformed data, missing
  windows, counter regression, digest mismatch, and Java/shell decision disagreement;
- paired-comparison fixtures for pass, threshold equality, direction disagreement,
  insufficient effect, excessive SD, duplicate run, and environment mismatch;
- proof that all existing modes and historical analyzers remain compatible;
- fake-gcloud propagation, dry-run, fail-fast, collection, checksum, interruption, and
  cleanup tests without a GCP API mutation;
- reduced local READY runs for `stable-update` and `revision-update` with analysis in
  checksums;
- a deterministic Java phase-state test proving `NOT_READY` cannot start measurement,
  plus a runner fixture proving its evidence is analyzed, retained, and checksummed;
- a reduced measurement-only JFR probe;
- Maven reactor tests and the existing no-GCP CI suite;
- six paid-cell dry runs showing the exact matrix controls and no mutation.

CI must not authenticate to GCP, provision a VM, or depend on retained local raw
evidence. Existing default soak execution must allocate no stabilization counters,
reservoirs, samples, analyzers, or JFR objects.

## Completion and reporting

The phase closes with a committed results report referencing every retained run and the
comparison report. It records stabilization readiness, handoff, absolute rates, drift,
sample standard deviations, paired directions, identity behavior, uncertainty, and any
JFR limitations.

The report must choose exactly one outcome:

1. stabilization not demonstrated;
2. inconclusive without JFR or product work;
3. jointly supported factor requiring a separately contracted engine investigation.

Even a jointly supported factor does not authorize a product fix in this branch. No
engine implementation belongs to this phase.
