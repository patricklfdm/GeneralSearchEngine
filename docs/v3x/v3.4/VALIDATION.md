# V3.4 validation contract

## Validation order

V3.4 follows an evidence-before-change order:

1. freeze this contract on published `3.3.0`;
2. establish seven-baseline compatibility and exact-V3.3 reference fixtures;
3. validate every new benchmark/probe against deterministic reduced fixtures;
4. capture local construction, extreme-corpus, heap, burst, and long-run calibration;
5. implement and fake-test the separate cloud lane;
6. perform paid experiment/canonical execution only after dry-run review; and
7. repeat release, remote publication, and post-publication proof on final `3.4.0`.

Phase 0 provisions no cloud resource and changes no implementation.

## Existing correctness suite remains mandatory

Every phase retains all focused, randomized, differential, mutation, index-lifecycle,
concurrency, retention, compatibility, consumer, Javadoc, artifact, reproducibility,
JMH smoke, and Cloud Benchmark local tests already required by V3.3.

New evidence must exercise, without redefining:

- equality/range/prefix/boolean structured queries;
- V2 ranked terms and filters;
- V3 TEXT, exact/sloppy PHRASE, FUZZY, nested BOOL/BOOST, and Explain;
- V3.2 offset analysis and structured highlighting;
- V3.3 disabled/exact page results, cursor continuation, and staleness;
- add/update/remove and atomic bulk mutation;
- structured/text dynamic index create/replay/drop; and
- admission, close, failure recovery, and metrics consistency.

## Benchmark validation rules

Every benchmark or probe has a reduced deterministic test that proves:

- requested parameters actually change the intended workload;
- operation counts and checksums are non-zero and stable;
- timed regions include and exclude exactly the documented work;
- corpus generation is deterministic for its seed and schema;
- failure paths cannot be reported as successful measurements;
- cleanup and final oracles execute even after bounded failure; and
- benchmark-only instrumentation does not alter production semantics.

JMH packaging is insufficient by itself; retained forked smoke cells must launch and
execute the new harnesses.

## Cold construction validation

Focused tests prove each process checkpoint is emitted once and in order. They verify
document count, canonical fields, initial indexes, text statistics, first-query
checksum, dynamic-index replay result, and final engine closure.

The process runner distinguishes timeout, non-zero exit, missing checkpoint, invalid
checksum, resource exhaustion, and harness error. No timed-out or partially initialized
process contributes a successful duration.

## Extreme-corpus validation

For every generator axis, a small exhaustive oracle and a larger randomized oracle
compare query truth, raw score bits, canonical order, Explain, highlight ranges, page
walks, and exact totals where applicable. Unicode fixtures retain original Java string
and half-open UTF-16 boundaries.

Boundary tests cover empty text, repeated terms, same-position alternatives, large
position gaps, large term frequency, long strings, vocabulary extremes, multiple
fields, and overflow rejection. Resource caps prevent an invalid generator parameter
from exhausting the host before validation.

## Burst and recovery validation

Controlled barriers separate submission, writer processing, reader observation, burst
end, and drainage. Tests verify:

- all accepted futures terminate;
- duplicate/missing/invalid operations retain existing explicit failures;
- successful batches publish atomically and failed batches do not publish;
- readers see complete immutable snapshots;
- dynamic-index builds and mutation bursts preserve replay/publication semantics;
- queue and writer progress telemetry is internally consistent; and
- the final document/index/query oracle matches the submitted successful history.

Producer threads are bounded and joined. A harness deadlock has a timeout and diagnostic
dump and is a hard failure.

## Heap validation

Heap probes record the JVM/collector/options and reject swapping or insufficient
physical-memory conditions when they would invalidate interpretation. Live-set methods
are calibrated on empty, loaded, and released controls.

Retained-object inspection checks that benchmark samplers, cursors, results, completed
futures, producer tasks, and dynamic-index fixtures are released at the documented
checkpoint. The probe does not require a universal byte threshold before calibration,
but unexplained growth or a retained production graph fails review.

## Long-run validation

Reduced tests validate window rotation, warmup exclusion, steady and burst schedules,
checkpoint oracles, queue telemetry, GC/heap sampling, p50/p95/p99 aggregation,
throughput, snapshot/publication counters, error capture, shutdown, and artifacts.

The required two-hour run passes only when:

- the process and every required workload window complete;
- no unexpected error, timeout, checksum, or semantic mismatch occurs;
- writer progress and queue drainage are proved;
- final futures, engine state, and query/index oracles agree;
- every required raw window and environment fact is present; and
- upload/retention and cleanup evidence are complete.

An interrupted or partial run remains diagnosable but is not accepted.

## Cloud lifecycle validation

Before paid execution, unit, shell, synthetic, and fake-gcloud suites cover:

- the `final-v34` experiment and canonical input matrices;
- mode/suite/preset/duration/cap propagation;
- plan-before-provision rejection;
- Standard/GCS canonical enforcement;
- slot failure, upload failure, timeout, cancellation, partial state, resume/replace,
  and cleanup;
- exact environment and source comparability;
- eligible/ineligible aggregation and immutable registration; and
- unchanged behavior for every existing mode and preset.

The dry run is reviewed for machine count, maximum duration, worst-case resource cost,
retention, and cleanup before the user starts a paid job.

## Release validation

Final `3.4.0` requires:

- core and reactor clean verification;
- V3.4 zero-addition fixture and fresh-isolated seven-baseline Japicmp;
- V1/V2/V3 consumers and travel example;
- strict core/processor Javadocs and six expected release JARs;
- processor service-entry isolation;
- two byte-identical clean release builds;
- retained JMH and hardening smoke gates;
- reviewed two-hour and canonical evidence tied to final source identity;
- signed tag on exact protected-master commit;
- Maven Central publication and clean remote verification; and
- successful production deployment, GitHub Release, and post-publication evidence.

No local same-coordinate artifact may satisfy a published-baseline or remote-release
gate.

