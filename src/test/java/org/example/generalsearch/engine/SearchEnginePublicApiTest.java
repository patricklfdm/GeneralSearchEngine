package org.example.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.time.Duration;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.example.generalsearch.engine.exception.DocumentAlreadyExistsException;
import org.example.generalsearch.engine.exception.DocumentNotFoundException;
import org.example.generalsearch.engine.exception.EngineRejectedExecutionException;
import org.example.generalsearch.engine.exception.IndexLifecycleException;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;
import org.example.generalsearch.query.Query;
import org.example.generalsearch.schema.Field;
import org.example.generalsearch.schema.annotation.IndexType;
import org.example.generalsearch.schema.annotation.SearchId;
import org.example.generalsearch.schema.annotation.SearchIndex;
import org.junit.jupiter.api.Test;

class SearchEnginePublicApiTest {
    private static final Field<Item, Long> ID =
            Field.of("id", Long.class, Item::id);
    private static final Field<Item, String> WAREHOUSE =
            Field.of("warehouse", String.class, Item::warehouse);
    private static final Field<Item, Integer> QUANTITY =
            Field.of("quantity", Integer.class, Item::quantity);
    private static final Field<Item, String> NOTE =
            Field.of("note", String.class, Item::note);

    @Test
    void manualBuilderAssemblesSchemaIndexesAndConfig() {
        SnapshotEngineConfig config =
                new SnapshotEngineConfig(1_000, 50, Duration.ZERO);
        try (SearchEngine<Long, Item> engine = SearchEngine.builder(Item.class, ID)
                .field(NOTE)
                .index(IndexDefinition.equality(WAREHOUSE))
                .index(IndexDefinition.range(QUANTITY))
                .config(config)
                .build()) {
            Item cable = new Item(7, "north", 120, "cable");
            engine.add(cable).join();

            assertSame(ID, engine.schema().idField());
            assertSame(WAREHOUSE, engine.schema().requireField("warehouse"));
            assertSame(NOTE, engine.schema().requireField("note"));
            assertEquals(List.of(cable), engine.search(Query.and(
                    Query.eq(WAREHOUSE, "north"),
                    Query.between(QUANTITY, 100, 150))));
            assertEquals(2, engine.metrics().registeredIndexCount());
        }
    }

    @Test
    void annotatedFactoryExposesCanonicalFieldsForQueriesAndDynamicIndexes() {
        try (SearchEngine<Long, AnnotatedItem> engine =
                     SearchEngine.fromAnnotatedClass(AnnotatedItem.class, Long.class)) {
            Field<AnnotatedItem, String> warehouse =
                    engine.schema().requireField("warehouse", String.class);
            Field<AnnotatedItem, Integer> score =
                    engine.schema().requireField("score", Integer.class);
            AnnotatedItem item = new AnnotatedItem(3, "west", 88);
            engine.add(item).join();

            assertEquals(List.of(item), engine.search(Query.eq(warehouse, "west")));
            assertFalse(engine.search(Query.between(score, 80, 90)).isEmpty());
            engine.createIndex(IndexDefinition.range(score)).join();
            assertEquals(2, engine.metrics().registeredIndexCount());
        }
    }

    @Test
    void operationalFailuresExposeStableExceptionTypesAndContext() {
        Product product = new Product(
                "p1", "Laptop", Category.ELECTRONICS, 999, true, 4.8);
        SnapshotUpdateEngine engine = new SnapshotUpdateEngine();
        try {
            engine.add(product).join();

            DocumentAlreadyExistsException duplicate = assertCause(
                    DocumentAlreadyExistsException.class,
                    () -> engine.add(product).join());
            assertEquals("p1", duplicate.documentId());

            Product missing = new Product(
                    "missing", "Phone", Category.ELECTRONICS, 500, false, 4.0);
            DocumentNotFoundException notFound = assertCause(
                    DocumentNotFoundException.class,
                    () -> engine.update(missing).join());
            assertEquals("missing", notFound.documentId());

            engine.createIndex(IndexDefinition.range(ProductFields.RATING)).join();
            IndexLifecycleException duplicateIndex = assertCause(
                    IndexLifecycleException.class,
                    () -> engine.createIndex(
                            IndexDefinition.range(ProductFields.RATING)).join());
            assertEquals(IndexLifecycleException.Reason.ALREADY_EXISTS,
                    duplicateIndex.reason());
            assertEquals("rating", duplicateIndex.fieldName());

            engine.close();
            EngineRejectedExecutionException rejected = assertCause(
                    EngineRejectedExecutionException.class,
                    () -> engine.remove("p1").join());
            assertEquals(EngineRejectedExecutionException.Reason.CLOSED,
                    rejected.reason());
        } finally {
            engine.close();
        }
    }

    @Test
    void queueRejectionExposesCapacityReason() throws Exception {
        BlockingScoreExtractor extractor = new BlockingScoreExtractor();
        Field<BlockingItem, Long> id =
                Field.of("id", Long.class, BlockingItem::id);
        Field<BlockingItem, Integer> score =
                Field.of("score", Integer.class, extractor::valueOf);
        SearchEngine<Long, BlockingItem> engine = SearchEngine
                .builder(BlockingItem.class, id)
                .index(IndexDefinition.range(score))
                .config(new SnapshotEngineConfig(1, 1, Duration.ZERO))
                .build();
        try {
            extractor.blockNextWriterExtraction();
            CompletableFuture<Void> first = engine.add(new BlockingItem(1, 10));
            extractor.awaitWriterExtraction();
            CompletableFuture<Void> queued = engine.add(new BlockingItem(2, 20));

            EngineRejectedExecutionException rejected = assertCause(
                    EngineRejectedExecutionException.class,
                    () -> engine.add(new BlockingItem(3, 30)).join());
            assertEquals(EngineRejectedExecutionException.Reason.QUEUE_FULL,
                    rejected.reason());

            extractor.releaseWriter();
            first.join();
            queued.join();
        } finally {
            extractor.releaseWriter();
            engine.close();
        }
    }

    private static <E extends Throwable> E assertCause(
            Class<E> expectedType,
            Runnable operation
    ) {
        CompletionException completion =
                assertThrows(CompletionException.class, operation::run);
        return assertInstanceOf(expectedType, completion.getCause());
    }

    private record Item(long id, String warehouse, int quantity, String note) {}

    private record AnnotatedItem(
            @SearchId long id,
            @SearchIndex(IndexType.EQUALITY) String warehouse,
            int score
    ) {}

    private record BlockingItem(long id, int score) {}

    private static final class BlockingScoreExtractor {
        private final AtomicBoolean armed = new AtomicBoolean();
        private volatile CountDownLatch started = new CountDownLatch(0);
        private volatile CountDownLatch release = new CountDownLatch(0);

        private int valueOf(BlockingItem item) {
            if (Thread.currentThread().getName().startsWith("snapshot-search-writer-")
                    && armed.compareAndSet(true, false)) {
                started.countDown();
                try {
                    release.await();
                } catch (InterruptedException failure) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("writer extraction interrupted", failure);
                }
            }
            return item.score();
        }

        private void blockNextWriterExtraction() {
            started = new CountDownLatch(1);
            release = new CountDownLatch(1);
            armed.set(true);
        }

        private void awaitWriterExtraction() throws InterruptedException {
            if (!started.await(5, TimeUnit.SECONDS)) {
                throw new AssertionError("writer did not reach the blocking extractor");
            }
        }

        private void releaseWriter() {
            release.countDown();
        }
    }
}
