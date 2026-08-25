# Migrating from GeneralSearchEngine v1.0.0 to v2

GeneralSearchEngine v2 preserves the supported v1 application API. Existing v1 code
can update its dependency version without rewriting schemas, typed structured queries,
mutation calls, lifecycle handling, or custom `IndexSnapshot` implementations.

For the final release, change only the version:

```xml
<dependency>
    <groupId>io.github.patricklfdm</groupId>
    <artifactId>general-search-engine</artifactId>
    <version>2.0.0</version>
</dependency>
```

Structured query truth and ascending internal-document-ID result order remain intact.
Cost-aware Range planning may choose a different access path, but planning cannot
change which documents match.

## Optional v2 adoption

- Configure Range planning with `SearchEngineBuilder.plannerConfig(...)`; the default
  is cost-aware and force modes are intended for regression/diagnostic use.
- Add one canonical `TextField<T>` per analyzed String field and use the same instance
  in schema, text index, boolean text queries, and ranked requests.
- Use `searchTopK(RankedSearchRequest<T>)` for BM25-ranked results. Existing
  `search(Query<T>)` remains unranked.
- Use `addAll`, `updateAll`, and `removeAll` when one explicit collection must publish
  atomically. These differ from submitting independent futures.
- Add the optional `general-search-engine-processor` artifact through Maven compiler
  `annotationProcessorPaths` to generate typed `*SearchFields` companions. Runtime
  reflection generation remains supported.

Exact analyzed-text, ranking, and bulk contracts are documented in
[`phases/p4/TEXT_SEMANTICS.md`](phases/p4/TEXT_SEMANTICS.md),
[`phases/p5/RANKING_SEMANTICS.md`](phases/p5/RANKING_SEMANTICS.md), and
[`phases/p6/DEVELOPER_EXPERIENCE.md`](phases/p6/DEVELOPER_EXPERIENCE.md).

## Boundaries retained in v2

The following are not introduced by v2: fuzzy/phonetic search, phrase or positional
search, persistence or WAL, distributed search/sharding, vector retrieval, and
cross-field/distributed score merging. String-based fluent queries and `SearchSession`
remain deferred to v2.1.

Applications that directly depend on bitmap, storage, concrete index implementation,
or `internal` packages must audit those uses separately. Those packages were public in
the JAR but were never part of the v1 application compatibility promise.
