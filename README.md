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
├── schema      Type-safe fields and document schemas
├── filter      Compatibility layer for former Product filters
├── bitmap      Persistent tree and immutable bitmap primitives
├── index       Immutable field indexes and batch builders
├── storage     Generic document tables and immutable search snapshots
├── query       Candidate planning and final result evaluation
└── engine      Public API, mutation queue and snapshot publication
```

Dependencies flow from the engine toward the lower-level packages. The bitmap package
is domain-independent, storage and query components operate on any document type `T`,
and indexes advertise their own query capabilities. Product defaults are assembled only
at the Product engine boundary.

## Basic usage

```java
import java.util.List;
import org.example.generalsearch.engine.SnapshotUpdateEngine;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;
import org.example.generalsearch.query.Query;

try (var engine = new SnapshotUpdateEngine()) {
    engine.add(0, new Product(
            "p1", "Laptop", Category.ELECTRONICS, 999.99, true, 4.7
    )).join();

    List<Product> products = engine.search(Query.and(
            Query.eq(ProductFields.CATEGORY, Category.ELECTRONICS),
            Query.between(ProductFields.PRICE, 500.0, 1_500.0)
    ));
}
```

`ProductFields` contains the canonical `Field<Product, V>` definitions and a complete
`SearchSchema<Product>`. Field extractors keep the query DSL type-safe without runtime
reflection. The old `ProductFilter` types remain temporarily source-compatible but are
deprecated; new code should use `Query<T>`.

Mutation methods are asynchronous. Completion means the mutation is visible in the
published snapshot. Mutations submitted through one engine are applied in submission
order. Closing the engine stops new submissions, drains accepted mutations and waits
for the writer thread to finish.

`SnapshotEngineConfig` controls queue capacity, maximum batch size and maximum batch
wait. The default is a 100,000-item queue, batches of up to 1,000 mutations and a 5 ms
batch window.

## Generic storage and search

`DocumentTable<T>`, `SearchSnapshot<T>`, `CandidatePlanner<T>` and
`SnapshotSearcher<T>` form the domain-independent search chain. A second document type
can use it by defining fields and startup indexes:

```java
Field<Item, String> warehouse =
        Field.of("warehouse", String.class, Item::warehouse);
Field<Item, Integer> quantity =
        Field.of("quantity", Integer.class, Item::quantity);

var snapshot = new SearchSnapshot<Item>(List.of(
        IndexDefinition.equality(warehouse),
        IndexDefinition.range(quantity)
));
snapshot = snapshot.add(0, new Item("sku-1", "north", 120));

var searcher = new SnapshotSearcher<Item>();
List<Item> items = searcher.search(snapshot, Query.and(
        Query.eq(warehouse, "north"),
        Query.between(quantity, 100, 200)
));
```

The asynchronous public engine is still Product-specific. Generalizing that boundary
and mapping business IDs to internal document IDs is the next development phase.

## Query planning

Product category, Prime and price queries currently have bitmap indexes. Name-prefix
and rating queries are evaluated by scanning the safe candidate set. Composite planning
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

Built-in indexes can be selected dynamically when the engine starts:

```java
var indexes = List.<IndexDefinition<Product>>of(
        IndexDefinition.equality(ProductFields.CATEGORY),
        IndexDefinition.equality(ProductFields.PRIME),
        IndexDefinition.range(ProductFields.PRICE),
        IndexDefinition.range(ProductFields.RATING)
);

var engine = new SnapshotUpdateEngine(SnapshotEngineConfig.DEFAULT, indexes);
```

`EqualityIndex` works with enums, booleans, strings and other exact values. `RangeIndex`
works with `Comparable` values and also answers exact equality queries. Adding another
field with either built-in index does not require changes to SearchSnapshot or
CandidatePlanner.

To add a new index algorithm:

1. Implement `IndexDefinition<T>`, `IndexSnapshot<T>` and `IndexBuilder<T>`.
2. Let the snapshot report candidates for the query types it supports.
3. Register the definition when creating the engine.
4. Add mutation, snapshot-isolation and randomized differential tests.

## Engineering benchmark

The repository retains a lightweight smoke benchmark. It is useful for local regression
checks but is not a replacement for JMH.

```bash
mvn test-compile
java -cp target/classes:target/test-classes \
  org.example.generalsearch.benchmark.ProductFilterBenchmark \
  --products=100000 --queries=100000
```
