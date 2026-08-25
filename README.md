# GeneralSearchEngine

GeneralSearchEngine v2.0.0 is a generic Java 21 in-memory object search engine.
Product is its reference document type. The engine uses immutable search
snapshots and persistent, block-based bitmaps so readers can search without
locking while a single writer batches mutations and atomically publishes new snapshots.

Version 2.0.0 is the current published stable release. Its signed `v2.0.0` tag and both
Maven artifacts were published on August 25, 2026. The completed v2 work and
compatibility constraints are recorded in the
[development roadmap](DEVELOPMENT_ROADMAP.md) and
[v2 architecture contracts](docs/v2/phases/p0/ARCHITECTURE.md).
The complete document map is available in [`docs/README.md`](docs/README.md).

## Requirements

- JDK 21 or newer
- Maven 3.9 or newer

## Maven coordinates

The v2.0.0 runtime dependency is:

```xml
<dependency>
    <groupId>io.github.patricklfdm</groupId>
    <artifactId>general-search-engine</artifactId>
    <version>2.0.0</version>
</dependency>
```

The optional annotation processor is published separately as
`io.github.patricklfdm:general-search-engine-processor:2.0.0`. Existing v1 users should
read the [migration guide](docs/v2/MIGRATION_GUIDE.md); the published v1 coordinates
remain recorded in the [v1 documentation](docs/v1/API_COMPATIBILITY.md).

Both the
[`general-search-engine`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine/2.0.0)
and
[`general-search-engine-processor`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine-processor/2.0.0)
artifacts are available from Maven Central. Release notes and direct-download archives
are available from the
[`v2.0.0` GitHub Release](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v2.0.0).

## Build and test

```bash
mvn clean test
```

The test suite contains unit tests for the persistent tree, immutable bitmap, generic
storage, query planner and engine lifecycle, plus randomized Product and non-Product
differential tests against full-scan oracles.

See the completed v1 [performance baseline](docs/v1/PERFORMANCE_BASELINE.md) for the
environment- and workload-specific JMH regression results.

The v2 baselines are staged by phase: [P1 estimate/statistics results](docs/v2/phases/p1/PERFORMANCE_BASELINE.md),
the [P2 bitmap/publication baseline](docs/v2/phases/p2/PERFORMANCE_BASELINE.md), and the
[P3 planner performance baseline](docs/v2/phases/p3/PERFORMANCE_BASELINE.md). P4 analyzed-text
semantics and the accepted 58-row
[P4 performance baseline](docs/v2/phases/p4/PERFORMANCE_BASELINE.md) are now frozen. P5 BM25
semantics and its accepted
[70-row performance baseline](docs/v2/phases/p5/PERFORMANCE_BASELINE.md) are now frozen.
P6 atomic-bulk and generated-field semantics and its accepted
[eight-row explicit-bulk baseline](docs/v2/phases/p6/PERFORMANCE_BASELINE.md) are now frozen.
The representative 141-row
[P7 regression baseline](docs/v2/phases/p7/PERFORMANCE_BASELINE.md) is accepted; the separate
target-machine concurrency soak also passed.

Run only the frozen v1 source/JVM-descriptor compatibility fixture with:

```bash
mvn clean -Papi-compat test
```

## Release engineering

The release profile runs strict structural Javadoc validation and attaches the main,
sources, and Javadoc JARs. Validate both the runtime and optional processor artifacts
through the reactor:

```bash
mvn -f reactor/pom.xml clean -Prelease verify
```

Release archives use a fixed `project.build.outputTimestamp` and pinned lifecycle
plugin versions. Verify that two clean builds are byte-for-byte identical with:

```bash
bash scripts/verify-reproducible-build.sh
```

The script skips tests because release verification runs them separately, then compares
all six core/processor JARs and prints their SHA-256 checksums. Reproduction assumes the same JDK
major version; `.gitattributes` fixes repository text files to LF across platforms.
See [CHANGELOG.md](CHANGELOG.md), the
[v2 release checklist](docs/v2/RELEASE_CHECKLIST.md), and the
[P7 validation record](docs/v2/phases/p7/RELEASE_VALIDATION.md) for the frozen v2.0.0
release evidence. The
[v1 release checklist](docs/v1/RELEASE_CHECKLIST.md) remains historical. External
repository credentials and signing configuration remain environment-specific. The
project identity and Apache License 2.0 metadata are finalized for v2.0.0.

