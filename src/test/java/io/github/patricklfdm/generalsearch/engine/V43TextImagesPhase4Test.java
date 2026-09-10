package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableDerivedStateStatus;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationPlan;
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
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V43TextImagesPhase4Test {
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
    private static final List<Document> DOCUMENTS = List.of(
            new Document(1, "book", 10, "alpha", "Java search search"),
            new Document(2, "music", 20, "alpine", "java memory model"),
            new Document(3, "book", 30, "beta", "search engine design"),
            new Document(4, "empty", 40, "gamma", "!!!"),
            new Document(5, "unicode", 50, "delta", "ＣＡＦＥ cafe"));

    @Test
    void mixedCheckpointPublishesCompleteWarmTextSemantics(@TempDir Path store) {
        writeCheckpoint(store);
        var inspected = DurableStorageOperations.inspectDerivedState(store);
        assertEquals(DurableDerivedStateStatus.VALID, inspected.status());
        assertEquals(4, inspected.admissibleComponentCount());

        try (SearchEngine<Integer, Document> rebuilt = builder().build();
                DurableSearchEngine<Integer, Document> reopened = builder()
                        .buildDurable(config(store, DurableStorageFormat.V1_2))) {
            rebuilt.addAll(DOCUMENTS).join();
            DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.COMPLETE_WARM, report.outcome());
            assertEquals(4, report.loadedComponentCount());
            assertEquals(0, report.rebuiltComponentCount());
            assertTextEquivalent(rebuilt, reopened);
        }
    }

    @Test
    void corruptTextComponentLoadsStructuredSiblingsAndRefreshes(
            @TempDir Path store
    ) throws IOException {
        writeCheckpoint(store);
        corrupt(component(store, 3));
        assertEquals(DurableDerivedStateStatus.PARTIAL,
                DurableStorageOperations.inspectDerivedState(store).status());

        try (SearchEngine<Integer, Document> rebuilt = builder().build();
                DurableSearchEngine<Integer, Document> reopened = builder()
                        .buildDurable(config(store, DurableStorageFormat.V1_2))) {
            rebuilt.addAll(DOCUMENTS).join();
            DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.PARTIAL_FALLBACK, report.outcome());
            assertEquals(3, report.loadedComponentCount());
            assertEquals(1, report.rebuiltComponentCount());
            assertEquals(3, report.rejections().getFirst().ordinal());
            assertTrue(report.refreshAttempted());
            assertTrue(report.refreshSucceeded());
            assertTextEquivalent(rebuilt, reopened);
        }
        assertEquals(DurableDerivedStateStatus.VALID,
                DurableStorageOperations.inspectDerivedState(store).status());
    }

    @Test
    void corruptStructuredComponentPreservesWarmTextSibling(
            @TempDir Path store
    ) throws IOException {
        writeCheckpoint(store);
        corrupt(component(store, 0));
        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2))) {
            DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.PARTIAL_FALLBACK, report.outcome());
            assertEquals(3, report.loadedComponentCount());
            assertEquals(1, report.rebuiltComponentCount());
            assertEquals(0, report.rejections().getFirst().ordinal());
            assertEquals(List.of(1, 2), ids(reopened.search(
                    Query.term(TEXT, "java"))));
            assertEquals(List.of(1, 3), ids(reopened.search(
                    Query.eq(CATEGORY, "book"))));
        }
    }

    @Test
    void catalogFailureRebuildsAndRepublishesAllFourKinds(
            @TempDir Path store
    ) throws IOException {
        writeCheckpoint(store);
        corrupt(store.resolve(DurableStructuredDerivedState.CATALOG_FILE));
        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2))) {
            DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.FULL_FALLBACK, report.outcome());
            assertEquals(0, report.loadedComponentCount());
            assertEquals(4, report.rebuiltComponentCount());
            assertTrue(report.refreshSucceeded());
            assertEquals(List.of(1), ids(reopened.search(
                    Query.allTerms(TEXT, "java search"))));
        }
        assertEquals(DurableDerivedStateStatus.VALID,
                DurableStorageOperations.inspectDerivedState(store).status());
    }

    @Test
    void warmCheckpointReplaysTextMutationAndDynamicLifecycle(
            @TempDir Path store
    ) {
        DurableStorageConfig<Integer, Document> storage = config(
                store, DurableStorageFormat.V1_2);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            engine.addAll(DOCUMENTS).join();
            engine.checkpoint().join();
            engine.update(new Document(2, "music", 20, "alpine",
                    "replacement replay term")).join();
            engine.remove(3).join();
            engine.dropIndex(BODY.name()).join();
            engine.createIndex(IndexDefinition.text(TEXT)).join();
        }
        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(storage)) {
            DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.COMPLETE_WARM, report.outcome());
            assertEquals(4, report.loadedComponentCount());
            assertEquals(1, report.replayCreatedIndexCount());
            assertEquals(List.of(2), ids(reopened.search(
                    Query.term(TEXT, "replay"))));
            assertEquals(List.of(1), ids(reopened.search(
                    Query.term(TEXT, "search"))));
            assertNull(reopened.get(3));
        }
    }

    @Test
    void directOlderMigrationIsColdThenPublishesCompleteMixedGeneration(
            @TempDir Path workspace
    ) throws IOException {
        Path source = workspace.resolve("source");
        Path target = workspace.resolve("target");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source, DurableStorageFormat.V1_1))) {
            engine.addAll(DOCUMENTS).join();
            engine.checkpoint().join();
        }
        DurableMigrationRequest<Integer, Document, Integer, Document> request =
                request(source, target);
        DurableMigrationPlan plan = builder().planDurableMigration(builder(), request);
        builder().applyDurableMigration(builder(), request, plan);
        assertEquals(DurableDerivedStateStatus.ABSENT,
                DurableStorageOperations.inspectDerivedState(target).status());

        try (DurableSearchEngine<Integer, Document> first = builder()
                .buildDurable(config(target, DurableStorageFormat.V1_2))) {
            DurableReopenReport report = first.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.FULL_FALLBACK, report.outcome());
            assertEquals(4, report.rebuiltComponentCount());
            assertTrue(report.refreshSucceeded());
        }
        try (DurableSearchEngine<Integer, Document> second = builder()
                .buildDurable(config(target, DurableStorageFormat.V1_2))) {
            assertEquals(DurableReopenOutcome.COMPLETE_WARM,
                    second.lastReopenReport().orElseThrow().outcome());
            assertEquals(List.of(1), ids(second.search(
                    Query.allTerms(TEXT, "java search"))));
        }
    }

    @Test
    void textGenerationCapacityFailureRemainsNonAuthoritative(
            @TempDir Path store
    ) {
        DurableStorageConfig<Integer, Document> tiny = config(
                store, DurableStorageFormat.V1_2, 128L);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(tiny)) {
            engine.addAll(DOCUMENTS).join();
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
            assertEquals(List.of(1, 2), ids(reopened.search(
                    Query.term(TEXT, "java"))));
        }
    }

    private static void assertTextEquivalent(
            SearchEngine<Integer, Document> rebuilt,
            SearchEngine<Integer, Document> reopened
    ) {
        assertEquals(rebuilt.search(Query.term(TEXT, "java")),
                reopened.search(Query.term(TEXT, "java")));
        assertEquals(rebuilt.search(Query.anyTerms(TEXT, "java design")),
                reopened.search(Query.anyTerms(TEXT, "java design")));
        assertEquals(rebuilt.search(Query.allTerms(TEXT, "java search")),
                reopened.search(Query.allTerms(TEXT, "java search")));

        List<SearchRequest<Document>> requests = List.of(
                SearchRequest.of(SearchQueries.text(TEXT, "java search")),
                SearchRequest.of(SearchQueries.phrase(TEXT, "java search")),
                SearchRequest.of(SearchQueries.fuzzy(TEXT, "serch")));
        for (SearchRequest<Document> request : requests) {
            assertEquals(rebuilt.search(request).hits(), reopened.search(request).hits());
        }
        RankedSearchRequest<Document> ranked = RankedSearchRequest.of(
                TextScoringQuery.of(TEXT, "java search"), 10);
        assertEquals(rebuilt.searchTopK(ranked), reopened.searchTopK(ranked));
        assertEquals(
                Double.doubleToLongBits(rebuilt.explain(requests.getFirst(), 1)
                        .orElseThrow().score()),
                Double.doubleToLongBits(reopened.explain(requests.getFirst(), 1)
                        .orElseThrow().score()));
        assertNotEquals(0, reopened.search(requests.get(2)).hits().size());
    }

    private static void writeCheckpoint(Path store) {
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2))) {
            engine.addAll(DOCUMENTS).join();
            engine.checkpoint().join();
        }
    }

    private static Path component(Path store, int ordinal) throws IOException {
        String marker = "-%05d-".formatted(ordinal);
        try (var entries = Files.list(store)) {
            return entries.filter(path -> DurableStructuredDerivedState.COMPONENT_FILE
                            .matcher(path.getFileName().toString()).matches())
                    .filter(path -> path.getFileName().toString().contains(marker))
                    .min(Comparator.comparing(path -> path.getFileName().toString()))
                    .orElseThrow();
        }
    }

    private static void corrupt(Path path) throws IOException {
        byte[] bytes = Files.readAllBytes(path);
        bytes[bytes.length / 2] ^= 1;
        Files.write(path, bytes);
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

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            DurableStorageFormat format
    ) {
        return config(directory, format, 32L * 1024 * 1024);
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            DurableStorageFormat format,
            long maxDerivedBytes
    ) {
        DurableStorageConfig.Builder<Integer, Document> builder =
                DurableStorageConfig.builder(directory, new DocumentCodec())
                        .format(format)
                        .storageIdentity("v43-phase4-store")
                        .schemaIdentity("v43-phase4-schema")
                        .checkpointWalBytes(1024 * 1024)
                        .maxRetainedBytes(64L * 1024 * 1024);
        if (format.equals(DurableStorageFormat.V1_2)) {
            builder.maxDerivedStateBytes(maxDerivedBytes);
        }
        return builder.build();
    }

    private static DurableMigrationRequest<Integer, Document, Integer, Document>
            request(Path source, Path target) {
        return new DurableMigrationRequest<>(source,
                new DurableVerificationConfig<>(
                        "v43-phase4-store", "v43-phase4-schema",
                        new DocumentCodec(), 1,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_DOCUMENTS),
                config(target, DurableStorageFormat.V1_2),
                new DurableMigrationTransformDescriptor("identity-format-v1", 1),
                (key, document) -> new DurableMigrationRecord<>(key, document),
                64L * 1024 * 1024, 64L * 1024 * 1024,
                1024 * 1024, 1000, 1000, 64 * 1024);
    }

    private static List<Integer> ids(List<Document> documents) {
        return documents.stream().map(Document::id).toList();
    }

    private record Document(
            int id,
            String category,
            int price,
            String title,
            String body
    ) {
    }

    private static final class DocumentCodec implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v43-phase4-codec";
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
                Document result = new Document(input.readInt(), input.readUTF(),
                        input.readInt(), input.readUTF(), input.readUTF());
                if (input.available() != 0) {
                    throw new IllegalArgumentException("trailing document bytes");
                }
                return result;
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid document bytes", failure);
            }
        }
    }
}
