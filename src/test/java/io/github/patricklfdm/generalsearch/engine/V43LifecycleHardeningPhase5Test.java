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
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupPlan;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupScope;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableDerivedStateStatus;
import io.github.patricklfdm.generalsearch.durability.DurableOperationException;
import io.github.patricklfdm.generalsearch.durability.DurableReopenOutcome;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V43LifecycleHardeningPhase5Test {
    private static final Pattern COMPONENT = Pattern.compile(
            "gse-derived-index-[0-9]{20}-[0-9]{5}-[a-f0-9]{32}\\.idx");
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final Field<Document, Integer> PRICE =
            Field.of("price", Integer.class, Document::price);
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void cleanupBindsCatalogAndDeletesOnlySupersededDerivedGenerations(
            @TempDir Path store
    ) throws Exception {
        writeTwoGenerations(store);
        Set<Path> allComponents = componentPaths(store);
        assertEquals(8, allComponents.size());
        Files.writeString(store.resolve("gse-derived-manifest.staging"),
                "abandoned catalog staging");
        Path componentStaging = Files.writeString(store.resolve(
                "gse-derived-index-00000000000000000000-00000-"
                        + "11111111111111111111111111111111.idx.staging"),
                "abandoned component staging");

        DurableCleanupRequest request = new DurableCleanupRequest(
                store, DurableCleanupScope.LIVE_STORE);
        DurableCleanupPlan first = DurableStorageOperations.planCleanup(request);
        DurableCleanupPlan second = DurableStorageOperations.planCleanup(request);
        assertEquals(first, second);
        assertEquals(6, first.deleteSet().size());
        assertEquals(4, first.deleteSet().stream().filter(entry -> entry.reason()
                .equals("superseded-derived-component")).count());
        assertEquals(2, first.deleteSet().stream().filter(entry -> entry.reason()
                .equals("derived-staging-remnant")).count());
        assertTrue(first.deleteSet().stream().anyMatch(entry ->
                entry.member().equals(componentStaging)));

        Set<Path> protectedComponents = allComponents.stream()
                .filter(path -> first.deleteSet().stream().noneMatch(entry ->
                        entry.member().equals(path))).collect(Collectors.toSet());
        assertEquals(4, protectedComponents.size());
        DurableStorageOperations.applyCleanup(first);
        assertEquals(protectedComponents, componentPaths(store));
        DurableCleanupPlan converged = DurableStorageOperations.planCleanup(request);
        assertTrue(converged.deleteSet().isEmpty());
        assertTrue(DurableStorageOperations.applyCleanup(converged)
                .deletedMembers().isEmpty());
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(store).status());
        var derived = DurableStorageOperations.inspectDerivedState(store);
        assertEquals(DurableDerivedStateStatus.VALID, derived.status());
        assertEquals(0, derived.stagingBytes());
        assertEquals(0, derived.unreferencedBytes());

        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(config(store))) {
            assertEquals(DurableReopenOutcome.COMPLETE_WARM,
                    reopened.lastReopenReport().orElseThrow().outcome());
            assertEquals(List.of(1, 2, 3), ids(reopened.search(
                    Query.term(TEXT, "search"))));
        }
    }

    @Test
    void rejectedCatalogNeverAuthorizesAmbiguousFinalComponents(
            @TempDir Path store
    ) throws Exception {
        writeTwoGenerations(store);
        Set<Path> components = componentPaths(store);
        Path catalog = store.resolve("gse-derived-manifest");
        byte[] bytes = Files.readAllBytes(catalog);
        bytes[bytes.length / 2] ^= 1;
        Files.write(catalog, bytes);
        Path staging = Files.writeString(
                store.resolve("gse-derived-manifest.staging"), "safe staging");

        DurableCleanupPlan plan = DurableStorageOperations.planCleanup(
                new DurableCleanupRequest(store, DurableCleanupScope.LIVE_STORE));
        assertEquals(List.of(staging), plan.deleteSet().stream()
                .map(entry -> entry.member()).toList());
        DurableStorageOperations.applyCleanup(plan);
        assertEquals(components, componentPaths(store));
        assertFalse(Files.exists(staging));
        Files.delete(catalog);
        assertTrue(DurableStorageOperations.planCleanup(
                new DurableCleanupRequest(store, DurableCleanupScope.LIVE_STORE))
                .deleteSet().isEmpty());
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(store).status());
    }

    @Test
    void changedOrAliasedDerivedCandidateFailsClosed(@TempDir Path workspace)
            throws Exception {
        Path store = workspace.resolve("store");
        writeTwoGenerations(store);
        DurableCleanupRequest request = new DurableCleanupRequest(
                store, DurableCleanupScope.LIVE_STORE);
        DurableCleanupPlan stale = DurableStorageOperations.planCleanup(request);
        Path candidate = stale.deleteSet().getFirst().member();
        Files.write(candidate, new byte[] {1, 2, 3});
        DurableOperationException changed = assertThrows(
                DurableOperationException.class,
                () -> DurableStorageOperations.applyCleanup(stale));
        assertEquals(DurableOperationException.Reason.SOURCE_INVALID,
                changed.reason());
        assertTrue(Files.exists(candidate));

        Path aliasTarget = Files.writeString(store.resolve(
                "gse-derived-index-00000000000000000000-00000-"
                        + "22222222222222222222222222222222.idx.staging"),
                "aliased");
        Files.createLink(workspace.resolve(
                "v43-derived-alias-" + UUID.randomUUID()), aliasTarget);
        DurableOperationException aliased = assertThrows(
                DurableOperationException.class,
                () -> DurableStorageOperations.planCleanup(request));
        assertEquals(DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM,
                aliased.reason());
    }

    @Test
    void backupRestoreIsColdThenWarmAndContinuesMutation(
            @TempDir Path workspace
    ) throws Exception {
        Path store = workspace.resolve("store");
        Path backup = workspace.resolve("backup");
        Path restored = workspace.resolve("restored");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store))) {
            engine.addAll(documents()).join();
            engine.checkpoint().join();
            engine.backup(new DurableBackupRequest(
                    backup, 64L * 1024 * 1024)).join();
        }
        try (var members = Files.list(backup)) {
            assertTrue(members.noneMatch(path -> path.getFileName().toString()
                    .startsWith("gse-derived-")));
        }
        var semantic = builder().verifyDurableBackup(backup,
                new DurableVerificationConfig<>("v43-phase5-store",
                        "v43-phase5-schema", new DocumentCodec(), 1,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_DOCUMENTS));
        assertEquals(DurableSemanticVerificationStatus.SEMANTICALLY_VALID,
                semantic.status(), semantic.findings().toString());
        builder().restoreDurableBackup(backup, config(restored));
        assertEquals(DurableDerivedStateStatus.ABSENT,
                DurableStorageOperations.inspectDerivedState(restored).status());

        try (DurableSearchEngine<Integer, Document> first = builder()
                .buildDurable(config(restored))) {
            assertEquals(DurableReopenOutcome.FULL_FALLBACK,
                    first.lastReopenReport().orElseThrow().outcome());
            first.add(new Document(4, "book", 40, "delta",
                    "continued search")).join();
            first.checkpoint().join();
        }
        try (DurableSearchEngine<Integer, Document> second = builder()
                .buildDurable(config(restored))) {
            assertEquals(DurableReopenOutcome.COMPLETE_WARM,
                    second.lastReopenReport().orElseThrow().outcome());
            assertEquals(List.of(1, 2, 3, 4), ids(second.search(
                    Query.term(TEXT, "search"))));
        }
    }

    @Test
    void concurrentMutationBurstsRemainWarmAcrossRepeatedCheckpoints(
            @TempDir Path store
    ) {
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store))) {
            engine.addAll(documents()).join();
            for (int cycle = 0; cycle < 4; cycle++) {
                int base = 10 + cycle * 20;
                CompletableFuture<?>[] writes = new CompletableFuture<?>[20];
                for (int index = 0; index < writes.length; index++) {
                    int id = base + index;
                    writes[index] = engine.add(new Document(id, "burst", id,
                            "title-" + id, "search burst " + cycle));
                }
                CompletableFuture.allOf(writes).join();
                engine.checkpoint().join();
            }
        }
        assertEquals(DurableDerivedStateStatus.VALID,
                DurableStorageOperations.inspectDerivedState(store).status());
        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(config(store))) {
            assertEquals(DurableReopenOutcome.COMPLETE_WARM,
                    reopened.lastReopenReport().orElseThrow().outcome());
            assertEquals(83, reopened.search(Query.term(TEXT, "search")).size());
        }
    }

    private static void writeTwoGenerations(Path store) {
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store))) {
            engine.addAll(documents()).join();
            engine.checkpoint().join();
            engine.update(new Document(2, "book", 25, "alpine",
                    "java search refreshed")).join();
            engine.checkpoint().join();
        }
    }

    private static Set<Path> componentPaths(Path store) throws IOException {
        try (var members = Files.list(store)) {
            return members.filter(path -> COMPONENT.matcher(
                            path.getFileName().toString()).matches())
                    .collect(Collectors.toUnmodifiableSet());
        }
    }

    private static List<Document> documents() {
        return List.of(
                new Document(1, "book", 10, "alpha", "java search"),
                new Document(2, "music", 20, "alpine", "memory search"),
                new Document(3, "book", 30, "beta", "search engine"));
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID)
                .field(CATEGORY).field(PRICE).field(TITLE).field(BODY)
                .textField(TEXT)
                .index(IndexDefinition.equality(CATEGORY))
                .index(IndexDefinition.range(PRICE))
                .index(IndexDefinition.prefix(TITLE))
                .index(IndexDefinition.text(TEXT));
    }

    private static DurableStorageConfig<Integer, Document> config(Path store) {
        return DurableStorageConfig.builder(store, new DocumentCodec())
                .format(DurableStorageFormat.V1_2)
                .storageIdentity("v43-phase5-store")
                .schemaIdentity("v43-phase5-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .maxDerivedStateBytes(32L * 1024 * 1024)
                .build();
    }

    private static List<Integer> ids(List<Document> values) {
        return values.stream().map(Document::id).toList();
    }

    private record Document(
            int id,
            String category,
            int price,
            String title,
            String body
    ) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v43-phase5-codec";
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
                return new Document(input.readInt(), input.readUTF(),
                        input.readInt(), input.readUTF(), input.readUTF());
            } catch (IOException malformed) {
                throw new IllegalArgumentException(malformed);
            }
        }
    }
}
