package io.github.patricklfdm.generalsearch.bitmap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.BitSet;
import java.util.List;
import java.util.Random;
import org.junit.jupiter.api.Test;

class ImmutableBitmapTest {
    @Test
    void supportsSetClearAndSetOperationsAcrossBlockBoundaries() {
        ImmutableBitmap left = bitmapOf(0, 31, 32, 1_023, 1_024, 80_000);
        ImmutableBitmap right = bitmapOf(32, 1_024, 2_048, 80_000);

        assertEquals(List.of(32, 1_024, 80_000), values(left.and(right)));
        assertEquals(List.of(0, 31, 1_023), values(left.andNot(right)));
        assertEquals(List.of(0, 31, 32, 1_023, 1_024, 2_048, 80_000), values(left.or(right)));
        assertFalse(left.withClear(80_000).get(80_000));
        assertTrue(left.get(80_000));
    }

    @Test
    void agreesWithBitSetUnderRandomOperations() {
        ImmutableBitmap actual = ImmutableBitmap.empty();
        BitSet expected = new BitSet();
        Random random = new Random(7);
        for (int i = 0; i < 20_000; i++) {
            int docId = random.nextInt(100_000);
            if (random.nextBoolean()) {
                actual = actual.withSet(docId);
                expected.set(docId);
            } else {
                actual = actual.withClear(docId);
                expected.clear(docId);
            }
        }
        assertEquals(expected.cardinality(), actual.cardinality());
        for (int bit = expected.nextSetBit(0); bit >= 0; bit = expected.nextSetBit(bit + 1)) {
            assertTrue(actual.get(bit));
        }
    }

    @Test
    void bulkUnionAgreesWithBitSetForSparseDenseAndOverlappingSources() {
        Random random = new Random(19);
        BitSet expected = new BitSet();
        ImmutableBitmapBuilder accumulator =
                new ImmutableBitmapBuilder(ImmutableBitmap.empty());

        for (int source = 0; source < 80; source++) {
            ImmutableBitmapBuilder sourceBuilder =
                    new ImmutableBitmapBuilder(ImmutableBitmap.empty());
            int values = source % 4 == 0 ? 4_000 : 40;
            for (int index = 0; index < values; index++) {
                int docId = random.nextInt(250_000);
                sourceBuilder.set(docId);
                expected.set(docId);
            }
            accumulator.or(sourceBuilder.build());
        }

        ImmutableBitmap actual = accumulator.build();
        assertEquals(expected.cardinality(), actual.cardinality());
        for (int docId = 0; docId < 250_000; docId++) {
            assertEquals(expected.get(docId), actual.get(docId), "docId=" + docId);
        }
    }

    @Test
    void builderReusesBaseWhenOperationsDoNotChangeItsContents() {
        ImmutableBitmap base = bitmapOf(1, 1_024, 80_000);

        ImmutableBitmapBuilder unchanged = new ImmutableBitmapBuilder(base);
        unchanged.set(1);
        unchanged.or(base);
        assertSame(base, unchanged.build());

        ImmutableBitmapBuilder reverted = new ImmutableBitmapBuilder(base);
        reverted.clear(1_024);
        reverted.set(1_024);
        assertSame(base, reverted.build());

        ImmutableBitmapBuilder restoredByUnion = new ImmutableBitmapBuilder(base);
        restoredByUnion.clear(80_000);
        restoredByUnion.or(base);
        assertSame(base, restoredByUnion.build());
    }

    private static ImmutableBitmap bitmapOf(int... values) {
        ImmutableBitmap bitmap = ImmutableBitmap.empty();
        for (int value : values) {
            bitmap = bitmap.withSet(value);
        }
        return bitmap;
    }

    private static List<Integer> values(ImmutableBitmap bitmap) {
        List<Integer> values = new ArrayList<>();
        bitmap.forEachSetBit(values::add);
        return values;
    }
}
