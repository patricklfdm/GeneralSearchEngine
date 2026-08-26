package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Random;
import org.junit.jupiter.api.Test;

class BoundedOptimalStringAlignmentTest {
    private static final long SEED = 0x4f53415f5633L;
    private static final int[] ALPHABET = {
            'a', 'b', 'c', 'd', 0x00e9, 0xe000, 0x10000, 0x1f600
    };

    @Test
    void appliesAutoThresholdsToUnicodeCodePointLength() {
        assertEquals(0, BoundedOptimalStringAlignment.autoMaxEdits("a"));
        assertEquals(0, BoundedOptimalStringAlignment.autoMaxEdits("ab"));
        assertEquals(1, BoundedOptimalStringAlignment.autoMaxEdits("abc"));
        assertEquals(1, BoundedOptimalStringAlignment.autoMaxEdits("abcde"));
        assertEquals(2, BoundedOptimalStringAlignment.autoMaxEdits("abcdef"));
        assertEquals(2, BoundedOptimalStringAlignment.autoMaxEdits("abcdefghijkl"));
        assertEquals(0, BoundedOptimalStringAlignment.autoMaxEdits("😀😀"));
        assertEquals(1, BoundedOptimalStringAlignment.autoMaxEdits("😀😀😀"));
    }

    @Test
    void supportsEveryFrozenEditAndReturnsOneOutOfRangeSentinel() {
        assertEquals(0, distance("restaurant", "restaurant", 2));
        assertEquals(1, distance("jav", "java", 1));
        assertEquals(1, distance("java", "jav", 1));
        assertEquals(1, distance("apple", "applr", 1));
        assertEquals(1, distance("teh", "the", 1));
        assertEquals(1, distance("😀ab", "😀ba", 1));
        assertEquals(2, distance("abc", "axd", 2));
        assertEquals(2, distance("abc", "axd", 1));
        assertEquals(3, distance("abc", "uvwxyz", 2));
    }

    @Test
    void comparesTheNumericCodePointSequenceRatherThanUtf16Units() {
        String privateUse = "ab\ue000";
        String supplementary = "ab\ud800\udc00";

        assertTrue(privateUse.compareTo(supplementary) > 0);
        assertTrue(BoundedOptimalStringAlignment.compareCodePoints(
                privateUse,
                supplementary
        ) < 0);
        assertEquals(0, BoundedOptimalStringAlignment.compareCodePoints("😀a", "😀a"));
    }

    @Test
    void validatesTheInternalBoundedOperation() {
        assertThrows(
                NullPointerException.class,
                () -> BoundedOptimalStringAlignment.distance(null, "a", 1)
        );
        assertThrows(
                NullPointerException.class,
                () -> BoundedOptimalStringAlignment.distance("a", null, 1)
        );
        assertThrows(
                IllegalArgumentException.class,
                () -> BoundedOptimalStringAlignment.distance("a", "b", -1)
        );
        assertThrows(
                IllegalArgumentException.class,
                () -> BoundedOptimalStringAlignment.distance("a", "b", 3)
        );
    }

    @Test
    void reusableWorkspaceHonorsLogicalLengthsAndIgnoresBufferTails() {
        int[] queryBuffer = {'t', 'e', 'h', 0x1f600, 'x'};
        int[] candidateBuffer = {'t', 'h', 'e', 0xe000, 'y', 'z'};
        BoundedOptimalStringAlignment.Workspace workspace =
                new BoundedOptimalStringAlignment.Workspace();

        assertEquals(1, BoundedOptimalStringAlignment.distance(
                queryBuffer,
                3,
                candidateBuffer,
                3,
                1,
                workspace
        ));

        candidateBuffer[0] = 't';
        candidateBuffer[1] = 'e';
        candidateBuffer[2] = 'h';
        candidateBuffer[3] = 's';
        assertEquals(0, BoundedOptimalStringAlignment.distance(
                queryBuffer,
                3,
                candidateBuffer,
                3,
                2,
                workspace
        ));
        assertEquals(1, BoundedOptimalStringAlignment.distance(
                queryBuffer,
                3,
                candidateBuffer,
                4,
                1,
                workspace
        ));
    }

    @Test
    void randomizedBoundedDistanceMatchesFullMatrixOsa() {
        Random random = new Random(SEED);
        for (int iteration = 0; iteration < 20_000; iteration++) {
            String left = randomTerm(random, random.nextInt(9));
            String right = random.nextInt(4) == 0
                    ? adjacentSwap(left, random)
                    : randomTerm(random, random.nextInt(9));
            int reference = FuzzyTestReference.optimalStringAlignmentDistance(
                    left,
                    right
            );
            for (int bound = 0; bound <= 2; bound++) {
                int expected = reference <= bound ? reference : bound + 1;
                assertEquals(
                        expected,
                        BoundedOptimalStringAlignment.distance(left, right, bound),
                        "seed=" + SEED + ", iteration=" + iteration
                                + ", bound=" + bound + ", left=" + left
                                + ", right=" + right
                );
            }
        }
    }

    private static int distance(String left, String right, int maxEdits) {
        return BoundedOptimalStringAlignment.distance(left, right, maxEdits);
    }

    private static String randomTerm(Random random, int length) {
        StringBuilder term = new StringBuilder();
        for (int index = 0; index < length; index++) {
            term.appendCodePoint(ALPHABET[random.nextInt(ALPHABET.length)]);
        }
        return term.toString();
    }

    private static String adjacentSwap(String value, Random random) {
        int[] points = value.codePoints().toArray();
        if (points.length < 2) {
            return value;
        }
        int index = random.nextInt(points.length - 1);
        int held = points[index];
        points[index] = points[index + 1];
        points[index + 1] = held;
        StringBuilder swapped = new StringBuilder();
        for (int point : points) {
            swapped.appendCodePoint(point);
        }
        return swapped.toString();
    }
}
