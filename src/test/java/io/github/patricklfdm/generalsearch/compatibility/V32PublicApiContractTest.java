package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.lang.reflect.RecordComponent;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.SimpleJavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import org.junit.jupiter.api.Test;

/**
 * Pre-implementation descriptor and source fixture for the two additive V3.2 API
 * families. Each family may be wholly absent in its preceding phase, but a partial or
 * descriptor-drifting implementation fails immediately once any family type appears.
 */
class V32PublicApiContractTest {
    private static final String ANALYSIS_PACKAGE =
            "io.github.patricklfdm.generalsearch.analysis.";
    private static final String SEARCH_PACKAGE =
            "io.github.patricklfdm.generalsearch.search.";
    private static final String SOURCE_FIXTURE =
            "/compatibility/V32PublicApiConsumer.java.fixture";

    @Test
    void publishedAnalyzerAndPositionTokenShapeRemainFrozen() {
        assertTrue(Analyzer.class.isAnnotationPresent(FunctionalInterface.class));
        assertEquals(1, Arrays.stream(Analyzer.class.getMethods())
                .filter(method -> Modifier.isAbstract(method.getModifiers()))
                .count());
        assertEquals(List.of("term", "positionIncrement"), Arrays.stream(
                        AnalyzedToken.class.getRecordComponents())
                .map(RecordComponent::getName)
                .toList());
    }

    @Test
    void offsetAnalysisFamilyIsAbsentOrExactlyComplete() throws Exception {
        Optional<Class<?>> analyzer = load(ANALYSIS_PACKAGE + "OffsetAnalyzer");
        Optional<Class<?>> token = load(ANALYSIS_PACKAGE + "OffsetAnalyzedToken");
        assertEquals(analyzer.isPresent(), token.isPresent(),
                "the offset-analysis family must appear atomically");
        if (analyzer.isEmpty()) {
            return;
        }

        Class<?> analyzerType = analyzer.orElseThrow();
        Class<?> tokenType = token.orElseThrow();
        assertTrue(analyzerType.isInterface());
        assertTrue(Modifier.isPublic(analyzerType.getModifiers()));
        assertTrue(Analyzer.class.isAssignableFrom(analyzerType));
        assertTrue(analyzerType.isAnnotationPresent(FunctionalInterface.class));

        List<Method> abstractMethods = Arrays.stream(analyzerType.getMethods())
                .filter(method -> Modifier.isAbstract(method.getModifiers()))
                .toList();
        assertEquals(1, abstractMethods.size());
        assertMethod(
                analyzerType,
                "analyzeWithOffsets",
                List.class,
                String.class
        );
        assertTrue(analyzerType.getMethod("analyze", String.class).isDefault());
        assertTrue(analyzerType.getMethod(
                "analyzeWithPositions",
                String.class
        ).isDefault());
        assertTrue(analyzerType.isAssignableFrom(SimpleAnalyzer.class));

        assertTrue(tokenType.isRecord());
        assertTrue(Modifier.isPublic(tokenType.getModifiers()));
        assertTrue(Modifier.isFinal(tokenType.getModifiers()));
        assertRecord(
                tokenType,
                List.of("term", "positionIncrement", "startOffset", "endOffset"),
                List.of(String.class, int.class, int.class, int.class)
        );
        assertConstructor(
                tokenType,
                String.class,
                int.class,
                int.class,
                int.class
        );
    }

