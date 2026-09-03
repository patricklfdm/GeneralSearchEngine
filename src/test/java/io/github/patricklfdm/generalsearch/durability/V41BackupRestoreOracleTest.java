package io.github.patricklfdm.generalsearch.durability;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class V41BackupRestoreOracleTest {
    private final V41BackupRestoreOracle oracle = new V41BackupRestoreOracle();

    @Test
    void exactCutExcludesLaterMutationAndHasStableContentIdentity() {
        V41BackupRestoreOracle.SourceState atB = source(7, Map.of(
                "doc-1", "alpha",
                "doc-2", "beta"));
        V41BackupRestoreOracle.Backup first = oracle.backup(atB);
        V41BackupRestoreOracle.Backup repeat = oracle.backup(atB);
        V41BackupRestoreOracle.SourceState later = atB.add("doc-3", "gamma");

        assertEquals(first.contentIdentity(), repeat.contentIdentity());
        assertArrayEquals(first.metadata(), repeat.metadata());
        assertArrayEquals(first.checkpoint(), repeat.checkpoint());
        assertEquals(7, first.captured().sequence());
        assertEquals(8, later.sequence());
        assertEquals(Map.of("doc-1", "alpha", "doc-2", "beta"),
                first.captured().documents());
    }

    @Test
    void restoreCreatesNewHistoryAndPreservesTheFullLogicalOracle() {
        V41BackupRestoreOracle.SourceState source = source(12, Map.of(
                "alpha", "red apple",
                "beta", "blue berry"));
        V41BackupRestoreOracle.Backup backup = oracle.backup(source);
        UUID restoredHistory = UUID.fromString("12345678-1234-4234-9234-123456789abc");

        V41BackupRestoreOracle.RestoredState restored = oracle.restore(
                backup, restoredHistory, "catalog", "product-v1", "utf8-json", 1);

        assertEquals(restoredHistory, restored.newHistory());
        assertNotEquals(source.history(), restored.newHistory());
        assertEquals(source.history(), restored.sourceHistory());
        assertEquals(source.sequence(), restored.sequence());
        assertEquals(source.nextDocId(), restored.nextDocId());
        assertEquals(source.documents(), restored.documents());
        assertEquals(source.durableIndexes(), restored.durableIndexes());
        assertEquals(backup.contentIdentity(), restored.sourceContentIdentity());
    }

    @Test
    void semanticIdentityMismatchAndSequenceExhaustionFailClosed() {
        V41BackupRestoreOracle.SourceState source = source(3, Map.of());
        V41BackupRestoreOracle.Backup backup = oracle.backup(source);
        UUID target = UUID.fromString("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");

        assertThrows(IllegalArgumentException.class, () -> oracle.restore(
                backup, target, "other", "product-v1", "utf8-json", 1));
        assertThrows(IllegalArgumentException.class, () -> oracle.restore(
                backup, source.history(), "catalog", "product-v1", "utf8-json", 1));

        V41BackupRestoreOracle.SourceState exhausted = new V41BackupRestoreOracle.SourceState(
                source.history(), "catalog", "product-v1", "utf8-json", 1,
                Long.MAX_VALUE, 0, Map.of(), List.of());
        assertThrows(IllegalStateException.class, () -> oracle.backup(exhausted));
    }

    private static V41BackupRestoreOracle.SourceState source(
            long sequence, Map<String, String> documents) {
        return new V41BackupRestoreOracle.SourceState(
                UUID.fromString("00000000-0000-4000-8000-000000000041"),
                "catalog",
                "product-v1",
                "utf8-json",
                1,
                sequence,
                100 + documents.size(),
                new LinkedHashMap<>(documents),
                List.of("price:range", "name:text"));
    }
}
