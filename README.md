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

`SearchEngine<K,T>` is implemented by `SnapshotSearchEngine<K,T>`. A document type only
needs a typed ID field, a schema and its startup indexes:

```java
record Item(Long id, String warehouse, int quantity) {}

Field<Item, Long> id = Field.of("id", Long.class, Item::id);
Field<Item, String> warehouse =
        Field.of("warehouse", String.class, Item::warehouse);
Field<Item, Integer> quantity =
        Field.of("quantity", Integer.class, Item::quantity);

SearchSchema<Item, Long> schema = SearchSchema.builder(Item.class, id)
        .field(warehouse)
        .field(quantity)
        .build();

try (SearchEngine<Long, Item> engine = new SnapshotSearchEngine<>(
        schema,
        List.of(
                IndexDefinition.equality(warehouse),
                IndexDefinition.range(quantity)
        ))) {
    engine.add(new Item(1001L, "north", 120)).join();
    List<Item> items = engine.search(Query.and(
            Query.eq(warehouse, "north"),
            Query.between(quantity, 100, 200)
    ));
}
```

`DocumentTable<T>`, `SearchSnapshot<T>`, `CandidatePlanner<T>` and
`SnapshotSearcher<T>` remain the lower-level domain-independent search chain.
`SnapshotUpdateEngine` is the Product convenience boundary that supplies Product's
schema and default indexes while retaining the deprecated ProductFilter adapter.

## Annotation-generated configuration

`AnnotatedSchemaFactory` generates a normal `SearchSchema<T,K>` and startup index
definitions. Reflection is limited to member discovery and startup validation; member
extractors are pre-bound as method handles.

```java
record Item(
        @SearchId Long id,
        @SearchIndex(IndexType.EQUALITY) String warehouse,
        @SearchIndex(IndexType.RANGE) int quantity,
        String name
) {}

AnnotatedSearchConfiguration<Item, Long> configuration =
        AnnotatedSchemaFactory.create(Item.class, Long.class);

Field<Item, String> warehouse =
        configuration.schema().requireField("warehouse", String.class);

try (SearchEngine<Long, Item> engine = new SnapshotSearchEngine<>(
        configuration.schema(), configuration.indexDefinitions())) {
    engine.add(new Item(1001L, "north", 120, "Cable")).join();
    List<Item> items = engine.search(Query.eq(warehouse, "north"));
}
```

All record components become schema fields. For ordinary classes, only fields and
zero-argument getters carrying `@SearchId` or `@SearchIndex` are included. Private
members are accepted only when `trySetAccessible()` succeeds. Primitive member types
are exposed through their boxed classes.

Exactly one ID is required. Duplicate logical field names, an ID type mismatch, static
annotated members, invalid getters and incompatible index types fail during generation.
`EQUALITY`, `RANGE` and `PREFIX` are available.

Prefix matching intentionally has the same semantics as `String.startsWith`: it is
case-sensitive, performs no Locale conversion or Unicode normalization, and indexes
raw UTF-16 strings. Canonically equivalent strings such as precomposed and decomposed
accented text remain distinct. Null field values are not indexed; an empty prefix
matches every non-null value.

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

## Engineering benchmark

The repository retains a lightweight smoke benchmark covering all Product default
indexes, including name prefixes. It reports total load time, approximate memory growth
and mixed-query throughput. These values are useful for local regression checks but are
not a replacement for JMH or a memory profiler.

```bash
mvn test-compile
java -cp target/classes:target/test-classes \
  org.example.generalsearch.benchmark.ProductFilterBenchmark \
  --products=100000 --queries=100000
```
