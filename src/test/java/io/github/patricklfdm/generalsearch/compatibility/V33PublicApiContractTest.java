package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.OptionalLong;
import java.util.Set;
import java.util.stream.Collectors;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.SimpleJavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.exception.SearchEngineException;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchResult;
import org.junit.jupiter.api.Test;

/**
 * Pre-implementation descriptor and source fixture for the additive V3.3 page
 * family. The family may be wholly absent before implementation, but it may not
 * appear partially or with a descriptor that differs from the frozen contract.
 */
class V33PublicApiContractTest {
    private static final String SEARCH_PACKAGE =
            "io.github.patricklfdm.generalsearch.search.";
    private static final String EXCEPTION_PACKAGE =
            "io.github.patricklfdm.generalsearch.engine.exception.";
    private static final String SOURCE_FIXTURE =
            "/compatibility/V33PublicApiConsumer.java.fixture";

    @Test
    void existingOrdinarySearchModelsRemainFreeOfPageState() {
        assertEquals(Set.of(
                "builder", "of", "query", "filter", "limit", "bm25"),
                publicDeclaredMethodNames(SearchRequest.class));
        assertEquals(Set.of("hits"), publicDeclaredMethodNames(SearchResult.class));
        assertEquals(Set.of(
                "document", "score", "equals", "hashCode", "toString"),
                publicDeclaredMethodNames(SearchHit.class));
        assertFalse(Arrays.stream(SearchRequest.class.getDeclaredMethods())
                .anyMatch(method -> method.getName().equals("after")
                        || method.getName().equals("totalHits")));
    }

    @Test
    void pageFamilyIsAbsentOrExactlyComplete() throws Exception {
        List<String> names = List.of(
                SEARCH_PACKAGE + "SearchAfterCursor",
                SEARCH_PACKAGE + "TotalHitsMode",
                SEARCH_PACKAGE + "SearchPageRequest",
                SEARCH_PACKAGE + "SearchPageResult",
                EXCEPTION_PACKAGE + "SearchCursorException"
        );
        List<Class<?>> present = new ArrayList<>();
        for (String name : names) {
            load(name).ifPresent(present::add);
        }
        assertTrue(present.isEmpty() || present.size() == names.size(),
                "the V3.3 page family must appear atomically");
        if (present.isEmpty()) {
            assertFalse(Arrays.stream(SearchEngine.class.getMethods())
                    .anyMatch(method -> method.getName().equals("search")
                            && method.getParameterCount() == 1
                            && method.getParameterTypes()[0].getName().equals(
                                    SEARCH_PACKAGE + "SearchPageRequest")));
            return;
        }

        Class<?> cursor = require(SEARCH_PACKAGE + "SearchAfterCursor");
        Class<?> totalHitsMode = require(SEARCH_PACKAGE + "TotalHitsMode");
        Class<?> request = require(SEARCH_PACKAGE + "SearchPageRequest");
        Class<?> builder = require(SEARCH_PACKAGE + "SearchPageRequest$Builder");
        Class<?> result = require(SEARCH_PACKAGE + "SearchPageResult");
        Class<?> exception = require(EXCEPTION_PACKAGE + "SearchCursorException");
        Class<?> reason = require(EXCEPTION_PACKAGE + "SearchCursorException$Reason");

        assertTrue(cursor.isInterface());
        assertTrue(Modifier.isPublic(cursor.getModifiers()));
        assertEquals(0, cursor.getDeclaredMethods().length,
                "SearchAfterCursor is a zero-method marker");

        assertTrue(totalHitsMode.isEnum());
        assertTrue(Modifier.isPublic(totalHitsMode.getModifiers()));
        assertEquals(List.of("DISABLED", "EXACT"), enumNames(totalHitsMode));

        assertPublicFinal(request);
        assertPublicFinal(builder);
        assertTrue(Modifier.isStatic(builder.getModifiers()));
        assertEquals(request, builder.getEnclosingClass());
        assertEquals(0, request.getConstructors().length,
                "SearchPageRequest exposes no public constructor");
        assertMethod(request, "builder", builder, SearchRequest.class);
        assertStaticMethod(request, "builder", SearchRequest.class);
        assertMethod(request, "searchRequest", SearchRequest.class);
        assertMethod(request, "after", Optional.class);
        assertMethod(request, "totalHitsMode", totalHitsMode);
        assertMethod(builder, "after", builder, cursor);
        assertMethod(builder, "totalHits", builder, totalHitsMode);
        assertMethod(builder, "build", request);
        assertEquals(Set.of(
                signature("builder", SearchRequest.class),
                signature("searchRequest"),
                signature("after"),
                signature("totalHitsMode")
        ), publicDeclaredMethodSignatures(request));
        assertEquals(Set.of(
                signature("after", cursor),
                signature("totalHits", totalHitsMode),
                signature("build")
        ), publicDeclaredMethodSignatures(builder));

        assertPublicFinal(result);
        assertEquals(0, result.getConstructors().length,
                "SearchPageResult exposes no public constructor");
        assertMethod(result, "withoutTotalHits", result, List.class);
        assertMethod(result, "withoutTotalHits", result, List.class, cursor);
        assertMethod(result, "withExactTotalHits", result,
                List.class, long.class);
        assertMethod(result, "withExactTotalHits", result,
                List.class, cursor, long.class);
        assertStaticMethod(result, "withoutTotalHits", List.class);
        assertStaticMethod(result, "withoutTotalHits", List.class, cursor);
        assertStaticMethod(result, "withExactTotalHits", List.class, long.class);
        assertStaticMethod(result, "withExactTotalHits",
                List.class, cursor, long.class);
        assertMethod(result, "hits", List.class);
        assertMethod(result, "nextCursor", Optional.class);
        assertMethod(result, "totalHits", OptionalLong.class);
        assertEquals(Set.of(
                signature("withoutTotalHits", List.class),
                signature("withoutTotalHits", List.class, cursor),
                signature("withExactTotalHits", List.class, long.class),
                signature("withExactTotalHits", List.class, cursor, long.class),
                signature("hits"),
                signature("nextCursor"),
                signature("totalHits")
        ), publicDeclaredMethodSignatures(result));

        assertPublicFinal(exception);
        assertEquals(SearchEngineException.class, exception.getSuperclass());
        assertTrue(reason.isEnum());
        assertEquals(List.of(
                "UNSUPPORTED_CURSOR",
                "DIFFERENT_ENGINE",
                "DIFFERENT_REQUEST",
                "STALE_SNAPSHOT"
        ), enumNames(reason));
        assertEquals(1, exception.getConstructors().length);
        assertNotNull(exception.getConstructor(reason));
        assertMethod(exception, "reason", reason);
        assertEquals(Set.of(signature("reason")),
                publicDeclaredMethodSignatures(exception));

        Method engineSearch = SearchEngine.class.getMethod("search", request);
        assertTrue(engineSearch.isDefault());
        assertEquals(result, engineSearch.getReturnType());
    }

