package io.github.patricklfdm.generalsearch.bitmap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.util.HashMap;
import java.util.Map;
import java.util.Random;
import org.junit.jupiter.api.Test;

class PersistentBlockTreeTest {
    @Test
    void preservesPreviousVersionsAndSupportsSparseIndexes() {
        PersistentBlockTree<String> empty = new PersistentBlockTree<>();
        PersistentBlockTree<String> first = empty.with(31, "a");
        PersistentBlockTree<String> second = first.with(32, "b").with(1_000_000, "c");

        assertNull(empty.get(31));
        assertEquals("a", first.get(31));
        assertNull(first.get(32));
        assertEquals("a", second.get(31));
        assertEquals("b", second.get(32));
        assertEquals("c", second.get(1_000_000));
    }

    @Test
    void agreesWithAMutableMapUnderRandomUpdates() {
        PersistentBlockTree<Integer> tree = new PersistentBlockTree<>();
        Map<Integer, Integer> expected = new HashMap<>();
        Random random = new Random(42);
        for (int i = 0; i < 10_000; i++) {
            int index = random.nextInt(2_000_000);
            Integer value = random.nextBoolean() ? random.nextInt() : null;
            tree = tree.with(index, value);
            if (value == null) {
                expected.remove(index);
            } else {
                expected.put(index, value);
            }
        }
        PersistentBlockTree<Integer> actual = tree;
        expected.forEach((index, value) -> assertEquals(value, actual.get(index)));
    }
}
