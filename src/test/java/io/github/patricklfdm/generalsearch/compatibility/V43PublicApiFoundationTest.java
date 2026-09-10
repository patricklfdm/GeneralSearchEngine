package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Constructor;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationStage;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurabilityMetrics;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Freezes V4.3 declarations while production derived-state support remains absent. */
class V43PublicApiFoundationTest {
    private static final String FIXTURE =
            "/compatibility/V43FastReopenPublicApi.java.fixture";
    private static final String PACKAGE =
            "io.github.patricklfdm.generalsearch.durability.";

    @Test
    void declarationFixtureFreezesExactSurfaceAndCompiles(@TempDir Path temporary)
            throws IOException {
        String source = readFixture();
        for (String required : List.of(
                "new DurableStorageFormatV43(\"gse-durable\", 1, 2)",
                "new DurableBackupFormatV43(\"gse-backup\", 1, 2)",
                "DEFAULT_MAX_DERIVED_STATE_BYTES = 2L * 1024 * 1024 * 1024",
                "HARD_MAX_DERIVED_STATE_BYTES = 8L * 1024 * 1024 * 1024 * 1024",
                "maxDerivedStateBytes(long value)",
                "inspectDerivedState(Path directory)",
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

        Path sourceFile = temporary.resolve("V43FastReopenPublicApi.java");
        Path classes = Files.createDirectory(temporary.resolve("classes"));
        Files.writeString(sourceFile, source, StandardCharsets.UTF_8);
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        assertNotNull(compiler, "V4.3 declaration fixtures require a JDK");
        assertEquals(0, compiler.run(null, null, null,
                "-classpath", System.getProperty("java.class.path"),
                "-d", classes.toString(), sourceFile.toString()));
    }

    @Test
    void phaseOneDoesNotShipV43ProductionTypes() {
        for (String name : List.of(
                "DurableDerivedStateStatus", "DurableDerivedComponentStatus",
                "DurableDerivedFinding", "DurableDerivedComponentReport",
                "DurableDerivedStateReport", "DurableReopenOutcome",
                "DurableReopenRejection", "DurableReopenReport")) {
            assertThrows(ClassNotFoundException.class,
                    () -> Class.forName(PACKAGE + name), name);
        }
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

    private static String readFixture() throws IOException {
        try (InputStream input = V43PublicApiFoundationTest.class
                .getResourceAsStream(FIXTURE)) {
            assertNotNull(input, FIXTURE);
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