    @Test
    void sourceFixtureFreezesThirdPartyConstructionAndInvocationPaths()
            throws Exception {
        String source = readFixture();
        assertTrue(source.contains("implements SearchAfterCursor"));
        assertTrue(source.contains("SearchPageRequest.<Document>builder(request)"));
        assertTrue(source.contains("TotalHitsMode.EXACT"));
        assertTrue(source.contains("SearchPageResult.withoutTotalHits("));
        assertTrue(source.contains("SearchPageResult.withExactTotalHits("));

        if (load(SEARCH_PACKAGE + "SearchPageRequest").isPresent()) {
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

    private static void assertPublicFinal(Class<?> type) {
        assertTrue(Modifier.isPublic(type.getModifiers()), type.getName());
        assertTrue(Modifier.isFinal(type.getModifiers()), type.getName());
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

    private static void assertStaticMethod(
            Class<?> owner,
            String name,
            Class<?>... parameterTypes
    ) throws Exception {
        Method method = owner.getMethod(name, parameterTypes);
        assertTrue(Modifier.isStatic(method.getModifiers()), method.toGenericString());
    }

    private static Set<String> publicDeclaredMethodNames(Class<?> owner) {
        return Arrays.stream(owner.getDeclaredMethods())
                .filter(method -> Modifier.isPublic(method.getModifiers()))
                .filter(method -> !method.isSynthetic())
                .map(Method::getName)
                .collect(Collectors.toUnmodifiableSet());
    }

    private static Set<String> publicDeclaredMethodSignatures(Class<?> owner) {
        return Arrays.stream(owner.getDeclaredMethods())
                .filter(method -> Modifier.isPublic(method.getModifiers()))
                .filter(method -> !method.isSynthetic())
                .map(method -> signature(
                        method.getName(),
                        method.getParameterTypes()
                ))
                .collect(Collectors.toUnmodifiableSet());
    }

    private static String signature(String name, Class<?>... parameterTypes) {
        return name + Arrays.stream(parameterTypes)
                .map(Class::getName)
                .collect(Collectors.joining(",", "(", ")"));
    }

    private static List<String> enumNames(Class<?> type) {
        return Arrays.stream(type.getEnumConstants())
                .map(constant -> ((Enum<?>) constant).name())
                .toList();
    }

    private static String readFixture() throws IOException {
        try (InputStream input = V33PublicApiContractTest.class
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
        Path output = Path.of("target", "v33-public-api-fixture");
        Files.createDirectories(output);
        JavaFileObject sourceObject = new SimpleJavaFileObject(
                URI.create("string:///fixture/V33PublicApiConsumer.java"),
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
