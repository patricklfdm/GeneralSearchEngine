# GeneralSearchEngine

GeneralSearchEngine is evolving into a generic Java 21 in-memory object search engine.
Product is currently its reference document type. The engine uses immutable search
snapshots and persistent, block-based bitmaps so readers can search without
locking while a single writer batches mutations and atomically publishes new snapshots.

## Requirements

- JDK 21 or newer
- Maven 3.9 or newer

## Build and test

```bash
mvn test
```

The test suite contains unit tests for the persistent tree, immutable bitmap, generic
storage, query planner and engine lifecycle, plus randomized Product and non-Product
differential tests against full-scan oracles.

Run only the frozen v1 source/JVM-descriptor compatibility fixture with:

```bash
mvn clean -Papi-compat test
```

## Package layout

```text
org.example.generalsearch
├── model       Product domain types
├── schema      Type-safe fields, schemas and annotation generation
├── filter      Compatibility layer for former Product filters
├── bitmap      Persistent tree and immutable bitmap primitives
├── index       Immutable field indexes and batch builders
├── storage     Generic document tables and immutable search snapshots
├── query       Candidate planning and final result evaluation
└── engine      Public API, mutation queue and snapshot publication
```

Dependencies flow from the engine toward the lower-level packages. The bitmap package
is domain-independent, storage and query components operate on any document type `T`,
and indexes advertise their own query capabilities. Product's canonical fields and
default indexes are generated once from its annotations at startup.

## Basic usage

```java
import java.util.List;
import org.example.generalsearch.engine.SnapshotUpdateEngine;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;
import org.example.generalsearch.query.Query;

try (var engine = new SnapshotUpdateEngine()) {
    engine.add(new Product(
            "p1", "Laptop", Category.ELECTRONICS, 999.99, true, 4.7
    )).join();

    List<Product> products = engine.search(Query.and(
            Query.eq(ProductFields.CATEGORY, Category.ELECTRONICS),
            Query.between(ProductFields.PRICE, 500.0, 1_500.0)
    ));
}
```

`ProductFields` contains the canonical `Field<Product, V>` definitions and a complete
`SearchSchema<Product, String>`. Field extractors keep the query DSL and business ID
type-safe without exposing reflection to the search core. The old `ProductFilter` types
remain temporarily source-compatible but are deprecated; new code should use
`Query<T>`.

Mutation methods are asynchronous. Completion means the mutation is visible in the
published snapshot. Mutations submitted through one engine are applied in submission
order. Closing the engine stops new submissions, drains accepted mutations and waits
for the writer thread and accepted index builds to finish.

The public API uses business IDs. The engine assigns internal integer document IDs and
keeps their mapping in the same atomically published state as the search snapshot.
Duplicate `add` and `update` of a missing ID fail through their returned futures;
removing a missing ID is idempotent. Removed internal document IDs are not reused.

`SnapshotEngineConfig` controls queue capacity, maximum batch size and maximum batch
wait. The default is a 100,000-item queue, batches of up to 1,000 mutations and a 5 ms
batch window.

## Generic engine

`SearchEngine<K,T>` is the primary public entry point. A document type only needs a
typed ID field and its searchable fields/indexes:

```java
record Item(Long id, String warehouse, int quantity) {}

Field<Item, Long> id = Field.of("id", Long.class, Item::id);
Field<Item, String> warehouse =
        Field.of("warehouse", String.class, Item::warehouse);
Field<Item, Integer> quantity =
        Field.of("quantity", Integer.class, Item::quantity);

try (SearchEngine<Long, Item> engine = SearchEngine.builder(Item.class, id)
        .index(IndexDefinition.equality(warehouse))
        .index(IndexDefinition.range(quantity))
        .build()) {
    engine.add(new Item(1001L, "north", 120)).join();
    List<Item> items = engine.search(Query.and(
            Query.eq(warehouse, "north"),
            Query.between(quantity, 100, 200)
    ));
}
```

