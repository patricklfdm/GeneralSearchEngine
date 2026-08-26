package io.github.patricklfdm.generalsearch.index.text;

import static org.junit.jupiter.api.Assertions.assertFalse;
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
    }

    private static PostingList posting(int docId, int... positions) {
        return PostingList.empty().withPositions(
                docId,
                IntPositions.copyOf(positions)
        );
    }
}
