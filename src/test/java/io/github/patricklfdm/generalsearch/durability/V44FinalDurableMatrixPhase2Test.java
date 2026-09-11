package io.github.patricklfdm.generalsearch.durability;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V44FinalDurableMatrixPhase2Test {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @Test
    void everyPublishedFormatCompletesCheckpointWalReopenAndContinuation(
            @TempDir Path workspace
    ) {
        List<DurableStorageFormat> formats = List.of(
                DurableStorageFormat.V1_0,
                DurableStorageFormat.V1_1,
                DurableStorageFormat.V1_2);
        for (int index = 0; index < formats.size(); index++) {
            DurableStorageFormat format = formats.get(index);
            Path store = workspace.resolve("format-" + format.minor());
            DurableStorageConfig<Integer, Document> storage = config(store, format);
            try (DurableSearchEngine<Integer, Document> engine = builder()
                    .buildDurable(storage)) {
                engine.addAll(List.of(
                        new Document(1, "alpha"),
                        new Document(2, "beta"))).join();
                engine.checkpoint().join();
                engine.update(new Document(2, "alpha beta")).join();
                assertEquals(1, engine.search(Query.eq(BODY, "alpha")).size());
                assertEquals(1, engine.durabilityMetrics().checkpointSequence());
                assertEquals(2, engine.currentSequence());
            }

            DurableStoreFormatReport report =
                    DurableStorageOperations.inspectStoreFormat(store);
            assertEquals(DurableVerificationStatus.VALID,
                    report.structuralReport().status());
            assertEquals(Optional.of(format), report.declaredFormat());

            try (DurableSearchEngine<Integer, Document> reopened = builder()
                    .buildDurable(storage)) {
                assertEquals(new Document(1, "alpha"), reopened.get(1));
                assertEquals(new Document(2, "alpha beta"), reopened.get(2));
                reopened.add(new Document(3, "continued " + index)).join();
                reopened.checkpoint().join();
                assertEquals(3, reopened.currentSequence());
            }
            try (DurableSearchEngine<Integer, Document> second = builder()
                    .buildDurable(storage)) {
                assertEquals(new Document(3, "continued " + index), second.get(3));
                assertEquals(3, second.currentSequence());
            }
        }
    }

    @Test
    void renamedWalGenerationFailsClosedWithoutMutation(@TempDir Path workspace)
            throws Exception {
        Path store = workspace.resolve("swapped-generation");
        DurableStorageConfig<Integer, Document> storage = config(
                store, DurableStorageFormat.V1_2);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            engine.add(new Document(1, "alpha")).join();
            engine.checkpoint().join();
        }
        Path wal = only(store, "gse-wal-", ".log");
        byte[] before = Files.readAllBytes(wal);
        Path renamed = store.resolve("gse-wal-00000000000000000003.log");
        Files.move(wal, renamed);

        DurableVerificationReport report =
                DurableStorageOperations.verifyStore(store);
        assertEquals(DurableVerificationStatus.CORRUPT, report.status());
        assertTrue(report.findings().stream().anyMatch(finding ->
                finding.code().equals("WAL_GENERATION_IDENTITY")));
        assertThrows(DurabilityException.class,
                () -> builder().buildDurable(storage));
        try (var files = Files.list(store)) {
            assertEquals(List.of(renamed.getFileName().toString()), files
                        .filter(path -> path.getFileName().toString()
                                .startsWith("gse-wal-"))
                        .map(path -> path.getFileName().toString())
                        .toList());
        }
        assertArrayEquals(before, Files.readAllBytes(renamed));
    }

    @Test
    void canonicalHardLinkFailsClosedAndIsNeverRemoved(@TempDir Path workspace)
            throws Exception {
        assumeTrue(FileSystems.getDefault().supportedFileAttributeViews()
                .contains("unix"));
        Path store = workspace.resolve("hard-link");
        writeCheckpoint(store);
        Path checkpoint = only(store, "gse-checkpoint-", ".chk");
        Path alias = store.resolve("operator-checkpoint-alias");
        Files.createLink(alias, checkpoint);

        DurableVerificationReport report =
                DurableStorageOperations.verifyStore(store);

        assertEquals(DurableVerificationStatus.CORRUPT, report.status());
        assertTrue(report.findings().stream().anyMatch(finding ->
                finding.code().equals("ALIASED_MEMBER")));
        assertTrue(Files.exists(alias));
        assertTrue(Files.exists(checkpoint));
    }

    @Test
    void permissionDeniedFailsClosedAndFailedOpenReleasesOwnership(
            @TempDir Path workspace
    ) throws Exception {
        assumeTrue(FileSystems.getDefault().supportedFileAttributeViews()
                .contains("posix"));
        Path store = workspace.resolve("permission-denied");
        DurableStorageConfig<Integer, Document> storage = writeCheckpoint(store);
        Path checkpoint = only(store, "gse-checkpoint-", ".chk");
        Set<PosixFilePermission> original = Files.getPosixFilePermissions(checkpoint);
        try {
            Files.setPosixFilePermissions(checkpoint, Set.of());
            DurableOperationException failure = assertThrows(
                    DurableOperationException.class,
                    () -> DurableStorageOperations.verifyStore(store));
            assertEquals(DurableOperationException.Reason.IO_FAILURE,
                    failure.reason());
            assertThrows(DurabilityException.class,
                    () -> builder().buildDurable(storage));
        } finally {
            Files.setPosixFilePermissions(checkpoint, original);
        }

        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(storage)) {
            assertEquals(new Document(1, "alpha"), reopened.get(1));
            reopened.add(new Document(2, "continued")).join();
            assertEquals(2, reopened.currentSequence());
        }
    }

    private static DurableStorageConfig<Integer, Document> writeCheckpoint(Path store) {
        DurableStorageConfig<Integer, Document> storage = config(
                store, DurableStorageFormat.V1_2);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            engine.add(new Document(1, "alpha")).join();
            engine.checkpoint().join();
        }
        return storage;
    }

    private static Path only(Path directory, String prefix, String suffix)
            throws Exception {
        try (var files = Files.list(directory)) {
            List<Path> matches = files.filter(path -> path.getFileName().toString()
                            .startsWith(prefix)
                            && path.getFileName().toString().endsWith(suffix)
                            && !path.getFileName().toString().endsWith(".staging"))
                    .toList();
            assertEquals(1, matches.size());
            return matches.getFirst();
        }
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID)
                .field(BODY)
                .index(IndexDefinition.equality(BODY));
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            DurableStorageFormat format
    ) {
        DurableStorageConfig.Builder<Integer, Document> builder =
                DurableStorageConfig.builder(directory, new DocumentCodec())
                        .format(format)
                        .storageIdentity("v44-phase2-final-matrix")
                        .schemaIdentity("v44-phase2-schema")
                        .checkpointWalBytes(1024 * 1024)
                        .maxRetainedBytes(64L * 1024 * 1024);
        if (format.equals(DurableStorageFormat.V1_2)) {
            builder.maxDerivedStateBytes(16L * 1024 * 1024);
        }
        return builder.build();
    }

    private record Document(int id, String body) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v44-phase2-codec";
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
            byte[] body = document.body().getBytes(StandardCharsets.UTF_8);
            return ByteBuffer.allocate(Integer.BYTES * 2 + body.length)
                    .putInt(document.id()).putInt(body.length).put(body).array();
        }

        @Override
        public Document decodeDocument(byte[] bytes) {
            ByteBuffer input = ByteBuffer.wrap(bytes);
            int id = input.getInt();
            int length = input.getInt();
            if (length < 0 || length != input.remaining()) {
                throw new IllegalArgumentException("invalid document bytes");
            }
            byte[] body = new byte[length];
            input.get(body);
            return new Document(id, new String(body, StandardCharsets.UTF_8));
        }
    }
}
