package io.github.patricklfdm.generalsearch.durability;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SnapshotEngineConfig;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V40DurableEnginePhase2Test {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @Test
    void freshWalPreservesLogicalUnitsSequencesAndPublicationOrder(
            @TempDir Path directory
    ) throws Exception {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec());
        DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage);
        assertEquals(0, engine.currentSequence());
        assertEquals(Set.of("gse.lock", "gse-metadata",
                        "gse-wal-00000000000000000001.log"),
                fileNames(directory));

        List<CompletableFuture<Void>> singles = List.of(
                engine.add(new Document(7, "seven")),
                engine.add(new Document(2, "two")),
                engine.add(new Document(9, "nine")));
        CompletableFuture.allOf(singles.toArray(CompletableFuture[]::new)).join();
        assertEquals(3, engine.currentSequence());
        assertEquals("seven", engine.get(7).body());

        engine.addAll(List.of(
                new Document(1, "one"),
                new Document(5, "five"))).join();
        assertEquals(4, engine.currentSequence());
        engine.remove(99).join();
        assertEquals(5, engine.currentSequence());
        engine.addAll(List.of()).join();
        assertEquals(5, engine.currentSequence());
        engine.update(new Document(7, "updated")).join();
        engine.createIndex(IndexDefinition.equality(BODY)).join();
        engine.dropIndex(BODY.name()).join();
        assertEquals(8, engine.currentSequence());
        assertEquals("updated", engine.get(7).body());

        V40WalInspector.Inspection inspection = V40WalInspector.inspect(
                directory.resolve("gse-wal-00000000000000000001.log"));
        assertEquals(1, inspection.generation());
        assertEquals(1, inspection.firstSequence());
        assertEquals(List.of(1L, 2L, 3L, 4L, 5L, 6L, 7L, 8L),
                inspection.frames().stream()
                        .map(V40WalInspector.Frame::sequence)
                        .toList());
        assertEquals(List.of(1, 1, 1, 2, 1, 1, 3, 4),
                inspection.frames().stream()
                        .map(frame -> Byte.toUnsignedInt(frame.type()))
                        .toList());
        assertEquals(2, intAtStart(inspection.frames().get(3).payload()));
        assertEquals(8, engine.durabilityMetrics().walRecords());
        assertEquals(DurabilityStatus.OPEN, engine.durabilityMetrics().status());
        assertTrue(engine.durabilityMetrics().walBytes() > 48);
        assertTrue(engine.durabilityMetrics().retainedBytes()
                > engine.durabilityMetrics().walBytes());

        CompletionException checkpoint = assertThrows(
                CompletionException.class, () -> engine.checkpoint().join());
        assertInstanceOf(UnsupportedOperationException.class, checkpoint.getCause());
        engine.close();
        assertEquals(DurabilityStatus.CLOSED, engine.durabilityMetrics().status());
    }

    @Test
    void codecRejectionConsumesNoSequenceAndWriterRemainsUsable(
            @TempDir Path directory
    ) {
        DocumentCodec delegate = new DocumentCodec();
        DurableCodec<Integer, Document> codec = new DurableCodec<>() {
            @Override
            public String codecId() {
                return "conditional-document-v1";
            }

            @Override
            public int codecVersion() {
                return 1;
            }

            @Override
            public byte[] encodeKey(Integer key) {
                return delegate.encodeKey(key);
            }

            @Override
            public Integer decodeKey(byte[] bytes) {
                return delegate.decodeKey(bytes);
            }

            @Override
            public byte[] encodeDocument(Document document) {
                return delegate.encodeDocument(document);
            }

            @Override
            public Document decodeDocument(byte[] bytes) {
                Document decoded = delegate.decodeDocument(bytes);
                return decoded.body().equals("bad")
                        ? new Document(decoded.id(), "not-canonical")
                        : decoded;
            }
        };

        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(directory, codec))) {
            CompletionException rejected = assertThrows(
                    CompletionException.class,
                    () -> engine.add(new Document(1, "bad")).join());
            DurabilityException failure = assertInstanceOf(
                    DurabilityException.class, rejected.getCause());
            assertEquals(DurabilityException.Reason.CODEC_FAILURE, failure.reason());
            assertEquals(0, engine.currentSequence());

            engine.add(new Document(2, "good")).join();
            assertEquals(1, engine.currentSequence());
            assertEquals("good", engine.get(2).body());
        }
    }

    @Test
    void directoryOwnershipRemainsExclusiveAcrossReopen(
            @TempDir Path directory
    ) {
        DurableStorageConfig<Integer, Document> storage = config(
                directory, new DocumentCodec());
        DurableSearchEngine<Integer, Document> first = builder().buildDurable(storage);
        DurabilityException locked = assertThrows(
                DurabilityException.class,
                () -> builder().buildDurable(storage));
        assertEquals(DurabilityException.Reason.STORAGE_IN_USE, locked.reason());
        first.close();

        try (DurableSearchEngine<Integer, Document> reopened =
                     builder().buildDurable(storage)) {
            assertEquals(0, reopened.currentSequence());
            assertEquals(RecoverySource.WAL_ONLY,
                    reopened.durabilityMetrics().recoverySource());
        }
    }

    @Test
    void metadataAndWalBytesAreDeterministicForEquivalentInput(
            @TempDir Path root
    ) throws IOException {
        Path left = root.resolve("left");
        Path right = root.resolve("right");
        try (DurableSearchEngine<Integer, Document> first = builder()
                .buildDurable(config(left, new DocumentCodec()));
             DurableSearchEngine<Integer, Document> second = builder()
                     .buildDurable(config(right, new DocumentCodec()))) {
            first.add(new Document(1, "same")).join();
            second.add(new Document(1, "same")).join();
        }
        V40WalInspector.Inspection leftWal = V40WalInspector.inspect(
                left.resolve("gse-wal-00000000000000000001.log"));
        V40WalInspector.Inspection rightWal = V40WalInspector.inspect(
                right.resolve("gse-wal-00000000000000000001.log"));
        assertArrayEquals(
                leftWal.frames().getFirst().payload(),
                rightWal.frames().getFirst().payload());
        assertEquals(
                leftWal.frames().getFirst().sequence(),
                rightWal.frames().getFirst().sequence());
    }

    @Test
    void capacityRejectionConsumesNoSequenceAndLaterSmallUnitCanCommit(
            @TempDir Path directory
    ) {
        DurableStorageConfig<Integer, Document> storage =
                DurableStorageConfig.builder(directory, new DocumentCodec())
                        .storageIdentity("capacity-store-v1")
                        .schemaIdentity("capacity-schema-v1")
                        .maxEncodedDocumentBytes(4_096)
                        .checkpointWalBytes(1)
                        .maxRetainedBytes(512)
                        .build();
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            CompletionException rejected = assertThrows(
                    CompletionException.class,
                    () -> engine.add(new Document(1, "x".repeat(1_000))).join());
            DurabilityException capacity = assertInstanceOf(
                    DurabilityException.class, rejected.getCause());
            assertEquals(
                    DurabilityException.Reason.CAPACITY_EXCEEDED,
                    capacity.reason());
            assertEquals(0, engine.currentSequence());
            assertEquals(
                    DurabilityStatus.CAPACITY_BLOCKED,
                    engine.durabilityMetrics().status());

            engine.add(new Document(2, "small")).join();
            assertEquals(1, engine.currentSequence());
            assertEquals(DurabilityStatus.OPEN, engine.durabilityMetrics().status());
        }
    }

    @Test
    void forceFailureIsTerminalAndDoesNotPublishCandidate(
            @TempDir Path directory
    ) throws Exception {
        DurableSearchEngine<Integer, Document> engine = builder().buildDurable(
                config(directory, new DocumentCodec()));
        System.setProperty("gse.v4.ioFailurePoint", "before-force");
        try {
            CompletionException rejected = assertThrows(
                    CompletionException.class,
                    () -> engine.add(new Document(1, "unpublished")).join());
            DurabilityException failure = assertInstanceOf(
                    DurabilityException.class, rejected.getCause());
            assertEquals(DurabilityException.Reason.IO_FAILURE, failure.reason());
            assertEquals(null, engine.get(1));
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(2);
            while (engine.durabilityMetrics().status() != DurabilityStatus.FAILED
                    && System.nanoTime() < deadline) {
                Thread.onSpinWait();
            }
            assertEquals(DurabilityStatus.FAILED, engine.durabilityMetrics().status());
        } finally {
            System.clearProperty("gse.v4.ioFailurePoint");
            engine.close();
        }
    }

    @Test
    void customStartupIndexIsRejectedBeforeStorageInitialization(
            @TempDir Path directory
    ) throws IOException {
        IndexDefinition<Document> custom = new IndexDefinition<>() {
            @Override
            public Field<Document, ?> field() {
                return BODY;
            }

            @Override
            public IndexSnapshot<Document> createEmpty() {
                return IndexDefinition.equality(BODY).createEmpty();
            }
        };
        DurabilityException rejected = assertThrows(
                DurabilityException.class,
                () -> SearchEngine.builder(Document.class, ID)
                        .index(custom)
                        .buildDurable(config(directory, new DocumentCodec())));
        assertEquals(
                DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                rejected.reason());
        assertTrue(fileNames(directory).isEmpty());
    }

    @Test
    void unsafeTargetsAndImpossibleInitialCapacityFailClosed(
            @TempDir Path root
    ) throws IOException {
        Path real = Files.createDirectory(root.resolve("real"));
        Path alias = Files.createSymbolicLink(root.resolve("alias"), real);
        DurabilityException symbolicDirectory = assertThrows(
                DurabilityException.class,
                () -> builder().buildDurable(config(alias, new DocumentCodec())));
        assertEquals(
                DurabilityException.Reason.UNSUPPORTED_FILESYSTEM,
                symbolicDirectory.reason());

        Path unsafeLockDirectory = Files.createDirectory(root.resolve("unsafe-lock"));
        Path externalLock = Files.createFile(root.resolve("external-lock"));
        Files.createSymbolicLink(
                unsafeLockDirectory.resolve("gse.lock"), externalLock);
        DurabilityException symbolicLock = assertThrows(
                DurabilityException.class,
                () -> builder().buildDurable(
                        config(unsafeLockDirectory, new DocumentCodec())));
        assertEquals(
                DurabilityException.Reason.UNSUPPORTED_FILESYSTEM,
                symbolicLock.reason());

        Path nonEmpty = Files.createDirectory(root.resolve("non-empty"));
        Files.writeString(nonEmpty.resolve("application-owned.txt"), "keep");
        DurabilityException unknownMember = assertThrows(
                DurabilityException.class,
                () -> builder().buildDurable(config(nonEmpty, new DocumentCodec())));
        assertEquals(
                DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                unknownMember.reason());

        DurableStorageConfig<Integer, Document> impossible =
                DurableStorageConfig.builder(
                                root.resolve("too-small"), new DocumentCodec())
                        .storageIdentity("too-small-store-v1")
                        .schemaIdentity("too-small-schema-v1")
                        .checkpointWalBytes(1)
                        .maxRetainedBytes(2)
                        .build();
        DurabilityException initialCapacity = assertThrows(
                DurabilityException.class,
                () -> builder().buildDurable(impossible));
        assertEquals(
                DurabilityException.Reason.CAPACITY_EXCEEDED,
                initialCapacity.reason());
    }

    private static io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder<
            Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID)
                .field(BODY)
                .config(new SnapshotEngineConfig(
                        1_000,
                        100,
                        java.time.Duration.ofMillis(5)));
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            DurableCodec<Integer, Document> codec
    ) {
        return DurableStorageConfig.builder(directory, codec)
                .storageIdentity("phase2-store-v1")
                .schemaIdentity("phase2-schema-v1")
                .build();
    }

    private static Set<String> fileNames(Path directory) throws IOException {
        try (var entries = Files.list(directory)) {
            return entries.map(path -> path.getFileName().toString())
                    .collect(java.util.stream.Collectors.toUnmodifiableSet());
        }
    }

    private static int intAtStart(byte[] bytes) {
        return java.nio.ByteBuffer.wrap(bytes).getInt();
    }

    private record Document(int id, String body) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "phase2-document-v1";
        }

        @Override
        public int codecVersion() {
            return 1;
        }

        @Override
        public byte[] encodeKey(Integer key) {
            return java.nio.ByteBuffer.allocate(Integer.BYTES).putInt(key).array();
        }

        @Override
        public Integer decodeKey(byte[] bytes) {
            if (bytes.length != Integer.BYTES) {
                throw new IllegalArgumentException("invalid integer key");
            }
            return java.nio.ByteBuffer.wrap(bytes).getInt();
        }

        @Override
        public byte[] encodeDocument(Document document) {
            byte[] body = document.body().getBytes(StandardCharsets.UTF_8);
            try {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (DataOutputStream output = new DataOutputStream(bytes)) {
                    output.writeInt(document.id());
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
                int length = input.readInt();
                if (length < 0 || length != input.available()) {
                    throw new IllegalArgumentException("invalid document length");
                }
                return new Document(id, new String(
                        input.readNBytes(length), StandardCharsets.UTF_8));
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid document", failure);
            }
        }
    }
}
