# GeneralSearchEngine v2 P6 developer-experience contract

## Status and scope

This document freezes the P6 developer-experience behavior selected by D6, D7, and D8.
Implementation, correctness, compatibility, compile-test, release, reproducibility,
and the complete explicit-bulk JMH matrix pass. P6 is accepted and complete.

P6 adds atomic collection mutation and an optional typed-field annotation processor.
It does not change query truth, ranking, snapshot visibility, or existing single-item
mutation behavior. String-based fluent queries and `SearchSession` APIs remain deferred
to v2.1.

## Explicit atomic bulk mutation

`SearchEngine<K,T>` adds default `addAll`, `updateAll`, and `removeAll` methods. The
default methods preserve compatibility for third-party implementations and throw
`UnsupportedOperationException` until overridden. The built-in snapshot engine
supports all three operations.

One non-empty explicit bulk:

- is copied at submission so later collection changes cannot alter the request;
- occupies one writer-queue slot and one position in submission order;
- is never merged with or split across opportunistic single-mutation batches;
- applies collection elements in iteration order through one private builder state;
- publishes at most one immutable snapshot;
- is entirely visible to later reads after successful future completion, or entirely
  absent after failure;
- contributes its document-operation count, rather than one future, to successful or
  failed mutation metrics.

The maximum collection size is `SnapshotEngineConfig.maxBatchSize()`. A larger request
fails with `BulkMutationException.Reason.TOO_LARGE` before entering the queue. A bulk
therefore consumes one queue slot but cannot bypass the configured per-task work bound.
Queue-full and closed-engine rejection retain `EngineRejectedExecutionException`.

An empty collection succeeds immediately, uses no queue capacity, changes no metrics,
and publishes no snapshot. Null collections or elements are rejected synchronously.

### IDs, conflicts, and failure

Duplicate business IDs are invalid in all three bulk methods, including duplicate
removals. The complete future fails with
`BulkMutationException.Reason.DUPLICATE_ID`, exposing the duplicate ID.

- `addAll`: any ID already present in the base snapshot fails the entire collection
  with `DocumentAlreadyExistsException`.
- `updateAll`: any ID missing from the base or evolving private batch state fails the
  entire collection with `DocumentNotFoundException`.
- `removeAll`: a missing ID remains idempotent, matching single `remove`; other IDs in
  that valid collection are removed atomically.

ID and index extractors execute before publication. If validation or an extractor
fails after earlier private builder changes, that builder and its dynamic-index replay
changes are discarded. Engine state is atomic; external side effects performed by a
user extractor are outside the engine and cannot be rolled back.

Explicit bulks preserve ordering against individual mutations and create/drop-index
tasks. Changes accepted while a dynamic index builds are journaled under the one bulk
snapshot version and replayed before that index becomes visible. Graceful close drains
accepted non-empty bulks; later non-empty submissions are rejected.

## Optional typed-field processor

The processor is a separate artifact with the same version as the runtime core:

```text
io.github.patricklfdm:general-search-engine-processor:2.0.0
```

The processor JAR registers
`io.github.patricklfdm.generalsearch.processor.SearchFieldsProcessor` through the
standard processor service file. The core JAR contains no processor service entry, so
runtime-only consumers do not enable compile-time processing accidentally. The
processor itself has no runtime dependency; applications still put
`general-search-engine` on their normal compilation/runtime class path.

For Maven, opt in through the compiler processor path:

```xml
<annotationProcessorPaths>
    <path>
        <groupId>io.github.patricklfdm</groupId>
        <artifactId>general-search-engine-processor</artifactId>
        <version>2.0.0</version>
    </path>
</annotationProcessorPaths>
```

For a top-level `CatalogItem`, generated source is named `CatalogItemSearchFields` in
the same package. Nested names join enclosing simple names with `_`, for example
`Envelope.Entry` produces `Envelope_EntrySearchFields`. Each companion contains:

- one public typed `Field<T,V>` constant per supported member;
- a canonical `SCHEMA` built from those exact field instances;
- immutable `INDEX_DEFINITIONS` using the same canonical constants.

Constants use deterministic upper snake case. A collision such as `fooBar` and
`foo_bar` is a compile error rather than an implicit rename.

### Supported source models

- Records: all components become fields in declaration order, matching the runtime
  factory; exactly one component must carry `@SearchId`.
- Classes: directly declared, non-static, non-private fields and zero-argument getters
  carrying `@SearchId` or `@SearchIndex` are sorted by logical field name.
- Primitive values are boxed in `Field<T,V>` exactly as in the runtime factory.
- Equality, naturally comparable Range, and String Prefix indexes are supported.
- Public, protected, and package-visible document/member types work because the
  companion is generated in the document package.

Parameterized field types, private annotated members/types, inherited annotated
members, unnamed-package documents, and generated-name collisions produce stable
`GSE###` diagnostics or use the existing runtime reflection path. The runtime
`AnnotatedSchemaFactory` and `SearchEngine.fromAnnotatedClass` remain supported and can
handle scenarios intentionally outside the compile-time subset.

Generated source is deterministic for equivalent inputs. The processor's javac tests
cover successful record/class/nested compilation, primitive boxing, runtime-field
equivalence, deterministic rebuilds, collision diagnostics, private members, and
unsupported generic members.

## Maven structure and validation

The root `pom.xml` remains the unchanged runtime artifact project. A separate
`reactor/pom.xml` aggregates it with `general-search-engine-processor/pom.xml` without
moving core source directories or changing core coordinates. Run both modules with:

```bash
mvn -f reactor/pom.xml clean test
mvn -f reactor/pom.xml -Prelease verify
```

The release profile attaches and signs main, sources, and Javadoc JARs for both
artifacts. Reproducibility validation compares all six JARs across clean reactor builds.

See [`PERFORMANCE_BASELINE.md`](PERFORMANCE_BASELINE.md) for the accepted
explicit-bulk benchmark evidence.
