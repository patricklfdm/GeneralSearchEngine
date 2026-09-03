package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupEntry;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupPlan;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupResult;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupScope;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import org.junit.jupiter.api.Test;

/** Exact public descriptor gate for the frozen Phase 5 cleanup surface. */
class V41CleanupPublicApiTest {
    @Test
    void operationDescriptorsMatchTheFrozenContract() throws Exception {
        Method plan = DurableStorageOperations.class.getMethod(
                "planCleanup", DurableCleanupRequest.class);
        Method apply = DurableStorageOperations.class.getMethod(
                "applyCleanup", DurableCleanupPlan.class);
        assertEquals(DurableCleanupPlan.class, plan.getReturnType());
        assertEquals(DurableCleanupResult.class, apply.getReturnType());
        assertTrue(Modifier.isPublic(plan.getModifiers()));
        assertTrue(Modifier.isStatic(plan.getModifiers()));
        assertTrue(Modifier.isPublic(apply.getModifiers()));
        assertTrue(Modifier.isStatic(apply.getModifiers()));
    }

    @Test
    void recordsAndScopeOrderRemainFrozen() {
        assertEquals(List.of("directory", "scope"),
                components(DurableCleanupRequest.class));
        assertEquals(List.of("member", "reason", "size", "fingerprint"),
                components(DurableCleanupEntry.class));
        assertEquals(List.of("directory", "scope", "authorityIdentity",
                        "deleteSet", "planDigest"),
                components(DurableCleanupPlan.class));
        assertEquals(List.of("directory", "planDigest", "deletedMembers",
                        "deletedBytes"),
                components(DurableCleanupResult.class));
        assertArrayEquals(new DurableCleanupScope[]{
                DurableCleanupScope.LIVE_STORE,
                DurableCleanupScope.OPERATION_REMNANT
        }, DurableCleanupScope.values());
    }

    private static List<String> components(Class<?> type) {
        return Arrays.stream(type.getRecordComponents())
                .map(component -> component.getName()).toList();
    }
}
