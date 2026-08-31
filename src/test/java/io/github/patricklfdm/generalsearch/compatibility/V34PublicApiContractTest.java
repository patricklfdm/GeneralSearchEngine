package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.SimpleJavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchPageRequest;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import org.junit.jupiter.api.Test;

/** Freezes V3.4 as a zero-addition line over the complete V3.3 facade. */
class V34PublicApiContractTest {
    private static final String FIXTURE =
            "/compatibility/V34PublicApiConsumer.java.fixture";

    @Test
    void engineRetainsOnlyTheThreePublishedV3SearchEntryPoints() {
        Set<Class<?>> requestTypes = Arrays.stream(SearchEngine.class.getMethods())
                .filter(method -> method.getName().equals("search"))
                .filter(method -> method.getParameterCount() == 1)
                .map(method -> method.getParameterTypes()[0])
                .filter(type -> type.getPackageName().equals(
                        "io.github.patricklfdm.generalsearch.search"))
                .collect(Collectors.toUnmodifiableSet());

        assertEquals(Set.of(
                SearchRequest.class,
                HighlightedSearchRequest.class,
                SearchPageRequest.class
        ), requestTypes);
    }

    @Test
    void noV34HardeningFacadeIsPublished() {
        List<String> forbidden = List.of(
                "FinalHardeningRequest",
                "ColdBuildRequest",
                "HeapDiagnosticRequest",
                "MutationBurstRequest"
        );
        for (String simpleName : forbidden) {
            assertThrows(ClassNotFoundException.class, () -> Class.forName(
                    "io.github.patricklfdm.generalsearch.search." + simpleName
            ));
        }
    }

    @Test
    void thirdPartyFixtureUsesOnlyPublishedV33Capabilities() throws Exception {
        String source = readFixture();
        assertTrue(source.contains("class V34PublicApiConsumer"));
        assertTrue(source.contains("SearchRequest.<Document>builder()"));
        assertTrue(source.contains("HighlightedSearchRequest"));
        assertTrue(source.contains("SearchPageRequest"));
        assertFalse(source.contains("HardeningRequest"));
        compileFixture(source);
    }

    private static String readFixture() throws IOException {
        try (InputStream input = V34PublicApiContractTest.class
                .getResourceAsStream(FIXTURE)) {
            assertNotNull(input, FIXTURE);
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    private static void compileFixture(String source) throws IOException {
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        assertNotNull(compiler, "a full JDK is required");
        DiagnosticCollector<JavaFileObject> diagnostics =
                new DiagnosticCollector<>();
        Path output = Path.of("target", "v34-public-api-fixture");
        Files.createDirectories(output);
        JavaFileObject sourceObject = new SimpleJavaFileObject(
                URI.create("string:///fixture/V34PublicApiConsumer.java"),
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
                            "--release", "21",
                            "-classpath", System.getProperty("java.class.path"),
                            "-d", output.toString()
                    ),
                    null,
                    List.of(sourceObject)
            ).call();
            assertTrue(success, diagnostics.getDiagnostics().toString());
        }
    }
}