## v1.0.0 scope

Version 1.0.0 is frozen around typed equality, inclusive range, prefix and boolean
queries over immutable in-memory snapshots. The following capabilities are explicitly
out of scope for v1.0.0:

- full-text search and BM25 ranking;
- fuzzy search;
- write-ahead logging (WAL) and persistence;
- distributed search and sharding.

## Package layout

```text
io.github.patricklfdm.generalsearch
├── model       Product domain types
├── analysis    Deterministic analyzed-text tokenization
├── schema      Type-safe fields, schemas and annotation generation
├── filter      Compatibility layer for former Product filters
├── bitmap      Persistent tree and immutable bitmap primitives
├── index       Immutable field indexes and batch builders
├── storage     Generic document tables and immutable search snapshots
├── query       Candidate planning and final result evaluation
├── ranking     BM25 requests, scoring, hits and bounded top-K retrieval
└── engine      Public API, mutation queue and snapshot publication
```

Dependencies flow from the engine toward the lower-level packages. The bitmap package
is domain-independent, storage and query components operate on any document type `T`,
and indexes advertise their own query capabilities. Product's canonical fields and
default indexes are generated once from its annotations at startup.

## Quick start: annotated search

The shortest path uses runtime annotation discovery and does not require the optional
annotation processor:

```java
public record TravelPlace(
        @SearchId long id,
        @SearchIndex(IndexType.EQUALITY) String city,
        @SearchIndex(IndexType.RANGE) double price,
        double rating,
        String description
) {}
```

```java
try (SearchEngine<Long, TravelPlace> engine = SearchEngine
        .annotatedBuilder(TravelPlace.class, Long.class)
        .textIndex("description", Analyzer.simple())
        .build()) {
    Field<TravelPlace, String> city = engine.field("city", String.class);
    TextField<TravelPlace> description = engine.textField("description");

    engine.add(new TravelPlace(
            1L, "Paris", 120.0, 4.9, "Museum beside the river")).join();

    List<TravelPlace> results = engine.search(Query.and(
            Query.eq(city, "Paris"),
            Query.term(description, "museum")));
}
```

Every record component is available through `engine.field(...)`. `@SearchIndex` also
creates a startup structured index, while `textIndex(...)` selects the analyzer and
creates a startup text index. For ordinary classes, annotate fields or zero-argument
getters with `@SearchField` when they should be available without a startup index.
`SearchEngine.fromAnnotatedClass(...)` remains the shortest option when no builder
configuration is needed. The generated-field workflow described below is optional.

## Product convenience API

```java
import java.util.List;
import io.github.patricklfdm.generalsearch.engine.SnapshotUpdateEngine;
import io.github.patricklfdm.generalsearch.model.Category;
import io.github.patricklfdm.generalsearch.model.Product;
import io.github.patricklfdm.generalsearch.model.ProductFields;
import io.github.patricklfdm.generalsearch.query.Query;

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

The v2 development line also provides explicit atomic collection mutations:

```java
engine.addAll(List.of(first, second, third)).join();
engine.updateAll(List.of(updatedFirst, updatedSecond)).join();
engine.removeAll(List.of(first.id(), second.id())).join();
```

A non-empty explicit collection occupies one writer-queue slot and publishes at most
one snapshot. Duplicate IDs, an existing `addAll` ID, a missing `updateAll` ID, or an
extractor failure rejects the complete collection without partial visibility. The
collection size is bounded by `SnapshotEngineConfig.maxBatchSize()`; missing IDs in
`removeAll` remain idempotent. See the
[P6 developer-experience contract](docs/v2/phases/p6/DEVELOPER_EXPERIENCE.md) for exact ordering,
failure, empty-input, metrics, and close behavior.

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

`index(...)` automatically registers its canonical field. Use `field(...)` for
unindexed fields. `SearchEngine.builder(schema)` safely copies and extends the
configuration when a new field or `TextField` is added; the supplied immutable schema
is never mutated. Both builder forms accept `config(SnapshotEngineConfig)`,
`plannerConfig(PlannerConfig)`, and multiple `indexes(...)`.

`engine.schema()` returns the immutable canonical schema. Fields retrieved from this
schema should be used for queries and runtime indexes, especially with annotation-
generated engines.

`DocumentTable<T>`, `SearchSnapshot<T>`, `CandidatePlanner<T>` and
`SnapshotSearcher<T>` remain the lower-level domain-independent search chain.
`SnapshotUpdateEngine` is the Product convenience boundary that supplies Product's
schema and default indexes while retaining the deprecated ProductFilter adapter.
The concrete `SnapshotSearchEngine` constructors remain compatible for lower-level
callers, but new application code should construct engines through `SearchEngine`.

## Analyzed text in the v2 development line

Version `2.0.0` adds unranked full-text membership without changing
v1 query behavior. One canonical `TextField<T>` binds a String field to its Analyzer,
and the same instance is used by queries, scan fallback, and the inverted index:

```java
record Article(Long id, String body) {}

