package io.github.patricklfdm.generalsearch.analysis;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class OffsetAnalyzedTokenTest {
    @Test
    void preservesTheFrozenFourComponentShape() {
        OffsetAnalyzedToken token = new OffsetAnalyzedToken("term", 0, 2, 6);

        assertEquals("term", token.term());
        assertEquals(0, token.positionIncrement());
        assertEquals(2, token.startOffset());
        assertEquals(6, token.endOffset());
    }

    @Test
    void rejectsInvalidContextFreeValues() {
        assertThrows(IllegalArgumentException.class, () ->
                new OffsetAnalyzedToken(null, 1, 0, 1));
        assertThrows(IllegalArgumentException.class, () ->
                new OffsetAnalyzedToken("", 1, 0, 1));
        assertThrows(IllegalArgumentException.class, () ->
                new OffsetAnalyzedToken("term", -1, 0, 1));
        assertThrows(IllegalArgumentException.class, () ->
                new OffsetAnalyzedToken("term", 1, -1, 1));
        assertThrows(IllegalArgumentException.class, () ->
                new OffsetAnalyzedToken("term", 1, 1, 1));
        assertThrows(IllegalArgumentException.class, () ->
                new OffsetAnalyzedToken("term", 1, 2, 1));
    }
}
