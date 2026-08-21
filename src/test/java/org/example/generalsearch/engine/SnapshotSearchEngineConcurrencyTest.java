package org.example.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReferenceArray;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;
import org.example.generalsearch.query.Query;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

class SnapshotSearchEngineConcurrencyTest {
    private static final int PRODUCT_COUNT = 240;
    private static final int WRITER_COUNT = 2;

    @Test
    @Timeout(20)
    void readersRemainSafeDuringMutationsAndDynamicIndexChanges() throws Exception {
        AtomicReferenceArray<Product> oracle = new AtomicReferenceArray<>(PRODUCT_COUNT);
        SnapshotEngineConfig config =
                new SnapshotEngineConfig(10_000, 64, Duration.ofMillis(1));

        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine(config)) {
            for (int slot = 0; slot < PRODUCT_COUNT; slot++) {
                Product product = product(slot, 0);
                engine.add(product).join();
                oracle.set(slot, product);
            }

            int readerCount = 4;
            ExecutorService workers = Executors.newFixedThreadPool(
                    readerCount + WRITER_COUNT + 1);
            CountDownLatch start = new CountDownLatch(1);
            List<Future<?>> tasks = new ArrayList<>();
            try {
                for (int reader = 0; reader < readerCount; reader++) {
                    int seed = 1_000 + reader;
                    tasks.add(workers.submit(() -> runReader(engine, start, seed)));
                }
                for (int writer = 0; writer < WRITER_COUNT; writer++) {
                    int writerId = writer;
                    tasks.add(workers.submit(
                            () -> runWriter(engine, oracle, start, writerId)));
                }
                tasks.add(workers.submit(() -> manageIndexes(engine, start)));

                start.countDown();
                for (Future<?> task : tasks) {
                    task.get(15, TimeUnit.SECONDS);
                }
            } finally {
                workers.shutdownNow();
                assertTrue(workers.awaitTermination(5, TimeUnit.SECONDS));
            }

            for (Query<Product> query : verificationQueries()) {
                assertEquals(fullScan(oracle, query), ids(engine.search(query)));
            }
        }
    }

    private static void runReader(
            SnapshotUpdateEngine engine,
            CountDownLatch start,
            int seed
    ) {
        await(start);
        Random random = new Random(seed);
        for (int queryNumber = 0; queryNumber < 500; queryNumber++) {
            Query<Product> query = randomQuery(random);
            List<Product> result = engine.search(query);
            Set<String> ids = new HashSet<>();
            for (Product product : result) {
                assertTrue(query.matches(product),
                        () -> "query returned a non-matching product: " + product.id());
                assertTrue(ids.add(product.id()),
                        () -> "query returned a duplicate product: " + product.id());
            }
        }
    }

    private static void runWriter(
            SnapshotUpdateEngine engine,
            AtomicReferenceArray<Product> oracle,
            CountDownLatch start,
            int writerId
    ) {
        await(start);
        for (int operation = 0; operation < 160; operation++) {
            int ownedSlot = operation % (PRODUCT_COUNT / WRITER_COUNT);
            int slot = ownedSlot * WRITER_COUNT + writerId;
            Product current = oracle.get(slot);
            if (operation % 11 == 0 && current != null) {
                engine.remove(current.id()).join();
                oracle.set(slot, null);
            } else {
                Product replacement = product(slot, operation + 1);
                if (current == null) {
                    engine.add(replacement).join();
                } else {
                    engine.update(replacement).join();
                }
                oracle.set(slot, replacement);
            }
        }
    }

    private static void manageIndexes(
            SnapshotUpdateEngine engine,
            CountDownLatch start
    ) {
        await(start);
        CompletableFuture<Void> range =
                engine.createIndex(IndexDefinition.range(ProductFields.RATING));
        CompletableFuture<Void> equality =
                engine.createIndex(IndexDefinition.equality(ProductFields.RATING));
        CompletableFuture.allOf(range, equality).join();
        engine.dropIndex(ProductFields.RATING.name()).join();
        engine.createIndex(IndexDefinition.range(ProductFields.RATING)).join();
    }

    private static void await(CountDownLatch latch) {
        try {
            latch.await();
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("concurrency test was interrupted", failure);
        }
    }

    private static Product product(int slot, int revision) {
        return new Product(
                "p" + slot,
                (revision % 2 == 0 ? "Product " : "Updated ") + slot,
                Category.values()[(slot + revision) % Category.values().length],
                (slot * 17L + revision * 13L) % 1_000,
                (slot + revision) % 2 == 0,
                1.0 + ((slot * 7L + revision * 3L) % 40) / 10.0
        );
    }

    private static Query<Product> randomQuery(Random random) {
        Category category =
                Category.values()[random.nextInt(Category.values().length)];
        return switch (random.nextInt(8)) {
            case 0 -> Query.eq(ProductFields.CATEGORY, category);
            case 1 -> Query.eq(ProductFields.PRIME, random.nextBoolean());
            case 2 -> Query.between(ProductFields.PRICE, 100.0, 700.0);
            case 3 -> Query.between(ProductFields.RATING, 3.0, 4.5);
            case 4 -> Query.prefix(ProductFields.NAME, "Product 1");
            case 5 -> Query.and(
                    Query.eq(ProductFields.CATEGORY, category),
                    Query.between(ProductFields.RATING, 2.5, 5.0));
            case 6 -> Query.or(
                    Query.eq(ProductFields.PRIME, true),
                    Query.prefix(ProductFields.NAME, "Updated 2"));
            default -> Query.not(Query.eq(ProductFields.CATEGORY, category));
        };
    }

    private static List<Query<Product>> verificationQueries() {
        return List.of(
                Query.matchAll(),
                Query.eq(ProductFields.CATEGORY, Category.ELECTRONICS),
                Query.eq(ProductFields.PRIME, true),
                Query.between(ProductFields.PRICE, 100.0, 700.0),
                Query.between(ProductFields.RATING, 3.0, 4.5),
                Query.prefix(ProductFields.NAME, "Updated 1"),
                Query.and(
                        Query.eq(ProductFields.CATEGORY, Category.BOOKS),
                        Query.between(ProductFields.RATING, 2.0, 5.0)),
                Query.not(Query.eq(ProductFields.CATEGORY, Category.CLOTHING))
        );
    }

    private static Set<String> fullScan(
            AtomicReferenceArray<Product> documents,
            Query<Product> query
    ) {
        Set<String> matches = new HashSet<>();
        for (int slot = 0; slot < documents.length(); slot++) {
            Product product = documents.get(slot);
            if (product != null && query.matches(product)) {
                matches.add(product.id());
            }
        }
        return matches;
    }

    private static Set<String> ids(List<Product> documents) {
        Set<String> ids = new HashSet<>();
        documents.forEach(product -> ids.add(product.id()));
        return ids;
    }
}
