package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Random;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import org.junit.jupiter.api.Test;

class OffsetTokenSequenceValidatorTest {
    private static final OffsetAnalyzer SIMPLE = (OffsetAnalyzer) Analyzer.simple();

    @Test
    void acceptsGapsAlternativesAndMonotonicOverlapAcrossPositions() {
        List<OffsetAnalyzedToken> source = new ArrayList<>(List.of(
                token("first", 1, 0, 4),
                token("alternative", 0, 0, 4),
                token("expanded-next", 1, 0, 4),
                token("crossing", 1, 2, 6),
                token("after-gap", 3, 7, 12)
        ));

        List<OffsetAnalyzedToken> validated =
                OffsetTokenSequenceValidator.validate("body", "word   later", source);

        assertEquals(source, validated);
        source.clear();
        assertEquals(5, validated.size());
        assertThrows(UnsupportedOperationException.class, () ->
                validated.add(token("extra", 1, 0, 1)));
    }

    @Test
    void acceptsBuiltInMultiTokenCompatibilityExpansion() {
        List<OffsetAnalyzedToken> output = SIMPLE.analyzeWithOffsets("\uFDFA");

        assertEquals(output, OffsetTokenSequenceValidator.validate(
                "body",
                "\uFDFA",
                output
        ));
    }

    @Test
    void rejectsNullOutputElementAndInvalidFirstPosition() {
        assertFieldFailure(-1, () -> OffsetTokenSequenceValidator.validate(
                "body",
                "a",
                null
        ));
        assertFieldFailure(1, () -> OffsetTokenSequenceValidator.validate(
                "body",
                "ab",
                Arrays.asList(token("a", 1, 0, 1), null)
        ));
        assertFieldFailure(0, () -> OffsetTokenSequenceValidator.validate(
                "body",
                "a",
                List.of(token("a", 0, 0, 1))
        ));
    }

    @Test
    void rejectsOutOfBoundsAndSplitSurrogateRanges() {
        assertFieldFailure(0, () -> OffsetTokenSequenceValidator.validate(
                "body",
                "a",
                List.of(token("a", 1, 0, 2))
        ));
        assertFieldFailure(0, () -> OffsetTokenSequenceValidator.validate(
                "body",
                "a\uD83D\uDE00b",
                List.of(token("broken", 1, 1, 2))
        ));
        assertFieldFailure(0, () -> OffsetTokenSequenceValidator.validate(
                "body",
                "a\uD83D\uDE00b",
                List.of(token("broken", 1, 2, 4))
        ));
    }

    @Test
    void rejectsSamePositionMismatchAndEitherBoundaryMovingBackward() {
        assertFieldFailure(1, () -> OffsetTokenSequenceValidator.validate(
                "body",
                "abcdef",
                List.of(
                        token("first", 1, 0, 3),
                        token("alternative", 0, 0, 2)
                )
        ));
        assertFieldFailure(1, () -> OffsetTokenSequenceValidator.validate(
                "body",
                "abcdef",
                List.of(
                        token("first", 1, 1, 3),
                        token("start-backward", 1, 0, 4)
                )
        ));
        assertFieldFailure(1, () -> OffsetTokenSequenceValidator.validate(
                "body",
                "abcdef",
                List.of(
                        token("first", 1, 0, 5),
                        token("end-backward", 1, 1, 4)
                )
        ));
    }

    @Test
    void rejectsLogicalPositionOverflowWithTokenContext() {
        assertFieldFailure(2, () -> OffsetTokenSequenceValidator.validate(
                "body",
                "abc",
                List.of(
                        token("a", Integer.MAX_VALUE, 0, 1),
                        token("b", 1, 1, 2),
                        token("c", 1, 2, 3)
                )
        ));
    }

    @Test
    void randomizedUnicodeOutputPreservesOrdinaryViewsAndValidRanges() {
        long seed = 0x32A11CE5L;
        Random random = new Random(seed);
        int[] palette = {
                'A', 'z', '0', ' ', '-', 0x00E9, 0x0301, 0x2460, 0x00BD,
                0xFB03, 0xFDFA, 0x1100, 0x1161, 0x10400, 0x1F600,
                0xD800, 0xDC00
        };
        for (int trial = 0; trial < 2_000; trial++) {
            StringBuilder source = new StringBuilder();
            int length = random.nextInt(32);
            for (int index = 0; index < length; index++) {
                int codePoint = random.nextBoolean()
                        ? palette[random.nextInt(palette.length)]
                        : random.nextInt(Character.MAX_CODE_POINT + 1);
                source.appendCodePoint(codePoint);
            }
            String text = source.toString();
            List<OffsetAnalyzedToken> output = SIMPLE.analyzeWithOffsets(text);
            List<OffsetAnalyzedToken> validated;
            try {
                validated = OffsetTokenSequenceValidator.validate(
                        "body",
                        text,
                        output
                );
            } catch (IllegalArgumentException failure) {
                throw new AssertionError(
                        "seed=" + seed
                                + " trial=" + trial
                                + " sourceCodePoints=" + text.codePoints()
                                        .boxed()
                                        .toList()
                                + " output=" + output,
                        failure
                );
            }

            assertEquals(Analyzer.simple().analyze(text), validated.stream()
                    .map(token -> new Token(token.term()))
                    .toList(), "seed=" + seed + " trial=" + trial);
            assertEquals(
                    Analyzer.simple().analyzeWithPositions(text),
                    validated.stream()
                            .map(token -> new AnalyzedToken(
                                    token.term(),
                                    token.positionIncrement()
                            ))
                            .toList(),
                    "seed=" + seed + " trial=" + trial
            );
            for (OffsetAnalyzedToken token : validated) {
                assertTrue(token.startOffset() < token.endOffset());
                assertTrue(token.endOffset() <= text.length());
            }
        }
    }

    private static void assertFieldFailure(int tokenIndex, Runnable invocation) {
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                invocation::run
        );
        assertTrue(failure.getMessage().contains("text field 'body'"));
        if (tokenIndex >= 0) {
            assertTrue(failure.getMessage().contains("token " + tokenIndex));
        }
    }

    private static OffsetAnalyzedToken token(
            String term,
            int increment,
            int start,
            int end
    ) {
        return new OffsetAnalyzedToken(term, increment, start, end);
    }
}
