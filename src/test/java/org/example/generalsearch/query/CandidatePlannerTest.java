package org.example.generalsearch.query;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;
import org.example.generalsearch.model.ProductIndexDefinitions;
import org.example.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class CandidatePlannerTest {
    private final CandidatePlanner<Product> planner = new CandidatePlanner<>();
    private SearchSnapshot<Product> snapshot;

    @BeforeEach
    void buildCatalog() {
        snapshot = new SearchSnapshot<>(ProductIndexDefinitions.defaults())
                .add(0, product("p0", "Laptop", Category.ELECTRONICS, 999, 4.8))
                .add(1, product("p1", "Book", Category.BOOKS, 25, 4.9))
                .add(2, product("p2", "Mouse", Category.ELECTRONICS, 40, 3.0));
    }

    @Test
    void priceRangeUsesItsIndex() {
        CandidateResult result = planner.plan(
                snapshot,
                Query.between(ProductFields.PRICE, 20.0, 50.0)
        ).orElseThrow();
        assertEquals(CandidateAccuracy.EXACT, result.accuracy());
        assertEquals(2, result.bitmap().cardinality());
        assertTrue(result.bitmap().get(1));
        assertTrue(result.bitmap().get(2));
    }

    @Test
    void andWithAnUnindexedFilterReturnsASuperset() {
        CandidateResult result = planner.plan(snapshot, Query.and(
                Query.eq(ProductFields.CATEGORY, Category.ELECTRONICS),
                Query.between(ProductFields.RATING, 4.0, 5.0)
        )).orElseThrow();
        assertEquals(CandidateAccuracy.SUPERSET, result.accuracy());
        assertEquals(2, result.bitmap().cardinality());
    }

    @Test
    void indexedPrefixEnablesExactOrAndNotPlanning() {
        CandidateResult or = planner.plan(snapshot, Query.or(
                Query.eq(ProductFields.CATEGORY, Category.BOOKS),
                Query.prefix(ProductFields.NAME, "Lap")
        )).orElseThrow();
        CandidateResult not = planner.plan(snapshot,
                Query.not(Query.prefix(ProductFields.NAME, "Lap"))).orElseThrow();

        assertEquals(CandidateAccuracy.EXACT, or.accuracy());
        assertEquals(2, or.bitmap().cardinality());
        assertEquals(CandidateAccuracy.EXACT, not.accuracy());
        assertEquals(2, not.bitmap().cardinality());

        assertTrue(planner.plan(snapshot,
                Query.not(Query.between(ProductFields.RATING, 4.0, 5.0))).isEmpty());
    }

    @Test
    void usesAStartupRegisteredIndexWithoutPlannerChanges() {
        SearchSnapshot<Product> ratingIndexed = new SearchSnapshot<>(List.of(
                IndexDefinition.range(ProductFields.RATING)
        )).add(0, product("p0", "Laptop", Category.ELECTRONICS, 999, 4.8))
                .add(1, product("p1", "Mouse", Category.ELECTRONICS, 40, 3.0));

        CandidateResult result = planner.plan(
                ratingIndexed,
                Query.between(ProductFields.RATING, 4.0, 5.0)
        ).orElseThrow();

        assertEquals(CandidateAccuracy.EXACT, result.accuracy());
        assertEquals(1, result.bitmap().cardinality());
        assertTrue(result.bitmap().get(0));
    }

    private static Product product(
            String id, String name, Category category, double price, double rating
    ) {
        return new Product(id, name, category, price, true, rating);
    }
}
