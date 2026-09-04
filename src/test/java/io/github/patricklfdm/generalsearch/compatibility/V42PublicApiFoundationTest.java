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
import io.github.patricklfdm.generalsearch.durability.DurableOperationException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Freezes V4.2 declarations while production storage evolution remains absent. */
class V42PublicApiFoundationTest {
    private static final String FIXTURE =
            "/compatibility/V42StorageEvolutionPublicApi.java.fixture";
    private static final String PACKAGE =
            "io.github.patricklfdm.generalsearch.durability.";

    @Test
    void declarationFixtureContainsEveryFrozenFamilyAndCompiles(
            @TempDir Path temporary
    ) throws IOException {
        String source = readFixture();
        for (String required : List.of(
                "record DurableStorageFormat(String family, int major, int minor)",
                "new DurableStorageFormat(\"gse-durable\", 1, 0)",
                "new DurableStorageFormat(\"gse-durable\", 1, 1)",
                "DurableStorageConfig.Builder<K, T> format(DurableStorageFormat format)",
                "static DurableStoreFormatReport inspectStoreFormat(Path directory)",
                "static DurableBackupFormatReport inspectBackupFormat(Path directory)",
                "<SK, ST> DurableMigrationPlan planDurableMigration(",
                "<SK, ST> DurableMigrationResult applyDurableMigration(",
                "record DurableMigrationRequest<SK, ST, TK, TT>(",
                "record DurableMigrationPlan(",
                "record DurableMigrationResult(",
                "interface DurableMigrationTransform<SK, ST, TK, TT>",
                "TRANSFORM_NONDETERMINISTIC",
                "PUBLICATION_INDETERMINATE",
                "VERIFY_SOURCE_PRESERVED"
        )) {
            assertTrue(source.contains(required), required);
        }
        assertFalse(source.contains("Serializable"));
        assertFalse(source.contains("ServiceLoader"));
        assertFalse(source.contains("ObjectOutputStream"));

        Path sourceFile = temporary.resolve("V42StorageEvolutionPublicApi.java");
        Path classes = Files.createDirectory(temporary.resolve("classes"));
        Files.writeString(sourceFile, source, StandardCharsets.UTF_8);
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        assertNotNull(compiler, "V4.2 declaration fixtures require a JDK");
        int exit = compiler.run(
                null,
                null,
                null,
                "-classpath",
                System.getProperty("java.class.path"),
                "-d",
                classes.toString(),
                sourceFile.toString());
        assertEquals(0, exit, "V4.2 declaration fixture must compile");
    }

    @Test
    void phase1DoesNotShipStorageEvolutionTypes() {
        for (String simpleName : List.of(
                "DurableStorageFormat",
                "DurableStoreFormatReport",
                "DurableBackupFormatReport",
                "DurableMigrationTransform",
                "DurableMigrationTransformDescriptor",
                "DurableMigrationRecord",
                "DurableMigrationRequest",
                "DurableMigrationSourceMember",
                "DurableMigrationIndexChange",
                "DurableMigrationPlan",
                "DurableMigrationResult",
                "DurableMigrationStage",
                "DurableMigrationException"
        )) {
            assertThrows(ClassNotFoundException.class,
                    () -> Class.forName(PACKAGE + simpleName), simpleName);
        }
    }

    @Test
    void publishedV41OperationalReasonOrderRemainsFrozen() {
        assertEquals(List.of(
                "STORAGE_IN_USE",
                "SOURCE_INVALID",
                "BACKUP_INVALID",
                "IDENTITY_MISMATCH",
                "TARGET_EXISTS",
                "TARGET_INVALID",
                "OPERATION_IN_PROGRESS",
                "UNSUPPORTED_FORMAT",
                "UNSUPPORTED_FILESYSTEM",
                "CAPACITY_EXCEEDED",
                "IO_FAILURE",
                "CLOSED"
        ), List.of(DurableOperationException.Reason.values()).stream()
                .map(Enum::name)
                .toList());
    }

    private static String readFixture() throws IOException {
        try (InputStream input = V42PublicApiFoundationTest.class
                .getResourceAsStream(FIXTURE)) {
            assertNotNull(input, FIXTURE);
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