Field<Article, Long> id = Field.of("id", Long.class, Article::id);
Field<Article, String> body = Field.of("body", String.class, Article::body);
TextField<Article> analyzedBody = TextField.of(body, Analyzer.simple());

try (SearchEngine<Long, Article> engine = SearchEngine.builder(Article.class, id)
        .index(IndexDefinition.text(analyzedBody))
        .build()) {
    engine.add(new Article(1L, "Fast Java search")).join();

    List<Article> java = engine.search(Query.term(analyzedBody, "JAVA"));
    List<Article> any = engine.search(Query.anyTerms(analyzedBody, "java memory"));
    List<Article> all = engine.search(Query.allTerms(analyzedBody, "fast search"));
}
```

`Analyzer.simple()` applies NFKC normalization, locale-independent lowercase, and
Unicode letter/digit token boundaries. Text queries are boolean and unranked; BM25,
top-K, phrases, fuzzy search, persistence, and distributed search are not part of P4.
See the frozen [v2 analyzed-text semantics](docs/v2/phases/p4/TEXT_SEMANTICS.md) for null,
zero-token, duplicate-term, identity, and lifecycle behavior.

## BM25 ranking in the v2 development line

P5 keeps scoring separate from boolean eligibility. A ranked request contains one text
scoring query, an optional existing `Query<T>` filter, a positive K, and BM25 config:

```java
try (SearchEngine<Long, Article> engine = SearchEngine.builder(Article.class, id)
        .index(IndexDefinition.text(analyzedBody))
        .build()) {
    engine.add(new Article(1L, "Fast Java search")).join();
    RankedSearchRequest<Article> request = RankedSearchRequest.filtered(
            TextScoringQuery.of(analyzedBody, "java search"),
            Query.term(analyzedBody, "fast"),
            10
    );
    List<SearchHit<Article>> hits = engine.searchTopK(request);
}
```

The default formula uses `k1=1.2` and `b=0.75`. Hits are ordered by descending score,
then ascending internal document ID for deterministic ties. Existing
`search(Query<T>)` remains boolean, unranked, and ordered exactly as before. Ranking
requires the canonical text index; repeated query terms are deduplicated and zero-token
queries return no hits. See the frozen
[BM25 ranking semantics](docs/v2/phases/p5/RANKING_SEMANTICS.md) for the exact formula, metadata,
filter, lifecycle, and compatibility contract.

## Runtime annotation configuration

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
            engine.field("warehouse", String.class);
    engine.add(new Item(1001L, "north", 120, "Cable")).join();
    List<Item> items = engine.search(Query.eq(warehouse, "north"));
}
```

Use `SearchEngine.annotatedBuilder(...)` instead when engine configuration must be
customized before `build()`. `AnnotatedSchemaFactory` remains available as the
lower-level configuration generator.

