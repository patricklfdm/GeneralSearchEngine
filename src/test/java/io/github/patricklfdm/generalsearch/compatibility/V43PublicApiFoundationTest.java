package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.lang.reflect.RecordComponent;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import io.github.patricklfdm.generalsearch.durability.DurableBackupFormat;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationStage;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurabilityMetrics;
import org.junit.jupiter.api.Test;

/** Freezes V4.3 declarations and verifies their Phase 2 realization. */
class V43PublicApiFoundationTest {
    private static final String FIXTURE =
            "/compatibility/V43FastReopenPublicApi.java.fixture";
    private static final String PACKAGE =
            "io.github.patricklfdm.generalsearch.durability.";
    private static final String PHASE_ONE_FIXTURE_SHA256 =
            "4bf3503d77d01834915377002ceea92e5704274a2f131f15c71baaf7c2ed233a";

    @Test
    void phaseOneDeclarationFixtureRemainsByteExact() throws IOException {
        String source = readFixture();
        assertEquals(PHASE_ONE_FIXTURE_SHA256, sha256(source));
        for (String required : List.of(
                "new DurableStorageFormatV43(\"gse-durable\", 1, 2)",
                "new DurableBackupFormatV43(\"gse-backup\", 1, 2)",
                "DEFAULT_MAX_DERIVED_STATE_BYTES = 2L * 1024 * 1024 * 1024",
                "HARD_MAX_DERIVED_STATE_BYTES = 8L * 1024 * 1024 * 1024 * 1024",
                "maxDerivedStateBytes(long value)",
                "inspectDerivedState(Path directory)",
                "extends DurableSearchEngine<K, T>",
                "Optional<DurableReopenReport> lastReopenReport()",
                "record DurableDerivedStateReport(",
                "record DurableDerivedComponentReport(",
                "record DurableReopenReport(",
                "NOT_APPLICABLE,\n    ABSENT,\n    VALID,\n    PARTIAL,",
                "COMPLETE_WARM,\n    PARTIAL_FALLBACK,\n    FULL_FALLBACK"
        )) {
            assertTrue(source.contains(required), required);
        }
        for (String forbidden : List.of(
                "Serializable", "ObjectOutputStream", "ServiceLoader",
                "MappedByteBuffer", "Class.forName")) {
            assertFalse(source.contains(forbidden), forbidden);
        }
    }