    @Test
    void highlightedSearchFamilyIsAbsentOrExactlyComplete() throws Exception {
        List<String> names = List.of(
                "HighlightedSearchRequest",
                "HighlightedSearchResult",
                "HighlightedSearchHit",
                "FieldHighlight",
                "HighlightFragment",
                "HighlightSpan"
        );
        List<Class<?>> present = new ArrayList<>();
        for (String name : names) {
            load(SEARCH_PACKAGE + name).ifPresent(present::add);
        }
        assertTrue(present.isEmpty() || present.size() == names.size(),
                "the highlighted-search family must appear atomically");
        if (present.isEmpty()) {
            assertFalse(Arrays.stream(SearchEngine.class.getMethods())
                    .anyMatch(method -> method.getName().equals("search")
                            && method.getParameterCount() == 1
                            && method.getParameterTypes()[0].getName().equals(
                                    SEARCH_PACKAGE + "HighlightedSearchRequest")));
            return;
        }

        Class<?> request = require(SEARCH_PACKAGE + "HighlightedSearchRequest");
        Class<?> builder = require(
                SEARCH_PACKAGE + "HighlightedSearchRequest$Builder");
        Class<?> result = require(SEARCH_PACKAGE + "HighlightedSearchResult");
        Class<?> hit = require(SEARCH_PACKAGE + "HighlightedSearchHit");
        Class<?> field = require(SEARCH_PACKAGE + "FieldHighlight");
        Class<?> fragment = require(SEARCH_PACKAGE + "HighlightFragment");
        Class<?> span = require(SEARCH_PACKAGE + "HighlightSpan");
        List<Class<?>> allTypes = List.of(
                request,
                builder,
                result,
                hit,
                field,
                fragment,
                span
        );
        allTypes.forEach(type -> {
            assertTrue(Modifier.isPublic(type.getModifiers()), type.getName());
            assertTrue(Modifier.isFinal(type.getModifiers()), type.getName());
        });

        assertEquals(0, Arrays.stream(request.getConstructors()).count());
        assertMethod(request, "builder", builder,
                require(SEARCH_PACKAGE + "SearchRequest"));
        assertMethod(request, "searchRequest",
                require(SEARCH_PACKAGE + "SearchRequest"));
        assertMethod(request, "fields", List.class);
        assertMethod(request, "contextCharacters", int.class);
        assertMethod(request, "maxFragmentsPerField", int.class);
        assertMethod(builder, "field", builder,
                require("io.github.patricklfdm.generalsearch.schema.TextField"));
        assertMethod(builder, "contextCharacters", builder, int.class);
        assertMethod(builder, "maxFragmentsPerField", builder, int.class);
        assertMethod(builder, "build", request);

        assertConstructor(result, List.class);
        assertMethod(result, "hits", List.class);
        assertConstructor(hit,
                require("io.github.patricklfdm.generalsearch.ranking.SearchHit"),
                List.class);
        assertMethod(hit, "hit",
                require("io.github.patricklfdm.generalsearch.ranking.SearchHit"));
        assertMethod(hit, "highlights", List.class);
        assertConstructor(field, String.class, List.class);
        assertMethod(field, "fieldName", String.class);
        assertMethod(field, "fragments", List.class);
        assertConstructor(fragment,
                int.class,
                int.class,
                String.class,
                List.class);
        assertMethod(fragment, "startOffset", int.class);
        assertMethod(fragment, "endOffset", int.class);
        assertMethod(fragment, "text", String.class);
        assertMethod(fragment, "spans", List.class);
        assertConstructor(span, int.class, int.class);
        assertMethod(span, "startOffset", int.class);
        assertMethod(span, "endOffset", int.class);

        Method engineSearch = SearchEngine.class.getMethod("search", request);
        assertTrue(engineSearch.isDefault());
        assertEquals(result, engineSearch.getReturnType());
    }

    @Test
    void sourceFixtureFreezesTheSupportedConstructionPath() throws Exception {
        String source = readFixture();
        assertTrue(source.contains("OffsetAnalyzer analyzer = text ->"));
        assertTrue(source.contains("new OffsetAnalyzedToken("));
        assertTrue(source.contains("HighlightedSearchRequest.<Document>builder("));
        assertTrue(source.contains("new HighlightedSearchResult<>("));

        if (load(ANALYSIS_PACKAGE + "OffsetAnalyzer").isPresent()
                && load(SEARCH_PACKAGE + "HighlightedSearchRequest").isPresent()) {
            compileFixture(source);
        }
    }

    private static Optional<Class<?>> load(String name) {
        try {
            return Optional.of(Class.forName(name));
        } catch (ClassNotFoundException missing) {
            return Optional.empty();
        }
    }

    private static Class<?> require(String name) throws ClassNotFoundException {
        return Class.forName(name);
    }

    private static void assertRecord(
            Class<?> type,
            List<String> names,
            List<Class<?>> types
    ) {
        RecordComponent[] components = type.getRecordComponents();
        assertEquals(names, Arrays.stream(components)
                .map(RecordComponent::getName)
                .toList());
        assertEquals(types, Arrays.stream(components)
                .map(RecordComponent::getType)
                .toList());
    }

    private static void assertMethod(
            Class<?> owner,
            String name,
            Class<?> returnType,
            Class<?>... parameterTypes
    ) throws Exception {
        Method method = owner.getMethod(name, parameterTypes);
        assertEquals(returnType, method.getReturnType(), method.toGenericString());
    }

    private static void assertConstructor(
            Class<?> owner,
            Class<?>... parameterTypes
    ) throws Exception {
        Constructor<?> constructor = owner.getConstructor(parameterTypes);
        assertNotNull(constructor);
    }

    private static String readFixture() throws IOException {
        try (InputStream input = V32PublicApiContractTest.class
                .getResourceAsStream(SOURCE_FIXTURE)) {
            assertNotNull(input, SOURCE_FIXTURE);
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    private static void compileFixture(String source) throws IOException {
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        assertNotNull(compiler, "a full JDK is required");
        DiagnosticCollector<JavaFileObject> diagnostics =
                new DiagnosticCollector<>();
        Path output = Path.of("target", "v32-public-api-fixture");
        Files.createDirectories(output);
        JavaFileObject sourceObject = new SimpleJavaFileObject(
                URI.create("string:///fixture/V32PublicApiConsumer.java"),
                JavaFileObject.Kind.SOURCE
        ) {
            @Override
            public CharSequence getCharContent(boolean ignoreEncodingErrors) {
                return source;
            }
        };
        try (StandardJavaFileManager files = compiler.getStandardFileManager(
                diagnostics,
                null,
                StandardCharsets.UTF_8
        )) {
            boolean success = compiler.getTask(
                    null,
                    files,
                    diagnostics,
                    List.of(
                            "--release",
                            "21",
                            "-classpath",
                            System.getProperty("java.class.path"),
                            "-d",
                            output.toString()
                    ),
                    null,
                    List.of(sourceObject)
            ).call();
            assertTrue(success, diagnostics.getDiagnostics().toString());
        }
    }
}
