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
import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Runs exact V4.3 physical bytes using only the immutable published V4.2 core. */
class V43PublishedV42FormatCompatibilityTest {
    private static final Path PUBLISHED = Path.of(
            "target/compat-baselines/published-general-search-engine-4.2.0.jar");
    private static final Path PROBE = Path.of(
            "scripts/v43/PublishedV42FormatRejectionProbe.java");
    private static final String ROOT = "/compatibility/v43-derived-v12/";

    @Test
    void exactV12LiveAndBackupBytesFailClosedUnderPublishedV42(
            @TempDir Path temporary
    ) throws Exception {
        Assumptions.assumeTrue(Files.isRegularFile(PUBLISHED),
                "artifact-compat owns the published V4.2 format probe");
        Path live = Files.createDirectory(temporary.resolve("live"));
        Path backup = Files.createDirectory(temporary.resolve("backup"));
        Path classes = Files.createDirectory(temporary.resolve("classes"));
        materialize("live", live);
        materialize("backup", backup);
        Files.write(live.resolve("gse.lock"), new byte[0]);

        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        assertNotNull(compiler, "published compatibility probe requires a JDK");
        assertEquals(0, compiler.run(null, null, null,
                "-classpath", PUBLISHED.toString(), "-d", classes.toString(),
                PROBE.toString()));
        Process process = new ProcessBuilder(
                Path.of(System.getProperty("java.home"), "bin", "java").toString(),
                "-cp", classes + System.getProperty("path.separator") + PUBLISHED,
                "PublishedV42FormatRejectionProbe", live.toString(), backup.toString())
                .redirectErrorStream(true).start();
        String output = new String(process.getInputStream().readAllBytes(),
                StandardCharsets.UTF_8);
        assertEquals(0, process.waitFor(), output);
        assertTrue(output.contains("publishedV42V12Rejection=PASS"), output);
    }

    private static void materialize(String kind, Path directory)
            throws IOException {
        for (String line : resource("fixture-inventory.tsv").lines().toList()) {
            if (line.isBlank() || line.startsWith("#")) {
                continue;
            }
            String[] columns = line.split("\\t");
            if (columns[0].equals(kind)) {
                Files.write(directory.resolve(columns[1]), HexFormat.of().parseHex(
                        resource(columns[3]).replaceAll("\\s", "")));
            }
        }
    }

    private static String resource(String name) throws IOException {
        try (InputStream input = V43PublishedV42FormatCompatibilityTest.class
                .getResourceAsStream(ROOT + name)) {
            if (input == null) {
                throw new IOException("missing fixture: " + name);
            }
            return new String(input.readAllBytes(), StandardCharsets.US_ASCII);
        }
    }
}
