package org.example.generalsearch.benchmark;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.concurrent.CompletableFuture;
import org.example.generalsearch.engine.SnapshotEngineConfig;
import org.example.generalsearch.engine.SnapshotUpdateEngine;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;
import org.example.generalsearch.query.Query;

/**
 * Lightweight engineering smoke benchmark. Use JMH for publishable results.
 */
public final class ProductFilterBenchmark {
    private ProductFilterBenchmark() {}

    public static void main(String[] args) {
        int productCount = intArg(args, "--products", 100_000);
        int queryCount = intArg(args, "--queries", 100_000);
        Random random = new Random(42);
        List<Query<Product>> queries = queries(queryCount, productCount, random);
        long memoryBeforeLoad = usedMemory();
        long loadStarted = System.nanoTime();

        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine(
                new SnapshotEngineConfig(100_000, 1_000, Duration.ofMillis(2)))) {
            List<CompletableFuture<Void>> pending = new ArrayList<>(1_000);
            for (int docId = 0; docId < productCount; docId++) {
                pending.add(engine.add(product(docId, random)));
                if (pending.size() == 1_000) {
                    CompletableFuture.allOf(pending.toArray(CompletableFuture[]::new)).join();
                    pending.clear();
                }
            }
            CompletableFuture.allOf(pending.toArray(CompletableFuture[]::new)).join();
            double loadMillis = (System.nanoTime() - loadStarted) / 1_000_000.0;
            double approximateMemoryMiB = Math.max(
                    0,
                    usedMemory() - memoryBeforeLoad
            ) / (1024.0 * 1024.0);

            long checksum = 0;
            long started = System.nanoTime();
            for (Query<Product> query : queries) {
                checksum += engine.search(query).size();
            }
            double seconds = (System.nanoTime() - started) / 1_000_000_000.0;
            System.out.printf(Locale.US,
                    "products=%,d queries=%,d load=%,.1f ms "
                            + "approx_memory=%,.1f MiB throughput=%,.0f q/s checksum=%d%n",
                    productCount,
                    queryCount,
                    loadMillis,
                    approximateMemoryMiB,
                    queryCount / seconds,
                    checksum);
        }
    }

    private static Product product(int docId, Random random) {
        return new Product(
                "p" + docId,
                "Product " + docId,
                Category.values()[random.nextInt(Category.values().length)],
                random.nextInt(1_000),
                random.nextBoolean(),
                1 + random.nextDouble() * 4
        );
    }

    private static List<Query<Product>> queries(
            int count,
            int productCount,
            Random random
    ) {
        List<Query<Product>> filters = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            Category category = Category.values()[random.nextInt(Category.values().length)];
            filters.add(switch (random.nextInt(5)) {
                case 0 -> Query.eq(ProductFields.CATEGORY, category);
                case 1 -> Query.eq(ProductFields.PRIME, random.nextBoolean());
                case 2 -> Query.between(
                        ProductFields.PRICE,
                        (double) random.nextInt(500),
                        (double) (500 + random.nextInt(500)));
                case 3 -> Query.and(
                        Query.eq(ProductFields.CATEGORY, category),
                        Query.eq(ProductFields.PRIME, random.nextBoolean()));
                default -> Query.prefix(
                        ProductFields.NAME,
                        "Product " + random.nextInt(productCount));
            });
        }
        return List.copyOf(filters);
    }

    private static long usedMemory() {
        Runtime runtime = Runtime.getRuntime();
        return runtime.totalMemory() - runtime.freeMemory();
    }

    private static int intArg(String[] args, String name, int fallback) {
        String prefix = name + "=";
        for (String arg : args) {
            if (arg.startsWith(prefix)) {
                return Integer.parseInt(arg.substring(prefix.length()));
            }
        }
        return fallback;
    }
}
