package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Arrays;
import java.util.List;
import java.util.zip.CRC32C;
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

class V40DurableRecoveryPhase3Test {
    private static final int GENERATION_HEADER_BYTES = 48;
    private static final int FRAME_HEADER_BYTES = 28;
    private static final int FRAME_TRAILER_BYTES = 4;
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, Integer> PRICE =
            Field.of("price", Integer.class, Document::price);

    @Test
    void walOnlyRecoveryRestoresSlotsIndexesQueriesAndContinuedSequence(
            @TempDir Path directory
    ) {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec(), "phase3-schema-v1");
        try (DurableSearchEngine<Integer, Document> engine = builder(BODY)
                .buildDurable(storage)) {
            engine.addAll(List.of(
                    new Document(7, "guide", 70),
                    new Document(2, "archive", 20))).join();
            engine.update(new Document(7, "updated", 75)).join();
            engine.remove(2).join();
            engine.remove(99).join();
            engine.createIndex(IndexDefinition.range(PRICE)).join();
            assertEquals(5, engine.currentSequence());
            assertEquals(0, asSnapshot(engine).internalDocIdForTesting(7));
        }

        try (DurableSearchEngine<Integer, Document> recovered = builder(BODY)
                .buildDurable(storage)) {
            SnapshotSearchEngine<Integer, Document> snapshot = asSnapshot(recovered);
            assertEquals(RecoverySource.WAL_ONLY,
                    recovered.durabilityMetrics().recoverySource());
            assertEquals(5, recovered.currentSequence());
            assertEquals(5, recovered.durabilityMetrics().replayedRecords());
            assertEquals(0, recovered.durabilityMetrics().checkpointSequence());
            assertEquals(0, snapshot.metrics().snapshotVersion());
            assertEquals(2, snapshot.snapshotForTesting().indexes().indexes().size());
            assertEquals(new Document(7, "updated", 75), recovered.get(7));
            assertNull(recovered.get(2));
            assertEquals(List.of(7), recovered.search(Query.eq(BODY, "updated"))
                    .stream().map(Document::id).toList());
            assertEquals(0, snapshot.internalDocIdForTesting(7));

            recovered.add(new Document(9, "next", 90)).join();
            assertEquals(6, recovered.currentSequence());
            assertEquals(2, snapshot.internalDocIdForTesting(9));
            assertEquals(1, snapshot.metrics().snapshotVersion());
        }

