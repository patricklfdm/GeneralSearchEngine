package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Modifier;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;

class V50PublicApiInventoryTest {
    private static final String PACKAGE =
            "io.github.patricklfdm.generalsearch.replication";

    @Test
    void reflectionInventoryMatchesTheFrozenTopLevelPublicSurface() throws Exception {
        Map<String, String> expected = loadInventory();
        Set<String> actual = compiledTopLevelTypes();
        assertEquals(expected.keySet(), actual,
                "update the reviewed reflection fixture when the public surface changes");
        for (Map.Entry<String, String> entry : expected.entrySet()) {
            Class<?> type = Class.forName(entry.getKey());
            assertTrue(Modifier.isPublic(type.getModifiers()), entry.getKey());
            assertEquals(entry.getValue(), kind(type), entry.getKey());
        }
    }

    private Map<String, String> loadInventory() throws Exception {
        var resource = getClass().getResourceAsStream(
                "/compatibility/v50-replication-public-api-v1.txt");
        if (resource == null) {
            throw new IllegalStateException("public API inventory is absent");
        }
        Map<String, String> inventory = new LinkedHashMap<>();
        try (resource; var reader = new java.io.BufferedReader(
                new java.io.InputStreamReader(resource, java.nio.charset.StandardCharsets.UTF_8))) {
            for (String line; (line = reader.readLine()) != null;) {
                if (line.isBlank() || line.startsWith("#")) {
                    continue;
                }
                String[] fields = line.split(" ", 2);
                inventory.put(fields[1], fields[0]);
            }
        }
        return inventory;
    }

    private Set<String> compiledTopLevelTypes() throws Exception {
        URI classesRoot = ReplicationNodeId.class.getProtectionDomain()
                .getCodeSource().getLocation().toURI();
        Path packageDirectory = Path.of(classesRoot)
                .resolve(PACKAGE.replace('.', '/'));
        try (var paths = Files.list(packageDirectory)) {
            return paths
                    .map(path -> path.getFileName().toString())
                    .filter(name -> name.endsWith(".class"))
                    .filter(name -> !name.contains("$"))
                    .filter(name -> !name.equals("package-info.class"))
                    .map(name -> PACKAGE + "." + name.substring(0, name.length() - 6))
                    .collect(Collectors.toCollection(TreeSet::new));
        }
    }

    private String kind(Class<?> type) {
        if (type.isRecord()) {
            return "record";
        }
        if (type.isEnum()) {
            return "enum";
        }
        if (type.isInterface()) {
            return "interface";
        }
        return "class";
    }
}
