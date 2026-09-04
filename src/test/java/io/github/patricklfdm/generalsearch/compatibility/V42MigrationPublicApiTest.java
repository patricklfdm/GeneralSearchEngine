package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.Arrays;
import java.util.List;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationException;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationIndexChange;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationPlan;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRecord;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRequest;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationResult;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationSourceMember;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationStage;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationTransform;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationTransformDescriptor;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import org.junit.jupiter.api.Test;

/** Exact public descriptor gate for the Phase 3 migration surface. */
class V42MigrationPublicApiTest {
    @Test
    void builderMethodsMatchFrozenOwnersAndErasure() throws Exception {
        Method plan = SearchEngineBuilder.class.getMethod(
                "planDurableMigration", SearchEngineBuilder.class,
                DurableMigrationRequest.class);
        Method apply = SearchEngineBuilder.class.getMethod(
                "applyDurableMigration", SearchEngineBuilder.class,
                DurableMigrationRequest.class, DurableMigrationPlan.class);
        assertEquals(DurableMigrationPlan.class, plan.getReturnType());
        assertEquals(DurableMigrationResult.class, apply.getReturnType());
        assertTrue(Modifier.isPublic(plan.getModifiers()));
        assertTrue(Modifier.isPublic(apply.getModifiers()));
        assertEquals(2, plan.getTypeParameters().length);
        assertEquals(2, apply.getTypeParameters().length);
    }

    @Test
    void recordComponentsAndEnumOrdersAreExact() {
        assertEquals(List.of("identifier", "version"),
                components(DurableMigrationTransformDescriptor.class));
        assertEquals(List.of("key", "document"),
                components(DurableMigrationRecord.class));
        assertEquals(List.of("sourceDirectory", "sourceConfig", "targetConfig",
                        "transformDescriptor", "transform",
                        "maxSourceAuthoritativeBytes",
                        "maxTargetAuthoritativeBytes",
                        "capacitySafetyReserveBytes", "maxCollisionEntries",
                        "maxFindings", "maxDiagnosticBytes"),
                components(DurableMigrationRequest.class));
        assertEquals(List.of("name", "size", "sha256"),
                components(DurableMigrationSourceMember.class));
        assertEquals(List.of("added", "removed", "retained"),
                components(DurableMigrationIndexChange.class));
        assertEquals(List.of("schemaVersion", "sourceDirectory", "targetDirectory",
                        "sourceFormat", "targetFormat", "sourceHistory",
                        "targetHistory", "sourceSequence", "nextDocId",
                        "sourceMembers", "sourceAuthorityIdentity",
                        "sourceDescriptorDigest", "targetDescriptorDigest",
                        "transformDescriptor", "documentCount", "sourceIndexCount",
                        "targetIndexCount", "indexChange", "targetAuthoritativeBytes",
                        "peakTargetBytes", "capacitySafetyReserveBytes",
                        "projectionDigest", "planDigest"),
                components(DurableMigrationPlan.class));
        assertEquals(List.of("sourceDirectory", "targetDirectory", "sourceFormat",
                        "targetFormat", "sourceHistory", "targetHistory", "sequence",
                        "nextDocId", "documentCount", "sourceAuthorityIdentity",
                        "projectionDigest", "planDigest", "authoritativeBytes"),
                components(DurableMigrationResult.class));
        assertArrayEquals(new DurableMigrationStage[]{
                DurableMigrationStage.VALIDATE_REQUEST,
                DurableMigrationStage.ACQUIRE_SOURCE,
                DurableMigrationStage.VERIFY_SOURCE,
                DurableMigrationStage.PROJECT_TARGET,
                DurableMigrationStage.VALIDATE_CAPACITY,
                DurableMigrationStage.PREPARE_TARGET,
                DurableMigrationStage.WRITE_METADATA,
                DurableMigrationStage.WRITE_CHECKPOINT,
                DurableMigrationStage.WRITE_MANIFEST,
                DurableMigrationStage.WRITE_WAL,
                DurableMigrationStage.VERIFY_STAGING,
                DurableMigrationStage.PUBLISH_TARGET,
                DurableMigrationStage.FORCE_PARENT,
                DurableMigrationStage.VERIFY_TARGET,
                DurableMigrationStage.VERIFY_SOURCE_PRESERVED,
                DurableMigrationStage.CLEANUP_MARKER,
                DurableMigrationStage.COMPLETE
        }, DurableMigrationStage.values());
        assertArrayEquals(new DurableMigrationException.Reason[]{
                DurableMigrationException.Reason.STORAGE_IN_USE,
                DurableMigrationException.Reason.SOURCE_INVALID,
                DurableMigrationException.Reason.IDENTITY_MISMATCH,
                DurableMigrationException.Reason.MIGRATION_PATH_UNSUPPORTED,
                DurableMigrationException.Reason.MIGRATION_NOT_REQUIRED,
                DurableMigrationException.Reason.PLAN_STALE,
                DurableMigrationException.Reason.TRANSFORM_FAILURE,
                DurableMigrationException.Reason.TRANSFORM_NONDETERMINISTIC,
                DurableMigrationException.Reason.TARGET_EXISTS,
                DurableMigrationException.Reason.TARGET_INVALID,
                DurableMigrationException.Reason.UNSUPPORTED_FILESYSTEM,
                DurableMigrationException.Reason.CAPACITY_EXCEEDED,
                DurableMigrationException.Reason.IO_FAILURE,
                DurableMigrationException.Reason.PUBLICATION_INDETERMINATE
        }, DurableMigrationException.Reason.values());
        assertTrue(DurableMigrationTransform.class.isAnnotationPresent(
                FunctionalInterface.class));
    }

    private static List<String> components(Class<?> type) {
        return Arrays.stream(type.getRecordComponents())
                .map(component -> component.getName()).toList();
    }
}
