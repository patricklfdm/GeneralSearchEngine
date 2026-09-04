package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HexFormat;
import java.util.List;
import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Executes exact V4.2 bytes with only the immutable published V4.1 artifact. */
class V42PublishedV41FormatCompatibilityTest {
    private static final Path PUBLISHED_V41 = Path.of(
            "target/compat-baselines/published-general-search-engine-4.1.0.jar");
    private static final Path PROBE = Path.of(
            "scripts/v42/PublishedV41FormatProbe.java");
    private static final String FIXTURE_ROOT = "/compatibility/v42-storage-v11/";
    private static final String CHECKPOINT =
            "gse-checkpoint-00000000000000000007-"
                    + "00112233445566778899aabbccddeeff.chk";

    @Test
    void exactV11BytesFailClosedUnderPublishedV41(@TempDir Path temporary)
            throws Exception {
        Assumptions.assumeTrue(Files.isRegularFile(PUBLISHED_V41),
                "artifact-compat profile owns the published V4.1 probe");
        assertTrue(Files.isRegularFile(PROBE), PROBE.toString());
        Path live = Files.createDirectory(temporary.resolve("live"));
        Path backup = Files.createDirectory(temporary.resolve("backup"));
        Path classes = Files.createDirectory(temporary.resolve("classes"));
        materialize(live, backup);

        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        assertNotNull(compiler, "published compatibility probe requires a JDK");
        assertEquals(0, compiler.run(null, null, null,
                "-classpath", PUBLISHED_V41.toString(),
                "-d", classes.toString(), PROBE.toString()));

        Process process = new ProcessBuilder(
                Path.of(System.getProperty("java.home"), "bin", "java").toString(),
                "-cp", classes + System.getProperty("path.separator") + PUBLISHED_V41,
                "PublishedV41FormatProbe", live.toString(), backup.toString())
                .redirectErrorStream(true)
                .start();
        String output = new String(
                process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        assertEquals(0, process.waitFor(), output);
        assertTrue(output.contains("publishedV41 kind=store status=CORRUPT"), output);
        assertTrue(output.contains("publishedV41 kind=backup status=CORRUPT"), output);
        assertTrue(output.contains("STRING_LENGTH:gse-metadata"), output);
        assertTrue(output.contains("STRING_LENGTH:gse-backup-manifest"), output);
    }

    private static void materialize(Path live, Path backup) throws IOException {
        Files.write(live.resolve("gse.lock"), new byte[0]);
        writeHex(live.resolve("gse-metadata"), "gse-metadata.hex");
        writeHex(live.resolve(CHECKPOINT), "gse-checkpoint.hex");
        writeHex(live.resolve("gse-checkpoint-manifest"),
                "gse-checkpoint-manifest.hex");
        writeHex(live.resolve("gse-wal-00000000000000000002.log"),
                "gse-wal.hex");
        for (List<String> mapping : List.of(
                List.of("gse-backup-metadata", "gse-metadata.hex"),
                List.of("gse-backup-checkpoint", "gse-checkpoint.hex"),
                List.of("gse-backup-manifest", "gse-backup-manifest.hex"))) {
            writeHex(backup.resolve(mapping.get(0)), mapping.get(1));
        }
    }

    private static void writeHex(Path path, String resource) throws IOException {
        try (InputStream input = V42PublishedV41FormatCompatibilityTest.class
                .getResourceAsStream(FIXTURE_ROOT + resource)) {
            if (input == null) {
                throw new IOException("missing fixture: " + resource);
            }
            String hex = new String(input.readAllBytes(), StandardCharsets.US_ASCII);
            Files.write(path, HexFormat.of().parseHex(hex.replaceAll("\\s", "")));
        }
    }
}