All record components become schema fields. For ordinary classes, fields and
zero-argument getters carrying `@SearchId`, `@SearchIndex`, or `@SearchField` are
included. `@SearchField` registers a field without creating a startup index, which is
useful for analyzed text and later dynamic indexes. Private members are accepted only
when `trySetAccessible()` succeeds. Primitive member types are exposed through their
boxed classes.

Exactly one ID is required. Duplicate logical field names, an ID type mismatch, static
annotated members, invalid getters and incompatible index types fail during generation.
`EQUALITY`, `RANGE` and `PREFIX` are available.

### Runtime annotations with text and BM25

The runtime path can configure analyzed text directly without an annotation processor
or generated class:

```java
try (SearchEngine<Long, TravelPlace> engine = SearchEngine
        .annotatedBuilder(TravelPlace.class, Long.class)
        .textIndex("description", Analyzer.simple())
        .build()) {
    TextField<TravelPlace> description =
            engine.textField("description");
    Field<TravelPlace, String> city =
            engine.field("city", String.class);

    engine.addAll(List.of(museum, guide)).join();
    List<SearchHit<TravelPlace>> ranked = engine.searchTopK(
            RankedSearchRequest.filtered(
                    TextScoringQuery.of(description, "museum river art"),
                    Query.eq(city, "Paris"),
                    10));
}
```

For a normal class, mark `description` with `@SearchField`; records already include all
components, so the annotation is optional there. `textIndex(...)` explicitly selects
the Analyzer, installs the startup text index, and publishes its canonical `TextField`
through `engine.textField(...)` for boolean and ranked queries. `engine.schema()`
remains available for schema inspection and advanced configuration.

## Generated fields (optional)

Add the separate processor only when compile-time typed field constants are useful:

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-compiler-plugin</artifactId>
    <version>3.15.0</version>
    <configuration>
        <annotationProcessorPaths>
            <path>
                <groupId>io.github.patricklfdm</groupId>
                <artifactId>general-search-engine-processor</artifactId>
                <version>2.0.0</version>
            </path>
        </annotationProcessorPaths>
    </configuration>
</plugin>
```

During `mvn compile`, javac transforms:

```text
TravelPlace.java
→ target/generated-sources/annotations/TravelPlaceSearchFields.java
```

The generated companion is marked as generated and says not to edit it manually. It
contains `ID`, `CITY`, `PRICE`, `RATING`, and `DESCRIPTION`, plus a canonical `SCHEMA`
containing every record component and `INDEX_DEFINITIONS` containing only the indexes
requested by annotations. An IDE can briefly show `Cannot resolve symbol` before the
first annotation-processing build; run `mvn compile` and make sure annotation
processing is enabled in the IDE.

Top-level model types produce the predictable name `TravelPlaceSearchFields`. Nested
types join enclosing simple names with `_`: `TravelDemo.TravelPlace` produces
`TravelDemo_TravelPlaceSearchFields`. The runtime reflection quick start remains
available when generated sources are undesirable. Supported visibility, primitive
boxing, collision, and fallback rules are frozen in the
[P6 developer-experience contract](docs/v2/phases/p6/DEVELOPER_EXPERIENCE.md).

## Text and BM25 with generated fields

A normal generated schema can use the same `textIndex(...)` convenience. `Field` owns
value extraction; `TextField` adds the analyzer that defines token semantics:

```java
try (SearchEngine<Long, TravelPlace> engine =
        SearchEngine.builder(TravelPlaceSearchFields.SCHEMA)
                .indexes(TravelPlaceSearchFields.INDEX_DEFINITIONS)
                .textIndex("description", Analyzer.simple())
                .build()) {
    TextField<TravelPlace> description =
            engine.textField("description");
    TravelPlace museum = new TravelPlace(
            1L, "Paris", 120.0, 4.9, "museum museum riverside");
    TravelPlace guide = new TravelPlace(
            2L, "Paris", 90.0, 4.4, "museum city guide");
    engine.addAll(List.of(museum, guide)).join();

    List<TravelPlace> structuredAndText = engine.search(Query.and(
            Query.eq(TravelPlaceSearchFields.CITY, "Paris"),
            Query.between(TravelPlaceSearchFields.PRICE, 80.0, 130.0),
            Query.term(description, "museum")));

    List<SearchHit<TravelPlace>> ranked = engine.searchTopK(
            RankedSearchRequest.filtered(
                    TextScoringQuery.of(description, "museum"),
                    Query.eq(TravelPlaceSearchFields.CITY, "Paris"),
                    10));
}
```

The same `description` instance is used for the text index, boolean text queries, and
BM25 requests. No manual schema reconstruction is needed. Advanced callers can still
construct a `TextField` explicitly and pass `IndexDefinition.text(description)`.

## Dynamic index on a generated field

Generated record schemas include fields that do not have startup indexes. `RATING` can
therefore receive an index later without being manually registered during engine
construction:

```java
engine.createIndex(IndexDefinition.range(
        TravelPlaceSearchFields.RATING)).join();

