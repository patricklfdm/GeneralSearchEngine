package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.RecoverySource;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V40DurablePerformancePhase6Test {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @Test
    void retainedByteSnapshotToleratesConcurrentCheckpointCleanup(
            @TempDir Path directory
    ) throws IOException {
        Path metadata = directory.resolve(DurableStorageOwner.METADATA_FILE);
        Path checkpoint = directory.resolve(
                "gse-checkpoint-00000000000000000131-"
                        + "c1015dd8fb2d4039964fbd606e49c359.chk");
        Files.write(metadata, new byte[17]);
        Files.write(checkpoint, new byte[31]);
        List<Path> snapshot = List.of(metadata, checkpoint);

        Files.delete(checkpoint);

        assertEquals(17L,
                DurableStorageOwner.retainedBytesFromSnapshot(snapshot));
    }

    @Test
    void internalCountersReportActualSuccessfulForceGroups(@TempDir Path directory) {
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(directory))) {
            engine.addAll(documents(100)).join();
            List<CompletableFuture<Void>> updates = new ArrayList<>();
            for (int operation = 0; operation < 80; operation++) {
                int id = operation % 100;
                updates.add(engine.update(new Document(
                        id, "updated-" + operation)));
            }
            CompletableFuture.allOf(
                    updates.toArray(CompletableFuture[]::new)).join();

            DurablePerformanceSnapshot snapshot = snapshot(engine);
            assertEquals(81, snapshot.forcedUnits());
            assertTrue(snapshot.forceGroups() >= 2);
            assertTrue(snapshot.forceGroups() <= snapshot.forcedUnits());
            assertTrue(snapshot.maximumForceGroupSize() >= 1);
            assertTrue(snapshot.maximumForceGroupSize() <= 80);
            assertTrue(snapshot.walAppendForceNanos() >= 0);
        }
    }

    @Test
    void recoveryStageTimingsRemainInternalAndMatchRecoverySource(
            @TempDir Path directory
    ) {
        DurableStorageConfig<Integer, Document> config = config(directory);
        try (DurableSearchEngine<Integer, Document> writer = builder()
                .buildDurable(config)) {
            writer.addAll(documents(100)).join();
            writer.checkpoint().join();
            writer.update(new Document(0, "post-checkpoint")).join();
        }

        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(config)) {
            assertEquals(RecoverySource.CHECKPOINT_AND_WAL,
                    reopened.durabilityMetrics().recoverySource());
            DurablePerformanceSnapshot snapshot = snapshot(reopened);
            assertTrue(snapshot.storageOpenNanos() >= 0);
            assertTrue(snapshot.checkpointLoadNanos() >= 0);
            assertTrue(snapshot.replayAndRebuildNanos() >= 0);
            assertEquals(0, snapshot.forceGroups());
            assertEquals(0, snapshot.forcedUnits());
        }
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID)
                .field(BODY)
                .index(IndexDefinition.equality(BODY));
    }

    private static DurableStorageConfig<Integer, Document> config(Path directory) {
        return DurableStorageConfig.builder(directory, new DocumentCodec())
                .storageIdentity("phase6-performance-store-v1")
                .schemaIdentity("phase6-performance-schema-v1")
                .checkpointWalBytes(16L * 1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private static DurablePerformanceSnapshot snapshot(
            DurableSearchEngine<Integer, Document> engine
    ) {
        return ((DurableSnapshotSearchEngine<Integer, Document>) engine)
                .performanceSnapshot();
    }

    private static List<Document> documents(int count) {
        List<Document> documents = new ArrayList<>(count);
        for (int id = 0; id < count; id++) {
            documents.add(new Document(id, "document-" + id));
        }
        return documents;
    }

    private record Document(int id, String body) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "phase6-performance-codec-v1";
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
                return new Document(input.readInt(), input.readUTF());
            } catch (IOException failure) {
                throw new IllegalArgumentException(failure);
            }
        }
    }
}
