package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V43PublishedV42RollbackCompatibilityTest {
    private static final Path PUBLISHED = Path.of(
            "target/compat-baselines/published-general-search-engine-4.2.0.jar");
    private static final Path PROBE = Path.of("scripts/v43/PublishedV42RollbackProbe.java");
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, Integer> VALUE =
            Field.of("value", Integer.class, Document::value);
    private static final Field<Document, String> TEXT =
            Field.of("text", String.class, Document::text);
    private static final TextField<Document> ANALYZED =
            TextField.of(TEXT, SimpleAnalyzer.INSTANCE);

    @Test
    void publishedV42ReopensCurrentDefaultFormatWithoutByteChanges(
            @TempDir Path workspace) throws Exception {
        Assumptions.assumeTrue(Files.isRegularFile(PUBLISHED),
                "artifact-compat owns the published V4.2 rollback proof");
        Path store = workspace.resolve("store");
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID).field(VALUE).textField(ANALYZED)
                .index(IndexDefinition.equality(VALUE))
                .index(IndexDefinition.range(VALUE))
                .index(IndexDefinition.prefix(TEXT))
                .index(IndexDefinition.text(ANALYZED))
                .buildDurable(config(store))) {
            engine.add(new Document(1, 11, "alpha search")).join();
            engine.add(new Document(2, 22, "beta durable")).join();
            engine.checkpoint().join();
        }
        String before = treeDigest(store);
        Path classes = Files.createDirectory(workspace.resolve("classes"));
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        assertNotNull(compiler);
        assertEquals(0, compiler.run(null, null, null,
                "-classpath", PUBLISHED.toString(), "-d", classes.toString(),
                PROBE.toString()));
        Process process = new ProcessBuilder(
                Path.of(System.getProperty("java.home"), "bin", "java").toString(),
                "-cp", classes + System.getProperty("path.separator") + PUBLISHED,
                "PublishedV42RollbackProbe", store.toString())
                .redirectErrorStream(true).start();
        String output = new String(process.getInputStream().readAllBytes(),
                StandardCharsets.UTF_8);
        assertEquals(0, process.waitFor(), output);
        assertTrue(output.contains("publishedV42Rollback=PASS sequence=2 format=1.0"),
                output);
        assertEquals(before, treeDigest(store));
    }

    private static DurableStorageConfig<Integer, Document> config(Path directory) {
        return DurableStorageConfig.builder(directory, new Codec())
                .storageIdentity("v43-published-v42-rollback-v1")
                .schemaIdentity("v43-published-v42-rollback-schema-v1")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024).build();
    }

    private static String treeDigest(Path directory) throws Exception {
        var digest = java.security.MessageDigest.getInstance("SHA-256");
        try (var members = Files.list(directory)) {
            for (Path member : members.sorted().toList()) {
                digest.update(member.getFileName().toString().getBytes(StandardCharsets.UTF_8));
                digest.update(Files.readAllBytes(member));
            }
        }
        return java.util.HexFormat.of().formatHex(digest.digest());
    }

    private record Document(int id, int value, String text) { }

    private static final class Codec implements DurableCodec<Integer, Document> {
        @Override public String codecId() { return "v43-rollback-codec-v1"; }
        @Override public int codecVersion() { return 1; }
        @Override public byte[] encodeKey(Integer key) {
            return ByteBuffer.allocate(4).putInt(key).array();
        }
        @Override public Integer decodeKey(byte[] encoded) {
            return ByteBuffer.wrap(encoded).getInt();
        }
        @Override public byte[] encodeDocument(Document document) {
            byte[] text = document.text().getBytes(StandardCharsets.UTF_8);
            return ByteBuffer.allocate(12 + text.length).putInt(document.id())
                    .putInt(document.value()).putInt(text.length).put(text).array();
        }
        @Override public Document decodeDocument(byte[] encoded) {
            ByteBuffer input = ByteBuffer.wrap(encoded);
            int id = input.getInt();
            int value = input.getInt();
            int length = input.getInt();
            if (length < 0 || length != input.remaining()) {
                throw new IllegalArgumentException("invalid document");
            }
            byte[] text = new byte[length];
            input.get(text);
            return new Document(id, value, new String(text, StandardCharsets.UTF_8));
        }
    }
}
