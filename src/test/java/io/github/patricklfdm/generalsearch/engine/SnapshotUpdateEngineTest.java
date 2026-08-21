package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import io.github.patricklfdm.generalsearch.filter.CategoryFilter;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.model.Category;
import io.github.patricklfdm.generalsearch.model.Product;
import io.github.patricklfdm.generalsearch.model.ProductFields;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.CandidateAccuracy;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;

class SnapshotUpdateEngineTest {
    @Test
    void appliesQueuedMutationsInSubmissionOrder() {
        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine(
                new SnapshotEngineConfig(100, 100, Duration.ofMillis(1)))) {
            Product original = product("p1", Category.BOOKS, 10);
            Product updated = product("p1", Category.ELECTRONICS, 20);
            engine.add(original).join();
            engine.update(updated).join();

            assertEquals(updated, engine.get("p1"));
            assertEquals(List.of(updated), engine.search(
                    Query.between(ProductFields.PRICE, 15.0, 25.0)));
            assertTrue(engine.search(
                    Query.eq(ProductFields.CATEGORY, Category.BOOKS)).isEmpty());

            engine.remove("p1").join();
            assertNull(engine.get("p1"));
        }
    }

    @Test
    void rejectsSubmissionsAfterGracefulClose() {
        SnapshotUpdateEngine engine = new SnapshotUpdateEngine();
        engine.add(product("p0", Category.HOME, 5)).join();
        engine.close();

        assertThrows(CompletionException.class,
                () -> engine.remove("p0").join());
    }

    @Test
    void closePublishesEveryAcceptedMutation() {
        SnapshotUpdateEngine engine = new SnapshotUpdateEngine(
                new SnapshotEngineConfig(1_000, 1_000, Duration.ofSeconds(10)));
        List<CompletableFuture<Void>> accepted = new ArrayList<>();
        for (int docId = 0; docId < 500; docId++) {
            accepted.add(engine.add(product("p" + docId, Category.HOME, docId)));
        }

        engine.close();

        accepted.forEach(CompletableFuture::join);
        assertEquals(500, engine.search(
                Query.eq(ProductFields.CATEGORY, Category.HOME)).size());
    }

    @Test
    void acceptsDynamicIndexDefinitionsAtStartup() {
        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine(
                SnapshotEngineConfig.DEFAULT,
                List.of(IndexDefinition.range(ProductFields.RATING)))) {
            Product product = product("p1", Category.BOOKS, 10);
            engine.add(product).join();

            Query<Product> query = Query.between(ProductFields.RATING, 4.0, 5.0);
            assertTrue(engine.snapshotForTesting()
                    .indexes()
                    .candidates(query)
                    .orElseThrow()
                    .bitmap()
                    .get(engine.internalDocIdForTesting("p1")));
            assertEquals(List.of(product), engine.search(query));
        }
    }

    @Test
    @SuppressWarnings("deprecation")
    void keepsFormerProductFiltersCompatibleAtTheProductBoundary() {
        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine()) {
            Product book = product("p1", Category.BOOKS, 10);
            engine.add(book).join();

            assertEquals(List.of(book), engine.search(new CategoryFilter(Category.BOOKS)));
        }
    }

    @Test
    void enforcesBusinessIdMutationSemanticsAndDoesNotReuseDocIds() {
        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine()) {
            Product first = product("p1", Category.BOOKS, 10);
            engine.add(first).join();
            int firstDocId = engine.internalDocIdForTesting("p1");

            assertThrows(CompletionException.class, () -> engine.add(first).join());
            assertThrows(CompletionException.class,
                    () -> engine.update(product("missing", Category.HOME, 1)).join());

            engine.remove("missing").join();
            engine.remove("p1").join();
            engine.add(product("p1", Category.HOME, 20)).join();

            assertTrue(engine.internalDocIdForTesting("p1") > firstDocId);
        }
    }

    @Test
    void createsAndDropsIndexesAtRuntime() {
        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine()) {
            Product book = product("p1", Category.BOOKS, 10);
            engine.add(book).join();
            Query<Product> rating = Query.between(ProductFields.RATING, 4.0, 5.0);
            CandidatePlanner<Product> planner = new CandidatePlanner<>();
            long initialVersion = engine.snapshotForTesting().version();

            assertTrue(planner.plan(engine.snapshotForTesting(), rating).isEmpty());
            engine.createIndex(IndexDefinition.range(ProductFields.RATING)).join();

            var candidate = planner.plan(engine.snapshotForTesting(), rating).orElseThrow();
            assertEquals(CandidateAccuracy.EXACT, candidate.accuracy());
            assertEquals(List.of(book), engine.search(rating));
            assertTrue(engine.snapshotForTesting().version() > initialVersion);
            assertThrows(CompletionException.class,
                    () -> engine.createIndex(
                            IndexDefinition.range(ProductFields.RATING)).join());

            engine.dropIndex("rating").join();
            assertTrue(planner.plan(engine.snapshotForTesting(), rating).isEmpty());
            engine.dropIndex("rating").join();

            Field<Product, Double> nonCanonical =
                    Field.of("rating", Double.class, Product::rating);
            assertThrows(CompletionException.class,
                    () -> engine.createIndex(IndexDefinition.range(nonCanonical)).join());
            assertThrows(CompletionException.class,
                    () -> engine.dropIndex("unknown").join());
        }
    }

    private static Product product(String id, Category category, double price) {
        return new Product(id, "Product " + id, category, price, true, 4.5);
    }
}
