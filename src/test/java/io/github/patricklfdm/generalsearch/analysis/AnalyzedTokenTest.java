package io.github.patricklfdm.generalsearch.analysis;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.RecordComponent;
import java.util.Arrays;
import org.junit.jupiter.api.Test;

class AnalyzedTokenTest {
    @Test
    void acceptsZeroAndPositivePositionIncrements() {
        assertEquals(0, new AnalyzedToken("synonym", 0).positionIncrement());
        assertEquals(1, new AnalyzedToken("next", 1).positionIncrement());
        assertEquals(
                Integer.MAX_VALUE,
                new AnalyzedToken("large-gap", Integer.MAX_VALUE).positionIncrement()
        );
        assertEquals(" ", new AnalyzedToken(" ", 1).term());
    }

    @Test
    void rejectsInvalidLocalState() {
        assertThrows(IllegalArgumentException.class, () -> new AnalyzedToken(null, 1));
        assertThrows(IllegalArgumentException.class, () -> new AnalyzedToken("", 1));
        assertThrows(IllegalArgumentException.class, () -> new AnalyzedToken("term", -1));
    }

    @Test
    void exposesFrozenRecordComponentShape() {
        assertTrue(AnalyzedToken.class.isRecord());
        RecordComponent[] components = AnalyzedToken.class.getRecordComponents();

        assertArrayEquals(
                new String[]{"term", "positionIncrement"},
                Arrays.stream(components).map(RecordComponent::getName).toArray(String[]::new)
        );
        assertArrayEquals(
                new Class<?>[]{String.class, int.class},
                Arrays.stream(components).map(RecordComponent::getType).toArray(Class<?>[]::new)
        );
    }
}
