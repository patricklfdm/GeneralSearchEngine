package io.github.patricklfdm.generalsearch.differential;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.time.Duration;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import io.github.patricklfdm.generalsearch.engine.SnapshotUpdateEngine;
import io.github.patricklfdm.generalsearch.engine.SnapshotEngineConfig;
import io.github.patricklfdm.generalsearch.model.Category;
import io.github.patricklfdm.generalsearch.model.Product;
import io.github.patricklfdm.generalsearch.model.ProductFields;
import io.github.patricklfdm.generalsearch.query.Query;
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
                engine.add(product).join();
            }

            for (int operation = 0; operation < 2_000; operation++) {
                int docId = random.nextInt(oracle.length);
                if (oracle[docId] == null) {
                    Product product = randomProduct(docId, random);
                    oracle[docId] = product;
                    engine.add(product).join();
                } else if (random.nextInt(5) == 0) {
                    oracle[docId] = null;
                    engine.remove("p" + docId).join();
                } else {
                    Product product = randomProduct(docId, random);
                    oracle[docId] = product;
                    engine.update(product).join();
                }

                if (operation % 25 == 0) {
                    for (int query = 0; query < 10; query++) {
                        Query<Product> querySpec = randomQuery(random);
                        assertEquals(fullScan(oracle, querySpec), ids(engine.search(querySpec)));
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

    private static Query<Product> randomQuery(Random random) {
        Category category = Category.values()[random.nextInt(Category.values().length)];
        return switch (random.nextInt(7)) {
            case 0 -> Query.eq(ProductFields.CATEGORY, category);
            case 1 -> Query.eq(ProductFields.PRIME, random.nextBoolean());
            case 2 -> Query.between(ProductFields.PRICE, 50.0, 200.0);
            case 3 -> Query.prefix(ProductFields.NAME, "Alpha");
            case 4 -> Query.between(ProductFields.RATING, 3.5, 5.0);
            case 5 -> Query.and(
                    Query.eq(ProductFields.CATEGORY, category),
                    Query.between(ProductFields.PRICE, 10.0, 300.0));
            default -> Query.or(
                    Query.eq(ProductFields.CATEGORY, category),
                    Query.eq(ProductFields.PRIME, random.nextBoolean()));
        };
    }

    private static Set<String> fullScan(Product[] products, Query<Product> query) {
        Set<String> ids = new HashSet<>();
        for (Product product : products) {
            if (product != null && query.matches(product)) {
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
