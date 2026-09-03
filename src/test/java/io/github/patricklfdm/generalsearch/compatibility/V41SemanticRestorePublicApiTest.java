package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import io.github.patricklfdm.generalsearch.durability.DurableRestoreResult;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationReport;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import org.junit.jupiter.api.Test;

/** Exact public descriptor gate for the frozen Phase 4 typed operation surface. */
class V41SemanticRestorePublicApiTest {
    @Test
    void builderDescriptorsMatchTheFrozenContract() throws Exception {
        Method verify = SearchEngineBuilder.class.getMethod(
                "verifyDurableBackup", Path.class,
                DurableVerificationConfig.class);
        Method restore = SearchEngineBuilder.class.getMethod(
                "restoreDurableBackup", Path.class, DurableStorageConfig.class);
        assertEquals(DurableSemanticVerificationReport.class,
                verify.getReturnType());
        assertEquals(DurableRestoreResult.class, restore.getReturnType());
        assertTrue(Modifier.isPublic(verify.getModifiers()));
        assertTrue(Modifier.isPublic(restore.getModifiers()));
    }

    @Test
    void recordsAndStatusOrderRemainFrozen() {
        assertEquals(List.of("storageIdentity", "schemaIdentity", "codec",
                        "codecVersion", "maxEncodedKeyBytes",
                        "maxEncodedDocumentBytes", "maxDocuments"),
                components(DurableVerificationConfig.class));
        assertEquals(List.of("structuralReport", "status", "findings",
                        "documentCount"),
                components(DurableSemanticVerificationReport.class));
        assertEquals(List.of("targetDirectory", "newHistory", "sourceHistory",
                        "sourceContentIdentity", "restoredSequence",
                        "authoritativeBytes"),
                components(DurableRestoreResult.class));
        assertArrayEquals(new DurableSemanticVerificationStatus[]{
                DurableSemanticVerificationStatus.SEMANTICALLY_VALID,
                DurableSemanticVerificationStatus.IDENTITY_MISMATCH,
                DurableSemanticVerificationStatus.DECODE_FAILURE,
                DurableSemanticVerificationStatus.STATE_MISMATCH
        }, DurableSemanticVerificationStatus.values());
    }

    private static List<String> components(Class<?> type) {
        return Arrays.stream(type.getRecordComponents())
                .map(component -> component.getName()).toList();
    }
}
