package org.example.generalsearch.query;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.example.generalsearch.catalog.CatalogSnapshot;
import org.example.generalsearch.filter.AndFilter;
import org.example.generalsearch.filter.CategoryFilter;
import org.example.generalsearch.filter.NameFilter;
import org.example.generalsearch.filter.NotFilter;
import org.example.generalsearch.filter.OrFilter;
import org.example.generalsearch.filter.PriceRangeFilter;
import org.example.generalsearch.filter.RatingFilter;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class CandidatePlannerTest {
    private final CandidatePlanner planner = new CandidatePlanner();
    private CatalogSnapshot snapshot;

    @BeforeEach
    void buildCatalog() {
        snapshot = new CatalogSnapshot()
                .add(0, product("p0", "Laptop", Category.ELECTRONICS, 999, 4.8))
                .add(1, product("p1", "Book", Category.BOOKS, 25, 4.9))
                .add(2, product("p2", "Mouse", Category.ELECTRONICS, 40, 3.0));
    }

    @Test
    void priceRangeUsesItsIndex() {
        CandidateResult result = planner.plan(snapshot, new PriceRangeFilter(20, 50)).orElseThrow();
        assertEquals(CandidateAccuracy.EXACT, result.accuracy());
        assertEquals(2, result.bitmap().cardinality());
        assertTrue(result.bitmap().get(1));
        assertTrue(result.bitmap().get(2));
    }

    @Test
    void andWithAnUnindexedFilterReturnsASuperset() {
        CandidateResult result = planner.plan(snapshot, new AndFilter(List.of(
                new CategoryFilter(Category.ELECTRONICS),
                new RatingFilter(4.0)
        ))).orElseThrow();
        assertEquals(CandidateAccuracy.SUPERSET, result.accuracy());
        assertEquals(2, result.bitmap().cardinality());
    }

    @Test
    void unsafeOrAndNotFallBackToScanning() {
        assertTrue(planner.plan(snapshot, new OrFilter(List.of(
                new CategoryFilter(Category.BOOKS), new NameFilter("Lap")))).isEmpty());
        assertTrue(planner.plan(snapshot, new NotFilter(new NameFilter("Lap"))).isEmpty());
    }

    private static Product product(
            String id, String name, Category category, double price, double rating
    ) {
        return new Product(id, name, category, price, true, rating);
    }
}
