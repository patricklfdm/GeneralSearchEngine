package io.github.patricklfdm.generalsearch.processor;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.AnnotatedSchemaFactory;
import io.github.patricklfdm.generalsearch.schema.AnnotatedSearchConfiguration;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class SearchFieldsProcessorTest {
    @TempDir
    Path temporaryDirectory;

    @Test
    void generatedRecordFieldsSchemaAndIndexesMatchRuntimeFactory() throws Exception {
        String source = """
                package fixture;

                import io.github.patricklfdm.generalsearch.schema.annotation.IndexType;
                import io.github.patricklfdm.generalsearch.schema.annotation.SearchId;
                import io.github.patricklfdm.generalsearch.schema.annotation.SearchIndex;

                public record CatalogItem(
                        @SearchId int id,
                        @SearchIndex(IndexType.EQUALITY) String category,
                        boolean active
                ) {}
                """;
        Compilation compilation = compile(
                temporaryDirectory.resolve("record"),
                "fixture.CatalogItem",
                source);
        assertTrue(compilation.success(), compilation::diagnosticsText);

        String generated = Files.readString(compilation.generatedSource(
                "fixture/CatalogItemSearchFields.java"));
        assertTrue(generated.contains("Field<fixture.CatalogItem, java.lang.Integer> ID"));
        assertTrue(generated.contains("Field<fixture.CatalogItem, java.lang.Boolean> ACTIVE"));
        assertTrue(generated.contains("IndexDefinition.equality(CATEGORY)"));

        try (URLClassLoader loader = compilation.classLoader()) {
            Class<?> documentType = loader.loadClass("fixture.CatalogItem");
            Class<?> fieldsType = loader.loadClass("fixture.CatalogItemSearchFields");
            Object document = documentType
                    .getConstructor(int.class, String.class, boolean.class)
                    .newInstance(7, "books", true);

            @SuppressWarnings("unchecked")
            SearchSchema<Object, Integer> generatedSchema =
                    (SearchSchema<Object, Integer>) fieldsType
                            .getField("SCHEMA").get(null);
            @SuppressWarnings({"rawtypes", "unchecked"})
            AnnotatedSearchConfiguration<Object, Integer> runtime =
                    AnnotatedSchemaFactory.create((Class) documentType, Integer.class);

            assertEquals(runtime.schema().fields().keySet(),
                    generatedSchema.fields().keySet());
            for (String name : runtime.schema().fields().keySet()) {
                Field<Object, ?> expected = runtime.schema().requireField(name);
                Field<Object, ?> actual = generatedSchema.requireField(name);
                assertEquals(expected.valueType(), actual.valueType());
                assertEquals(expected.valueOf(document), actual.valueOf(document));
            }
            assertSame(fieldsType.getField("ID").get(null), generatedSchema.idField());

            @SuppressWarnings("unchecked")
            List<IndexDefinition<Object>> generatedIndexes =
                    (List<IndexDefinition<Object>>) fieldsType
                            .getField("INDEX_DEFINITIONS").get(null);
            assertEquals(runtime.indexDefinitions().size(), generatedIndexes.size());
            assertEquals(runtime.indexDefinitions().getFirst().field().name(),
                    generatedIndexes.getFirst().field().name());
            assertSame(fieldsType.getField("CATEGORY").get(null),
                    generatedIndexes.getFirst().field());
        }
    }

    @Test
    void supportsAccessibleClassGettersAndStableNestedNaming() throws Exception {
        String classSource = """
                package fixture;

                import io.github.patricklfdm.generalsearch.schema.annotation.IndexType;
                import io.github.patricklfdm.generalsearch.schema.annotation.SearchId;
                import io.github.patricklfdm.generalsearch.schema.annotation.SearchIndex;

                public final class Customer {
                    private final long id;
                    private final String region;

                    public Customer(long id, String region) {
                        this.id = id;
                        this.region = region;
                    }

                    @SearchId public long getId() { return id; }
                    @SearchIndex(IndexType.PREFIX)
                    public String getRegion() { return region; }
                    public int ignored() { return 1; }
                }
                """;
        Compilation classCompilation = compile(
                temporaryDirectory.resolve("class"),
                "fixture.Customer",
                classSource);
        assertTrue(classCompilation.success(), classCompilation::diagnosticsText);
        String generated = Files.readString(classCompilation.generatedSource(
                "fixture/CustomerSearchFields.java"));
        assertTrue(generated.contains("Customer::getId"));
        assertTrue(generated.contains("Customer::getRegion"));
        assertFalse(generated.contains("IGNORED"));

        String nestedSource = """
                package fixture;

                import io.github.patricklfdm.generalsearch.schema.annotation.SearchId;

                public final class Envelope {
                    public record Entry(@SearchId long id, String value) {}
                }
                """;
        Compilation nested = compile(
                temporaryDirectory.resolve("nested"),
                "fixture.Envelope",
                nestedSource);
        assertTrue(nested.success(), nested::diagnosticsText);
        assertTrue(Files.exists(nested.generatedSource(
                "fixture/Envelope_EntrySearchFields.java")));
    }

    @Test
    void generatedSourceIsDeterministicAcrossRebuilds() throws Exception {
        String source = """
                package fixture;
                import io.github.patricklfdm.generalsearch.schema.annotation.SearchId;
                public record Stable(@SearchId int id, String zeta, long alpha) {}
                """;
        Compilation first = compile(
                temporaryDirectory.resolve("first"),
                "fixture.Stable",
                source);
        Compilation second = compile(
                temporaryDirectory.resolve("second"),
                "fixture.Stable",
                source);
        assertTrue(first.success(), first::diagnosticsText);
        assertTrue(second.success(), second::diagnosticsText);
        assertEquals(
                Files.readString(first.generatedSource(
                        "fixture/StableSearchFields.java")),
                Files.readString(second.generatedSource(
                        "fixture/StableSearchFields.java")));
    }

    @Test
    void reportsStableDiagnosticsForUnsupportedOrCollidingModels() throws Exception {
        Compilation collision = compile(
                temporaryDirectory.resolve("collision"),
                "fixture.Collision",
                """
                        package fixture;
                        import io.github.patricklfdm.generalsearch.schema.annotation.SearchId;
                        public record Collision(
                                @SearchId int id,
                                int fooBar,
                                int foo_bar
                        ) {}
                        """);
        assertFalse(collision.success());
        assertTrue(collision.diagnosticsText().contains(
                "GSE008 generated constant-name collision: FOO_BAR"));

        Compilation privateMember = compile(
                temporaryDirectory.resolve("private"),
                "fixture.PrivateMember",
                """
                        package fixture;
                        import io.github.patricklfdm.generalsearch.schema.annotation.SearchId;
                        public final class PrivateMember {
                            @SearchId private final int id = 1;
                        }
                        """);
        assertFalse(privateMember.success());
        assertTrue(privateMember.diagnosticsText().contains(
                "GSE005 private annotated members"));

        Compilation generic = compile(
                temporaryDirectory.resolve("generic"),
                "fixture.GenericField",
                """
                        package fixture;
                        import java.util.List;
                        import io.github.patricklfdm.generalsearch.schema.annotation.SearchId;
                        public record GenericField(@SearchId int id, List<String> tags) {}
                        """);
        assertFalse(generic.success());
        assertTrue(generic.diagnosticsText().contains(
                "GSE006 parameterized field types require the runtime reflection factory"));
    }

    private Compilation compile(Path root, String typeName, String source)
            throws IOException {
        Path sourceRoot = Files.createDirectories(root.resolve("source"));
        Path classes = Files.createDirectories(root.resolve("classes"));
        Path generated = Files.createDirectories(root.resolve("generated"));
        Path sourceFile = sourceRoot.resolve(typeName.replace('.', '/') + ".java");
        Files.createDirectories(sourceFile.getParent());
        Files.writeString(sourceFile, source);

        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        boolean success;
        try (StandardJavaFileManager files = compiler.getStandardFileManager(
                diagnostics,
                Locale.ROOT,
                null)) {
            Iterable<? extends JavaFileObject> units =
                    files.getJavaFileObjects(sourceFile.toFile());
            List<String> options = List.of(
                    "--release", "21",
                    "-classpath", System.getProperty("java.class.path"),
                    "-processor", SearchFieldsProcessor.class.getName(),
                    "-d", classes.toString(),
                    "-s", generated.toString());
            success = Boolean.TRUE.equals(compiler.getTask(
                    null,
                    files,
                    diagnostics,
                    options,
                    null,
                    units).call());
        }
        List<String> messages = diagnostics.getDiagnostics().stream()
                .sorted(Comparator.comparingLong(Diagnostic::getLineNumber))
                .map(diagnostic -> diagnostic.getKind() + ":"
                        + diagnostic.getLineNumber() + ":"
                        + diagnostic.getMessage(Locale.ROOT))
                .toList();
        return new Compilation(success, classes, generated, messages);
    }

    private record Compilation(
            boolean success,
            Path classes,
            Path generated,
            List<String> diagnostics
    ) {
        private Path generatedSource(String relativePath) {
            return generated.resolve(relativePath);
        }

        private String diagnosticsText() {
            return String.join("\n", diagnostics);
        }

        private URLClassLoader classLoader() throws IOException {
            return new URLClassLoader(
                    new URL[]{classes.toUri().toURL()},
                    SearchFieldsProcessorTest.class.getClassLoader());
        }
    }
}
