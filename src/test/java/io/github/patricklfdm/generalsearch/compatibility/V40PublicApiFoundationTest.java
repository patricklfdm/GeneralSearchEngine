package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Freezes the declaration fixture without admitting production durability in Phase 1. */
class V40PublicApiFoundationTest {
    private static final String FIXTURE =
            "/compatibility/V40DurablePublicApi.java.fixture";

    @Test
    void declarationFixtureContainsEveryPhase0CapabilityAndCompiles(
            @TempDir Path temporary
    ) throws IOException {
        String source = readFixture();
        for (String required : List.of(
                "interface DurableCodec<K, T>",
                "byte[] encodeKey(K key)",
                "byte[] encodeDocument(T document)",
                "interface DurableSearchEngine<K, T> extends SearchEngine<K, T>",
                "CompletableFuture<Void> checkpoint()",
                "buildDurable(DurableStorageConfig<K, T> config)",
                "final class DurableStorageConfig<K, T>",
                "static <K, T> Builder<K, T> builder(",
                "long checkpointWalBytes()",
                "long maxRetainedBytes()",
                "final class DurabilityMetrics",
                "DurabilityStatus status()",
                "RecoverySource recoverySource()",
                "enum Reason",
                "CAPACITY_EXCEEDED",
                "OptionalLong sequence()"
        )) {
            assertTrue(source.contains(required), required);
        }
        assertFalse(source.contains("ObjectOutputStream"));
        assertFalse(source.contains("Serializable"));

        Path sourceFile = temporary.resolve("V40DurablePublicApi.java");
        Path classes = Files.createDirectory(temporary.resolve("classes"));
        Files.writeString(sourceFile, source, StandardCharsets.UTF_8);
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        assertNotNull(compiler, "Phase 1 contract fixtures require a JDK");
        int exit = compiler.run(
                null,
                null,
                null,
                "-classpath",
                System.getProperty("java.class.path"),
                "-d",
                classes.toString(),
                sourceFile.toString());
        assertEquals(0, exit, "V4 durable declaration fixture must compile");
    }

    @Test
    void phase1DoesNotPublishDurabilityTypesPrematurely() {
        for (String simpleName : List.of(
                "DurableCodec",
                "DurableSearchEngine",
                "DurableStorageConfig",
                "DurabilityMetrics",
                "DurabilityException"
        )) {
            assertThrows(ClassNotFoundException.class, () -> Class.forName(
                    "io.github.patricklfdm.generalsearch.durability." + simpleName));
        }
    }

    private static String readFixture() throws IOException {
        try (InputStream input = V40PublicApiFoundationTest.class
                .getResourceAsStream(FIXTURE)) {
            assertNotNull(input, FIXTURE);
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
