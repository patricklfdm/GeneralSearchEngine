package org.example.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.example.generalsearch.engine.metrics.IndexBuildMetrics;
import org.example.generalsearch.engine.metrics.SearchEngineMetrics;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.schema.Field;
import org.example.generalsearch.schema.SearchSchema;
import org.junit.jupiter.api.Test;

class SearchEngineMetricsTest {
    @Test
    void productFacadeReportsDocumentsIndexesAndMutationOutcomes() {
        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine()) {
            SearchEngineMetrics initial = engine.metrics();
            assertEquals(0, initial.snapshotVersion());
            assertEquals(0, initial.documentCount());
            assertEquals(4, initial.registeredIndexCount());
            assertEquals(0, initial.writerQueueDepth());
            assertTrue(initial.acceptingRequests());

            Product product = new Product(
                    "p1", "Laptop", Category.ELECTRONICS, 999.0, true, 4.8);
            engine.add(product).join();
            assertThrows(CompletionException.class, () -> engine.add(product).join());

            SearchEngineMetrics afterMutations = engine.metrics();
            assertEquals(1, afterMutations.documentCount());
            assertEquals(1, afterMutations.successfulMutations());
            assertEquals(1, afterMutations.failedMutations());
            assertTrue(afterMutations.snapshotVersion() > initial.snapshotVersion());
            assertEquals(0, afterMutations.mutationJournalLength());
            assertEquals(0, afterMutations.pendingIndexBuildCount());

            engine.close();
            assertThrows(CompletionException.class,
                    () -> engine.update(product).join());
            SearchEngineMetrics closed = engine.metrics();
            assertFalse(closed.acceptingRequests());
            assertEquals(2, closed.failedMutations());
        }
    }

    @Test
    void exposesActiveBuildJournalSuccessDurationAndCancellation() throws Exception {
        BlockingExtractor extractor = new BlockingExtractor();
        Field<Item, Long> id = Field.of("id", Long.class, Item::id);
        Field<Item, Integer> score =
                Field.of("score", Integer.class, extractor::valueOf);
        SearchSchema<Item, Long> schema = SearchSchema.builder(Item.class, id)
                .field(score)
                .build();

        try (SnapshotSearchEngine<Long, Item> engine =
                     new SnapshotSearchEngine<>(schema, List.of())) {
            engine.add(new Item(1, 10)).join();
            extractor.blockNextBuild();
            CompletableFuture<Void> firstBuild =
                    engine.createIndex(IndexDefinition.range(score));
            assertTrue(extractor.awaitBuildStart());

            engine.update(new Item(1, 20)).join();
            SearchEngineMetrics building = engine.metrics();
            assertEquals(1, building.pendingIndexBuildCount());
            assertEquals(1, building.indexBuildsStarted());
            assertEquals(1, building.mutationJournalLength());
            IndexBuildMetrics active = building.activeIndexBuilds().getFirst();
            assertEquals("score", active.fieldName());
            assertEquals(1, active.baseSnapshotVersion());
            assertFalse(active.elapsed().isNegative());
            assertThrows(UnsupportedOperationException.class,
                    () -> building.activeIndexBuilds().clear());

            engine.dropIndex("score").join();
            assertThrows(CompletionException.class, firstBuild::join);
            SearchEngineMetrics cancelled = engine.metrics();
            assertEquals(0, cancelled.pendingIndexBuildCount());
            assertEquals(0, cancelled.mutationJournalLength());
            assertEquals(1, cancelled.indexBuildsCancelled());

            extractor.releaseBuild();
            engine.createIndex(IndexDefinition.range(score)).join();
            SearchEngineMetrics completed = engine.metrics();
            assertEquals(2, completed.indexBuildsStarted());
            assertEquals(1, completed.indexBuildsSucceeded());
            assertEquals(1, completed.indexBuildsCancelled());
            assertEquals(0, completed.indexBuildsFailed());
            assertTrue(completed.lastSuccessfulIndexBuildDuration().isPresent());
            assertTrue(completed.lastIndexBuildFailure().isEmpty());
            assertEquals(1, completed.registeredIndexCount());
        } finally {
            extractor.releaseBuild();
        }
    }

    @Test
    void recordsTheMostRecentBuildFailureWithoutRetainingTheThrowable() {
        AtomicBoolean fail = new AtomicBoolean(true);
        Field<Item, Long> id = Field.of("id", Long.class, Item::id);
        Field<Item, Integer> score = Field.of("score", Integer.class, item -> {
            if (fail.get() && Thread.currentThread().getName()
                    .startsWith("snapshot-index-builder-")) {
                throw new IllegalStateException("synthetic metrics failure");
            }
            return item.score();
        });
        SearchSchema<Item, Long> schema = SearchSchema.builder(Item.class, id)
                .field(score)
                .build();

        try (SnapshotSearchEngine<Long, Item> engine =
                     new SnapshotSearchEngine<>(schema, List.of())) {
            engine.add(new Item(1, 10)).join();
            assertThrows(CompletionException.class,
                    () -> engine.createIndex(IndexDefinition.range(score)).join());

            SearchEngineMetrics metrics = engine.metrics();
            assertEquals(1, metrics.indexBuildsStarted());
            assertEquals(0, metrics.indexBuildsSucceeded());
            assertEquals(1, metrics.indexBuildsFailed());
            assertEquals(0, metrics.pendingIndexBuildCount());
            var failure = metrics.lastIndexBuildFailure().orElseThrow();
            assertEquals(IllegalStateException.class.getName(), failure.exceptionType());
            assertEquals("synthetic metrics failure", failure.message().orElseThrow());
            assertFalse(failure.duration().isNegative());
        } finally {
            fail.set(false);
        }
    }

    private record Item(long id, int score) {}

    private static final class BlockingExtractor {
        private final AtomicBoolean armed = new AtomicBoolean();
        private volatile CountDownLatch started = new CountDownLatch(0);
        private volatile CountDownLatch release = new CountDownLatch(0);

        private int valueOf(Item item) {
            if (Thread.currentThread().getName().startsWith("snapshot-index-builder-")
                    && armed.compareAndSet(true, false)) {
                started.countDown();
                try {
                    release.await();
                } catch (InterruptedException failure) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("build interrupted", failure);
                }
            }
            return item.score();
        }

        private void blockNextBuild() {
            started = new CountDownLatch(1);
            release = new CountDownLatch(1);
            armed.set(true);
        }

        private boolean awaitBuildStart() throws InterruptedException {
            return started.await(5, TimeUnit.SECONDS);
        }

        private void releaseBuild() {
            release.countDown();
        }
    }
}
