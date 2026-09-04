package io.github.patricklfdm.generalsearch.durability;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
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
import java.security.NoSuchAlgorithmException;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.OptionalLong;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V42FormatInspectionPhase2Test {
    private static final String FIXTURE_ROOT = "/compatibility/v42-storage-v11/";
    private static final String PROFILE_DIGEST =
            "f5013976ba0c49b62a6a38ce8a6af4cf5f8acf53e24dcf9733d22382b1e5f50f";
    private static final byte[] PROFILE_DOMAIN =
            "gse-durable-format-profile-v1\0".getBytes(StandardCharsets.US_ASCII);
    private static final String CHECKPOINT =
            "gse-checkpoint-00000000000000000007-"
                    + "00112233445566778899aabbccddeeff.chk";
    private static final String WAL = "gse-wal-00000000000000000002.log";
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);

    @Test
    void publicFormatValuesReportsAndSelectorEnforceFrozenContract(
            @TempDir Path temporary
    ) {
        assertEquals(new DurableStorageFormat("gse-durable", 1, 0),
                DurableStorageFormat.V1_0);
        assertEquals(new DurableStorageFormat("gse-durable", 1, 1),
                DurableStorageFormat.V1_1);
        assertEquals(new DurableBackupFormat("gse-backup", 1, 1),
                DurableBackupFormat.V1_1);
        assertThrows(IllegalArgumentException.class,
                () -> new DurableStorageFormat("GSE", 1, 0));
        assertThrows(IllegalArgumentException.class,
                () -> new DurableStorageFormat("gse-durable", -1, 0));

        DurableVerificationReport structural = new DurableVerificationReport(
                temporary, DurableVerificationStatus.VALID, List.of(),
                OptionalLong.empty(), 0);
        DurableStoreFormatReport report = new DurableStoreFormatReport(
                structural, Optional.of(DurableStorageFormat.V1_1),
                Optional.of(PROFILE_DIGEST));
        assertEquals(PROFILE_DIGEST, report.profileDigest().orElseThrow());
        assertThrows(IllegalArgumentException.class, () ->
                new DurableStoreFormatReport(structural, Optional.empty(),
                        Optional.of(PROFILE_DIGEST.toUpperCase())));

        Path unopened = temporary.resolve("must-not-be-created");
        DurableStorageConfig<Integer, Document> defaultConfig =
                DurableStorageConfig.builder(unopened, new DocumentCodec())
                        .storageIdentity("v42-phase2-selector")
                        .schemaIdentity("v42-phase2-schema")
                        .build();
        assertEquals(DurableStorageFormat.V1_0, defaultConfig.format());
        DurableStorageConfig<Integer, Document> selected =
                DurableStorageConfig.builder(unopened, new DocumentCodec())
                        .storageIdentity("v42-phase2-selector")
                        .schemaIdentity("v42-phase2-schema")
                        .format(DurableStorageFormat.V1_1)
                        .build();
        assertEquals(DurableStorageFormat.V1_1, selected.format());
        try (var ignored = SearchEngine.builder(Document.class, ID)
                .buildDurable(selected)) {
            // Phase 3 activates the selector frozen and rejected by Phase 2.
        }
        assertTrue(Files.isDirectory(unopened));
        assertEquals(Optional.of(DurableStorageFormat.V1_1),
                DurableStorageOperations.inspectStoreFormat(unopened)
                        .declaredFormat());
    }

    @Test
    void exactV11LiveAndBackupFixturesInspectWithoutMutation(
            @TempDir Path temporary
    ) throws Exception {
        Path live = Files.createDirectory(temporary.resolve("live"));
        Path backup = Files.createDirectory(temporary.resolve("backup"));
        materializeLive(live);
        materializeBackup(backup);
        Map<String, byte[]> liveBefore = directoryDigests(live);
        Map<String, byte[]> backupBefore = directoryDigests(backup);

        DurableStoreFormatReport store =
                DurableStorageOperations.inspectStoreFormat(live);
        DurableBackupFormatReport bundle =
                DurableStorageOperations.inspectBackupFormat(backup);

        assertEquals(DurableVerificationStatus.VALID,
                store.structuralReport().status());
        assertEquals(OptionalLong.of(7), store.structuralReport().sequence());
        assertEquals(Optional.of(DurableStorageFormat.V1_1),
                store.declaredFormat());
        assertEquals(Optional.of(PROFILE_DIGEST), store.profileDigest());
        assertEquals(DurableVerificationStatus.VALID,
                bundle.structuralReport().status());
        assertEquals(OptionalLong.of(7), bundle.structuralReport().sequence());
        assertEquals(Optional.of(DurableBackupFormat.V1_1),
                bundle.declaredFormat());
        assertEquals(Optional.of(DurableStorageFormat.V1_1),
                bundle.sourceFormat());
        assertEquals(Optional.of(PROFILE_DIGEST), bundle.profileDigest());
        assertDigestMapEquals(liveBefore, directoryDigests(live));
        assertDigestMapEquals(backupBefore, directoryDigests(backup));
    }

    @Test
    void intactUnknownVersionsRemainDeclaredAndClassified(
            @TempDir Path temporary
    ) throws Exception {
        Path higherMinor = Files.createDirectory(temporary.resolve("minor"));
        materializeLive(higherMinor);
        rewriteVersion(higherMinor.resolve("gse-metadata"), 1, 2);
        DurableStoreFormatReport minorReport =
                DurableStorageOperations.inspectStoreFormat(higherMinor);
        assertEquals(DurableVerificationStatus.INCOMPATIBLE,
                minorReport.structuralReport().status());
        assertEquals(Optional.of(new DurableStorageFormat("gse-durable", 1, 2)),
                minorReport.declaredFormat());
        assertTrue(minorReport.profileDigest().isEmpty());

        Path higherMajor = Files.createDirectory(temporary.resolve("major"));
        materializeLive(higherMajor);
        rewriteVersion(higherMajor.resolve("gse-metadata"), 2, 1);
        DurableStoreFormatReport majorReport =
                DurableStorageOperations.inspectStoreFormat(higherMajor);
        assertEquals(DurableVerificationStatus.UNSUPPORTED,
                majorReport.structuralReport().status());
        assertEquals(Optional.of(new DurableStorageFormat("gse-durable", 2, 1)),
                majorReport.declaredFormat());

        Path corruptHeader = Files.createDirectory(temporary.resolve("corrupt"));
        materializeLive(corruptHeader);
        Path metadata = corruptHeader.resolve("gse-metadata");
        byte[] bytes = Files.readAllBytes(metadata);
        bytes[bytes.length - 1] ^= 1;
        Files.write(metadata, bytes);
        DurableStoreFormatReport corruptReport =
                DurableStorageOperations.inspectStoreFormat(corruptHeader);
        assertEquals(DurableVerificationStatus.CORRUPT,
                corruptReport.structuralReport().status());
        assertTrue(corruptReport.declaredFormat().isEmpty(),
                "a checksum-invalid header must not be represented as a declaration");
    }

    @Test
    void profileAndMemberBindingCorruptionFailClosed(
            @TempDir Path temporary
    ) throws Exception {
        Path unknownProfile = Files.createDirectory(temporary.resolve("profile"));
        materializeLive(unknownProfile);
        Path metadata = unknownProfile.resolve("gse-metadata");
        byte[] metadataBytes = Files.readAllBytes(metadata);
        ByteBuffer metadataReader = ByteBuffer.wrap(metadataBytes)
                .order(ByteOrder.BIG_ENDIAN);
        metadataReader.position(28);
        int familyBytes = metadataReader.getInt();
        metadataReader.position(metadataReader.position() + familyBytes);
        int profileBytes = metadataReader.getInt();
        int profileOffset = metadataReader.position();
        byte[] before = "canonical-documents-v1"
                .getBytes(StandardCharsets.US_ASCII);
        byte[] after = "canonical-documentt-v1"
                .getBytes(StandardCharsets.US_ASCII);
        int capabilityOffset = indexOf(metadataBytes, before, profileOffset,
                profileOffset + profileBytes);
        System.arraycopy(after, 0, metadataBytes, capabilityOffset, after.length);
        MessageDigest sha = sha256();
        sha.update(PROFILE_DOMAIN);
        sha.update(metadataBytes, profileOffset, profileBytes);
        byte[] changedDigest = sha.digest();
        System.arraycopy(changedDigest, 0, metadataBytes,
                profileOffset + profileBytes, changedDigest.length);
        rewriteCrc(metadataBytes);
        Files.write(metadata, metadataBytes);
        for (String member : List.of(CHECKPOINT, WAL)) {
            Path path = unknownProfile.resolve(member);
            byte[] bound = Files.readAllBytes(path);
            System.arraycopy(changedDigest, 0, bound, 28, changedDigest.length);
            rewriteCrc(bound);
            Files.write(path, bound);
        }
        byte[] checkpointBytes = Files.readAllBytes(
                unknownProfile.resolve(CHECKPOINT));
        int checkpointCrc = ByteBuffer.wrap(checkpointBytes)
                .order(ByteOrder.BIG_ENDIAN)
                .getInt(checkpointBytes.length - Integer.BYTES);
        Path checkpointManifest = unknownProfile.resolve(
                "gse-checkpoint-manifest");
        byte[] manifestBytes = Files.readAllBytes(checkpointManifest);
        System.arraycopy(changedDigest, 0, manifestBytes, 28,
                changedDigest.length);
        ByteBuffer.wrap(manifestBytes).order(ByteOrder.BIG_ENDIAN)
                .putInt(76, checkpointCrc);
        rewriteCrc(manifestBytes);
        Files.write(checkpointManifest, manifestBytes);

        DurableStoreFormatReport unknown =
                DurableStorageOperations.inspectStoreFormat(unknownProfile);
        assertEquals(DurableVerificationStatus.INCOMPATIBLE,
                unknown.structuralReport().status());
        assertTrue(unknown.structuralReport().findings().stream().anyMatch(finding ->
                finding.code().equals("INCOMPATIBLE_FORMAT_PROFILE")));
        assertEquals(Optional.of(HexFormat.of().formatHex(changedDigest)),
                unknown.profileDigest());

        Path mismatchedWal = Files.createDirectory(temporary.resolve("wal"));
        materializeLive(mismatchedWal);
        Path wal = mismatchedWal.resolve(WAL);
        byte[] walBytes = Files.readAllBytes(wal);
        walBytes[28] ^= 1;
        rewriteCrc(walBytes);
        Files.write(wal, walBytes);
        DurableVerificationReport mismatch =
                DurableStorageOperations.verifyStore(mismatchedWal);
        assertEquals(DurableVerificationStatus.CORRUPT, mismatch.status());
        assertTrue(mismatch.findings().stream().anyMatch(finding ->
                finding.code().equals("PROFILE_BINDING_MISMATCH")));

        Path mixedMinor = Files.createDirectory(temporary.resolve("mixed"));
        materializeLive(mixedMinor);
        Path mixedWal = mixedMinor.resolve(WAL);
        byte[] mixedBytes = Files.readAllBytes(mixedWal);
        ByteBuffer.wrap(mixedBytes).order(ByteOrder.BIG_ENDIAN)
                .putShort(10, (short) 0);
        Files.write(mixedWal, mixedBytes);
        DurableVerificationReport mixed =
                DurableStorageOperations.verifyStore(mixedMinor);
        assertEquals(DurableVerificationStatus.CORRUPT, mixed.status());
        assertTrue(mixed.findings().stream().anyMatch(finding ->
                finding.code().equals("MIXED_MINOR_VERSION")));
    }

    @Test
    void publishedV10StoresRemainExplicitlyInspectable(@TempDir Path directory)
            throws Exception {
        DurableStorageConfig<Integer, Document> storage =
                DurableStorageConfig.builder(directory, new DocumentCodec())
                        .storageIdentity("v42-phase2-v10")
                        .schemaIdentity("v42-phase2-schema")
                        .build();
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID).buildDurable(storage)) {
            engine.add(new Document(1)).join();
        }

        DurableStoreFormatReport report =
                DurableStorageOperations.inspectStoreFormat(directory);
        assertEquals(DurableVerificationStatus.VALID,
                report.structuralReport().status());
        assertEquals(Optional.of(DurableStorageFormat.V1_0),
                report.declaredFormat());
        assertTrue(report.profileDigest().isEmpty());
    }

    private static void materializeLive(Path directory) throws IOException {
        Files.write(directory.resolve("gse.lock"), new byte[0]);
        writeHex(directory.resolve("gse-metadata"), "gse-metadata.hex");
        writeHex(directory.resolve(CHECKPOINT), "gse-checkpoint.hex");
        writeHex(directory.resolve("gse-checkpoint-manifest"),
                "gse-checkpoint-manifest.hex");
        writeHex(directory.resolve(WAL), "gse-wal.hex");
    }

    private static void materializeBackup(Path directory) throws IOException {
        writeHex(directory.resolve("gse-backup-metadata"), "gse-metadata.hex");
        writeHex(directory.resolve("gse-backup-checkpoint"),
                "gse-checkpoint.hex");
        writeHex(directory.resolve("gse-backup-manifest"),
                "gse-backup-manifest.hex");
    }

    private static void writeHex(Path path, String resource) throws IOException {
        try (InputStream input = V42FormatInspectionPhase2Test.class
                .getResourceAsStream(FIXTURE_ROOT + resource)) {
            if (input == null) {
                throw new IOException("missing fixture: " + resource);
            }
            String hex = new String(input.readAllBytes(), StandardCharsets.US_ASCII);
            Files.write(path, HexFormat.of().parseHex(hex.replaceAll("\\s", "")));
        }
    }

    private static void rewriteVersion(Path path, int major, int minor)
            throws IOException {
        byte[] bytes = Files.readAllBytes(path);
        ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN)
                .putShort(8, (short) major)
                .putShort(10, (short) minor);
        rewriteCrc(bytes);
        Files.write(path, bytes);
    }

    private static void rewriteCrc(byte[] bytes) {
        CRC32C crc = new CRC32C();
        crc.update(bytes, 0, bytes.length - Integer.BYTES);
        ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN)
                .putInt(bytes.length - Integer.BYTES, (int) crc.getValue());
    }

    private static int indexOf(byte[] haystack, byte[] needle, int from, int to) {
        for (int offset = from; offset + needle.length <= to; offset++) {
            boolean match = true;
            for (int index = 0; index < needle.length; index++) {
                if (haystack[offset + index] != needle[index]) {
                    match = false;
                    break;
                }
            }
            if (match) {
                return offset;
            }
        }
        throw new AssertionError("fixture capability not found");
    }

    private static Map<String, byte[]> directoryDigests(Path directory)
            throws IOException {
        Map<String, byte[]> result = new HashMap<>();
        try (var entries = Files.list(directory)) {
            for (Path path : entries.sorted(
                    Comparator.comparing(value -> value.getFileName().toString()))
                    .toList()) {
                result.put(path.getFileName().toString(),
                        sha256().digest(Files.readAllBytes(path)));
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

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private record Document(int id) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v42-phase2-codec";
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
            return ByteBuffer.allocate(Integer.BYTES).putInt(document.id()).array();
        }

        @Override
        public Document decodeDocument(byte[] bytes) {
            return new Document(ByteBuffer.wrap(bytes).getInt());
        }
    }
}
