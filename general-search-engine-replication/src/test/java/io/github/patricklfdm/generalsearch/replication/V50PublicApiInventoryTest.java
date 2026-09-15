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
                "/compatibility/v50-replication-public-signatures-v1.txt")) {
            if (resource == null) {
                throw new IllegalStateException("public signature fixture is absent");
            }
            String expected = new String(resource.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
            assertEquals(expected, signatures(),
                    "review every constructor, method, generic, record component, enum and constant change");
        }
    }

    private String signatures() throws Exception {
        Set<String> declarations = new TreeSet<>();
        for (String name : compiledTopLevelTypes()) {
            collectSignatures(Class.forName(name), declarations);
        }
        return String.join("\n", declarations) + "\n";
    }

    private void collectSignatures(Class<?> type, Set<String> declarations) throws Exception {
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
        System.out.print(new V50PublicApiInventoryTest().signatures());
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
