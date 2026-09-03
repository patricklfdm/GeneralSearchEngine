package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Modifier;
import java.nio.file.Path;
import java.util.List;
import java.util.OptionalLong;
import io.github.patricklfdm.generalsearch.durability.DurableOperationException;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationFinding;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationReport;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import org.junit.jupiter.api.Test;

class V41StructuralPublicApiTest {
    @Test
    void codecFreeOperationDescriptorsAreExact() throws Exception {
        assertTrue(Modifier.isFinal(DurableStorageOperations.class.getModifiers()));
        for (String method : List.of("verifyStore", "verifyBackup")) {
            var reflected = DurableStorageOperations.class.getMethod(
                    method, Path.class);
            assertTrue(Modifier.isPublic(reflected.getModifiers()));
            assertTrue(Modifier.isStatic(reflected.getModifiers()));
            assertEquals(DurableVerificationReport.class,
                    reflected.getReturnType());
        }
    }

    @Test
    void immutableReportRecordComponentsRemainFrozen() {
        assertArrayEquals(new Class<?>[]{String.class, String.class, String.class},
                componentTypes(DurableVerificationFinding.class));
        assertArrayEquals(new Class<?>[]{
                Path.class,
                DurableVerificationStatus.class,
                List.class,
                OptionalLong.class,
                long.class
        }, componentTypes(DurableVerificationReport.class));
        assertArrayEquals(new String[]{
                "directory", "status", "findings", "sequence",
                "authoritativeBytes"
        }, componentNames(DurableVerificationReport.class));
    }

    @Test
    void statusAndOperationalFailureFamiliesRemainStable() {
        assertArrayEquals(new DurableVerificationStatus[]{
                DurableVerificationStatus.VALID,
                DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS,
                DurableVerificationStatus.INCOMPATIBLE,
                DurableVerificationStatus.INCOMPLETE,
                DurableVerificationStatus.CORRUPT,
                DurableVerificationStatus.UNSUPPORTED
        }, DurableVerificationStatus.values());
        assertArrayEquals(new DurableOperationException.Reason[]{
                DurableOperationException.Reason.STORAGE_IN_USE,
                DurableOperationException.Reason.SOURCE_INVALID,
                DurableOperationException.Reason.BACKUP_INVALID,
                DurableOperationException.Reason.IDENTITY_MISMATCH,
                DurableOperationException.Reason.TARGET_EXISTS,
                DurableOperationException.Reason.TARGET_INVALID,
                DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                DurableOperationException.Reason.UNSUPPORTED_FORMAT,
                DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM,
                DurableOperationException.Reason.CAPACITY_EXCEEDED,
                DurableOperationException.Reason.IO_FAILURE,
                DurableOperationException.Reason.CLOSED
        }, DurableOperationException.Reason.values());
    }

    private static Class<?>[] componentTypes(Class<?> type) {
        return java.util.Arrays.stream(type.getRecordComponents())
                .map(java.lang.reflect.RecordComponent::getType)
                .toArray(Class<?>[]::new);
    }

    private static String[] componentNames(Class<?> type) {
        return java.util.Arrays.stream(type.getRecordComponents())
                .map(java.lang.reflect.RecordComponent::getName)
                .toArray(String[]::new);
    }
}
