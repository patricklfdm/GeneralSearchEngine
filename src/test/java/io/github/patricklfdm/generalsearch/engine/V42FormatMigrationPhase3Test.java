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
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Map;
import io.github.patricklfdm.generalsearch.durability.DurableBackupFormat;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableBackupResult;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationPlan;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationException;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRecord;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRequest;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationResult;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationTransformDescriptor;
import io.github.patricklfdm.generalsearch.durability.DurableRestoreResult;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V42FormatMigrationPhase3Test {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @Test
    void explicitV11SupportsMutationCheckpointBackupRestoreAndContinuation(
            @TempDir Path workspace) {
        Path source = workspace.resolve("v11-source");
        Path backup = workspace.resolve("v11-backup");
        Path restored = workspace.resolve("v11-restored");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source, DurableStorageFormat.V1_1))) {
            engine.add(new Document(1, "alpha")).join();
            engine.add(new Document(2, "removed")).join();
            engine.update(new Document(1, "alpha-updated")).join();
            engine.remove(2).join();
            engine.checkpoint().join();
            DurableBackupResult result = engine.backup(
                    new DurableBackupRequest(backup, 64L * 1024 * 1024)).join();
            assertEquals(DurableBackupFormat.V1_1, result.format());
            assertTrue(result.contentIdentity().startsWith("gse-backup-v2-"));
        }

        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(source).status());
        assertEquals(DurableStorageFormat.V1_1,
                DurableStorageOperations.inspectStoreFormat(source)
                        .declaredFormat().orElseThrow());
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyBackup(backup).status());

        DurableRestoreResult result = builder().restoreDurableBackup(
                backup, config(restored, DurableStorageFormat.V1_1));
        assertNotEquals(result.sourceHistory(), result.newHistory());
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(restored, DurableStorageFormat.V1_1))) {
            assertEquals(new Document(1, "alpha-updated"), engine.get(1));
            assertEquals(4, engine.currentSequence());
            engine.add(new Document(3, "continued")).join();
            engine.checkpoint().join();
        }
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(restored, DurableStorageFormat.V1_1))) {
            assertEquals(new Document(3, "continued"), engine.get(3));
            assertEquals(5, engine.currentSequence());
        }
    }

    @Test
    void formatOnlyPlanAndApplyPreserveSlotsSequenceAndSourceBytes(
            @TempDir Path workspace) throws IOException {
        Path source = workspace.resolve("source");
        Path target = workspace.resolve("target");
        DurableStorageConfig<Integer, Document> sourceStorage =
                config(source, DurableStorageFormat.V1_0);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(sourceStorage)) {
            engine.add(new Document(1, "alpha")).join();
            engine.add(new Document(2, "removed")).join();
            engine.add(new Document(3, "gamma")).join();
            engine.remove(2).join();
            engine.update(new Document(1, "alpha-updated")).join();
            engine.checkpoint().join();
        }
        Map<String, byte[]> before = digests(source);

        SearchEngineBuilder<Integer, Document> sourceBuilder = builder();
        SearchEngineBuilder<Integer, Document> targetBuilder = builder();
        DurableMigrationRequest<Integer, Document, Integer, Document> request =
                new DurableMigrationRequest<>(
                        source, verification(),
                        config(target, DurableStorageFormat.V1_1),
                        new DurableMigrationTransformDescriptor(
                                "identity-format-v1", 1),
                        (key, document) -> new DurableMigrationRecord<>(key, document),
                        64L * 1024 * 1024,
                        64L * 1024 * 1024,
                        1024 * 1024,
                        1000, 1000, 64 * 1024);

        DurableMigrationPlan plan = targetBuilder.planDurableMigration(
                sourceBuilder, request);
        assertFalse(Files.exists(target));
        assertEquals(DurableStorageFormat.V1_0, plan.sourceFormat());
        assertEquals(DurableStorageFormat.V1_1, plan.targetFormat());
        assertEquals(5, plan.sourceSequence());
        assertEquals(3, plan.nextDocId());
        assertEquals(2, plan.documentCount());
        assertTrue(plan.planDigest().startsWith("gse-migration-plan-v1-"));
        assertDigestMapEquals(before, digests(source));

        DurableMigrationResult result = targetBuilder.applyDurableMigration(
                sourceBuilder, request, plan);
        assertEquals(plan.planDigest(), result.planDigest());
        assertEquals(plan.targetHistory(), result.targetHistory());
        assertEquals(plan.targetAuthoritativeBytes(), result.authoritativeBytes());
        assertDigestMapEquals(before, digests(source));
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(target).status());

        try (DurableSearchEngine<Integer, Document> old = builder()
                     .buildDurable(sourceStorage);
             DurableSearchEngine<Integer, Document> migrated = builder()
                     .buildDurable(config(target, DurableStorageFormat.V1_1))) {
            assertEquals(new Document(1, "alpha-updated"), old.get(1));
            assertEquals(new Document(3, "gamma"), old.get(3));
            assertEquals(old.get(1), migrated.get(1));
            assertEquals(old.get(3), migrated.get(3));
            assertEquals(5, migrated.currentSequence());
            migrated.add(new Document(4, "continued")).join();
            assertEquals(6, migrated.currentSequence());
        }
    }

    @Test
    void formatOnlyMigrationFailsClosedForLockTransformStalenessAndCollision(
            @TempDir Path workspace) throws IOException {
        Path source = workspace.resolve("source");
        Path target = workspace.resolve("target");
        DurableStorageConfig<Integer, Document> sourceStorage =
                config(source, DurableStorageFormat.V1_0);
        DurableSearchEngine<Integer, Document> open = builder()
                .buildDurable(sourceStorage);
        try {
            open.add(new Document(1, "alpha")).join();
            open.checkpoint().join();
            DurableMigrationException locked = assertThrows(
                    DurableMigrationException.class,
                    () -> builder().planDurableMigration(builder(),
                            request(source, target,
                                    (key, document) ->
                                            new DurableMigrationRecord<>(
                                                    key, document))));
            assertEquals(DurableMigrationException.Reason.STORAGE_IN_USE,
                    locked.reason());
        } finally {
            open.close();
        }
        Map<String, byte[]> sourceBeforeFailures = digests(source);

        DurableMigrationException transform = assertThrows(
                DurableMigrationException.class,
                () -> builder().planDurableMigration(builder(),
                        request(source, target, (key, document) -> null)));
        assertEquals(DurableMigrationException.Reason.TRANSFORM_FAILURE,
                transform.reason());
        assertFalse(Files.exists(target));

        DurableMigrationRequest<Integer, Document, Integer, Document> request =
                request(source, target,
                        (key, document) -> new DurableMigrationRecord<>(key, document));
        DurableMigrationPlan plan = builder().planDurableMigration(builder(), request);
        DurableMigrationPlan stale = new DurableMigrationPlan(
                plan.schemaVersion(), plan.sourceDirectory(), plan.targetDirectory(),
                plan.sourceFormat(), plan.targetFormat(), plan.sourceHistory(),
                plan.targetHistory(), plan.sourceSequence(), plan.nextDocId(),
                plan.sourceMembers(), plan.sourceAuthorityIdentity(),
                plan.sourceDescriptorDigest(), plan.targetDescriptorDigest(),
                plan.transformDescriptor(), plan.documentCount(),
                plan.sourceIndexCount(), plan.targetIndexCount(), plan.indexChange(),
                plan.targetAuthoritativeBytes(), plan.peakTargetBytes(),
                plan.capacitySafetyReserveBytes(), plan.projectionDigest(),
                "gse-migration-plan-v1-" + "0".repeat(64));
        DurableMigrationException staleFailure = assertThrows(
                DurableMigrationException.class,
                () -> builder().applyDurableMigration(builder(), request, stale));
        assertEquals(DurableMigrationException.Reason.PLAN_STALE,
                staleFailure.reason());
        assertFalse(Files.exists(target));

        Files.createDirectory(target);
        DurableMigrationException collision = assertThrows(
                DurableMigrationException.class,
                () -> builder().applyDurableMigration(builder(), request, plan));
        assertEquals(DurableMigrationException.Reason.TARGET_EXISTS,
                collision.reason());
        assertDigestMapEquals(sourceBeforeFailures, digests(source));
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID).field(BODY)
                .index(IndexDefinition.equality(BODY));
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory, DurableStorageFormat format) {
        return DurableStorageConfig.builder(directory, new DocumentCodec())
                .format(format)
                .storageIdentity("v42-phase3-store")
                .schemaIdentity("v42-phase3-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private static DurableVerificationConfig<Integer, Document> verification() {
        return new DurableVerificationConfig<>(
                "v42-phase3-store", "v42-phase3-schema", new DocumentCodec(), 1,
                DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                DurableStorageConfig.DEFAULT_MAX_DOCUMENTS);
    }

    private static DurableMigrationRequest<Integer, Document, Integer, Document>
            request(
                    Path source,
                    Path target,
                    io.github.patricklfdm.generalsearch.durability
                            .DurableMigrationTransform<Integer, Document,
                            Integer, Document> transform
            ) {
        return new DurableMigrationRequest<>(
                source, verification(), config(target, DurableStorageFormat.V1_1),
                new DurableMigrationTransformDescriptor("identity-format-v1", 1),
                transform, 64L * 1024 * 1024, 64L * 1024 * 1024,
                1024 * 1024, 1000, 1000, 64 * 1024);
    }

    private static Map<String, byte[]> digests(Path directory) throws IOException {
        Map<String, byte[]> result = new HashMap<>();
        try (var stream = Files.list(directory)) {
            for (Path path : stream.sorted(Comparator.comparing(
                    value -> value.getFileName().toString())).toList()) {
                result.put(path.getFileName().toString(),
                        sha256().digest(Files.readAllBytes(path)));
            }
        }
        return result;
    }

    private static void assertDigestMapEquals(
            Map<String, byte[]> expected, Map<String, byte[]> actual) {
        assertEquals(expected.keySet(), actual.keySet());
        for (String name : expected.keySet()) {
            assertTrue(MessageDigest.isEqual(expected.get(name), actual.get(name)), name);
        }
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private record Document(int id, String body) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v42-phase3-codec";
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
                if (input.available() != 0) {
                    throw new IllegalArgumentException("trailing document bytes");
                }
                return result;
            } catch (IOException problem) {
                throw new IllegalArgumentException("invalid document bytes", problem);
            }
        }
    }
}
