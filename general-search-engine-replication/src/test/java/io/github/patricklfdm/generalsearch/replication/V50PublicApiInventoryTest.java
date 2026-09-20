package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Modifier;
import java.lang.reflect.Field;
import java.lang.reflect.RecordComponent;
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
        actual.retainAll(expected.keySet()); // V5.1 separately checks the complete old + additive surface.
        assertEquals(expected.keySet(), actual,
                "update the reviewed reflection fixture when the public surface changes");
        for (Map.Entry<String, String> entry : expected.entrySet()) {
            Class<?> type = Class.forName(entry.getKey());
            assertTrue(Modifier.isPublic(type.getModifiers()), entry.getKey());
            assertEquals(entry.getValue(), kind(type), entry.getKey());
        }
    }

    @Test
    void completePublicDeclarationsMatchTheReviewedSignatureFixture() throws Exception {
        try (var resource = getClass().getResourceAsStream(
                "/compatibility/v50-replication-public-signatures-v2.txt")) {
            if (resource == null) {
                throw new IllegalStateException("public signature fixture is absent");
            }
            String expected = new String(resource.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
            assertEquals(expected, signatures(),
                    "review every constructor, method, generic, record component, enum and constant change");
        }
    }

    @Test
    void reviewedDeltaPreservesHistoricalDeclarationsAndOnlyChangesTheProtocolConstant() throws Exception {
        Set<String> oldLines = fixtureLines("v50-replication-public-signatures-v1.txt");
        Set<String> newLines = fixtureLines("v50-replication-public-signatures-v2.txt");
        Set<String> removed = new TreeSet<>(oldLines); removed.removeAll(newLines);
        assertEquals(Set.of("field public static final java.lang.String " + PACKAGE
                + ".ReplicatedSearchEngines.PROTOCOL = gse-replication/1.0"), removed);
        assertEquals(fixtureLines("v50-public-admission-signature-delta.txt"), delta(oldLines, newLines));
        Set<String> oldCore = fixtureLines("v50-core-handoff-signatures-v1.txt");
        Set<String> newCore = fixtureLines("v50-core-handoff-signatures-v2.txt");
        assertTrue(newCore.containsAll(oldCore), "all pre-amendment builder declarations survive");
        assertEquals(fixtureLines("v50-core-handoff-signature-delta.txt"), delta(oldCore, newCore));
        assertEquals(String.join("\n", newCore) + "\n", coreSignatures(true));
    }

    private Set<String> fixtureLines(String name) throws Exception {
        try (var input = getClass().getResourceAsStream("/compatibility/" + name)) {
            if (input == null) throw new IllegalStateException("missing fixture " + name);
            return new TreeSet<>(new String(input.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8).lines().toList());
        }
    }

    private Set<String> delta(Set<String> oldLines, Set<String> newLines) {
        Set<String> result = new TreeSet<>();
        oldLines.stream().filter(line -> !newLines.contains(line)).forEach(line -> result.add("- " + line));
        newLines.stream().filter(line -> !oldLines.contains(line)).forEach(line -> result.add("+ " + line));
        return result;
    }

    private String coreSignatures(boolean additions) throws Exception {
        Set<String> declarations = new TreeSet<>();
        collectSignatures(io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder.class, declarations);
        if (additions) {
            collectSignatures(Class.forName("io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration"), declarations);
            collectSignatures(Class.forName("io.github.patricklfdm.generalsearch.durability.DurableApplicationState"), declarations);
        }
        return String.join("\n", declarations) + "\n";
    }

    private String signatures() throws Exception {
        Set<String> declarations = new TreeSet<>();
        for (String name : loadInventory().keySet()) {
            collectSignatures(Class.forName(name), declarations);
        }
        return String.join("\n", declarations) + "\n";
    }

    void collectSignatures(Class<?> type, Set<String> declarations) throws Exception {
        if (!Modifier.isPublic(type.getModifiers()) && !Modifier.isProtected(type.getModifiers())) {
            return;
        }
        declarations.add("type " + type.toGenericString());
        if (type.getGenericSuperclass() != null) {
            declarations.add("super " + type.getName() + " " + type.getGenericSuperclass().getTypeName());
        }
        for (var implemented : type.getGenericInterfaces()) {
            declarations.add("interface " + type.getName() + " " + implemented.getTypeName());
        }
        for (var constructor : type.getDeclaredConstructors()) {
            if (visible(constructor.getModifiers()) && !constructor.isSynthetic()) {
                declarations.add("constructor " + constructor.toGenericString());
            }
        }
        for (var method : type.getDeclaredMethods()) {
            if (visible(method.getModifiers()) && !method.isSynthetic() && !method.isBridge()) {
                declarations.add("method " + method.toGenericString());
            }
        }
        for (Field field : type.getDeclaredFields()) {
            if (visible(field.getModifiers()) && !field.isSynthetic()) {
                String value = "";
                if (Modifier.isStatic(field.getModifiers()) && Modifier.isFinal(field.getModifiers())
                        && (field.getType().isPrimitive() || field.getType() == String.class)) {
                    value = " = " + field.get(null);
                }
                declarations.add("field " + field.toGenericString() + value);
            }
        }
        if (type.isRecord()) {
            RecordComponent[] components = type.getRecordComponents();
            for (int index = 0; index < components.length; index++) {
                var component = components[index];
                declarations.add("record-component " + type.getName() + " " + index + " "
                        + component.getGenericType().getTypeName() + " " + component.getName());
            }
        }
        if (type.isEnum()) {
            declarations.add("enum-values " + type.getName() + " "
                    + java.util.Arrays.stream(type.getEnumConstants())
                    .map(value -> ((Enum<?>) value).name()).collect(Collectors.joining(",")));
        }
        for (Class<?> nested : type.getDeclaredClasses()) {
            collectSignatures(nested, declarations);
        }
    }

    private boolean visible(int modifiers) {
        return Modifier.isPublic(modifiers) || Modifier.isProtected(modifiers);
    }

    /** Explicit fixture generation for review; tests never rewrite expected declarations. */
    public static void main(String[] args) throws Exception {
        var test = new V50PublicApiInventoryTest();
        System.out.print(args.length == 0 ? test.signatures() : test.coreSignatures(args[0].equals("core-v2")));
    }

    private Map<String, String> loadInventory() throws Exception {
        var resource = getClass().getResourceAsStream(
                "/compatibility/v50-replication-public-api-v2.txt");
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

    Set<String> compiledTopLevelTypes() throws Exception {
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
                    .filter(name -> {
                        try {
                            return Modifier.isPublic(Class.forName(name).getModifiers());
                        } catch (ClassNotFoundException error) {
                            throw new AssertionError(error);
                        }
                    })
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
