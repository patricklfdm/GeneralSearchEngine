# V3.4 hardening and V4 handoff contract

## Purpose

V3.4 closes the purely in-memory V3.x line with evidence that later durability work
can use as an explicit comparison point. It does not attempt to predict or pre-build
V4 persistence structures.

The handoff is complete only when one signed V3.4 source identity has a reviewed
correctness, compatibility, capacity, construction, concurrency, long-run, artifact,
and cloud evidence package. A document saying that a test should eventually run is not
handoff evidence.

## Frozen decisions

| Decision | V3.4 rule |
|---|---|
| Release identity | use minor line `3.4.0`; do not hide the final evidence family inside a `3.3.x` patch |
| Product scope | no new search feature, public API, or durability behavior |
| Production changes | none by default; a reproducible release blocker requires a contract amendment before a narrow fix |
| Required long run | one controlled two-hour Standard/GCS experiment on final source identity, separate from 30-minute canonical members |
| Longer runs | 6h/12h/24h are non-blocking investigations until durable orchestration is separately contracted |
| Final cloud family | new `v3.4-final-in-memory-v1` preset and independent `v3.4.0-in-memory-cloud` baseline family |
| Historical cloud families | `v3.0.0-cloud` and `v3.1.0-ranked-cloud` remain immutable and are never relabeled as V3.4 evidence |
| Cross-hardware evidence | optional and isolated by environment fingerprint and baseline family |
| V4 start | only after V3.4 publication and post-publication evidence close the gates below |

## Required handoff package

### Search and API contract

- all published V1, V2, V3.0, V3.1, V3.2, and V3.3 behavior remains accepted;
- V3.4 publishes no supported API addition;
- ordinary, ranked, highlighted, paged, exact-total, and Explain results retain their
  frozen truth, score, order, failure, lifecycle, and snapshot behavior; and
- the final public artifact passes seven-baseline compatibility and independent
  consumers.

### Runtime and memory contract

- mixed readers and one writer retain snapshot consistency;
- concurrent producers do not become concurrent internal writers;
- every accepted mutation completes successfully or with the existing explicit
  failure, and the queue drains after bounded bursts;
- no benchmark-only cursor, probe, sampler, or evidence recorder becomes an engine
  registry or retained production graph; and
- heap and GC claims identify exact JVM, collector, heap, workload, and measurement
  method.

### Construction contract

- cold-process startup and ready-to-search boundaries are explicitly measured;
- initial load, structured index, text index, and dynamic-index construction are
  distinguished rather than merged into one unexplained duration;
- input counts, bytes/characters, vocabulary, positions, indexes, and field shapes are
  recorded; and
- failures or timeouts produce diagnosable partial evidence without being accepted as
  successful baseline members.

### Evidence and operations contract

- the final canonical set uses a fixed reference machine, image, Java runtime, JVM
  options, suite, preset, source commit, and at least three independent Standard slots;
- median, variation, individual members, exclusions, and comparison eligibility are
  preserved;
- canonical evidence uses durable GCS retention and mandatory cleanup; and
- the signed release tag, Central artifacts, GitHub Release, production deployment,
  final baseline registration, and documentation all resolve to reviewed identities.

## V4 entry gates

V4 durability implementation may begin only after all of these are true:

- [x] V3.4 Phase 0 contracts are accepted on protected `master`.
- [x] Exact published `3.3.0` is frozen as the seventh compatibility and behavioral
  input baseline.
- [ ] Cold construction, extreme-corpus, heap, and producer-burst local evidence pass.
- [ ] The required two-hour run passes correctness, liveness, queue, and evidence
  integrity gates.
- [ ] A three-or-more-member `final-v34` Standard canonical set is reviewed and
  registered as `v3.4.0-in-memory-cloud`.
- [ ] Any admitted production fix has its own amendment, regression proof, and
  regenerated affected evidence.
- [ ] Final V1/V2/V3 consumers, seven-baseline Japicmp, strict Javadocs, six release
  JARs, service boundaries, and reproducibility pass.
- [ ] Signed `v3.4.0`, Maven Central publication, clean remote verification,
  production deployment, GitHub Release, and post-publication documentation complete.

## What V4 may assume

After the gates pass, V4 may treat the published V3.4 behavior and artifacts as the
frozen in-memory reference. V4 performance reports may compare with V3.4 only when
workload and environment compatibility are stated; persistence overhead must not be
hidden by aggregating unrelated cells.

V4 may not reinterpret V3.4 snapshot, mutation-completion, query, ranking, pagination,
or failure semantics merely because durable state is introduced. Any intentional
change requires a V4 contract and migration policy.

## What does not block V4

The following are not V3.4 or V4 entry blockers unless later evidence elevates them:

- a 6h, 12h, or 24h soak;
- AWS or local-Intel comparison runs;
- universal numeric latency or allocation thresholds;
- a performance optimization with no correctness/liveness necessity;
- new search, analysis, aggregation, timeout, or prepared-query features; and
- parity between in-memory startup and future persisted reopen time.
