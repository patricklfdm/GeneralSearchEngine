# V3.3 timeout, cancellation, and preparation decision contract

## Phase 0 decision

Timeout/cancellation and prepared queries are decision obligations for V3.3, not
authorized implementation in the initial pagination foundation.

The required order is:

```text
pagination and exact-total implementation
-> focused scale / cancellation-point profiling
-> consumer and API review
-> explicit decision record
-> contract amendment before any public or production implementation
```

V3.3 cannot silently claim these capabilities. Before release it must record either an
accepted bounded design with completed evidence or an explicit deferral with reasons.

## Cooperative boundary if accepted

Any later timeout/cancellation design must be cooperative. Permitted check boundaries
include:

- before and after ranked-query normalization;
- between fuzzy dictionary traversal steps;
- between candidate words or candidate bitmap blocks;
- before/after structured filter evaluation for one document;
- between positional verification work units;
- between scoring candidates; and
- before result construction and return.

The engine cannot promise preemption inside arbitrary application
`Analyzer.analyze(...)`, field extraction, or `Query.matches(...)` code. It cannot use
unsafe thread termination or asynchronous interruption as a correctness guarantee.

Cancellation must leave no retained scratch state, partial result, mutable plan,
published read state, or writer interaction. It cannot cancel or roll back a mutation,
dynamic-index build, or another reader.

## Required semantic decisions before implementation

An amendment must freeze all of the following:

- one public control shape: deadline, duration, cancellation token, or a bounded
  combination;
- clock source and overflow rules;
- already-expired/already-cancelled behavior;
- deterministic exception type and failure precedence;
- ordinary, paged, highlighted, and Explain applicability;
- whether exact total hits may terminate without a count;
- metrics counters and whether cancellation is an error;
- check granularity for text, phrase, fuzzy, BOOL, filters, and result assembly;
- lifecycle behavior before and during close; and
- independent deterministic testing without wall-clock flakes.

No public timeout method is reserved speculatively in the Phase 0 API.

## Decision evidence

The decision review must identify real workloads where an admitted read materially
exceeds an application budget, and profile where cooperative checks could observe it.
It must measure disabled-control overhead on ordinary and paged search, because a
control that materially taxes every normal request is not automatically justified.

Required candidate workloads include high-frequency phrase, large fuzzy vocabulary,
dense BOOL, expensive structured filters, exact total hits, and deep cursor walks.
Evidence distinguishes engine-controlled loops from opaque consumer code.

No fixed implementation phase is required if the evidence shows negligible consumer
need, insufficient safe check coverage, or unacceptable disabled-path overhead.

## Prepared-query decision

Prepared queries remain deferred unless profiling proves repeated logical
normalization or validation is material after pagination work. A future prepared value
may cache only immutable logical facts:

- validated public query shape;
- deterministic analyzer output tied to exact canonical fields/analyzers;
- immutable normalized logical nodes; and
- request-independent query metadata.

It may not retain a snapshot, index, posting, position array, candidate bitmap, fuzzy
dictionary, document ID, physical plan, filter plan, cursor, or result.

An implicit global cache, unbounded map, thread-local request cache, weakly specified
invalidation scheme, or cross-engine prepared object is prohibited. Any public prepared
type needs its own lifecycle, ownership, compatibility, and memory-retention contract.

## Explicit non-goals

This decision contract does not authorize asynchronous search, reactive streams,
parallel candidate scoring, interrupt-driven cancellation, query scheduling, admission
queues for readers, global plan caching, or mutation cancellation.
