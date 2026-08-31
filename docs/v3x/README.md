# GeneralSearchEngine V3.x development line

V3.x contains the current stable `3.1.0` release and remains the active development
line before V4 changes the process-lifetime durability boundary. It matures the
in-memory engine without changing its immutable-snapshot, lock-free-reader,
asynchronous-single-writer, and atomic-publication architecture.

## Authority and history

- [`docs/v3/`](../v3/README.md) is the frozen historical record for published
  `3.0.0`. V3.x documents do not rewrite it.
- [V3.x roadmap](ROADMAP.md) defines version scope, ordering, and entry gates.
- [`v3.1/`](v3.1/PHASE_0_CHECKLIST.md) freezes the first executable V3.x contract;
  [Phase 1](v3.1/PHASE_1_CHECKLIST.md) establishes its implementation baseline and
  [Phase 2](v3.1/PHASE_2_CHECKLIST.md) implements phrase slop.
  [Phase 3](v3.1/PHASE_3_CHECKLIST.md) implements BOOL `minimumShouldMatch`, and
  [Phase 4](v3.1/PHASE_4_CHECKLIST.md) hardens the combined semantics, lifecycle,
  mutation, and concurrency behavior. [Phase 5](v3.1/PHASE_5_CHECKLIST.md) completes
  the profile-guided phrase allocation work without semantic or API drift, and
  [Phase 6](v3.1/PHASE_6_CHECKLIST.md) replaces full-scan fuzzy expansion with an
  exact persistent code-point trie. [Phase 7](v3.1/PHASE_7_CHECKLIST.md) implements
  the isolated ranked feature lane; its canonical set and frozen regression comparison
  are reviewed, and `v3.1.0-ranked-cloud` is registered as a distinct immutable family.
  [Phase 8](v3.1/PHASE_8_CHECKLIST.md) is complete: signed `v3.1.0`, Maven Central
  publication, clean remote verification, and the
  [GitHub Release](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v3.1.0)
  are accepted and recorded.
- [`v3.2/`](v3.2/PHASE_0_CHECKLIST.md) freezes the additive offset-capable analyzer and
  snapshot-consistent structured-highlighting foundation. Phase 0 is accepted, and
  [Phase 1](v3.2/PHASE_1_CHECKLIST.md) establishes the `3.2.0-SNAPSHOT` compatibility,
  independent-oracle, API-fixture, and pre-change evidence foundation without adding
  production offset or highlighting code. [Phase 2](v3.2/PHASE_2_CHECKLIST.md)
  implements the offset API family, exact built-in Unicode source mapping, sequence
  validation, and ordinary-path regression controls without introducing highlighting.
  [Phase 3](v3.2/PHASE_3_CHECKLIST.md) adds the immutable highlighted request/result
  family and integrated one-snapshot TEXT highlighting while deferring all other
  ranked query evidence to Phase 4.
- V3.3 and later versions receive their own Phase 0 contracts before implementation;
  roadmap descriptions alone are not executable semantics.

## V3.1 contract map

- [Architecture](v3.1/ARCHITECTURE.md)
- [Ranked-search semantics](v3.1/RANKED_SEARCH_SEMANTICS.md)
- [API compatibility](v3.1/API_COMPATIBILITY.md)
- [3.0-to-3.1 migration guide](v3.1/MIGRATION_GUIDE.md)
- [Performance and evidence](v3.1/PERFORMANCE_AND_EVIDENCE.md)
- [Validation](v3.1/VALIDATION.md)
- [Cloud Benchmark feature-lane extension](v3.1/CLOUD_BENCHMARK_EXTENSION.md)
- [Phase 0 checklist](v3.1/PHASE_0_CHECKLIST.md)
- [Phase 1 checklist](v3.1/PHASE_1_CHECKLIST.md)
- [Phase 1 local diagnostic baseline](v3.1/PHASE_1_BASELINE.md)
- [Phase 2 checklist](v3.1/PHASE_2_CHECKLIST.md)
- [Phase 2 local diagnostic baseline](v3.1/PHASE_2_BASELINE.md)
- [Phase 3 checklist](v3.1/PHASE_3_CHECKLIST.md)
- [Phase 4 checklist](v3.1/PHASE_4_CHECKLIST.md)
- [Phase 5 local pre-change baseline](v3.1/PHASE_5_BASELINE.md)
- [Phase 5 optimization 1](v3.1/PHASE_5_OPTIMIZATION_1.md)
- [Phase 5 optimization 2](v3.1/PHASE_5_OPTIMIZATION_2.md)
- [Phase 5 checklist](v3.1/PHASE_5_CHECKLIST.md)
- [Phase 6 local pre-change baseline](v3.1/PHASE_6_BASELINE.md)
- [Phase 6 checklist](v3.1/PHASE_6_CHECKLIST.md)
- [Phase 7 local calibration](v3.1/PHASE_7_LOCAL_CALIBRATION.md)
- [Phase 7 experiment review](v3.1/PHASE_7_EXPERIMENT_REVIEW.md)
- [Phase 7 ranked feature canonical review](v3.1/PHASE_7_CANONICAL_REVIEW.md)
- [Phase 7 frozen regression review](v3.1/PHASE_7_REGRESSION_REVIEW.md)
- [Phase 7 checklist](v3.1/PHASE_7_CHECKLIST.md)
- [Phase 8 hardening and release contract](v3.1/HARDENING_AND_RELEASE.md)
- [Phase 8 checklist](v3.1/PHASE_8_CHECKLIST.md)
- [V3.1 release checklist](v3.1/RELEASE_CHECKLIST.md)

## V3.2 contract map

- [Architecture](v3.2/ARCHITECTURE.md)
- [Token metadata and offset semantics](v3.2/TOKEN_METADATA_AND_OFFSETS.md)
- [Structured highlighting semantics](v3.2/HIGHLIGHTING.md)
- [API compatibility](v3.2/API_COMPATIBILITY.md)
- [Performance and evidence](v3.2/PERFORMANCE_AND_EVIDENCE.md)
- [Validation](v3.2/VALIDATION.md)
- [Phase 0 checklist](v3.2/PHASE_0_CHECKLIST.md)
- [Phase 1 checklist](v3.2/PHASE_1_CHECKLIST.md)
- [Phase 1 pre-change baseline](v3.2/PHASE_1_BASELINE.md)
- [Phase 2 checklist](v3.2/PHASE_2_CHECKLIST.md)
- [Phase 2 offset-analysis baseline](v3.2/PHASE_2_BASELINE.md)
- [Phase 3 checklist](v3.2/PHASE_3_CHECKLIST.md)
- [Phase 3 TEXT-highlighting baseline](v3.2/PHASE_3_BASELINE.md)

## Stable boundaries

V3.x continues to separate deterministic eligibility from ranked relevance:

```text
Query<T>       -> structured filtering
SearchQuery<T> -> ranked matching and scoring
```

V3.x does not introduce WAL, checkpoints, crash recovery, persisted index reopen,
disk segments, sharding, replication, vector retrieval, or distributed coordination.
Those capabilities require a V4 durability contract.