List<TravelPlace> highlyRated = engine.search(Query.between(
        TravelPlaceSearchFields.RATING, 4.7, 5.0));
```

## Failure contract

Mutation and dynamic-index operations return `CompletableFuture<Void>`. Operational
failures are available as the cause of `CompletionException` from `join()`:

- `DocumentAlreadyExistsException`: `add` received an active business ID.
- `DocumentNotFoundException`: `update` received a missing business ID.
- `EngineRejectedExecutionException`: the engine is closed or its writer queue is full;
  inspect `reason()` for `CLOSED` or `QUEUE_FULL`.
- `BulkMutationException`: an explicit collection contains a duplicate ID or exceeds
  the configured maximum; inspect `reason()`, `batchSize()`, and related context.
- `IndexLifecycleException`: an index already exists, the same build is in progress, or
  a pending build was cancelled by `dropIndex`; inspect `reason()` and `fieldName()`.

Removing a missing ID and dropping a known field without indexes remain idempotent.
Invalid arguments and invalid builder/schema configuration fail synchronously with
`IllegalArgumentException` or `SchemaGenerationException`. A field extractor or custom
index failure remains the original build failure rather than being hidden by a generic
wrapper.

## V1 boundary semantics

The complete contract is recorded in
[v1 semantics](docs/v1/SEMANTICS.md). The important boundaries are:

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
[v1 API compatibility](docs/v1/API_COMPATIBILITY.md). Public types in low-level
implementation packages are not automatically part of that application-level promise.

## Query planning

Product category, Prime, price and name-prefix queries currently have bitmap indexes.
Rating queries are evaluated by scanning the safe candidate set. In the v2 development
tree, a direct Range query estimates first and chooses its least-cost index only when
the internal relative-work model prefers it to scanning active documents. Rejected
estimating paths are not materialized. Composite planning follows these rules:

- `AND` starts with one lowest-cost useful path and materializes an additional exact
  path only when it guarantees enough reduced verification work; otherwise final
  predicate evaluation handles skipped children through a safe superset.
- `OR` uses a bitmap only when every child can provide a safe candidate set.
- `NOT` uses a bitmap complement only when its child result is exact.
- Every candidate document is evaluated by `Query.matches`, regardless of the
  planner result.

The generic builder accepts an additive planner configuration without changing
`SnapshotEngineConfig`:

```java
.plannerConfig(new PlannerConfig(RangePlanningMode.COST_AWARE))
```

`FORCE_INDEX` and `FORCE_SCAN` are regression/benchmark controls. They preserve query
truth and are not recommendations for a universal crossover. Cost-aware OR/NOT is not
part of P3.

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

The suite contains 51 benchmark methods in twenty groups:

- `ProductQueryBenchmark`: Equality, Range, Prefix, indexed composite and unindexed
  range-scan throughput.
- `ProductMutationBenchmark`: end-to-end single update and 100-update batch
  publication latency. The batch result is normalized per document operation.
- `DynamicIndexBuildBenchmark`: end-to-end Rating Range/Equality build, publication
  and drop latency.
- `RangeIndexComparisonBenchmark`: cost-aware, forced-index, and forced-scan Range
  execution at controlled selectivities, plus candidate-only construction.
- `MutationBatchScalingBenchmark`: total latency and allocation for 1, 10, 100, and
  1,000 updates with a one-publication assertion.
- `RangeEstimateBenchmark`: direct Range estimate versus candidate materialization at
  0.01%, 0.1%, 1%, 10%, 25%, 50%, and 100% selectivity.
- `RangeBucketSpreadBenchmark`: equal-selectivity estimate/materialization with 100,
  10,000, and 100,000 distinct values.
- `AndPlannerBenchmark`: conservative AND versus scan under positive, negative, and
  independent-like child correlation.
- `IndexStatisticsPublicationBenchmark`: direct Range index publication at equal
  document count with low and high distinct-key counts.
- `BitmapUnionBenchmark`: repeated immutable union versus P2 single-freeze
  accumulation across selectivity, source-count, and overlap dimensions.
- `DictionaryStrategyBenchmark`: bounded overlay, persistent AVL, and full-copy
  publication controls across dictionary size, dirty count, and removal histories.
- `DictionaryLookupBenchmark`: point lookup at compacted and maximum overlay depth.
- `TextTermQueryBenchmark`: posting lookup, indexed term search, and analyzed scan by
  document frequency.
- `TextMultiTermQueryBenchmark`: indexed/scanned any/all analyzed-term queries.
- `TextIndexPublicationBenchmark`: text dictionary publication by vocabulary and batch.
- `TextIndexBuildBenchmark`: raw and dynamic text index construction.
- `Bm25TopKBenchmark`: bounded top-K retention versus exhaustive full sort.
- `Bm25MultiTermBenchmark`: single/multi-term BM25 with structured filtering.
- `RankedMetadataPublicationBenchmark`: posting plus document-length publication.
- `ExplicitBulkMutationBenchmark`: successful atomic publication and invalid rollback.

The diagnostic round-two protocol and IntelliJ terminal commands are documented in
[v1 JMH diagnostic round 2](docs/v1/JMH_DIAGNOSTIC_ROUND_2.md).
The accepted P1 results are recorded in
[P1 performance baseline](docs/v2/phases/p1/PERFORMANCE_BASELINE.md).
The accepted P2 results and D3 representation decision are recorded in
[P2 performance baseline](docs/v2/phases/p2/PERFORMANCE_BASELINE.md).
The accepted P3 planner results and commands are recorded in
[P3 performance baseline](docs/v2/phases/p3/PERFORMANCE_BASELINE.md).
The accepted analyzed-text, ranking, and explicit-bulk matrices are recorded in the
[P4](docs/v2/phases/p4/PERFORMANCE_BASELINE.md),
[P5](docs/v2/phases/p5/PERFORMANCE_BASELINE.md), and
[P6](docs/v2/phases/p6/PERFORMANCE_BASELINE.md) baselines. The accepted P7 representative
rerun is recorded in [P7 performance baseline](docs/v2/phases/p7/PERFORMANCE_BASELINE.md);
the soak evidence is in [P7 release validation](docs/v2/phases/p7/RELEASE_VALIDATION.md).

The original baseline groups default to 10,000 documents, while the round-two
diagnostic groups default to 100,000. All groups use two forked JVMs, explicit warmup
and five measurement iterations. Override the data size and select a group using JMH
options:

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
  io.github.patricklfdm.generalsearch.benchmark.ProductFilterBenchmark \
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
  io.github.patricklfdm.generalsearch.benchmark.ProductEngineConcurrencyStress \
  --products=100000 --readers=8 --writers=2 --seconds=300 --seed=42
```

All arguments are optional. Defaults are 100,000 products, up to 8 readers, 2 writers,
60 seconds and seed 42. The runner continuously mixes indexed and unindexed queries,
add/update/remove mutations, and concurrent Range/Equality index builds followed by
drop operations. It prints query and mutation throughput only after the worker checks
and final oracle comparison pass. This is a correctness-oriented soak runner rather
than a statistically rigorous microbenchmark; use the JMH suite above for stable
performance and allocation baselines.

## License

GeneralSearchEngine v1.0.0 is licensed under the
[Apache License 2.0](LICENSE).
