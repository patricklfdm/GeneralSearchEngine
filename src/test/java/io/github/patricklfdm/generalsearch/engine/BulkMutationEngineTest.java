package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import io.github.patricklfdm.generalsearch.engine.exception.BulkMutationException;
import io.github.patricklfdm.generalsearch.engine.exception.DocumentAlreadyExistsException;
import io.github.patricklfdm.generalsearch.engine.exception.DocumentNotFoundException;
import io.github.patricklfdm.generalsearch.engine.exception.EngineRejectedExecutionException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import org.junit.jupiter.api.Test;

class BulkMutationEngineTest {
    private static final Field<Item, Integer> ID =
            Field.of("id", Integer.class, Item::id);
    private static final Field<Item, String> CATEGORY =
            Field.of("category", String.class, Item::category);

    @Test
    void publicBulkMethodsAreCompatibilityDefaults() throws Exception {
        assertTrue(SearchEngine.class
                .getMethod("addAll", Collection.class)
                .isDefault());
        assertTrue(SearchEngine.class
                .getMethod("updateAll", Collection.class)
                .isDefault());
        assertTrue(SearchEngine.class
                .getMethod("removeAll", Collection.class)
                .isDefault());
    }

    @Test
    void publishesEachExplicitBulkExactlyOnceInIterationOrder() {
        try (SnapshotSearchEngine<Integer, Item> engine = engine(10)) {
            long initialVersion = engine.metrics().snapshotVersion();
            List<Item> added = List.of(
                    new Item(3, "old"),
                    new Item(1, "old"),
                    new Item(2, "old"));
            engine.addAll(added).join();

            assertEquals(initialVersion + 1, engine.metrics().snapshotVersion());
            assertEquals(added, engine.search(Query.matchAll()));
            assertEquals(3, engine.metrics().successfulMutations());

            engine.updateAll(List.of(
                    new Item(3, "new"),
                    new Item(1, "new"))).join();
            assertEquals(initialVersion + 2, engine.metrics().snapshotVersion());
            assertEquals(List.of(3, 1), engine.search(Query.eq(CATEGORY, "new"))
                    .stream().map(Item::id).toList());

            engine.removeAll(List.of(1, 999)).join();
            assertEquals(initialVersion + 3, engine.metrics().snapshotVersion());
            assertNull(engine.get(1));
            assertEquals(7, engine.metrics().successfulMutations());
        }
    }

    @Test
    void rejectsDuplicatesAndSnapshotConflictsWithoutPublishingPartialState() {
        try (SnapshotSearchEngine<Integer, Item> engine = engine(10)) {
            long emptyVersion = engine.metrics().snapshotVersion();
            BulkMutationException duplicate = cause(
                    BulkMutationException.class,
                    () -> engine.addAll(List.of(
                            new Item(1, "first"),
                            new Item(1, "second"))).join());
            assertEquals(BulkMutationException.Reason.DUPLICATE_ID, duplicate.reason());
            assertEquals(1, duplicate.documentId());
            assertEquals(emptyVersion, engine.metrics().snapshotVersion());
            assertNull(engine.get(1));

            Item original = new Item(2, "original");
            engine.add(original).join();
            long populatedVersion = engine.metrics().snapshotVersion();
            DocumentAlreadyExistsException existing = cause(
                    DocumentAlreadyExistsException.class,
                    () -> engine.addAll(List.of(
                            new Item(3, "new"),
                            new Item(2, "duplicate"))).join());
            assertEquals(2, existing.documentId());
            assertEquals(populatedVersion, engine.metrics().snapshotVersion());
            assertNull(engine.get(3));

            DocumentNotFoundException missing = cause(
                    DocumentNotFoundException.class,
                    () -> engine.updateAll(List.of(
                            new Item(2, "changed"),
                            new Item(4, "missing"))).join());
            assertEquals(4, missing.documentId());
            assertEquals(populatedVersion, engine.metrics().snapshotVersion());
            assertEquals(original, engine.get(2));

            cause(BulkMutationException.class,
                    () -> engine.removeAll(List.of(2, 2)).join());
            assertEquals(original, engine.get(2));
            assertEquals(populatedVersion, engine.metrics().snapshotVersion());
        }
    }