`index(...)` automatically registers its canonical field when the builder is assembling
a manual schema. Use `field(...)` for unindexed fields. An already assembled schema can
instead be supplied through `SearchEngine.builder(schema)`. Both builders accept
`config(SnapshotEngineConfig)` and multiple `indexes(...)`.

`engine.schema()` returns the immutable canonical schema. Fields retrieved from this
schema should be used for queries and runtime indexes, especially with annotation-
generated engines.

`DocumentTable<T>`, `SearchSnapshot<T>`, `CandidatePlanner<T>` and
`SnapshotSearcher<T>` remain the lower-level domain-independent search chain.
`SnapshotUpdateEngine` is the Product convenience boundary that supplies Product's
schema and default indexes while retaining the deprecated ProductFilter adapter.
The concrete `SnapshotSearchEngine` constructors remain compatible for lower-level
callers, but new application code should construct engines through `SearchEngine`.

## Annotation-generated configuration

`SearchEngine.fromAnnotatedClass` is the short factory for annotated documents.
Reflection is limited to member discovery and startup validation; member extractors
are pre-bound as method handles.

```java
record Item(
        @SearchId Long id,
        @SearchIndex(IndexType.EQUALITY) String warehouse,
        @SearchIndex(IndexType.RANGE) int quantity,
        String name
) {}

try (SearchEngine<Long, Item> engine =
        SearchEngine.fromAnnotatedClass(Item.class, Long.class)) {
    Field<Item, String> warehouse =
            engine.schema().requireField("warehouse", String.class);
    engine.add(new Item(1001L, "north", 120, "Cable")).join();
    List<Item> items = engine.search(Query.eq(warehouse, "north"));
}
```

Use `SearchEngine.annotatedBuilder(...)` instead when engine configuration must be
customized before `build()`. `AnnotatedSchemaFactory` remains available as the
lower-level configuration generator.

All record components become schema fields. For ordinary classes, only fields and
zero-argument getters carrying `@SearchId` or `@SearchIndex` are included. Private
members are accepted only when `trySetAccessible()` succeeds. Primitive member types
are exposed through their boxed classes.

Exactly one ID is required. Duplicate logical field names, an ID type mismatch, static
annotated members, invalid getters and incompatible index types fail during generation.
`EQUALITY`, `RANGE` and `PREFIX` are available.

## Failure contract

Mutation and dynamic-index operations return `CompletableFuture<Void>`. Operational
failures are available as the cause of `CompletionException` from `join()`:

- `DocumentAlreadyExistsException`: `add` received an active business ID.
- `DocumentNotFoundException`: `update` received a missing business ID.
- `EngineRejectedExecutionException`: the engine is closed or its writer queue is full;
  inspect `reason()` for `CLOSED` or `QUEUE_FULL`.
- `IndexLifecycleException`: an index already exists, the same build is in progress, or
  a pending build was cancelled by `dropIndex`; inspect `reason()` and `fieldName()`.

Removing a missing ID and dropping a known field without indexes remain idempotent.
Invalid arguments and invalid builder/schema configuration fail synchronously with
`IllegalArgumentException` or `SchemaGenerationException`. A field extractor or custom
index failure remains the original build failure rather than being hidden by a generic
wrapper.

## V1 boundary semantics

The complete contract is recorded in
[V1_SEMANTICS.md](docs/V1_SEMANTICS.md). The important boundaries are:

- The engine retains object references rather than copying documents. Treat accepted
  objects as immutable and use `update(newDocument)` for every change.
- Documents and IDs are non-null. Other fields may be null; built-in indexes omit null
  values, while `eq(field, null)` remains correct by falling back to a scan.
- Equality uses `Objects.equals`. Ranges are inclusive and use Java natural ordering;
  reversed bounds match nothing. A Range index conservatively treats equality as a
  candidate superset because some Comparable types are inconsistent with equals.
  Custom comparators are not available in v1.
- Strings are case-sensitive raw UTF-16 values. There is no Locale conversion, Unicode
  normalization, trimming, or case folding.
- `Float`/`Double` use their Java wrapper semantics, including NaN, infinities, and
  distinct signed-zero equality keys.

