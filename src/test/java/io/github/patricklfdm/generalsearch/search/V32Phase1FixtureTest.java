package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import org.junit.jupiter.api.Test;

class V32Phase1FixtureTest {
    @Test
    void offsetFixturesFreezeOriginalUtf16RangesAndPositionRules() {
        String source = "Cafe\u0301 \u2460 \uD83D\uDE00Z";

        List<V32TestReference.OffsetTerm> terms = V32TestReference.offsetFixture(
                source,
                offset("café", 1, 0, 5),
                offset("1", 1, 6, 7),
                offset("z", 1, 10, 11)
        );

        assertEquals(List.of("Cafe\u0301", "\u2460", "Z"), terms.stream()
                .map(term -> source.substring(
                        term.range().start(),
                        term.range().end()
                ))
                .toList());
        assertEquals(
                List.of(offset("ffi", 1, 0, 1)),
                V32TestReference.offsetFixture(
                        "\uFB03",
                        offset("ffi", 1, 0, 1)
                )
        );
        assertEquals(
                List.of(
                        offset("primary", 1, 0, 4),
                        offset("alternative", 0, 0, 4),
                        offset("after-gap", 3, 7, 12)
                ),
                V32TestReference.offsetFixture(
                        "word   later",
                        offset("primary", 1, 0, 4),
                        offset("alternative", 0, 0, 4),
                        offset("after-gap", 3, 7, 12)
                )
        );
        assertThrows(IllegalArgumentException.class, () ->
                V32TestReference.offsetFixture(
                        "a\uD83D\uDE00b",
                        offset("broken", 1, 1, 2)
                ));
    }

    @Test
    void phraseWitnessPrefersLeastSlopThenEarliestOffsetTuple() {
        List<V32TestReference.PhraseSlot> slots = List.of(
                slot(0, "quick"),
                slot(1, "fox")
        );
        List<V32TestReference.Occurrence> document = List.of(
                occurrence("quick", 0, 0, 5),
                occurrence("fox", 3, 8, 11),
                occurrence("quick", 4, 12, 17),
                occurrence("fox", 5, 18, 21),
                occurrence("quick", 6, 22, 27),
                occurrence("fox", 7, 28, 31)
        );

        V32TestReference.PhraseWitness witness = V32TestReference.phraseWitness(
                slots,
                document
        ).orElseThrow();

        assertEquals(0L, witness.consumedSlop());
        assertEquals(new V32TestReference.Range(12, 21), witness.range());
        assertEquals(List.of(4, 5), witness.occurrences().stream()
                .map(V32TestReference.Occurrence::position)
                .toList());
    }

    @Test
    void fuzzySelectionPreservesExactPriorityAndDeterministicWeightedTie() {
        V32TestReference.FuzzySelection exact = V32TestReference.selectFuzzy(
                "cat",
                1,
                List.of(
                        scored("bat", 100.0, range(8, 11)),
                        scored("cat", 0.25, range(0, 3))
                )
        ).orElseThrow();
        assertEquals("cat", exact.term());
        assertEquals(List.of(range(0, 3)), exact.occurrences());

        V32TestReference.FuzzySelection tie = V32TestReference.selectFuzzy(
                "cat",
                1,
                List.of(
                        scored("cut", 3.0, range(12, 15)),
                        scored("bat", 3.0, range(4, 7))
                )
        ).orElseThrow();
        assertEquals("bat", tie.term());
        assertEquals(1, tie.distance());
        assertEquals(2.0, tie.weightedScore());
        assertEquals(List.of(range(4, 7)), tie.occurrences());
    }

    @Test
    void boolAndBoostCollectEveryMatchedMustAndShouldRange() {
        V32TestReference.EvidenceNode evidence = new V32TestReference.BoolEvidence(
                List.of(new V32TestReference.BoostEvidence(
                        leaf(true, fieldRange("body", 1, 3))
                )),
                List.of(
                        leaf(true, fieldRange("body", 3, 5)),
                        leaf(true, fieldRange("title", 0, 4)),
                        leaf(false)
                ),
                1
        );

        V32TestReference.EvidenceEvaluation evaluation =
                V32TestReference.evaluate(evidence);

        assertEquals(true, evaluation.matched());
        assertEquals(List.of(
                fieldRange("body", 1, 3),
                fieldRange("body", 3, 5),
                fieldRange("title", 0, 4)
        ), evaluation.ranges());
    }

    @Test
    void fragmentOracleKeepsAdjacentSpansAndMergesOnlyOverlappingWindows() {
        List<V32TestReference.Fragment> fragments = V32TestReference.fragments(
                "0123456789ABCDEFGHIJ",
                List.of(range(10, 12), range(2, 4), range(4, 6), range(3, 5)),
                1,
                1
        );

        assertEquals(List.of(new V32TestReference.Fragment(
                range(1, 7),
                "123456",
                List.of(range(2, 6))
        )), fragments);
        assertEquals(
                List.of(range(2, 4), range(4, 6)),
                V32TestReference.normalizeRanges(List.of(
                        range(2, 4),
                        range(4, 6)
                ))
        );
    }

    @Test
    void fragmentContextExpandsOutwardAtSurrogateBoundaries() {
        List<V32TestReference.Fragment> fragments = V32TestReference.fragments(
                "a\uD83D\uDE00b",
                List.of(range(3, 4)),
                1,
                3
        );

        assertEquals(List.of(new V32TestReference.Fragment(
                range(1, 4),
                "\uD83D\uDE00b",
                List.of(range(3, 4))
        )), fragments);
    }

    private static V32TestReference.OffsetTerm offset(
            String term,
            int increment,
            int start,
            int end
    ) {
        return new V32TestReference.OffsetTerm(
                term,
                increment,
                range(start, end)
        );
    }

    private static V32TestReference.PhraseSlot slot(
            int relativePosition,
            String... alternatives
    ) {
        return new V32TestReference.PhraseSlot(
                relativePosition,
                List.of(alternatives)
        );
    }

    private static V32TestReference.Occurrence occurrence(
            String term,
            int position,
            int start,
            int end
    ) {
        return new V32TestReference.Occurrence(
                term,
                position,
                range(start, end)
        );
    }

    private static V32TestReference.ScoredTerm scored(
            String term,
            double score,
            V32TestReference.Range... occurrences
    ) {
        return new V32TestReference.ScoredTerm(
                term,
                score,
                List.of(occurrences)
        );
    }

    private static V32TestReference.LeafEvidence leaf(
            boolean matched,
            V32TestReference.FieldRange... ranges
    ) {
        return new V32TestReference.LeafEvidence(matched, List.of(ranges));
    }

    private static V32TestReference.FieldRange fieldRange(
            String field,
            int start,
            int end
    ) {
        return new V32TestReference.FieldRange(field, range(start, end));
    }

    private static V32TestReference.Range range(int start, int end) {
        return new V32TestReference.Range(start, end);
    }
}