        try (DurableSearchEngine<Integer, Document> recoveredAgain = builder(BODY)
                .buildDurable(storage)) {
            assertEquals(6, recoveredAgain.currentSequence());
            assertEquals(new Document(9, "next", 90), recoveredAgain.get(9));
            assertEquals(2, asSnapshot(recoveredAgain).internalDocIdForTesting(9));
            assertEquals(0, recoveredAgain.metrics().snapshotVersion());
        }
    }

    @Test
    void incompleteNewestHeaderIsTruncatedBeforeWriterAdmission(
            @TempDir Path directory
    ) throws IOException {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec(), "phase3-schema-v1");
        try (DurableSearchEngine<Integer, Document> engine = builder(BODY)
                .buildDurable(storage)) {
            engine.add(new Document(1, "complete", 10)).join();
        }
        Path wal = wal(directory);
        long validBytes = Files.size(wal);
        Files.write(
                wal,
                ByteBuffer.allocate(8).order(ByteOrder.BIG_ENDIAN)
                        .putInt(0x47534546).putShort((short) 1).putShort((short) 0)
                        .array(),
                StandardOpenOption.APPEND);
        assertEquals(validBytes + 8, Files.size(wal));

        try (DurableSearchEngine<Integer, Document> recovered = builder(BODY)
                .buildDurable(storage)) {
            assertEquals(1, recovered.currentSequence());
            assertEquals(validBytes, Files.size(wal));
            recovered.add(new Document(2, "after-tail", 20)).join();
            assertEquals(2, recovered.currentSequence());
        }
    }

    @Test
    void completeCorruptionSequenceGapAndInvalidShortTailFailClosed(
            @TempDir Path root
    ) throws IOException {
        Path checksum = createOneRecordStore(root.resolve("checksum"));
        byte[] checksumWal = Files.readAllBytes(wal(checksum));
        checksumWal[GENERATION_HEADER_BYTES + FRAME_HEADER_BYTES] ^= 0x01;
        Files.write(wal(checksum), checksumWal);
        assertReason(checksum, new DocumentCodec(), "phase3-schema-v1",
                DurabilityException.Reason.CORRUPT_WAL);

        Path sequence = createOneRecordStore(root.resolve("sequence"));
        byte[] sequenceWal = Files.readAllBytes(wal(sequence));
        ByteBuffer.wrap(sequenceWal).order(ByteOrder.BIG_ENDIAN)
                .putLong(GENERATION_HEADER_BYTES + 12, 2L);
        rewriteFrameChecksum(sequenceWal, GENERATION_HEADER_BYTES);
        Files.write(wal(sequence), sequenceWal);
        assertReason(sequence, new DocumentCodec(), "phase3-schema-v1",
                DurabilityException.Reason.CORRUPT_WAL);

        Path shortTail = createOneRecordStore(root.resolve("short-tail"));
        long before = Files.size(wal(shortTail));
        Files.write(wal(shortTail), new byte[]{0}, StandardOpenOption.APPEND);
        assertReason(shortTail, new DocumentCodec(), "phase3-schema-v1",
                DurabilityException.Reason.CORRUPT_WAL);
        assertEquals(before + 1, Files.size(wal(shortTail)));

        Path payload = createOneRecordStore(root.resolve("payload"));
        byte[] invalidPayload = Files.readAllBytes(wal(payload));
        invalidPayload[GENERATION_HEADER_BYTES + FRAME_HEADER_BYTES] = 9;
        rewriteFrameChecksum(invalidPayload, GENERATION_HEADER_BYTES);
        Files.write(wal(payload), invalidPayload);
        assertReason(payload, new DocumentCodec(), "phase3-schema-v1",
                DurabilityException.Reason.CORRUPT_WAL);
    }

    @Test
    void structurallyValidDuplicateAddFailsReplayWithoutPublishingEngine(
            @TempDir Path directory
    ) throws IOException {
        createOneRecordStore(directory);
        Path wal = wal(directory);
        byte[] original = Files.readAllBytes(wal);
        byte[] duplicated = Arrays.copyOfRange(
                original, GENERATION_HEADER_BYTES, original.length);
        ByteBuffer.wrap(duplicated).order(ByteOrder.BIG_ENDIAN).putLong(12, 2L);
        rewriteFrameChecksum(duplicated, 0);
        Files.write(wal, duplicated, StandardOpenOption.APPEND);

        assertReason(directory, new DocumentCodec(), "phase3-schema-v1",
                DurabilityException.Reason.REPLAY_FAILURE);
        try (DurableSearchEngine<Integer, Document> repaired = builder(BODY)
                .buildDurable(config(
                        directory,
                        new DocumentCodec(),
                        "phase3-schema-v1"))) {
            throw new AssertionError("corrupt logical history unexpectedly reopened: "
                    + repaired);
        } catch (DurabilityException expected) {
            assertEquals(DurabilityException.Reason.REPLAY_FAILURE,
                    expected.reason());
        }
    }

    @Test
    void metadataIdentityChecksumAndWalHistoryMismatchFailBeforeReplay(
            @TempDir Path root
    ) throws IOException {
        Path identity = createOneRecordStore(root.resolve("identity"));
        assertReason(identity, new DocumentCodec(), "changed-schema-v1",
                DurabilityException.Reason.INCOMPATIBLE_STORAGE);

        Path metadata = createOneRecordStore(root.resolve("metadata"));
        byte[] metadataBytes = Files.readAllBytes(metadata.resolve("gse-metadata"));
        metadataBytes[16] ^= 0x01;
        Files.write(metadata.resolve("gse-metadata"), metadataBytes);
        assertReason(metadata, new DocumentCodec(), "phase3-schema-v1",
                DurabilityException.Reason.INCOMPATIBLE_STORAGE);

        Path zeroHistory = createOneRecordStore(root.resolve("zero-history"));
        Path zeroMetadataPath = zeroHistory.resolve("gse-metadata");
        byte[] zeroMetadata = Files.readAllBytes(zeroMetadataPath);
        java.util.Arrays.fill(zeroMetadata, 12, 28, (byte) 0);
        rewriteMetadataChecksum(zeroMetadata);
        Files.write(zeroMetadataPath, zeroMetadata);
        assertReason(zeroHistory, new DocumentCodec(), "phase3-schema-v1",
                DurabilityException.Reason.INCOMPATIBLE_STORAGE);

        Path history = createOneRecordStore(root.resolve("history"));
        byte[] historyWal = Files.readAllBytes(wal(history));
        historyWal[12] ^= 0x01;
        rewriteGenerationChecksum(historyWal);
        Files.write(wal(history), historyWal);
        assertReason(history, new DocumentCodec(), "phase3-schema-v1",
                DurabilityException.Reason.CORRUPT_WAL);
    }

    @Test
    void codecAndIndexRebuildFailuresUseStableOpenCategories(
            @TempDir Path root
    ) {
        Path codecDirectory = createOneRecordStore(root.resolve("codec"));
        DurableCodec<Integer, Document> failingCodec = new DocumentCodec() {
            @Override
            public Document decodeDocument(byte[] bytes) {
                throw new IllegalArgumentException("injected decode failure");
            }
        };
        assertReason(codecDirectory, failingCodec, "phase3-schema-v1",
                DurabilityException.Reason.CODEC_FAILURE);

        Path indexDirectory = createOneRecordStore(root.resolve("index"));
        Field<Document, String> failingBody = Field.of(
                "body",
                String.class,
                document -> {
                    throw new IllegalStateException("injected extractor failure");
                });
        DurabilityException rebuild = assertThrows(
                DurabilityException.class,
                () -> builder(failingBody).buildDurable(config(
                        indexDirectory,
                        new DocumentCodec(),
                        "phase3-schema-v1")));
        assertEquals(DurabilityException.Reason.INDEX_REBUILD_FAILURE,
                rebuild.reason());
    }

    @Test
    void startupIndexMismatchAndUnknownDirectoryMemberFailClosed(
            @TempDir Path root
    ) throws IOException {
        Path duplicate = root.resolve("duplicate");
        DurabilityException duplicateFailure = assertThrows(
                DurabilityException.class,
                () -> SearchEngine.builder(Document.class, ID)
                        .field(BODY)
                        .field(PRICE)
                        .index(IndexDefinition.equality(BODY))
                        .index(IndexDefinition.equality(BODY))
                        .buildDurable(config(
                                duplicate,
                                new DocumentCodec(),
                                "phase3-schema-v1")));
        assertEquals(DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                duplicateFailure.reason());
        assertFalse(Files.exists(duplicate));

        Path indexes = createOneRecordStore(root.resolve("indexes"));
        DurabilityException mismatch = assertThrows(
                DurabilityException.class,
                () -> SearchEngine.builder(Document.class, ID)
                        .field(BODY)
                        .field(PRICE)
                        .buildDurable(config(
                                indexes,
                                new DocumentCodec(),
                                "phase3-schema-v1")));
        assertEquals(DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                mismatch.reason());

        Path unknown = createOneRecordStore(root.resolve("unknown"));
        Files.writeString(unknown.resolve("gse-unknown"), "not authoritative");
        assertReason(unknown, new DocumentCodec(), "phase3-schema-v1",
                DurabilityException.Reason.INCOMPATIBLE_STORAGE);
    }

    private static Path createOneRecordStore(Path directory) {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec(), "phase3-schema-v1");
        try (DurableSearchEngine<Integer, Document> engine = builder(BODY)
                .buildDurable(storage)) {
            engine.add(new Document(1, "one", 10)).join();
        }
        return directory;
    }

    private static void assertReason(
            Path directory,
            DurableCodec<Integer, Document> codec,
            String schemaIdentity,
            DurabilityException.Reason expected
    ) {
        DurabilityException failure = assertThrows(
                DurabilityException.class,
                () -> builder(BODY).buildDurable(config(
                        directory, codec, schemaIdentity)));
        assertEquals(expected, failure.reason());
    }

    private static SearchEngineBuilder<Integer, Document> builder(
            Field<Document, String> body
    ) {
        return SearchEngine.builder(Document.class, ID)
                .field(body)
                .field(PRICE)
                .index(IndexDefinition.equality(body))
                .config(new SnapshotEngineConfig(
                        1_000,
                        100,
                        java.time.Duration.ofMillis(2)));
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            DurableCodec<Integer, Document> codec,
            String schemaIdentity
    ) {
        return DurableStorageConfig.builder(directory, codec)
                .storageIdentity("phase3-store-v1")
                .schemaIdentity(schemaIdentity)
                .build();
    }

    @SuppressWarnings("unchecked")
    private static SnapshotSearchEngine<Integer, Document> asSnapshot(
            DurableSearchEngine<Integer, Document> engine
    ) {
        return (SnapshotSearchEngine<Integer, Document>) engine;
    }

    private static Path wal(Path directory) {
        return directory.resolve("gse-wal-00000000000000000001.log");
    }

    private static void rewriteGenerationChecksum(byte[] wal) {
        CRC32C checksum = new CRC32C();
        checksum.update(wal, 0, GENERATION_HEADER_BYTES - Integer.BYTES);
        ByteBuffer.wrap(wal).order(ByteOrder.BIG_ENDIAN)
                .putInt(GENERATION_HEADER_BYTES - Integer.BYTES,
                        (int) checksum.getValue());
    }

    private static void rewriteMetadataChecksum(byte[] metadata) {
        CRC32C checksum = new CRC32C();
        checksum.update(metadata, 0, metadata.length - Integer.BYTES);
        ByteBuffer.wrap(metadata).order(ByteOrder.BIG_ENDIAN)
                .putInt(metadata.length - Integer.BYTES,
                        (int) checksum.getValue());
    }

    private static void rewriteFrameChecksum(byte[] bytes, int frameStart) {
        ByteBuffer input = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN);
        int frameLength = input.getInt(frameStart + 8);
        CRC32C checksum = new CRC32C();
        checksum.update(bytes, frameStart, frameLength - FRAME_TRAILER_BYTES);
        input.putInt(frameStart + frameLength - FRAME_TRAILER_BYTES,
                (int) checksum.getValue());
    }

    private record Document(int id, String body, int price) {
    }

    private static class DocumentCodec implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "phase3-document-v1";
        }

        @Override
        public int codecVersion() {
            return 1;
        }

        @Override
        public byte[] encodeKey(Integer key) {
            return ByteBuffer.allocate(Integer.BYTES)
                    .order(ByteOrder.BIG_ENDIAN).putInt(key).array();
        }

        @Override
        public Integer decodeKey(byte[] bytes) {
            if (bytes.length != Integer.BYTES) {
                throw new IllegalArgumentException("invalid integer key");
            }
            return ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN).getInt();
        }

        @Override
        public byte[] encodeDocument(Document document) {
            byte[] body = document.body().getBytes(StandardCharsets.UTF_8);
            try {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (DataOutputStream output = new DataOutputStream(bytes)) {
                    output.writeInt(document.id());
                    output.writeInt(document.price());
                    output.writeInt(body.length);
                    output.write(body);
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
                int id = input.readInt();
                int price = input.readInt();
                int length = input.readInt();
                if (length < 0 || length != input.available()) {
                    throw new IllegalArgumentException("invalid document length");
                }
                return new Document(
                        id,
                        new String(input.readNBytes(length), StandardCharsets.UTF_8),
                        price);
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid document", failure);
            }
        }
    }
}
