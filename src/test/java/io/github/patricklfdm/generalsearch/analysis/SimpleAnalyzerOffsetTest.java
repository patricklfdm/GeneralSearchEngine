package io.github.patricklfdm.generalsearch.analysis;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import java.util.stream.IntStream;
import org.junit.jupiter.api.Test;

class SimpleAnalyzerOffsetTest {
    private final Analyzer ordinary = Analyzer.simple();
    private final OffsetAnalyzer offset = assertInstanceOf(
            OffsetAnalyzer.class,
            ordinary
    );

    @Test
    void mapsAsciiCompatibilityAndRepeatedTermsToOriginalUtf16Ranges() {
        assertEquals(List.of(
                token("café", 0, 4),
                token("java", 5, 9),
                token("21", 10, 12),
                token("straße", 14, 20)
        ), offset.analyzeWithOffsets("Café ＪＡＶＡ-21, Straße"));

        assertEquals(List.of(
                token("repeat", 0, 6),
                token("repeat", 9, 15)
        ), offset.analyzeWithOffsets("Repeat...REPEAT"));
    }

    @Test
    void mapsComposedDecomposedHangulAndSupplementaryText() {
        assertEquals(List.of(
                token("é", 0, 1),
                token("é", 2, 4),
                token("가", 5, 7),
                token("\uD801\uDC28z", 8, 11)
        ), offset.analyzeWithOffsets(
                "é e\u0301 \u1100\u1161 \uD801\uDC00Z"
        ));
    }

    @Test
    void preservesContextSensitiveRootLowercaseOutput() {
        assertEquals(List.of(
                token("ος", 0, 2),
                token("οσα", 3, 6)
        ), offset.analyzeWithOffsets("ΟΣ ΟΣΑ"));
    }

    @Test
    void permitsSuccessiveTermsFromOneNfkcSourceRange() {
        assertEquals(List.of(
                token("صلى", 0, 1),
                token("الله", 0, 1),
                token("عليه", 0, 1),
                token("وسلم", 0, 1)
        ), offset.analyzeWithOffsets("\uFDFA"));
        assertEquals(List.of(
                token("1", 0, 1),
                token("2", 0, 1)
        ), offset.analyzeWithOffsets("½"));
    }

    @Test
    void treatsPunctuationAndUnpairedSurrogatesAsDelimiters() {
        assertEquals(List.of(
                token("a", 0, 1),
                token("b", 2, 3),
                token("c", 4, 5)
        ), offset.analyzeWithOffsets("a\uD800b\uDC00c"));
        assertEquals(List.of(), offset.analyzeWithOffsets("\uD800—\uDC00"));
    }

    @Test
    void nullEmptyAndDelimiterOnlyInputProduceImmutableEmptyOutput() {
        assertEquals(List.of(), offset.analyzeWithOffsets(null));
        assertEquals(List.of(), offset.analyzeWithOffsets(""));
        assertEquals(List.of(), offset.analyzeWithOffsets(" \t—!!!"));
        List<OffsetAnalyzedToken> output = offset.analyzeWithOffsets("word");
        assertThrows(UnsupportedOperationException.class, () ->
                output.add(token("extra", 0, 1)));
    }

    @Test
    void ordinaryProjectionsRemainBitForBitEquivalent() {
        List<String> fixtures = List.of(
                "",
                "Café ＪＡＶＡ-21, Straße",
                "é e\u0301 \u1100\u1161",
                "ΟΣ ΟΣΑ",
                "\uFDFA",
                "½",
                "a\uD800b\uDC00c",
                "\uD801\uDC00Z"
        );
        for (String source : fixtures) {
            List<OffsetAnalyzedToken> actual = offset.analyzeWithOffsets(source);
            assertEquals(ordinary.analyze(source), actual.stream()
                    .map(token -> new Token(token.term()))
                    .toList(), source);
            assertEquals(ordinary.analyzeWithPositions(source), actual.stream()
                    .map(token -> new AnalyzedToken(
                            token.term(),
                            token.positionIncrement()
                    ))
                    .toList(), source);
        }
    }

    @Test
    void remainsDeterministicUnderConcurrentUse() {
        String source = "Cafe\u0301 \uFDFA ½ \uD801\uDC00Z";
        List<OffsetAnalyzedToken> expected = offset.analyzeWithOffsets(source);

        IntStream.range(0, 5_000).parallel().forEach(ignored ->
                assertEquals(expected, offset.analyzeWithOffsets(source))
        );
    }

    private static OffsetAnalyzedToken token(
            String term,
            int start,
            int end
    ) {
        return new OffsetAnalyzedToken(term, 1, start, end);
    }
}
