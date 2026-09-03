package io.github.patricklfdm.generalsearch.durability;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.OptionalLong;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V41StructuralVerificationTest {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final int FRAME_MAGIC = 0x47534546;

    @Test
    void reportValuesNormalizeAndEnforceCanonicalFindings(@TempDir Path directory) {
        DurableVerificationFinding first = new DurableVerificationFinding(
                "A_CODE", "a", "first");
        DurableVerificationFinding second = new DurableVerificationFinding(
                "B_CODE", "b", "second");
        DurableVerificationReport report = new DurableVerificationReport(
                directory.resolve("child/.."),
                DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS,
                List.of(first, second), OptionalLong.of(7), 19);

        assertEquals(directory.toAbsolutePath().normalize(), report.directory());
        assertEquals(List.of(first, second), report.findings());
        assertThrows(UnsupportedOperationException.class,
                () -> report.findings().add(first));
        assertThrows(IllegalArgumentException.class, () ->
                new DurableVerificationReport(directory,
                        DurableVerificationStatus.CORRUPT,
                        List.of(second, first), OptionalLong.empty(), 0));
        assertThrows(IllegalArgumentException.class, () ->
                new DurableVerificationFinding("bad-code", "a", "detail"));
    }

    @Test
    void closedFreshAndCheckpointStoresVerifyWithoutMutation(@TempDir Path directory)
            throws Exception {
        DurableStorageConfig<Integer, Document> storage = config(directory);
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID).field(BODY).buildDurable(storage)) {
            DurableOperationException locked = assertThrows(
                    DurableOperationException.class,
                    () -> DurableStorageOperations.verifyStore(directory));
            assertEquals(DurableOperationException.Reason.STORAGE_IN_USE,
                    locked.reason());
            engine.add(new Document(1, "one")).join();
            engine.add(new Document(2, "two")).join();
            engine.checkpoint().join();
        }

        Map<String, byte[]> before = directoryDigests(directory);
        DurableVerificationReport report =
                DurableStorageOperations.verifyStore(directory);
        assertEquals(DurableVerificationStatus.VALID, report.status());
        assertEquals(OptionalLong.of(2), report.sequence());
        assertTrue(report.authoritativeBytes() > 0);
        assertTrue(report.findings().isEmpty());
        assertDigestMapEquals(before, directoryDigests(directory));
    }

    @Test
    void publishedV4ByteFixturesMatchIndependentExpectedClassifications(
            @TempDir Path temporary
    ) throws Exception {
        Map<String, DurableVerificationStatus> statuses = Map.of(
                "wal-only", DurableVerificationStatus.VALID,
                "checkpoint-only", DurableVerificationStatus.VALID,
                "checkpoint-wal", DurableVerificationStatus.VALID,
                "incomplete-tail",
                        DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS,
                "corruption", DurableVerificationStatus.CORRUPT);
        Map<String, Long> sequences = Map.of(
                "wal-only", 1L,
                "checkpoint-only", 1L,
                "checkpoint-wal", 2L,
                "incomplete-tail", 1L);
        Map<String, List<FixtureMember>> fixtures = loadV4Fixtures();

        for (Map.Entry<String, DurableVerificationStatus> expected
                : statuses.entrySet()) {
            Path directory = Files.createDirectory(
                    temporary.resolve(expected.getKey()));
            for (FixtureMember member : fixtures.get(expected.getKey())) {
                Files.write(directory.resolve(member.name()), member.bytes());
            }
            DurableVerificationReport report =
                    DurableStorageOperations.verifyStore(directory);
            assertEquals(expected.getValue(), report.status(),
                    expected.getKey() + ": " + report.findings());
            if (sequences.containsKey(expected.getKey())) {
                assertEquals(OptionalLong.of(sequences.get(expected.getKey())),
                        report.sequence(), expected.getKey());
            }
        }
    }

    @Test
    void incompleteFinalWalTailIsReportedButNeverTruncated(@TempDir Path directory)
            throws Exception {
        createWalOnlyStore(directory, 1);
        Path wal = onlyWal(directory);
        byte[] prefix = ByteBuffer.allocate(8).order(ByteOrder.BIG_ENDIAN)
                .putInt(FRAME_MAGIC).putShort((short) 1).putShort((short) 0)
                .array();
        Files.write(wal, prefix, StandardOpenOption.APPEND);
        long bytes = Files.size(wal);

        DurableVerificationReport report =
                DurableStorageOperations.verifyStore(directory);

        assertEquals(DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS,
                report.status());
        assertEquals(OptionalLong.of(1), report.sequence());
        assertTrue(report.findings().stream().anyMatch(finding ->
                finding.code().equals("INCOMPLETE_WAL_TAIL")));
        assertEquals(bytes, Files.size(wal));
    }

    @Test
    void committedWalCorruptionAndUnknownMembersFailClosed(@TempDir Path directory)
            throws Exception {
        createWalOnlyStore(directory, 1);
        Path wal = onlyWal(directory);
        byte[] bytes = Files.readAllBytes(wal);
        bytes[bytes.length - 1] ^= 1;
        Files.write(wal, bytes);
        Files.writeString(directory.resolve("operator-note"), "unknown");

        DurableVerificationReport report =
                DurableStorageOperations.verifyStore(directory);

        assertEquals(DurableVerificationStatus.CORRUPT, report.status());
        assertTrue(report.findings().stream().anyMatch(finding ->
                finding.code().equals("WAL_FRAME_CHECKSUM")));
        assertTrue(report.findings().stream().anyMatch(finding ->
                finding.code().equals("UNKNOWN_STORE_MEMBER")));
        assertTrue(Files.exists(directory.resolve("operator-note")));
    }

    @Test
    void recognizedStagingRemnantIsReportedOnlyAfterAuthorityValidates(
            @TempDir Path directory
    ) throws Exception {
        createWalOnlyStore(directory, 1);
        Path staging = directory.resolve("gse-metadata.staging");
        Files.writeString(staging, "non-authoritative-remnant");

        DurableVerificationReport report =
                DurableStorageOperations.verifyStore(directory);

        assertEquals(DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS,
                report.status());
        assertTrue(report.findings().stream().anyMatch(finding ->
                finding.code().equals("SAFE_STAGING_REMNANT")
                        && finding.member().equals("gse-metadata.staging")));
        assertTrue(Files.exists(staging));
    }

    @Test
    void absentOwnershipFileReportsIncompleteWithoutCreatingIt(
            @TempDir Path directory
    ) throws Exception {
        createWalOnlyStore(directory, 0);
        Files.delete(directory.resolve("gse.lock"));

        DurableVerificationReport report =
                DurableStorageOperations.verifyStore(directory);

        assertEquals(DurableVerificationStatus.INCOMPLETE, report.status());
        assertFalse(Files.exists(directory.resolve("gse.lock")));
    }

    @Test
    void corruptPresentWalIsNotHiddenByMissingMetadata(@TempDir Path directory)
            throws Exception {
        createWalOnlyStore(directory, 1);
        Path wal = onlyWal(directory);
        byte[] bytes = Files.readAllBytes(wal);
        bytes[bytes.length - 1] ^= 1;
        Files.write(wal, bytes);
        Files.delete(directory.resolve("gse-metadata"));

        DurableVerificationReport report =
                DurableStorageOperations.verifyStore(directory);

        assertEquals(DurableVerificationStatus.CORRUPT, report.status());
        assertTrue(report.findings().stream().anyMatch(finding ->
                finding.code().equals("MISSING_METADATA")));
        assertTrue(report.findings().stream().anyMatch(finding ->
                finding.code().equals("WAL_FRAME_CHECKSUM")));
    }

    @Test
    void exactImmutableBackupFixtureVerifiesWithoutCodecOrMutation(
            @TempDir Path directory
    ) throws Exception {
        materializeBackupFixture(directory);
        Map<String, byte[]> before = directoryDigests(directory);

        DurableVerificationReport report =
                DurableStorageOperations.verifyBackup(directory);

        assertEquals(DurableVerificationStatus.VALID, report.status());
        assertEquals(OptionalLong.of(7), report.sequence());
        assertEquals(3, before.size());
        assertTrue(report.authoritativeBytes() > 0);
        assertTrue(report.findings().isEmpty());
        assertDigestMapEquals(before, directoryDigests(directory));
    }

    @Test
    void backupInventoryAndIntegrityClassifyDeterministically(
            @TempDir Path temporary
    ) throws Exception {
        Path missing = Files.createDirectory(temporary.resolve("missing"));
        materializeBackupFixture(missing);
        Files.delete(missing.resolve("gse-backup-manifest"));
        assertEquals(DurableVerificationStatus.INCOMPLETE,
                DurableStorageOperations.verifyBackup(missing).status());

        Path corrupt = Files.createDirectory(temporary.resolve("corrupt"));
        materializeBackupFixture(corrupt);
        Path checkpoint = corrupt.resolve("gse-backup-checkpoint");
        byte[] bytes = Files.readAllBytes(checkpoint);
        bytes[bytes.length / 2] ^= 1;
        Files.write(checkpoint, bytes);
        Files.writeString(corrupt.resolve("extra"), "extra");
        DurableVerificationReport corruptReport =
                DurableStorageOperations.verifyBackup(corrupt);
        assertEquals(DurableVerificationStatus.CORRUPT,
                corruptReport.status());
        assertTrue(corruptReport.findings().stream().anyMatch(finding ->
                finding.code().equals("CHECKSUM_MISMATCH")),
                corruptReport.findings().toString());
        assertTrue(corruptReport.findings().stream().anyMatch(finding ->
                finding.code().equals("UNKNOWN_BACKUP_MEMBER")));
    }

    @Test
    void intactUnknownMajorAndSupportedMajorUnknownMinorRemainDistinct(
            @TempDir Path temporary
    ) throws Exception {
        Path unsupported = Files.createDirectory(temporary.resolve("unsupported"));
        materializeBackupFixture(unsupported);
        rewriteManifestVersion(unsupported.resolve("gse-backup-manifest"), 2, 0);
        assertEquals(DurableVerificationStatus.UNSUPPORTED,
                DurableStorageOperations.verifyBackup(unsupported).status());

        Path incompatible = Files.createDirectory(
                temporary.resolve("incompatible"));
        materializeBackupFixture(incompatible);
        rewriteManifestVersion(incompatible.resolve("gse-backup-manifest"), 1, 1);
        assertEquals(DurableVerificationStatus.INCOMPATIBLE,
                DurableStorageOperations.verifyBackup(incompatible).status());
    }

    private static void createWalOnlyStore(Path directory, int mutations) {
        DurableStorageConfig<Integer, Document> storage = config(directory);
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID).field(BODY).buildDurable(storage)) {
            for (int index = 1; index <= mutations; index++) {
                engine.add(new Document(index, "body-" + index)).join();
            }
        }
    }

    private static DurableStorageConfig<Integer, Document> config(Path directory) {
        return DurableStorageConfig.builder(directory, new DocumentCodec())
                .storageIdentity("v41-structural-store")
                .schemaIdentity("v41-structural-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private static Path onlyWal(Path directory) throws IOException {
        try (var entries = Files.list(directory)) {
            return entries.filter(path -> path.getFileName().toString()
                            .matches("gse-wal-.*\\.log"))
                    .findFirst().orElseThrow();
        }
    }

    private static void materializeBackupFixture(Path directory) throws IOException {
        for (String member : List.of(
                "gse-backup-metadata",
                "gse-backup-checkpoint",
                "gse-backup-manifest")) {
            String resource = "/compatibility/v41-backup-v1/" + member + ".hex";
            try (InputStream input = V41StructuralVerificationTest.class
                    .getResourceAsStream(resource)) {
                if (input == null) {
                    throw new IOException("missing fixture: " + resource);
                }
                String hex = new String(input.readAllBytes(), StandardCharsets.US_ASCII);
                Files.write(directory.resolve(member), java.util.HexFormat.of()
                        .parseHex(hex.replaceAll("\\s", "")));
            }
        }
    }

    private static Map<String, List<FixtureMember>> loadV4Fixtures()
            throws IOException {
        String resource = "/io/github/patricklfdm/generalsearch/durability/"
                + "v4-format-1.0-fixtures.tsv";
        String text;
        try (InputStream input = V41StructuralVerificationTest.class
                .getResourceAsStream(resource)) {
            if (input == null) {
                throw new IOException("missing fixture: " + resource);
            }
            text = new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
        Map<String, List<FixtureMember>> result = new HashMap<>();
        for (String line : text.lines().toList()) {
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            String[] fields = line.split("\\t", -1);
            if (fields[1].equals("-")) {
                continue;
            }
            byte[] bytes = Base64.getDecoder().decode(fields[3]);
            assertEquals(fields[2], HexFormat.of().formatHex(digest(bytes)),
                    fields[0] + "/" + fields[1]);
            result.computeIfAbsent(fields[0], ignored -> new java.util.ArrayList<>())
                    .add(new FixtureMember(fields[1], bytes));
        }
        return result;
    }

    private static void rewriteManifestVersion(
            Path manifest,
            int major,
            int minor
    ) throws IOException {
        byte[] bytes = Files.readAllBytes(manifest);
        ByteBuffer buffer = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN);
        buffer.putShort(8, (short) major);
        buffer.putShort(10, (short) minor);
        CRC32C crc = new CRC32C();
        crc.update(bytes, 0, bytes.length - Integer.BYTES);
        buffer.putInt(bytes.length - Integer.BYTES, (int) crc.getValue());
        Files.write(manifest, bytes);
    }

    private static Map<String, byte[]> directoryDigests(Path directory)
            throws IOException {
        Map<String, byte[]> result = new HashMap<>();
        try (var entries = Files.list(directory)) {
            for (Path path : entries.sorted(
                    Comparator.comparing(value -> value.getFileName().toString()))
                    .toList()) {
                result.put(path.getFileName().toString(),
                        digest(Files.readAllBytes(path)));
            }
        }
        return result;
    }

    private static void assertDigestMapEquals(
            Map<String, byte[]> expected,
            Map<String, byte[]> actual
    ) {
        assertEquals(expected.keySet(), actual.keySet());
        for (String name : expected.keySet()) {
            assertArrayEquals(expected.get(name), actual.get(name), name);
        }
    }

    private static byte[] digest(byte[] bytes) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(bytes);
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private record Document(int id, String body) {
    }

    private record FixtureMember(String name, byte[] bytes) {
        private FixtureMember {
            bytes = bytes.clone();
        }

        @Override
        public byte[] bytes() {
            return bytes.clone();
        }
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v41-structural-codec";
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
            byte[] body = document.body().getBytes(StandardCharsets.UTF_8);
            return ByteBuffer.allocate(Integer.BYTES * 2 + body.length)
                    .putInt(document.id()).putInt(body.length).put(body).array();
        }

        @Override
        public Document decodeDocument(byte[] bytes) {
            ByteBuffer buffer = ByteBuffer.wrap(bytes);
            int id = buffer.getInt();
            byte[] body = new byte[buffer.getInt()];
            buffer.get(body);
            return new Document(id, new String(body, StandardCharsets.UTF_8));
        }
    }
}
