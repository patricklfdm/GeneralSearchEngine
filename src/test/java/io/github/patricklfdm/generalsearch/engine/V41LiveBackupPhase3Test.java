package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.durability.DurableBackupFormat;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableBackupResult;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableOperationException;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationReport;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V41LiveBackupPhase3Test {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @AfterEach
    void clearControls() {
        System.clearProperty(DurableIoFaults.FAILURE_PROPERTY);
        System.clearProperty(DurableIoFaults.MAX_WRITE_PROPERTY);
        System.clearProperty(DurableCrashHooks.BARRIER_PROPERTY);
        System.clearProperty(DurableCrashHooks.ACTION_PROPERTY);
    }

    @Test
    void backupFreezesOneExactWriterOrderedSequenceAndExcludesLaterMutations(
            @TempDir Path workspace
    ) throws Exception {
        Path source = workspace.resolve("source");
        Path target = workspace.resolve("backup");
        DurableStorageConfig<Integer, Document> storage = config(source);
        DurableBackupResult result;
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            engine.add(new Document(1, "before-cut")).join();
            CompletableFuture<DurableBackupResult> backup = engine.backup(
                    new DurableBackupRequest(target, 64L * 1024 * 1024));
            engine.add(new Document(2, "after-cut-never-in-backup")).join();
            result = backup.get(10, TimeUnit.SECONDS);
            assertEquals(1, result.sequence());
            assertEquals(2, engine.currentSequence());
        }

        DurableVerificationReport report =
                DurableStorageOperations.verifyBackup(target);
        assertEquals(DurableVerificationStatus.VALID, report.status());
        assertEquals(1, report.sequence().orElseThrow());
        assertEquals(result.totalBytes(), report.authoritativeBytes());
        assertEquals(DurableBackupFormat.V1_0, result.format());
        assertEquals(3, result.memberCount());
        assertEquals(Set.of("gse-backup-checkpoint", "gse-backup-manifest",
                        "gse-backup-metadata"), names(target));
        byte[] checkpoint = Files.readAllBytes(
                target.resolve("gse-backup-checkpoint"));
        assertFalse(contains(checkpoint,
                "after-cut-never-in-backup".getBytes(StandardCharsets.UTF_8)));

        Path repeated = workspace.resolve("backup-repeat");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            DurableBackupResult later = engine.backup(new DurableBackupRequest(
                    repeated, 64L * 1024 * 1024)).join();
            assertEquals(2, later.sequence());
            assertNotEquals(result.contentIdentity(), later.contentIdentity());
        }
    }

    @Test
    void freshSequenceZeroStoreProducesACompleteBundle(@TempDir Path workspace) {
        Path source = workspace.resolve("source");
        Path target = workspace.resolve("empty-backup");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source))) {
            DurableBackupResult result = engine.backup(new DurableBackupRequest(
                    target, 64L * 1024 * 1024)).join();
            assertEquals(0, result.sequence());
        }
        DurableVerificationReport report =
                DurableStorageOperations.verifyBackup(target);
        assertEquals(DurableVerificationStatus.VALID, report.status());
        assertEquals(0, report.sequence().orElseThrow());
    }

    @Test
    void targetValidationPrecedesLifecycleAndNeverOverwrites(
            @TempDir Path workspace
    ) throws IOException {
        Path source = workspace.resolve("source");
        Path existing = Files.createDirectory(workspace.resolve("existing"));
        DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source));
        try {
            assertReason(engine.backup(new DurableBackupRequest(
                    existing, 1024)), DurableOperationException.Reason.TARGET_EXISTS);
            assertReason(engine.backup(new DurableBackupRequest(
                    source.resolve("nested"), 1024)),
                    DurableOperationException.Reason.TARGET_INVALID);
            engine.close();
            assertReason(engine.backup(new DurableBackupRequest(
                    workspace.resolve("after-close"), 1024)),
                    DurableOperationException.Reason.CLOSED);
        } finally {
            engine.close();
        }
    }

    @Test
    void targetIoFailureDoesNotInvalidateTheSourceAndRollsBackOwnedStaging(
            @TempDir Path workspace
    ) throws IOException {
        Path source = workspace.resolve("source");
        Path target = workspace.resolve("failed-backup");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source))) {
            engine.add(new Document(1, "survives")).join();
            System.setProperty(DurableIoFaults.FAILURE_PROPERTY,
                    "v41-backup-before-payload-force");
            assertReason(engine.backup(new DurableBackupRequest(
                    target, 64L * 1024 * 1024)),
                    DurableOperationException.Reason.IO_FAILURE);
            System.clearProperty(DurableIoFaults.FAILURE_PROPERTY);
            engine.add(new Document(2, "still-writable")).join();
            assertEquals(2, engine.currentSequence());
            assertFalse(Files.exists(target));
            assertTrue(names(workspace).stream()
                    .noneMatch(name -> name.startsWith(".gse-v41-backup-")));
        }
    }

    @Test
    void explicitBundleBoundFailsWithoutPublishingAndSourceRemainsWritable(
            @TempDir Path workspace
    ) {
        Path source = workspace.resolve("source");
        Path target = workspace.resolve("too-small");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source))) {
            engine.add(new Document(1, "capacity")).join();
            assertReason(engine.backup(new DurableBackupRequest(target, 1)),
                    DurableOperationException.Reason.CAPACITY_EXCEEDED);
            engine.add(new Document(2, "after-capacity-failure")).join();
            assertEquals(2, engine.currentSequence());
            assertFalse(Files.exists(target));
        }
    }

    @Test
    void oneBackupAtATimeAndCloseWaitsForTheAcceptedCopy(
            @TempDir Path workspace
    ) throws Exception {
        Path source = workspace.resolve("source");
        DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source));
        try {
            engine.add(new Document(1, "blocked-copy")).join();
            System.setProperty(DurableCrashHooks.BARRIER_PROPERTY,
                    "v41-backup-during-checkpoint-copy-v1");
            System.setProperty(DurableCrashHooks.ACTION_PROPERTY, "wait");
            CompletableFuture<DurableBackupResult> first = engine.backup(
                    new DurableBackupRequest(workspace.resolve("first"),
                            64L * 1024 * 1024));
            awaitSiblingMarker(workspace);
            assertReason(engine.backup(new DurableBackupRequest(
                    workspace.resolve("second"), 64L * 1024 * 1024)),
                    DurableOperationException.Reason.OPERATION_IN_PROGRESS);

            CompletableFuture<Void> close = CompletableFuture.runAsync(engine::close);
            Thread.sleep(100);
            assertFalse(close.isDone());
            System.clearProperty(DurableCrashHooks.BARRIER_PROPERTY);
            first.get(10, TimeUnit.SECONDS);
            close.get(10, TimeUnit.SECONDS);
            assertEquals(DurableVerificationStatus.VALID,
                    DurableStorageOperations.verifyBackup(
                            workspace.resolve("first")).status());
        } finally {
            System.clearProperty(DurableCrashHooks.BARRIER_PROPERTY);
            engine.close();
        }
    }

    @Test
    void pinnedCutSurvivesALaterCheckpointAndShortWrites(
            @TempDir Path workspace
    ) throws Exception {
        Path source = workspace.resolve("source");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source))) {
            engine.add(new Document(1, "pinned-at-one")).join();
            System.setProperty(DurableIoFaults.MAX_WRITE_PROPERTY, "1");
            System.setProperty(DurableCrashHooks.BARRIER_PROPERTY,
                    "v41-backup-during-checkpoint-copy-v1");
            System.setProperty(DurableCrashHooks.ACTION_PROPERTY, "wait");
            CompletableFuture<DurableBackupResult> backup = engine.backup(
                    new DurableBackupRequest(workspace.resolve("pinned"),
                            64L * 1024 * 1024));
            awaitSiblingMarker(workspace);

            engine.add(new Document(2, "later-checkpoint")).join();
            engine.checkpoint().get(10, TimeUnit.SECONDS);
            assertEquals(2, engine.durabilityMetrics().checkpointSequence());
            System.clearProperty(DurableCrashHooks.BARRIER_PROPERTY);
            DurableBackupResult result = backup.get(10, TimeUnit.SECONDS);
            assertEquals(1, result.sequence());
            assertEquals(DurableVerificationStatus.VALID,
                    DurableStorageOperations.verifyBackup(
                            workspace.resolve("pinned")).status());
        }
    }

    @Test
    void targetCollisionDuringCopyIsNeverOverwritten(
            @TempDir Path workspace
    ) throws Exception {
        Path source = workspace.resolve("source");
        Path target = workspace.resolve("collision");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source))) {
            engine.add(new Document(1, "collision-source")).join();
            System.setProperty(DurableCrashHooks.BARRIER_PROPERTY,
                    "v41-backup-during-checkpoint-copy-v1");
            System.setProperty(DurableCrashHooks.ACTION_PROPERTY, "wait");
            CompletableFuture<DurableBackupResult> backup = engine.backup(
                    new DurableBackupRequest(target, 64L * 1024 * 1024));
            awaitSiblingMarker(workspace);
            Files.createDirectory(target);
            System.clearProperty(DurableCrashHooks.BARRIER_PROPERTY);
            assertReason(backup, DurableOperationException.Reason.TARGET_EXISTS);
            assertTrue(Files.isDirectory(target));
            assertTrue(names(target).isEmpty());
            assertTrue(names(workspace).stream()
                    .noneMatch(name -> name.startsWith(".gse-v41-backup-")));
            engine.add(new Document(2, "source-still-open")).join();
        }
    }

    @Test
    void backupNeverTreatsAnUnrelatedActiveCheckpointAsItsCut(
            @TempDir Path workspace
    ) throws Exception {
        Path source = workspace.resolve("source");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source))) {
            engine.add(new Document(1, "checkpoint-in-flight")).join();
            System.setProperty(DurableCrashHooks.BARRIER_PROPERTY,
                    "v4-checkpoint-partial-data-v1");
            System.setProperty(DurableCrashHooks.ACTION_PROPERTY, "wait");
            CompletableFuture<Void> checkpoint = engine.checkpoint();
            awaitMember(source, ".chk.staging");
            assertReason(engine.backup(new DurableBackupRequest(
                    workspace.resolve("not-coalesced"), 64L * 1024 * 1024)),
                    DurableOperationException.Reason.OPERATION_IN_PROGRESS);
            System.clearProperty(DurableCrashHooks.BARRIER_PROPERTY);
            checkpoint.get(10, TimeUnit.SECONDS);
            assertFalse(Files.exists(workspace.resolve("not-coalesced")));
        }
    }

    @Test
    void terminalSequenceUsesTheInheritedSequenceExhaustionFailure() {
        DurabilityException failure = assertThrows(DurabilityException.class,
                () -> DurableCommitCoordinator.backupWalFirstSequence(
                        Long.MAX_VALUE));
        assertEquals(DurabilityException.Reason.SEQUENCE_EXHAUSTED,
                failure.reason());
        assertEquals(Long.MAX_VALUE, failure.sequence().orElseThrow());
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID).field(BODY);
    }

    private static DurableStorageConfig<Integer, Document> config(Path directory) {
        return DurableStorageConfig.builder(directory, new DocumentCodec())
                .storageIdentity("v41-phase3-store")
                .schemaIdentity("v41-phase3-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private static void assertReason(
            CompletableFuture<?> operation,
            DurableOperationException.Reason reason
    ) {
        CompletionException wrapper = assertThrows(
                CompletionException.class, operation::join);
        DurableOperationException failure = assertInstanceOf(
                DurableOperationException.class, wrapper.getCause());
        assertEquals(reason, failure.reason());
    }

    private static void awaitSiblingMarker(Path workspace) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
        while (System.nanoTime() < deadline) {
            if (names(workspace).stream().anyMatch(
                    name -> name.endsWith(".staging.operation"))) {
                return;
            }
            Thread.onSpinWait();
        }
        throw new AssertionError("backup marker was not published");
    }

    private static void awaitMember(Path directory, String suffix) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
        while (System.nanoTime() < deadline) {
            if (names(directory).stream().anyMatch(name -> name.endsWith(suffix))) {
                return;
            }
            Thread.onSpinWait();
        }
        throw new AssertionError("expected member was not published: " + suffix);
    }

    private static Set<String> names(Path directory) throws IOException {
        try (var entries = Files.list(directory)) {
            return entries.map(path -> path.getFileName().toString())
                    .collect(java.util.stream.Collectors.toUnmodifiableSet());
        }
    }

    private static boolean contains(byte[] source, byte[] needle) {
        outer: for (int offset = 0; offset <= source.length - needle.length; offset++) {
            for (int index = 0; index < needle.length; index++) {
                if (source[offset + index] != needle[index]) {
                    continue outer;
                }
            }
            return true;
        }
        return false;
    }

    private record Document(int id, String body) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v41-phase3-codec";
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
                Document result = new Document(input.readInt(), input.readUTF());
                assertArrayEquals(new byte[0], input.readAllBytes());
                return result;
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid document bytes", failure);
            }
        }
    }
}
