package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Freezes V4.1 descriptors and tracks the currently admitted production phase. */
class V41PublicApiFoundationTest {
    private static final String FIXTURE =
            "/compatibility/V41OperationalPublicApi.java.fixture";

    @Test
    void declarationFixtureContainsEveryFrozenOperationAndCompiles(
            @TempDir Path temporary
    ) throws IOException {
        String source = readFixture();
        for (String required : List.of(
                "default CompletableFuture<DurableBackupResult> backup(",
                "record DurableBackupRequest(Path targetDirectory, long maxBundleBytes)",
                "record DurableBackupResult(",
                "new DurableBackupFormat(\"gse-backup\", 1, 0)",
                "static DurableVerificationReport verifyStore(Path directory)",
                "static DurableVerificationReport verifyBackup(Path directory)",
                "static DurableCleanupPlan planCleanup(DurableCleanupRequest request)",
                "static DurableCleanupResult applyCleanup(DurableCleanupPlan plan)",
                "DurableSemanticVerificationReport verifyDurableBackup(",
                "DurableRestoreResult restoreDurableBackup(",
                "record DurableVerificationConfig<K, T>(",
                "SEMANTICALLY_VALID",
                "VALID_WITH_SAFE_REMNANTS",
                "OPERATION_IN_PROGRESS"
        )) {
            assertTrue(source.contains(required), required);
        }
        assertFalse(source.contains("ObjectOutputStream"));
        assertFalse(source.contains("Serializable"));

        Path sourceFile = temporary.resolve("V41OperationalPublicApi.java");
        Path classes = Files.createDirectory(temporary.resolve("classes"));
        Files.writeString(sourceFile, source, StandardCharsets.UTF_8);
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        assertNotNull(compiler, "V4.1 contract fixtures require a JDK");
        int exit = compiler.run(
                null,
                null,
                null,
                "-classpath",
                System.getProperty("java.class.path"),
                "-d",
                classes.toString(),
                sourceFile.toString());
        assertEquals(0, exit, "V4.1 declaration fixture must compile");
    }

    @Test
    void phase4ShipsTypedRestoreButNotCleanupTypes() throws Exception {
        for (String simpleName : List.of(
                "DurableStorageOperations",
                "DurableVerificationStatus",
                "DurableVerificationFinding",
                "DurableVerificationReport",
                "DurableOperationException",
                "DurableBackupRequest",
                "DurableBackupFormat",
                "DurableBackupResult",
                "DurableVerificationConfig",
                "DurableSemanticVerificationStatus",
                "DurableSemanticVerificationReport",
                "DurableRestoreResult"
        )) {
            assertNotNull(Class.forName(
                    "io.github.patricklfdm.generalsearch.durability." + simpleName));
        }
        assertFalse(classExists(
                "io.github.patricklfdm.generalsearch.durability.DurableCleanupPlan"));
    }

    @Test
    void phase4AddsTypedBuilderOperations() {
        assertTrue(List.of(DurableSearchEngine.class.getMethods()).stream()
                .anyMatch(method -> method.getName().equals("backup")));
        assertTrue(List.of(SearchEngineBuilder.class.getMethods()).stream()
                .anyMatch(method -> method.getName().equals("verifyDurableBackup")));
        assertTrue(List.of(SearchEngineBuilder.class.getMethods()).stream()
                .anyMatch(method -> method.getName().equals("restoreDurableBackup")));
    }

    private static String readFixture() throws IOException {
        try (InputStream input = V41PublicApiFoundationTest.class
                .getResourceAsStream(FIXTURE)) {
            assertNotNull(input, FIXTURE);
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    private static boolean classExists(String name) {
        try {
            Class.forName(name);
            return true;
        } catch (ClassNotFoundException expected) {
            return false;
        }
    }
}