    @Test
    void enforcesConfiguredMaximumAndTreatsEmptyCollectionsAsNoOps() {
        try (SnapshotSearchEngine<Integer, Item> engine = engine(2)) {
            long initialVersion = engine.metrics().snapshotVersion();
            engine.addAll(List.of()).join();
            assertEquals(initialVersion, engine.metrics().snapshotVersion());

            BulkMutationException tooLarge = cause(
                    BulkMutationException.class,
                    () -> engine.addAll(List.of(
                            new Item(1, "a"),
                            new Item(2, "b"),
                            new Item(3, "c"))).join());
            assertEquals(BulkMutationException.Reason.TOO_LARGE, tooLarge.reason());
            assertEquals(3, tooLarge.batchSize());
            assertEquals(2, tooLarge.maximumBatchSize());
            assertEquals(3, engine.metrics().failedMutations());
            assertEquals(initialVersion, engine.metrics().snapshotVersion());
        }
    }

    @Test
    void preservesOrderingAgainstIndividualAndIndexLifecycleTasks() {
        try (SnapshotSearchEngine<Integer, Item> engine = new SnapshotSearchEngine<>(
                new SnapshotEngineConfig(1_000, 100, Duration.ZERO),
                SearchSchema.builder(Item.class, ID).field(CATEGORY).build(),
                List.of())) {
            CompletableFuture<Void> add = engine.addAll(List.of(
                    new Item(1, "before"),
                    new Item(2, "before")));
            CompletableFuture<Void> create = engine.createIndex(
                    IndexDefinition.equality(CATEGORY));
            CompletableFuture<Void> update = engine.updateAll(List.of(
                    new Item(1, "after"),
                    new Item(2, "after")));
            CompletableFuture<Void> remove = engine.remove(2);

            CompletableFuture.allOf(add, create, update, remove).join();
            assertEquals(List.of(new Item(1, "after")),
                    engine.search(Query.eq(CATEGORY, "after")));
            assertTrue(engine.snapshotForTesting().indexes()
                    .candidates(Query.eq(CATEGORY, "after"))
                    .orElseThrow().bitmap()
                    .get(engine.internalDocIdForTesting(1)));
        }
    }

    @Test
    void extractorFailureRollsBackTheWholeBulkAndWriterContinues() {
        Field<Item, String> failing = Field.of(
                "category",
                String.class,
                item -> {
                    if ("fail".equals(item.category())) {
                        throw new IllegalStateException("synthetic extractor failure");
                    }
                    return item.category();
                });
        try (SnapshotSearchEngine<Integer, Item> engine = new SnapshotSearchEngine<>(
                new SnapshotEngineConfig(100, 10, Duration.ZERO),
                SearchSchema.builder(Item.class, ID).field(failing).build(),
                List.of(IndexDefinition.equality(failing)))) {
            long initialVersion = engine.metrics().snapshotVersion();
            cause(IllegalStateException.class, () -> engine.addAll(List.of(
                    new Item(1, "ok"),
                    new Item(2, "fail"))).join());

            assertEquals(initialVersion, engine.metrics().snapshotVersion());
            assertNull(engine.get(1));
            assertNull(engine.get(2));
            engine.add(new Item(3, "ok")).join();
            assertEquals(new Item(3, "ok"), engine.get(3));
        }
    }

    @Test
    void closeDrainsAcceptedBulkAndRejectsLaterNonEmptyBulk() {
        SnapshotSearchEngine<Integer, Item> engine = engine(1_000);
        List<Item> documents = new ArrayList<>();
        for (int id = 0; id < 500; id++) {
            documents.add(new Item(id, "accepted"));
        }
        CompletableFuture<Void> accepted = engine.addAll(documents);
        engine.close();

        accepted.join();
        assertEquals(500, engine.search(Query.matchAll()).size());
        EngineRejectedExecutionException closed = cause(
                EngineRejectedExecutionException.class,
                () -> engine.removeAll(List.of(1)).join());
        assertEquals(EngineRejectedExecutionException.Reason.CLOSED, closed.reason());
    }

