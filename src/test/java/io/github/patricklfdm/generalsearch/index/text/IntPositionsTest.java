package io.github.patricklfdm.generalsearch.index.text;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class IntPositionsTest {
    @Test
    void copiesAndExposesSortedPrimitiveValuesWithoutArrayLeakage() {
        int[] supplied = {0, 3, 8};
        IntPositions positions = IntPositions.copyOf(supplied);
        supplied[1] = 99;

        assertEquals(3, positions.size());
        assertEquals(0, positions.get(0));
        assertEquals(3, positions.get(1));
        assertEquals(8, positions.get(2));
        assertTrue(positions.contains(3));
        assertFalse(positions.contains(4));
        assertThrows(ArrayIndexOutOfBoundsException.class, () -> positions.get(3));
    }

    @Test
    void enforcesStrictlyIncreasingNonNegativeValues() {
        assertThrows(IllegalArgumentException.class,
                () -> IntPositions.copyOf(new int[]{-1}));
        assertThrows(IllegalArgumentException.class,
                () -> IntPositions.copyOf(new int[]{1, 1}));
        assertThrows(IllegalArgumentException.class,
                () -> IntPositions.copyOf(new int[]{2, 1}));

        IntPositions.Builder builder = IntPositions.builder();
        assertThrows(IllegalArgumentException.class, () -> builder.add(-1));
        builder.add(1);
        builder.add(1);
        builder.add(4);
        assertEquals(IntPositions.copyOf(new int[]{1, 4}), builder.build());
        assertThrows(IllegalArgumentException.class, () -> builder.add(3));
    }

    @Test
    void hasStableValueEqualityHashCodeAndSequentialCompatibilityValues() {
        IntPositions first = IntPositions.copyOf(new int[]{0, 2, 5});
        IntPositions equal = IntPositions.copyOf(new int[]{0, 2, 5});
        IntPositions different = IntPositions.copyOf(new int[]{0, 2, 6});

        assertEquals(first, equal);
        assertEquals(first.hashCode(), equal.hashCode());
        assertNotEquals(first, different);
        assertEquals(IntPositions.copyOf(new int[]{0, 1, 2}),
                IntPositions.sequential(3));
        assertEquals(0, IntPositions.empty().size());
        assertEquals(IntPositions.empty(), IntPositions.copyOf(new int[0]));
        assertThrows(IllegalArgumentException.class,
                () -> IntPositions.sequential(-1));
    }
}
