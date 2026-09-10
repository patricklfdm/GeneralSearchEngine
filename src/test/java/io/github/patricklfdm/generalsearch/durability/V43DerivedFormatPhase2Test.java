package io.github.patricklfdm.generalsearch.durability;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.OptionalLong;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V43DerivedFormatPhase2Test {
    private static final String FIXTURE_ROOT =
            "/compatibility/v43-derived-v12/";
    private static final String PROFILE_DIGEST =
            "596a1cdd7cf38f97f7bc740ff7a6e340fcca9c86b62ad261886db4c687b4595a";
    private static final String CATALOG_IDENTITY =
            "gse-derived-catalog-v1-"
                    + "5ffe7bbd7255fd5df581bae9c352f4c59c55214b5348bbd13c410063b6b266a6";
    private static final byte[] CATALOG_DOMAIN =
            "gse-derived-catalog-content-v1\0"
                    .getBytes(StandardCharsets.US_ASCII);
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<FixtureDocument, Integer> FIXTURE_ID =
            Field.of("id", Integer.class, FixtureDocument::id);
    private static final Field<FixtureDocument, String> CATEGORY =
            Field.of("category", String.class, FixtureDocument::category);
    private static final Field<FixtureDocument, Integer> PRICE =
            Field.of("price", Integer.class, FixtureDocument::price);
    private static final Field<FixtureDocument, String> TITLE =
            Field.of("title", String.class, FixtureDocument::title);
    private static final Field<FixtureDocument, String> BODY =
            Field.of("body", String.class, FixtureDocument::body);
    private static final TextField<FixtureDocument> ANALYZED_BODY =
            TextField.of(BODY, SimpleAnalyzer.INSTANCE);

    @Test
    void selectorAndDerivedAllowancePreserveOlderDefaults(@TempDir Path workspace) {
        DurableStorageConfig<Integer, Document> legacy = config(
                workspace.resolve("legacy"), DurableStorageFormat.V1_0).build();
        assertEquals(DurableStorageFormat.V1_0, legacy.format());
        assertEquals(DurableStorageConfig.DEFAULT_MAX_DERIVED_STATE_BYTES,
                legacy.maxDerivedStateBytes());

        assertThrows(IllegalArgumentException.class, () -> config(
                workspace.resolve("old-explicit"), DurableStorageFormat.V1_1)
                .maxDerivedStateBytes(1024).build());
        assertThrows(IllegalArgumentException.class, () -> config(
                workspace.resolve("zero"), DurableStorageFormat.V1_2)
                .maxDerivedStateBytes(0).build());
        assertThrows(IllegalArgumentException.class, () -> config(
                workspace.resolve("too-large"), DurableStorageFormat.V1_2)
                .maxDerivedStateBytes(9L * 1024 * 1024 * 1024 * 1024).build());
        assertThrows(IllegalArgumentException.class, () -> config(
                workspace.resolve("retained"), DurableStorageFormat.V1_2)
                .maxRetainedBytes(1024 * 1024)
                .checkpointWalBytes(1024)
                .maxDerivedStateBytes(1024 * 1024 + 1L).build());

        DurableStorageConfig<Integer, Document> selected = config(
                workspace.resolve("selected"), DurableStorageFormat.V1_2).build();
        assertEquals(DurableStorageFormat.V1_2, selected.format());
        assertEquals(DurableStorageConfig.DEFAULT_MAX_DERIVED_STATE_BYTES,
                selected.maxDerivedStateBytes());
    }

    @Test
    void exactV12CanonicalStoreActivatesPhaseThreeEmptyCatalog(
            @TempDir Path workspace
    ) {
        Path store = workspace.resolve("store");
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .buildDurable(config(store, DurableStorageFormat.V1_2).build())) {
            engine.add(new Document(1, "alpha")).join();
            engine.checkpoint().join();
            assertTrue(engine.lastReopenReport().isEmpty());
        }

        DurableStoreFormatReport format =
                DurableStorageOperations.inspectStoreFormat(store);
        assertEquals(DurableVerificationStatus.VALID,
                format.structuralReport().status());
        assertEquals(Optional.of(DurableStorageFormat.V1_2),
                format.declaredFormat());
        assertTrue(format.profileDigest().isPresent());

        DurableDerivedStateReport derived =
                DurableStorageOperations.inspectDerivedState(store);
        assertEquals(DurableDerivedStateStatus.VALID, derived.status());
        assertEquals(Optional.of(DurableStorageFormat.V1_2),
                derived.declaredFormat());
        assertTrue(derived.history().isPresent());
        assertEquals(OptionalLong.of(1), derived.checkpointSequence());
        assertEquals(0, derived.expectedComponentCount());
        assertTrue(derived.components().isEmpty());

        try (DurableSearchEngine<Integer, Document> reopened = SearchEngine
                .builder(Document.class, ID)
                .buildDurable(config(store, DurableStorageFormat.V1_2).build())) {
            assertEquals(new Document(1, "alpha"), reopened.get(1));
            DurableReopenReport report = reopened.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.COMPLETE_WARM, report.outcome());
            assertEquals(0, report.loadedComponentCount());
            assertEquals(0, report.rebuiltComponentCount());
        }
    }

    @Test
    void exactV12BackupIsCanonicalOnlyAndRestoresCold(@TempDir Path workspace) {
        Path store = workspace.resolve("store");
        Path backup = workspace.resolve("backup");
        Path restored = workspace.resolve("restored");
        DurableBackupResult result;
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .buildDurable(config(store, DurableStorageFormat.V1_2).build())) {
            engine.add(new Document(1, "alpha")).join();
            engine.checkpoint().join();
            result = engine.backup(new DurableBackupRequest(
                    backup, 64L * 1024 * 1024)).join();
        }
        assertEquals(DurableBackupFormat.V1_2, result.format());
        assertTrue(result.contentIdentity().startsWith("gse-backup-v3-"));
        assertEquals(3, result.memberCount());
        assertEquals(3, countMembers(backup));
        assertFalse(Files.exists(backup.resolve("gse-derived-manifest")));

        DurableBackupFormatReport report =
                DurableStorageOperations.inspectBackupFormat(backup);
        assertEquals(DurableVerificationStatus.VALID,
                report.structuralReport().status());
        assertEquals(Optional.of(DurableBackupFormat.V1_2),
                report.declaredFormat());
        assertEquals(Optional.of(DurableStorageFormat.V1_2),
                report.sourceFormat());

        SearchEngine.builder(Document.class, ID).restoreDurableBackup(
                backup, config(restored, DurableStorageFormat.V1_2).build());
        assertEquals(DurableDerivedStateStatus.ABSENT,
                DurableStorageOperations.inspectDerivedState(restored).status());
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .buildDurable(config(restored, DurableStorageFormat.V1_2).build())) {
            assertEquals(new Document(1, "alpha"), engine.get(1));
        }
    }

    @Test
    void olderFormatsRemainNotApplicable(@TempDir Path store) {
        try (DurableSearchEngine<Integer, Document> ignored = SearchEngine
                .builder(Document.class, ID)
                .buildDurable(config(store, DurableStorageFormat.V1_0).build())) {
            // Empty initialized V1.0 authority is enough for offline classification.
        }
        DurableDerivedStateReport report =
                DurableStorageOperations.inspectDerivedState(store);
        assertEquals(DurableDerivedStateStatus.NOT_APPLICABLE, report.status());
        assertEquals(Optional.of(DurableStorageFormat.V1_0),
                report.declaredFormat());
        assertTrue(report.history().isEmpty());
    }

    @Test
    void independentlyEncodedPhysicalFixtureIsValidAndReadOnly(
            @TempDir Path workspace
    ) throws Exception {
        Path live = Files.createDirectory(workspace.resolve("live"));
        Path backup = Files.createDirectory(workspace.resolve("backup"));
        materializeFixture(live, backup);
        Map<String, String> before = directoryDigests(live);

        DurableStoreFormatReport store =
                DurableStorageOperations.inspectStoreFormat(live);
        DurableDerivedStateReport derived =
                DurableStorageOperations.inspectDerivedState(live);
        DurableBackupFormatReport bundle =
                DurableStorageOperations.inspectBackupFormat(backup);

        assertEquals(DurableVerificationStatus.VALID,
                store.structuralReport().status());
        assertEquals(Optional.of(PROFILE_DIGEST), store.profileDigest());
        assertEquals(DurableDerivedStateStatus.VALID, derived.status());
        assertEquals(Optional.of(CATALOG_IDENTITY), derived.catalogIdentity());
        assertEquals(4, derived.expectedComponentCount());
        assertEquals(4, derived.admissibleComponentCount());
        assertEquals(List.of("equality", "range", "prefix", "text"),
                derived.components().stream()
                        .map(DurableDerivedComponentReport::indexKind).toList());
        assertEquals(DurableVerificationStatus.VALID,
                bundle.structuralReport().status());
        assertEquals(Optional.of(DurableBackupFormat.V1_2),
                bundle.declaredFormat());
        assertEquals(before, directoryDigests(live));
    }

    @Test
    void independentFixtureCoversComponentSelectiveAndCatalogClassifications(
            @TempDir Path workspace
    ) throws Exception {
        Path missing = materializeLive(workspace.resolve("missing"));
        Path first = firstComponent(missing);
        Files.delete(first);
        DurableDerivedStateReport missingReport =
                DurableStorageOperations.inspectDerivedState(missing);
        assertEquals(DurableDerivedStateStatus.PARTIAL, missingReport.status());
        assertEquals(3, missingReport.admissibleComponentCount());
        assertEquals(DurableDerivedComponentStatus.MISSING,
                missingReport.components().getFirst().status());
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(missing).status());

        Path corruptComponent = materializeLive(workspace.resolve("component"));
        flipMiddle(firstComponent(corruptComponent));
        DurableDerivedStateReport corruptComponentReport =
                DurableStorageOperations.inspectDerivedState(corruptComponent);
        assertEquals(DurableDerivedStateStatus.PARTIAL,
                corruptComponentReport.status());
        assertEquals(DurableDerivedComponentStatus.CORRUPT,
                corruptComponentReport.components().getFirst().status());
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(corruptComponent).status(),
                "non-authoritative damage must not corrupt canonical verification");

        Path stale = materializeLive(workspace.resolve("stale"));
        Path staleCatalog = stale.resolve("gse-derived-manifest");
        byte[] staleBytes = Files.readAllBytes(staleCatalog);
        staleBytes[48] ^= 1;
        resignCatalog(staleBytes);
        Files.write(staleCatalog, staleBytes);
        assertEquals(DurableDerivedStateStatus.STALE,
                DurableStorageOperations.inspectDerivedState(stale).status());

        Path incompatible = materializeLive(workspace.resolve("incompatible"));
        Path incompatibleCatalog = incompatible.resolve("gse-derived-manifest");
        byte[] incompatibleBytes = Files.readAllBytes(incompatibleCatalog);
        replaceAscii(incompatibleBytes, "gse-derived-generator-v1",
                "gse-derived-generator-v2");
        resignCatalog(incompatibleBytes);
        Files.write(incompatibleCatalog, incompatibleBytes);
        assertEquals(DurableDerivedStateStatus.INCOMPATIBLE,
                DurableStorageOperations.inspectDerivedState(incompatible).status());

        Path incomplete = materializeLive(workspace.resolve("incomplete"));
        Path incompleteCatalog = incomplete.resolve("gse-derived-manifest");
        byte[] incompleteBytes = Files.readAllBytes(incompleteCatalog);
        Files.write(incompleteCatalog,
                java.util.Arrays.copyOf(incompleteBytes, incompleteBytes.length / 2));
        assertEquals(DurableDerivedStateStatus.INCOMPLETE,
                DurableStorageOperations.inspectDerivedState(incomplete).status());

        Path corruptCatalog = materializeLive(workspace.resolve("catalog"));
        flipMiddle(corruptCatalog.resolve("gse-derived-manifest"));
        assertEquals(DurableDerivedStateStatus.CORRUPT,
                DurableStorageOperations.inspectDerivedState(corruptCatalog).status());
    }

    @Test
    void stagingAndUnreferencedBytesAreReportedWithoutChangingAuthority(
            @TempDir Path workspace
    ) throws Exception {
        Path live = materializeLive(workspace.resolve("inventory"));
        Path component = firstComponent(live);
        byte[] bytes = Files.readAllBytes(component);
        Path staging = live.resolve(component.getFileName() + ".staging");
        Files.write(staging, bytes);
        String alternate = component.getFileName().toString()
                .replace("0123456789abcdeffedcba9876543210",
                        "11111111111111111111111111111111");
        Files.write(live.resolve(alternate), bytes);

        DurableDerivedStateReport report =
                DurableStorageOperations.inspectDerivedState(live);
        assertEquals(DurableDerivedStateStatus.VALID, report.status());
        assertEquals(bytes.length, report.stagingBytes());
        assertEquals(bytes.length, report.unreferencedBytes());
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(live).status());
    }

    @Test
    void derivedAllowanceAndAliasedMembersFailOnlyDerivedInspection(
            @TempDir Path workspace
    ) throws Exception {
        Path bounded = materializeLive(workspace.resolve("bounded"));
        Path metadata = bounded.resolve("gse-metadata");
        byte[] metadataBytes = Files.readAllBytes(metadata);
        byte[] encodedAllowance = ByteBuffer.allocate(Long.BYTES)
                .order(ByteOrder.BIG_ENDIAN).putLong(33_554_432L).array();
        int allowanceOffset = indexOf(metadataBytes, encodedAllowance);
        assertNotEquals(-1, allowanceOffset);
        ByteBuffer.wrap(metadataBytes).order(ByteOrder.BIG_ENDIAN)
                .putLong(allowanceOffset, 1L);
        rewriteCrc(metadataBytes);
        Files.write(metadata, metadataBytes);
        DurableDerivedStateReport boundedReport =
                DurableStorageOperations.inspectDerivedState(bounded);
        assertEquals(DurableDerivedStateStatus.CORRUPT, boundedReport.status());
        assertTrue(boundedReport.findings().stream().anyMatch(finding ->
                finding.code().equals("DERIVED_BYTES_EXCEEDED")));
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(bounded).status());

        Path aliased = materializeLive(workspace.resolve("aliased"));
        Files.createLink(aliased.resolve("gse-derived-manifest.staging"),
                firstComponent(aliased));
        DurableDerivedStateReport aliasedReport =
                DurableStorageOperations.inspectDerivedState(aliased);
        assertEquals(DurableDerivedStateStatus.CORRUPT, aliasedReport.status());
        assertTrue(aliasedReport.findings().stream().anyMatch(finding ->
                finding.code().equals("ALIASED_DERIVED_MEMBER")));
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(aliased).status());
    }

    @Test
    void phaseThreeLoadsStructuredFixtureAndLeavesTextForPhaseFour(
            @TempDir Path workspace
    ) throws Exception {
        Path live = materializeLive(workspace.resolve("rebuild-only"));
        Map<String, String> before = directoryDigests(live);
        DurableStorageConfig<Integer, FixtureDocument> storage =
                DurableStorageConfig.builder(live, new FixtureCodec())
                        .format(DurableStorageFormat.V1_2)
                        .storageIdentity("v43-fixture-store")
                        .schemaIdentity("v43-fixture-schema")
                        .maxEncodedKeyBytes(1024)
                        .maxEncodedDocumentBytes(4096)
                        .maxBulkElements(1000)
                        .maxDocuments(10000)
                        .checkpointWalBytes(1_048_576)
                        .maxRetainedBytes(67_108_864)
                        .maxDerivedStateBytes(33_554_432)
                        .build();
        try (DurableSearchEngine<Integer, FixtureDocument> engine = SearchEngine
                .builder(FixtureDocument.class, FIXTURE_ID)
                .field(CATEGORY).field(PRICE).field(TITLE)
                .textField(ANALYZED_BODY)
                .index(IndexDefinition.equality(CATEGORY))
                .index(IndexDefinition.range(PRICE))
                .index(IndexDefinition.prefix(TITLE))
                .index(IndexDefinition.text(ANALYZED_BODY))
                .buildDurable(storage)) {
            assertEquals(7, engine.currentSequence());
            DurableReopenReport report = engine.lastReopenReport().orElseThrow();
            assertEquals(DurableReopenOutcome.PARTIAL_FALLBACK, report.outcome());
            assertEquals(3, report.loadedComponentCount());
            assertEquals(1, report.rebuiltComponentCount());
            assertFalse(report.refreshSucceeded());
        }
        assertEquals(before, directoryDigests(live));
    }

    private static DurableStorageConfig.Builder<Integer, Document> config(
            Path directory,
            DurableStorageFormat format
    ) {
        return DurableStorageConfig.builder(directory, new DocumentCodec())
                .format(format)
                .storageIdentity("v43-phase2-storage")
                .schemaIdentity("v43-phase2-schema");
    }

    private static long countMembers(Path directory) {
        try (var members = Files.list(directory)) {
            return members.count();
        } catch (java.io.IOException failure) {
            throw new AssertionError(failure);
        }
    }

    private static Path materializeLive(Path directory) throws IOException {
        Files.createDirectory(directory);
        materialize("live", directory);
        Files.write(directory.resolve("gse.lock"), new byte[0]);
        return directory;
    }

    private static void materializeFixture(Path live, Path backup)
            throws IOException {
        materialize("live", live);
        materialize("backup", backup);
        Files.write(live.resolve("gse.lock"), new byte[0]);
    }

    private static void materialize(String kind, Path directory)
            throws IOException {
        String inventory = resource("fixture-inventory.tsv");
        for (String line : inventory.lines().toList()) {
            if (line.isBlank() || line.startsWith("#")) {
                continue;
            }
            String[] columns = line.split("\\t");
            if (columns[0].equals(kind)) {
                Files.write(directory.resolve(columns[1]),
                        HexFormat.of().parseHex(resource(columns[3]).replaceAll("\\s", "")));
            }
        }
    }

    private static String resource(String name) throws IOException {
        try (InputStream input = V43DerivedFormatPhase2Test.class
                .getResourceAsStream(FIXTURE_ROOT + name)) {
            if (input == null) {
                throw new IOException("missing fixture: " + name);
            }
            return new String(input.readAllBytes(), StandardCharsets.US_ASCII);
        }
    }

    private static Path firstComponent(Path directory) throws IOException {
        try (var members = Files.list(directory)) {
            return members.filter(path -> path.getFileName().toString()
                            .startsWith("gse-derived-index-"))
                    .sorted().findFirst().orElseThrow();
        }
    }

    private static void flipMiddle(Path path) throws IOException {
        byte[] bytes = Files.readAllBytes(path);
        bytes[bytes.length / 2] ^= 1;
        Files.write(path, bytes);
    }

    private static void replaceAscii(byte[] bytes, String before, String after) {
        byte[] source = before.getBytes(StandardCharsets.US_ASCII);
        byte[] replacement = after.getBytes(StandardCharsets.US_ASCII);
        assertEquals(source.length, replacement.length);
        int offset = indexOf(bytes, source);
        assertNotEquals(-1, offset);
        System.arraycopy(replacement, 0, bytes, offset, replacement.length);
    }

    private static int indexOf(byte[] bytes, byte[] expected) {
        outer: for (int offset = 0; offset <= bytes.length - expected.length;
                offset++) {
            for (int index = 0; index < expected.length; index++) {
                if (bytes[offset + index] != expected[index]) {
                    continue outer;
                }
            }
            return offset;
        }
        return -1;
    }

    private static void resignCatalog(byte[] bytes) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        digest.update(CATALOG_DOMAIN);
        digest.update(bytes, 0, bytes.length - 36);
        System.arraycopy(digest.digest(), 0, bytes, bytes.length - 36, 32);
        rewriteCrc(bytes);
    }

    private static void rewriteCrc(byte[] bytes) {
        CRC32C crc = new CRC32C();
        crc.update(bytes, 0, bytes.length - 4);
        ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN)
                .putInt(bytes.length - 4, (int) crc.getValue());
    }

    private static Map<String, String> directoryDigests(Path directory)
            throws Exception {
        Map<String, String> result = new HashMap<>();
        try (var members = Files.list(directory)) {
            for (Path member : members.sorted().toList()) {
                result.put(member.getFileName().toString(), HexFormat.of().formatHex(
                        MessageDigest.getInstance("SHA-256")
                                .digest(Files.readAllBytes(member))));
            }
        }
        return result;
    }

    private record Document(int id, String body) {
    }

    private record FixtureDocument(
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
            return "v43-phase2-codec";
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
        public Integer decodeKey(byte[] bytes) {
            return ByteBuffer.wrap(bytes).getInt();
        }

        @Override
        public byte[] encodeDocument(Document document) {
            byte[] body = document.body().getBytes(java.nio.charset.StandardCharsets.UTF_8);
            return ByteBuffer.allocate(8 + body.length)
                    .putInt(document.id()).putInt(body.length).put(body).array();
        }

        @Override
        public Document decodeDocument(byte[] bytes) {
            ByteBuffer buffer = ByteBuffer.wrap(bytes);
            int id = buffer.getInt();
            byte[] body = new byte[buffer.getInt()];
            buffer.get(body);
            return new Document(id,
                    new String(body, java.nio.charset.StandardCharsets.UTF_8));
        }
    }

    private static final class FixtureCodec
            implements DurableCodec<Integer, FixtureDocument> {
        @Override
        public String codecId() {
            return "v43-fixture-codec";
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
        public Integer decodeKey(byte[] bytes) {
            return ByteBuffer.wrap(bytes).getInt();
        }

        @Override
        public byte[] encodeDocument(FixtureDocument document) {
            throw new UnsupportedOperationException("empty physical fixture");
        }

        @Override
        public FixtureDocument decodeDocument(byte[] bytes) {
            throw new UnsupportedOperationException("empty physical fixture");
        }
    }
}
