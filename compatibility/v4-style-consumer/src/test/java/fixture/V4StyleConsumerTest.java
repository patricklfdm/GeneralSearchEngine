package fixture;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableBackupResult;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupScope;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.RecoverySource;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V4StyleConsumerTest {
    @TempDir
    Path temporary;

    @Test
    void executesDurableRoundTripThroughPublishedApiOnly() {
        Path directory = temporary.resolve("round-trip");
        try (DurableSearchEngine<Integer, DurableDocument> engine =
                     V4StyleConsumer.open(directory)) {
            engine.addAll(List.of(
                    new DurableDocument(1, "alpha"),
                    new DurableDocument(2, "beta"))).join();
            engine.checkpoint().join();
            engine.update(new DurableDocument(2, "beta-updated")).join();
            assertEquals(2L, engine.currentSequence());
        }

        try (DurableSearchEngine<Integer, DurableDocument> reopened =
                     V4StyleConsumer.open(directory)) {
            assertEquals(2L, reopened.currentSequence());
            assertEquals(new DurableDocument(1, "alpha"), reopened.get(1));
            assertEquals(
                    new DurableDocument(2, "beta-updated"), reopened.get(2));
            assertEquals(
                    RecoverySource.CHECKPOINT_AND_WAL,
                    reopened.durabilityMetrics().recoverySource());
        }
    }

    @Test
    void executesOperationalSafetyRoundTripThroughPublishedApiOnly() {
        Path source = temporary.resolve("operational-source");
        Path backup = temporary.resolve("operational-backup");
        Path restored = temporary.resolve("operational-restored");

        var backupResult = runBackup(source, backup);
        assertEquals(1L, backupResult.sequence());
        assertEquals(3, backupResult.memberCount());
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyBackup(backup).status());

        var semantic = V4StyleConsumer.builder().verifyDurableBackup(
                backup, V4StyleConsumer.verificationConfig());
        assertEquals(DurableSemanticVerificationStatus.SEMANTICALLY_VALID,
                semantic.status());
        assertEquals(2L, semantic.documentCount());

        var restoreResult = V4StyleConsumer.builder().restoreDurableBackup(
                backup,
                V4StyleConsumer.config(
                        restored, V4StyleConsumer.SCHEMA_IDENTITY));
        assertEquals(backupResult.sourceHistory(), restoreResult.sourceHistory());
        assertEquals(backupResult.contentIdentity(),
                restoreResult.sourceContentIdentity());
        assertNotEquals(restoreResult.sourceHistory(), restoreResult.newHistory());
        assertEquals(1L, restoreResult.restoredSequence());

        try (DurableSearchEngine<Integer, DurableDocument> reopened =
                     V4StyleConsumer.open(restored)) {
            assertEquals(new DurableDocument(1, "alpha"), reopened.get(1));
            assertEquals(new DurableDocument(2, "beta"), reopened.get(2));
            reopened.update(new DurableDocument(2, "beta-restored")).join();
            reopened.checkpoint().join();
            assertEquals(2L, reopened.currentSequence());
        }

        try (DurableSearchEngine<Integer, DurableDocument> reopenedAgain =
                     V4StyleConsumer.open(restored)) {
            assertEquals(2L, reopenedAgain.currentSequence());
            assertEquals(
                    new DurableDocument(2, "beta-restored"),
                    reopenedAgain.get(2));
        }

        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyStore(restored).status());
        var cleanup = DurableStorageOperations.planCleanup(
                new DurableCleanupRequest(
                        restored, DurableCleanupScope.LIVE_STORE));
        assertTrue(cleanup.deleteSet().isEmpty());
        assertTrue(DurableStorageOperations.applyCleanup(cleanup)
                .deletedMembers().isEmpty());
    }

    @Test
    void opensEveryImmutablePositiveFormatFixture() throws IOException {
        assertFixture("fresh", RecoverySource.FRESH, 0L, List.of());
        assertFixture(
                "wal-only", RecoverySource.WAL_ONLY, 1L,
                List.of(new DurableDocument(7, "alpha")));
        assertFixture(
                "checkpoint-only", RecoverySource.CHECKPOINT_ONLY, 1L,
                List.of(new DurableDocument(7, "alpha")));
        assertFixture(
                "checkpoint-wal", RecoverySource.CHECKPOINT_AND_WAL, 2L,
                List.of(
                        new DurableDocument(7, "alpha"),
                        new DurableDocument(8, "beta")));
        assertFixture(
                "incomplete-tail", RecoverySource.WAL_ONLY, 1L,
                List.of(new DurableDocument(7, "alpha")));
    }

    @Test
    void rejectsImmutableCorruptionFixture() throws IOException {
        Path directory = materialize("corruption");
        DurabilityException failure = assertThrows(
                DurabilityException.class,
                () -> V4StyleConsumer.open(directory));
        assertEquals(DurabilityException.Reason.CORRUPT_WAL, failure.reason());
    }

    @Test
    void rejectsMismatchedPersistedIdentity() {
        Path directory = temporary.resolve("identity-mismatch");
        try (DurableSearchEngine<Integer, DurableDocument> engine =
                     V4StyleConsumer.open(directory)) {
            engine.add(new DurableDocument(1, "alpha")).join();
        }

        DurabilityException failure = assertThrows(
                DurabilityException.class,
                () -> SearchEngine.builder(
                                DurableDocument.class, V4StyleConsumer.ID)
                        .field(V4StyleConsumer.BODY)
                        .buildDurable(V4StyleConsumer.config(
                                directory, "different-schema-v1")));
        assertEquals(
                DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                failure.reason());
    }

    @Test
    void rejectsUnsupportedCustomStartupIndexBeforeCreatingStorage() {
        Path directory = temporary.resolve("custom-index");
        IndexDefinition<DurableDocument> unsupported = new IndexDefinition<>() {
            @Override
            public io.github.patricklfdm.generalsearch.schema.Field<
                    DurableDocument, ?> field() {
                return V4StyleConsumer.BODY;
            }

            @Override
            public IndexSnapshot<DurableDocument> createEmpty() {
                return null;
            }
        };

        DurabilityException failure = assertThrows(
                DurabilityException.class,
                () -> SearchEngine.builder(
                                DurableDocument.class, V4StyleConsumer.ID)
                        .index(unsupported)
                        .buildDurable(V4StyleConsumer.config(
                                directory, V4StyleConsumer.SCHEMA_IDENTITY)));
        assertEquals(
                DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                failure.reason());
        assertFalse(Files.exists(directory));
    }

    private void assertFixture(
            String name,
            RecoverySource expectedSource,
            long expectedSequence,
            List<DurableDocument> expectedDocuments
    ) throws IOException {
        Path directory = materialize(name);
        try (DurableSearchEngine<Integer, DurableDocument> engine =
                     V4StyleConsumer.open(directory)) {
            assertEquals(expectedSource, engine.durabilityMetrics().recoverySource());
            assertEquals(expectedSequence, engine.currentSequence());
            for (DurableDocument document : expectedDocuments) {
                assertEquals(document, engine.get(document.id()));
            }
            assertNull(engine.get(999));
        }
    }

    private static DurableBackupResult runBackup(Path source, Path backup) {
        try (DurableSearchEngine<Integer, DurableDocument> engine =
                     V4StyleConsumer.open(source)) {
            engine.addAll(List.of(
                    new DurableDocument(1, "alpha"),
                    new DurableDocument(2, "beta"))).join();
            return engine.backup(new DurableBackupRequest(
                    backup, 64L * 1024 * 1024)).join();
        }
    }

    private Path materialize(String requested) throws IOException {
        Path directory = temporary.resolve(requested);
        Files.createDirectory(directory);
        for (FixtureMember member : fixtures().getOrDefault(
                requested, List.of())) {
            if (member.fileName().equals("-")) {
                continue;
            }
            byte[] bytes = Base64.getDecoder().decode(member.base64());
            assertEquals(member.sha256(), sha256(bytes));
            Files.write(directory.resolve(member.fileName()), bytes);
        }
        return directory;
    }

    private static Map<String, List<FixtureMember>> fixtures() throws IOException {
        Map<String, List<FixtureMember>> fixtures = new TreeMap<>();
        try (InputStream input = V4StyleConsumerTest.class.getResourceAsStream(
                "/io/github/patricklfdm/generalsearch/durability/"
                        + "v4-format-1.0-fixtures.tsv")) {
            if (input == null) {
                throw new IOException("format fixture resource is missing");
            }
            String text = new String(input.readAllBytes(), StandardCharsets.UTF_8);
            for (String line : text.lines().toList()) {
                if (line.isBlank() || line.startsWith("#")) {
                    continue;
                }
                String[] fields = line.split("\\t", -1);
                if (fields.length != 4) {
                    throw new IOException("invalid format fixture row");
                }
                fixtures.computeIfAbsent(fields[0], ignored -> new ArrayList<>())
                        .add(new FixtureMember(fields[1], fields[2], fields[3]));
            }
        }
        return fixtures;
    }

    private static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private record FixtureMember(String fileName, String sha256, String base64) {
    }
}
