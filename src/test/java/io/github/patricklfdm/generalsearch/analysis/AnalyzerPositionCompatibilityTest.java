package io.github.patricklfdm.generalsearch.analysis;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class AnalyzerPositionCompatibilityTest {
    @Test
    void remainsAFunctionalInterfaceForLegacyLambdas() {
        Analyzer legacy = text -> List.of(new Token(text));

        assertEquals(List.of(new Token("legacy")), legacy.analyze("legacy"));
        assertEquals(1, Arrays.stream(Analyzer.class.getMethods())
                .filter(Method::isDefault)
                .filter(method -> method.getName().equals("analyzeWithPositions"))
                .count());
        assertEquals(1, Arrays.stream(Analyzer.class.getMethods())
                .filter(method -> Modifier.isAbstract(method.getModifiers()))
                .count());
    }

    @Test
    void defaultAdapterDelegatesOnceAndPreservesLegacyOutput() {
        AtomicInteger calls = new AtomicInteger();
        AtomicReference<String> received = new AtomicReference<>();
        String input = new String("original input");
        Analyzer legacy = text -> {
            calls.incrementAndGet();
            received.set(text);
            return List.of(new Token("Case"), new Token("Case"), new Token(" exact "));
        };

        List<AnalyzedToken> actual = legacy.analyzeWithPositions(input);

        assertEquals(1, calls.get());
        assertSame(input, received.get());
        assertEquals(List.of(
                new AnalyzedToken("Case", 1),
                new AnalyzedToken("Case", 1),
                new AnalyzedToken(" exact ", 1)
        ), actual);
        assertThrows(UnsupportedOperationException.class,
                () -> actual.add(new AnalyzedToken("extra", 1)));
    }

    @Test
    void defaultAdapterPassesNullAndPreservesEmptyOutput() {
        AtomicInteger calls = new AtomicInteger();
        AtomicReference<String> received = new AtomicReference<>("not-null");
        Analyzer legacy = text -> {
            calls.incrementAndGet();
            received.set(text);
            return List.of();
        };

        List<AnalyzedToken> actual = legacy.analyzeWithPositions(null);

        assertEquals(1, calls.get());
        assertNull(received.get());
        assertEquals(List.of(), actual);
        assertThrows(UnsupportedOperationException.class,
                () -> actual.add(new AnalyzedToken("extra", 1)));
    }

    @Test
    void defaultAdapterPropagatesLegacyExceptionUnchanged() {
        RuntimeException failure = new RuntimeException("legacy failure");
        Analyzer legacy = text -> {
            throw failure;
        };

        RuntimeException thrown = assertThrows(
                RuntimeException.class,
                () -> legacy.analyzeWithPositions("text")
        );

        assertSame(failure, thrown);
    }

    @Test
    void customOverrideCanEmitGapsAndSamePositionAlternatives() {
        Analyzer positioned = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return List.of(new Token("legacy"));
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return List.of(
                        new AnalyzedToken("first", 1),
                        new AnalyzedToken("after-gap", 3),
                        new AnalyzedToken("synonym", 0)
                );
            }
        };

        assertEquals(List.of(new Token("legacy")), positioned.analyze("ignored"));
        assertEquals(List.of(
                new AnalyzedToken("first", 1),
                new AnalyzedToken("after-gap", 3),
                new AnalyzedToken("synonym", 0)
        ), positioned.analyzeWithPositions("ignored"));
    }
}
