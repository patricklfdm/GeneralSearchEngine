package io.github.patricklfdm.generalsearch.internal.index;

import static org.junit.jupiter.api.Assertions.assertEquals;
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
}
