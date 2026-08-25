package io.github.patricklfdm.generalsearch.analysis;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import java.util.stream.IntStream;
import org.junit.jupiter.api.Test;

class SimpleAnalyzerTest {
    private final Analyzer analyzer = Analyzer.simple();

    @Test
    void appliesDocumentedUnicodeCaseAndBoundaryRules() {
        assertEquals(List.of(), terms(null));
        assertEquals(List.of(), terms(" \t—!!!"));
        assertEquals(
                List.of("café", "java", "21", "straße"),
                terms("Café ＪＡＶＡ-21, Straße")
        );
        assertEquals(List.of("你好", "世界"), terms("你好，世界"));
        assertEquals(List.of("repeat", "repeat"), terms("Repeat...REPEAT"));
    }

    @Test
    void isDeterministicUnderConcurrentUse() {
        List<String> expected = terms("Ｆｕｌｌ-Text SEARCH 2026");
        IntStream.range(0, 10_000).parallel().forEach(ignored ->
                assertEquals(expected, terms("Ｆｕｌｌ-Text SEARCH 2026"))
        );
    }

    @Test
    void tokenRejectsEmptyTerms() {
        assertThrows(IllegalArgumentException.class, () -> new Token(""));
        assertThrows(IllegalArgumentException.class, () -> new Token(null));
    }

    private List<String> terms(String text) {
        return analyzer.analyze(text).stream().map(Token::term).toList();
    }
}
