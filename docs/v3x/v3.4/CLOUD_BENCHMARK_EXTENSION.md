# V3.4 final in-memory Cloud Benchmark extension contract

## Purpose and non-activation

This contract reserves a separate V3.4 cloud evidence lane. Phase 0 does not change
the protected workflow, runner, analyzer, uploader, preset registry, GCS state, VM, or
paid resource. Implementation begins only after this document and the Phase 0
checklist merge to protected `master`.

The extension answers one question:

> Does the final in-memory V3.4 candidate remain correct, live, bounded, and
> reproducible under the frozen hardening workload on the reference machine?

It is not a replacement for the frozen V3.0 regression or V3.1 ranked feature lanes.

## Immutable identifiers

| Field | V3.4 value |
|---|---|
| Workflow mode | `final-v34` |
| Suite | `v3.4-final-in-memory-suite-v1` |
| Canonical preset | `v3.4-final-in-memory-v1` |
| Accepted baseline registration | `v3.4.0-in-memory-cloud` |
| Primary machine | `c3d-standard-30` |
| Java line | Java 21, exact runtime recorded per set |
| Canonical provisioning | Standard only |
| Canonical retention | GCS only |

Changing a workload, parameter, metric meaning, JVM option, suite schema, or preset
after evidence exists requires a new versioned identifier. Existing
`v3-production-*-v1` and `v3.1-ranked-v1` definitions remain unchanged.

## Profile matrix

| Evidence profile | Mode | Repeats | Provisioning | Retention | Long window |
|---|---|---:|---|---|---|
| `experiment` | `final-v34` | 1 | Spot or Standard | Actions or GCS | `30m` calibration or `2h` investigation |
| `canonical` | `final-v34` | 3 or 5 | Standard | GCS | fixed `30m` window |

Canonical planning selects `v3.4-final-in-memory-v1` automatically. The protected
workflow also resolves that preset for experiments, and every `final-v34` set rejects
a different or missing effective preset. This keeps the two-hour experiment on the
same frozen workload while duration remains a distinct fingerprint field.

The required release-grade two-hour run is specifically a one-repeat Standard
experiment with GCS retention and the V3.4 preset. Duration remains an explicit plan
and benchmark-fingerprint field: the `2h` experiment is not comparable with the `30m`
canonical members and is retained as supplemental long-run evidence.

No `final-v34` result is eligible under `quick`, `full`, `concurrency`, `soak`, `all`,
or `ranked-v31`. Conversely, no existing mode result becomes a V3.4 canonical member.

## Preset-owned workload

The V3.4 preset owns a bounded combination of:

- cold-process and ready-to-search measurement;
- initial structured/text and dynamic-index construction;
- deterministic extreme-corpus ranked and structured query cells;
- controlled multi-producer mutation bursts followed by queue recovery;
- mixed ordinary/ranked/highlighted/page/Explain readers with one writer;
- heap, GC, publication, queue, checksum, and failure telemetry; and
- a long window whose exact duration and operation schedule are present in the plan.

The canonical preset uses one fixed heap and collector. The broader heap matrix remains
diagnostic evidence and is not hidden inside canonical members.

The exact Phase 4 values are published in
[`PHASE_4_BASELINE.md`](PHASE_4_BASELINE.md). Phase 4 must publish the exact corpus sizes, seeds, operation counts, reader/writer
groups, burst schedule, index lifecycle, JMH/process settings, JVM options, timeouts,
and expected metric schema before the first paid canonical run. Calibration may reduce
an unsafe proposed cell, but doing so changes the not-yet-published contract rather
than silently changing a live preset.

## Runtime and cost bounds

Every plan resolves before provisioning:

- slot count and repeat topology;
- maximum VM lifetime per slot;
- worst-case aggregate VM hours and vCPU hours;
- machine and provisioning model;
- storage and artifact retention destination; and
- cleanup/recovery actions.

The initial extension caps a slot at three hours and at most five slots. A canonical
three-member set therefore has a nine-VM-hour worst-case bound before provisioning.
The workflow must reject any plan whose resolved controls exceed the cap.

The user-visible dry run prints the bound and exact plan without creating cloud state.
Paid execution always requires explicit manual dispatch; canonical deployment uses the
existing protected approval boundary where applicable.

## Two-hour and longer soak policy

The V3.4 release requires one controlled two-hour Standard/GCS experiment using the
V3.4 preset. Canonical members retain their fixed 30-minute window. The two-hour result
keeps its experiment profile and one-member identity and is never presented as a
canonical repeat.

Six-, twelve-, and twenty-four-hour targets are rejected by this V1 extension. They
require a later contract covering execution beyond one job window, durable heartbeat,
resume semantics, source/image immutability across resume, partial evidence, repeated
failure precedence, budget, orphan detection, cleanup, and retention. Their absence is
not a V3.4 release blocker.

## Failure, recovery, and cleanup

The workflow preserves the existing Cloud Benchmark V2 plan-first lifecycle. It must:

1. validate all input, preset, duration, provisioning, retention, repository, source,
   and budget rules before cloud mutation;
2. persist an immutable plan and per-slot identity;
3. distinguish provisioning, runner, benchmark, upload, analysis, comparison, and
   cleanup failure;
4. retain raw and partial evidence without admitting an invalid canonical member;
5. support bounded resume/replace only through the existing immutable-plan rules;
6. attempt cleanup after success, failure, cancellation, and timeout; and
7. record cleanup receipts or explicit orphan diagnostics.

An early failed benchmark with successful cleanup remains a failed slot. A successful
benchmark with missing required upload or cleanup evidence is not canonical-eligible.

## Evidence and registration

Canonical eligibility requires exact agreement on source, suite, preset, machine,
image, Java/JVM, workload controls, metric schema, Standard provisioning, retention,
and successful lifecycle state. The report must expose every excluded member and
reason; aggregation cannot discard an inconvenient valid member.

Registration as `v3.4.0-in-memory-cloud` occurs only after:

- at least three eligible members are reviewed;
- the final `3.4.0` source identity is protected and unchanged;
- individual and aggregate manifests are durably retained;
- correctness and evidence-integrity gates pass;
- cleanup is confirmed; and
- the immutable baseline descriptor is reviewed in a protected PR.

Once registered, the family is immutable. V4 comparisons reference it by identity and
may not rewrite its members or preset.

## Required implementation tests

Before paid execution, Phase 4 must add focused tests for:

- accepted experiment/canonical profile matrices;
- automatic canonical preset resolution and mismatch rejection;
- exact mode/suite/preset propagation through plan, remote runner, facts, analysis,
  upload, comparison, and registration;
- three-hour/slot-count/cost-bound validation before provisioning;
- `30m` calibration and `2h` investigation handling;
- rejection of 6h/12h/24h and incompatible existing modes;
- fake-gcloud success, benchmark failure, upload failure, cancellation, timeout,
  resume/replace, partial evidence, and cleanup;
- existing mode and preset definitions remaining unchanged; and
- synthetic eligible/ineligible canonical member aggregation.
