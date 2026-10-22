package io.github.patricklfdm.generalsearch.replication;

import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Byte production only; no voting or physical-storage acceptance claim. */
public final class V53FormatWorker {
    private V53FormatWorker() {}
    public static void main(String[] args) throws Exception {
        var rows = new ArrayList<Map<String,Object>>();
        for (Object item : list(V53FormatTest.fixtures().get("fixtures"))) {
            var fixture = object(item); String family = (String) fixture.get("family"), name = (String) fixture.get("name");
            byte[] bytes = encode(family, name, object(fixture.get("value")));
            rows.add(Map.of("family", family, "name", name, "hex", HexFormat.of().formatHex(bytes), "sha256", hash(bytes)));
        }
        Path output = Path.of(args[0]);
        Files.write(output, canonical(Map.of("schema", "gse-v53-java-format-output-v1", "fixtures", rows), FRAME), StandardOpenOption.CREATE_NEW);
        System.out.println("{\"status\":\"PASS\",\"syntaxFixtures\":"+rows.size()+",\"runtimeEnabled\":false}");
    }
}
