package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
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
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableBackupResult;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableOperationException;
import io.github.patricklfdm.generalsearch.durability.DurableRestoreResult;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationReport;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V41SemanticRestorePhase4Test {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @AfterEach
    void clearFaults() {
        System.clearProperty(DurableIoFaults.FAILURE_PROPERTY);
        System.clearProperty(DurableIoFaults.MAX_WRITE_PROPERTY);
        System.clearProperty(DurableCrashHooks.BARRIER_PROPERTY);
        System.clearProperty(DurableCrashHooks.ACTION_PROPERTY);
    }

    @Test
    void semanticPassAndNewHistoryRestorePreserveLogicalState(
            @TempDir Path workspace) throws IOException {
        Path backup = createBackup(workspace, new DocumentCodec());
        SearchEngineBuilder<Integer, Document> builder = builder();
        DurableSemanticVerificationReport semantic = builder.verifyDurableBackup(
                backup, verification(new DocumentCodec()));
        assertEquals(DurableSemanticVerificationStatus.SEMANTICALLY_VALID,
                semantic.status());
        assertEquals(2, semantic.documentCount());
        assertTrue(semantic.findings().isEmpty());

        Path target = workspace.resolve("restored");
        DurableRestoreResult restored = builder.restoreDurableBackup(
                backup, config(target, new DocumentCodec()));
        assertNotEquals(restored.sourceHistory(), restored.newHistory());
        assertEquals(5, restored.restoredSequence());
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(target).status());
        assertEquals(Set.of("gse.lock", "gse-metadata",
                        "gse-checkpoint-manifest",
                        "gse-wal-00000000000000000002.log"),
                namesWithoutCheckpoint(target));

        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(target, new DocumentCodec()))) {
            assertEquals(new Document(1, "updated-alpha"), engine.get(1));
            assertEquals(new Document(3, "gamma"), engine.get(3));
            assertEquals(List.of(new Document(3, "gamma")),
                    engine.search(Query.eq(BODY, "gamma")));
            assertEquals(5, engine.currentSequence());
            engine.add(new Document(4, "continued")).join();
            assertEquals(6, engine.currentSequence());
            engine.checkpoint().join();
        }
        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(config(target, new DocumentCodec()))) {
            assertEquals(new Document(4, "continued"), reopened.get(4));
            assertEquals(6, reopened.currentSequence());
        }
    }

    @Test
    void identityAndDecodeFailuresAreReportsWithoutPayload(
            @TempDir Path workspace) {
        Path backup = createBackup(workspace, new DocumentCodec());
        DurableVerificationConfig<Integer, Document> wrongIdentity =
                new DurableVerificationConfig<>("other-store", "phase4-schema",
                        new DocumentCodec(), 1,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_DOCUMENTS);
        DurableSemanticVerificationReport mismatch = builder()
                .verifyDurableBackup(backup, wrongIdentity);
        assertEquals(DurableSemanticVerificationStatus.IDENTITY_MISMATCH,
                mismatch.status());
        assertEquals(0, mismatch.documentCount());

        DurableSemanticVerificationReport decode = builder()
                .verifyDurableBackup(backup, verification(new FailingCodec()));
        assertEquals(DurableSemanticVerificationStatus.DECODE_FAILURE,
                decode.status());
        assertTrue(decode.findings().stream().noneMatch(
                finding -> finding.detail().contains("updated-alpha")));
    }

    @Test
    void restoreRejectsExistingAndOverlappingTargetsBeforeDecode(
            @TempDir Path workspace) throws IOException {
        Path backup = createBackup(workspace, new DocumentCodec());
        Path existing = Files.createDirectory(workspace.resolve("existing"));
        DurableOperationException collision = assertThrows(
                DurableOperationException.class,
                () -> builder().restoreDurableBackup(backup,
                        config(existing, new FailingCodec())));
        assertEquals(DurableOperationException.Reason.TARGET_EXISTS,
                collision.reason());

        DurableOperationException overlap = assertThrows(
                DurableOperationException.class,
                () -> builder().restoreDurableBackup(backup,
                        config(backup.resolve("nested"), new DocumentCodec())));
        assertEquals(DurableOperationException.Reason.TARGET_INVALID,
                overlap.reason());
    }

    @Test
    void prepublicationIoFailureRollsBackOnlyOwnedRestoreRemnants(
            @TempDir Path workspace) throws IOException {
        Path backup = createBackup(workspace, new DocumentCodec());
        Path target = workspace.resolve("failed-target");
        System.setProperty(DurableIoFaults.FAILURE_PROPERTY,
                "v41-restore-before-manifest-force");
        DurableOperationException failure = assertThrows(
                DurableOperationException.class,
                () -> builder().restoreDurableBackup(backup,
                        config(target, new DocumentCodec())));
        assertEquals(DurableOperationException.Reason.IO_FAILURE,
                failure.reason());
        assertFalse(Files.exists(target));
        assertTrue(names(workspace).stream().noneMatch(
                name -> name.startsWith(".gse-v41-restore-")));
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyBackup(backup).status());
    }

    private static Path createBackup(Path workspace, DurableCodec<Integer, Document> codec) {
        Path source = workspace.resolve("source");
        Path backup = workspace.resolve("backup");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source, codec))) {
            engine.add(new Document(1, "alpha")).join();
            engine.add(new Document(2, "removed")).join();
            engine.update(new Document(1, "updated-alpha")).join();
            engine.remove(2).join();
            engine.add(new Document(3, "gamma")).join();
            DurableBackupResult result = engine.backup(
                    new DurableBackupRequest(backup, 64L * 1024 * 1024)).join();
            assertEquals(5, result.sequence());
        }
        return backup;
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID).field(BODY)
                .index(IndexDefinition.equality(BODY));
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory, DurableCodec<Integer, Document> codec) {
        return DurableStorageConfig.builder(directory, codec)
                .storageIdentity("phase4-store")
                .schemaIdentity("phase4-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private static DurableVerificationConfig<Integer, Document> verification(
            DurableCodec<Integer, Document> codec) {
        return new DurableVerificationConfig<>("phase4-store", "phase4-schema",
                codec, 1,
                DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                DurableStorageConfig.DEFAULT_MAX_DOCUMENTS);
    }

    private static Set<String> names(Path directory) throws IOException {
        try (var members = Files.list(directory)) {
            return members.map(path -> path.getFileName().toString())
                    .collect(java.util.stream.Collectors.toUnmodifiableSet());
        }
    }

    private static Set<String> namesWithoutCheckpoint(Path directory)
            throws IOException {
        return names(directory).stream()
                .filter(name -> !name.endsWith(".chk"))
                .collect(java.util.stream.Collectors.toUnmodifiableSet());
    }

    private record Document(int id, String body) {
    }

    private static class DocumentCodec implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "phase4-codec";
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

    private static final class FailingCodec extends DocumentCodec {
        @Override
        public Document decodeDocument(byte[] bytes) {
            throw new IllegalArgumentException("intentional decode failure");
        }
    }
}
