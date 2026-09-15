package io.github.patricklfdm.generalsearch.admission;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.AdmissionOracle.*;

import java.nio.charset.StandardCharsets;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.List;
import org.junit.jupiter.api.Test;

class V50AdmissionFormatTest {
    @org.junit.jupiter.api.io.TempDir java.nio.file.Path temporary;
    private static final String RESOURCE = "/replication/v50-admission-fixtures-v2.json";

    @Test
    void bothLanguagesReadTheSameFrozenPositiveAndNegativeBytes() throws Exception {
        byte[] raw;
        try (var input = getClass().getResourceAsStream(RESOURCE)) { raw = input.readAllBytes(); }
        var catalog = object(AdmissionJson.parse(new String(raw, StandardCharsets.UTF_8)));
        assertEquals("gse-v50-admission-fixtures-v2", catalog.get("schema"));
        var bases = object(catalog.get("bases"));
        int accepted = 0, rejected = 0;
        for (Object row : list(catalog.get("cases"))) {
            var c = object(row); String name = string(c.get("name"));
            var files = new LinkedHashMap<String, byte[]>();
            object(bases.get(c.get("base"))).forEach((file, value) -> files.put(file, HexFormat.of().parseHex(string(value))));
            if (c.containsKey("replace")) object(c.get("replace")).forEach((file, value) -> {
                if (value == null) files.remove(file); else files.put(file, HexFormat.of().parseHex(string(value)));
            });
            Map<String, String> before = hashes(files);
            if (Boolean.TRUE.equals(c.get("valid"))) {
                var result = assertDoesNotThrow(() -> validate(files), name);
                assertEquals(c.get("expected"), result, name);
                long base = number(result.get("baseSequence"));
                assertEquals(List.of(base, base + 1, base + 1, base + 1), result.get("snapshotSequences"), name);
                accepted++;
            } else {
                // Only a format rejection counts; incidental NPE/IO/assertion bugs must fail the test.
                assertThrows(IllegalArgumentException.class, () -> validate(files), name);
                rejected++;
            }
            assertEquals(before, hashes(files), name + " source-preserving inspection");
        }
        assertEquals(5, accepted); assertEquals(48, rejected);
        try (var input = getClass().getResourceAsStream("/replication/v50-admission-fixtures-v2.sha256")) {
            String expected = new String(input.readAllBytes(), StandardCharsets.US_ASCII).strip();
            assertEquals(hex(sha(raw)) + "  v50-admission-fixtures-v2.json", expected);
        }
    }

    @Test
    void aConsumerCompiledAgainstTheHistoricalConstantIsRejectedByTheNewWireContract() throws Exception {
        var old = temporary.resolve("old"); var consumer = temporary.resolve("consumer");
        java.nio.file.Files.createDirectories(old); java.nio.file.Files.createDirectories(consumer);
        var stub = old.resolve("ReplicatedSearchEngines.java");
        java.nio.file.Files.writeString(stub, "package io.github.patricklfdm.generalsearch.replication; "
                + "public final class ReplicatedSearchEngines { public static final String PROTOCOL = \"gse-replication/1.0\"; }");
        var compiler = javax.tools.ToolProvider.getSystemJavaCompiler();
        assertEquals(0, compiler.run(null, null, null, "-d", old.toString(), stub.toString()));
        var source = consumer.resolve("StaleConsumer.java");
        java.nio.file.Files.writeString(source, "public class StaleConsumer { public static String protocol() { return "
                + "io.github.patricklfdm.generalsearch.replication.ReplicatedSearchEngines.PROTOCOL; } }");
        assertEquals(0, compiler.run(null, null, null, "-cp", old.toString(), "-d", consumer.toString(), source.toString()));
        try (var loader = new java.net.URLClassLoader(new java.net.URL[]{consumer.toUri().toURL()}, getClass().getClassLoader())) {
            String stale = (String) loader.loadClass("StaleConsumer").getMethod("protocol").invoke(null);
            assertEquals("gse-replication/1.0", stale);
            assertEquals("gse-replication/1.1", io.github.patricklfdm.generalsearch.replication.ReplicatedSearchEngines.PROTOCOL);
            Map<String, Object> catalog;
            try (var input = getClass().getResourceAsStream(RESOURCE)) {
                catalog = object(AdmissionJson.parse(new String(input.readAllBytes(), StandardCharsets.UTF_8)));
            }
            var base = object(object(catalog.get("bases")).get("empty"));
            byte[] genesis = HexFormat.of().parseHex(string(base.get("genesis.gsr")));
            byte[] manifest = HexFormat.of().parseHex(string(base.get("manifest.gsr")));
            var g = genesis(genesis); var m = manifest(manifest, g);
            byte[] raw = HexFormat.of().parseHex(string(base.get("wire-01.gsrp")));
            var body = json(java.util.Arrays.copyOfRange(raw, 48, raw.length));
            body.put("protocol", stale);
            byte[] encoded = AdmissionJson.canonical(body).getBytes(StandardCharsets.US_ASCII);
            byte[] prefix = java.nio.ByteBuffer.allocate(16).putInt(0x47535250).putShort((short) 1).putShort((short) 1)
                    .putShort((short) 1).putShort((short) 0).putInt(encoded.length).array();
            byte[] frame = java.nio.ByteBuffer.allocate(48 + encoded.length).put(prefix).put(sha(prefix, encoded)).put(encoded).array();
            assertThrows(IllegalArgumentException.class, () -> wire(frame, m, g));
        }
    }

    private Map<String, String> hashes(Map<String, byte[]> files) throws Exception {
        var result = new LinkedHashMap<String, String>();
        for (var e : files.entrySet()) result.put(e.getKey(), hex(sha(e.getValue())));
        return result;
    }
}
