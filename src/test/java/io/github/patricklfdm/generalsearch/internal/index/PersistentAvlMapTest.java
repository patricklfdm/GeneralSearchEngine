package io.github.patricklfdm.generalsearch.internal.index;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.TreeMap;
import org.junit.jupiter.api.Test;

class PersistentAvlMapTest {
    @Test
    void randomizedUpdatesAndRangesMatchTreeMap() {
        PersistentAvlMap<Integer, String> actual = PersistentAvlMap.empty();
        TreeMap<Integer, String> expected = new TreeMap<>();
        Random random = new Random(31);

        for (int operation = 0; operation < 20_000; operation++) {
            int key = random.nextInt(2_000);
            if (random.nextBoolean()) {
                String value = "value-" + random.nextInt(200);
                actual = actual.with(key, value);
                expected.put(key, value);
            } else {
                actual = actual.without(key);
                expected.remove(key);
            }
        }

        assertEquals(expected.size(), actual.size());
        for (int key = 0; key < 2_000; key++) {
            assertEquals(expected.get(key), actual.get(key), "key=" + key);
        }

        List<String> range = new ArrayList<>();
        actual.forEachInRange(200, true, 800, false,
                (key, value) -> range.add(key + "=" + value));
        List<String> expectedRange = expected.subMap(200, true, 800, false)
                .entrySet().stream()
                .map(entry -> entry.getKey() + "=" + entry.getValue())
                .toList();
        assertEquals(expectedRange, range);
        assertTrue(actual.height() < 30, "AVL height=" + actual.height());
    }

    @Test
    void unchangedOperationsReuseTheSameTreeAndOldTreesRemainIsolated() {
        PersistentAvlMap<Integer, String> base = PersistentAvlMap
                .<Integer, String>empty()
                .with(1, "one")
                .with(2, "two");

        assertSame(base, base.with(1, "one"));
        assertSame(base, base.without(3));

        PersistentAvlMap<Integer, String> updated = base.with(1, "changed").without(2);
        assertEquals("one", base.get(1));
        assertEquals("two", base.get(2));
        assertEquals("changed", updated.get(1));
        assertEquals(1, updated.size());
    }

    @Test
    void weightedRangesMatchTreeMapAcrossRandomBoundsAndUpdates() {
        PersistentAvlMap<Integer, Integer> actual =
                PersistentAvlMap.empty(Integer::longValue);
        TreeMap<Integer, Integer> expected = new TreeMap<>();
        Random random = new Random(47);

        for (int operation = 0; operation < 5_000; operation++) {
            int key = random.nextInt(500);
            if (random.nextBoolean()) {
                int weight = random.nextInt(201);
                actual = actual.with(key, weight);
                expected.put(key, weight);
            } else {
                actual = actual.without(key);
                expected.remove(key);
            }

            if (operation % 25 == 0) {
                Integer lower = random.nextBoolean() ? null : random.nextInt(550) - 25;
                Integer upper = random.nextBoolean() ? null : random.nextInt(550) - 25;
                boolean lowerInclusive = random.nextBoolean();
                boolean upperInclusive = random.nextBoolean();
                assertWeightedRange(
                        expected,
                        actual,
                        lower,
                        lowerInclusive,
                        upper,
                        upperInclusive
                );
            }
        }

        assertWeightedRange(expected, actual, null, true, null, true);
        assertWeightedRange(expected, actual, 100, true, 100, true);
        assertWeightedRange(expected, actual, 100, false, 100, true);
        assertWeightedRange(expected, actual, 300, true, 200, true);
    }

    @Test
    void weightedTreesPreserveOldSnapshotsAndRejectNegativeWeights() {
        PersistentAvlMap<Integer, Integer> base =
                PersistentAvlMap.<Integer, Integer>empty(Integer::longValue)
                        .with(1, 10)
                        .with(2, 20);
        PersistentAvlMap<Integer, Integer> updated = base.with(1, 100).without(2);

        assertEquals(30L, base.aggregateWeightInRange(null, true, null, true));
        assertEquals(2, base.entryCountInRange(null, true, null, true));
        assertEquals(100L, updated.aggregateWeightInRange(null, true, null, true));
        assertEquals(1, updated.entryCountInRange(null, true, null, true));
        assertThrows(IllegalArgumentException.class, () -> base.with(3, -1));
    }

    private static void assertWeightedRange(
            TreeMap<Integer, Integer> expected,
            PersistentAvlMap<Integer, Integer> actual,
            Integer lower,
            boolean lowerInclusive,
            Integer upper,
            boolean upperInclusive
    ) {
        boolean empty = lower != null && upper != null
                && (lower > upper || lower.equals(upper)
                && (!lowerInclusive || !upperInclusive));
        long expectedWeight = 0L;
        int expectedCount = 0;
        if (!empty) {
            for (var entry : expected.entrySet()) {
                boolean aboveLower = lower == null || entry.getKey() > lower
                        || lowerInclusive && entry.getKey().equals(lower);
                boolean belowUpper = upper == null || entry.getKey() < upper
                        || upperInclusive && entry.getKey().equals(upper);
                if (aboveLower && belowUpper) {
                    expectedWeight += entry.getValue();
                    expectedCount++;
                }
            }
        }

        assertEquals(expectedWeight, actual.aggregateWeightInRange(
                lower, lowerInclusive, upper, upperInclusive
        ));
        assertEquals(expectedCount, actual.entryCountInRange(
                lower, lowerInclusive, upper, upperInclusive
        ));
    }
}
