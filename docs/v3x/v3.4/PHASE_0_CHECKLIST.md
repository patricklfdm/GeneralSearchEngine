# V3.4 Phase 0 contract checklist

Status: contract frozen locally on `feat/v3.4-phase0-contract` and pending protected
review. Phase 0 is documentation-only and does not authorize version conversion,
implementation, workflow mutation, paid execution, or baseline registration before
the protected merge and exact-commit CI pass.

## Accepted entry boundary

- [x] V3.3 Phases 0–5 and post-publication evidence are complete.
- [x] Signed `v3.3.0`, Maven Central artifacts, clean remote verification, production
  deployment, and GitHub Release resolve to
  `b399ee999e65ca363e68503720dedd4ddd2b3c2e`.
- [x] Post-publication documentation merged through PR #66 as
  `89b0d2f4e05450858c7aa02524dba4eac148d706`; exact-master
  [CI run 33372074868](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33372074868)
  passed.
- [x] Published `3.3.0` and every earlier coordinate, tag, artifact hash, release
  record, and cloud baseline are immutable.
- [x] Phase 0 starts from that exact clean protected-master documentation merge.

## Frozen scope and architecture

- [x] V3.4 is the `3.4.0` Final In-Memory Hardening line, not a search-feature release.
- [x] Immutable snapshots, structural sharing, lock-free readers, one asynchronous
  writer, and atomic publication remain authoritative.
- [x] No public API, query semantic, score, order, Explain, highlight, page, cursor,
  mutation, index, lifecycle, or failure behavior changes.
- [x] Tests, JMH/process benchmarks, bounded probes, evidence tooling, and one separate
  cloud lane are the default implementation scope.
- [x] Production source changes require a reproducible release blocker and an accepted
  contract amendment before a narrow compatibility-preserving fix.
- [x] Persistence, WAL, checkpoints, recovery, reopen, distributed/vector features,
  and all deferred V3.3 application features remain outside V3.4.

## Frozen hardening evidence

- [x] Cold-process evidence separates engine construction, corpus generation/load,
  initial structured/text indexes, ready checkpoint, first query, and dynamic indexes.
- [x] Extreme-corpus evidence covers long text, high-frequency terms, large/sparse and
  Zipf vocabularies, multiple fields, Unicode, repeated terms, and position-heavy cases.
- [x] Heap diagnostics require `4g`, `8g`, and `16g`; `32g` is optional only with
  sufficient physical memory and no swapping.
- [x] Burst diagnostics cover bounded `1`/`4`/`16` producers and `1`/`100`/`1,000`
  submitted batch sizes with writer progress, completion, queue drainage, and oracles.
- [x] One controlled two-hour final-source run is a V3.4 release gate.
- [x] Six-, twelve-, and twenty-four-hour runs remain non-blocking investigations until
  a separate durable orchestration contract is accepted.
- [x] Phase 0 freezes no unsupported universal latency, allocation, heap-plateau, or
  drift percentage.

## Frozen cloud boundary

- [x] New mode is `final-v34`, suite is `v3.4-final-in-memory-suite-v1`, preset is
  `v3.4-final-in-memory-v1`, and accepted family is `v3.4.0-in-memory-cloud`.
- [x] Existing `v3-production-*-v1`, `v3.1-ranked-v1`, `v3.0.0-cloud`, and
  `v3.1.0-ranked-cloud` identities and contents remain unchanged.
- [x] Canonical evidence requires 3 or 5 Standard `c3d-standard-30` slots, GCS
  retention, the exact preset, fixed 30-minute windows, and complete comparable
  environment/source identities.
- [x] The initial extension caps each slot at three hours and the set at five slots;
  the resolved worst-case plan must be printed and approved before provisioning.
- [x] The required two-hour run is a separate one-repeat Standard/GCS experiment using
  the V3.4 preset; it never counts as a 30-minute canonical member.
