# GeneralSearchEngine

GeneralSearchEngine is a Java 21 in-memory product search engine. It uses immutable
catalog snapshots and persistent, block-based bitmaps so readers can search without
locking while a single writer batches mutations and atomically publishes new snapshots.

## Requirements

- JDK 21 or newer
- Maven 3.9 or newer

## Build and test

```bash
mvn test
```

The test suite contains unit tests for the persistent tree, immutable bitmap, catalog,
query planner and engine lifecycle, plus a randomized differential test against a full
scan oracle.

## Package layout

```text
org.example.generalsearch
├── model       Product domain types
├── filter      Simple and composite query predicates
├── bitmap      Persistent tree and immutable bitmap primitives
├── index       Immutable field indexes and batch builders
├── catalog     Product storage and complete catalog snapshots
├── query       Candidate planning and final result evaluation
└── engine      Public API, mutation queue and snapshot publication
```

Dependencies flow from the engine toward the lower-level packages. The bitmap package
is domain-independent, indexes do not interpret filters, and query planning is kept out
of the catalog model.

## Basic usage

```java
import java.util.List;
import org.example.generalsearch.engine.SnapshotUpdateEngine;
import org.example.generalsearch.filter.AndFilter;
import org.example.generalsearch.filter.CategoryFilter;
import org.example.generalsearch.filter.PriceRangeFilter;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;

try (var engine = new SnapshotUpdateEngine()) {
    engine.add(0, new Product(
            "p1", "Laptop", Category.ELECTRONICS, 999.99, true, 4.7
    )).join();

    List<Product> products = engine.search(new AndFilter(List.of(
            new CategoryFilter(Category.ELECTRONICS),
            new PriceRangeFilter(500, 1_500)
    )));
}
```

Mutation methods are asynchronous. Completion means the mutation is visible in the
published snapshot. Mutations submitted through one engine are applied in submission
order. Closing the engine stops new submissions, drains accepted mutations and waits
for the writer thread to finish.

`SnapshotEngineConfig` controls queue capacity, maximum batch size and maximum batch
wait. The default is a 100,000-item queue, batches of up to 1,000 mutations and a 5 ms
batch window.

## Query planning

Category, Prime and price-range filters currently have bitmap indexes. Name and rating
filters are evaluated by scanning the safe candidate set. Composite planning follows
these rules:

- `AND` can use any indexed children and returns a safe superset when some children are
  not indexed.
- `OR` uses a bitmap only when every child can provide a safe candidate set.
- `NOT` uses a bitmap complement only when its child result is exact.
- Every candidate product is evaluated by `ProductFilter.matches`, regardless of the
  planner result.

## Adding a filter or index

To add an unindexed filter:

1. Add a `ProductFilter` implementation in `filter`.
2. Implement its `matches(Product)` behavior.
3. Add direct and composite-query tests. The searcher will safely fall back to scanning.

To index that filter as well:

1. Add an immutable snapshot and batch builder in `index`.
2. Add the index to `CatalogSnapshot` and `CatalogSnapshotBuilder`.
3. Teach `CandidatePlanner` how to produce an `EXACT` or `SUPERSET` candidate bitmap.
4. Add mutation regression tests and randomized differential coverage.

## Engineering benchmark

The repository retains a lightweight smoke benchmark. It is useful for local regression
checks but is not a replacement for JMH.

```bash
mvn test-compile
java -cp target/classes:target/test-classes \
  org.example.generalsearch.benchmark.ProductFilterBenchmark \
  --products=100000 --queries=100000
```
