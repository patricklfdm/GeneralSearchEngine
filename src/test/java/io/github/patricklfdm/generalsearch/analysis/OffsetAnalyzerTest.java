package io.github.patricklfdm.generalsearch.analysis;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class OffsetAnalyzerTest {
    @Test
    void defaultAdaptersDelegateOnceAndReturnImmutableProjections() {
        AtomicInteger calls = new AtomicInteger();
        AtomicReference<String> received = new AtomicReference<>();
        String source = new String("source");
        OffsetAnalyzer analyzer = text -> {
            calls.incrementAndGet();
            received.set(text);
            return List.of(
                    new OffsetAnalyzedToken("first", 1, 0, 3),
                    new OffsetAnalyzedToken("alternative", 0, 0, 3),
                    new OffsetAnalyzedToken("later", 2, 4, 6)
            );
        };

        List<Token> terms = analyzer.analyze(source);
        assertEquals(1, calls.get());
        assertSame(source, received.get());
        assertEquals(List.of(
                new Token("first"),
                new Token("alternative"),
                new Token("later")
        ), terms);
        assertThrows(UnsupportedOperationException.class, () ->
                terms.add(new Token("extra")));

        List<AnalyzedToken> positioned = analyzer.analyzeWithPositions(source);
        assertEquals(2, calls.get());
        assertEquals(List.of(
                new AnalyzedToken("first", 1),
                new AnalyzedToken("alternative", 0),
                new AnalyzedToken("later", 2)
        ), positioned);
        assertThrows(UnsupportedOperationException.class, () ->
                positioned.add(new AnalyzedToken("extra", 1)));
    }

    @Test
    void adaptersPassNullAndPreserveEmptyOutput() {
        AtomicReference<String> received = new AtomicReference<>("not-null");
        OffsetAnalyzer analyzer = text -> {
            received.set(text);
            return List.of();
        };

        assertEquals(List.of(), analyzer.analyze(null));
        assertNull(received.get());
        assertEquals(List.of(), analyzer.analyzeWithPositions(null));
        assertNull(received.get());
    }

    @Test
    void adaptersPropagateImplementationFailureUnchanged() {
        RuntimeException failure = new RuntimeException("offset failure");
        OffsetAnalyzer analyzer = text -> {
            throw failure;
        };

        assertSame(failure, assertThrows(RuntimeException.class, () ->
                analyzer.analyze("text")));
        assertSame(failure, assertThrows(RuntimeException.class, () ->
                analyzer.analyzeWithPositions("text")));
    }
}
