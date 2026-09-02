package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;
import io.github.patricklfdm.generalsearch.durability.DurabilityStatus;
import io.github.patricklfdm.generalsearch.durability.RecoverySource;
import io.github.patricklfdm.generalsearch.engine.exception.EngineRejectedExecutionException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V40DurableLifecyclePhase5Test {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, Integer> PRICE =
            Field.of("price", Integer.class, Document::price);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, SimpleAnalyzer.INSTANCE);

    @AfterEach
    void clearFaults() {
        System.clearProperty(DurableIoFaults.FAILURE_PROPERTY);
        System.clearProperty(DurableIoFaults.MAX_WRITE_PROPERTY);
    }

    @Test
    void everyMutationAndBuiltInDynamicIndexTransitionSurvivesCheckpoint(
            @TempDir Path directory
    ) {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec(), 1024 * 1024, 64L * 1024 * 1024);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            engine.add(document(1, "one", 10)).join();
            engine.addAll(List.of(
                    document(2, "two", 20),
                    document(3, "three", 30))).join();
            engine.update(document(1, "one-updated", 11)).join();
            engine.updateAll(List.of(
                    document(2, "two-updated", 22),
                    document(3, "three-updated", 33))).join();
            engine.remove(99).join();
            engine.removeAll(List.of(3, 100)).join();

            engine.createIndex(IndexDefinition.equality(BODY)).join();
            assertEquals(List.of(1), ids(engine.search(Query.eq(
                    BODY, "one-updated"))));
            engine.dropIndex(BODY.name()).join();
            engine.createIndex(IndexDefinition.range(PRICE)).join();
            assertEquals(List.of(1, 2), ids(engine.search(Query.between(
                    PRICE, 0, 30))));
            engine.dropIndex(PRICE.name()).join();
            engine.createIndex(IndexDefinition.prefix(BODY)).join();
            assertEquals(List.of(2), ids(engine.search(Query.prefix(
                    BODY, "two"))));
            engine.dropIndex(BODY.name()).join();
            engine.createIndex(IndexDefinition.text(TEXT)).join();
            assertEquals(List.of(1), ids(engine.search(Query.term(
                    TEXT, "one"))));
            assertEquals(13, engine.currentSequence());
            engine.checkpoint().join();
        }

        try (DurableSearchEngine<Integer, Document> recovered = builder()
                .buildDurable(storage)) {
            assertEquals(13, recovered.currentSequence());
            assertEquals(RecoverySource.CHECKPOINT_ONLY,
                    recovered.durabilityMetrics().recoverySource());
            assertEquals(document(1, "one-updated", 11), recovered.get(1));
            assertEquals(document(2, "two-updated", 22), recovered.get(2));
            assertNull(recovered.get(3));
            assertEquals(List.of(1), ids(recovered.search(Query.term(TEXT, "one"))));
        }
    }

    @Test
    void checkpointWalAndCloseRaceDrainsAcceptedWorkAndRejectsNewAdmission(
            @TempDir Path directory
    ) throws Exception {
        BlockingCheckpointCodec codec = new BlockingCheckpointCodec();
        DurableStorageConfig<Integer, Document> storage = config(
                directory, codec, 1024 * 1024, 64L * 1024 * 1024);
        DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage);
        engine.add(document(0, "seed", 0)).join();
        codec.blockCheckpoint();
        CompletableFuture<Void> firstCheckpoint = engine.checkpoint();
        assertTrue(codec.awaitCheckpointEncode());

        ExecutorService producers = Executors.newFixedThreadPool(4);
        try {
            List<CompletableFuture<Void>> accepted = new ArrayList<>();
            for (int id = 1; id <= 80; id++) {
                int captured = id;
                accepted.add(CompletableFuture.runAsync(() -> engine.add(
                        document(captured, "body-" + captured, captured)).join(),
                        producers));
            }
            CompletableFuture.allOf(accepted.toArray(CompletableFuture[]::new))
                    .get(10, TimeUnit.SECONDS);
            CompletableFuture<Void> coalescedCheckpoint = engine.checkpoint();

            CountDownLatch closeStarted = new CountDownLatch(1);
            CompletableFuture<Void> close = CompletableFuture.runAsync(() -> {
                closeStarted.countDown();
                engine.close();
            });
            assertTrue(closeStarted.await(5, TimeUnit.SECONDS));
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
            while (engine.metrics().acceptingRequests()
                    && System.nanoTime() < deadline) {
                Thread.onSpinWait();
            }
            assertFalse(engine.metrics().acceptingRequests());
            CompletionException rejected = assertThrows(
                    CompletionException.class,
                    () -> engine.add(document(999, "rejected", 999)).join());
            assertInstanceOf(EngineRejectedExecutionException.class,
                    rejected.getCause());
            assertFalse(close.isDone());

            codec.releaseCheckpoint();
            CompletableFuture.allOf(firstCheckpoint, coalescedCheckpoint, close)
                    .get(10, TimeUnit.SECONDS);
        } finally {
            producers.shutdownNow();
            codec.releaseCheckpoint();
            engine.close();
        }

        try (DurableSearchEngine<Integer, Document> recovered = builder()
                .buildDurable(storage)) {
            assertEquals(81, recovered.currentSequence());
            for (int id = 0; id <= 80; id++) {
                assertNotNull(recovered.get(id));
            }
            assertEquals(RecoverySource.CHECKPOINT_AND_WAL,
                    recovered.durabilityMetrics().recoverySource());
        }
    }

    @Test
    void concurrentProducersAndReadersPreserveOneContiguousDurableHistory(
            @TempDir Path directory
    ) throws Exception {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec(), 1024 * 1024,
                64L * 1024 * 1024);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            ExecutorService workers = Executors.newFixedThreadPool(10);
            AtomicBoolean reading = new AtomicBoolean(true);
            AtomicReference<Throwable> readerFailure = new AtomicReference<>();
            List<CompletableFuture<Void>> readers = new ArrayList<>();
            for (int reader = 0; reader < 2; reader++) {
                readers.add(CompletableFuture.runAsync(() -> {
                    try {
                        while (reading.get()) {
                            List<Document> snapshot = engine.search(
                                    Query.between(PRICE, 0, 10_000));
                            for (Document document : snapshot) {
                                if (document == null || document.id() < 0) {
                                    throw new AssertionError(
                                            "reader observed invalid document");
                                }
                            }
                        }
                    } catch (Throwable failure) {
                        readerFailure.compareAndSet(null, failure);
                    }
                }, workers));
            }
            List<CompletableFuture<Void>> producers = new ArrayList<>();
            for (int producer = 0; producer < 8; producer++) {
                int base = producer * 50;
                producers.add(CompletableFuture.runAsync(() -> {
                    for (int offset = 0; offset < 50; offset++) {
                        int id = base + offset;
                        engine.add(document(id, "concurrent-" + id, id)).join();
                    }
                }, workers));
            }
            try {
                CompletableFuture.allOf(producers.toArray(CompletableFuture[]::new))
                        .get(15, TimeUnit.SECONDS);
            } finally {
                reading.set(false);
            }
            CompletableFuture.allOf(readers.toArray(CompletableFuture[]::new))
                    .get(5, TimeUnit.SECONDS);
            workers.shutdownNow();

            assertNull(readerFailure.get());
            assertEquals(400, engine.currentSequence());
            assertEquals(400, engine.durabilityMetrics().walRecords());
            assertEquals(400, engine.metrics().documentCount());
            engine.checkpoint().join();
        }

        try (DurableSearchEngine<Integer, Document> recovered = builder()
                .buildDurable(storage)) {
            assertEquals(400, recovered.currentSequence());
            assertEquals(400, recovered.metrics().documentCount());
            for (int id = 0; id < 400; id++) {
                assertEquals(document(id, "concurrent-" + id, id),
                        recovered.get(id));
            }
        }
    }

    @Test
    void safePreAuthorityCheckpointFailuresKeepWriterUsable(
            @TempDir Path root
    ) {
        List<String> failurePoints = List.of(
                "checkpoint-before-data-rename",
                "checkpoint-before-manifest-force",
                "checkpoint-before-manifest-rename");
        for (int index = 0; index < failurePoints.size(); index++) {
            Path directory = root.resolve("safe-" + index);
            DurableStorageConfig<Integer, Document> storage = config(
                    directory, new DocumentCodec(), 1024 * 1024,
                    64L * 1024 * 1024);
            try (DurableSearchEngine<Integer, Document> engine = builder()
                    .buildDurable(storage)) {
                engine.add(document(1, "one", 1)).join();
                System.setProperty(DurableIoFaults.FAILURE_PROPERTY,
                        failurePoints.get(index));
                assertCheckpointFailure(engine, DurabilityException.Reason.IO_FAILURE);
                System.clearProperty(DurableIoFaults.FAILURE_PROPERTY);

                assertEquals(DurabilityStatus.OPEN,
                        engine.durabilityMetrics().status());
                assertEquals(DurabilityException.Reason.IO_FAILURE,
                        engine.durabilityMetrics().lastCheckpointFailure()
                                .orElseThrow());
                engine.add(document(2, "two", 2)).join();
                engine.checkpoint().join();
                assertEquals(2, engine.currentSequence());
            }
            try (DurableSearchEngine<Integer, Document> recovered = builder()
                    .buildDurable(storage)) {
                assertEquals(2, recovered.currentSequence());
                assertNotNull(recovered.get(1));
                assertNotNull(recovered.get(2));
            }
        }
    }

    @Test
    void postManifestDirectoryForceFailureIsTerminalButReopensAuthority(
            @TempDir Path directory
    ) {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec(), 1024 * 1024,
                64L * 1024 * 1024);
        DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage);
        try {
            engine.add(document(1, "one", 1)).join();
            System.setProperty(DurableIoFaults.FAILURE_PROPERTY,
                    "checkpoint-before-directory-force");
            assertCheckpointFailure(engine, DurabilityException.Reason.IO_FAILURE);
            assertEquals(DurabilityStatus.FAILED,
                    engine.durabilityMetrics().status());
            CompletionException rejected = assertThrows(
                    CompletionException.class,
                    () -> engine.add(document(2, "blocked", 2)).join());
            assertEquals(DurabilityException.Reason.IO_FAILURE,
                    assertInstanceOf(DurabilityException.class,
                            rejected.getCause()).reason());
        } finally {
            System.clearProperty(DurableIoFaults.FAILURE_PROPERTY);
            engine.close();
        }

        try (DurableSearchEngine<Integer, Document> recovered = builder()
                .buildDurable(storage)) {
            assertEquals(1, recovered.currentSequence());
            assertEquals(document(1, "one", 1), recovered.get(1));
            recovered.add(document(2, "continued", 2)).join();
            assertEquals(2, recovered.currentSequence());
        }
    }

    @Test
    void cleanupFailureIsDiagnosticAndLaterCheckpointRestoresBound(
            @TempDir Path directory
    ) throws IOException {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec(), 1024 * 1024,
                64L * 1024 * 1024);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            engine.add(document(1, "one", 1)).join();
            System.setProperty(DurableIoFaults.FAILURE_PROPERTY,
                    "checkpoint-before-cleanup-delete");
            engine.checkpoint().join();
            System.clearProperty(DurableIoFaults.FAILURE_PROPERTY);

            assertEquals(DurabilityStatus.OPEN,
                    engine.durabilityMetrics().status());
            assertEquals(DurabilityException.Reason.IO_FAILURE,
                    engine.durabilityMetrics().lastCheckpointFailure()
                            .orElseThrow());
            assertTrue(walCount(directory) > 1);

            engine.add(document(2, "two", 2)).join();
            engine.checkpoint().join();
            assertEquals(1, walCount(directory));
            assertEquals(1, checkpointCount(directory));
            assertTrue(engine.durabilityMetrics().lastCheckpointFailure().isEmpty());
        }
    }

    @Test
    void boundedShortWritesAndRepeatedCheckpointsPreserveRetainedFootprint(
            @TempDir Path directory
    ) throws IOException {
        long maximumRetained = 256L * 1024;
        System.setProperty(DurableIoFaults.MAX_WRITE_PROPERTY, "3");
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec(), 128L * 1024, maximumRetained);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            for (int cycle = 0; cycle < 24; cycle++) {
                int id = cycle;
                engine.add(document(id, "cycle-" + cycle, cycle)).join();
                engine.checkpoint().join();
                assertTrue(engine.durabilityMetrics().retainedBytes()
                        <= maximumRetained);
                assertEquals(1, walCount(directory));
                assertEquals(1, checkpointCount(directory));
            }
            assertEquals(24, engine.currentSequence());
            assertEquals(25, engine.durabilityMetrics().walGeneration());
        }
        System.clearProperty(DurableIoFaults.MAX_WRITE_PROPERTY);

        try (DurableSearchEngine<Integer, Document> recovered = builder()
                .buildDurable(storage)) {
            assertEquals(24, recovered.currentSequence());
            for (int id = 0; id < 24; id++) {
                assertNotNull(recovered.get(id));
            }
        }
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID)
                .field(BODY)
                .field(PRICE)
                .textField(TEXT)
                .config(new SnapshotEngineConfig(
                        2_000, 64, Duration.ofMillis(2)));
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            DurableCodec<Integer, Document> codec,
            long checkpointWalBytes,
            long maximumRetainedBytes
    ) {
        return DurableStorageConfig.builder(directory, codec)
                .storageIdentity("phase5-store-v1")
                .schemaIdentity("phase5-schema-v1")
                .checkpointWalBytes(checkpointWalBytes)
                .maxRetainedBytes(maximumRetainedBytes)
                .build();
    }

    private static void assertCheckpointFailure(
            DurableSearchEngine<Integer, Document> engine,
            DurabilityException.Reason reason
    ) {
        CompletionException rejected = assertThrows(
                CompletionException.class, () -> engine.checkpoint().join());
        assertEquals(reason, assertInstanceOf(
                DurabilityException.class, rejected.getCause()).reason());
    }

    private static int walCount(Path directory) throws IOException {
        try (var files = Files.list(directory)) {
            return (int) files.filter(path -> path.getFileName().toString()
                    .matches("gse-wal-[0-9]{20}\\.log")).count();
        }
    }

    private static int checkpointCount(Path directory) throws IOException {
        try (var files = Files.list(directory)) {
            return (int) files.filter(path -> path.getFileName().toString()
                    .matches("gse-checkpoint-.*\\.chk")).count();
        }
    }

    private static List<Integer> ids(List<Document> documents) {
        return documents.stream().map(Document::id).toList();
    }

    private static Document document(int id, String body, int price) {
        return new Document(id, body, price);
    }

    private record Document(int id, String body, int price) {
    }

    private static class DocumentCodec implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "phase5-document-v1";
        }

        @Override
        public int codecVersion() {
            return 1;
        }

        @Override
        public byte[] encodeKey(Integer key) {
            return ByteBuffer.allocate(Integer.BYTES).putInt(key).array();
        }

        @Override
        public Integer decodeKey(byte[] bytes) {
            if (bytes.length != Integer.BYTES) {
                throw new IllegalArgumentException("invalid key bytes");
            }
            return ByteBuffer.wrap(bytes).getInt();
        }

        @Override
        public byte[] encodeDocument(Document document) {
            try {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (DataOutputStream output = new DataOutputStream(bytes)) {
                    output.writeInt(document.id());
                    output.writeUTF(document.body());
                    output.writeInt(document.price());
                }
                return bytes.toByteArray();
            } catch (IOException impossible) {
                throw new AssertionError(impossible);
            }
        }

        @Override
        public Document decodeDocument(byte[] bytes) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(bytes))) {
                Document document = new Document(
                        input.readInt(), input.readUTF(), input.readInt());
                if (input.available() != 0) {
                    throw new IllegalArgumentException("trailing document bytes");
                }
                return document;
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid document bytes", failure);
            }
        }
    }

    private static final class BlockingCheckpointCodec extends DocumentCodec {
        private final AtomicBoolean block = new AtomicBoolean();
        private final AtomicReference<CountDownLatch> entered =
                new AtomicReference<>(new CountDownLatch(1));
        private final AtomicReference<CountDownLatch> release =
                new AtomicReference<>(new CountDownLatch(1));

        void blockCheckpoint() {
            entered.set(new CountDownLatch(1));
            release.set(new CountDownLatch(1));
            block.set(true);
        }

        boolean awaitCheckpointEncode() throws InterruptedException {
            return entered.get().await(5, TimeUnit.SECONDS);
        }

        void releaseCheckpoint() {
            release.get().countDown();
        }

        @Override
        public byte[] encodeDocument(Document document) {
            if (Thread.currentThread().getName().equals("gse-durable-checkpoint")
                    && block.compareAndSet(true, false)) {
                entered.get().countDown();
                try {
                    if (!release.get().await(10, TimeUnit.SECONDS)) {
                        throw new IllegalStateException("checkpoint codec timed out");
                    }
                } catch (InterruptedException failure) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException(failure);
                }
            }
            return super.encodeDocument(document);
        }
    }
}