    @Test
    void oneBulkUsesOneQueueSlotAndQueueRejectionCountsEveryItem() throws Exception {
        BlockingExtractor extractor = new BlockingExtractor();
        Field<Item, String> blocking =
                Field.of("category", String.class, extractor::valueOf);
        SnapshotSearchEngine<Integer, Item> engine = new SnapshotSearchEngine<>(
                new SnapshotEngineConfig(1, 10, Duration.ZERO),
                SearchSchema.builder(Item.class, ID).field(blocking).build(),
                List.of(IndexDefinition.equality(blocking)));
        try {
            extractor.blockNext();
            CompletableFuture<Void> active = engine.addAll(List.of(
                    new Item(1, "a"),
                    new Item(2, "b")));
            extractor.awaitStart();
            CompletableFuture<Void> queued = engine.addAll(List.of(
                    new Item(3, "c"),
                    new Item(4, "d")));
            EngineRejectedExecutionException full = cause(
                    EngineRejectedExecutionException.class,
                    () -> engine.addAll(List.of(
                            new Item(5, "e"),
                            new Item(6, "f"))).join());
            assertEquals(EngineRejectedExecutionException.Reason.QUEUE_FULL,
                    full.reason());

            extractor.release();
            active.join();
            queued.join();
            assertEquals(4, engine.metrics().successfulMutations());
            assertEquals(2, engine.metrics().failedMutations());
        } finally {
            extractor.release();
            engine.close();
        }
    }

    @Test
    void concurrentDisjointBulksDoNotLoseDocuments() {
        try (SnapshotSearchEngine<Integer, Item> engine = engine(100)) {
            List<CompletableFuture<Void>> submitted = new ArrayList<>();
            for (int batch = 0; batch < 4; batch++) {
                int base = batch * 25;
                submitted.add(CompletableFuture.runAsync(() -> {
                    List<Item> documents = new ArrayList<>();
                    for (int offset = 0; offset < 25; offset++) {
                        documents.add(new Item(base + offset, "parallel"));
                    }
                    engine.addAll(documents).join();
                }));
            }
            CompletableFuture.allOf(submitted.toArray(CompletableFuture[]::new)).join();
            assertEquals(100, engine.search(Query.eq(CATEGORY, "parallel")).size());
        }
    }

    private static SnapshotSearchEngine<Integer, Item> engine(int maxBatchSize) {
        return new SnapshotSearchEngine<>(
                new SnapshotEngineConfig(1_000, maxBatchSize, Duration.ZERO),
                SearchSchema.builder(Item.class, ID).field(CATEGORY).build(),
                List.of(IndexDefinition.equality(CATEGORY)));
    }

    private static <E extends Throwable> E cause(
            Class<E> type,
            Runnable operation
    ) {
        CompletionException completion =
                assertThrows(CompletionException.class, operation::run);
        return assertInstanceOf(type, completion.getCause());
    }

    private record Item(int id, String category) {}

    private static final class BlockingExtractor {
        private final AtomicBoolean armed = new AtomicBoolean();
        private volatile CountDownLatch started = new CountDownLatch(0);
        private volatile CountDownLatch release = new CountDownLatch(0);

        private String valueOf(Item item) {
            if (Thread.currentThread().getName().startsWith("snapshot-search-writer-")
                    && armed.compareAndSet(true, false)) {
                started.countDown();
                try {
                    release.await();
                } catch (InterruptedException failure) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException(failure);
                }
            }
            return item.category();
        }

        private void blockNext() {
            started = new CountDownLatch(1);
            release = new CountDownLatch(1);
            armed.set(true);
        }

        private void awaitStart() throws InterruptedException {
            if (!started.await(5, TimeUnit.SECONDS)) {
                throw new AssertionError("writer did not reach blocking extractor");
            }
        }

        private void release() {
            release.countDown();
        }
    }
}