    @Test
    void phaseTwoShipsFrozenInspectionTypes() throws Exception {
        for (String name : List.of(
                "DurableDerivedStateStatus", "DurableDerivedComponentStatus",
                "DurableDerivedFinding", "DurableDerivedComponentReport",
                "DurableDerivedStateReport", "DurableReopenOutcome",
                "DurableReopenRejection", "DurableReopenReport")) {
            assertNotNull(Class.forName(PACKAGE + name), name);
        }
        assertEquals(new DurableStorageFormat("gse-durable", 1, 2),
                DurableStorageFormat.V1_2);
        assertEquals(new DurableBackupFormat("gse-backup", 1, 2),
                DurableBackupFormat.V1_2);
        assertEquals(2L * 1024 * 1024 * 1024,
                DurableStorageConfig.DEFAULT_MAX_DERIVED_STATE_BYTES);
        Method allowance = DurableStorageConfig.Builder.class.getMethod(
                "maxDerivedStateBytes", long.class);
        assertEquals(DurableStorageConfig.Builder.class, allowance.getReturnType());
        Method inspect = DurableStorageOperations.class.getMethod(
                "inspectDerivedState", Path.class);
        assertEquals(Class.forName(PACKAGE + "DurableDerivedStateReport"),
                inspect.getReturnType());
        Method reopen = DurableSearchEngine.class.getMethod("lastReopenReport");
        assertTrue(reopen.isDefault());
        assertEquals("java.util.Optional<" + PACKAGE + "DurableReopenReport>",
                reopen.getGenericReturnType().getTypeName());
        assertArrayEquals(new String[] {
                "NOT_APPLICABLE", "ABSENT", "VALID", "PARTIAL", "STALE",
                "INCOMPATIBLE", "INCOMPLETE", "CORRUPT"
        }, enumNames("DurableDerivedStateStatus"));
        assertArrayEquals(new String[] {
                "ADMISSIBLE", "MISSING", "STALE", "INCOMPATIBLE",
                "INCOMPLETE", "CORRUPT"
        }, enumNames("DurableDerivedComponentStatus"));
        assertArrayEquals(new String[] {
                "NOT_APPLICABLE", "COMPLETE_WARM", "PARTIAL_FALLBACK",
                "FULL_FALLBACK"
        }, enumNames("DurableReopenOutcome"));
        assertArrayEquals(new String[] {
                "directory", "status", "declaredFormat", "history",
                "checkpointSequence", "catalogIdentity", "expectedComponentCount",
                "referencedComponentCount", "admissibleComponentCount",
                "rejectedComponentCount", "referencedBytes", "admissibleBytes",
                "rejectedBytes", "stagingBytes", "unreferencedBytes",
                "components", "findings"
        }, componentNames("DurableDerivedStateReport"));
        assertArrayEquals(new String[] {
                "authoritativeCheckpointSequence", "recoveredSequence",
                "checkpointIndexCount", "loadedComponentCount",
                "rebuiltComponentCount", "replayCreatedIndexCount",
                "derivedStatus", "outcome", "rejections",
                "canonicalLoadDuration", "derivedInspectionDuration",
                "derivedLoadDuration", "rebuildDuration", "walReplayDuration",
                "refreshDuration", "totalOpenDuration", "derivedBytesRead",
                "derivedBytesWritten", "refreshAttempted", "refreshSucceeded"
        }, componentNames("DurableReopenReport"));
    }

    @Test
    void publishedEnumsAndMetricsConstructorRemainFrozen() {
        assertArrayEquals(new String[] {
                "VALID", "VALID_WITH_SAFE_REMNANTS", "INCOMPATIBLE",
                "INCOMPLETE", "CORRUPT", "UNSUPPORTED"
        }, names(DurableVerificationStatus.values()));
        assertArrayEquals(new String[] {
                "VALIDATE_REQUEST", "ACQUIRE_SOURCE", "VERIFY_SOURCE",
                "PROJECT_TARGET", "VALIDATE_CAPACITY", "PREPARE_TARGET",
                "WRITE_METADATA", "WRITE_CHECKPOINT", "WRITE_MANIFEST",
                "WRITE_WAL", "VERIFY_STAGING", "PUBLISH_TARGET",
                "FORCE_PARENT", "VERIFY_TARGET", "VERIFY_SOURCE_PRESERVED",
                "CLEANUP_MARKER", "COMPLETE"
        }, names(DurableMigrationStage.values()));
        Constructor<?>[] constructors = DurabilityMetrics.class.getConstructors();
        assertEquals(1, constructors.length);
        assertEquals(12, constructors[0].getParameterCount());
    }

    private static String[] names(Enum<?>[] values) {
        return java.util.Arrays.stream(values).map(Enum::name).toArray(String[]::new);
    }

    private static String[] enumNames(String simpleName) throws Exception {
        Object[] values = Class.forName(PACKAGE + simpleName).getEnumConstants();
        return java.util.Arrays.stream(values)
                .map(value -> ((Enum<?>) value).name()).toArray(String[]::new);
    }

    private static String[] componentNames(String simpleName) throws Exception {
        return java.util.Arrays.stream(Class.forName(PACKAGE + simpleName)
                        .getRecordComponents())
                .map(RecordComponent::getName).toArray(String[]::new);
    }

    private static String sha256(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static String readFixture() throws IOException {
        try (InputStream input = V43PublicApiFoundationTest.class
                .getResourceAsStream(FIXTURE)) {
            assertNotNull(input, FIXTURE);
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
