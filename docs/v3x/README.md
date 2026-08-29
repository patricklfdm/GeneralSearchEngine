# GeneralSearchEngine V3.x development line

V3.x is the active development line after published `3.0.0` and before V4 changes
the process-lifetime durability boundary. It matures the in-memory engine without
changing its immutable-snapshot, lock-free-reader, asynchronous-single-writer, and
atomic-publication architecture.

## Authority and history

- [`docs/v3/`](../v3/README.md) is the frozen historical record for published
  `3.0.0`. V3.x documents do not rewrite it.
- [V3.x roadmap](ROADMAP.md) defines version scope, ordering, and entry gates.
- [`v3.1/`](v3.1/PHASE_0_CHECKLIST.md) freezes the first executable V3.x contract;
  [Phase 1](v3.1/PHASE_1_CHECKLIST.md) establishes its implementation baseline and
  [Phase 2](v3.1/PHASE_2_CHECKLIST.md) implements phrase slop.
  [Phase 3](v3.1/PHASE_3_CHECKLIST.md) implements BOOL `minimumShouldMatch`, and
  [Phase 4](v3.1/PHASE_4_CHECKLIST.md) hardens the combined semantics, lifecycle,
  mutation, and concurrency behavior.
- Later V3.x versions receive their own Phase 0 contracts before implementation;
  roadmap descriptions alone are not executable semantics.

## V3.1 contract map

- [Architecture](v3.1/ARCHITECTURE.md)
- [Ranked-search semantics](v3.1/RANKED_SEARCH_SEMANTICS.md)
- [API compatibility](v3.1/API_COMPATIBILITY.md)
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

## Stable boundaries

V3.x continues to separate deterministic eligibility from ranked relevance:

```text
Query<T>       -> structured filtering
SearchQuery<T> -> ranked matching and scoring
```

V3.x does not introduce WAL, checkpoints, crash recovery, persisted index reopen,
disk segments, sharding, replication, vector retrieval, or distributed coordination.
Those capabilities require a V4 durability contract.
