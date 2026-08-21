package org.example.generalsearch.benchmark;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.concurrent.CompletableFuture;
import org.example.generalsearch.engine.SnapshotEngineConfig;
import org.example.generalsearch.engine.SnapshotUpdateEngine;
import org.example.generalsearch.filter.AndFilter;
import org.example.generalsearch.filter.CategoryFilter;
import org.example.generalsearch.filter.PriceRangeFilter;
import org.example.generalsearch.filter.PrimeFilter;
import org.example.generalsearch.filter.ProductFilter;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;

/**
 * Lightweight engineering smoke benchmark. Use JMH for publishable results.
 */
public final class ProductFilterBenchmark {
    private ProductFilterBenchmark() {}

    public static void main(String[] args) {
        int productCount = intArg(args, "--products", 100_000);
        int queryCount = intArg(args, "--queries", 100_000);
        Random random = new Random(42);
        List<ProductFilter> queries = queries(queryCount, random);

        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine(
                new SnapshotEngineConfig(100_000, 1_000, Duration.ofMillis(2)))) {
            List<CompletableFuture<Void>> pending = new ArrayList<>(1_000);
            for (int docId = 0; docId < productCount; docId++) {
                pending.add(engine.add(docId, product(docId, random)));
                if (pending.size() == 1_000) {
                    CompletableFuture.allOf(pending.toArray(CompletableFuture[]::new)).join();
                    pending.clear();
                }
            }
            CompletableFuture.allOf(pending.toArray(CompletableFuture[]::new)).join();

            long checksum = 0;
            long started = System.nanoTime();
            for (ProductFilter query : queries) {
                checksum += engine.search(query).size();
            }
            double seconds = (System.nanoTime() - started) / 1_000_000_000.0;
            System.out.printf(Locale.US,
                    "products=%,d queries=%,d throughput=%,.0f q/s checksum=%d%n",
                    productCount, queryCount, queryCount / seconds, checksum);
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

    private static List<ProductFilter> queries(int count, Random random) {
        List<ProductFilter> filters = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            Category category = Category.values()[random.nextInt(Category.values().length)];
            filters.add(switch (random.nextInt(4)) {
                case 0 -> new CategoryFilter(category);
                case 1 -> new PrimeFilter(random.nextBoolean());
                case 2 -> new PriceRangeFilter(random.nextInt(500), 500 + random.nextInt(500));
                default -> new AndFilter(List.of(
                        new CategoryFilter(category), new PrimeFilter(random.nextBoolean())));
            });
        }
        return List.copyOf(filters);
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
