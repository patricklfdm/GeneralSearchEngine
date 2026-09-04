package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRecord;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRequest;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationTransformDescriptor;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V42PublishedV41RollbackCompatibilityTest {
    private static final Path PUBLISHED_V41 = Path.of(
            "target/compat-baselines/published-general-search-engine-4.1.0.jar");
    private static final Path PROBE = Path.of(
            "scripts/v42/PublishedV41RollbackProbe.java");
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);

    @Test
    void publishedV41ReopensUntouchedSourceAfterTargetContinues(
            @TempDir Path workspace
    ) throws Exception {
        Assumptions.assumeTrue(Files.isRegularFile(PUBLISHED_V41),
                "artifact-compat owns published V4.1 rollback proof");
        Path source = workspace.resolve("source").toAbsolutePath().normalize();
        Path target = workspace.resolve("target").toAbsolutePath().normalize();
        Path backup = workspace.resolve("backup").toAbsolutePath().normalize();
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source, DurableStorageFormat.V1_0))) {
            engine.add(new Document(1, 11)).join();
            engine.add(new Document(2, 22)).join();
            engine.remove(1).join();
            engine.checkpoint().join();
            engine.backup(new DurableBackupRequest(
                    backup, 64L * 1024 * 1024)).join();
        }
        assertEquals(DurableVerificationStatus.VALID,
                DurableStorageOperations.verifyBackup(backup).status());
        String before = treeDigest(source);

        DurableMigrationRequest<Integer, Document, Integer, Document> request =
                request(source, target);
        var plan = builder().planDurableMigration(builder(), request);
        builder().applyDurableMigration(builder(), request, plan);
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(target, DurableStorageFormat.V1_1))) {
            engine.add(new Document(3, 33)).join();
            engine.checkpoint().join();
        }
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(target, DurableStorageFormat.V1_1))) {
            assertEquals(new Document(3, 33), engine.get(3));
        }
        assertEquals(before, treeDigest(source));

        Path classes = Files.createDirectory(workspace.resolve("v41-classes"));
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        assertNotNull(compiler);
        assertEquals(0, compiler.run(null, null, null,
                "-classpath", PUBLISHED_V41.toString(),
                "-d", classes.toString(), PROBE.toString()));
        Process process = new ProcessBuilder(
                Path.of(System.getProperty("java.home"), "bin", "java").toString(),
                "-cp", classes + System.getProperty("path.separator") + PUBLISHED_V41,
                "PublishedV41RollbackProbe", source.toString())
                .redirectErrorStream(true).start();
        String output = new String(
                process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        assertEquals(0, process.waitFor(), output);
        assertTrue(output.contains("publishedV41Rollback=PASS sequence=3"), output);
        assertEquals(before, treeDigest(source));
    }

    private static DurableMigrationRequest<Integer, Document,
            Integer, Document> request(Path source, Path target) {
        return new DurableMigrationRequest<>(source,
                new DurableVerificationConfig<>(
                        "v42-rollback-store", "v42-rollback-schema",
                        new DocumentCodec(), 1,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_DOCUMENTS),
                config(target, DurableStorageFormat.V1_1),
                new DurableMigrationTransformDescriptor("identity-format-v1", 1),
                (key, document) -> new DurableMigrationRecord<>(key, document),
                64L * 1024 * 1024, 64L * 1024 * 1024,
                1024 * 1024, 1000, 1000, 64 * 1024);
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID);
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            DurableStorageFormat format
    ) {
        return DurableStorageConfig.builder(directory, new DocumentCodec())
                .format(format)
                .storageIdentity("v42-rollback-store")
                .schemaIdentity("v42-rollback-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private static String treeDigest(Path directory) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (var members = Files.list(directory)) {
            for (Path member : members.sorted().toList()) {
                digest.update(member.getFileName().toString()
                        .getBytes(StandardCharsets.UTF_8));
                digest.update(Files.readAllBytes(member));
            }
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private record Document(int id, int value) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override public String codecId() { return "v42-rollback-codec"; }
        @Override public int codecVersion() { return 1; }
        @Override public byte[] encodeKey(Integer key) {
            return ByteBuffer.allocate(4).putInt(key).array();
        }
        @Override public Integer decodeKey(byte[] encoded) {
            return ByteBuffer.wrap(encoded).getInt();
        }
        @Override public byte[] encodeDocument(Document document) {
            return ByteBuffer.allocate(8)
                    .putInt(document.id()).putInt(document.value()).array();
        }
        @Override public Document decodeDocument(byte[] encoded) {
            ByteBuffer value = ByteBuffer.wrap(encoded);
            return new Document(value.getInt(), value.getInt());
        }
    }
}
