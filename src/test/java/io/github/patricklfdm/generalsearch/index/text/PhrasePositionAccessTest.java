package io.github.patricklfdm.generalsearch.index.text;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class PhrasePositionAccessTest {
    @Test
    void verifiesExactGapsRepeatedTermsAndAlternatives() {
        PostingList quick = posting(7, 3);
        PostingList fast = posting(7, 3);
        PostingList brown = posting(7, 5);
        PostingList repeated = posting(7, 3, 4);

        assertTrue(PhrasePositionAccess.matches(
                7,
                new int[]{0, 2},
                new PostingList[][]{{quick, fast}, {brown}},
                0
        ));
        assertFalse(PhrasePositionAccess.matches(
                7,
                new int[]{0, 1},
                new PostingList[][]{{quick}, {brown}},
                0
        ));
        assertTrue(PhrasePositionAccess.matches(
                7,
                new int[]{0, 1},
                new PostingList[][]{{repeated}, {repeated}},
                0
        ));
        assertFalse(PhrasePositionAccess.matches(
                7,
                new int[]{0, 2},
                new PostingList[][]{{repeated}, {repeated}},
                0
        ));
    }

    @Test
    void findsMinimumOrderedExtraGapFromEitherAnchorDirection() {
        PostingList alpha = posting(7, 0, 10, 20);
        PostingList beta = posting(7, 2, 13, 21);
        PostingList repeated = posting(7, 3, 5);

        assertEquals(0L, PhrasePositionAccess.minimumConsumedSlop(
                7,
                new int[]{0, 1},
                new PostingList[][]{{alpha}, {beta}},
                0,
                4
        ));
        assertEquals(0L, PhrasePositionAccess.minimumConsumedSlop(
                7,
                new int[]{0, 1},
                new PostingList[][]{{alpha}, {beta}},
                1,
                4
        ));
        assertEquals(1L, PhrasePositionAccess.minimumConsumedSlop(
                7,
                new int[]{0, 1},
                new PostingList[][]{{repeated}, {repeated}},
                0,
                1
        ));
        assertEquals(-1L, PhrasePositionAccess.minimumConsumedSlop(
                7,
                new int[]{0, 1},
                new PostingList[][]{{repeated}, {repeated}},
                0,
                0
        ));
    }

    @Test
    void rejectsContractionAndTranspositionAtEverySlop() {
        PostingList alphaAtZero = posting(4, 0);
        PostingList alphaAtOne = posting(4, 1);
        PostingList betaAtZero = posting(4, 0);
        PostingList betaAtOne = posting(4, 1);

        assertEquals(-1L, PhrasePositionAccess.minimumConsumedSlop(
                4,
                new int[]{0, 2},
                new PostingList[][]{{alphaAtZero}, {betaAtOne}},
                0,
                Integer.MAX_VALUE
        ));
        assertEquals(-1L, PhrasePositionAccess.minimumConsumedSlop(
                4,
                new int[]{0, 1},
                new PostingList[][]{{alphaAtOne}, {betaAtZero}},
                0,
                Integer.MAX_VALUE
        ));
    }

    @Test
    void handlesOneSlotAlternativesAndPositionBoundaries() {
        PostingList absent = posting(2, 9);
        PostingList present = posting(3, 9);
        assertEquals(0L, PhrasePositionAccess.minimumConsumedSlop(
                3,
                new int[]{0},
                new PostingList[][]{{absent, present}},
                0,
                0
        ));

        PostingList atZero = posting(3, 0);
        PostingList atMaximum = posting(3, Integer.MAX_VALUE);
        assertEquals(0L, PhrasePositionAccess.minimumConsumedSlop(
                3,
                new int[]{0, Integer.MAX_VALUE},
                new PostingList[][]{{atZero}, {atMaximum}},
                1,
                Integer.MAX_VALUE
        ));
    }

    @Test
    void treatsRequiredPositionOverflowAndUnderflowAsNonMatches() {
        PostingList atZero = posting(3, 0);
        PostingList atOne = posting(3, 1);
        PostingList atMaximum = posting(3, Integer.MAX_VALUE);

        assertFalse(PhrasePositionAccess.matches(
                3,
                new int[]{0, Integer.MAX_VALUE},
                new PostingList[][]{{atOne}, {atMaximum}},
                0
        ));
        assertFalse(PhrasePositionAccess.matches(
                3,
                new int[]{0, Integer.MAX_VALUE},
                new PostingList[][]{{atZero}, {atZero}},
                1
        ));
    }

    @Test
    void validatesTheUnsupportedBridgeBoundary() {
        PostingList posting = posting(1, 0);
        assertThrows(
                IllegalArgumentException.class,
                () -> PhrasePositionAccess.matches(
                        -1,
                        new int[]{0},
                        new PostingList[][]{{posting}},
                        0
                )
        );
        assertThrows(
                IllegalArgumentException.class,
                () -> PhrasePositionAccess.minimumConsumedSlop(
                        1,
                        new int[]{0},
                        new PostingList[][]{{posting}},
                        0,
                        -1
                )
        );
        assertThrows(
                IllegalArgumentException.class,
                () -> PhrasePositionAccess.matches(
                        1,
                        new int[]{1},
                        new PostingList[][]{{posting}},
                        0
                )
        );
        assertThrows(
                IllegalArgumentException.class,
                () -> PhrasePositionAccess.matches(
                        1,
                        new int[]{0},
                        new PostingList[][]{{}},
                        0
                )
        );

        NullPointerException missingSlot = assertThrows(
                NullPointerException.class,
                () -> PhrasePositionAccess.matches(
                        1,
                        new int[]{0},
                        new PostingList[][]{null},
                        0
                )
        );
        assertEquals("alternativesBySlot[0]", missingSlot.getMessage());

        NullPointerException missingAlternative = assertThrows(
                NullPointerException.class,
                () -> PhrasePositionAccess.matches(
                        1,
                        new int[]{0},
                        new PostingList[][]{{null}},
                        0
                )
        );
        assertEquals(
                "alternativesBySlot[0][0]",
                missingAlternative.getMessage()
        );
    }

    private static PostingList posting(int docId, int... positions) {
        return PostingList.empty().withPositions(
                docId,
                IntPositions.copyOf(positions)
        );
    }
}
