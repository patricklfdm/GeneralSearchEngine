package io.github.patricklfdm.generalsearch.internal.index;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import org.junit.jupiter.api.Test;

class ImmutableOverlayMapTest {
    @Test
    void randomizedPublicationsMatchHashMapAndKeepHistoryBounded() {
        ImmutableOverlayMap<Integer, String> actual = ImmutableOverlayMap.empty();
        Map<Integer, String> expected = new HashMap<>();
        Random random = new Random(29);

        for (int publication = 0; publication < 250; publication++) {
            ImmutableOverlayMap<Integer, String> previous = actual;
            Map<Integer, String> replacements = new HashMap<>();
            Set<Integer> removals = new HashSet<>();
            for (int change = 0; change < 7; change++) {
                int key = random.nextInt(500);
                if (random.nextBoolean()) {
                    String value = "value-" + publication + '-' + change;
                    removals.remove(key);
                    replacements.put(key, value);
                    expected.put(key, value);
                } else {
                    replacements.remove(key);
                    removals.add(key);
                    expected.remove(key);
                }
            }
            String retainedZero = previous.get(0);
            actual = actual.withChanges(replacements, removals);

            assertEquals(retainedZero, previous.get(0));
            assertEquals(expected.size(), actual.size());
            assertTrue(actual.depth() <= 12);
            for (int key = 0; key < 500; key++) {
                assertEquals(expected.get(key), actual.get(key), "key=" + key);
            }
        }
    }

    @Test
    void ineffectiveChangesReuseTheSameDictionary() {
        ImmutableOverlayMap<String, Integer> base = ImmutableOverlayMap
                .<String, Integer>empty()
                .withChanges(Map.of("one", 1), Set.of());

        assertSame(base, base.withChanges(Map.of("one", 1), Set.of("missing")));
        assertNull(base.get("missing"));
    }
}
