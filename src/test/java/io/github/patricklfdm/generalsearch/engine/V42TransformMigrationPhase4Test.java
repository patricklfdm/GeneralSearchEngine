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
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationException;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationPlan;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRecord;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRequest;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationResult;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationTransform;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationTransformDescriptor;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V42TransformMigrationPhase4Test {
    private static final Field<LegacyDocument, Integer> LEGACY_ID =
            Field.of("id", Integer.class, LegacyDocument::id);
    private static final Field<LegacyDocument, String> LEGACY_TITLE =
            Field.of("title", String.class, LegacyDocument::title);
    private static final Field<LegacyDocument, Integer> LEGACY_SCORE =
            Field.of("score", Integer.class, LegacyDocument::score);
    private static final Field<CatalogDocument, String> CATALOG_ID =
            Field.of("sku", String.class, CatalogDocument::sku);
    private static final Field<CatalogDocument, String> CATALOG_TITLE =
            Field.of("title", String.class, CatalogDocument::title);
    private static final Field<CatalogDocument, String> CATALOG_CATEGORY =
            Field.of("category", String.class, CatalogDocument::category);
    private static final Field<CatalogDocument, String> BROKEN =
            Field.of("broken", String.class, document -> {
                throw new IllegalStateException("deliberate index extractor failure");
            });

    @Test
    void declaredCodecSchemaAndKeyTransformRebuildsTargetIndexes(
            @TempDir Path workspace) throws IOException {
        Path source = workspace.resolve("legacy-source");
        Path target = workspace.resolve("catalog-target");
        DurableStorageConfig<Integer, LegacyDocument> sourceConfig =
                legacyConfig(source, DurableStorageFormat.V1_0);
        prepareLegacySource(sourceConfig);
        Map<String, byte[]> sourceBefore = digests(source);

        DurableMigrationRequest<Integer, LegacyDocument, String, CatalogDocument>
                request = catalogRequest(source, target, catalogTransform());
        SearchEngineBuilder<String, CatalogDocument> targetBuilder = catalogBuilder();
        DurableMigrationPlan plan = targetBuilder.planDurableMigration(
                legacyBuilder(), request);

        assertEquals(DurableStorageFormat.V1_0, plan.sourceFormat());
        assertEquals(DurableStorageFormat.V1_1, plan.targetFormat());
        assertEquals(5, plan.sourceSequence());
        assertEquals(3, plan.nextDocId());
        assertEquals(2, plan.documentCount());
        assertNotEquals(plan.sourceDescriptorDigest(), plan.targetDescriptorDigest());
        assertEquals(List.of("3:category:"), plan.indexChange().added());
        assertEquals(List.of("2:score:"), plan.indexChange().removed());
        assertEquals(List.of("1:title:"), plan.indexChange().retained());
        assertFalse(Files.exists(target));
        assertDigestMapEquals(sourceBefore, digests(source));

        DurableMigrationResult result = targetBuilder.applyDurableMigration(
                legacyBuilder(), request, plan);
        assertEquals(plan.targetHistory(), result.targetHistory());
        assertEquals(plan.projectionDigest(), result.projectionDigest());
        assertEquals(plan.planDigest(), result.planDigest());
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(target).status());
        assertDigestMapEquals(sourceBefore, digests(source));

        try (DurableSearchEngine<String, CatalogDocument> migrated =
                     catalogBuilder().buildDurable(catalogConfig(target))) {
            assertEquals(new CatalogDocument(
                    "sku-0007", "ALPHA UPDATED", 107, "legacy"),
                    migrated.get("sku-0007"));
            assertEquals(new CatalogDocument(
                    "sku-0009", "GAMMA", 103, "legacy"),
                    migrated.get("sku-0009"));
            assertEquals(List.of("sku-0007"), migrated.search(
                    Query.eq(CATALOG_TITLE, "ALPHA UPDATED")).stream()
                    .map(CatalogDocument::sku).toList());
            assertEquals(List.of("sku-0007", "sku-0009"), migrated.search(
                    Query.prefix(CATALOG_CATEGORY, "leg")).stream()
                    .map(CatalogDocument::sku).toList());
            assertEquals(5, migrated.currentSequence());
            migrated.add(new CatalogDocument(
                    "sku-0010", "CONTINUED", 110, "native")).join();
            migrated.checkpoint().join();
            assertEquals(6, migrated.currentSequence());
        }
        try (DurableSearchEngine<String, CatalogDocument> reopened =
                     catalogBuilder().buildDurable(catalogConfig(target))) {
            assertEquals("CONTINUED", reopened.get("sku-0010").title());
            assertEquals(6, reopened.currentSequence());
        }
        assertDigestMapEquals(sourceBefore, digests(source));
    }

    @Test
    void sameFormatIndexMigrationWorksAndExactNoOpFailsClosed(
            @TempDir Path workspace) {
        Path source = workspace.resolve("source-v11");
        Path target = workspace.resolve("target-index-change");
        DurableStorageConfig<Integer, LegacyDocument> sourceConfig =
                legacyConfig(source, DurableStorageFormat.V1_1);
        try (DurableSearchEngine<Integer, LegacyDocument> engine = legacyBuilder()
                .buildDurable(sourceConfig)) {
            engine.add(new LegacyDocument(1, "one", 1)).join();
            engine.add(new LegacyDocument(2, "two", 2)).join();
            engine.checkpoint().join();
        }

        DurableMigrationRequest<Integer, LegacyDocument,
                Integer, LegacyDocument> request = identityRequest(
                        source, legacyConfig(target, DurableStorageFormat.V1_1));
        SearchEngineBuilder<Integer, LegacyDocument> targetBuilder =
                legacyTitleOnlyBuilder();
        DurableMigrationPlan plan = targetBuilder.planDurableMigration(
                legacyBuilder(), request);
        assertEquals(DurableStorageFormat.V1_1, plan.sourceFormat());
        assertEquals(List.of(), plan.indexChange().added());
        assertEquals(List.of("2:score:"), plan.indexChange().removed());
        assertEquals(List.of("1:title:"), plan.indexChange().retained());

        targetBuilder.applyDurableMigration(legacyBuilder(), request, plan);
        try (DurableSearchEngine<Integer, LegacyDocument> migrated =
                     legacyTitleOnlyBuilder().buildDurable(
                             legacyConfig(target, DurableStorageFormat.V1_1))) {
            assertEquals(List.of(2), migrated.search(
                    Query.eq(LEGACY_TITLE, "two")).stream()
                    .map(LegacyDocument::id).toList());
        }

        Path noOpTarget = workspace.resolve("no-op-target");
        DurableMigrationRequest<Integer, LegacyDocument,
                Integer, LegacyDocument> noOp = identityRequest(
                        source, legacyConfig(noOpTarget, DurableStorageFormat.V1_1));
        DurableMigrationException failure = assertThrows(
                DurableMigrationException.class,
                () -> legacyBuilder().planDurableMigration(
                        legacyBuilder(), noOp));
        assertEquals(DurableMigrationException.Reason.MIGRATION_NOT_REQUIRED,
                failure.reason());
        assertFalse(Files.exists(noOpTarget));
    }

    @Test
    void transformAndIndexFailuresLeaveNoTarget(@TempDir Path workspace) {
        Path source = workspace.resolve("source");
        prepareLegacySource(legacyConfig(source, DurableStorageFormat.V1_0));

        assertTransformFailure(source, workspace.resolve("collision"),
                (key, document) -> new DurableMigrationRecord<>(
                        "duplicate", new CatalogDocument(
                                "duplicate", document.title(), 1, "legacy")),
                catalogBuilder());
        assertTransformFailure(source, workspace.resolve("key-mismatch"),
                (key, document) -> new DurableMigrationRecord<>(
                        "sku-%04d".formatted(key), new CatalogDocument(
                                "different", document.title(), 1, "legacy")),
                catalogBuilder());
        assertTransformFailure(source, workspace.resolve("throwing"),
                (key, document) -> {
                    throw new IllegalStateException("application payload");
                }, catalogBuilder());
        assertTransformFailure(source, workspace.resolve("index-failure"),
                catalogTransform(), brokenCatalogBuilder());
    }

    @Test
    void applyRejectsNondeterminismAndChangedBounds(@TempDir Path workspace) {
        Path source = workspace.resolve("source");
        prepareLegacySource(legacyConfig(source, DurableStorageFormat.V1_0));

        Path nondeterministicTarget = workspace.resolve("nondeterministic");
        AtomicBoolean changed = new AtomicBoolean();
        DurableMigrationTransform<Integer, LegacyDocument,
                String, CatalogDocument> nondeterministic = (key, document) -> {
                    String prefix = changed.get() ? "alt-" : "sku-";
                    String targetKey = prefix + "%04d".formatted(key);
                    return new DurableMigrationRecord<>(targetKey,
                            new CatalogDocument(targetKey,
                                    document.title().toUpperCase(Locale.ROOT),
                                    document.score() + 100L, "legacy"));
                };
        DurableMigrationRequest<Integer, LegacyDocument,
                String, CatalogDocument> request = catalogRequest(
                        source, nondeterministicTarget, nondeterministic);
        DurableMigrationPlan plan = catalogBuilder().planDurableMigration(
                legacyBuilder(), request);
        changed.set(true);
        DurableMigrationException nondeterministicFailure = assertThrows(
                DurableMigrationException.class,
                () -> catalogBuilder().applyDurableMigration(
                        legacyBuilder(), request, plan));
        assertEquals(DurableMigrationException.Reason.TRANSFORM_NONDETERMINISTIC,
                nondeterministicFailure.reason());
        assertFalse(Files.exists(nondeterministicTarget));

        Path staleTarget = workspace.resolve("changed-bounds");
        DurableMigrationRequest<Integer, LegacyDocument,
                String, CatalogDocument> stable = catalogRequest(
                        source, staleTarget, catalogTransform());
        DurableMigrationPlan stablePlan = catalogBuilder().planDurableMigration(
                legacyBuilder(), stable);
        DurableMigrationRequest<Integer, LegacyDocument,
                String, CatalogDocument> changedRequest = new DurableMigrationRequest<>(
                        source, legacyVerification(), catalogConfig(staleTarget),
                        transformDescriptor(), catalogTransform(),
                        64L * 1024 * 1024, 64L * 1024 * 1024,
                        1024 * 1024, 1000, 999, 64 * 1024);
        DurableMigrationException staleFailure = assertThrows(
                DurableMigrationException.class,
                () -> catalogBuilder().applyDurableMigration(
                        legacyBuilder(), changedRequest, stablePlan));
        assertEquals(DurableMigrationException.Reason.PLAN_STALE,
                staleFailure.reason());
        assertFalse(Files.exists(staleTarget));

        DurableMigrationPlan tamperedProjection = withProjection(
                stablePlan, "gse-migration-projection-v1-" + "0".repeat(64));
        DurableMigrationException tamperedFailure = assertThrows(
                DurableMigrationException.class,
                () -> catalogBuilder().applyDurableMigration(
                        legacyBuilder(), stable, tamperedProjection));
        assertEquals(DurableMigrationException.Reason.PLAN_STALE,
                tamperedFailure.reason());
        assertFalse(Files.exists(staleTarget));

        Path changedDescriptorTarget = workspace.resolve("changed-descriptor");
        AtomicBoolean invoked = new AtomicBoolean();
        DurableMigrationRequest<Integer, LegacyDocument,
                String, CatalogDocument> descriptorPlanRequest = catalogRequest(
                        source, changedDescriptorTarget, catalogTransform());
        DurableMigrationPlan descriptorPlan = catalogBuilder().planDurableMigration(
                legacyBuilder(), descriptorPlanRequest);
        DurableMigrationRequest<Integer, LegacyDocument,
                String, CatalogDocument> changedDescriptor = new DurableMigrationRequest<>(
                        source, legacyVerification(), catalogConfig(
                                changedDescriptorTarget, "changed-catalog-store"),
                        transformDescriptor(), (key, document) -> {
                            invoked.set(true);
                            return catalogTransform().transform(key, document);
                        },
                        64L * 1024 * 1024, 64L * 1024 * 1024,
                        1024 * 1024, 1000, 1000, 64 * 1024);
        DurableMigrationException descriptorFailure = assertThrows(
                DurableMigrationException.class,
                () -> catalogBuilder().applyDurableMigration(
                        legacyBuilder(), changedDescriptor, descriptorPlan));
        assertEquals(DurableMigrationException.Reason.PLAN_STALE,
                descriptorFailure.reason());
        assertFalse(invoked.get());
        assertFalse(Files.exists(changedDescriptorTarget));
    }

    @Test
    void unsupportedEdgeAndSourceIdentityMismatchFailClosed(
            @TempDir Path workspace) {
        Path source = workspace.resolve("source");
        prepareLegacySource(legacyConfig(source, DurableStorageFormat.V1_0));

        Path v10Target = workspace.resolve("target-v10");
        DurableMigrationRequest<Integer, LegacyDocument,
                Integer, LegacyDocument> unsupported = identityRequest(
                        source, legacyConfig(v10Target, DurableStorageFormat.V1_0));
        DurableMigrationException edge = assertThrows(
                DurableMigrationException.class,
                () -> legacyBuilder().planDurableMigration(
                        legacyBuilder(), unsupported));
        assertEquals(DurableMigrationException.Reason.MIGRATION_PATH_UNSUPPORTED,
                edge.reason());
        assertFalse(Files.exists(v10Target));

        Path mismatchTarget = workspace.resolve("identity-mismatch");
        DurableVerificationConfig<Integer, LegacyDocument> wrong =
                new DurableVerificationConfig<>(
                        "legacy-store", "wrong-schema", new LegacyCodec(), 1,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_DOCUMENTS);
        DurableMigrationRequest<Integer, LegacyDocument,
                String, CatalogDocument> mismatch = new DurableMigrationRequest<>(
                        source, wrong, catalogConfig(mismatchTarget),
                        transformDescriptor(), catalogTransform(),
                        64L * 1024 * 1024, 64L * 1024 * 1024,
                        1024 * 1024, 1000, 1000, 64 * 1024);
        DurableMigrationException identity = assertThrows(
                DurableMigrationException.class,
                () -> catalogBuilder().planDurableMigration(
                        legacyBuilder(), mismatch));
        assertEquals(DurableMigrationException.Reason.IDENTITY_MISMATCH,
                identity.reason());
        assertFalse(Files.exists(mismatchTarget));
    }

    private static void assertTransformFailure(
            Path source,
            Path target,
            DurableMigrationTransform<Integer, LegacyDocument,
                    String, CatalogDocument> transform,
            SearchEngineBuilder<String, CatalogDocument> targetBuilder) {
        DurableMigrationException failure = assertThrows(
                DurableMigrationException.class,
                () -> targetBuilder.planDurableMigration(
                        legacyBuilder(), catalogRequest(source, target, transform)));
        assertEquals(DurableMigrationException.Reason.TRANSFORM_FAILURE,
                failure.reason());
        assertFalse(Files.exists(target));
        assertEquals("TRANSFORM_FAILURE", failure.getMessage());
    }

    private static DurableMigrationPlan withProjection(
            DurableMigrationPlan plan, String projection) {
        return new DurableMigrationPlan(
                plan.schemaVersion(), plan.sourceDirectory(), plan.targetDirectory(),
                plan.sourceFormat(), plan.targetFormat(), plan.sourceHistory(),
                plan.targetHistory(), plan.sourceSequence(), plan.nextDocId(),
                plan.sourceMembers(), plan.sourceAuthorityIdentity(),
                plan.sourceDescriptorDigest(), plan.targetDescriptorDigest(),
                plan.transformDescriptor(), plan.documentCount(),
                plan.sourceIndexCount(), plan.targetIndexCount(), plan.indexChange(),
                plan.targetAuthoritativeBytes(), plan.peakTargetBytes(),
                plan.capacitySafetyReserveBytes(), projection, plan.planDigest());
    }

    private static void prepareLegacySource(
            DurableStorageConfig<Integer, LegacyDocument> config) {
        try (DurableSearchEngine<Integer, LegacyDocument> engine = legacyBuilder()
                .buildDurable(config)) {
            engine.add(new LegacyDocument(7, "alpha", 1)).join();
            engine.add(new LegacyDocument(8, "removed", 2)).join();
            engine.add(new LegacyDocument(9, "gamma", 3)).join();
            engine.remove(8).join();
            engine.update(new LegacyDocument(7, "alpha updated", 7)).join();
            engine.checkpoint().join();
        }
    }

    private static SearchEngineBuilder<Integer, LegacyDocument> legacyBuilder() {
        return SearchEngine.builder(LegacyDocument.class, LEGACY_ID)
                .field(LEGACY_TITLE)
                .field(LEGACY_SCORE)
                .index(IndexDefinition.equality(LEGACY_TITLE))
                .index(IndexDefinition.range(LEGACY_SCORE));
    }

    private static SearchEngineBuilder<Integer, LegacyDocument>
            legacyTitleOnlyBuilder() {
        return SearchEngine.builder(LegacyDocument.class, LEGACY_ID)
                .field(LEGACY_TITLE)
                .field(LEGACY_SCORE)
                .index(IndexDefinition.equality(LEGACY_TITLE));
    }

    private static SearchEngineBuilder<String, CatalogDocument> catalogBuilder() {
        return SearchEngine.builder(CatalogDocument.class, CATALOG_ID)
                .field(CATALOG_TITLE)
                .field(CATALOG_CATEGORY)
                .index(IndexDefinition.equality(CATALOG_TITLE))
                .index(IndexDefinition.prefix(CATALOG_CATEGORY));
    }

    private static SearchEngineBuilder<String, CatalogDocument>
            brokenCatalogBuilder() {
        return SearchEngine.builder(CatalogDocument.class, CATALOG_ID)
                .field(CATALOG_TITLE)
                .field(CATALOG_CATEGORY)
                .field(BROKEN)
                .index(IndexDefinition.equality(BROKEN));
    }

    private static DurableStorageConfig<Integer, LegacyDocument> legacyConfig(
            Path directory, DurableStorageFormat format) {
        return DurableStorageConfig.builder(directory, new LegacyCodec())
                .format(format)
                .storageIdentity("legacy-store")
                .schemaIdentity("legacy-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private static DurableStorageConfig<String, CatalogDocument> catalogConfig(
            Path directory) {
        return catalogConfig(directory, "catalog-store");
    }

    private static DurableStorageConfig<String, CatalogDocument> catalogConfig(
            Path directory, String storageIdentity) {
        return DurableStorageConfig.builder(directory, new CatalogCodec())
                .format(DurableStorageFormat.V1_1)
                .storageIdentity(storageIdentity)
                .schemaIdentity("catalog-schema")
                .checkpointWalBytes(2L * 1024 * 1024)
                .maxRetainedBytes(96L * 1024 * 1024)
                .build();
    }

    private static DurableVerificationConfig<Integer, LegacyDocument>
            legacyVerification() {
        return new DurableVerificationConfig<>(
                "legacy-store", "legacy-schema", new LegacyCodec(), 1,
                DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                DurableStorageConfig.DEFAULT_MAX_DOCUMENTS);
    }

    private static DurableMigrationTransformDescriptor transformDescriptor() {
        return new DurableMigrationTransformDescriptor("catalog-schema-key-v1", 1);
    }

    private static DurableMigrationTransform<Integer, LegacyDocument,
            String, CatalogDocument> catalogTransform() {
        return (key, document) -> {
            String targetKey = "sku-%04d".formatted(key);
            return new DurableMigrationRecord<>(targetKey,
                    new CatalogDocument(targetKey,
                            document.title().toUpperCase(Locale.ROOT),
                            document.score() + 100L, "legacy"));
        };
    }

    private static DurableMigrationRequest<Integer, LegacyDocument,
            String, CatalogDocument> catalogRequest(
                    Path source,
                    Path target,
                    DurableMigrationTransform<Integer, LegacyDocument,
                            String, CatalogDocument> transform) {
        return new DurableMigrationRequest<>(
                source, legacyVerification(), catalogConfig(target),
                transformDescriptor(), transform,
                64L * 1024 * 1024, 64L * 1024 * 1024,
                1024 * 1024, 1000, 1000, 64 * 1024);
    }

    private static DurableMigrationRequest<Integer, LegacyDocument,
            Integer, LegacyDocument> identityRequest(
                    Path source,
                    DurableStorageConfig<Integer, LegacyDocument> target) {
        return new DurableMigrationRequest<>(
                source, legacyVerification(), target,
                new DurableMigrationTransformDescriptor("identity-format-v1", 1),
                (key, document) -> new DurableMigrationRecord<>(key, document),
                64L * 1024 * 1024, 64L * 1024 * 1024,
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

    private record LegacyDocument(int id, String title, int score) {
    }

    private record CatalogDocument(
            String sku,
            String title,
            long score,
            String category
    ) {
    }

    private static final class LegacyCodec
            implements DurableCodec<Integer, LegacyDocument> {
        @Override
        public String codecId() {
            return "legacy-codec";
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
                throw new IllegalArgumentException("invalid legacy key");
            }
            return ByteBuffer.wrap(bytes).getInt();
        }

        @Override
        public byte[] encodeDocument(LegacyDocument document) {
            try {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (DataOutputStream output = new DataOutputStream(bytes)) {
                    output.writeInt(document.id());
                    output.writeUTF(document.title());
                    output.writeInt(document.score());
                }
                return bytes.toByteArray();
            } catch (IOException impossible) {
                throw new AssertionError(impossible);
            }
        }

        @Override
        public LegacyDocument decodeDocument(byte[] bytes) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(bytes))) {
                LegacyDocument result = new LegacyDocument(
                        input.readInt(), input.readUTF(), input.readInt());
                if (input.available() != 0) {
                    throw new IllegalArgumentException("trailing legacy bytes");
                }
                return result;
            } catch (IOException problem) {
                throw new IllegalArgumentException("invalid legacy document", problem);
            }
        }
    }

    private static final class CatalogCodec
            implements DurableCodec<String, CatalogDocument> {
        @Override
        public String codecId() {
            return "catalog-codec";
        }

        @Override
        public int codecVersion() {
            return 2;
        }

        @Override
        public byte[] encodeKey(String key) {
            return write(output -> output.writeUTF(key));
        }

        @Override
        public String decodeKey(byte[] bytes) {
            return read(bytes, input -> input.readUTF());
        }

        @Override
        public byte[] encodeDocument(CatalogDocument document) {
            return write(output -> {
                output.writeUTF(document.sku());
                output.writeUTF(document.title());
                output.writeLong(document.score());
                output.writeUTF(document.category());
            });
        }

        @Override
        public CatalogDocument decodeDocument(byte[] bytes) {
            return read(bytes, input -> new CatalogDocument(
                    input.readUTF(), input.readUTF(), input.readLong(),
                    input.readUTF()));
        }

        private static byte[] write(Writer writer) {
            try {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (DataOutputStream output = new DataOutputStream(bytes)) {
                    writer.write(output);
                }
                return bytes.toByteArray();
            } catch (IOException impossible) {
                throw new AssertionError(impossible);
            }
        }

        private static <T> T read(byte[] bytes, Reader<T> reader) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(bytes))) {
                T result = reader.read(input);
                if (input.available() != 0) {
                    throw new IllegalArgumentException("trailing catalog bytes");
                }
                return result;
            } catch (IOException problem) {
                throw new IllegalArgumentException("invalid catalog bytes", problem);
            }
        }

        @FunctionalInterface
        private interface Writer {
            void write(DataOutputStream output) throws IOException;
        }

        @FunctionalInterface
        private interface Reader<T> {
            T read(DataInputStream input) throws IOException;
        }
    }
}
