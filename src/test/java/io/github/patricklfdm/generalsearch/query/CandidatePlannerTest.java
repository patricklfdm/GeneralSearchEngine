package io.github.patricklfdm.generalsearch.query;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.index.CandidateEstimate;
import io.github.patricklfdm.generalsearch.index.EstimateQuality;
import io.github.patricklfdm.generalsearch.index.EstimatingIndexSnapshot;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.index.IndexStatistics;
import io.github.patricklfdm.generalsearch.model.Category;
import io.github.patricklfdm.generalsearch.model.Product;
import io.github.patricklfdm.generalsearch.model.ProductFields;
import io.github.patricklfdm.generalsearch.model.ProductIndexDefinitions;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
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

    @Test
    void costAwareRangeChoosesSelectiveIndexAndScansBroadRange() {
        SearchSnapshot<Product> catalog = catalog(100);
        Query<Product> selective = Query.between(ProductFields.PRICE, 0.0, 4.0);
        Query<Product> equalCost = Query.between(ProductFields.PRICE, 0.0, 9.0);
        Query<Product> broad = Query.between(ProductFields.PRICE, 0.0, 99.0);

        assertEquals(5, planner.plan(catalog, selective).orElseThrow()
                .bitmap().cardinality());
        assertEquals(10, planner.plan(catalog, equalCost).orElseThrow()
                .bitmap().cardinality());
        assertTrue(planner.plan(catalog, broad).isEmpty());

        CandidatePlanner<Product> forcedIndex = new CandidatePlanner<>(
                new PlannerConfig(RangePlanningMode.FORCE_INDEX));
        CandidatePlanner<Product> forcedScan = new CandidatePlanner<>(
                new PlannerConfig(RangePlanningMode.FORCE_SCAN));
        assertEquals(100, forcedIndex.plan(catalog, broad).orElseThrow()
                .bitmap().cardinality());
        assertTrue(forcedScan.plan(catalog, selective).isEmpty());
    }

    @Test
    void scanAndIndexPlansKeepIdenticalFinalResults() {
        SearchSnapshot<Product> catalog = catalog(100);
        Query<Product> broad = Query.between(ProductFields.PRICE, 0.0, 99.0);
        SnapshotSearcher<Product> costAware = new SnapshotSearcher<>();
        SnapshotSearcher<Product> forcedIndex = new SnapshotSearcher<>(
                new CandidatePlanner<>(new PlannerConfig(
                        RangePlanningMode.FORCE_INDEX)));

        assertEquals(
                forcedIndex.search(catalog, broad),
                costAware.search(catalog, broad)
        );
    }

    @Test
    void inspectingAccessPathsMaterializesOnlyTheSelectedIndex() {
        AtomicInteger selectedCalls = new AtomicInteger();
        AtomicInteger rejectedCalls = new AtomicInteger();
        Field<Product, Double> alternate = Field.of(
                "alternate-price", Double.class, Product::price);
        CountingDefinition selected = new CountingDefinition(
                ProductFields.PRICE,
                estimate(5, 1),
                bitmap(0, 1, 2, 3, 4),
                selectedCalls
        );
        CountingDefinition rejected = new CountingDefinition(
                alternate,
                estimate(80, 1),
                bitmapRange(80),
                rejectedCalls
        );
        SearchSnapshot<Product> catalog = new SearchSnapshot<Product>(
                List.of(selected, rejected)
        );
        for (int docId = 0; docId < 100; docId++) {
            catalog = catalog.add(docId, product(
                    "p" + docId,
                    "Product " + docId,
                    Category.ELECTRONICS,
                    docId,
                    4.0
            ));
        }

        CandidateResult result = planner.plan(
                catalog,
                Query.between(ProductFields.PRICE, 0.0, 10.0)
        ).orElseThrow();

        assertEquals(5, result.bitmap().cardinality());
        assertEquals(1, selectedCalls.get());
        assertEquals(0, rejectedCalls.get());
    }

    @Test
    void andUsesOneUsefulPathAndLeavesSkippedPredicatesForVerification() {
        SearchSnapshot<Product> catalog = catalog(100);
        CandidateResult result = planner.plan(catalog, Query.and(
                Query.between(ProductFields.PRICE, 0.0, 4.0),
                Query.eq(ProductFields.CATEGORY, Category.ELECTRONICS),
                product -> product.id().endsWith("0")
        )).orElseThrow();

        assertEquals(5, result.bitmap().cardinality());
        assertEquals(CandidateAccuracy.SUPERSET, result.accuracy());
        assertEquals(1, new SnapshotSearcher<Product>().search(catalog, Query.and(
                Query.between(ProductFields.PRICE, 0.0, 4.0),
                Query.eq(ProductFields.CATEGORY, Category.ELECTRONICS),
                product -> product.id().endsWith("0")
        )).size());
    }

    @Test
    void orAndNotRetainIndexCompatibilityEvenWhenDirectRangeWouldScan() {
        SearchSnapshot<Product> catalog = catalog(100);
        Query<Product> broad = Query.between(ProductFields.PRICE, 0.0, 99.0);

        assertTrue(planner.plan(catalog, broad).isEmpty());
        assertEquals(100, planner.plan(catalog, Query.or(
                broad,
                Query.eq(ProductFields.CATEGORY, Category.BOOKS)
        )).orElseThrow().bitmap().cardinality());
        assertEquals(0, planner.plan(catalog, Query.not(broad))
                .orElseThrow().bitmap().cardinality());
    }

    @Test
    void approximateEstimateCanChangeWorkButNeverFinalCorrectness() {
        AtomicInteger calls = new AtomicInteger();
        CountingDefinition approximate = new CountingDefinition(
                ProductFields.PRICE,
                new CandidateEstimate(
                        1,
                        1,
                        EstimateQuality.APPROXIMATE,
                        CandidateAccuracy.SUPERSET
                ),
                bitmapRange(100),
                calls
        );
        SearchSnapshot<Product> catalog = new SearchSnapshot<Product>(
                List.of(approximate));
        for (int docId = 0; docId < 100; docId++) {
            catalog = catalog.add(docId, product(
                    "p" + docId,
                    "Product " + docId,
                    Category.ELECTRONICS,
                    docId,
                    4.0
            ));
        }
        Query<Product> query = Query.between(ProductFields.PRICE, 10.0, 19.0);

        assertEquals(10, new SnapshotSearcher<Product>().search(catalog, query).size());
        assertEquals(1, calls.get());
    }

    @Test
    void equalityAndRangeIndexesCanCoexistWithoutChangingEqualityAccuracy() {
        SearchSnapshot<Product> catalog = new SearchSnapshot<>(List.of(
                IndexDefinition.equality(ProductFields.PRICE),
                IndexDefinition.range(ProductFields.PRICE)
        )).add(0, product(
                "p0", "Laptop", Category.ELECTRONICS, 999.0, 4.8
        )).add(1, product(
                "p1", "Other", Category.BOOKS, 999.0, 4.0
        ));

        CandidateResult result = planner.plan(
                catalog,
                Query.eq(ProductFields.PRICE, 999.0)
        ).orElseThrow();

        assertEquals(CandidateAccuracy.EXACT, result.accuracy());
        assertEquals(2, result.bitmap().cardinality());
    }

    private static SearchSnapshot<Product> catalog(int size) {
        SearchSnapshot<Product> result = new SearchSnapshot<>(
                ProductIndexDefinitions.defaults());
        for (int docId = 0; docId < size; docId++) {
            result = result.add(docId, product(
                    "p" + docId,
                    "Product " + docId,
                    Category.ELECTRONICS,
                    docId,
                    4.0
            ));
        }
        return result;
    }

    private static CandidateEstimate estimate(int cardinality, int sources) {
        return new CandidateEstimate(
                cardinality,
                sources,
                EstimateQuality.EXACT,
                CandidateAccuracy.EXACT
        );
    }

    private static ImmutableBitmap bitmap(int... docIds) {
        ImmutableBitmap bitmap = ImmutableBitmap.empty();
        for (int docId : docIds) {
            bitmap = bitmap.withSet(docId);
        }
        return bitmap;
    }

    private static ImmutableBitmap bitmapRange(int size) {
        ImmutableBitmap bitmap = ImmutableBitmap.empty();
        for (int docId = 0; docId < size; docId++) {
            bitmap = bitmap.withSet(docId);
        }
        return bitmap;
    }

    private static Product product(
            String id, String name, Category category, double price, double rating
    ) {
        return new Product(id, name, category, price, true, rating);
    }

    private record CountingDefinition(
            Field<Product, Double> field,
            CandidateEstimate estimate,
            ImmutableBitmap candidates,
            AtomicInteger materializations
    ) implements IndexDefinition<Product> {
        @Override
        public IndexSnapshot<Product> createEmpty() {
            return new CountingIndex(field, estimate, candidates, materializations);
        }
    }

    private record CountingIndex(
            Field<Product, Double> field,
            CandidateEstimate estimate,
            ImmutableBitmap candidateBitmap,
            AtomicInteger materializations
    ) implements EstimatingIndexSnapshot<Product> {
        @Override
        public Optional<CandidateResult> candidates(Query<Product> query) {
            materializations.incrementAndGet();
            return Optional.of(new CandidateResult(
                    candidateBitmap,
                    estimate.accuracy()
            ));
        }

        @Override
        public IndexStatistics statistics() {
            return new IndexStatistics(100, estimate.estimatedSourceCount());
        }

        @Override
        public Optional<CandidateEstimate> estimateCandidates(Query<Product> query) {
            return query instanceof RangeQuery<?, ?>
                    ? Optional.of(estimate)
                    : Optional.empty();
        }

        @Override
        public IndexBuilder<Product> toBuilder() {
            return new IndexBuilder<>() {
                @Override
                public void add(int docId, Product document) {}

                @Override
                public void remove(int docId, Product document) {}

                @Override
                public void update(
                        int docId,
                        Product oldDocument,
                        Product newDocument
                ) {}

                @Override
                public IndexSnapshot<Product> build() {
                    return CountingIndex.this;
                }
            };
        }
    }
}