- [x] Failure, partial evidence, resume/replace, upload, cleanup, and registration
  semantics remain fail-closed under the existing plan-first Cloud Benchmark lifecycle.
- [x] Phase 0 creates no paid run, workflow input, runner behavior, preset registry,
  GCS object, or baseline member.

## Frozen compatibility and validation

- [x] V3.4 adds no supported public descriptor or processor/generated-source change.
- [x] Phase 1 adds published `3.3.0` as the seventh normal and fresh-isolated Japicmp
  baseline with its pinned core hash.
- [x] All seven active coordinates switch atomically to `3.4.0-SNAPSHOT` only after
  Phase 0 protected acceptance.
- [x] V1/V2 consumers remain source-unchanged; the V3 consumer and travel example add
  no V3.4-only API.
- [x] Every new benchmark/probe receives deterministic reduced correctness, parameter,
  checksum, timeout, cleanup, and forked-execution coverage.
- [x] Existing focused/randomized/differential, mutation, dynamic-index, lifecycle,
  concurrency, retention, artifact, reproducibility, consumer, and cloud local gates
  remain mandatory.

## V4 handoff decisions

- [x] V4 begins only after signed `v3.4.0`, remote publication, post-publication
  evidence, and immutable `v3.4.0-in-memory-cloud` registration complete.
- [x] V4 may use published V3.4 as the final in-memory semantic and performance
  reference but may compare performance only under documented compatible workloads.
- [x] V4 durability cannot silently reinterpret V3.4 query, ranking, pagination,
  snapshot, mutation completion, or failure semantics.
- [x] Cross-hardware results are optional, independently fingerprinted evidence and
  never aggregate with the primary C3D family.

## Phase 0 repository gates

- [x] Architecture, compatibility, validation, performance, cloud, and V4 handoff
  documents agree.
- [x] Root development roadmap and V3.x roadmap/document maps describe the same scope
  and phase order.
- [x] The locally excluded master roadmap is refreshed without entering Git status.
- [x] Local links, Markdown/diff hygiene, and stale-state wording checks pass.
- [x] No POM, production/test/JMH source, script, workflow, preset, or baseline changes.

## Implementation entry gates

- [ ] Merge this documentation-only Phase 0 branch through protected review.
- [ ] Wait for exact-commit protected-master `CI / Required` success.
- [ ] Create `feat/v3.4-phase1-foundation` from that exact merge.
- [ ] Convert all seven active coordinates atomically to `3.4.0-SNAPSHOT`.
- [ ] Add the zero-addition V3.4 fixture, pinned published-3.3 hash, seven-baseline
  compatibility, exact-V3.3 reference fixtures, and pre-change evidence.
- [ ] Write no cold/extreme/heap/burst/cloud production implementation in Phase 1.

## Required V3.4 exit gates

- [ ] Cold construction and dynamic-index build baselines are reviewed.
- [ ] Extreme-corpus correctness and bounded-resource evidence pass.
- [ ] Heap diagnostics distinguish live state, allocation, GC pressure, and invalid
  resource-exhaustion cells.
- [ ] Multi-producer bursts preserve single-writer semantics and recover to a drained,
  oracle-correct state.
- [ ] The required two-hour run passes all correctness, liveness, queue, drift-review,
  evidence-integrity, retention, and cleanup gates.
- [ ] A final 3-or-more-member Standard canonical set is accepted and registered as
  `v3.4.0-in-memory-cloud`.
- [ ] Seven-baseline compatibility, consumers, Javadocs, artifacts, reproducibility,
  documentation, signed release, Central, deployment, GitHub Release, and remote
  verification pass.
- [ ] Post-publication evidence freezes the `3.4.0` artifact hash and closes the V3.x
  line before V4 implementation begins.

No unchecked implementation-entry item authorizes later-phase work. Any scope, public
surface, production-change, two-hour, cloud-identity, or V4-entry change requires a
Phase 0 amendment before implementation.
