package io.github.patricklfdm.generalsearch.durability;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V42MigrationLifecyclePhase5Test {
    private static final long OPERATION_MAGIC = 0x4753454f50313030L;
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);

    @Test
    void migrationRemnantCleanupIsPlanBoundAndRefusesUnknownMember(
            @TempDir Path workspace
    ) throws Exception {
        Fixture fixture = fixture(workspace);
        UUID operation = UUID.randomUUID();
        Path staging = staging(workspace, operation);
        Files.createDirectory(staging);
        Path owned = Files.writeString(staging.resolve("gse-metadata"), "partial");
        Path marker = marker(staging);
        Files.write(marker, encodeMarker(operation, staging, fixture));

        DurableCleanupPlan plan = DurableStorageOperations.planCleanup(
                new DurableCleanupRequest(
                        staging, DurableCleanupScope.OPERATION_REMNANT));
        assertEquals(3, plan.deleteSet().size());
        Path unknown = Files.writeString(staging.resolve("operator-note"), "keep");

        DurableOperationException failure = assertThrows(
                DurableOperationException.class,
                () -> DurableStorageOperations.applyCleanup(plan));
        assertEquals(DurableOperationException.Reason.SOURCE_INVALID,
                failure.reason());
        assertTrue(Files.exists(owned));
        assertTrue(Files.exists(unknown));
        assertTrue(Files.exists(marker));
        assertFalse(Files.exists(fixture.target()));
    }

    @Test
    void changedSourceAuthorityRefusesRemnantCleanup(@TempDir Path workspace)
            throws Exception {
        Fixture fixture = fixture(workspace);
        UUID operation = UUID.randomUUID();
        Path staging = staging(workspace, operation);
        Files.createDirectory(staging);
        Path marker = marker(staging);
        Files.write(marker, encodeMarker(operation, staging, fixture));

        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(fixture.source(), DurableStorageFormat.V1_0))) {
            DurableOperationException inUse = assertThrows(
                    DurableOperationException.class,
                    () -> DurableStorageOperations.planCleanup(
                            new DurableCleanupRequest(staging,
                                    DurableCleanupScope.OPERATION_REMNANT)));
            assertEquals(DurableOperationException.Reason.STORAGE_IN_USE,
                    inUse.reason());
            engine.add(new Document(3, 33)).join();
        }

        DurableOperationException failure = assertThrows(
                DurableOperationException.class,
                () -> DurableStorageOperations.planCleanup(
                        new DurableCleanupRequest(staging,
                                DurableCleanupScope.OPERATION_REMNANT)));
        assertEquals(DurableOperationException.Reason.SOURCE_INVALID,
                failure.reason());
        assertTrue(Files.exists(staging));
        assertTrue(Files.exists(marker));
    }

    @Test
    void postPublicationCleanupDeletesOnlyMarkerAndPreservesBothAuthorities(
            @TempDir Path workspace
    ) throws Exception {
        Fixture fixture = fixture(workspace);
        builder().applyDurableMigration(builder(), fixture.request(), fixture.plan());
        UUID operation = UUID.randomUUID();
        Path staging = staging(workspace, operation);
        Path marker = marker(staging);
        Files.write(marker, encodeMarker(operation, staging, fixture));

        DurableCleanupPlan cleanup = DurableStorageOperations.planCleanup(
                new DurableCleanupRequest(
                        marker, DurableCleanupScope.OPERATION_REMNANT));
        assertEquals(1, cleanup.deleteSet().size());
        assertEquals(marker, cleanup.deleteSet().getFirst().member());
        DurableStorageOperations.applyCleanup(cleanup);

        assertFalse(Files.exists(marker));
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(fixture.source()).status());
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(fixture.target()).status());
    }

    private static Fixture fixture(Path workspace) {
        Path source = workspace.resolve("source").toAbsolutePath().normalize();
        Path target = workspace.resolve("target").toAbsolutePath().normalize();
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source, DurableStorageFormat.V1_0))) {
            engine.add(new Document(1, 11)).join();
            engine.add(new Document(2, 22)).join();
            engine.checkpoint().join();
        }
        DurableMigrationRequest<Integer, Document, Integer, Document> request =
                new DurableMigrationRequest<>(source,
                        new DurableVerificationConfig<>(
                                "v42-phase5-store", "v42-phase5-schema",
                                new DocumentCodec(), 1,
                                DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                                DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                                DurableStorageConfig.DEFAULT_MAX_DOCUMENTS),
                        config(target, DurableStorageFormat.V1_1),
                        new DurableMigrationTransformDescriptor(
                                "identity-format-v1", 1),
                        (key, document) ->
                                new DurableMigrationRecord<>(key, document),
                        64L * 1024 * 1024, 64L * 1024 * 1024,
                        1024 * 1024, 1000, 1000, 64 * 1024);
        DurableMigrationPlan plan = builder().planDurableMigration(
                builder(), request);
        return new Fixture(source, target, request, plan);
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID);
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            DurableStorageFormat format
    ) {
        return DurableStorageConfig.builder(directory, new DocumentCodec())
                .format(format)
                .storageIdentity("v42-phase5-store")
                .schemaIdentity("v42-phase5-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private static Path staging(Path workspace, UUID operation) {
        return workspace.resolve(".gse-v42-migration-"
                + operation.toString().replace("-", "") + ".staging");
    }

    private static Path marker(Path staging) {
        return staging.resolveSibling(staging.getFileName() + ".operation");
    }

    private static byte[] encodeMarker(
            UUID operation,
            Path staging,
            Fixture fixture
    ) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        CRC32C checksum = new CRC32C();
        try (DataOutputStream output = new DataOutputStream(bytes)) {
            output.writeLong(OPERATION_MAGIC);
            output.writeShort(1);
            output.writeShort(1);
            output.writeByte(3);
            output.writeLong(operation.getMostSignificantBits());
            output.writeLong(operation.getLeastSignificantBits());
            writeString(output, staging.getFileName().toString());
            writeString(output, fixture.target().getFileName().toString());
            writeString(output, fixture.source().toString());
            writeString(output, fixture.plan().planDigest());
            writeString(output, fixture.plan().sourceAuthorityIdentity());
            writeString(output, fixture.plan().projectionDigest());
            output.writeInt(fixture.plan().sourceMembers().size());
            for (DurableMigrationSourceMember member
                    : fixture.plan().sourceMembers()) {
                writeString(output, member.name());
                output.writeLong(member.size());
                writeString(output, member.sha256());
            }
            output.flush();
            checksum.update(bytes.toByteArray());
            output.writeInt((int) checksum.getValue());
        }
        return bytes.toByteArray();
    }

    private static void writeString(DataOutputStream output, String value)
            throws IOException {
        byte[] encoded = value.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        output.writeInt(encoded.length);
        output.write(encoded);
    }

    private record Fixture(
            Path source,
            Path target,
            DurableMigrationRequest<Integer, Document, Integer, Document> request,
            DurableMigrationPlan plan
    ) {
    }

    private record Document(int id, int value) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v42-phase5-codec";
        }

        @Override
        public int codecVersion() {
            return 1;
        }

        @Override
        public byte[] encodeKey(Integer key) {
            return ByteBuffer.allocate(4).putInt(key).array();
        }

        @Override
        public Integer decodeKey(byte[] encoded) {
            return ByteBuffer.wrap(encoded).getInt();
        }

        @Override
        public byte[] encodeDocument(Document document) {
            return ByteBuffer.allocate(8)
                    .putInt(document.id()).putInt(document.value()).array();
        }

        @Override
        public Document decodeDocument(byte[] encoded) {
            try (DataInputStream input = new DataInputStream(
                    new java.io.ByteArrayInputStream(encoded))) {
                return new Document(input.readInt(), input.readInt());
            } catch (IOException impossible) {
                throw new AssertionError(impossible);
            }
        }
    }
}
