# V3.4 final in-memory hardening architecture contract

## Boundary

V3.4 is the final engineering-hardening line before V4 changes the durability
boundary. It is not a search-feature release and does not authorize a new public API,
query semantic, scoring model, writer model, snapshot model, or storage layer.

The protected V3.3 architecture remains authoritative:

```text
application readers
  -> supported query / ranked / highlighted / page / Explain APIs
  -> one captured immutable search snapshot
  -> existing planner and execution paths

application mutation producers
  -> asynchronous admission and bounded batching
  -> one writer
  -> structurally shared immutable state
  -> atomic snapshot publication
```

V3.4 measures and hardens that exact shape under longer duration, producer bursts,
heap pressure, cold construction, extreme corpora, and a final independent cloud
evidence family. Persistence, recovery, and reopen begin only in V4.

## No-feature release rule

Phase 0 authorizes documentation and contract work only. Later V3.4 phases may add
tests, benchmark fixtures, bounded probes, evidence tooling, and a separately named
Cloud Benchmark mode/preset. They do not receive blanket authority to change core or
processor production source.

A production change is admitted only when all of the following are true:

1. a reproducible V3.4 workload demonstrates a correctness, liveness, bounded-memory,
   or architecture-level release blocker;
2. the cause is localized and cannot be addressed by correcting invalid evidence;
3. this contract is amended before implementation with the exact affected behavior;
4. the narrow fix preserves every published semantic and public descriptor; and
5. all affected local and cloud evidence is regenerated from the fixed commit.

An attractive throughput or allocation improvement is not by itself a V3.4 release
blocker. Speculative caches, parallel writers, snapshot registries, cursor registries,
new executor pools, and broad refactors are outside the default boundary.

## Frozen runtime invariants

V3.4 preserves:

- immutable search snapshots with structural sharing;
- lock-free readers and one asynchronous writer;
- atomic visibility for successful document and dynamic-index publication;
- existing admission, completion, close, and failure precedence;
- deterministic query/filter truth, BM25 arithmetic, score bits, and canonical order;
- Explain equivalence and highlighted/page snapshot consistency;
- strict current-snapshot search-after cursor ownership and staleness;
- no snapshot pinning, disk state, recovery state, or cross-process cursor; and
- the existing supported package and third-party engine boundaries.

Measurements may observe internal counters, queue depth, heap, GC, process timing, or
benchmark-only checksums. They may not turn those observations into new application
contracts.

## Hardening surfaces

### Long-run stability

The required release-grade long run is one controlled two-hour workload on the final
V3.4 source identity. It must demonstrate reader correctness, writer progress, queue
recovery, bounded live-state behavior, and complete evidence capture. Six-, twelve-,
and twenty-four-hour runs remain investigation targets until a separate durable
orchestration extension freezes recovery, cost, cleanup, and retention.

### Producer pressure

Multiple application producer threads may submit asynchronous mutations concurrently,
but the engine remains single-writer. Burst evidence measures admission, queue growth,
batching, completion, backpressure symptoms, failure isolation, and recovery after the
burst ends. It does not authorize multiple internal writers.

### Memory envelope

Heap experiments separate algorithmic work, live retained state, allocation rate, and
collector pressure. A heap size, collector, JVM option set, and corpus fingerprint are
part of evidence identity; results with different values are not direct repeats.

### Construction and extreme inputs

Cold-process evidence covers engine creation, initial load, initial structured/text
index construction, ready-to-search transition, and dynamic-index construction. Input
stress covers long fields, high-frequency terms, large and sparse vocabularies,
Zipf-heavy distributions, multiple text fields, Unicode-heavy content, repeated terms,
and position-heavy phrase cases without changing their published semantics.

## V3.4 phase order

| Phase | Scope | Exit rule |
|---|---|---|
| 0 | freeze architecture, compatibility, validation, evidence, cloud, and V4 handoff contracts | documentation only; protected merge required |
| 1 | switch all seven active coordinates to `3.4.0-SNAPSHOT`; add seven-baseline compatibility and exact-V3.3 reference fixtures | no production behavior or benchmark-family change |
| 2 | add cold-build, extreme-corpus, and heap diagnostic surfaces; capture reviewed local evidence | deterministic fixtures and bounded resource controls pass |
| 3 | add multi-producer burst and recovery hardening plus local long-run calibration | writer progress, queue drainage, completion, and final oracles pass |
| 4 | implement and calibrate the separately frozen `final-v34` Cloud Benchmark extension | existing modes/presets remain byte-for-byte and semantically frozen |
| 5 | convert the accepted candidate to final `3.4.0`; run the required two-hour investigation and final canonical set; review the V4 handoff | evidence is valid, retained, reviewed, and tied to the exact final source/environment identities |
| 6 | consumers, final compatibility/Javadocs/artifacts/reproducibility, documentation, signed release, and post-publication evidence | all release gates pass; signed `3.4.0` becomes the final V3.x baseline |

Phase boundaries may be split into smaller protected PRs, but no later phase may use
unaccepted evidence from an earlier one.

## Explicit exclusions

V3.4 does not add WAL, checkpoints, disk segments, reopen, crash recovery, replication,
sharding, distributed coordination, vectors, embeddings, facets, aggregations,
grouping, snapshot pinning, portable cursors, highlighted pagination, lower-bound
totals, timeout/cancellation, prepared queries, new relevance operators, or analyzer
features.

Any correctness defect found in an excluded capability remains outside V3.4 unless it
affects an already published supported behavior.