The supported v1 surface and change policy are recorded in
[V1_API_COMPATIBILITY.md](docs/V1_API_COMPATIBILITY.md). Public types in low-level
implementation packages are not automatically part of that application-level promise.

## Query planning

Product category, Prime, price and name-prefix queries currently have bitmap indexes.
Rating queries are evaluated by scanning the safe candidate set. Composite planning
follows these rules:

- `AND` can use any indexed children and returns a safe superset when some children are
  not indexed.
- `OR` uses a bitmap only when every child can provide a safe candidate set.
- `NOT` uses a bitmap complement only when its child result is exact.
- Every candidate document is evaluated by `Query.matches`, regardless of the
  planner result.

## Adding a query or index

To add an unindexed query:

1. Define or reuse a type-safe `Field<T,V>`.
2. Add a `Query<T>` implementation and implement `matches(T)`.
3. Add direct and composite-query tests. The searcher will safely fall back to scanning.

Built-in indexes can be selected when the engine starts:

```java
var indexes = List.<IndexDefinition<Product>>of(
        IndexDefinition.equality(ProductFields.CATEGORY),
        IndexDefinition.equality(ProductFields.PRIME),
        IndexDefinition.range(ProductFields.PRICE),
        IndexDefinition.prefix(ProductFields.NAME),
        IndexDefinition.range(ProductFields.RATING)
);

var engine = new SnapshotUpdateEngine(SnapshotEngineConfig.DEFAULT, indexes);
```

`EqualityIndex` works with enums, booleans, strings and other exact values. `RangeIndex`
works with self-compatible `Comparable` values and also answers exact equality queries.
`PrefixIndex` uses a sorted value map to answer `startsWith` and string equality
queries. Adding another field with any built-in index does not require changes to
SearchSnapshot or CandidatePlanner.

## Runtime index management

Indexes can also be created and dropped while reads and mutations continue:

```java
engine.createIndex(IndexDefinition.range(ProductFields.RATING)).join();

List<Product> highlyRated = engine.search(
        Query.between(ProductFields.RATING, 4.5, 5.0)
);

engine.dropIndex("rating").join();
```

`createIndex` captures an immutable snapshot and its version, builds the index on a
dedicated background thread, journals successful document mutations, replays changes
newer than the captured version, and finally publishes the new registry atomically on
the writer thread. Until publication, queries continue using the previous registry and
safely fall back to scanning when necessary.

Dynamic definitions must use the exact canonical `Field` instance from the engine's
schema. Creating the same index algorithm for the same field twice fails, including
when an equivalent build is already running. Different algorithms may coexist on one
field. `dropIndex(fieldName)` removes every index for that field and cancels pending
builds. Dropping a known field with no index is idempotent; an unknown field name fails.
Completion of either operation means the resulting registry is visible to readers.

To add a new index algorithm:

1. Implement `IndexDefinition<T>`, `IndexSnapshot<T>` and `IndexBuilder<T>`.
2. Let the snapshot report candidates for the query types it supports.
3. Register the definition at startup or through `createIndex`.
4. Add mutation, snapshot-isolation and randomized differential tests.

## Operational metrics

Every engine exposes a lock-free, immutable operational snapshot:

```java
SearchEngineMetrics metrics = engine.metrics();

System.out.println(metrics.documentCount());
System.out.println(metrics.mutationJournalLength());
System.out.println(metrics.activeIndexBuilds());
```

The snapshot includes the published snapshot version, document and registered-index
counts, writer queue depth/capacity, journal length, successful/failed mutations and
index-build started/succeeded/failed/cancelled totals. `activeIndexBuilds` reports the
field, concrete index snapshot type, captured base version and elapsed duration for
each build that has not reached publication.

`lastSuccessfulIndexBuildDuration` measures scan, queue wait and mutation replay up to
atomic publication. `lastIndexBuildFailure` retains only the build identity, exception
class name, optional message and duration; it deliberately does not retain the
Throwable object. Cancellation through `dropIndex` has its own counter and is not
reported as a build failure. Mutation totals cover writer-processed operations and
mutation submissions rejected because the queue is full or the engine is closed.

