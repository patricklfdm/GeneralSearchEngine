package org.example.generalsearch.catalog;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;
import org.example.generalsearch.query.Query;
import org.junit.jupiter.api.Test;

class CatalogSnapshotTest {
    @Test
    void updatesAllIndexesAndPreservesPreviousSnapshot() {
        Product original = product("p1", Category.BOOKS, 10, true);
        Product updated = product("p1", Category.ELECTRONICS, 25, false);
        CatalogSnapshot first = new CatalogSnapshot().add(50_000, original);
        CatalogSnapshot second = first.update(50_000, updated);

        assertEquals(original, first.get(50_000));
        assertEquals(updated, second.get(50_000));
        assertTrue(hasCandidate(first, Query.eq(ProductFields.PRICE, 10.0), 50_000));
        assertFalse(hasCandidate(second, Query.eq(ProductFields.PRICE, 10.0), 50_000));
        assertTrue(hasCandidate(second, Query.eq(ProductFields.PRICE, 25.0), 50_000));
        assertTrue(hasCandidate(second, Query.eq(ProductFields.PRIME, false), 50_000));
        assertTrue(hasCandidate(
                second,
                Query.eq(ProductFields.CATEGORY, Category.ELECTRONICS),
                50_000
        ));
    }

    @Test
    void builderAppliesAnOrderedBatchAtomically() {
        CatalogSnapshotBuilder builder = new CatalogSnapshotBuilder(new CatalogSnapshot());
        builder.add(0, product("p0", Category.HOME, 30, false));
        builder.update(0, product("p0", Category.HOME, 35, true));
        builder.add(2_000, product("p2", Category.BEAUTY, 50, false));
        builder.remove(2_000);
        CatalogSnapshot snapshot = builder.build();

        assertEquals(35, snapshot.get(0).price());
        assertTrue(hasCandidate(snapshot, Query.eq(ProductFields.PRIME, true), 0));
        assertNull(snapshot.get(2_000));
    }

    private static boolean hasCandidate(
            CatalogSnapshot snapshot,
            Query<Product> query,
            int docId
    ) {
        return snapshot.indexes().candidates(query).orElseThrow().bitmap().get(docId);
    }

    private static Product product(String id, Category category, double price, boolean prime) {
        return new Product(id, "Product " + id, category, price, prime, 4.5);
    }
}
