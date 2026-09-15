package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.PlannerConfig;
import io.github.patricklfdm.generalsearch.query.RangePlanningMode;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V50ApplicationTransferTest {
    @TempDir Path workspace;
    record Doc(int id, String value) { }
    private static final Field<Doc, Integer> ID = Field.of("id", Integer.class, Doc::id);
    private static final Field<Doc, String> VALUE = Field.of("value", String.class, Doc::value);
    private static final UUID HISTORY = UUID.fromString("33333333-3333-3333-3333-333333333333");
    private final Codec codec = new Codec();

    record AnnotatedDoc(@io.github.patricklfdm.generalsearch.schema.annotation.SearchId int id,
            @io.github.patricklfdm.generalsearch.schema.annotation.SearchIndex(io.github.patricklfdm.generalsearch.schema.annotation.IndexType.EQUALITY) String value) { }

    @Test
    void annotatedSchemaCaptureKeepsResolvedFieldAndIndexIdentity() {
        var captured = SearchEngine.annotatedBuilder(AnnotatedDoc.class, Integer.class).configuration();
        var restored = captured.newBuilder().configuration();
        assertSame(captured.schema(), restored.schema());
        assertEquals(captured.indexes(), restored.indexes());
        assertSame(restored.schema().requireField("value"), restored.indexes().getFirst().field());
    }

    @Test
    void configurationCaptureKeepsCanonicalExtendedFieldsAndNondefaultsWithoutThreads() {
        var originalSchema = SearchSchema.builder(Doc.class, ID).build();
        var settings = new SnapshotEngineConfig(31, 7, Duration.ofNanos(1_234_567));
        var planner = new PlannerConfig(RangePlanningMode.FORCE_SCAN);
        var builder = SearchEngine.builder(originalSchema).index(IndexDefinition.equality(VALUE)).config(settings).plannerConfig(planner);
        long threads = Thread.getAllStackTraces().keySet().stream().filter(t -> t.getName().contains("snapshot")).count();
        var captured = builder.configuration();
        builder.config(SnapshotEngineConfig.DEFAULT).plannerConfig(PlannerConfig.DEFAULT).index(IndexDefinition.equality(ID));
        var restored = captured.newBuilder().configuration();
        assertSame(ID, restored.schema().idField()); assertSame(VALUE, restored.schema().requireField("value"));
        assertTrue(originalSchema.field("value").isEmpty()); assertEquals(1, restored.indexes().size());
        assertEquals(settings, restored.config()); assertEquals(planner, restored.plannerConfig());
        assertEquals(threads, Thread.getAllStackTraces().keySet().stream().filter(t -> t.getName().contains("snapshot")).count());
    }

    @Test
    void eachFormatPreservesHistorySequenceOrderAndActiveIndexesWithoutCreatingAnchor() throws Exception {
        for (var format : List.of(DurableStorageFormat.V1_0, DurableStorageFormat.V1_1, DurableStorageFormat.V1_2)) {
            var config = config("anchor-" + format.minor(), format);
            var docs = List.of(new Doc(3, "shared"), new Doc(1, "changed"));
            var state = new DurableApplicationState<>(HISTORY, 41, docs, List.of(IndexDefinition.prefix(VALUE)));
            Path target = workspace.resolve("backup-" + format.minor());
            var result = builder(false).writeDurableBackup(state, config, new DurableBackupRequest(target, 1 << 20));
            assertEquals(HISTORY, result.sourceHistory()); assertEquals(41, result.sequence());
            assertFalse(Files.exists(config.directory()));
            assertEquals(DurableVerificationStatus.VALID, DurableStorageOperations.verifyBackup(target).status());
            var loaded = builder(true).readDurableBackup(target, verification(config), 1 << 20);
            assertEquals(docs, loaded.documents()); assertEquals(HISTORY, loaded.history()); assertEquals(41, loaded.sequence());
            assertInstanceOf(io.github.patricklfdm.generalsearch.index.prefix.PrefixIndexDefinition.class, loaded.indexes().getFirst());
            assertThrows(DurableOperationException.class, () -> builder(false).readDurableBackup(target, verification(config), 1 << 20));
            var restoreConfig = config("restored-" + format.minor(), format);
            builder(true).restoreDurableBackup(target, restoreConfig);
            try (var engine = builder(true).buildDurable(restoreConfig)) {
                assertEquals(docs, engine.search(document -> true)); assertEquals(41, engine.currentSequence());
            }
        }
    }

    @Test
    void exportUsesDynamicIndexesInsteadOfOriginalStartupIndexes() {
        var config = config("live", DurableStorageFormat.V1_2);
        Path target = workspace.resolve("dynamic");
        try (var engine = builder(false).buildDurable(config)) {
            engine.addAll(List.of(new Doc(9, "old"), new Doc(3, "shared"), new Doc(1, "shared"))).join();
            engine.remove(9).join();
            engine.dropIndex("value").join(); engine.createIndex(IndexDefinition.prefix(VALUE)).join();
            builder(false).writeDurableBackup(new DurableApplicationState<>(HISTORY,
                    engine.currentSequence(), engine.search(document -> true), List.of(IndexDefinition.prefix(VALUE))),
                    config, new DurableBackupRequest(target, 1 << 20));
        }
        var loaded = builder(true).readDurableBackup(target, verification(config), 1 << 20);
        assertEquals(List.of(new Doc(3, "shared"), new Doc(1, "shared")), loaded.documents());
        assertEquals(4, loaded.sequence());
        assertInstanceOf(io.github.patricklfdm.generalsearch.index.prefix.PrefixIndexDefinition.class, loaded.indexes().getFirst());
    }

    @Test
    void importBoundsAndCorruptionRejectBeforeCodecAndPreserveSource() throws Exception {
        var config = config("anchor", DurableStorageFormat.V1_0);
        Path target = workspace.resolve("backup");
        builder(false).writeDurableBackup(new DurableApplicationState<>(HISTORY, 0, List.of(), List.of(IndexDefinition.equality(VALUE))),
                config, new DurableBackupRequest(target, 1 << 20));
        codec.calls.set(0);
        var failure = assertThrows(DurableOperationException.class, () -> builder(false).readDurableBackup(target, verification(config), 1));
        assertEquals(DurableOperationException.Reason.CAPACITY_EXCEEDED, failure.reason()); assertEquals(0, codec.calls.get());
        Path checkpoint = target.resolve("gse-backup-checkpoint"); byte[] original = Files.readAllBytes(checkpoint);
        byte[] damaged = original.clone(); damaged[damaged.length - 1] ^= 1; Files.write(checkpoint, damaged);
        assertThrows(DurableOperationException.class, () -> builder(false).readDurableBackup(target, verification(config), 1 << 20));
        assertArrayEquals(damaged, Files.readAllBytes(checkpoint)); assertEquals(0, codec.calls.get());
    }

    @Test
    void invalidExportCannotPublishAndOccupiedTargetIsPreserved() throws Exception {
        var config = config("anchor", DurableStorageFormat.V1_0);
        Path target = workspace.resolve("backup");
        var invalid = new DurableApplicationState<>(HISTORY, 10,
                List.of(new Doc(1, "one"), new Doc(1, "two")), List.of(IndexDefinition.equality(VALUE)));
        assertThrows(IllegalArgumentException.class, () -> builder(false).writeDurableBackup(invalid, config, new DurableBackupRequest(target, 1 << 20)));
        assertFalse(Files.exists(target)); assertFalse(Files.exists(config.directory()));
        Files.createDirectory(target); Files.writeString(target.resolve("user-file"), "keep");
        var failure = assertThrows(DurableOperationException.class, () -> builder(false).writeDurableBackup(invalid, config, new DurableBackupRequest(target, 1 << 20)));
        assertEquals(DurableOperationException.Reason.TARGET_EXISTS, failure.reason());
        assertEquals("keep", Files.readString(target.resolve("user-file")));
    }

    @Test
    void exportRejectsSymlinkAncestorBeforeCreatingAnyBundle() throws Exception {
        Path real = Files.createDirectory(workspace.resolve("real")); Files.createDirectory(real.resolve("parent"));
        Path alias = Files.createSymbolicLink(workspace.resolve("alias"), real);
        var state = new DurableApplicationState<Doc>(HISTORY, 0, List.of(), List.of(IndexDefinition.equality(VALUE)));
        assertEquals(DurableOperationException.Reason.TARGET_INVALID,
                assertThrows(DurableOperationException.class, () -> builder(false).writeDurableBackup(state,
                        config("anchor", DurableStorageFormat.V1_0), new DurableBackupRequest(alias.resolve("parent/backup"), 1 << 20))).reason());
        assertFalse(Files.exists(real.resolve("parent/backup")));
    }

    private SearchEngineBuilder<Integer, Doc> builder(boolean prefix) {
        return SearchEngine.builder(Doc.class, ID).field(VALUE)
                .index(prefix ? IndexDefinition.prefix(VALUE) : IndexDefinition.equality(VALUE));
    }
    private DurableStorageConfig<Integer, Doc> config(String name, DurableStorageFormat format) {
        return DurableStorageConfig.builder(workspace.resolve(name), codec).format(format)
                .storageIdentity("fixture-store").schemaIdentity("fixture-schema").maxEncodedKeyBytes(1024)
                .maxEncodedDocumentBytes(65536).maxDocuments(10000).build();
    }
    private DurableVerificationConfig<Integer, Doc> verification(DurableStorageConfig<Integer, Doc> config) {
        return new DurableVerificationConfig<>(config.storageIdentity(), config.schemaIdentity(), codec, 1,
                config.maxEncodedKeyBytes(), config.maxEncodedDocumentBytes(), config.maxDocuments());
    }
    static class Codec implements DurableCodec<Integer, Doc> {
        final AtomicInteger calls = new AtomicInteger();
        public String codecId() { return "fixture-codec"; }
        public int codecVersion() { return 1; }
        public byte[] encodeKey(Integer key) { calls.incrementAndGet(); return ByteBuffer.allocate(4).putInt(key).array(); }
        public Integer decodeKey(byte[] bytes) { calls.incrementAndGet(); return ByteBuffer.wrap(bytes).getInt(); }
        public byte[] encodeDocument(Doc doc) { calls.incrementAndGet(); return (doc.id() + ":" + doc.value()).getBytes(StandardCharsets.UTF_8); }
        public Doc decodeDocument(byte[] bytes) { calls.incrementAndGet(); String[] parts = new String(bytes, StandardCharsets.UTF_8).split(":", 2); return new Doc(Integer.parseInt(parts[0]), parts[1]); }
    }
}