Metrics are intended for polling and monitoring adapters. They describe one instant
and may be stale immediately after return; collecting them never locks search readers.

## JMH performance baselines

Formal performance measurements use JMH 1.37 in an opt-in Maven profile. Benchmark
sources live under `src/jmh/java`; they are excluded from the normal build and
`mvn test` never executes them. Build the self-contained forkable JAR with:

```bash
mvn -Pjmh -DskipTests clean package
java -jar target/benchmarks.jar -l
```

The suite contains nine benchmarks in three groups:

- `ProductQueryBenchmark`: Equality, Range, Prefix, indexed composite and unindexed
  range-scan throughput.
- `ProductMutationBenchmark`: end-to-end single update and 100-update batch
  publication latency. The batch result is normalized per document operation.
- `DynamicIndexBuildBenchmark`: end-to-end Rating Range/Equality build, publication
  and drop latency.

The annotations default to 10,000 documents, two forked JVMs, explicit warmup and five
measurement iterations. Override the data size and select a group using JMH options:

```bash
java -jar target/benchmarks.jar 'ProductQueryBenchmark.*' \
  -p productCount=100000 \
  -prof gc -prof mempool \
  -rf json -rff target/jmh-query.json

java -jar target/benchmarks.jar 'ProductMutationBenchmark.*' \
  -p productCount=100000 -prof gc \
  -rf json -rff target/jmh-mutation.json

java -jar target/benchmarks.jar 'DynamicIndexBuildBenchmark.*' \
  -p productCount=100000 -prof gc \
  -rf json -rff target/jmh-index-build.json
```

`gc.alloc.rate.norm` is normalized allocation per operation in bytes. The `mempool`
profiler reports JVM pool occupancy and is useful for same-environment footprint
comparisons, but it is not an engine-only retained-object size. Use `-prof jfr` or a
heap dump when retained-object paths need investigation. Keep the JDK, heap settings,
collector, hardware, document count and benchmark options identical when comparing
runs. JSON result files under `target` are intentionally disposable build artifacts.

For IntelliJ, run the Maven goal above and execute the resulting JAR from the built-in
terminal. Direct, non-forked IDE runs are suitable only for debugging benchmark setup,
not for recording baselines.

## Lightweight engineering benchmark

The repository retains a lightweight smoke benchmark covering all Product default
indexes, including name prefixes. It reports total load time, approximate memory growth
and mixed-query throughput. These values are useful for quick local regression checks
but are not accepted as formal JMH or memory results.

```bash
mvn test-compile
java -cp target/classes:target/test-classes \
  org.example.generalsearch.benchmark.ProductFilterBenchmark \
  --products=100000 --queries=100000
```

## Concurrency stress testing

The normal `mvn test` lifecycle includes a bounded concurrency regression test. It
runs readers, independent writers and runtime index create/drop operations together,
checks every returned document against its query, rejects duplicate IDs, and performs
a final differential comparison with a full-scan oracle.

Long-running stress is opt-in and is not discovered by Surefire. In IntelliJ, open
`ProductEngineConcurrencyStress`, run its `main` method, and set program arguments in
the run configuration. The same runner is available from a terminal:

```bash
mvn test-compile
java -cp target/classes:target/test-classes \
  org.example.generalsearch.benchmark.ProductEngineConcurrencyStress \
  --products=100000 --readers=8 --writers=2 --seconds=300 --seed=42
```

All arguments are optional. Defaults are 100,000 products, up to 8 readers, 2 writers,
60 seconds and seed 42. The runner continuously mixes indexed and unindexed queries,
add/update/remove mutations, and concurrent Range/Equality index builds followed by
drop operations. It prints query and mutation throughput only after the worker checks
and final oracle comparison pass. This is a correctness-oriented soak runner rather
than a statistically rigorous microbenchmark; use the JMH suite above for stable
performance and allocation baselines.
