package org.example.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;
import org.example.generalsearch.engine.exception.IndexLifecycleException;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.index.range.RangeIndexSnapshot;
import org.example.generalsearch.query.CandidateAccuracy;
import org.example.generalsearch.query.CandidatePlanner;
import org.example.generalsearch.query.Query;
import org.example.generalsearch.schema.Field;
import org.example.generalsearch.schema.SearchSchema;
import org.junit.jupiter.api.Test;

class DynamicIndexLifecycleTest {
    @Test
    void replaysMutationsThatCompleteDuringABackgroundBuild() throws Exception {
        BlockingScoreExtractor extractor = new BlockingScoreExtractor();
        Field<Item, Long> id = Field.of("id", Long.class, Item::id);
        Field<Item, Integer> score = Field.of(
                "score", Integer.class, extractor::valueOf);
        SearchSchema<Item, Long> schema = SearchSchema.builder(Item.class, id)
                .field(score)
                .build();

        try (SnapshotSearchEngine<Long, Item> engine = new SnapshotSearchEngine<>(
                new SnapshotEngineConfig(10_000, 100, Duration.ZERO),
                schema,
                List.of())) {
            for (long itemId = 0; itemId < 100; itemId++) {
                engine.add(new Item(itemId, (int) itemId)).join();
            }

            extractor.blockNextIndexBuild();
            CompletableFuture<Void> create =
                    engine.createIndex(IndexDefinition.range(score));
            assertTrue(extractor.awaitBuildStart());

            CompletableFuture<Void> duplicate =
                    engine.createIndex(IndexDefinition.range(score));
            CompletionException duplicateFailure =
                    assertThrows(CompletionException.class, duplicate::join);
            IndexLifecycleException duplicateCause = assertInstanceOf(
                    IndexLifecycleException.class, duplicateFailure.getCause());
            assertEquals(IndexLifecycleException.Reason.BUILD_IN_PROGRESS,
                    duplicateCause.reason());

            engine.update(new Item(0, 950)).join();
            engine.remove(1L).join();
            engine.add(new Item(1_000, 975)).join();
            engine.remove(2L).join();
            engine.add(new Item(2, 925)).join();

            extractor.releaseBuild();
            create.join();

            Query<Item> highScore = Query.between(score, 900, 1_000);
            assertEquals(Set.of(0L, 2L, 1_000L), ids(engine.search(highScore)));
            var candidate = new CandidatePlanner<Item>()
                    .plan(engine.snapshotForTesting(), highScore)
                    .orElseThrow();
            assertEquals(CandidateAccuracy.EXACT, candidate.accuracy());
            assertEquals(3, candidate.bitmap().cardinality());
            assertTrue(engine.snapshotForTesting().indexes().indexes().stream()
                    .anyMatch(RangeIndexSnapshot.class::isInstance));
        } finally {
            extractor.releaseBuild();
        }
    }

    @Test
    void dropCancelsPendingBuildsAndIsIdempotent() throws Exception {
        BlockingScoreExtractor extractor = new BlockingScoreExtractor();
        Field<Item, Long> id = Field.of("id", Long.class, Item::id);
        Field<Item, Integer> score = Field.of(
                "score", Integer.class, extractor::valueOf);
        SearchSchema<Item, Long> schema = SearchSchema.builder(Item.class, id)
                .field(score)
                .build();

        try (SnapshotSearchEngine<Long, Item> engine =
                     new SnapshotSearchEngine<>(schema, List.of())) {
            engine.add(new Item(1, 10)).join();
            extractor.blockNextIndexBuild();
            CompletableFuture<Void> create =
                    engine.createIndex(IndexDefinition.range(score));
            assertTrue(extractor.awaitBuildStart());

            engine.dropIndex("score").join();
            CompletionException cancelledFailure =
                    assertThrows(CompletionException.class, create::join);
            IndexLifecycleException cancelledCause = assertInstanceOf(
                    IndexLifecycleException.class, cancelledFailure.getCause());
            assertEquals(IndexLifecycleException.Reason.CANCELLED,
                    cancelledCause.reason());
            engine.dropIndex("score").join();
            assertTrue(new CandidatePlanner<Item>()
                    .plan(engine.snapshotForTesting(), Query.between(score, 0, 100))
                    .isEmpty());
        } finally {
            extractor.releaseBuild();
        }
    }

    @Test
    void closeWaitsForAnAcceptedIndexBuild() throws Exception {
        BlockingScoreExtractor extractor = new BlockingScoreExtractor();
        Field<Item, Long> id = Field.of("id", Long.class, Item::id);
        Field<Item, Integer> score = Field.of(
                "score", Integer.class, extractor::valueOf);
        SearchSchema<Item, Long> schema = SearchSchema.builder(Item.class, id)
                .field(score)
                .build();
        SnapshotSearchEngine<Long, Item> engine =
                new SnapshotSearchEngine<>(schema, List.of());
        engine.add(new Item(1, 10)).join();
        extractor.blockNextIndexBuild();
        CompletableFuture<Void> create = engine.createIndex(IndexDefinition.range(score));
        assertTrue(extractor.awaitBuildStart());

        CompletableFuture<Void> close = CompletableFuture.runAsync(engine::close);
        assertThrows(TimeoutException.class,
                () -> close.get(100, TimeUnit.MILLISECONDS));

        extractor.releaseBuild();
        close.get(5, TimeUnit.SECONDS);
        create.join();
        assertFalse(engine.snapshotForTesting().indexes().indexes().isEmpty());
    }

    @Test
    void aFailedBuildDoesNotStopMutationsAndCanBeRetried() {
        AtomicBoolean failBuild = new AtomicBoolean(true);
        Field<Item, Long> id = Field.of("id", Long.class, Item::id);
        Field<Item, Integer> score = Field.of("score", Integer.class, item -> {
            if (failBuild.get()
                    && Thread.currentThread().getName()
                    .startsWith("snapshot-index-builder-")) {
                throw new IllegalStateException("synthetic index build failure");
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

            engine.update(new Item(1, 20)).join();
            failBuild.set(false);
            engine.createIndex(IndexDefinition.range(score)).join();

            assertEquals(List.of(new Item(1, 20)),
                    engine.search(Query.between(score, 15, 25)));
        }
    }

    private static Set<Long> ids(List<Item> items) {
        Set<Long> ids = new HashSet<>();
        items.forEach(item -> ids.add(item.id()));
        return ids;
    }

    private record Item(long id, int score) {}

    private static final class BlockingScoreExtractor {
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
                    throw new IllegalStateException("index build was interrupted", failure);
                }
            }
            return item.score();
        }

        private void blockNextIndexBuild() {
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
