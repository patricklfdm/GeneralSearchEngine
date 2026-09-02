package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
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
import java.util.List;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;
import io.github.patricklfdm.generalsearch.durability.RecoverySource;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V40DurableCheckpointPhase4Test {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @Test
    void explicitCheckpointPublishesManifestCleansOldWalAndReplaysPostCutWal(
            @TempDir Path directory
    ) throws IOException {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec(), 1024 * 1024);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            engine.addAll(List.of(
                    new Document(7, "seven"),
                    new Document(2, "two"))).join();
            engine.remove(2).join();
            engine.createIndex(IndexDefinition.equality(BODY)).join();
            assertEquals(3, engine.currentSequence());

            engine.checkpoint().join();
            assertEquals(3, engine.durabilityMetrics().checkpointSequence());
            assertEquals(2, engine.durabilityMetrics().walGeneration());
            assertEquals(0, engine.durabilityMetrics().walRecords());
            assertTrue(fileNames(directory).contains("gse-checkpoint-manifest"));
            assertFalse(fileNames(directory).contains(
                    "gse-wal-00000000000000000001.log"));
            assertTrue(fileNames(directory).contains(
                    "gse-wal-00000000000000000002.log"));

            engine.add(new Document(9, "nine")).join();
            assertEquals(4, engine.currentSequence());
        }

        try (DurableSearchEngine<Integer, Document> recovered = builder()
                .buildDurable(storage)) {
            assertEquals(RecoverySource.CHECKPOINT_AND_WAL,
                    recovered.durabilityMetrics().recoverySource());
            assertEquals(3, recovered.durabilityMetrics().checkpointSequence());
            assertEquals(1, recovered.durabilityMetrics().replayedRecords());
            assertEquals(4, recovered.currentSequence());
            assertEquals(new Document(7, "seven"), recovered.get(7));
            assertEquals(new Document(9, "nine"), recovered.get(9));
            assertEquals(List.of(7), recovered.search(Query.eq(BODY, "seven"))
                    .stream().map(Document::id).toList());
            SnapshotSearchEngine<Integer, Document> snapshot = asSnapshot(recovered);
            assertEquals(0, snapshot.internalDocIdForTesting(7));
            assertEquals(2, snapshot.internalDocIdForTesting(9));
        }
    }

    @Test
    void concurrentCheckpointRequestsCoalesceAtOneGenerationCut(
            @TempDir Path directory
    ) throws Exception {
        BlockingCheckpointCodec codec = new BlockingCheckpointCodec();
        DurableStorageConfig<Integer, Document> storage = config(
                directory, codec, 1024 * 1024);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            engine.add(new Document(1, "one")).join();
            codec.blockCheckpoint();
            CompletableFuture<Void> first = engine.checkpoint();
            assertTrue(codec.awaitCheckpointEncode());
            CompletableFuture<Void> second = engine.checkpoint();
            codec.releaseCheckpoint();
            CompletableFuture.allOf(first, second).get(5, TimeUnit.SECONDS);

            assertEquals(1, engine.durabilityMetrics().checkpointSequence());
            assertEquals(2, engine.durabilityMetrics().walGeneration());
            assertFalse(fileNames(directory).contains(
                    "gse-wal-00000000000000000003.log"));
        }
    }

    @Test
    void automaticThresholdRequestsCheckpointWithoutChangingMutationSuccess(
            @TempDir Path directory
    ) throws Exception {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec(), 1);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            engine.add(new Document(1, "automatic")).join();
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
            while (engine.durabilityMetrics().checkpointSequence() != 1
                    && System.nanoTime() < deadline) {
                Thread.onSpinWait();
            }
            assertEquals(1, engine.currentSequence());
            assertEquals(1, engine.durabilityMetrics().checkpointSequence());
            assertEquals(2, engine.durabilityMetrics().walGeneration());
        }
    }

    @Test
    void authoritativeCheckpointCorruptionFailsClosed(@TempDir Path directory)
            throws IOException {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec(), 1024 * 1024);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            engine.add(new Document(1, "persisted")).join();
            engine.checkpoint().join();
        }
        Path checkpoint;
        try (var entries = Files.list(directory)) {
            checkpoint = entries.filter(path -> path.getFileName().toString()
                            .matches("gse-checkpoint-.*\\.chk"))
                    .findFirst().orElseThrow();
        }
        byte[] bytes = Files.readAllBytes(checkpoint);
        bytes[bytes.length / 2] ^= 0x01;
        Files.write(checkpoint, bytes);

        DurabilityException failure = assertThrows(
                DurabilityException.class,
                () -> builder().buildDurable(storage));
        assertEquals(DurabilityException.Reason.CORRUPT_CHECKPOINT,
                failure.reason());
    }

    @Test
    void emptyCheckpointIsAuthoritativeAndReopensCheckpointOnly(
            @TempDir Path directory
    ) {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec(), 1024 * 1024);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            engine.checkpoint().join();
            assertEquals(0, engine.currentSequence());
            assertEquals(2, engine.durabilityMetrics().walGeneration());
        }
        try (DurableSearchEngine<Integer, Document> recovered = builder()
                .buildDurable(storage)) {
            assertEquals(RecoverySource.CHECKPOINT_ONLY,
                    recovered.durabilityMetrics().recoverySource());
            assertEquals(0, recovered.currentSequence());
            assertEquals(0, recovered.durabilityMetrics().replayedRecords());
        }
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID).field(BODY);
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            DurableCodec<Integer, Document> codec,
            long checkpointWalBytes
    ) {
        return DurableStorageConfig.builder(directory, codec)
                .storageIdentity("phase4-store-v1")
                .schemaIdentity("phase4-schema-v1")
                .checkpointWalBytes(checkpointWalBytes)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private static SnapshotSearchEngine<Integer, Document> asSnapshot(
            DurableSearchEngine<Integer, Document> engine
    ) {
        return (SnapshotSearchEngine<Integer, Document>) engine;
    }

    private static Set<String> fileNames(Path directory) throws IOException {
        try (var entries = Files.list(directory)) {
            return entries.map(path -> path.getFileName().toString())
                    .collect(java.util.stream.Collectors.toUnmodifiableSet());
        }
    }

    private record Document(int id, String body) {
    }

    private static class DocumentCodec implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "phase4-document-v1";
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
                Document document = new Document(input.readInt(), input.readUTF());
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
        private final CountDownLatch entered = new CountDownLatch(1);
        private final CountDownLatch release = new CountDownLatch(1);

        void blockCheckpoint() {
            block.set(true);
        }

        boolean awaitCheckpointEncode() throws InterruptedException {
            return entered.await(5, TimeUnit.SECONDS);
        }

        void releaseCheckpoint() {
            release.countDown();
        }

        @Override
        public byte[] encodeDocument(Document document) {
            if (block.compareAndSet(true, false)) {
                entered.countDown();
                try {
                    if (!release.await(5, TimeUnit.SECONDS)) {
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
