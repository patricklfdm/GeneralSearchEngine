package org.example.generalsearch.differential;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.time.Duration;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import org.example.generalsearch.engine.SnapshotUpdateEngine;
import org.example.generalsearch.engine.SnapshotEngineConfig;
import org.example.generalsearch.filter.AndFilter;
import org.example.generalsearch.filter.CategoryFilter;
import org.example.generalsearch.filter.NameFilter;
import org.example.generalsearch.filter.OrFilter;
import org.example.generalsearch.filter.PriceRangeFilter;
import org.example.generalsearch.filter.PrimeFilter;
import org.example.generalsearch.filter.ProductFilter;
import org.example.generalsearch.filter.RatingFilter;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.junit.jupiter.api.Test;

class SearchDifferentialTest {
    @Test
    void indexedSearchAgreesWithFullScanAcrossRandomMutations() {
        Random random = new Random(42);
        Product[] oracle = new Product[1_000];
        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine(
                new SnapshotEngineConfig(10_000, 1_000, Duration.ZERO))) {
            for (int docId = 0; docId < oracle.length; docId++) {
                Product product = randomProduct(docId, random);
                oracle[docId] = product;
                engine.add(docId, product).join();
            }

            for (int operation = 0; operation < 2_000; operation++) {
                int docId = random.nextInt(oracle.length);
                if (oracle[docId] == null) {
                    Product product = randomProduct(docId, random);
                    oracle[docId] = product;
                    engine.add(docId, product).join();
                } else if (random.nextInt(5) == 0) {
                    oracle[docId] = null;
                    engine.remove(docId).join();
                } else {
                    Product product = randomProduct(docId, random);
                    oracle[docId] = product;
                    engine.update(docId, product).join();
                }

                if (operation % 25 == 0) {
                    for (int query = 0; query < 10; query++) {
                        ProductFilter filter = randomFilter(random);
                        assertEquals(fullScan(oracle, filter), ids(engine.search(filter)));
                    }
                }
            }
        }
    }

    private static Product randomProduct(int docId, Random random) {
        Category category = Category.values()[random.nextInt(Category.values().length)];
        return new Product(
                "p" + docId,
                (random.nextBoolean() ? "Alpha " : "Beta ") + docId,
                category,
                random.nextInt(500),
                random.nextBoolean(),
                1 + random.nextDouble() * 4
        );
    }

    private static ProductFilter randomFilter(Random random) {
        Category category = Category.values()[random.nextInt(Category.values().length)];
        return switch (random.nextInt(7)) {
            case 0 -> new CategoryFilter(category);
            case 1 -> new PrimeFilter(random.nextBoolean());
            case 2 -> new PriceRangeFilter(50, 200);
            case 3 -> new NameFilter("Alpha");
            case 4 -> new RatingFilter(3.5);
            case 5 -> new AndFilter(List.of(
                    new CategoryFilter(category), new PriceRangeFilter(10, 300)));
            default -> new OrFilter(List.of(
                    new CategoryFilter(category), new PrimeFilter(random.nextBoolean())));
        };
    }

    private static Set<String> fullScan(Product[] products, ProductFilter filter) {
        Set<String> ids = new HashSet<>();
        for (Product product : products) {
            if (product != null && filter.matches(product)) {
                ids.add(product.id());
            }
        }
        return ids;
    }

    private static Set<String> ids(List<Product> products) {
        Set<String> ids = new HashSet<>();
        products.forEach(product -> ids.add(product.id()));
        return ids;
    }
}
