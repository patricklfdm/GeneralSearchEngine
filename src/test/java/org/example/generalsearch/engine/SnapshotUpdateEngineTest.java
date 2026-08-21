package org.example.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.List;
import java.util.ArrayList;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import org.example.generalsearch.filter.CategoryFilter;
import org.example.generalsearch.filter.PriceRangeFilter;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.junit.jupiter.api.Test;

class SnapshotUpdateEngineTest {
    @Test
    void appliesQueuedMutationsInSubmissionOrder() {
        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine(
                new SnapshotEngineConfig(100, 100, Duration.ofMillis(1)))) {
            Product original = product("p1", Category.BOOKS, 10);
            Product updated = product("p1", Category.ELECTRONICS, 20);
            engine.add(7, original).join();
            engine.update(7, updated).join();

            assertEquals(updated, engine.get(7));
            assertEquals(List.of(updated), engine.search(new PriceRangeFilter(15, 25)));
            assertTrue(engine.search(new CategoryFilter(Category.BOOKS)).isEmpty());

            engine.remove(7).join();
            assertNull(engine.get(7));
        }
    }

    @Test
    void rejectsSubmissionsAfterGracefulClose() {
        SnapshotUpdateEngine engine = new SnapshotUpdateEngine();
        engine.add(0, product("p0", Category.HOME, 5)).join();
        engine.close();

        assertThrows(CompletionException.class,
                () -> engine.remove(0).join());
    }

    @Test
    void closePublishesEveryAcceptedMutation() {
        SnapshotUpdateEngine engine = new SnapshotUpdateEngine(
                new SnapshotEngineConfig(1_000, 1_000, Duration.ofSeconds(10)));
        List<CompletableFuture<Void>> accepted = new ArrayList<>();
        for (int docId = 0; docId < 500; docId++) {
            accepted.add(engine.add(docId, product("p" + docId, Category.HOME, docId)));
        }

        engine.close();

        accepted.forEach(CompletableFuture::join);
        assertEquals(500, engine.search(new CategoryFilter(Category.HOME)).size());
    }

    private static Product product(String id, Category category, double price) {
        return new Product(id, "Product " + id, category, price, true, 4.5);
    }
}
