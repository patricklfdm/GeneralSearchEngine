package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import io.github.patricklfdm.generalsearch.durability.DurableBackupFormat;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableBackupResult;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import org.junit.jupiter.api.Test;

/** Exact public descriptor gate for the Phase 3 backup surface. */
class V41BackupPublicApiTest {
    @Test
    void backupMethodMatchesTheFrozenDefaultDescriptor() throws Exception {
        Method method = DurableSearchEngine.class.getMethod(
                "backup", DurableBackupRequest.class);
        assertEquals(CompletableFuture.class, method.getReturnType());
        assertTrue(method.isDefault());
        assertTrue(Modifier.isPublic(method.getModifiers()));
    }

    @Test
    void valueRecordsMatchTheFrozenComponents() {
        assertEquals(List.of("targetDirectory", "maxBundleBytes"),
                components(DurableBackupRequest.class));
        assertEquals(List.of("family", "major", "minor"),
                components(DurableBackupFormat.class));
        assertEquals(List.of("targetDirectory", "format", "contentIdentity",
                        "sourceHistory", "sequence", "memberCount", "totalBytes"),
                components(DurableBackupResult.class));
        assertEquals(new DurableBackupFormat("gse-backup", 1, 0),
                DurableBackupFormat.V1_0);
    }

    @Test
    void requestNormalizesItsPath() {
        Path expected = Path.of("backup").toAbsolutePath().normalize();
        assertEquals(expected, new DurableBackupRequest(
                Path.of(".", "backup"), 1).targetDirectory());
    }

    private static List<String> components(Class<?> type) {
        return List.of(type.getRecordComponents()).stream()
                .map(component -> component.getName())
                .toList();
    }
}
