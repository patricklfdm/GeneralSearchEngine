package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
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
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableDerivedStateStatus;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationPlan;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationException;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRecord;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRequest;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationTransformDescriptor;
import io.github.patricklfdm.generalsearch.durability.DurableReopenOutcome;
import io.github.patricklfdm.generalsearch.durability.DurableReopenReport;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V43StructuredImagesPhase3Test {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final Field<Document, Integer> PRICE =
            Field.of("price", Integer.class, Document::price);
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);

    @Test
    void structuredCheckpointPublishesAndWarmReopenReplaysWal(
            @TempDir Path store
    ) {
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2))) {
            engine.addAll(List.of(
                    new Document(1, "book", 10, "alpha"),
                    new Document(2, "music", 20, "alpine"),
                    new Document(3, "book", 30, "beta"))).join();
            engine.checkpoint().join();
            engine.update(new Document(3, "music", 25, "atlas")).join();
        }
        assertEquals(DurableDerivedStateStatus.VALID,
                DurableStorageOperations.inspectDerivedState(store).status());

        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2))) {
            DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.COMPLETE_WARM, report.outcome());
            assertEquals(3, report.loadedComponentCount());
            assertEquals(0, report.rebuiltComponentCount());
            assertEquals(2, report.recoveredSequence());
            assertEquals(List.of(1), ids(reopened.search(Query.eq(CATEGORY, "book"))));
            assertEquals(List.of(2, 3), ids(reopened.search(
                    Query.between(PRICE, 20, 30))));
            assertEquals(List.of(1, 2), ids(reopened.search(
                    Query.prefix(TITLE, "al"))));
        }
    }

    @Test
    void oneCorruptComponentFallsBackSelectivelyAndRefreshes(
            @TempDir Path store
    ) throws IOException {
        writeCheckpoint(store);
        Path component;
        try (var entries = Files.list(store)) {
            component = entries.filter(path -> DurableStructuredDerivedState
                            .COMPONENT_FILE.matcher(path.getFileName().toString()).matches())
                    .sorted(Comparator.comparing(path -> path.getFileName().toString()))
                    .findFirst().orElseThrow();
        }
        byte[] bytes = Files.readAllBytes(component);
        bytes[bytes.length / 2] ^= 1;
        Files.write(component, bytes);
        assertEquals(DurableDerivedStateStatus.PARTIAL,
                DurableStorageOperations.inspectDerivedState(store).status());

        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2))) {
            DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.PARTIAL_FALLBACK, report.outcome());
            assertEquals(2, report.loadedComponentCount());
            assertEquals(1, report.rebuiltComponentCount());
            assertTrue(report.refreshAttempted());
            assertTrue(report.refreshSucceeded());
            assertFalse(report.rejections().isEmpty());
            assertEquals(List.of(1, 3), ids(reopened.search(
                    Query.eq(CATEGORY, "book"))));
        }
        assertEquals(DurableDerivedStateStatus.VALID,
                DurableStorageOperations.inspectDerivedState(store).status());
    }

    @Test
    void directOlderToV12MigrationIsColdThenPublishesStructuredImages(
            @TempDir Path workspace
    ) throws IOException {
        for (DurableStorageFormat sourceFormat : List.of(
                DurableStorageFormat.V1_0, DurableStorageFormat.V1_1)) {
            Path source = workspace.resolve("source-" + sourceFormat.minor());
            Path target = workspace.resolve("target-" + sourceFormat.minor());
            try (DurableSearchEngine<Integer, Document> engine = builder()
                    .buildDurable(config(source, sourceFormat))) {
                engine.add(new Document(1, "book", 10, "alpha")).join();
                engine.checkpoint().join();
            }
            DurableMigrationRequest<Integer, Document, Integer, Document> request =
                    request(source, target);
            SearchEngineBuilder<Integer, Document> migrationBuilder = builder();
            DurableMigrationPlan plan = migrationBuilder.planDurableMigration(
                    builder(), request);
            assertEquals(sourceFormat, plan.sourceFormat());
            assertEquals(DurableStorageFormat.V1_2, plan.targetFormat());
            migrationBuilder.applyDurableMigration(builder(), request, plan);
            assertEquals(DurableDerivedStateStatus.ABSENT,
                    DurableStorageOperations.inspectDerivedState(target).status());
            try (DurableSearchEngine<Integer, Document> reopened = builder()
                    .buildDurable(config(target, DurableStorageFormat.V1_2))) {
                DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
                assertEquals(DurableReopenOutcome.FULL_FALLBACK, report.outcome());
                assertTrue(report.refreshSucceeded());
                assertEquals(new Document(1, "book", 10, "alpha"), reopened.get(1));
            }
            assertEquals(DurableDerivedStateStatus.VALID,
                    DurableStorageOperations.inspectDerivedState(target).status());
        }
    }

    @Test
    void catalogFailureUsesFullFallbackAndBestEffortRefresh(
            @TempDir Path store
    ) throws IOException {
        writeCheckpoint(store);
        Path catalog = store.resolve(DurableStructuredDerivedState.CATALOG_FILE);
        byte[] bytes = Files.readAllBytes(catalog);
        bytes[bytes.length / 2] ^= 1;
        Files.write(catalog, bytes);
        assertEquals(DurableDerivedStateStatus.CORRUPT,
                DurableStorageOperations.inspectDerivedState(store).status());
        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2))) {
            DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.FULL_FALLBACK, report.outcome());
            assertEquals(0, report.loadedComponentCount());
            assertEquals(3, report.rebuiltComponentCount());
            assertTrue(report.refreshAttempted());
            assertTrue(report.refreshSucceeded());
        }
        assertEquals(DurableDerivedStateStatus.VALID,
                DurableStorageOperations.inspectDerivedState(store).status());
    }

    @Test
    void derivedCapacityFailureCannotFailCanonicalCheckpoint(
            @TempDir Path store
    ) {
        DurableStorageConfig<Integer, Document> tiny = config(
                store, DurableStorageFormat.V1_2, "v43-phase3-store", 128L);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(tiny)) {
            engine.add(new Document(1, "book", 10, "alpha")).join();
            engine.checkpoint().join();
        }
        assertEquals(DurableDerivedStateStatus.ABSENT,
                DurableStorageOperations.inspectDerivedState(store).status());
        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(tiny)) {
            DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.FULL_FALLBACK, report.outcome());
            assertTrue(report.refreshAttempted());
            assertFalse(report.refreshSucceeded());
            assertEquals(new Document(1, "book", 10, "alpha"), reopened.get(1));
        }
    }

    @Test
    void backupCheckpointDoesNotPublishDerivedState(
            @TempDir Path workspace
    ) throws IOException {
        Path store = workspace.resolve("store");
        Path backup = workspace.resolve("backup");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2))) {
            engine.add(new Document(1, "book", 10, "alpha")).join();
            engine.backup(new DurableBackupRequest(
                    backup, 64L * 1024 * 1024)).join();
        }
        assertEquals(DurableDerivedStateStatus.ABSENT,
                DurableStorageOperations.inspectDerivedState(store).status());
        try (var entries = Files.list(backup)) {
            assertEquals(3, entries.filter(Files::isRegularFile).count());
        }
        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2))) {
            DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.FULL_FALLBACK, report.outcome());
            assertTrue(report.refreshSucceeded());
        }
    }

    @Test
    void replayedIndexLifecycleStartsFromWarmCheckpointState(
            @TempDir Path store
    ) {
        SearchEngineBuilder<Integer, Document> twoIndexes = SearchEngine
                .builder(Document.class, ID)
                .field(CATEGORY).field(PRICE).field(TITLE)
                .index(IndexDefinition.equality(CATEGORY))
                .index(IndexDefinition.range(PRICE));
        DurableStorageConfig<Integer, Document> storage = config(
                store, DurableStorageFormat.V1_2);
        try (DurableSearchEngine<Integer, Document> engine = twoIndexes
                .buildDurable(storage)) {
            engine.addAll(List.of(
                    new Document(1, "book", 10, "alpha"),
                    new Document(2, "music", 20, "alpine"))).join();
            engine.checkpoint().join();
            engine.createIndex(IndexDefinition.prefix(TITLE)).join();
            engine.dropIndex(CATEGORY.name()).join();
        }
        try (DurableSearchEngine<Integer, Document> reopened = twoIndexes
                .buildDurable(storage)) {
            DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.COMPLETE_WARM, report.outcome());
            assertEquals(2, report.loadedComponentCount());
            assertEquals(1, report.replayCreatedIndexCount());
            assertEquals(List.of(1, 2), ids(reopened.search(
                    Query.prefix(TITLE, "al"))));
        }
    }

    @Test
    void meaningfulV12MigrationPreservesSourceDerivedMembers(
            @TempDir Path workspace
    ) throws IOException {
        Path source = workspace.resolve("source");
        Path target = workspace.resolve("target");
        writeCheckpoint(source);
        Map<String, byte[]> before = directoryBytes(source);
        DurableMigrationRequest<Integer, Document, Integer, Document> request =
                request(source, target,
                        config(target, DurableStorageFormat.V1_2,
                                "v43-phase3-target", 16L * 1024 * 1024));
        DurableMigrationPlan plan = builder().planDurableMigration(builder(), request);
        builder().applyDurableMigration(builder(), request, plan);
        assertEquals(before.keySet(), directoryBytes(source).keySet());
        before.forEach((name, value) -> assertTrue(Arrays.equals(
                value, directoryBytes(source).get(name)), name));
        assertEquals(DurableDerivedStateStatus.ABSENT,
                DurableStorageOperations.inspectDerivedState(target).status());

        DurableMigrationRequest<Integer, Document, Integer, Document> noChange =
                request(source, workspace.resolve("unneeded"),
                        config(workspace.resolve("unneeded"),
                                DurableStorageFormat.V1_2,
                                "v43-phase3-store", 16L * 1024 * 1024));
        DurableMigrationException failure = assertThrows(
                DurableMigrationException.class,
                () -> builder().planDurableMigration(builder(), noChange));
        assertEquals(DurableMigrationException.Reason.MIGRATION_NOT_REQUIRED,
                failure.reason());
    }

    private static void writeCheckpoint(Path store) {
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2))) {
            engine.addAll(List.of(
                    new Document(1, "book", 10, "alpha"),
                    new Document(2, "music", 20, "alpine"),
                    new Document(3, "book", 30, "beta"))).join();
            engine.checkpoint().join();
        }
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID)
                .field(CATEGORY).field(PRICE).field(TITLE)
                .index(IndexDefinition.equality(CATEGORY))
                .index(IndexDefinition.range(PRICE))
                .index(IndexDefinition.prefix(TITLE));
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            DurableStorageFormat format
    ) {
        return config(directory, format, "v43-phase3-store",
                16L * 1024 * 1024);
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            DurableStorageFormat format,
            String storageIdentity,
            long maxDerivedBytes
    ) {
        DurableStorageConfig.Builder<Integer, Document> builder =
                DurableStorageConfig.builder(directory, new DocumentCodec())
                .format(format)
                .storageIdentity(storageIdentity)
                .schemaIdentity("v43-phase3-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024);
        if (format.equals(DurableStorageFormat.V1_2)) {
            builder.maxDerivedStateBytes(maxDerivedBytes);
        }
        return builder.build();
    }

    private static DurableMigrationRequest<Integer, Document, Integer, Document>
            request(Path source, Path target) {
        return request(source, target,
                config(target, DurableStorageFormat.V1_2));
    }

    private static DurableMigrationRequest<Integer, Document, Integer, Document>
            request(
                    Path source,
                    Path target,
                    DurableStorageConfig<Integer, Document> targetConfig
            ) {
        return new DurableMigrationRequest<>(source,
                new DurableVerificationConfig<>(
                        "v43-phase3-store", "v43-phase3-schema",
                        new DocumentCodec(), 1,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_DOCUMENTS),
                targetConfig,
                new DurableMigrationTransformDescriptor("identity-format-v1", 1),
                (key, document) -> new DurableMigrationRecord<>(key, document),
                64L * 1024 * 1024, 64L * 1024 * 1024,
                1024 * 1024, 1000, 1000, 64 * 1024);
    }

    private static Map<String, byte[]> directoryBytes(Path directory) {
        try {
            Map<String, byte[]> result = new java.util.TreeMap<>();
            try (var stream = Files.list(directory)) {
                for (Path path : stream.toList()) {
                    result.put(path.getFileName().toString(), Files.readAllBytes(path));
                }
            }
            return result;
        } catch (IOException failure) {
            throw new AssertionError(failure);
        }
    }

    private static List<Integer> ids(List<Document> documents) {
        return documents.stream().map(Document::id).toList();
    }

    private record Document(int id, String category, int price, String title) {
    }

    private static final class DocumentCodec implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v43-phase3-codec";
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
                    output.writeUTF(document.category());
                    output.writeInt(document.price());
                    output.writeUTF(document.title());
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
                Document document = new Document(input.readInt(), input.readUTF(),
                        input.readInt(), input.readUTF());
                if (input.available() != 0) {
                    throw new IllegalArgumentException("trailing document bytes");
                }
                return document;
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid document bytes", failure);
            }
        }
    }
}
