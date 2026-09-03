package io.github.patricklfdm.generalsearch.durability;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V41SafeCleanupPhase5Test {
    private static final long OPERATION_MAGIC = 0x4753454f50313030L;
    private static final int FRAME_MAGIC = 0x47534546;
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @Test
    void livePlanIsReadOnlyDeterministicAndIdempotentlyApplicable(
            @TempDir Path workspace
    ) throws Exception {
        Path store = createCheckpointStore(workspace.resolve("store"));
        Path authoritativeCheckpoint = onlyCheckpoint(store);
        Path obsolete = store.resolve(
                "gse-checkpoint-00000000000000000000-"
                        + "11111111111111111111111111111111.chk");
        Files.copy(authoritativeCheckpoint, obsolete);
        Path staging = Files.writeString(
                store.resolve("gse-metadata.staging"), "safe-remnant");

        DurableCleanupRequest request = new DurableCleanupRequest(
                store, DurableCleanupScope.LIVE_STORE);
        DurableCleanupPlan first = DurableStorageOperations.planCleanup(request);
        DurableCleanupPlan second = DurableStorageOperations.planCleanup(request);

        assertEquals(first, second);
        assertEquals(List.of(obsolete, staging), first.deleteSet().stream()
                .map(DurableCleanupEntry::member).toList());
        assertTrue(Files.exists(obsolete));
        assertTrue(Files.exists(staging));

        DurableCleanupResult result =
                DurableStorageOperations.applyCleanup(first);
        assertEquals(first.planDigest(), result.planDigest());
        assertEquals(List.of(obsolete, staging), result.deletedMembers());
        assertFalse(Files.exists(obsolete));
        assertFalse(Files.exists(staging));
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(store).status());

        DurableCleanupPlan empty = DurableStorageOperations.planCleanup(request);
        assertTrue(empty.deleteSet().isEmpty());
        assertTrue(DurableStorageOperations.applyCleanup(empty)
                .deletedMembers().isEmpty());
    }

    @Test
    void stalePlanAndOpenStoreRefuseBeforeDeletingAnything(
            @TempDir Path workspace
    ) throws Exception {
        Path store = createCheckpointStore(workspace.resolve("store"));
        Path remnant = Files.writeString(
                store.resolve("gse-metadata.staging"), "before");
        DurableCleanupRequest request = new DurableCleanupRequest(
                store, DurableCleanupScope.LIVE_STORE);
        DurableCleanupPlan plan = DurableStorageOperations.planCleanup(request);
        Files.writeString(remnant, "changed-after-plan");

        DurableOperationException stale = assertThrows(
                DurableOperationException.class,
                () -> DurableStorageOperations.applyCleanup(plan));
        assertEquals(DurableOperationException.Reason.SOURCE_INVALID,
                stale.reason());
        assertTrue(Files.exists(remnant));

        try (DurableSearchEngine<Integer, Document> ignored = SearchEngine
                .builder(Document.class, ID).field(BODY)
                .buildDurable(config(store))) {
            DurableOperationException inUse = assertThrows(
                    DurableOperationException.class,
                    () -> DurableStorageOperations.planCleanup(request));
            assertEquals(DurableOperationException.Reason.STORAGE_IN_USE,
                    inUse.reason());
        }
        assertTrue(Files.exists(remnant));
    }

    @Test
    void incompleteWalTailAndUnknownMembersAreNeverCleanupAuthority(
            @TempDir Path workspace
    ) throws Exception {
        Path store = createCheckpointStore(workspace.resolve("store"));
        Path wal;
        try (var members = Files.list(store)) {
            wal = members.filter(path -> path.getFileName().toString()
                            .endsWith(".log"))
                    .findFirst().orElseThrow();
        }
        byte[] incompleteHeader = ByteBuffer.allocate(8)
                .order(ByteOrder.BIG_ENDIAN)
                .putInt(FRAME_MAGIC).putShort((short) 1).putShort((short) 0)
                .array();
        Files.write(wal, incompleteHeader, StandardOpenOption.APPEND);
        long before = Files.size(wal);
        DurableCleanupRequest request = new DurableCleanupRequest(
                store, DurableCleanupScope.LIVE_STORE);

        DurableCleanupPlan tailPlan =
                DurableStorageOperations.planCleanup(request);
        assertTrue(tailPlan.deleteSet().isEmpty());
        DurableStorageOperations.applyCleanup(tailPlan);
        assertEquals(before, Files.size(wal));

        Path unknown = Files.writeString(store.resolve("operator-note"), "keep");
        DurableOperationException refusal = assertThrows(
                DurableOperationException.class,
                () -> DurableStorageOperations.planCleanup(request));
        assertEquals(DurableOperationException.Reason.SOURCE_INVALID,
                refusal.reason());
        assertTrue(Files.exists(unknown));
        assertEquals(before, Files.size(wal));
    }

    @Test
    void explicitlyBoundAbandonedStagingDeletesOnlyOwnedMembers(
            @TempDir Path workspace
    ) throws Exception {
        UUID operation = UUID.randomUUID();
        String compact = operation.toString().replace("-", "");
        Path staging = Files.createDirectory(workspace.resolve(
                ".gse-v41-backup-" + compact + ".staging"));
        Path member = Files.writeString(
                staging.resolve("gse-backup-metadata"), "partial");
        Path marker = staging.resolveSibling(
                staging.getFileName() + ".operation");
        Files.write(marker, marker(operation, (byte) 1,
                staging.getFileName().toString(), "final-backup"));

        DurableCleanupPlan plan = DurableStorageOperations.planCleanup(
                new DurableCleanupRequest(staging,
                        DurableCleanupScope.OPERATION_REMNANT));
        assertEquals(List.of(member, staging, marker), plan.deleteSet().stream()
                .map(DurableCleanupEntry::member).toList());
        DurableStorageOperations.applyCleanup(plan);
        assertFalse(Files.exists(member));
        assertFalse(Files.exists(staging));
        assertFalse(Files.exists(marker));
    }

    @Test
    void unknownStagingMemberAndHeldMarkerFailClosed(
            @TempDir Path workspace
    ) throws Exception {
        UUID operation = UUID.randomUUID();
        String compact = operation.toString().replace("-", "");
        Path staging = Files.createDirectory(workspace.resolve(
                ".gse-v41-restore-" + compact + ".staging"));
        Files.writeString(staging.resolve("operator-note"), "never-owned");
        Path marker = staging.resolveSibling(
                staging.getFileName() + ".operation");
        Files.write(marker, marker(operation, (byte) 2,
                staging.getFileName().toString(), "restored"));
        DurableCleanupRequest request = new DurableCleanupRequest(
                staging, DurableCleanupScope.OPERATION_REMNANT);

        DurableOperationException unknown = assertThrows(
                DurableOperationException.class,
                () -> DurableStorageOperations.planCleanup(request));
        assertEquals(DurableOperationException.Reason.SOURCE_INVALID,
                unknown.reason());
        assertTrue(Files.exists(staging.resolve("operator-note")));

        Files.delete(staging.resolve("operator-note"));
        try (FileChannel channel = FileChannel.open(marker,
                StandardOpenOption.READ, StandardOpenOption.WRITE);
                var ignored = channel.lock()) {
            DurableOperationException held = assertThrows(
                    DurableOperationException.class,
                    () -> DurableStorageOperations.planCleanup(request));
            assertEquals(DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                    held.reason());
        }
    }

    @Test
    void orphanMarkerMayBeRemovedWithoutMutatingCompleteBackup(
            @TempDir Path workspace
    ) throws Exception {
        Path source = workspace.resolve("source");
        Path backup = workspace.resolve("backup");
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID).field(BODY)
                .buildDurable(config(source))) {
            engine.add(new Document(1, "alpha")).join();
            engine.backup(new DurableBackupRequest(
                    backup, 64L * 1024 * 1024)).join();
        }
        UUID operation = UUID.randomUUID();
        String compact = operation.toString().replace("-", "");
        String stagingName = ".gse-v41-backup-" + compact + ".staging";
        Path marker = workspace.resolve(stagingName + ".operation");
        Files.write(marker, marker(operation, (byte) 1,
                stagingName, backup.getFileName().toString()));
        Set<String> before = names(backup);

        DurableCleanupPlan plan = DurableStorageOperations.planCleanup(
                new DurableCleanupRequest(marker,
                        DurableCleanupScope.OPERATION_REMNANT));
        assertEquals(List.of(marker), plan.deleteSet().stream()
                .map(DurableCleanupEntry::member).toList());
        DurableStorageOperations.applyCleanup(plan);

        assertFalse(Files.exists(marker));
        assertEquals(before, names(backup));
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyBackup(backup).status());
    }

    private static Path createCheckpointStore(Path store) throws IOException {
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID).field(BODY)
                .buildDurable(config(store))) {
            engine.add(new Document(1, "alpha")).join();
            engine.add(new Document(2, "beta")).join();
            engine.checkpoint().join();
        }
        return store;
    }

    private static DurableStorageConfig<Integer, Document> config(Path store) {
        return DurableStorageConfig.builder(store, new DocumentCodec())
                .storageIdentity("phase5-store")
                .schemaIdentity("phase5-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private static Path onlyCheckpoint(Path store) throws IOException {
        try (var members = Files.list(store)) {
            return members.filter(path -> path.getFileName().toString()
                            .endsWith(".chk"))
                    .findFirst().orElseThrow();
        }
    }

    private static Set<String> names(Path directory) throws IOException {
        try (var members = Files.list(directory)) {
            return members.map(path -> path.getFileName().toString())
                    .collect(java.util.stream.Collectors.toUnmodifiableSet());
        }
    }

    private static byte[] marker(
            UUID operation,
            byte kind,
            String staging,
            String target
    ) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        CRC32C checksum = new CRC32C();
        try (DataOutputStream output = new DataOutputStream(bytes)) {
            output.writeLong(OPERATION_MAGIC);
            output.writeShort(1);
            output.writeShort(0);
            output.writeByte(kind);
            output.writeLong(operation.getMostSignificantBits());
            output.writeLong(operation.getLeastSignificantBits());
            writeString(output, staging);
            writeString(output, target);
            output.flush();
            checksum.update(bytes.toByteArray());
            output.writeInt((int) checksum.getValue());
        }
        return bytes.toByteArray();
    }

    private static void writeString(DataOutputStream output, String value)
            throws IOException {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        output.writeInt(bytes.length);
        output.write(bytes);
    }

    private record Document(int id, String body) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "phase5-codec";
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
            return (document.id() + "\0" + document.body())
                    .getBytes(StandardCharsets.UTF_8);
        }

        @Override
        public Document decodeDocument(byte[] bytes) {
            String encoded = new String(bytes, StandardCharsets.UTF_8);
            int separator = encoded.indexOf('\0');
            return new Document(Integer.parseInt(
                    encoded.substring(0, separator)),
                    encoded.substring(separator + 1));
        }
    }
}
