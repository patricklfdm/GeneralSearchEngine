# Migrating from 3.3 to 3.4

V3.4 is a zero-addition final in-memory hardening release. Existing V1, V2, V3.0,
V3.1, V3.2, and V3.3 applications upgrade without changing supported source code,
query construction, ranking, highlighting, pagination, mutation, index, or lifecycle
behavior. V3.4 adds benchmark and evidence infrastructure, not an application feature.

## Dependency

After `3.4.0` is published, upgrade the runtime and optional processor together:

```xml
<dependency>
    <groupId>io.github.patricklfdm</groupId>
    <artifactId>general-search-engine</artifactId>
    <version>3.4.0</version>
</dependency>
```

Java 21 and Maven 3.9 or newer remain required. Until remote publication is verified,
`3.3.0` remains the current Maven Central release; do not resolve a local same-version
`3.4.0` install as proof of publication.

## No API migration

V3.4 adds or removes no supported public type, method, constructor, field, enum
constant, record component, annotation, service, or module descriptor. In particular:

- structured `Query<T>` and every ranked query/request/result descriptor are unchanged;
- analyzers, source offsets, highlighting, Explain, pagination, cursors, and exact
  total hits are unchanged;
- schemas, generated fields, processor behavior, and runtime discovery are unchanged;
- mutation, batching, dynamic-index, metrics, close, and failure APIs are unchanged;
  and
- third-party `SearchEngine` implementations require no new method implementation.

Applications should compile and run their existing 3.3 suite before adopting any
operational recommendation. No V3.4 benchmark type belongs on an application classpath.

## Preserved behavior

The upgrade preserves:

- structured filtering and iteration order;
- BM25 scores, score bits, canonical ordering, filters, and limits;
- TEXT, PHRASE/slop, FUZZY, BOOL/BOOST, and Explain semantics;
- exact offsets and structured-highlight hits, spans, and fragments;
- first-page parity, search-after continuation, exact totals, and cursor failures;
- single-writer admission, batching, future completion, and failure atomicity;
- immutable-snapshot visibility and dynamic-index replay/publication/drop; and
- close admission and completion of already admitted reads.

V3.4 evidence does not create an application SLA or a guaranteed queue, latency,
memory, thread-count, or throughput threshold.

## Hardening and evidence additions

The release adds benchmark-only cold-construction, extreme-corpus, bounded-heap,
multi-producer burst/recovery, and windowed long-run diagnostics. It also adds the
isolated cloud identities:

```text
mode       final-v34
suite      v3.4-final-in-memory-suite-v1
preset     v3.4-final-in-memory-v1
baseline   v3.4.0-in-memory-cloud
```

These are maintainer evidence contracts. They do not appear in the runtime or
processor artifacts, alter an index snapshot, or aggregate with the historical
`v3.0.0-cloud` and `v3.1.0-ranked-cloud` families.

## Deliberately deferred scope

V3.4 does not add WAL, checkpoints, disk segments, persisted reopen, crash recovery,
replication, sharding, vectors, facets, aggregations, grouping, portable cursors,
snapshot pinning, highlighted pagination, lower-bound totals, timeout/cancellation,
prepared queries, or new relevance/analyzer operators. V4 durability starts only
after signed publication and post-publication evidence close V3.x.

## Upgrade checklist

1. Keep using `3.3.0` until `3.4.0` is remotely verified on Maven Central.
2. Upgrade runtime and processor coordinates together.
3. Compile and run the existing application suite without source changes.
4. Confirm no application imports benchmark, probe, or cloud-runner packages.
5. Preserve existing pagination restart policy and highlighting presentation rules.
6. Treat performance evidence as environment-specific rather than a universal SLA.
